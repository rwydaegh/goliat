"""Simple GUI for Analysis Progress."""

import logging
import time
from typing import Callable

from PySide6.QtCore import QThread, Signal, Slot, QObject, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QTextEdit,
    QHBoxLayout,
)

from goliat.gui.components.ui_builder import UIBuilder


class SignalingLogHandler(logging.Handler, QObject):
    """Log handler that emits Qt signals for log records."""

    # Define signal on the class (must inherit QObject)
    # message, levelname, log_type
    log_signal = Signal(str, str, str)

    def __init__(self):
        logging.Handler.__init__(self)
        QObject.__init__(self)

    def emit(self, record):
        try:
            msg = self.format(record)
            # Extract log_type for coloring (defaults to 'default')
            log_type = getattr(record, "log_type", "default")
            self.log_signal.emit(msg, record.levelname, log_type)
        except Exception:
            self.handleError(record)


class AnalysisWorker(QThread):
    """Worker thread for running analysis in background."""

    finished_signal = Signal()
    error_signal = Signal(str)

    def __init__(self, target: Callable):
        super().__init__()
        self.target = target

    def run(self):
        try:
            self.target()
        except Exception as e:
            import traceback

            traceback.print_exc()
            self.error_signal.emit(str(e))
        finally:
            self.finished_signal.emit()


