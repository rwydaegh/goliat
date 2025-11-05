"""Web GUI Bridge for forwarding GUI messages to monitoring dashboard."""

import os
import time
import threading
import logging
import json
from queue import Queue, Empty
from typing import Dict, Any, Optional

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


class WebGUIBridge:
    """Bridges GUI messages to web monitoring dashboard.
    
    Receives messages via enqueue() and forwards them to the dashboard API.
    Uses an internal queue to decouple from the multiprocessing queue.
    Throttles messages to prevent overwhelming the API.
    """

    def __init__(self, server_url: str, machine_id: str, throttle_hz: float = 5.0):
        """Initialize the web GUI bridge.
        
        Args:
            server_url: Base URL of the monitoring dashboard (e.g., https://goliat-monitoring.vercel.app)
            machine_id: Unique identifier for this machine (typically IP address)
            throttle_hz: Maximum message rate in Hz (default: 5 messages/second)
        """
        if not REQUESTS_AVAILABLE:
            raise ImportError(
                "requests library is required for WebGUIBridge. "
                "Install with: pip install requests"
            )
        
        self.server_url = server_url.rstrip("/")
        self.machine_id = machine_id
        self.throttle_interval = 1.0 / throttle_hz
        self.internal_queue: Queue = Queue()
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.logger = logging.getLogger("web_gui_bridge")
        self.is_connected = False
        self.last_heartbeat_success = False
        self.connection_callback: Optional[callable] = None
        self._system_info: Optional[Dict[str, Any]] = None
        
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
        self.thread = threading.Thread(target=self._forward_loop, daemon=True)
        self.thread.start()
        self.logger.info(
            f"WebGUIBridge started: {self.server_url}, machine_id={self.machine_id}"
        )
        
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
                self.logger.warning(f"Heartbeat timeout after 10s - connection may be slow or server unreachable")
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
        self.logger.info("WebGUIBridge stopped")
    
    def _forward_loop(self) -> None:
        """Main loop that forwards messages from internal queue to API."""
        last_send_time = 0.0
        last_heartbeat_time = 0.0
        heartbeat_interval = 30.0  # Send heartbeat every 30 seconds
        
        while self.running:
            try:
                current_time = time.time()
                
                # Send periodic heartbeat
                if current_time - last_heartbeat_time >= heartbeat_interval:
                    self._send_heartbeat(self._system_info)
                    last_heartbeat_time = current_time
                
                # Throttle: wait if needed
                time_since_last_send = current_time - last_send_time
                if time_since_last_send < self.throttle_interval:
                    time.sleep(self.throttle_interval - time_since_last_send)
                
                # Try to get a message (non-blocking)
                try:
                    message = self.internal_queue.get_nowait()
                except Empty:
                    time.sleep(0.1)  # Small delay when queue is empty
                    continue
                
                # Forward to API
                self._send_message(message)
                last_send_time = time.time()
                
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
    
    def _send_message(self, message: Dict[str, Any]) -> None:
        """Send a single message to the dashboard API.
        
        Args:
            message: GUI message dictionary
        """
        try:
            # Sanitize message to remove non-serializable objects
            sanitized_message = self._sanitize_message(message)
            
            payload = {
                "machineId": self.machine_id,
                "message": sanitized_message,
                "timestamp": time.time(),
            }
            
            response = requests.post(
                f"{self.server_url}/api/gui-update",
                json=payload,
                timeout=10,  # Increased timeout from 5 to 10 seconds
            )
            
            if response.status_code == 200:
                self.is_connected = True
                # Don't call callback here - heartbeat handles connection status
            else:
                # Only mark as disconnected if we get a persistent error
                # Don't override successful heartbeat status immediately
                self.logger.debug(f"GUI update returned status {response.status_code}")
                # Don't set is_connected = False here - let heartbeat handle connection status
            
        except requests.exceptions.Timeout:
            # Timeout - don't mark as disconnected immediately, heartbeat will handle it
            self.logger.debug("GUI update timeout")
        except requests.exceptions.ConnectionError:
            # Connection error - don't mark as disconnected immediately, heartbeat will handle it
            self.logger.debug("GUI update connection error")
        except Exception as e:
            # Only log unexpected errors
            self.logger.error(f"Unexpected error sending message: {e}")
    
    def set_connection_callback(self, callback: callable) -> None:
        """Set a callback function to be called when connection status changes.
        
        Args:
            callback: Function that takes a boolean (True=connected, False=disconnected)
        """
        self.connection_callback = callback

