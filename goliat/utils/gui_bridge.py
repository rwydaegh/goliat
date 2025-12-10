"""Web GUI Bridge for forwarding GUI messages to monitoring dashboard."""

import time
import threading
import logging
from concurrent.futures import ThreadPoolExecutor
from queue import Queue, Empty
from typing import Dict, Any, Optional, Callable

from goliat.logging_manager import LoggingMixin
from goliat.utils.http_client import HTTPClient

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
        self.server_url = server_url.rstrip("/")
        self.machine_id = machine_id
        self.throttle_interval = 1.0 / throttle_hz
        self.internal_queue: Queue = Queue()
        self.running = False
        self.thread: Optional[threading.Thread] = None
        # Use the main loggers so messages appear in log files
        self.verbose_logger = logging.getLogger("verbose")
        self.progress_logger = logging.getLogger("progress")
        self.is_connected = False
        self.last_heartbeat_success = False
        self.connection_callback: Optional[Callable[[bool], None]] = None
        self._system_info: Optional[Dict[str, Any]] = None
        self.log_executor: Optional[ThreadPoolExecutor] = None
        self.request_executor: Optional[ThreadPoolExecutor] = None

        # Sequence number for ordering batches when sent in parallel
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
        except Exception as e:
            self._log(f"Failed to enqueue message: {e}", level="verbose", log_type="warning")

    def start(self) -> None:
        """Start the forwarding thread and send initial heartbeat."""
        if self.running:
            return

        self.running = True
        # Start thread pools for async HTTP requests
        # log_executor: Multiple threads for parallel batch sending (order maintained via sequence numbers)
        self.log_executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="web_bridge_log")
        # request_executor: Multiple threads for independent requests like screenshots and heartbeats
        self.request_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="web_bridge_req")

        self.thread = threading.Thread(target=self._forward_loop, daemon=True)
        self.thread.start()
        self._log(f"WebGUIBridge started: {self.server_url}, machine_id={self.machine_id}", level="verbose")

        # Send initial heartbeat to register worker
        # Wait a bit for it to complete and call callback with initial status
        self._send_heartbeat_async(self._system_info)
        # Also trigger callback with current status (even if unchanged) so GUI gets initial state
        if self.connection_callback:
            self.connection_callback(self.is_connected)

    def _send_heartbeat_async(self, system_info: Optional[Dict[str, Any]] = None) -> None:
        """Send a heartbeat asynchronously via request executor.

        Args:
            system_info: Optional system information dict
        """
        if self.request_executor:
            self.request_executor.submit(self._send_heartbeat, system_info)

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

        # Don't try to flush remaining messages - just cancel pending requests
        # This prevents hanging on shutdown when network is slow
        if remaining:
            self._log(f"Dropping {len(remaining)} remaining messages on stop (shutdown)", level="verbose")

        # Cancel pending futures and shutdown immediately - don't wait for slow requests
        if hasattr(self, "log_executor") and self.log_executor:
            self.log_executor.shutdown(wait=False, cancel_futures=True)
        if hasattr(self, "request_executor") and self.request_executor:
            self.request_executor.shutdown(wait=False, cancel_futures=True)

        self._log("WebGUIBridge stopped", level="verbose")

    def _forward_loop(self) -> None:
        """Main loop that forwards messages from internal queue to API.

        Batches log messages for efficiency, sends progress updates immediately.
        """
        last_throttled_send_time = 0.0
        last_heartbeat_time = 0.0
        heartbeat_interval = 30.0  # Send heartbeat every 30 seconds
        throttle_interval_fast = 0.02  # 50 Hz for progress updates

        # Batching for log messages - tighter batching for more real-time updates
        log_batch = []
        batch_interval = 0.05  # Send batched logs every 50ms for very fast updates
        last_batch_send = time.time()

        while self.running:
            try:
                current_time = time.time()

                # Send periodic heartbeat
                if current_time - last_heartbeat_time >= heartbeat_interval:
                    self._send_heartbeat_async(self._system_info)
                    last_heartbeat_time = current_time

                # Tight batching: send every 50ms or when batch reaches 10 messages
                # Parallel executor (max_workers=3) with sequence numbers ensures correct ordering
                if log_batch:
                    time_since_last_batch = current_time - last_batch_send
                    should_send = (
                        len(log_batch) >= 10  # Size limit (reduced from 20 to 10)
                        or time_since_last_batch >= batch_interval  # Time limit (50ms, reduced from 200ms)
                    )

                    if should_send:
                        self._send_log_batch(log_batch)
                        log_batch = []
                        last_batch_send = current_time

                # Try to get a message (non-blocking)
                try:
                    message = self.internal_queue.get(timeout=0.01)
                except Empty:
                    time.sleep(0.01)
                    continue

                message_type = message.get("type", "")

                # Batch status (log) messages, send others immediately
                if message_type == "status":
                    log_batch.append(message)
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

            except Exception as e:
                self._log(f"Error in forward loop: {e}", level="verbose", log_type="error")
                # Try to flush batch even on error
                if log_batch:
                    try:
                        self._send_log_batch(log_batch)
                        log_batch = []
                    except Exception as flush_error:
                        self._log(f"Failed to flush batch after error: {flush_error}", level="verbose", log_type="error")
                time.sleep(1.0)  # Wait before retrying

        # Flush any remaining batch when loop exits
        if log_batch:
            try:
                self._send_log_batch_sync(log_batch)
            except Exception as e:
                self._log(f"Failed to flush final batch on exit: {e}", level="verbose", log_type="error")

    def _send_log_batch(self, log_messages: list[Dict[str, Any]], timeout: float = 10.0) -> None:
        """Send a batch of log messages to the dashboard API (async).

        Args:
            log_messages: List of status/log message dictionaries
            timeout: Request timeout in seconds (default: 10.0)
        """
        if not hasattr(self, "log_executor") or not self.log_executor or not log_messages:
            return

        # Submit to log executor for parallel processing (max_workers=3)
        # Sequence numbers ensure batches are ordered correctly on server side
        self.log_executor.submit(self._send_log_batch_sync, log_messages, timeout=timeout)

    def _send_log_batch_sync(self, log_messages: list[Dict[str, Any]], timeout: float = 10.0) -> None:
        """Synchronous implementation of log batch sending (runs in thread pool).

        Args:
            log_messages: List of status/log message dictionaries
            timeout: Request timeout in seconds (default: 10.0 - longer for slow networks)
        """
        if not log_messages:
            return

        # Get sequence number for ordering (batches sent in parallel, server sorts by sequence)
        with self._sequence_lock:
            sequence = self._sequence_counter
            self._sequence_counter += 1

        batch_message = {
            "type": "log_batch",
            "logs": log_messages,
            "sequence": sequence,  # Server uses this to sort batches that arrive out of order
        }

        # Single attempt with longer timeout - don't block on retries
        # If it fails, next batch will try again. Messages will eventually arrive.
        success = self.http_client.post_gui_update(batch_message, timeout=timeout)
        if success:
            self.is_connected = True
        else:
            # Don't log every failure - too noisy. Just mark as disconnected.
            self.is_connected = False

    def _send_message(self, message: Dict[str, Any]) -> None:
        """Send a single message to the dashboard API (async).

        Args:
            message: GUI message dictionary
        """
        if not hasattr(self, "log_executor") or not self.log_executor:
            return

        # Submit to log executor for sequential processing (FIFO)
        self.log_executor.submit(self._send_message_sync, message)

    def _send_screenshots(self, message: Dict[str, Any]) -> None:
        """Send screenshots to the dashboard API (async).

        Args:
            message: Message dictionary with 'screenshots' key containing tab name -> bytes mapping
        """
        if not hasattr(self, "request_executor") or not self.request_executor or "screenshots" not in message:
            return

        # Submit to request executor (can be parallel)
        self.request_executor.submit(self._send_screenshots_sync, message.get("screenshots", {}))

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
            message: GUI message dictionary (already sanitized upstream)
        """
        # Use short timeout (3s) for progress updates to avoid blocking queue
        # Messages are already sanitized: profiler_update is sanitized in queue_handler.py,
        # all other messages are primitives (str, int, float, bool, dict, list)
        success = self.http_client.post_gui_update(message, timeout=3.0)
        if success:
            self.is_connected = True

    def set_connection_callback(self, callback: Callable[[bool], None]) -> None:
        """Set a callback function to be called when connection status changes.

        Args:
            callback: Function that takes a boolean (True=connected, False=disconnected)
        """
        self.connection_callback = callback
