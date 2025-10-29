import logging
import time
import traceback
from logging import Logger
from multiprocessing import Process, Queue
from multiprocessing.synchronize import Event

from PySide6.QtCore import QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMenu,
    QProgressBar,
    QPushButton,
    QSystemTrayIcon,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.logging_manager import LoggingMixin, shutdown_loggers
from src.profiler import Profiler
from src.utils import format_time


class QueueGUI(LoggingMixin):
    """A proxy for the main GUI, designed to operate in a separate process.

    This class mimics the `ProgressGUI` interface but directs all calls to a
    `multiprocessing.Queue`, allowing a worker process to send thread-safe
    updates to the main GUI process.
    """

    def __init__(
        self,
        queue: Queue,
        stop_event: Event,
        profiler: "Profiler",
        progress_logger: "Logger",
        verbose_logger: "Logger",
    ):
        """Initializes the QueueGUI proxy.

        Args:
            queue: The queue for inter-process communication.
            stop_event: An event to signal termination.
            profiler: The profiler instance for ETA calculations.
            progress_logger: Logger for progress messages.
            verbose_logger: Logger for detailed messages.
        """
        self.queue = queue
        self.stop_event = stop_event
        self.profiler = profiler
        self.progress_logger = progress_logger
        self.verbose_logger = verbose_logger

    def log(self, message: str, level: str = "verbose", log_type: str = "default"):
        """Sends a log message to the main GUI process via the queue."""
        if level == "progress":
            self.queue.put({"type": "status", "message": message, "log_type": log_type})

    def update_overall_progress(self, current_step: int, total_steps: int):
        """Sends an overall progress update to the queue."""
        self.queue.put({"type": "overall_progress", "current": current_step, "total": total_steps})

    def update_stage_progress(self, stage_name: str, current_step: int, total_steps: int):
        """Sends a stage-specific progress update to the queue."""
        self.queue.put(
            {
                "type": "stage_progress",
                "name": stage_name,
                "current": current_step,
                "total": total_steps,
            }
        )

    def start_stage_animation(self, task_name: str, end_value: int):
        """Sends a command to start a progress bar animation."""
        estimate = self.profiler.get_subtask_estimate(task_name)
        self.queue.put({"type": "start_animation", "estimate": estimate, "end_value": end_value})

    def end_stage_animation(self):
        """Sends a command to stop the progress bar animation."""
        self.queue.put({"type": "end_animation"})

    def update_profiler(self):
        """Sends the updated profiler object to the GUI process."""
        self.queue.put({"type": "profiler_update", "profiler": self.profiler})

    def process_events(self):
        """A no-op method for interface compatibility."""
        pass

    def is_stopped(self) -> bool:
        """Checks if the main process has signaled a stop request."""
        return self.stop_event.is_set()