class AnalysisGUI(QWidget):
    """Simple GUI to show analysis progress."""

    # Redefined stylesheet to target AnalysisGUI specifically
    STYLESHEET = """
        AnalysisGUI {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                       stop:0 #2b2b2b, stop:1 #b87d16);
        }
        QWidget {
            color: #f0f0f0;
            font-family: 'Segoe UI', Arial, sans-serif;
        }
        QLabel {
            font-size: 14px;
        }
    """

    # Map log_types (from goliat.colors) to Hex colors for GUI
    COLOR_MAP = {
        "default": "#e0e0e0",  # White/Light Gray
        "progress": "#44ff44",  # Green
        "info": "#00ccff",  # Cyan
        "verbose": "#8888ff",  # Blue
        "warning": "#ffcc00",  # Yellow/Orange
        "error": "#ff4444",  # Red
        "fatal": "#ff00ff",  # Magenta
        "success": "#44ff44",  # Bright Green
        "header": "#ff00ff",  # Magenta
        "highlight": "#ffff00",  # Bright Yellow
        "caller": "#888888",  # Gray
    }

    def __init__(self, phantom_name: str, total_items: int):
        super().__init__()
        self.phantom_name = phantom_name
        # Use the provided total_items directly (caller provides accurate estimate)
        self.total_estimated_items = total_items
        self.current_item = 0

        # Helper state for timer
        self.start_time = None
        self.elapsed_timer = QTimer(self)
        self.elapsed_timer.timeout.connect(self.update_timer)

        # Setup UI
        self.setWindowTitle(f"GOLIAT Analysis - {phantom_name}")
        self.resize(800, 700)
        self.setStyleSheet(self.STYLESHEET)

        # Set icon
        icon_path = UIBuilder.get_icon_path()
        if icon_path:
            self.setWindowIcon(QIcon(icon_path))

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)

        # Header Row
        header_layout = QHBoxLayout()

        self.header_label = QLabel(f"Analyzing Phantom: {phantom_name}")
        self.header_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #f0f0f0; background: transparent;")
        header_layout.addWidget(self.header_label)

        header_layout.addStretch()

        # Timer Label
        self.timer_label = QLabel("00:00:00")
        self.timer_label.setStyleSheet("font-size: 16px; font-family: monospace; color: #aaaaaa; background: transparent;")
        header_layout.addWidget(self.timer_label)

        layout.addLayout(header_layout)

        # Progress Section
        progress_layout = QVBoxLayout()
        progress_layout.setSpacing(5)

        self.status_label = QLabel("Initializing...")
        self.status_label.setStyleSheet("color: #cccccc; background: transparent;")
        progress_layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, self.total_estimated_items)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        # Using %v (value) and %m (total)
        self.progress_bar.setFormat("%p% (%v items processed)")
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #444;
                border-radius: 4px;
                text-align: center;
                font-size: 14px;
                height: 24px;
                background-color: #2b2b2b;
                color: #ffffff;
            }
            QProgressBar::chunk {
                background-color: #007acc;
                border-radius: 3px;
            }
        """)
        progress_layout.addWidget(self.progress_bar)
        layout.addLayout(progress_layout)

        # Log Section
        layout.addWidget(QLabel("Analysis Log:"))
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #222;
                border: 1px solid #444;
                border-radius: 4px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 12px;
                color: #e0e0e0;
            }
        """)
        layout.addWidget(self.log_text)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        # Tray Button
        self.tray_button = QPushButton("Minimize to Tray")
        self.tray_button.clicked.connect(self.hide_to_tray)
        self.tray_button.setStyleSheet("""
            QPushButton {
                background-color: #555;
                border: 1px solid #666;
                padding: 8px 16px;
                border-radius: 4px;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #666; }
        """)
        button_layout.addWidget(self.tray_button)

        # Close Button
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.close)
        self.close_button.setEnabled(False)  # Disabled until finished
        self.close_button.setStyleSheet("""
            QPushButton {
                background-color: #555;
                border: 1px solid #666;
                padding: 8px 16px;
                border-radius: 4px;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #666; }
            QPushButton:disabled { background-color: #333; color: #777; }
        """)
        button_layout.addWidget(self.close_button)
        layout.addLayout(button_layout)

        # Tray Manager
        from goliat.gui.components.tray_manager import TrayManager

        self.tray_manager = TrayManager(self, self.show_from_tray, self.close)

        # Log Handler
        self.log_handler = SignalingLogHandler()
        self.log_handler.log_signal.connect(self.append_log)

        # Attach handler to 'progress' logger
        self.progress_logger = logging.getLogger("progress")
        self.progress_logger.addHandler(self.log_handler)
        self.progress_logger.setLevel(logging.INFO)

    @Slot()
    def update_timer(self):
        if self.start_time:
            elapsed = time.time() - self.start_time
            # Format elapsed as HH:MM:SS
            e_hours, e_remainder = divmod(int(elapsed), 3600)
            e_minutes, e_seconds = divmod(e_remainder, 60)
            elapsed_str = f"{e_hours:02d}:{e_minutes:02d}:{e_seconds:02d}"

            # Calculate remaining time (simple linear estimate)
            current = self.progress_bar.value()
            maximum = self.progress_bar.maximum()
            if current > 0 and maximum > 0:
                remaining_secs = elapsed * (maximum - current) / current
                r_hours, r_remainder = divmod(int(remaining_secs), 3600)
                r_minutes, r_seconds = divmod(r_remainder, 60)
                remaining_str = f"{r_hours:02d}:{r_minutes:02d}:{r_seconds:02d}"
            else:
                remaining_str = "--:--:--"

            self.timer_label.setText(f"Elapsed: {elapsed_str}  |  Remaining: {remaining_str}")

    @Slot(str, str, str)
    def append_log(self, message: str, level: str, log_type: str):
        # Determine color based on log_type preference, falling back to simple level mapping
        color = self.COLOR_MAP.get(log_type)

        if not color:
            # Fallback if log_type doesn't match/is missing
            if level == "WARNING":
                color = self.COLOR_MAP["warning"]
            elif level == "ERROR" or level == "CRITICAL":
                color = self.COLOR_MAP["error"]
            elif "success" in message.lower() or "finished" in message.lower():
                color = self.COLOR_MAP["success"]
            else:
                color = self.COLOR_MAP["default"]

        # Strip ANSI codes if any slipped through
        import re

        ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        clean_msg = ansi_escape.sub("", message)

        if not color or color == self.COLOR_MAP["default"]:
            # Logic fallback based on content if log_type was missing or default
            if "Processing:" in clean_msg:
                color = self.COLOR_MAP["progress"]
            elif "Generating" in clean_msg or "Plotting:" in clean_msg:
                color = self.COLOR_MAP["info"]
            elif "WARNING" in clean_msg or "Warning" in clean_msg:
                color = self.COLOR_MAP["warning"]
            elif "ERROR" in clean_msg or "Error" in clean_msg:
                color = self.COLOR_MAP["error"]

        # Update Phantom Name Header if detected (but don't reset progress)
        if "Starting Results Analysis for Phantom:" in clean_msg:
            try:
                # Extract phantom name: "--- Starting Results Analysis for Phantom: Thelonious ---"
                phantom_name = clean_msg.split("Phantom:")[-1].replace("-", "").strip()
                self.header_label.setText(f"Analyzing Phantom: {phantom_name}")
                self.setWindowTitle(f"GOLIAT Analysis - {phantom_name}")
            except Exception:
                pass

        # Format HTML
        formatted_msg = f'<span style="color:{color}">{clean_msg}</span>'
        self.log_text.append(formatted_msg)

        # Parse message to update progress
        # 1. Processing results phase
        if "Processing:" in clean_msg:
            self._increment_progress(f"Processing: {clean_msg.split('Processing:')[-1].strip()}")

        # 2. Plotting phase (approximate tracking)
        elif "Generating" in clean_msg and ("plot" in clean_msg or "heatmap" in clean_msg):
            # Just strip decorative chars, keep text as-is
            raw_text = clean_msg.replace("Generating", "").strip()
            # Strip common decorators: "---", "- ", "..."
            raw_text = raw_text.replace("---", "").replace("- ", "").replace("...", "").strip()
            self._increment_progress(f"Plotting: {raw_text}")

        # 3. Generated file (plotting completion step)
        elif "Generated" in clean_msg:
            self._increment_progress("Plot generated")

        elif "Analysis Finished" in clean_msg:
            # Just update status - don't stop timer or change colors here
            # This fires per-phantom, final completion is handled in on_finished()
            self.status_label.setText("Analysis Finished!")

    def _increment_progress(self, status_text: str):
        self.current_item += 1
        # Prevent jump-back by extending maximum if we go over, instead of rescaling
        if self.current_item > self.progress_bar.maximum():
            self.progress_bar.setMaximum(self.current_item)

        self.progress_bar.setValue(self.current_item)
        if status_text != "Plot generated":
            self.status_label.setText(status_text)

    def start_analysis(self, target: Callable):
        self.start_time = time.time()
        self.elapsed_timer.start(1000)  # Update every second

        self.worker = AnalysisWorker(target)
        self.worker.finished_signal.connect(self.on_finished)
        self.worker.error_signal.connect(self.on_error)
        self.worker.start()

    @Slot()
    def on_finished(self):
        self.status_label.setText("All analysis complete. You may close this window.")
        # Set progress to max when truly finished
        self.progress_bar.setValue(self.progress_bar.maximum())
        self.close_button.setEnabled(True)
        self.elapsed_timer.stop()
        # Clean up handlers
        try:
            self.log_handler.close()
            self.progress_logger.removeHandler(self.log_handler)
        except Exception:
            pass

    @Slot(str)
    def on_error(self, error_msg: str):
        self.append_log(f"CRITICAL ERROR: {error_msg}", "ERROR", "error")
        self.status_label.setText("Error occurred.")
        self.close_button.setEnabled(True)
        self.elapsed_timer.stop()

    def hide_to_tray(self):
        """Hides main window and shows system tray icon."""
        self.hide()
        self.tray_manager.show()

    def show_from_tray(self):
        """Shows main window from system tray."""
        self.show()
        self.tray_manager.hide()

    def closeEvent(self, event):
        """Handle window close event to ensure clean shutdown."""
        # Hide tray if visible
        if hasattr(self, "tray_manager") and self.tray_manager.is_visible():
            self.tray_manager.hide()

        if hasattr(self, "worker") and self.worker.isRunning():
            self.worker.terminate()
            self.worker.wait()

        # Ensure application quits fully
        QApplication.instance().quit()
        event.accept()
