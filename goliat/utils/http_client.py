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

    def post_gui_update(self, message: Dict[str, Any]) -> bool:
        """Send a GUI update message to the API.

        Args:
            message: Message dictionary to send (will be wrapped in payload).

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
                timeout=10,
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
            self._handle_exception(e, message_type)
            return False

    def post_heartbeat(self, system_info: Optional[Dict[str, Any]] = None) -> bool:
        """Send a heartbeat to the API.

        Args:
            system_info: Optional system information dictionary.

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
                timeout=10,
            )

            return response.status_code == 200

        except Exception as e:
            self._handle_exception(e, "heartbeat")
            return False

    def _handle_exception(self, e: Exception, message_type: str) -> None:
        """Handle HTTP exceptions with appropriate logging.

        Args:
            e: Exception that occurred.
            message_type: Type of message being sent.
        """
        error_type = str(type(e).__name__)
        if "Timeout" in error_type:
            self._log(f"{message_type} timeout", level="verbose", log_type="warning")
        elif "ConnectionError" in error_type:
            self._log(f"{message_type} connection error", level="verbose", log_type="warning")
        else:
            self._log(f"Unexpected error sending {message_type}: {e}", level="verbose", log_type="error")