class ProgressGUI(QWidget):
    """The main GUI for monitoring simulation progress.

    Provides a real-time view of the study's progress, including progress bars,
    ETA, and a log of status messages. It runs in the main process and
    communicates with the worker process via a multiprocessing queue.
    """

    def __init__(
        self,
        queue: Queue,
        stop_event: Event,
        process: Process,
        window_title: str = "Simulation Progress",
    ):
        """Initializes the ProgressGUI window.

        Args:
            queue: The queue for receiving messages from the worker process.
            stop_event: An event to signal termination to the worker process.
            process: The worker process running the study.
            window_title: The title of the GUI window.
        """
        super().__init__()
        self.queue = queue
        self.stop_event = stop_event
        self.process = process
        self.start_time = time.monotonic()
        self.progress_logger = logging.getLogger("progress")
        self.verbose_logger = logging.getLogger("verbose")
        self.window_title = window_title
        self.DEBUG = True
        self.init_ui()

        self.phase_name_map = {
            "Setup": "setup",
            "Running Simulation": "run",
            "Extracting Results": "extract",
        }

        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self.update_animation)
        self.animation_active = False
        self.animation_start_time = 0
        self.animation_duration = 0
        self.animation_start_value = 0
        self.animation_end_value = 0
        self.total_steps_for_stage = 0

        self.profiler_phase = None

        self.queue_timer = QTimer(self)
        self.queue_timer.timeout.connect(self.process_queue)
        self.queue_timer.start(100)

        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self.update_clock)
        self.clock_timer.start(1000)

    def init_ui(self):
        """Initializes and arranges all UI widgets."""
        self.setWindowTitle(self.window_title)
        self.resize(650, 650)
        layout = QVBoxLayout()
        self.grid_layout = QGridLayout()

        self.overall_progress_label = QLabel("Overall Progress:")
        layout.addWidget(self.overall_progress_label)
        self.overall_progress_bar = QProgressBar(self)
        self.overall_progress_bar.setRange(0, 1000)
        layout.addWidget(self.overall_progress_bar)

        self.stage_label = QLabel("Current Stage:")
        layout.addWidget(self.stage_label)
        self.stage_progress_bar = QProgressBar(self)
        self.stage_progress_bar.setRange(0, 1000)
        layout.addWidget(self.stage_progress_bar)

        self.elapsed_label = QLabel("Elapsed: N/A")
        self.eta_label = QLabel("Time Remaining: N/A")
        self.grid_layout.addWidget(self.elapsed_label, 0, 0)
        self.grid_layout.addWidget(self.eta_label, 0, 1)
        layout.addLayout(self.grid_layout)

        self.status_log_label = QLabel("Status Log:")
        layout.addWidget(self.status_log_label)
        self.status_text = QTextEdit(self)
        self.status_text.setReadOnly(True)
        layout.addWidget(self.status_text)

        self.button_layout = QHBoxLayout()
        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.stop_study)
        self.tray_button = QPushButton("Run in Background")
        self.tray_button.clicked.connect(self.hide_to_tray)
        self.button_layout.addWidget(self.stop_button)
        self.button_layout.addWidget(self.tray_button)
        layout.addLayout(self.button_layout)

        self.setLayout(layout)

        self.tray_icon = QSystemTrayIcon(self)
        style = self.style()
        icon = style.standardIcon(style.StandardPixmap.SP_ComputerIcon)
        self.tray_icon.setIcon(icon)
        self.tray_icon.setToolTip("Simulation is running...")

        tray_menu = QMenu(self)
        show_action = QAction("Show", self)
        show_action.triggered.connect(self.show_from_tray)
        tray_menu.addAction(show_action)

        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        tray_menu.addAction(exit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.tray_icon_activated)

    def process_queue(self):
        """Processes messages from the worker process queue to update the UI."""
        from queue import Empty

        while not self.queue.empty():
            try:
                msg = self.queue.get_nowait()
                msg_type = msg.get("type")

                if msg_type == "status":
                    self.update_status(msg["message"], msg.get("log_type", "default"))
                elif msg_type == "overall_progress":
                    self.update_overall_progress(msg["current"], msg["total"])
                elif msg_type == "stage_progress":
                    self.update_stage_progress(msg["name"], msg["current"], msg["total"])
                elif msg_type == "start_animation":
                    self.start_stage_animation(msg["estimate"], msg["end_value"])
                elif msg_type == "end_animation":
                    self.end_stage_animation()
                elif msg_type == "profiler_update":
                    self.profiler = msg.get("profiler")
                    if self.profiler:
                        self.profiler_phase = self.profiler.current_phase
                elif msg_type == "finished":
                    self.study_finished()
                elif msg_type == "fatal_error":
                    self.update_status(f"FATAL ERROR: {msg['message']}", log_type="fatal")
                    self.study_finished(error=True)

            except Empty:
                break
            except Exception as e:
                self.verbose_logger.error(f"Error processing GUI queue: {e}\n{traceback.format_exc()}")

    def tray_icon_activated(self, reason):
        """Handles activation of the system tray icon."""
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show_from_tray()

    def hide_to_tray(self):
        """Hides the main window and shows the system tray icon."""
        self.hide()
        self.tray_icon.show()

    def show_from_tray(self):
        """Shows the main window from the system tray."""
        self.show()
        self.tray_icon.hide()

    def stop_study(self):
        """Sends a stop signal to the worker process."""
        message = "--- Sending stop signal to study process ---"
        self.progress_logger.info(message, extra={"log_type": "warning"})
        self.verbose_logger.info(message, extra={"log_type": "warning"})
        self.update_status(message, log_type="warning")
        self.stop_button.setEnabled(False)
        self.tray_button.setEnabled(False)

        self.stop_event.set()

    def update_overall_progress(self, current_step: int, total_steps: int):
        """Updates the overall progress bar."""
        if total_steps > 0:
            progress_percent = (current_step / total_steps) * 100
            self.overall_progress_bar.setValue(int(progress_percent * 10))
            self.overall_progress_bar.setFormat(f"{progress_percent:.1f}%")
            if self.DEBUG:
                self.update_status(f"DEBUG: Overall progress: {progress_percent:.1f}%")

    def update_stage_progress(self, stage_name: str, current_step: int, total_steps: int):
        """Updates the stage-specific progress bar."""
        self.stage_label.setText(f"Current Stage: {stage_name}")
        self.total_steps_for_stage = total_steps

        self.end_stage_animation()

        progress_percent = (current_step / total_steps) if total_steps > 0 else 0
        final_value = int(progress_percent * 1000)

        self.stage_progress_bar.setValue(final_value)
        self.stage_progress_bar.setFormat(f"{progress_percent * 100:.0f}%")
        if self.DEBUG:
            self.update_status(f"DEBUG: Stage '{stage_name}' progress: {progress_percent * 100:.0f}%")

    def start_stage_animation(self, estimated_duration: float, end_step: int):
        """Starts a smooth animation for the stage progress bar.

        Args:
            estimated_duration: The estimated time in seconds for the task.
            end_step: The target step value for the animation.
        """
        self.animation_start_time = time.monotonic()
        self.animation_duration = estimated_duration
        self.animation_start_value = self.stage_progress_bar.value()

        if self.total_steps_for_stage > 0:
            self.animation_end_value = int((end_step / self.total_steps_for_stage) * 1000)
        else:
            self.animation_end_value = 0

        if self.animation_start_value >= self.animation_end_value:
            return

        self.animation_active = True
        if not self.animation_timer.isActive():
            self.animation_timer.start(50)

    def end_stage_animation(self):
        """Stops the stage progress bar animation."""
        self.animation_active = False
        if self.animation_timer.isActive():
            self.animation_timer.stop()

    def update_animation(self):
        """Updates the progress bar animation frame by frame."""
        if not self.animation_active:
            return

        elapsed = time.monotonic() - self.animation_start_time

        if self.animation_duration > 0:
            progress_ratio = min(elapsed / self.animation_duration, 1.0)
        else:
            progress_ratio = 1.0

        value_range = self.animation_end_value - self.animation_start_value
        current_value = self.animation_start_value + int(value_range * progress_ratio)

        current_value = min(current_value, self.animation_end_value)

        self.stage_progress_bar.setValue(current_value)
        percent = (current_value / 1000) * 100
        self.stage_progress_bar.setFormat(f"{percent:.0f}%")

    def update_status(self, message: str, log_type: str = "default"):
        """Appends a message to the status log text box."""
        self.status_text.append(message)

    def update_clock(self):
        """Updates the elapsed time and ETA labels."""
        elapsed_sec = time.monotonic() - self.start_time
        self.elapsed_label.setText(f"Elapsed: {format_time(elapsed_sec)}")

        if hasattr(self, "profiler") and self.profiler and self.profiler.current_phase:
            current_stage_progress_ratio = self.stage_progress_bar.value() / 1000.0
            eta_sec = self.profiler.get_time_remaining(current_stage_progress=current_stage_progress_ratio)

            if eta_sec is not None:
                time_remaining_str = format_time(eta_sec)
                self.eta_label.setText(f"Time Remaining: {time_remaining_str}")
                if self.DEBUG and int(elapsed_sec) % 5 == 0:
                    overall_progress = self.overall_progress_bar.value() / 10.0
                    stage_progress = self.stage_progress_bar.value() / 10.0
                    self.update_status(
                        f"DEBUG: Time Remaining: {time_remaining_str} | "
                        f"Overall: {overall_progress:.1f}% | "
                        f"Stage: {stage_progress:.1f}%"
                    )
            else:
                self.eta_label.setText("Time Remaining: N/A")
        else:
            self.eta_label.setText("Time Remaining: N/A")

    def study_finished(self, error: bool = False):
        """Handles study completion, stopping timers and updating the UI."""
        self.clock_timer.stop()
        self.queue_timer.stop()
        self.end_stage_animation()
        if not error:
            self.update_status("--- Study Finished ---", log_type="success")
            self.overall_progress_bar.setValue(self.overall_progress_bar.maximum())
            self.stage_label.setText("Finished")
        else:
            self.update_status("--- Study Finished with Errors ---", log_type="fatal")
            self.stage_label.setText("Error")

        self.stop_button.setEnabled(False)
        self.tray_button.setEnabled(False)
        QTimer.singleShot(3000, self.close)

    def closeEvent(self, event):
        """Handles the window close event, ensuring worker process termination."""
        if self.tray_icon.isVisible():
            self.tray_icon.hide()

        if self.process.is_alive():
            self.progress_logger.info("Terminating study process...", extra={"log_type": "warning"})
            self.process.terminate()
            self.process.join(timeout=5)

        shutdown_loggers()
        event.accept()
