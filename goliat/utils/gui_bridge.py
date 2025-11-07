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
        self.verbose_logger = logging.getLogger("web_gui_bridge")
        self.progress_logger = logging.getLogger("web_gui_bridge")
        self.gui = None
        self.is_connected = False
        self.last_heartbeat_success = False
        self.connection_callback: Optional[Callable[[bool], None]] = None
        self._system_info: Optional[Dict[str, Any]] = None
        self.executor: Optional[ThreadPoolExecutor] = None

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
        """Stop the forwarding thread."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)
        if self.executor:
            self.executor.shutdown(wait=False, cancel_futures=True)
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

                # Send batched logs if enough time has passed
                if log_batch and (current_time - last_batch_send >= batch_interval):
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
                    # If batch is getting large, send immediately
                    if len(log_batch) >= 20:
                        self._send_log_batch(log_batch)
                        message_counts["status_batched"] = message_counts.get("status_batched", 0) + len(log_batch)
                        log_batch = []
                        last_batch_send = current_time
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
                time.sleep(1.0)  # Wait before retrying

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
        batch_message = {
            "type": "log_batch",
            "logs": log_messages,
        }
        success = self.http_client.post_gui_update(batch_message)
        if success:
            self.is_connected = True

    def _send_message(self, message: Dict[str, Any]) -> None:
        """Send a single message to the dashboard API (async).

        Args:
            message: GUI message dictionary
        """
        if not self.executor:
            return

        # Submit to thread pool for async execution (non-blocking)
        self.executor.submit(self._send_message_sync, message)

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
