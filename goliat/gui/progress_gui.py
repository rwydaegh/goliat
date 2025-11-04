"""ProgressGUI main window component."""

import logging
import os
import time
from datetime import datetime
from multiprocessing import Process, Queue
from multiprocessing.synchronize import Event
from typing import TYPE_CHECKING, Optional, Any

import matplotlib

matplotlib.use("Qt5Agg")
try:
    from PySide6.QtCore import QTimer, Qt
    from PySide6.QtWidgets import QWidget, QProgressBar, QLabel, QTextEdit, QPushButton, QTabWidget
    from PySide6.QtGui import QCloseEvent
except ImportError:
    # Fallback for environments without PySide6
    QTimer = Any  # type: ignore
    Qt = Any  # type: ignore
    QWidget = Any  # type: ignore
    QProgressBar = Any  # type: ignore
    QLabel = Any  # type: ignore
    QTextEdit = Any  # type: ignore
    QPushButton = Any  # type: ignore
    QTabWidget = Any  # type: ignore
    QCloseEvent = Any  # type: ignore

from goliat.gui.components.data_manager import DataManager
from goliat.gui.components.status_manager import StatusManager
from goliat.gui.components.progress_animation import ProgressAnimation
from goliat.gui.components.plots import PieChartsManager
from goliat.gui.components.queue_handler import QueueHandler
from goliat.gui.components.timings_table import TimingsTable
from goliat.gui.components.tray_manager import TrayManager
from goliat.gui.components.ui_builder import UIBuilder
from goliat.gui.components.system_monitor import SystemMonitor, PSUTIL_AVAILABLE
from goliat.logging_manager import shutdown_loggers
from goliat.utils import format_time

if TYPE_CHECKING:
    from goliat.profiler import Profiler


