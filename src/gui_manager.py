import sys
import time
import multiprocessing
import logging
import traceback
from queue import Empty
from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon, QAction
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QProgressBar,
                                 QLabel, QTextEdit, QGridLayout, QPushButton,
                                 QHBoxLayout, QSystemTrayIcon, QMenu)

from src.studies.near_field_study import NearFieldStudy
from src.studies.far_field_study import FarFieldStudy
from src.utils import format_time, ensure_s4l_running
from src.logging_manager import setup_loggers, shutdown_loggers

def study_process_wrapper(queue, config_filename, execution_control):
    """
    This function runs in a separate process and executes the study.
    It communicates with the main GUI process via a queue.
    """
    # Configure logging for this process to write to the same files
    progress_logger, verbose_logger, _ = setup_loggers()
    
    try:
        ensure_s4l_running()

        class QueueGUI:
            def __init__(self, queue):
                self.queue = queue
                self.profiler = None

            def log(self, message, level='verbose'):
                """Logs a message by sending it to the GUI if it's a progress message."""
                # Also log to the actual file/console from the worker process
                if level == 'progress':
                    self.queue.put({'type': 'status', 'message': message})

            def update_overall_progress(self, current_step, total_steps):
                self.queue.put({'type': 'overall_progress', 'current': current_step, 'total': total_steps})

            def update_stage_progress(self, stage_name, current_step, total_steps):
                self.queue.put({'type': 'stage_progress', 'name': stage_name, 'current': current_step, 'total': total_steps})

            def start_stage_animation(self, task_name, end_value):
                estimate = self.profiler.get_subtask_estimate(task_name)
                self.queue.put({'type': 'start_animation', 'estimate': estimate, 'end_value': end_value})

            def end_stage_animation(self):
                self.queue.put({'type': 'end_animation'})
                
            def update_timing(self, elapsed_sec, eta_sec):
                self.queue.put({'type': 'timing', 'elapsed': elapsed_sec, 'eta': eta_sec})

            def update_profiler(self):
                self.queue.put({'type': 'profiler_object', 'obj': self.profiler})

        from src.config import Config
        import os
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        config = Config(base_dir, config_filename)
        study_type = config.get_setting('study_type')

        if study_type == 'near_field':
            study = NearFieldStudy(config_filename=config_filename, gui=QueueGUI(queue))
        elif study_type == 'far_field':
            study = FarFieldStudy(config_filename=config_filename, gui=QueueGUI(queue))
        else:
            queue.put({'type': 'status', 'message': f"Error: Unknown or missing study type '{study_type}' in {config_filename}"})
            return
            
        study.gui.profiler = study.profiler
        queue.put({'type': 'profiler_object', 'obj': study.profiler})
        study.run()
        queue.put({'type': 'finished'})
    except Exception as e:
        progress_logger.error(f"FATAL ERROR in study process: {e}\n{traceback.format_exc()}")
        queue.put({'type': 'status', 'message': f"FATAL ERROR: Check verbose log for details."})
        queue.put({'type': 'finished'}) # Still signal finished to unblock GUI
    finally:
        # This is crucial for ensuring logs are written to disk.
        shutdown_loggers()


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

        self.queue = multiprocessing.Queue()
        self.profiler = None  # Placeholder for the profiler object
        from src.config import Config
        import os
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        config = Config(base_dir, self.config_filename)
        self.study_type = config.get_setting('study_type')

        if not self.study_type:
            self.update_status(f"FATAL ERROR: 'study_type' not found in {self.config_filename}")
            return

        # The study needs to be instantiated here to get the execution_control settings
        if self.study_type == 'near_field':
            study = NearFieldStudy(config_filename=self.config_filename)
        else:
            study = FarFieldStudy(config_filename=self.config_filename)
        
        execution_control = study.config.get_setting('execution_control')

        self.process = multiprocessing.Process(
            target=study_process_wrapper,
            args=(self.queue, self.config_filename, execution_control)
        )

        self.queue_timer = QTimer(self)
        self.queue_timer.timeout.connect(self.process_queue)
        self.queue_timer.start(100)

        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self.update_clock)
        # We start the clock timer after receiving the profiler object
        # to avoid a race condition where the clock ticks before the profiler exists.
        
        self.process.start()

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

    def stop_study(self):
        """Logs the stop message and closes the application."""
        message = "--- Study manually stopped by user ---"
        self.progress_logger.info(message)
        self.verbose_logger.info(message)
        self.update_status(message)
        self.stop_button.setEnabled(False)
        self.tray_button.setEnabled(False)
        
        # Forcefully terminate the worker process first
        if self.process.is_alive():
            self.process.terminate()
            self.process.join(timeout=3)
            
        # Now, explicitly shut down the loggers to write the final message
        shutdown_loggers()
        
        # Close the GUI window
        QTimer.singleShot(100, self.close)

    def process_queue(self):
        while not self.queue.empty():
            try:
                msg = self.queue.get_nowait()
                msg_type = msg.get('type')

                if msg_type == 'status':
                    self.update_status(msg['message'])
                elif msg_type == 'overall_progress':
                    self.update_overall_progress(msg['current'], msg['total'])
                elif msg_type == 'stage_progress':
                    self.update_stage_progress(msg['name'], msg['current'], msg['total'])
                elif msg_type == 'start_animation':
                    self.start_stage_animation(msg['estimate'], msg['end_value'])
                elif msg_type == 'end_animation':
                    self.end_stage_animation()
                elif msg_type == 'timing':
                    # This is now mostly deprecated in favor of the GUI's internal clock,
                    # but we keep it for any direct calls that might still exist.
                    self.update_timing(msg['elapsed'], msg['eta'])
                elif msg_type == 'profiler_object':
                    self.profiler = msg['obj']
                    # Start the clock timer only after we have the profiler
                    if not self.clock_timer.isActive():
                        self.clock_timer.start(1000)
                elif msg_type == 'finished':
                    self.study_finished()
            except Empty:
                break

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
        self.queue_timer.stop()
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
            
        if self.process.is_alive():
            self.progress_logger.warning("GUI closed unexpectedly. Terminating worker process.")
            self.process.terminate()
            self.process.join(timeout=3)
            
        # This is crucial to ensure all log files are properly closed.
        shutdown_loggers()
        event.accept()

if __name__ == '__main__':
    multiprocessing.freeze_support()
    # Setup loggers for the main process
    setup_loggers()
    app = QApplication(sys.argv)
    # This is for standalone testing of the GUI, so we don't pass a custom config.
    gui = ProgressGUI(config_filename='todays_far_field_config.json')
    gui.show()
    sys.exit(app.exec())
