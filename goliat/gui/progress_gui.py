"""ProgressGUI main window component."""

import logging
import os
import time
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
from goliat.gui.components.queue_handler import QueueHandler
from goliat.gui.components.tray_manager import TrayManager
from goliat.gui.components.ui_builder import UIBuilder
from goliat.gui.components.system_monitor import SystemMonitor, PSUTIL_AVAILABLE
from goliat.gui.components.machine_id_detector import MachineIdDetector
from goliat.gui.components.web_bridge_manager import WebBridgeManager
from goliat.gui.components.progress_manager import ProgressManager
from goliat.gui.components.clock_manager import ClockManager
from goliat.gui.components.utilization_manager import UtilizationManager
from goliat.gui.components.graph_manager import GraphManager
from goliat.logging_manager import shutdown_loggers

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
        self._initialize_components()

        # Auto-detect machine ID
        self.machine_id = MachineIdDetector.detect(self.verbose_logger)
        self.server_url = "https://goliat.waves-ugent.be"

        # Build UI
        UIBuilder.build(self, self.status_manager)

        # Initialize managers
        self.web_bridge_manager = WebBridgeManager(self, self.server_url, self.machine_id)
        self.progress_manager = ProgressManager(self)
        self.clock_manager = ClockManager(self)
        self.utilization_manager = UtilizationManager(self)
        self.graph_manager = GraphManager(self)

        # Initialize web GUI bridge after UI is built (so we can set callback)
        self.web_bridge_manager.initialize()

        # Initialize animation and other components
        self._initialize_animation()
        self._initialize_managers()
        self._setup_timers()
        self._initialize_system_monitoring()

    def _initialize_components(self) -> None:
        """Initializes core components (data manager, status manager)."""
        # Determine data directory: prefer cwd if it has data/, otherwise fallback to package location
        cwd = os.getcwd()
        if os.path.isdir(os.path.join(cwd, "data")):
            data_dir = os.path.join(cwd, "data")
        else:
            # Fallback: calculate from package location (for backwards compatibility)
            repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            data_dir = os.path.join(repo_root, "data")
        os.makedirs(data_dir, exist_ok=True)
        self.data_manager: DataManager = DataManager(data_dir, self.verbose_logger)
        self.status_manager: StatusManager = StatusManager()

    def _initialize_animation(self) -> None:
        """Initializes progress animation component."""
        from PySide6.QtCore import QTimer as _QTimer

        self.animation_timer: _QTimer = _QTimer(self)
        self.animation_timer.timeout.connect(self.update_animation)
        self.progress_animation: ProgressAnimation = ProgressAnimation(self.stage_progress_bar, self.animation_timer, self.DEBUG)

    def _initialize_managers(self) -> None:
        """Initializes tray manager and queue handler."""
        self.tray_manager: TrayManager = TrayManager(self, self.show_from_tray, self.close)
        self.queue_handler: QueueHandler = QueueHandler(self)

        self.total_steps_for_stage: int = 0
        self.profiler_phase: Optional[str] = None
        self.profiler: Optional["Profiler"] = None

    def _setup_timers(self) -> None:
        """Sets up all Qt timers for periodic updates."""
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

        # Progress sync timer (every 2 seconds) - send actual progress bar values to web
        self.progress_sync_timer: _QTimer = _QTimer(self)
        self.progress_sync_timer.timeout.connect(self.web_bridge_manager.sync_progress)
        self.progress_sync_timer.start(2000)

    def _initialize_system_monitoring(self) -> None:
        """Initializes system monitoring (GPU availability, CPU measurement)."""
        # Initialize GPU availability check
        # SystemMonitor is imported at module level, so it's always available
        self.gpu_available: bool = SystemMonitor.is_gpu_available()  # type: ignore[possibly-unbound]

        # Initialize CPU measurement (first call needs to be blocking)
        if PSUTIL_AVAILABLE:
            try:
                import psutil

                psutil.cpu_percent(interval=0.1)  # Initialize measurement
            except Exception:
                pass

    def update_overall_progress(self, current_step: float, total_steps: int) -> None:
        """Updates overall progress bar across all simulations."""
        self.progress_manager.update_overall(current_step, total_steps)

    def update_stage_progress(self, stage_name: str, current_step: int, total_steps: int, sub_stage: str = "") -> None:
        """Updates stage-specific progress bar and label."""
        self.progress_manager.update_stage(stage_name, current_step, total_steps, sub_stage)

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
            self.progress_manager.update_overall(progress, 100)

    def update_simulation_details(self, sim_count: int, total_sims: int, details: str) -> None:
        """Updates simulation counter and details labels."""
        self.progress_manager.update_simulation_details(sim_count, total_sims, details)

    def update_status(self, message: str, log_type: str = "default") -> None:
        """Appends message to status log with color formatting.

        Args:
            message: Message text.
            log_type: Log type for color coding.
        """
        self.status_manager.record_log(log_type)
        # Update error counter with current web status
        web_connected = False
        if (
            hasattr(self, "web_bridge_manager")
            and self.web_bridge_manager.web_bridge
            and hasattr(self.web_bridge_manager.web_bridge, "is_connected")
        ):
            web_connected = self.web_bridge_manager.web_bridge.is_connected
        self.error_counter_label.setText(self.status_manager.get_error_summary(web_connected=web_connected))
        formatted_message = self.status_manager.format_message(message, log_type)
        self.status_text.append(formatted_message)

    def update_utilization(self) -> None:
        """Updates CPU, RAM, and GPU utilization displays."""
        self.utilization_manager.update()

    def update_clock(self) -> None:
        """Updates elapsed time, ETA labels, and window title."""
        self.clock_manager.update()

    def _update_web_status(self, connected: bool, message: str = "") -> None:
        """Update the web connection status in the error counter label.

        Args:
            connected: True if connected, False if disconnected
            message: Optional status message (not used, kept for compatibility)
        """
        if hasattr(self, "error_counter_label") and hasattr(self, "status_manager"):
            self.error_counter_label.setText(self.status_manager.get_error_summary(web_connected=connected))

    def update_graphs(self) -> None:
        """Updates time remaining and overall progress graphs."""
        self.graph_manager.update()

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
        self.progress_sync_timer.stop()
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

        # Send final status update to web before stopping bridge
        self.web_bridge_manager.send_finished(error)

        self.update_clock()  # Final title update

        # Instead of auto-closing, show a message that user can close the window
        if not error:
            self.update_status("\n✓ All done! You may close this window now.", log_type="success")
        else:
            self.update_status("\n✓ Finished with errors. You may close this window now.", log_type="warning")

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

        # Stop web bridge if enabled
        self.web_bridge_manager.stop()

        shutdown_loggers()
        event.accept()
