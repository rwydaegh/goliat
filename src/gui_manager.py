import sys
import time
import logging
import traceback
from PySide6.QtCore import QTimer, QObject, Signal, QThread
from PySide6.QtGui import QIcon, QAction
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QProgressBar,
                                 QLabel, QTextEdit, QGridLayout, QPushButton,
                                 QHBoxLayout, QSystemTrayIcon, QMenu)

from src.studies.near_field_study import NearFieldStudy
from src.studies.far_field_study import FarFieldStudy
from src.utils import format_time, ensure_s4l_running
from src.logging_manager import setup_loggers, shutdown_loggers

class StudyWorker(QObject):
    """
    This worker runs the study in a separate thread.
    It communicates with the main GUI thread via signals.
    """
    status_updated = Signal(str)
    overall_progress_updated = Signal(int, int)
    stage_progress_updated = Signal(str, int, int)
    animation_started = Signal(float, int)
    animation_ended = Signal()
    timing_updated = Signal(float, float)
    profiler_updated = Signal(object)
    study_ready = Signal(object)  # Signal to pass the ready study object to the main thread
    finished = Signal()

    def __init__(self, config_filename):
        super().__init__()
        self.config_filename = config_filename
        self._is_stopped = False

    def run(self):
        """
        Prepares the study object and passes it to the main thread for execution.
        The actual study logic runs on the main thread to avoid S4L API conflicts.
        """
        try:
            # This class now acts as a bridge, so it needs access to the worker's signals
            class SignalGUI:
                def __init__(self, worker):
                    self.worker = worker
                    self.profiler = None

                def log(self, message, level='verbose'):
                    if level == 'progress':
                        self.worker.status_updated.emit(message)

                def update_overall_progress(self, current_step, total_steps):
                    self.worker.overall_progress_updated.emit(current_step, total_steps)

                def update_stage_progress(self, stage_name, current_step, total_steps):
                    self.worker.stage_progress_updated.emit(stage_name, current_step, total_steps)

                def start_stage_animation(self, task_name, end_value):
                    estimate = self.profiler.get_subtask_estimate(task_name)
                    self.worker.animation_started.emit(estimate, end_value)

                def end_stage_animation(self):
                    self.worker.animation_ended.emit()
                    
                def update_timing(self, elapsed_sec, eta_sec):
                    self.worker.timing_updated.emit(elapsed_sec, eta_sec)

                def update_profiler(self):
                    self.worker.profiler_updated.emit(self.profiler)

                def process_events(self):
                    # This is called from the main thread now, so we can process events.
                    QApplication.processEvents()

            from src.config import Config
            import os
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
            config = Config(base_dir, self.config_filename)
            study_type = config.get_setting('study_type')

            if study_type == 'near_field':
                study = NearFieldStudy(config_filename=self.config_filename, gui=SignalGUI(self))
            elif study_type == 'far_field':
                study = FarFieldStudy(config_filename=self.config_filename, gui=SignalGUI(self))
            else:
                self.status_updated.emit(f"Error: Unknown or missing study type '{study_type}' in {self.config_filename}")
                self.finished.emit()
                return
            
            study.gui.profiler = study.profiler
            self.profiler_updated.emit(study.profiler)
            
            # Pass the created study object to the main thread
            self.study_ready.emit(study)

        except Exception as e:
            logging.getLogger('progress').error(f"FATAL ERROR during study setup in worker thread: {e}\n{traceback.format_exc()}")
            self.status_updated.emit("FATAL ERROR: Check verbose log for details.")
            self.finished.emit()

    def stop(self):
        self._is_stopped = True


