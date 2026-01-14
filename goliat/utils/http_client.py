"""HTTP client helper for web bridge API calls."""

import time
import logging
from typing import Dict, Any, Optional

from goliat.logging_manager import LoggingMixin

try:
    import requests

    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    requests = None  # type: ignore


class HTTPClient(LoggingMixin):
    """Handles HTTP requests to the monitoring dashboard API."""

    def __init__(self, server_url: str, machine_id: str, logger: logging.Logger) -> None:
        """Initialize HTTP client.

        Args:
            server_url: Base URL of the monitoring dashboard.
            machine_id: Machine identifier.
            logger: Logger instance (used for verbose_logger).
        """
        self.server_url = server_url.rstrip("/")
        self.machine_id = machine_id
        self.verbose_logger = logger
        self.progress_logger = logger
        self.gui = None

    def post_gui_update(self, message: Dict[str, Any], timeout: float = 10.0) -> bool:
        """Send a GUI update message to the API.

        Args:
            message: Message dictionary to send (will be wrapped in payload).
            timeout: Request timeout in seconds (default: 10.0).

        Returns:
            True if successful, False otherwise.
        """
        if not REQUESTS_AVAILABLE or requests is None:
            return False

        message_type = message.get("type", "unknown")

        try:
            payload = {
                "machineId": self.machine_id,
                "message": message,
                "timestamp": time.time(),
            }

            response = requests.post(  # type: ignore[attr-defined]
                f"{self.server_url}/api/gui-update",
                json=payload,
                timeout=timeout,
            )

            if response.status_code == 200:
                return True
            else:
                self._log(
                    f"GUI update ({message_type}) returned status {response.status_code}: {response.text[:100]}",
                    level="verbose",
                    log_type="warning",
                )
                return False

        except Exception as e:
            self._handle_exception(e, message_type, timeout=timeout)
            return False

    def post_heartbeat(self, system_info: Optional[Dict[str, Any]] = None, timeout: float = 10.0) -> bool:
        """Send a heartbeat to the API.

        Args:
            system_info: Optional system information dictionary.
            timeout: Request timeout in seconds (default: 10.0).

        Returns:
            True if successful, False otherwise.
        """
        if not REQUESTS_AVAILABLE or requests is None:
            return False

        try:
            payload = {"machineId": self.machine_id}
            if system_info:
                payload.update(system_info)

            response = requests.post(
                f"{self.server_url}/api/heartbeat",
                json=payload,
                timeout=timeout,
            )

            return response.status_code == 200

        except Exception as e:
            self._handle_exception(e, "heartbeat", timeout=timeout)
            return False

    def post_gui_screenshots(self, screenshots: Dict[str, bytes]) -> bool:
        """Send GUI screenshots to the API.

        Sends screenshots as multipart/form-data for efficient binary transfer.
        Each tab screenshot is sent as a separate file field.

        Args:
            screenshots: Dictionary mapping tab names to JPEG bytes.

        Returns:
            True if successful, False otherwise.
        """
        if not REQUESTS_AVAILABLE or requests is None:
            return False

        if not screenshots:
            return False

        try:
            # Prepare multipart form data
            files = []
            for tab_name, jpeg_bytes in screenshots.items():
                # Sanitize tab name for form field name (replace spaces with underscores)
                field_name = tab_name.replace(" ", "_")
                files.append((field_name, (f"{field_name}.jpg", jpeg_bytes, "image/jpeg")))

            # Add machineId as form field
            data = {"machineId": self.machine_id}

            # Send with longer timeout for large payloads (up to 2MB for 6 tabs)
            response = requests.post(  # type: ignore[attr-defined]
                f"{self.server_url}/api/gui-screenshots",
                data=data,
                files=files,
                timeout=30,  # Longer timeout for large payloads
            )

            if response.status_code == 200:
                return True
            else:
                self._log(
                    f"GUI screenshots returned status {response.status_code}: {response.text[:100]}",
                    level="verbose",
                    log_type="warning",
                )
                return False

        except Exception as e:
            self._handle_exception(e, "gui_screenshots", timeout=30)
            return False

    def _handle_exception(self, e: Exception, message_type: str, timeout: Optional[float] = None) -> None:
        """Handle HTTP exceptions with appropriate logging.

        Args:
            e: Exception that occurred.
            message_type: Type of message being sent.
            timeout: Timeout value that was used (optional, for logging).
        """
        error_type = str(type(e).__name__)
        if "Timeout" in error_type:
            # Timeouts are expected during normal operation (e.g., offline mode)
            # Log as debug to avoid cluttering output
            timeout_msg = f" (timeout: {timeout}s)" if timeout is not None else ""
            self.verbose_logger.debug(f"HTTP request timeout for {message_type}{timeout_msg}")
        elif "ConnectionError" in error_type:
            # Connection errors are also expected (e.g., no internet, server down)
            self.verbose_logger.debug(f"{message_type} connection error")
        else:
            self._log(f"Unexpected error sending {message_type}: {e}", level="verbose", log_type="error")
