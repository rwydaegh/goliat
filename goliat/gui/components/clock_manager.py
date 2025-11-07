"""Clock and ETA management component."""

import time
from typing import TYPE_CHECKING, Optional

from goliat.utils import format_time

if TYPE_CHECKING:
    from goliat.gui.progress_gui import ProgressGUI


class ClockManager:
    """Manages elapsed time, ETA, and window title updates."""

    def __init__(self, gui: "ProgressGUI") -> None:
        """Initializes clock manager.

        Args:
            gui: ProgressGUI instance.
        """
        self.gui = gui

    def update(self) -> None:
        """Updates elapsed time, ETA labels, and window title.

        Called every second by Qt timer. Calculates elapsed time from start,
        gets ETA from profiler (if available), and updates window title with
        current status and progress percentage.

        The window title shows: [progress%] GOLIAT | Sim X/Y | Status
        where Status is 'Booting...', 'Running...', or 'Finished'.
        """
        elapsed_sec = time.monotonic() - self.gui.start_time
        self.gui.elapsed_label.setText(f"Elapsed: {format_time(elapsed_sec)}")

        eta_sec: Optional[float] = None
        if self.gui.profiler and self.gui.profiler.current_phase:
            current_stage_progress_ratio = self.gui.stage_progress_bar.value() / 1000.0
            eta_sec = self.gui.profiler.get_time_remaining(current_stage_progress=current_stage_progress_ratio)

            if eta_sec is not None:
                time_remaining_str = format_time(eta_sec)
                self.gui.eta_label.setText(f"Time Remaining: {time_remaining_str}")
            else:
                self.gui.eta_label.setText("Time Remaining: N/A")
        else:
            self.gui.eta_label.setText("Time Remaining: N/A")

        # Update window title with status
        progress_percent = max(0, self.gui.overall_progress_bar.value() / 100.0)
        title = self.gui.init_window_title
        if title:
            title += " | "
        title += f"[{progress_percent:.2f}%] GOLIAT"
        if self.gui.total_simulations > 0:
            title += f" | Sim {self.gui.current_simulation_count}/{self.gui.total_simulations}"

        # Determine status based on actual activity
        if self.gui.study_is_finished:
            status = "Finished" if not self.gui.study_had_errors else "Finished with Errors"
        elif progress_percent > 0 or self.gui.current_simulation_count > 0:
            status = "Running..."
        else:
            status = "Booting..."

        title += f" | {status}"
        self.gui.setWindowTitle(title)

        # Update web connection status indicator periodically
        if hasattr(self.gui, "web_bridge_manager") and self.gui.web_bridge_manager and self.gui.web_bridge_manager.web_bridge:
            if hasattr(self.gui.web_bridge_manager.web_bridge, "is_connected"):
                if hasattr(self.gui, "error_counter_label") and hasattr(self.gui, "status_manager"):
                    self.gui._update_web_status(self.gui.web_bridge_manager.web_bridge.is_connected)
