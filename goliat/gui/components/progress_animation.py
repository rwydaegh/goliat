"""Progress bar animation logic."""

import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QProgressBar
else:
    try:
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QProgressBar
    except ImportError:
        from typing import Any  # type: ignore

        QTimer = Any  # type: ignore
        QProgressBar = Any  # type: ignore


class ProgressAnimation:
    """Manages smooth progress bar animations based on estimated durations.

    Provides linear interpolation animation for progress bars when explicit
    progress updates aren't available. Animates from current value to target
    (100%) over estimated duration, giving visual feedback during long tasks.

    Updates every 50ms via Qt timer, calculating progress ratio from elapsed
    time and duration. Stops automatically when target is reached or stopped
    explicitly.
    """

    def __init__(self, progress_bar: "QProgressBar", timer: "QTimer", debug: bool = False) -> None:
        """Sets up the animation handler.

        Args:
            progress_bar: Progress bar widget to animate (0-1000 range).
            timer: QTimer instance for animation updates (50ms interval).
            debug: Enable debug logging (currently unused).
        """
        from PySide6.QtWidgets import QProgressBar as _QProgressBar
        from PySide6.QtCore import QTimer as _QTimer

        self.progress_bar: _QProgressBar = progress_bar
        self.timer: _QTimer = timer
        self.debug: bool = debug
        self.active: bool = False
        self.start_time: float = 0.0
        self.duration: float = 0.0
        self.start_value: int = 0
        self.end_value: int = 0

    def start(self, estimated_duration: float, end_step: int) -> None:
        """Starts smooth animation for progress bar.

        Begins linear interpolation from current value to 100% over estimated
        duration. If already at 100%, skips animation. Starts Qt timer if
        not already active.

        Args:
            estimated_duration: Estimated task duration in seconds (from profiler).
            end_step: Target step value (unused, always animates to 100%).
        """
        if self.debug:
            self._log(f"start_animation received: duration={estimated_duration:.2f}s, end_step={end_step}")

        self.start_time = time.monotonic()
        self.duration = estimated_duration
        self.start_value = self.progress_bar.value()
        self.end_value = 1000  # Progress bar range is 0-1000

        if self.start_value >= self.end_value:
            if self.debug:
                self._log("Animation skipped, start_value >= end_value.")
            return

        self.active = True
        if not self.timer.isActive():
            self.timer.start(50)
        if self.debug:
            self._log("Animation started.")

    def stop(self) -> None:
        """Stops the progress bar animation."""
        if self.active and self.debug:
            self._log("end_animation called.")
        self.active = False
        if self.timer.isActive():
            self.timer.stop()

    def update(self) -> None:
        """Updates progress bar animation frame by frame.

        Calculates current progress ratio based on elapsed time and duration,
        then interpolates between start and end values. Updates progress bar
        value and format string. Called every 50ms by Qt timer when active.
        """
        if not self.active:
            return

        elapsed = time.monotonic() - self.start_time

        if self.duration > 0:
            progress_ratio = min(elapsed / self.duration, 1.0)
        else:
            progress_ratio = 1.0

        value_range = self.end_value - self.start_value
        current_value = self.start_value + int(value_range * progress_ratio)
        current_value = min(current_value, self.end_value)

        self.progress_bar.setValue(current_value)
        percent = (current_value / 1000) * 100
        self.progress_bar.setFormat(f"{percent:.0f}%")

    def _log(self, message: str) -> None:
        """Logs debug message (placeholder for actual logging)."""
        # This would typically use a logger, but keeping it simple for now
        pass
