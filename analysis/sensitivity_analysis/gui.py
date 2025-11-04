import sys
import time
from queue import Empty
from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon, QAction
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QProgressBar,
    QLabel,
    QTextEdit,
    QPushButton,
    QHBoxLayout,
    QSystemTrayIcon,
    QMenu,
    QGridLayout,
)


class SensitivityAnalysisGUI(QWidget):
    """A GUI to display the progress of the sensitivity analysis, mirroring the main app's style."""

    def __init__(self, queue, process):
        super().__init__()
        self.queue = queue
        self.process = process
        self.start_time = time.monotonic()
        self.init_ui()

        self.queue_timer = QTimer(self)
        self.queue_timer.timeout.connect(self.process_queue)
        self.queue_timer.start(100)

        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self.update_clock)
        self.clock_timer.start(1000)

    def init_ui(self):
        """Initializes the user interface components."""
        self.setWindowTitle("Sensitivity Analysis Progress")
        self.layout = QVBoxLayout()

        # Overall Progress
        self.overall_progress_label = QLabel("Overall Progress:")
        self.layout.addWidget(self.overall_progress_label)
        self.overall_progress_bar = QProgressBar(self)
        self.overall_progress_bar.setRange(0, 1000)  # Use a finer scale
        self.overall_progress_bar.setFormat("%p%")
        self.layout.addWidget(self.overall_progress_bar)

        # Stage Progress (for individual runs)
        self.stage_label = QLabel("Current Run:")
        self.layout.addWidget(self.stage_label)
        self.stage_progress_bar = QProgressBar(self)
        self.stage_progress_bar.setRange(0, 100)
        self.stage_progress_bar.setFormat("%v/%m steps")
        self.layout.addWidget(self.stage_progress_bar)

        # Timing Info
        self.grid_layout = QGridLayout()
        self.elapsed_label = QLabel("Elapsed: N/A")
        self.eta_label = QLabel("Time Remaining: N/A")
        self.grid_layout.addWidget(self.elapsed_label, 0, 0)
        self.grid_layout.addWidget(self.eta_label, 0, 1)
        self.layout.addLayout(self.grid_layout)

        # Status Log
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
        style = self.style()
        icon = style.standardIcon(style.StandardPixmap.SP_ComputerIcon)
        self.tray_icon.setIcon(icon)
        self.tray_icon.setToolTip("Sensitivity analysis is running...")

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

    def process_queue(self):
        while not self.queue.empty():
            try:
                msg = self.queue.get_nowait()
                msg_type = msg.get("type")

                if msg_type == "status":
                    self.update_status(msg["message"])
                elif msg_type == "progress":
                    # This now controls the stage progress bar
                    self.update_stage_progress(msg["current"], msg["total"])
                elif msg_type == "timing":
                    self.update_timing(msg["elapsed"], msg["eta"])
                elif msg_type == "finished":
                    self.study_finished()
                elif msg_type == "plot":
                    # Import locally to avoid circular dependency issues at startup
                    from analysis.sensitivity_analysis.run_sensitivity_analysis import (
                        plot_results,
                    )

                    plot_results(msg["df"], msg["freq"], msg["config"])

            except Empty:
                break

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
        """Stops the analysis by terminating the worker process."""
        self.update_status("--- Stop requested by user ---")
        self.stop_button.setEnabled(False)
        if self.process.is_alive():
            self.process.terminate()
            self.process.join(timeout=3)
        self.study_finished()

    def update_status(self, message):
        """Appends a message to the status log."""
        self.status_text.append(message)

    def update_timing(self, elapsed, eta):
        """Updates the timing labels."""
        from goliat.utils import format_time

        if eta is not None:
            self.eta_label.setText(f"Time Remaining: {format_time(eta)}")
        else:
            self.eta_label.setText("Time Remaining: N/A")

    def update_clock(self):
        """Updates the elapsed time label every second."""
        from goliat.utils import format_time

        elapsed_sec = time.monotonic() - self.start_time
        self.elapsed_label.setText(f"Elapsed: {format_time(elapsed_sec)}")

    def update_stage_progress(self, current_step, total_steps):
        """Updates the progress for the current run (stage)."""
        if total_steps > 0:
            self.stage_progress_bar.setRange(0, total_steps)
            self.stage_progress_bar.setValue(current_step)
            self.stage_label.setText(f"Current Run: {current_step+1} of {total_steps}")

            # Update overall progress based on stage
            overall_percent = ((current_step) / total_steps) * 100
            self.overall_progress_bar.setValue(int(overall_percent * 10))
            self.overall_progress_bar.setFormat(f"{overall_percent:.1f}%")

    def study_finished(self):
        """Handles the completion of the study."""
        self.update_status("--- Analysis complete or stopped ---")
        self.overall_progress_bar.setValue(self.overall_progress_bar.maximum())
        self.stage_label.setText("Finished")
        self.clock_timer.stop()
        self.stop_button.setEnabled(False)
        self.tray_button.setEnabled(False)
        QTimer.singleShot(3000, self.close)

    def closeEvent(self, event):
        """Handle the window close event."""
        if self.process.is_alive():
            self.stop_study()
        if self.tray_icon.isVisible():
            self.tray_icon.hide()
        event.accept()
