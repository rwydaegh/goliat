"""Graph update management component."""

from typing import TYPE_CHECKING, Optional

from goliat.gui.components.plots.utils import get_ntp_utc_time

if TYPE_CHECKING:
    from goliat.gui.progress_gui import ProgressGUI


class GraphManager:
    """Manages time remaining and overall progress graph updates."""

    def __init__(self, gui: "ProgressGUI") -> None:
        """Initializes graph manager.

        Args:
            gui: ProgressGUI instance.
        """
        self.gui = gui

    def update(self) -> None:
        """Updates time remaining, overall progress, and system utilization graphs (called every 5 seconds).

        Gets current ETA and progress values, writes them to CSV files (via
        DataManager), and adds data points to matplotlib plots. The plots
        show trends over time, helping users see if ETA is converging or
        progress is steady.

        This runs less frequently than clock updates (5s vs 1s) because
        plotting is more expensive and the trends don't need millisecond
        precision.
        """
        # Get current ETA
        eta_sec: Optional[float] = None
        if self.gui.profiler and self.gui.profiler.current_phase:
            current_stage_progress_ratio = self.gui.stage_progress_bar.value() / 1000.0
            eta_sec = self.gui.profiler.get_time_remaining(current_stage_progress=current_stage_progress_ratio)

        # Get current progress
        progress_percent = max(0, self.gui.overall_progress_bar.value() / 100.0)

        # Update time remaining data
        if eta_sec is not None:
            current_time = get_ntp_utc_time()  # Use NTP time (bypasses system clock issues)
            hours_remaining = eta_sec / 3600.0
            self.gui.data_manager.write_time_remaining(hours_remaining)
            self.gui.time_remaining_plot.add_data_point(current_time, hours_remaining)

        # Update overall progress data
        current_time = get_ntp_utc_time()  # Use NTP time (bypasses system clock issues)
        self.gui.data_manager.write_overall_progress(progress_percent)
        self.gui.overall_progress_plot.add_data_point(current_time, progress_percent)

        # Note: System utilization plot is updated separately via utilization_plot_timer (every 2s)
