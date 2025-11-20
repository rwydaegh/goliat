"""Web GUI Bridge for forwarding GUI messages to monitoring dashboard."""

import time
import threading
import logging
from concurrent.futures import ThreadPoolExecutor
from queue import Queue, Empty
from typing import Dict, Any, Optional, Callable

from goliat.logging_manager import LoggingMixin
from goliat.utils.http_client import HTTPClient, REQUESTS_AVAILABLE
from goliat.utils.message_sanitizer import MessageSanitizer

try:
    import requests
except ImportError:
    requests = None  # type: ignore


class WebGUIBridge(LoggingMixin):
    """Bridges GUI messages to web monitoring dashboard.

    Receives messages via enqueue() and forwards them to the dashboard API.
    Uses an internal queue to decouple from the multiprocessing queue.
    Throttles messages to prevent overwhelming the API.
    """

    def __init__(self, server_url: str, machine_id: str, throttle_hz: float = 10.0):
        """Initialize the web GUI bridge.

        Args:
            server_url: Base URL of the monitoring dashboard (e.g., https://goliat-monitoring.vercel.app)
            machine_id: Unique identifier for this machine (typically IP address)
            throttle_hz: Maximum message rate in Hz (default: 10 messages/second)
        """
        if not REQUESTS_AVAILABLE:
            raise ImportError("requests library is required for WebGUIBridge. Install with: pip install requests")

        self.server_url = server_url.rstrip("/")
        self.machine_id = machine_id
        self.throttle_interval = 1.0 / throttle_hz
        self.internal_queue: Queue = Queue()
        self.running = False
        self.thread: Optional[threading.Thread] = None
        # Use the main verbose/progress loggers so messages appear in log files
        self.verbose_logger = logging.getLogger("verbose")
        self.progress_logger = logging.getLogger("progress")
        self.gui = None
        self.is_connected = False
        self.last_heartbeat_success = False
        self.connection_callback: Optional[Callable[[bool], None]] = None
        self._system_info: Optional[Dict[str, Any]] = None
        self.executor: Optional[ThreadPoolExecutor] = None

        # Sequence number for ordering batches (thread-safe)
        self._sequence_lock = threading.Lock()
        self._sequence_counter = 0

        # HTTP client for API calls
        self.http_client = HTTPClient(self.server_url, self.machine_id, self.verbose_logger)

    def enqueue(self, message: Dict[str, Any]) -> None:
        """Enqueue a message to be forwarded to the dashboard.

        This method is called by QueueHandler after processing messages for the GUI.
        Messages are stored in an internal queue and forwarded asynchronously.

        Args:
            message: GUI message dictionary with 'type' and other fields
        """
        if not self.running:
            self._log(f"WebGUIBridge not running, dropping message: {message.get('type', 'unknown')}", level="verbose", log_type="warning")
            return

        try:
            self.internal_queue.put_nowait(message)
            # Debug: Log enqueued messages
            msg_type = message.get("type", "unknown")
            if msg_type == "status":
                msg_text = message.get("message", "")[:50]  # First 50 chars
                self._log(f"[DEBUG] Enqueued status: {msg_text}", level="verbose")
        except Exception as e:
            self._log(f"Failed to enqueue message: {e}", level="verbose", log_type="warning")

    def start(self) -> None:
        """Start the forwarding thread and send initial heartbeat."""
        if self.running:
            return

        self.running = True
        # Start thread pool for async HTTP requests
        self.executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="web_bridge_http")
        self.thread = threading.Thread(target=self._forward_loop, daemon=True)
        self.thread.start()
        self._log(f"WebGUIBridge started: {self.server_url}, machine_id={self.machine_id}", level="verbose")

        # Send initial heartbeat to register worker
        # Wait a bit for it to complete and call callback with initial status
        self._send_heartbeat(self._system_info)
        # Also trigger callback with current status (even if unchanged) so GUI gets initial state
        if self.connection_callback:
            self.connection_callback(self.is_connected)

    def _send_heartbeat(self, system_info: Optional[Dict[str, Any]] = None) -> None:
        """Send a heartbeat to register/update worker status.

        Args:
            system_info: Optional system information dict with gpuName, cpuCores, totalRamGB, hostname
        """
        was_connected = self.is_connected
        success = self.http_client.post_heartbeat(system_info)

        if success:
            self.is_connected = True
            self.last_heartbeat_success = True
            if not was_connected:
                self._log("Web dashboard connection established", level="verbose")
            if self.connection_callback:
                self.connection_callback(True)
        else:
            self.is_connected = False
            self.last_heartbeat_success = False
            if was_connected:
                self._log("Lost connection to web dashboard", level="verbose", log_type="warning")
            else:
                self._log(f"Cannot connect to web dashboard: {self.server_url}", level="verbose")
            if self.connection_callback:
                self.connection_callback(False)

    def set_system_info(self, system_info: Dict[str, Any]) -> None:
        """Set system information to be sent with heartbeats.

        Args:
            system_info: Dict with gpuName, cpuCores, totalRamGB, hostname
        """
        self._system_info = system_info

    def send_heartbeat_with_system_info(self, system_info: Dict[str, Any]) -> None:
        """Send a heartbeat with system information.

        Args:
            system_info: Dict with gpuName, cpuCores, totalRamGB, hostname
        """
        self._send_heartbeat(system_info)

    def stop(self) -> None:
        """Stop the forwarding thread and flush any pending batches."""
        self.running = False

        # Flush any remaining messages in the queue before stopping
        # Give the thread a moment to process remaining messages
        if self.thread:
            self.thread.join(timeout=2.0)

        # Flush any remaining messages from internal queue
        remaining = []
        try:
            while True:
                msg = self.internal_queue.get_nowait()
                remaining.append(msg)
        except Exception:
            pass

        if remaining:
            self._log(f"Flushing {len(remaining)} remaining messages on stop", level="verbose")
            # Try to send remaining messages synchronously
            status_msgs = [m for m in remaining if m.get("type") == "status"]
            if status_msgs:
                try:
                    self._send_log_batch_sync(status_msgs)
                except Exception as e:
                    self._log(f"Failed to flush final batch: {e}", level="verbose", log_type="warning")

        if self.executor:
            self.executor.shutdown(wait=True, cancel_futures=False)  # Wait for pending requests
        self._log("WebGUIBridge stopped", level="verbose")

    def _forward_loop(self) -> None:
        """Main loop that forwards messages from internal queue to API.

        Batches log messages for efficiency, sends progress updates immediately.
        """
        last_throttled_send_time = 0.0
        last_heartbeat_time = 0.0
        heartbeat_interval = 30.0  # Send heartbeat every 30 seconds
        throttle_interval_fast = 0.02  # 50 Hz for progress updates

        # Batching for log messages
        log_batch = []
        batch_interval = 0.3  # Send batched logs every 300ms
        last_batch_send = time.time()

        # Debug counters
        message_counts = {}
        last_debug_time = time.time()

        while self.running:
            try:
                current_time = time.time()

                # Send periodic heartbeat
                if current_time - last_heartbeat_time >= heartbeat_interval:
                    self._send_heartbeat(self._system_info)
                    last_heartbeat_time = current_time

                # Send batched logs if enough time has passed OR if we've been waiting too long
                time_since_last_batch = current_time - last_batch_send
                if log_batch and (time_since_last_batch >= batch_interval or time_since_last_batch >= 1.0):
                    # If we've been waiting more than 1 second, send immediately (don't wait for 300ms)
                    reason = "timeout (1s)" if time_since_last_batch >= 1.0 else "timeout (300ms)"
                    self._log(f"[DEBUG] Sending batch of {len(log_batch)} messages ({reason})", level="verbose")
                    self._send_log_batch(log_batch)
                    message_counts["status_batched"] = message_counts.get("status_batched", 0) + len(log_batch)
                    log_batch = []
                    last_batch_send = current_time

                # Try to get a message (non-blocking)
                try:
                    message = self.internal_queue.get(timeout=0.01)
                except Empty:
                    # No message, but check if we should flush batch anyway
                    if log_batch and (current_time - last_batch_send >= batch_interval):
                        continue  # Will send batch on next iteration
                    time.sleep(0.01)
                    continue

                message_type = message.get("type", "")

                # Debug logging: count messages by type
                message_counts[message_type] = message_counts.get(message_type, 0) + 1

                # Batch status (log) messages, send others immediately
                if message_type == "status":
                    log_batch.append(message)
                    self._log(f"[DEBUG] Added to batch (size={len(log_batch)}): {message.get('message', '')[:50]}", level="verbose")
                    # If batch is getting large, send immediately
                    if len(log_batch) >= 20:
                        self._log(f"[DEBUG] Sending batch of {len(log_batch)} messages (size limit)", level="verbose")
                        self._send_log_batch(log_batch)
                        message_counts["status_batched"] = message_counts.get("status_batched", 0) + len(log_batch)
                        log_batch = []
                        last_batch_send = current_time
                elif message_type == "gui_screenshots":
                    # Send screenshots immediately via dedicated endpoint (don't batch)
                    self._send_screenshots(message)
                else:
                    # Send progress/profiler updates immediately
                    should_throttle = message_type in ["overall_progress", "stage_progress", "profiler_update"]
                    if should_throttle:
                        time_since_last_send = current_time - last_throttled_send_time
                        if time_since_last_send < throttle_interval_fast:
                            time.sleep(throttle_interval_fast - time_since_last_send)
                        last_throttled_send_time = time.time()
                    self._send_message(message)

                # Debug: Print message stats every 10 seconds
                if current_time - last_debug_time > 10.0:
                    if log_batch:
                        self._log(f"WebGUI stats (last 10s): {message_counts}, pending logs: {len(log_batch)}", level="verbose")
                    else:
                        self._log(f"WebGUI stats (last 10s): {message_counts}", level="verbose")
                    message_counts = {}
                    last_debug_time = current_time

            except Exception as e:
                self._log(f"Error in forward loop: {e}", level="verbose", log_type="error")
                # Try to flush batch even on error
                if log_batch:
                    self._log(f"[DEBUG] Flushing {len(log_batch)} messages after error", level="verbose")
                    try:
                        self._send_log_batch(log_batch)
                        log_batch = []
                    except Exception as flush_error:
                        self._log(f"Failed to flush batch after error: {flush_error}", level="verbose", log_type="error")
                time.sleep(1.0)  # Wait before retrying

        # Flush any remaining batch when loop exits
        if log_batch:
            self._log(f"[DEBUG] Flushing {len(log_batch)} messages on loop exit", level="verbose")
            try:
                self._send_log_batch_sync(log_batch)
            except Exception as e:
                self._log(f"Failed to flush final batch on exit: {e}", level="verbose", log_type="error")

    def _send_log_batch(self, log_messages: list[Dict[str, Any]]) -> None:
        """Send a batch of log messages to the dashboard API (async).

        Args:
            log_messages: List of status/log message dictionaries
        """
        if not self.executor or not log_messages:
            return

        # Submit to thread pool for async execution (non-blocking)
        self.executor.submit(self._send_log_batch_sync, log_messages)

    def _send_log_batch_sync(self, log_messages: list[Dict[str, Any]]) -> None:
        """Synchronous implementation of log batch sending (runs in thread pool).

        Args:
            log_messages: List of status/log message dictionaries
        """
        if not log_messages:
            return

        # Get next sequence number (thread-safe) for ordering batches
        with self._sequence_lock:
            sequence = self._sequence_counter
            self._sequence_counter += 1

        # Add per-message index within batch to preserve order when timestamps are identical
        for idx, msg in enumerate(log_messages):
            msg["batch_index"] = idx

        batch_message = {
            "type": "log_batch",
            "logs": log_messages,
            "sequence": sequence,  # Sequence number for proper ordering when batches arrive out of order
        }

        # Debug: Log what we're sending
        msg_previews = [f"{m.get('message', '')[:30]}..." for m in log_messages[:3]]
        self._log(f"[DEBUG] Sending batch seq={sequence} with {len(log_messages)} messages: {msg_previews}", level="verbose")

        # Retry logic for failed requests (up to 3 attempts)
        max_retries = 3
        retry_delay = 0.5  # Start with 500ms delay
        success = False

        for attempt in range(max_retries):
            success = self.http_client.post_gui_update(batch_message)
            if success:
                self.is_connected = True
                self._log(f"[DEBUG] Batch seq={sequence} sent successfully (attempt {attempt + 1})", level="verbose")
                break
            else:
                if attempt < max_retries - 1:
                    self._log(
                        f"[DEBUG] Batch seq={sequence} failed (attempt {attempt + 1}/{max_retries}), retrying in {retry_delay}s...",
                        level="verbose",
                        log_type="warning",
                    )
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    self._log(
                        f"[DEBUG] Batch seq={sequence} FAILED after {max_retries} attempts - MESSAGES LOST",
                        level="verbose",
                        log_type="error",
                    )
                    # Log the lost messages for debugging
                    for i, msg in enumerate(log_messages[:5]):  # Log first 5 messages
                        self._log(f"[DEBUG] Lost message {i + 1}: {msg.get('message', '')[:50]}", level="verbose", log_type="error")

    def _send_message(self, message: Dict[str, Any]) -> None:
        """Send a single message to the dashboard API (async).

        Args:
            message: GUI message dictionary
        """
        if not self.executor:
            return

        # Submit to thread pool for async execution (non-blocking)
        self.executor.submit(self._send_message_sync, message)

    def _send_screenshots(self, message: Dict[str, Any]) -> None:
        """Send screenshots to the dashboard API (async).

        Args:
            message: Message dictionary with 'screenshots' key containing tab name -> bytes mapping
        """
        if not self.executor or "screenshots" not in message:
            return

        # Submit to thread pool for async execution (non-blocking)
        self.executor.submit(self._send_screenshots_sync, message.get("screenshots", {}))

    def _send_screenshots_sync(self, screenshots: Dict[str, bytes]) -> None:
        """Synchronous implementation of screenshot sending (runs in thread pool).

        Args:
            screenshots: Dictionary mapping tab names to JPEG bytes
        """
        success = self.http_client.post_gui_screenshots(screenshots)
        if success:
            self.is_connected = True

    def _send_message_sync(self, message: Dict[str, Any]) -> None:
        """Synchronous implementation of message sending (runs in thread pool).

        Args:
            message: GUI message dictionary
        """
        sanitized_message = MessageSanitizer.sanitize(message)
        success = self.http_client.post_gui_update(sanitized_message)
        if success:
            self.is_connected = True

    def set_connection_callback(self, callback: Callable[[bool], None]) -> None:
        """Set a callback function to be called when connection status changes.

        Args:
            callback: Function that takes a boolean (True=connected, False=disconnected)
        """
        self.connection_callback = callback
