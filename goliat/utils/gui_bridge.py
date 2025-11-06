"""Web GUI Bridge for forwarding GUI messages to monitoring dashboard."""

import time
import threading
import logging
from concurrent.futures import ThreadPoolExecutor
from queue import Queue, Empty
from typing import Dict, Any, Optional, Callable

try:
    import requests

    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    requests = None  # type: ignore


class WebGUIBridge:
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
        self.logger = logging.getLogger("web_gui_bridge")
        self.is_connected = False
        self.last_heartbeat_success = False
        self.connection_callback: Optional[Callable[[bool], None]] = None
        self._system_info: Optional[Dict[str, Any]] = None
        # ThreadPoolExecutor for non-blocking HTTP requests (max 10 concurrent)
        self.executor: Optional[ThreadPoolExecutor] = None

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
            self.logger.warning(f"Failed to enqueue message: {e}")

    def start(self) -> None:
        """Start the forwarding thread and send initial heartbeat."""
        if self.running:
            return

        self.running = True
        # Start thread pool for async HTTP requests
        self.executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="web_bridge_http")
        self.thread = threading.Thread(target=self._forward_loop, daemon=True)
        self.thread.start()
        self.logger.info(f"WebGUIBridge started: {self.server_url}, machine_id={self.machine_id}")

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
        if not REQUESTS_AVAILABLE or requests is None:
            return
        try:
            payload = {"machineId": self.machine_id}
            if system_info:
                payload.update(system_info)

            response = requests.post(
                f"{self.server_url}/api/heartbeat",
                json=payload,
                timeout=10,  # Increased timeout from 5 to 10 seconds
            )
            if response.status_code == 200:
                self.is_connected = True
                self.last_heartbeat_success = True
                if not was_connected:
                    self.logger.info("Web dashboard connection established")
                if self.connection_callback:
                    self.connection_callback(True)
            else:
                self.is_connected = False
                self.last_heartbeat_success = False
                self.logger.warning(f"Heartbeat returned status {response.status_code}: {response.text[:200]}")
                if was_connected and self.connection_callback:
                    self.connection_callback(False)
                elif not was_connected and self.connection_callback:
                    # Call callback even on initial failure so GUI knows the status
                    self.connection_callback(False)
        except requests.exceptions.Timeout:
            self.is_connected = False
            self.last_heartbeat_success = False
            if was_connected:
                self.logger.warning("Heartbeat timeout after 10s - connection may be slow or server unreachable")
                if self.connection_callback:
                    self.connection_callback(False)
            else:
                self.logger.info(f"Heartbeat timeout - server may be unreachable: {self.server_url}")
                if self.connection_callback:
                    self.connection_callback(False)
        except requests.exceptions.ConnectionError as e:
            self.is_connected = False
            self.last_heartbeat_success = False
            if was_connected:
                self.logger.warning(f"Lost connection to web dashboard: {e}")
                if self.connection_callback:
                    self.connection_callback(False)
            else:
                self.logger.info(f"Cannot connect to web dashboard: {e}")
                if self.connection_callback:
                    self.connection_callback(False)
        except Exception as e:
            self.is_connected = False
            self.last_heartbeat_success = False
            if was_connected:
                self.logger.warning(f"Lost connection to web dashboard: {e}")
            else:
                # Log initial connection failure for debugging
                self.logger.info(f"Initial heartbeat failed: {type(e).__name__}: {e}")
            if self.connection_callback:
                self.connection_callback(False)
            # Don't log every failure, only when connection changes or on initial failure

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
        self.logger.info("WebGUIBridge stopped")

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
                    send_start = time.time()
                    self._send_log_batch(log_batch)
                    send_duration = time.time() - send_start

                    if send_duration > 0.5:
                        self.logger.warning(f"Slow batch send: {len(log_batch)} logs took {send_duration:.2f}s")

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
                    # Add to batch with timestamp
                    log_batch.append(message)
                    # If batch is getting large, send immediately
                    if len(log_batch) >= 20:
                        send_start = time.time()
                        self._send_log_batch(log_batch)
                        send_duration = time.time() - send_start

                        if send_duration > 0.5:
                            self.logger.warning(f"Slow batch send: {len(log_batch)} logs took {send_duration:.2f}s")

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

                    send_start = time.time()
                    self._send_message(message)
                    send_duration = time.time() - send_start

                    if send_duration > 0.5:
                        self.logger.warning(f"Slow send: {message_type} took {send_duration:.2f}s")

                # Debug: Print message stats every 10 seconds
                if current_time - last_debug_time > 10.0:
                    if log_batch:
                        self.logger.info(f"WebGUI stats (last 10s): {message_counts}, pending logs: {len(log_batch)}")
                    else:
                        self.logger.info(f"WebGUI stats (last 10s): {message_counts}")
                    message_counts = {}
                    last_debug_time = current_time

            except Exception as e:
                self.logger.error(f"Error in forward loop: {e}")
                time.sleep(1.0)  # Wait before retrying

    def _sanitize_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Remove non-serializable objects from message.

        Args:
            message: GUI message dictionary that may contain non-serializable objects

        Returns:
            Sanitized message dictionary with only JSON-serializable values
        """
        sanitized = {}
        for key, value in message.items():
            if key == "profiler":
                # Extract only serializable data from profiler
                if hasattr(value, "eta_seconds"):
                    sanitized[key] = {"eta_seconds": getattr(value, "eta_seconds", None)}
                else:
                    # Skip profiler object if we can't extract data
                    continue
            elif isinstance(value, (str, int, float, bool, type(None))):
                sanitized[key] = value
            elif isinstance(value, (list, tuple)):
                sanitized[key] = [
                    self._sanitize_message(item) if isinstance(item, dict) else item
                    for item in value
                    if isinstance(item, (str, int, float, bool, type(None), dict))
                ]
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_message(value)
            # Skip other non-serializable types
        return sanitized

    def _send_log_batch(self, log_messages: list[Dict[str, Any]]) -> None:
        """Send a batch of log messages to the dashboard API (async).

        Args:
            log_messages: List of status/log message dictionaries
        """
        if not REQUESTS_AVAILABLE or requests is None or not self.executor:
            return

        if not log_messages:
            return

        # Submit to thread pool for async execution (non-blocking)
        self.executor.submit(self._send_log_batch_sync, log_messages)

    def _send_log_batch_sync(self, log_messages: list[Dict[str, Any]]) -> None:
        """Synchronous implementation of log batch sending (runs in thread pool).

        Args:
            log_messages: List of status/log message dictionaries
        """
        send_start = time.time()
        try:
            # Create batch payload with all logs
            payload = {
                "machineId": self.machine_id,
                "message": {
                    "type": "log_batch",
                    "logs": log_messages,  # Each log has its own timestamp and message
                },
                "timestamp": time.time(),
            }

            response = requests.post(  # type: ignore[attr-defined]
                f"{self.server_url}/api/gui-update",
                json=payload,
                timeout=10,
            )

            if response.status_code == 200:
                self.is_connected = True
            else:
                self.logger.warning(f"Log batch ({len(log_messages)} logs) returned status {response.status_code}: {response.text[:100]}")

        except Exception as e:
            if "Timeout" in str(type(e).__name__):
                self.logger.warning(f"Log batch timeout ({len(log_messages)} logs)")
            elif "ConnectionError" in str(type(e).__name__):
                self.logger.warning(f"Log batch connection error ({len(log_messages)} logs)")
            else:
                self.logger.error(f"Unexpected error sending log batch: {e}")
        finally:
            send_duration = time.time() - send_start
            if send_duration > 0.5:
                self.logger.warning(f"Slow batch send: {len(log_messages)} logs took {send_duration:.2f}s")

    def _send_message(self, message: Dict[str, Any]) -> None:
        """Send a single message to the dashboard API (async).

        Args:
            message: GUI message dictionary
        """
        if not REQUESTS_AVAILABLE or requests is None or not self.executor:
            return

        # Submit to thread pool for async execution (non-blocking)
        self.executor.submit(self._send_message_sync, message)

    def _send_message_sync(self, message: Dict[str, Any]) -> None:
        """Synchronous implementation of message sending (runs in thread pool).

        Args:
            message: GUI message dictionary
        """
        message_type = message.get("type", "unknown")
        send_start = time.time()

        try:
            # Sanitize message to remove non-serializable objects
            sanitized_message = self._sanitize_message(message)

            payload = {
                "machineId": self.machine_id,
                "message": sanitized_message,
                "timestamp": time.time(),
            }

            response = requests.post(  # type: ignore[attr-defined]
                f"{self.server_url}/api/gui-update",
                json=payload,
                timeout=10,
            )

            if response.status_code == 200:
                self.is_connected = True
            else:
                self.logger.warning(f"GUI update ({message_type}) returned status {response.status_code}: {response.text[:100]}")

        except Exception as e:
            if "Timeout" in str(type(e).__name__):
                self.logger.warning(f"GUI update timeout for message type: {message_type}")
            elif "ConnectionError" in str(type(e).__name__):
                self.logger.warning(f"GUI update connection error for message type: {message_type}")
            else:
                self.logger.error(f"Unexpected error sending {message_type} message: {e}")
        finally:
            send_duration = time.time() - send_start
            if send_duration > 0.5:
                self.logger.warning(f"Slow send: {message_type} took {send_duration:.2f}s")

    def set_connection_callback(self, callback: Callable[[bool], None]) -> None:
        """Set a callback function to be called when connection status changes.

        Args:
            callback: Function that takes a boolean (True=connected, False=disconnected)
        """
        self.connection_callback = callback
