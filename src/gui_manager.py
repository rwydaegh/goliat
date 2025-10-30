import csv
import hashlib
import logging
import numpy as np
import os
import time
import traceback
from datetime import datetime
from logging import Logger
from multiprocessing import Process, Queue
from multiprocessing.synchronize import Event

import matplotlib

matplotlib.use("Qt5Agg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.dates as mdates

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QAction, QIcon
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
    QTabWidget,
    QTableWidget,
    QHeaderView,
    QTableWidgetItem,
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

    def update_simulation_details(self, sim_count: int, total_sims: int, details: str):
        """Sends simulation details to the GUI."""
        self.queue.put(
            {
                "type": "sim_details",
                "count": sim_count,
                "total": total_sims,
                "details": details,
            }
        )

    def update_overall_progress(self, current_step: int, total_steps: int):
        """Sends an overall progress update to the queue."""
        self.queue.put({"type": "overall_progress", "current": current_step, "total": total_steps})

    def update_stage_progress(self, stage_name: str, current_step: int, total_steps: int, sub_stage: str = ""):
        """Sends a stage-specific progress update to the queue."""
        self.queue.put(
            {
                "type": "stage_progress",
                "name": stage_name,
                "current": current_step,
                "total": total_steps,
                "sub_stage": sub_stage,
            }
        )

    def start_stage_animation(self, task_name: str, end_value: int):
        """Sends a command to start a progress bar animation."""
        if task_name in ["setup", "run", "extract"]:
            estimate = self.profiler.profiling_config.get(f"avg_{task_name}_time", 60)
        else:
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
        init_window_title: str = "",
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
        self.init_window_title = init_window_title
        self.DEBUG = False
        self.study_is_finished = False
        self.study_had_errors = False

        self.warning_count = 0
        self.error_count = 0
        self.total_simulations = 0
        self.current_simulation_count = 0

        # Time remaining tracking for graph
        self.time_remaining_data = []  # List of (timestamp, hours_remaining)
        self.max_time_remaining_seen = 0.0

        # Overall progress tracking for graph
        self.overall_progress_data = []  # List of (timestamp, progress_percent)
        self.max_progress_seen = 0.0

        # Generate unique hash for this GUI instance
        self.session_hash = hashlib.md5(f"{time.time()}_{os.getpid()}".encode()).hexdigest()[:8]
        self.data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
        os.makedirs(self.data_dir, exist_ok=True)

        # Generate timestamp for filenames
        session_timestamp = datetime.now().strftime("%d-%m_%H-%M-%S")

        # Cleanup old CSV files before creating new ones
        self._cleanup_old_data_files()

        self.time_remaining_file = os.path.join(self.data_dir, f"time_remaining_{session_timestamp}_{self.session_hash}.csv")
        self.overall_progress_file = os.path.join(self.data_dir, f"overall_progress_{session_timestamp}_{self.session_hash}.csv")

        # Initialize data files
        with open(self.time_remaining_file, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "hours_remaining"])

        with open(self.overall_progress_file, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "progress_percent"])

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

        # Graph update timer (every 5 seconds)
        self.graph_timer = QTimer(self)
        self.graph_timer.timeout.connect(self.update_graphs)
        self.graph_timer.start(5000)

    def init_ui(self):
        """Initializes and arranges all UI widgets."""
        self.setWindowTitle(self.init_window_title)
        self.resize(800, 900)

        # Set window icon
        icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "img", "favicon.svg")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.setStyleSheet("""
            ProgressGUI {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                           stop:0 #2b2b2b, stop:1 #b87d16);
            }
            QWidget {
                color: #f0f0f0;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QTabWidget::pane {
                border-top: 2px solid #3c3c3c;
                background-color: transparent;
            }
            QTabBar::tab {
                background: #2b2b2b;
                border: 1px solid #3c3c3c;
                padding: 10px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background: #3c3c3c;
                border-bottom-color: #3c3c3c;
            }
            QLabel {
                font-size: 14px;
            }
            QPushButton {
                background-color: #555;
                border: 1px solid #666;
                padding: 10px;
                border-radius: 4px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #666;
            }
            QPushButton:pressed {
                background-color: #777;
            }
            QProgressBar {
                border: 1px solid #444;
                border-radius: 4px;
                text-align: center;
                font-size: 14px;
                height: 24px;
            }
            QProgressBar::chunk {
                background-color: #007acc;
                border-radius: 3px;
            }
            QTextEdit {
                background-color: #222;
                border: 1px solid #444;
                border-radius: 4px;
                font-family: 'Consolas', 'Courier New', monospace;
                white-space: pre;
            }
            QTableWidget {
                gridline-color: #444;
            }
            QHeaderView::section {
                background-color: #3c3c3c;
                padding: 4px;
                border: 1px solid #444;
            }
        """)

        main_layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # --- Progress Tab ---
        progress_widget = QWidget()
        progress_layout = QVBoxLayout(progress_widget)
        self.tabs.addTab(progress_widget, "Progress")

        # Info Grid
        info_grid = QGridLayout()
        self.sim_counter_label = QLabel("Simulation: N/A")
        self.sim_details_label = QLabel("Current Case: N/A")
        self.error_counter_label = QLabel("⚠️ Warnings: 0 | ❌ Errors: 0")
        info_grid.addWidget(self.sim_counter_label, 0, 0)
        info_grid.addWidget(self.sim_details_label, 1, 0)
        info_grid.addWidget(self.error_counter_label, 0, 1, 2, 1, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignCenter)
        progress_layout.addLayout(info_grid)

        self.overall_progress_label = QLabel("Overall Progress:")
        progress_layout.addWidget(self.overall_progress_label)
        self.overall_progress_bar = QProgressBar(self)
        self.overall_progress_bar.setRange(0, 10000)
        progress_layout.addWidget(self.overall_progress_bar)

        self.stage_label = QLabel("Current Stage:")
        progress_layout.addWidget(self.stage_label)
        self.stage_progress_bar = QProgressBar(self)
        self.stage_progress_bar.setRange(0, 1000)
        progress_layout.addWidget(self.stage_progress_bar)

        time_layout = QHBoxLayout()
        self.elapsed_label = QLabel("Elapsed: N/A")
        self.eta_label = QLabel("Time Remaining: N/A")
        time_layout.addWidget(self.elapsed_label)
        time_layout.addStretch()
        time_layout.addWidget(self.eta_label)
        progress_layout.addLayout(time_layout)

        self.status_log_label = QLabel("High-level progress log:")
        progress_layout.addWidget(self.status_log_label)
        self.status_text = QTextEdit(self)
        self.status_text.setReadOnly(True)
        progress_layout.addWidget(self.status_text)

        # --- Timings Tab ---
        timings_widget = QWidget()
        timings_layout = QVBoxLayout(timings_widget)
        self.tabs.addTab(timings_widget, "Timings")
        self.timings_table = QTableWidget()
        self.timings_table.setColumnCount(10)
        self.timings_table.setHorizontalHeaderLabels(
            ["Phase", "Subtask", "Mean (s)", "Median (s)", "Min (s)", "Max (s)", "10% (s)", "25% (s)", "75% (s)", "90% (s)"]
        )
        self.timings_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        timings_layout.addWidget(self.timings_table)

        # --- Timings Piecharts Tab ---
        piecharts_widget = QWidget()
        piecharts_layout = QVBoxLayout(piecharts_widget)
        self.tabs.addTab(piecharts_widget, "Timings Piecharts")

        # Create matplotlib figure with 4 subplots arranged in 2x2 grid
        self.pie_figure = Figure(figsize=(12, 10), facecolor="#2b2b2b")
        self.pie_canvas = FigureCanvas(self.pie_figure)
        self.pie_axes = [
            self.pie_figure.add_subplot(221),  # Top-left: Phase weights
            self.pie_figure.add_subplot(222),  # Top-right: Setup subtasks
            self.pie_figure.add_subplot(223),  # Bottom-left: Run subtasks
            self.pie_figure.add_subplot(224),  # Bottom-right: Extract subtasks
        ]
        piecharts_layout.addWidget(self.pie_canvas)
        self._setup_piecharts()

        # --- Time Remaining Tab ---
        time_remaining_widget = QWidget()
        time_remaining_layout = QVBoxLayout(time_remaining_widget)
        self.tabs.addTab(time_remaining_widget, "Time Remaining")

        self.tr_figure = Figure(figsize=(10, 6), facecolor="#2b2b2b")
        self.tr_canvas = FigureCanvas(self.tr_figure)
        self.tr_ax = self.tr_figure.add_subplot(111)
        time_remaining_layout.addWidget(self.tr_canvas)
        self._setup_time_remaining_plot()

        # --- Overall Progress Tab ---
        overall_progress_widget = QWidget()
        overall_progress_layout = QVBoxLayout(overall_progress_widget)
        self.tabs.addTab(overall_progress_widget, "Overall Progress")

        self.op_figure = Figure(figsize=(10, 6), facecolor="#2b2b2b")
        self.op_canvas = FigureCanvas(self.op_figure)
        self.op_ax = self.op_figure.add_subplot(111)
        overall_progress_layout.addWidget(self.op_canvas)
        self._setup_overall_progress_plot()

        # --- Buttons ---
        self.button_layout = QHBoxLayout()
        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.stop_study)
        self.tray_button = QPushButton("Run in Background")
        self.tray_button.clicked.connect(self.hide_to_tray)
        self.button_layout.addWidget(self.stop_button)
        self.button_layout.addWidget(self.tray_button)
        main_layout.addLayout(self.button_layout)

        self.tray_icon = QSystemTrayIcon(self)
        icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "img", "favicon.svg")
        if os.path.exists(icon_path):
            self.tray_icon.setIcon(QIcon(icon_path))
        else:
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
                    self.update_stage_progress(msg["name"], msg["current"], msg["total"], msg.get("sub_stage", ""))
                elif msg_type == "start_animation":
                    self.start_stage_animation(msg["estimate"], msg["end_value"])
                elif msg_type == "end_animation":
                    self.end_stage_animation()
                elif msg_type == "profiler_update":
                    self.profiler = msg.get("profiler")
                    if self.profiler:
                        self.profiler_phase = self.profiler.current_phase
                        self.update_timings_tab()
                elif msg_type == "sim_details":
                    self.update_simulation_details(msg["count"], msg["total"], msg["details"])
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
        if self.DEBUG and isinstance(current_step, int):
            self.update_status(f"DEBUG: update_overall_progress received: current={current_step}, total={total_steps}")
        if total_steps > 0:
            progress_percent = (current_step / total_steps) * 100
            self.overall_progress_bar.setValue(int(progress_percent * 100))
            self.overall_progress_bar.setFormat(f"{progress_percent:.2f}%")
            if self.DEBUG and isinstance(current_step, int):
                self.update_status(f"DEBUG: Overall progress set to: {progress_percent:.2f}%")

    def update_stage_progress(self, stage_name: str, current_step: int, total_steps: int, sub_stage: str = ""):
        """Updates the stage-specific progress bar."""
        if self.DEBUG:
            self.update_status(
                f"DEBUG: update_stage_progress received: name='{stage_name}', current={current_step}, total={total_steps}, sub_stage='{sub_stage}'"
            )

        # Simple stage label without sub_stage details
        self.stage_label.setText(f"Current Stage: {stage_name}")

        self.total_steps_for_stage = total_steps

        self.end_stage_animation()

        progress_percent = (current_step / total_steps) if total_steps > 0 else 0
        final_value = int(progress_percent * 1000)

        self.stage_progress_bar.setValue(final_value)
        self.stage_progress_bar.setFormat(f"{progress_percent * 100:.0f}%")
        if self.DEBUG:
            self.update_status(f"DEBUG: Stage '{stage_name}' progress set to: {progress_percent * 100:.0f}%")

    def start_stage_animation(self, estimated_duration: float, end_step: int):
        """Starts a smooth animation for the stage progress bar.

        Args:
            estimated_duration: The estimated time in seconds for the task.
            end_step: The target step value for the animation.
        """
        if self.DEBUG:
            self.update_status(f"DEBUG: start_stage_animation received: duration={estimated_duration:.2f}s, end_step={end_step}")
        self.animation_start_time = time.monotonic()
        self.animation_duration = estimated_duration
        self.animation_start_value = self.stage_progress_bar.value()

        self.animation_end_value = 1000

        if self.animation_start_value >= self.animation_end_value:
            if self.DEBUG:
                self.update_status("DEBUG: Animation skipped, start_value >= end_value.")
            return

        self.animation_active = True
        if not self.animation_timer.isActive():
            self.animation_timer.start(50)
        if self.DEBUG:
            self.update_status("DEBUG: Animation started.")

    def end_stage_animation(self):
        """Stops the stage progress bar animation."""
        if self.animation_active and self.DEBUG:
            self.update_status("DEBUG: end_stage_animation called.")
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

        # Also update the overall progress based on the stage animation
        if hasattr(self, "profiler") and self.profiler and self.profiler.current_phase:
            progress = self.profiler.get_weighted_progress(self.profiler.current_phase, percent / 100.0)
            self.update_overall_progress(progress, 100)

    def update_simulation_details(self, sim_count: int, total_sims: int, details: str):
        """Updates the simulation counter and details labels."""
        self.current_simulation_count = sim_count
        self.total_simulations = total_sims
        self.sim_counter_label.setText(f"Simulation: {sim_count} / {total_sims}")
        self.sim_details_label.setText(f"Current Case: {details}")

    def update_timings_tab(self):
        """Populates the timings table with data from the profiler including statistics."""
        if not hasattr(self, "profiler") or not self.profiler:
            return

        self.timings_table.setRowCount(0)

        # Collect all tasks with their raw timing data
        all_tasks = {}
        for phase in ["setup", "run", "extract"]:
            avg_time = self.profiler.profiling_config.get(f"avg_{phase}_time")
            if avg_time is not None:
                raw_times = self.profiler.subtask_times.get(phase, [])
                all_tasks[f"{phase}_total"] = {"phase": phase, "subtask": "---", "raw_times": raw_times if raw_times else [avg_time]}

        # Filter out fake aggregated entries that shouldn't be displayed
        fake_entries = ["setup_simulation", "run_simulation_total", "extract_results_total"]

        for key, value in self.profiler.profiling_config.items():
            if key.startswith("avg_") and "_time" not in key:
                task_name = key.replace("avg_", "")

                # Skip fake aggregated entries
                if task_name in fake_entries:
                    continue

                parts = task_name.split("_", 1)
                phase = parts[0]
                subtask_name = parts[1] if len(parts) > 1 else phase
                raw_times = self.profiler.subtask_times.get(task_name, [])
                all_tasks[key] = {"phase": phase, "subtask": subtask_name, "raw_times": raw_times if raw_times else [value]}

        # Populate table with statistics
        for task_info in all_tasks.values():
            row_position = self.timings_table.rowCount()
            self.timings_table.insertRow(row_position)

            times = task_info.get("raw_times", [])
            if times:
                times_array = np.array(times)
                mean_val = np.mean(times_array)
                median_val = np.median(times_array)
                min_val = np.min(times_array)
                max_val = np.max(times_array)
                p10 = np.percentile(times_array, 10)
                p25 = np.percentile(times_array, 25)
                p75 = np.percentile(times_array, 75)
                p90 = np.percentile(times_array, 90)
            else:
                mean_val = median_val = min_val = max_val = p10 = p25 = p75 = p90 = 0.0

            self.timings_table.setItem(row_position, 0, QTableWidgetItem(task_info.get("phase", "N/A")))
            self.timings_table.setItem(row_position, 1, QTableWidgetItem(task_info.get("subtask", "---")))
            self.timings_table.setItem(row_position, 2, QTableWidgetItem(f"{mean_val:.2f}"))
            self.timings_table.setItem(row_position, 3, QTableWidgetItem(f"{median_val:.2f}"))
            self.timings_table.setItem(row_position, 4, QTableWidgetItem(f"{min_val:.2f}"))
            self.timings_table.setItem(row_position, 5, QTableWidgetItem(f"{max_val:.2f}"))
            self.timings_table.setItem(row_position, 6, QTableWidgetItem(f"{p10:.2f}"))
            self.timings_table.setItem(row_position, 7, QTableWidgetItem(f"{p25:.2f}"))
            self.timings_table.setItem(row_position, 8, QTableWidgetItem(f"{p75:.2f}"))
            self.timings_table.setItem(row_position, 9, QTableWidgetItem(f"{p90:.2f}"))

        # Update pie charts as well
        self._update_piecharts()

    def update_status(self, message: str, log_type: str = "default"):
        """Appends a message to the status log text box with proper color and space preservation."""
        if log_type == "warning":
            self.warning_count += 1
        elif log_type in ["error", "fatal"]:
            self.error_count += 1
        self.error_counter_label.setText(f"⚠️ Warnings: {self.warning_count} | ❌ Errors: {self.error_count}")

        # Color mapping - NOTE: Intentionally using white for "progress" in GUI
        # since all messages shown here are progress updates. This deviates from
        # the terminal color scheme defined in src/colors.py for better readability.
        color_map = {
            "default": "#f0f0f0",  # WHITE
            "progress": "#f0f0f0",  # WHITE (GUI-specific override)
            "info": "#17a2b8",  # CYAN
            "verbose": "#007acc",  # BLUE
            "warning": "#ffc107",  # YELLOW
            "error": "#dc3545",  # RED
            "fatal": "#d63384",  # MAGENTA
            "success": "#5cb85c",  # BRIGHT GREEN
            "header": "#e83e8c",  # BRIGHT MAGENTA
            "highlight": "#ffd700",  # BRIGHT YELLOW
            "caller": "#6c757d",  # DIM (gray)
        }
        color = color_map.get(log_type, "#f0f0f0")

        # Preserve leading spaces by converting them to &nbsp;
        preserved_message = message.replace(" ", "&nbsp;")

        self.status_text.append(f'<span style="color:{color};">{preserved_message}</span>')

    def update_clock(self):
        """Updates the elapsed time and ETA labels."""
        elapsed_sec = time.monotonic() - self.start_time
        self.elapsed_label.setText(f"Elapsed: {format_time(elapsed_sec)}")

        eta_sec = None
        if hasattr(self, "profiler") and self.profiler and self.profiler.current_phase:
            current_stage_progress_ratio = self.stage_progress_bar.value() / 1000.0
            eta_sec = self.profiler.get_time_remaining(current_stage_progress=current_stage_progress_ratio)

            if eta_sec is not None:
                time_remaining_str = format_time(eta_sec)
                self.eta_label.setText(f"Time Remaining: {time_remaining_str}")
            else:
                self.eta_label.setText("Time Remaining: N/A")
        else:
            self.eta_label.setText("Time Remaining: N/A")

        # Note: Graphs are updated separately via graph_timer every 5 seconds

        # Update window title with status
        progress_percent = max(0, self.overall_progress_bar.value() / 100.0)
        title = self.init_window_title
        title += f"[{progress_percent:.2f}%] GOLIAT"
        if self.total_simulations > 0:
            title += f" | Sim {self.current_simulation_count}/{self.total_simulations}"

        # Determine status based on actual activity, not time
        if self.study_is_finished:
            status = "Finished" if not self.study_had_errors else "Finished with Errors"
        elif progress_percent > 0 or self.current_simulation_count > 0:
            status = "Running..."
        else:
            status = "Booting..."

        title += f" | {status}"
        self.setWindowTitle(title)

    def update_graphs(self):
        """Updates both time remaining and overall progress graphs (called every 5 seconds)."""
        # Get current ETA
        eta_sec = None
        if hasattr(self, "profiler") and self.profiler and self.profiler.current_phase:
            current_stage_progress_ratio = self.stage_progress_bar.value() / 1000.0
            eta_sec = self.profiler.get_time_remaining(current_stage_progress=current_stage_progress_ratio)

        # Get current progress
        progress_percent = max(0, self.overall_progress_bar.value() / 100.0)

        # Update time remaining data
        if eta_sec is not None:
            current_time = datetime.now()
            hours_remaining = eta_sec / 3600.0

            if hours_remaining > self.max_time_remaining_seen:
                self.max_time_remaining_seen = hours_remaining

            self.time_remaining_data.append((current_time, hours_remaining))

            try:
                with open(self.time_remaining_file, "a", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow([current_time.isoformat(), hours_remaining])
            except Exception as e:
                self.verbose_logger.error(f"Failed to write time remaining data: {e}")

            self._refresh_time_remaining_plot()

        # Update overall progress data
        current_time = datetime.now()
        if progress_percent > self.max_progress_seen:
            self.max_progress_seen = progress_percent

        self.overall_progress_data.append((current_time, progress_percent))

        try:
            with open(self.overall_progress_file, "a", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([current_time.isoformat(), progress_percent])
        except Exception as e:
            self.verbose_logger.error(f"Failed to write overall progress data: {e}")

        self._refresh_overall_progress_plot()

    def study_finished(self, error: bool = False):
        """Handles study completion, stopping timers and updating the UI."""
        self.study_is_finished = True
        self.study_had_errors = error
        self.clock_timer.stop()
        self.queue_timer.stop()
        self.graph_timer.stop()
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
        self.update_clock()  # Final title update
        QTimer.singleShot(3000, self.close)

    def _setup_time_remaining_plot(self):
        """Initializes the time remaining plot with styling."""
        self.tr_ax.clear()
        self.tr_ax.set_facecolor("#2b2b2b")
        self.tr_figure.patch.set_facecolor("#2b2b2b")

        self.tr_ax.set_xlabel("Time", fontsize=12, color="#f0f0f0")
        self.tr_ax.set_ylabel("Hours Remaining", fontsize=12, color="#f0f0f0")
        self.tr_ax.set_title("Estimated Time Remaining", fontsize=14, color="#f0f0f0", pad=20)

        self.tr_ax.tick_params(colors="#f0f0f0", which="both")
        self.tr_ax.spines["bottom"].set_color("#f0f0f0")
        self.tr_ax.spines["left"].set_color("#f0f0f0")
        self.tr_ax.spines["top"].set_color("#2b2b2b")
        self.tr_ax.spines["right"].set_color("#2b2b2b")

        self.tr_ax.grid(True, alpha=0.2, color="#f0f0f0")

        self.tr_ax.plot([], [], "o-", color="#007acc", linewidth=2, markersize=4, label="Time Remaining")
        self.tr_ax.legend(loc="upper right", facecolor="#3c3c3c", edgecolor="#f0f0f0", labelcolor="#f0f0f0", fontsize=10)

        self.tr_canvas.draw()

    def _refresh_time_remaining_plot(self):
        """Refreshes the time remaining plot with current data."""
        if not self.time_remaining_data:
            return

        self.tr_ax.clear()

        times = [t for t, _ in self.time_remaining_data]
        hours = [h for _, h in self.time_remaining_data]

        self.tr_ax.plot(times, hours, "o-", color="#007acc", linewidth=2, markersize=4, label="Time Remaining")

        self.tr_ax.set_facecolor("#2b2b2b")
        self.tr_ax.set_xlabel("Time", fontsize=12, color="#f0f0f0")
        self.tr_ax.set_ylabel("Hours Remaining", fontsize=12, color="#f0f0f0")
        self.tr_ax.set_title("Estimated Time Remaining", fontsize=14, color="#f0f0f0", pad=20)

        y_max = self.max_time_remaining_seen * 1.1
        self.tr_ax.set_ylim(0, max(y_max, 0.1))

        self.tr_ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
        self.tr_figure.autofmt_xdate(rotation=45)

        self.tr_ax.grid(True, alpha=0.2, color="#f0f0f0")
        self.tr_ax.tick_params(colors="#f0f0f0", which="both")
        self.tr_ax.spines["bottom"].set_color("#f0f0f0")
        self.tr_ax.spines["left"].set_color("#f0f0f0")
        self.tr_ax.spines["top"].set_color("#2b2b2b")
        self.tr_ax.spines["right"].set_color("#2b2b2b")

        self.tr_ax.legend(loc="upper right", facecolor="#3c3c3c", edgecolor="#f0f0f0", labelcolor="#f0f0f0", fontsize=10)

        self.tr_figure.tight_layout()
        self.tr_canvas.draw()

    def _setup_overall_progress_plot(self):
        """Initializes the overall progress plot with styling."""
        self.op_ax.clear()
        self.op_ax.set_facecolor("#2b2b2b")
        self.op_figure.patch.set_facecolor("#2b2b2b")

        self.op_ax.set_xlabel("Time", fontsize=12, color="#f0f0f0")
        self.op_ax.set_ylabel("Progress (%)", fontsize=12, color="#f0f0f0")
        self.op_ax.set_title("Overall Progress", fontsize=14, color="#f0f0f0", pad=20)

        self.op_ax.tick_params(colors="#f0f0f0", which="both")
        self.op_ax.spines["bottom"].set_color("#f0f0f0")
        self.op_ax.spines["left"].set_color("#f0f0f0")
        self.op_ax.spines["top"].set_color("#2b2b2b")
        self.op_ax.spines["right"].set_color("#2b2b2b")

        self.op_ax.grid(True, alpha=0.2, color="#f0f0f0")
        self.op_ax.set_ylim(0, 100)

        self.op_ax.plot([], [], "o-", color="#28a745", linewidth=2, markersize=4, label="Overall Progress")
        self.op_ax.legend(loc="lower right", facecolor="#3c3c3c", edgecolor="#f0f0f0", labelcolor="#f0f0f0", fontsize=10)

        self.op_canvas.draw()

    def _refresh_overall_progress_plot(self):
        """Refreshes the overall progress plot with current data."""
        if not self.overall_progress_data:
            return

        self.op_ax.clear()

        times = [t for t, _ in self.overall_progress_data]
        progress = [p for _, p in self.overall_progress_data]

        self.op_ax.plot(times, progress, "o-", color="#28a745", linewidth=2, markersize=4, label="Overall Progress")

        self.op_ax.set_facecolor("#2b2b2b")
        self.op_ax.set_xlabel("Time", fontsize=12, color="#f0f0f0")
        self.op_ax.set_ylabel("Progress (%)", fontsize=12, color="#f0f0f0")
        self.op_ax.set_title("Overall Progress", fontsize=14, color="#f0f0f0", pad=20)

        self.op_ax.set_ylim(0, 100)

        self.op_ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
        self.op_figure.autofmt_xdate(rotation=45)

        self.op_ax.grid(True, alpha=0.2, color="#f0f0f0")
        self.op_ax.tick_params(colors="#f0f0f0", which="both")
        self.op_ax.spines["bottom"].set_color("#f0f0f0")
        self.op_ax.spines["left"].set_color("#f0f0f0")
        self.op_ax.spines["top"].set_color("#2b2b2b")
        self.op_ax.spines["right"].set_color("#2b2b2b")

        self.op_ax.legend(loc="lower right", facecolor="#3c3c3c", edgecolor="#f0f0f0", labelcolor="#f0f0f0", fontsize=10)

        self.op_figure.tight_layout()
        self.op_canvas.draw()

    def _setup_piecharts(self):
        """Initializes the four pie charts."""
        for ax in self.pie_axes:
            ax.clear()
            ax.set_facecolor("#2b2b2b")
        self.pie_figure.patch.set_facecolor("#2b2b2b")
        self.pie_figure.tight_layout()
        self.pie_canvas.draw()

    def _update_piecharts(self):
        """Updates the four pie charts with timing data."""
        if not hasattr(self, "profiler") or not self.profiler:
            return

        colors = ["#ff6b6b", "#4ecdc4", "#45b7d1", "#f9ca24", "#6c5ce7", "#00b894", "#fdcb6e", "#e17055"]

        # Chart 0 (Top-left): Phase Weights
        ax0 = self.pie_axes[0]
        ax0.clear()
        ax0.set_facecolor("#2b2b2b")

        # Get phase weights/times
        phase_weights = {}
        for phase in ["setup", "run", "extract"]:
            avg_time = self.profiler.profiling_config.get(f"avg_{phase}_time")
            if avg_time is not None:
                phase_weights[phase.capitalize()] = avg_time

        if phase_weights:
            labels = list(phase_weights.keys())
            sizes = list(phase_weights.values())

            pie_result = ax0.pie(
                sizes,
                labels=labels,
                autopct="%1.1f%%",
                startangle=90,
                colors=["#ff6b6b", "#4ecdc4", "#45b7d1"],
                textprops={"color": "#f0f0f0", "fontsize": 10},
            )

            autotexts = pie_result[2] if len(pie_result) > 2 else []
            for autotext in autotexts:
                autotext.set_color("#2b2b2b")
                autotext.set_fontweight("bold")
                autotext.set_fontsize(9)

            ax0.set_title("Phase Weights", fontsize=12, color="#f0f0f0", pad=10)
        else:
            ax0.text(0.5, 0.5, "No data", ha="center", va="center", fontsize=12, color="#f0f0f0", transform=ax0.transAxes)
            ax0.set_title("Phase Weights", fontsize=12, color="#f0f0f0", pad=10)

        # Charts 1-3: Subtasks for each phase
        phases = ["setup", "run", "extract"]
        phase_titles = ["Setup Subtasks", "Run Subtasks", "Extract Subtasks"]

        for i, (phase, title) in enumerate(zip(phases, phase_titles), start=1):
            ax = self.pie_axes[i]
            ax.clear()
            ax.set_facecolor("#2b2b2b")

            # Collect subtask data for this phase
            # Filter out fake aggregated entries
            fake_entries = ["simulation", "simulation_total", "results_total"]

            subtask_data = {}
            for key, value in self.profiler.profiling_config.items():
                if key.startswith(f"avg_{phase}_") and key != f"avg_{phase}_time":
                    # Extract the subtask name (everything after "avg_{phase}_")
                    subtask_key = key.replace(f"avg_{phase}_", "")

                    # Skip fake aggregated entries
                    if subtask_key in fake_entries:
                        continue

                    task_name = subtask_key.replace("_", " ").capitalize()
                    subtask_data[task_name] = value

            if subtask_data:
                labels = list(subtask_data.keys())
                sizes = list(subtask_data.values())

                # Create pie chart
                pie_result = ax.pie(
                    sizes,
                    labels=labels,
                    autopct="%1.1f%%",
                    startangle=90,
                    colors=colors[: len(labels)],
                    textprops={"color": "#f0f0f0", "fontsize": 9},
                )

                # Unpack result safely
                autotexts = pie_result[2] if len(pie_result) > 2 else []

                # Enhance text visibility
                for autotext in autotexts:
                    autotext.set_color("#2b2b2b")
                    autotext.set_fontweight("bold")
                    autotext.set_fontsize(8)

                ax.set_title(title, fontsize=12, color="#f0f0f0", pad=10)
            else:
                ax.text(0.5, 0.5, "No data", ha="center", va="center", fontsize=12, color="#f0f0f0", transform=ax.transAxes)
                ax.set_title(title, fontsize=12, color="#f0f0f0", pad=10)

        self.pie_figure.tight_layout()
        self.pie_canvas.draw()

    def _cleanup_old_data_files(self):
        """Removes old CSV and JSON files from the data/ directory when there are more than 50."""
        try:
            # Get all CSV and JSON files in the data directory
            data_files = []
            for f in os.listdir(self.data_dir):
                if f.endswith(".csv") or f.endswith(".json"):
                    # Only include files with the expected naming pattern
                    if any(prefix in f for prefix in ["time_remaining_", "overall_progress_", "profiling_config_"]):
                        full_path = os.path.join(self.data_dir, f)
                        data_files.append(full_path)

            # Sort by creation time (oldest first)
            data_files.sort(key=os.path.getctime)

            # Remove oldest files if we have more than 50
            while len(data_files) > 50:
                old_file = None
                try:
                    old_file = data_files.pop(0)
                    os.remove(old_file)
                    self.verbose_logger.info(f"Removed old data file: {os.path.basename(old_file)}")
                except OSError as e:
                    if old_file:
                        self.verbose_logger.warning(f"Failed to remove {os.path.basename(old_file)}: {e}")
                    else:
                        self.verbose_logger.warning(f"Failed to remove a file: {e}")
        except Exception as e:
            self.verbose_logger.warning(f"Error during data file cleanup: {e}")

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