class ProgressGUI(QWidget):
    def __init__(self, config_filename=None):
        super().__init__()
        self.config_filename = config_filename
        self.start_time = time.monotonic()
        self.progress_logger = logging.getLogger('progress')
        self.verbose_logger = logging.getLogger('verbose')
        self.init_ui()

        self.phase_name_map = {
            "Setup": "setup",
            "Running Simulation": "run",
            "Extracting Results": "extract"
        }
        
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self.update_animation)
        self.animation_active = False
        self.animation_start_time = 0
        self.animation_duration = 0
        self.animation_start_value = 0
        self.animation_end_value = 0
        self.total_steps_for_stage = 0

        self.profiler = None  # Placeholder for the profiler object
        
        self.setup_worker_thread()

        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self.update_clock)
        # We start the clock timer after receiving the profiler object
        # to avoid a race condition where the clock ticks before the profiler exists.

    def init_ui(self):
        self.setWindowTitle("Simulation Progress")
        self.layout = QVBoxLayout()
        self.grid_layout = QGridLayout()

        self.overall_progress_label = QLabel("Overall Progress:")
        self.layout.addWidget(self.overall_progress_label)
        self.overall_progress_bar = QProgressBar(self)
        self.overall_progress_bar.setRange(0, 1000)
        self.layout.addWidget(self.overall_progress_bar)

        self.stage_label = QLabel("Current Stage:")
        self.layout.addWidget(self.stage_label)
        self.stage_progress_bar = QProgressBar(self)
        self.stage_progress_bar.setRange(0, 1000)
        self.layout.addWidget(self.stage_progress_bar)

        self.elapsed_label = QLabel("Elapsed: N/A")
        self.eta_label = QLabel("Time Remaining: N/A")
        self.grid_layout.addWidget(self.elapsed_label, 0, 0)
        self.grid_layout.addWidget(self.eta_label, 0, 1)
        self.layout.addLayout(self.grid_layout)

        self.status_log_label = QLabel("Status Log:")
        self.layout.addWidget(self.status_log_label)
        self.status_text = QTextEdit(self)
        self.status_text.setReadOnly(True)
        self.layout.addWidget(self.status_text)

        # --- Buttons ---
        self.button_layout = QHBoxLayout()
        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.stop_study)
        self.tray_button = QPushButton("Run in Background")
        self.tray_button.clicked.connect(self.hide_to_tray)
        self.button_layout.addWidget(self.stop_button)
        self.button_layout.addWidget(self.tray_button)
        self.layout.addLayout(self.button_layout)
        # --- End Buttons ---

        self.setLayout(self.layout)

        # --- System Tray Icon ---
        self.tray_icon = QSystemTrayIcon(self)
        # Use a standard icon from the current style
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
        # --- End System Tray Icon ---

    def tray_icon_activated(self, reason):
        """Handle tray icon activation."""
        if reason == QSystemTrayIcon.ActivationReason.Trigger:  # Left-click
            self.show_from_tray()

    def hide_to_tray(self):
        """Hide the main window and show the tray icon."""
        self.hide()
        self.tray_icon.show()

    def show_from_tray(self):
        """Show the main window and hide the tray icon."""
        self.show()
        self.tray_icon.hide()

    def setup_worker_thread(self):
        """Sets up and starts the worker thread for the study."""
        self.thread = QThread()
        self.worker = StudyWorker(self.config_filename)
        self.worker.moveToThread(self.thread)
        self.thread.setParent(self) # Set parent to ensure proper cleanup

        # Connect worker signals to GUI slots
        self.worker.status_updated.connect(self.update_status)
        self.worker.overall_progress_updated.connect(self.update_overall_progress)
        self.worker.stage_progress_updated.connect(self.update_stage_progress)
        self.worker.animation_started.connect(self.start_stage_animation)
        self.worker.animation_ended.connect(self.end_stage_animation)
        self.worker.timing_updated.connect(self.update_timing)
        self.worker.profiler_updated.connect(self.on_profiler_updated)
        self.worker.study_ready.connect(self.start_study)  # Connect the new signal
        self.worker.finished.connect(self.study_finished)

        # Connect thread signals
        self.thread.started.connect(self.worker.run)
        # The worker now emits 'finished' from the main thread after study.run() completes
        # self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

        self.thread.start()

    def stop_study(self):
        """Requests the worker thread to stop and disables buttons."""
        message = "--- Study manually stopped by user ---"
        self.progress_logger.info(message)
        self.verbose_logger.info(message)
        self.update_status(message)
        self.stop_button.setEnabled(False)
        self.tray_button.setEnabled(False)
        
        if self.thread.isRunning():
            self.worker.stop()  # Signal the worker to stop
            self.thread.quit()   # Ask the event loop to quit
            self.thread.wait(5000) # Wait for 5 seconds for clean exit

    def on_profiler_updated(self, profiler_obj):
        """Receives the profiler object from the worker thread."""
        self.profiler = profiler_obj
        if not self.clock_timer.isActive():
            self.clock_timer.start(1000)

    def start_study(self, study_instance):
        """
        This slot is executed on the main GUI thread.
        It runs the study, which contains the blocking S4L API calls.
        """
        try:
            study_instance.run()
        except Exception as e:
            logging.getLogger('progress').error(f"FATAL ERROR in study execution: {e}\n{traceback.format_exc()}")
            self.update_status("FATAL ERROR: Check verbose log for details.")
        finally:
            # Manually emit finished and quit the thread
            self.worker.finished.emit()
            self.thread.quit()

    def update_overall_progress(self, current_step, total_steps):
        if total_steps > 0:
            progress_percent = (current_step / total_steps) * 100
            self.overall_progress_bar.setValue(int(progress_percent * 10))
            self.overall_progress_bar.setFormat(f"{progress_percent:.1f}%")

    def update_stage_progress(self, stage_name, current_step, total_steps):
        self.stage_label.setText(f"Current Stage: {stage_name}")
        self.total_steps_for_stage = total_steps
        
        self.end_stage_animation()
        
        progress_percent = (current_step / total_steps) if total_steps > 0 else 0
        final_value = int(progress_percent * 1000)

        self.stage_progress_bar.setValue(final_value)
        self.stage_progress_bar.setFormat(f"{progress_percent * 100:.0f}%")
        
        if self.profiler:
            phase_name = self.phase_name_map.get(stage_name, "")
            if phase_name:
                overall_progress = self.profiler.get_weighted_progress(phase_name, progress_percent)
                self.update_overall_progress(overall_progress, 100)

    def start_stage_animation(self, estimated_duration, end_step):
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
        self.animation_active = False
        if self.animation_timer.isActive():
            self.animation_timer.stop()

    def update_animation(self):
        if not self.animation_active:
            return

        elapsed = time.monotonic() - self.animation_start_time
        
        if self.animation_duration > 0:
            progress_ratio = min(elapsed / self.animation_duration, 1.0)
        else:
            progress_ratio = 1.0

        value_range = self.animation_end_value - self.animation_start_value
        current_value = self.animation_start_value + int(value_range * progress_ratio)
        
        # Ensure we don't overshoot during animation
        current_value = min(current_value, self.animation_end_value)

        self.stage_progress_bar.setValue(current_value)
        percent = (current_value / 1000) * 100
        self.stage_progress_bar.setFormat(f"{percent:.0f}%")

        # Update overall progress in real-time
        if self.profiler:
            display_name = self.stage_label.text().replace("Current Stage: ", "")
            phase_name = self.phase_name_map.get(display_name, "")
            if phase_name:
                stage_percent = current_value / 1000
                overall_progress = self.profiler.get_weighted_progress(phase_name, stage_percent)
                self.update_overall_progress(overall_progress, 100)

    def update_status(self, message):
        self.status_text.append(message)

    def update_timing(self, elapsed_sec, eta_sec):
        # This method is called from the queue, but the main clock timer is the primary source of truth.
        # We update the label here as a fallback.
        if eta_sec is not None:
            self.eta_label.setText(f"Time Remaining: {format_time(eta_sec)}")
        else:
            self.eta_label.setText("Time Remaining: N/A")

    def update_clock(self):
        elapsed_sec = time.monotonic() - self.start_time
        self.elapsed_label.setText(f"Elapsed: {format_time(elapsed_sec)}")

        if self.profiler and self.profiler.current_phase:
            current_stage_progress_ratio = self.stage_progress_bar.value() / 1000.0
            eta_sec = self.profiler.get_time_remaining(current_stage_progress=current_stage_progress_ratio)
            overall_progress = self.overall_progress_bar.value() / 10.0

            if eta_sec is not None:
                self.eta_label.setText(f"Time Remaining: {format_time(eta_sec)}")
            else:
                self.eta_label.setText("Time Remaining: N/A")

            # # Debug log as requested, using WARNING to make it stand out
            # self.verbose_logger.warning(
            #     f"GUI_Tick: Elapsed={format_time(elapsed_sec)}, "
            #     f"ETA={format_time(eta_sec) if eta_sec is not None else 'N/A'}, "
            #     f"Overall_Progress={overall_progress:.1f}%"
            # )
        else:
            self.eta_label.setText("Time Remaining: N/A")

    def study_finished(self):
        self.clock_timer.stop()
        self.end_stage_animation()
        self.update_status("--- Study Finished ---")
        self.overall_progress_bar.setValue(self.overall_progress_bar.maximum())
        self.stage_label.setText("Finished")
        self.stop_button.setEnabled(False)
        self.tray_button.setEnabled(False)
        QTimer.singleShot(2000, self.close)

    def closeEvent(self, event):
        """
        Ensures the worker process is terminated and loggers are shut down
        when the application is closed.
        """
        if self.tray_icon.isVisible():
            self.tray_icon.hide()

        # The thread is now a child of the QWidget, so Qt will handle its cleanup.
        # We just need to ensure the loggers are shut down.
        shutdown_loggers()
        event.accept()

if __name__ == '__main__':
    # Setup loggers for the main process
    setup_loggers()
    app = QApplication(sys.argv)
    # This is for standalone testing of the GUI, so we don't pass a custom config.
    gui = ProgressGUI(config_filename='todays_far_field_config.json')
    gui.show()
    sys.exit(app.exec())