class ProgressGUI(QWidget):  # type: ignore[misc]
    """Main GUI window for monitoring simulation progress.

    Provides real-time progress tracking via progress bars, ETA estimation,
    and status logs. Runs in the main process and communicates with worker
    process through a multiprocessing queue.

    The GUI architecture:
    - Main window runs in main process, worker runs in separate process
    - Communication via multiprocessing.Queue for thread-safe message passing
    - QueueHandler polls queue every 100ms and updates UI accordingly
    - Multiple timers handle different update frequencies (queue, clock, graphs)

    Features:
    - Overall progress bar (weighted across all simulations)
    - Stage progress bar (current phase: setup/run/extract)
    - Real-time ETA calculation based on profiler estimates
    - Status log with color-coded messages
    - Timings table showing execution statistics
    - Pie charts showing phase/subtask breakdowns
    - Time series plots for progress and ETA trends
    - System tray integration for background operation
    """

    def __init__(
        self,
        queue: Queue,
        stop_event: Event,
        process: Process,
        init_window_title: str = "",
    ) -> None:
        """Sets up the GUI window and all components.

        Initializes data manager, status manager, UI builder, timers, and
        queue handler. Sets up Qt timers for periodic updates (queue polling,
        clock updates, graph refreshes).

        Args:
            queue: Queue for receiving messages from worker process.
            stop_event: Event to signal termination to worker process.
            process: Worker process running the study.
            init_window_title: Initial window title.
        """
        super().__init__()
        self.queue: Queue = queue
        self.stop_event: Event = stop_event
        self.process: Process = process
        self.start_time: float = time.monotonic()
        self.progress_logger: logging.Logger = logging.getLogger("progress")
        self.verbose_logger: logging.Logger = logging.getLogger("verbose")
        self.init_window_title: str = init_window_title
        self.DEBUG: bool = False
        self.study_is_finished: bool = False
        self.study_had_errors: bool = False

        self.total_simulations: int = 0
        self.current_simulation_count: int = 0

        # Initialize components
        # Calculate repo root: go up 3 levels from goliat/gui/progress_gui.py to repo root
        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        data_dir = os.path.join(repo_root, "data")
        os.makedirs(data_dir, exist_ok=True)
        self.data_manager: DataManager = DataManager(data_dir, self.verbose_logger)
        self.status_manager: StatusManager = StatusManager()

        # Build UI
        UIBuilder.build(self, self.status_manager)

        # Initialize animation (must be after UI build to ensure stage_progress_bar exists)
        from PySide6.QtCore import QTimer as _QTimer
        self.animation_timer: _QTimer = _QTimer(self)
        self.animation_timer.timeout.connect(self.update_animation)
        self.progress_animation: ProgressAnimation = ProgressAnimation(
            self.stage_progress_bar, self.animation_timer, self.DEBUG
        )

        # Initialize tray manager
        self.tray_manager: TrayManager = TrayManager(self, self.show_from_tray, self.close)

        # Initialize queue handler
        self.queue_handler: QueueHandler = QueueHandler(self)

        self.total_steps_for_stage: int = 0
        self.profiler_phase: Optional[str] = None
        self.profiler: Optional["Profiler"] = None

        # Setup timers
        from PySide6.QtCore import QTimer as _QTimer
        self.queue_timer: _QTimer = _QTimer(self)
        self.queue_timer.timeout.connect(self.queue_handler.process_queue)
        self.queue_timer.start(100)

        self.clock_timer: _QTimer = _QTimer(self)
        self.clock_timer.timeout.connect(self.update_clock)
        self.clock_timer.start(1000)

        # Graph update timer (every 5 seconds)
        self.graph_timer: _QTimer = _QTimer(self)
        self.graph_timer.timeout.connect(self.update_graphs)
        self.graph_timer.start(5000)

        # System utilization update timer (every 1 second)
        self.utilization_timer: _QTimer = _QTimer(self)
        self.utilization_timer.timeout.connect(self.update_utilization)
        self.utilization_timer.start(1000)
        
        # Initialize GPU availability check
        self.gpu_available: bool = SystemMonitor.is_gpu_available()
        
        # Initialize CPU measurement (first call needs to be blocking)
        if PSUTIL_AVAILABLE:
            try:
                import psutil
                psutil.cpu_percent(interval=0.1)  # Initialize measurement
            except Exception:
                pass

    def update_overall_progress(self, current_step: float, total_steps: int) -> None:
        """Updates overall progress bar across all simulations.

        The progress bar uses a 0-10000 range internally (for finer granularity),
        but displays as percentage. Overall progress accounts for completed
        simulations plus progress within current simulation.

        Args:
            current_step: Current step number (0-100 range) or percentage (0-100).
            total_steps: Total number of steps (typically 100).
        """
        if self.DEBUG:
            self.update_status(f"DEBUG: update_overall_progress received: current={current_step}, total={total_steps}")
        if total_steps > 0:
            progress_percent = (current_step / total_steps) * 100
            self.overall_progress_bar.setValue(int(progress_percent * 100))
            self.overall_progress_bar.setFormat(f"{progress_percent:.2f}%")
            if self.DEBUG:
                self.update_status(f"DEBUG: Overall progress set to: {progress_percent:.2f}%")

    def update_stage_progress(self, stage_name: str, current_step: int, total_steps: int, sub_stage: str = "") -> None:
        """Updates stage-specific progress bar and label.

        Shows progress within current phase (setup/run/extract). Stops any
        active animation when explicit progress is set. Uses 0-1000 range
        internally for finer granularity.

        Args:
            stage_name: Name of current stage (e.g., 'Setup', 'Running Simulation').
            current_step: Current step within stage.
            total_steps: Total steps for the stage.
            sub_stage: Optional sub-stage description (currently unused).
        """
        if self.DEBUG:
            self.update_status(
                f"DEBUG: update_stage_progress received: name='{stage_name}', current={current_step}, total={total_steps}, sub_stage='{sub_stage}'"
            )

        self.stage_label.setText(f"Current Stage: {stage_name}")
        self.total_steps_for_stage = total_steps
        self.progress_animation.stop()

        progress_percent = (current_step / total_steps) if total_steps > 0 else 0
        final_value = int(progress_percent * 1000)

        self.stage_progress_bar.setValue(final_value)
        self.stage_progress_bar.setFormat(f"{progress_percent * 100:.0f}%")
        if self.DEBUG:
            self.update_status(f"DEBUG: Stage '{stage_name}' progress set to: {progress_percent * 100:.0f}%")

    def start_stage_animation(self, estimated_duration: float, end_step: int) -> None:
        """Starts smooth animated progress bar for a stage.

        Instead of jumping to discrete progress values, animates smoothly over
        the estimated duration. This provides visual feedback during long-running
        tasks where progress updates are infrequent.

        The animation uses linear interpolation between current value and target
        (always 100% = 1000). Updates every 50ms via Qt timer.

        Args:
            estimated_duration: Estimated task duration in seconds (from profiler).
            end_step: Target step value (unused, always animates to 100%).
        """
        if self.DEBUG:
            self.update_status(f"DEBUG: start_stage_animation received: duration={estimated_duration:.2f}s, end_step={end_step}")
        self.progress_animation.start(estimated_duration, end_step)

    def end_stage_animation(self) -> None:
        """Stops stage progress bar animation."""
        self.progress_animation.stop()

    def update_animation(self) -> None:
        """Updates progress bar animation frame and syncs overall progress.

        Called every 50ms by Qt timer when animation is active. Calculates
        current progress based on elapsed time and estimated duration, then
        updates stage progress bar. Also syncs overall progress bar using
        weighted progress calculation from profiler.
        """
        self.progress_animation.update()

        # Sync overall progress based on stage animation
        if self.profiler and self.profiler.current_phase:
            current_value = self.stage_progress_bar.value()
            percent = (current_value / 1000) * 100
            progress = self.profiler.get_weighted_progress(self.profiler.current_phase, percent / 100.0)
            self.update_overall_progress(progress, 100)

    def update_simulation_details(self, sim_count: int, total_sims: int, details: str) -> None:
        """Updates simulation counter and details labels.

        Args:
            sim_count: Current simulation number.
            total_sims: Total number of simulations.
            details: Description of current simulation case.
        """
        self.current_simulation_count = sim_count
        self.total_simulations = total_sims
        self.sim_counter_label.setText(f"Simulation: {sim_count} / {total_sims}")
        self.sim_details_label.setText(f"Current Case: {details}")

    def update_status(self, message: str, log_type: str = "default") -> None:
        """Appends message to status log with color formatting.

        Args:
            message: Message text.
            log_type: Log type for color coding.
        """
        self.status_manager.record_log(log_type)
        self.error_counter_label.setText(self.status_manager.get_error_summary())
        formatted_message = self.status_manager.format_message(message, log_type)
        self.status_text.append(formatted_message)

    def update_utilization(self) -> None:
        """Updates CPU, RAM, and GPU utilization displays.

        Called every second by Qt timer. Gets current utilization values
        from SystemMonitor and updates the progress bars and labels.
        """
        # Update CPU utilization
        cpu_percent = SystemMonitor.get_cpu_utilization()
        self.cpu_bar.setValue(int(cpu_percent))
        self.cpu_bar.setFormat(f"{cpu_percent:.0f}%")

        # Update RAM utilization
        used_gb, total_gb = SystemMonitor.get_ram_utilization()
        if total_gb > 0:
            ram_percent = (used_gb / total_gb) * 100
            self.ram_bar.setValue(int(ram_percent))
            self.ram_bar.setFormat(f"{used_gb:.1f}/{total_gb:.1f} GB")
        else:
            self.ram_bar.setValue(0)
            self.ram_bar.setFormat("N/A")

        # Update GPU utilization
        if self.gpu_available:
            gpu_percent = SystemMonitor.get_gpu_utilization()
            if gpu_percent is not None:
                self.gpu_bar.setValue(int(gpu_percent))
                self.gpu_bar.setFormat(f"{gpu_percent:.0f}%")
            else:
                self.gpu_bar.setValue(0)
                self.gpu_bar.setFormat("N/A")
                self.gpu_available = False  # GPU became unavailable
        else:
            self.gpu_bar.setValue(0)
            self.gpu_bar.setFormat("N/A")

    def update_clock(self) -> None:
        """Updates elapsed time, ETA labels, and window title.

        Called every second by Qt timer. Calculates elapsed time from start,
        gets ETA from profiler (if available), and updates window title with
        current status and progress percentage.

        The window title shows: [progress%] GOLIAT | Sim X/Y | Status
        where Status is 'Booting...', 'Running...', or 'Finished'.
        """
        elapsed_sec = time.monotonic() - self.start_time
        self.elapsed_label.setText(f"Elapsed: {format_time(elapsed_sec)}")

        eta_sec: Optional[float] = None
        if self.profiler and self.profiler.current_phase:
            current_stage_progress_ratio = self.stage_progress_bar.value() / 1000.0
            eta_sec = self.profiler.get_time_remaining(current_stage_progress=current_stage_progress_ratio)

            if eta_sec is not None:
                time_remaining_str = format_time(eta_sec)
                self.eta_label.setText(f"Time Remaining: {time_remaining_str}")
            else:
                self.eta_label.setText("Time Remaining: N/A")
        else:
            self.eta_label.setText("Time Remaining: N/A")

        # Update window title with status
        progress_percent = max(0, self.overall_progress_bar.value() / 100.0)
        title = self.init_window_title
        title += f"[{progress_percent:.2f}%] GOLIAT"
        if self.total_simulations > 0:
            title += f" | Sim {self.current_simulation_count}/{self.total_simulations}"

        # Determine status based on actual activity
        if self.study_is_finished:
            status = "Finished" if not self.study_had_errors else "Finished with Errors"
        elif progress_percent > 0 or self.current_simulation_count > 0:
            status = "Running..."
        else:
            status = "Booting..."

        title += f" | {status}"
        self.setWindowTitle(title)

    def update_graphs(self) -> None:
        """Updates time remaining and overall progress graphs (called every 5 seconds).

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
        if self.profiler and self.profiler.current_phase:
            current_stage_progress_ratio = self.stage_progress_bar.value() / 1000.0
            eta_sec = self.profiler.get_time_remaining(current_stage_progress=current_stage_progress_ratio)

        # Get current progress
        progress_percent = max(0, self.overall_progress_bar.value() / 100.0)

        # Update time remaining data
        if eta_sec is not None:
            current_time = datetime.now()
            hours_remaining = eta_sec / 3600.0
            self.data_manager.write_time_remaining(hours_remaining)
            self.time_remaining_plot.add_data_point(current_time, hours_remaining)

        # Update overall progress data
        current_time = datetime.now()
        self.data_manager.write_overall_progress(progress_percent)
        self.overall_progress_plot.add_data_point(current_time, progress_percent)

    def hide_to_tray(self) -> None:
        """Hides main window and shows system tray icon."""
        self.hide()
        self.tray_manager.show()

    def show_from_tray(self) -> None:
        """Shows main window from system tray."""
        self.show()
        self.tray_manager.hide()

    def stop_study(self) -> None:
        """Sends stop signal to worker process."""
        message = "--- Sending stop signal to study process ---"
        self.progress_logger.info(message, extra={"log_type": "warning"})
        self.verbose_logger.info(message, extra={"log_type": "warning"})
        self.update_status(message, log_type="warning")
        self.stop_button.setEnabled(False)
        self.tray_button.setEnabled(False)
        self.stop_event.set()

    def study_finished(self, error: bool = False) -> None:
        """Handles study completion, stopping timers and updating UI.

        Called when worker process signals completion. Stops all timers,
        updates final progress to 100%, sets stage label, and schedules
        window auto-close after 3 seconds (if no errors).

        Args:
            error: Whether study finished with errors (affects UI styling).
        """
        self.study_is_finished = True
        self.study_had_errors = error
        self.clock_timer.stop()
        self.queue_timer.stop()
        self.graph_timer.stop()
        self.utilization_timer.stop()
        self.progress_animation.stop()
        if not error:
            self.update_status("--- Study Finished ---", log_type="success")
            self.overall_progress_bar.setValue(self.overall_progress_bar.maximum())
            self.stage_label.setText("Finished")
        else:
            self.update_status("--- Study Finished with Errors ---", log_type="fatal")
            self.stage_label.setText("Error")

        self.stop_button.setEnabled(False)
        self.tray_button.setEnabled(False)
        self.update_clock()  # Final title update
        from PySide6.QtCore import QTimer as _QTimer
        _QTimer.singleShot(3000, self.close)

    def closeEvent(self, event: Any) -> None:
        """Handles window close event, ensuring worker process termination.

        Args:
            event: Close event.
        """
        if self.tray_manager.is_visible():
            self.tray_manager.hide()

        if self.process.is_alive():
            self.progress_logger.info("Terminating study process...", extra={"log_type": "warning"})
            self.process.terminate()
            self.process.join(timeout=5)

        shutdown_loggers()
        event.accept()
