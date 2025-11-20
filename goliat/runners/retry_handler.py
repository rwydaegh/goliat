"""Handler for retry logic and attempt tracking."""

from typing import TYPE_CHECKING, Optional

from ..logging_manager import LoggingMixin

if TYPE_CHECKING:
    from logging import Logger
    from ..gui_manager import QueueGUI


class RetryHandler(LoggingMixin):
    """Manages retry logic and attempt tracking."""

    def __init__(self, progress_logger: "Logger", gui: Optional["QueueGUI"] = None):
        """Initialize retry handler.

        Args:
            progress_logger: Logger for progress-level messages.
            gui: Optional GUI proxy for sending progress messages.
        """
        self.progress_logger = progress_logger
        self.gui = gui
        self.attempt_number = 0

    def should_retry(self, return_code: Optional[int], detected_errors: list) -> bool:
        """Determine if retry should occur.

        Args:
            return_code: Process return code (None if exception).
            detected_errors: List of errors detected in output.

        Returns:
            True if should retry (always True for non-zero return code).
        """
        return return_code != 0

    def record_attempt(self) -> None:
        """Record a retry attempt and log it."""
        self.attempt_number += 1
        if self.attempt_number > 0:
            self._log(
                f"    - iSolve failed, retry attempt {self.attempt_number}",
                level="progress",
                log_type="warning",
            )

        # Log error every 50 retries
        if self.attempt_number > 0 and self.attempt_number % 50 == 0:
            self._log(
                f"iSolve failed {self.attempt_number} times",
                level="progress",
                log_type="error",
            )

    def get_attempt_number(self) -> int:
        """Get current attempt number (0 = first attempt)."""
        return self.attempt_number

    def reset(self) -> None:
        """Reset attempt counter (for new simulation)."""
        self.attempt_number = 0
