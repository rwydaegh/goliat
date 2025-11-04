import logging

from PySide6.QtCore import Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QMenu,
    QPushButton,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

# --- 1. Set up Logging ---
logger = logging.getLogger(__name__)


class BatchGUI(QWidget):
    """A simple GUI for the oSPARC batch run."""

    print_progress_requested = Signal()
    stop_run_requested = Signal()
    cancel_jobs_requested = Signal()

    def __init__(self):
        super().__init__()
        self.init_ui()

        logger.info("Initializing BatchGUI UI.")

    def init_ui(self):
        """Initializes the user interface components."""
        self.setWindowTitle("oSPARC Batch Runner")
        layout = QVBoxLayout()

        self.button_layout = QHBoxLayout()
        self.progress_button = QPushButton("Print Progress")
        self.progress_button.clicked.connect(self.print_progress_requested.emit)

        self.force_stop_button = QPushButton("Force Stop")
        self.force_stop_button.clicked.connect(self.force_stop_run)

        self.stop_and_cancel_button = QPushButton("Stop and Cancel Jobs")
        self.stop_and_cancel_button.clicked.connect(self.stop_and_cancel_jobs)

        self.tray_button = QPushButton("Move to Tray")
        self.tray_button.clicked.connect(self.hide_to_tray)

        self.button_layout.addWidget(self.progress_button)
        self.button_layout.addWidget(self.force_stop_button)
        self.button_layout.addWidget(self.stop_and_cancel_button)
        self.button_layout.addWidget(self.tray_button)
        layout.addLayout(self.button_layout)

        self.setLayout(layout)

        self.tray_icon = QSystemTrayIcon(self)
        style = self.style()
        icon = style.standardIcon(style.StandardPixmap.SP_ComputerIcon)
        self.tray_icon.setIcon(icon)
        self.tray_icon.setToolTip("oSPARC batch run is in progress...")

        tray_menu = QMenu(self)
        show_action = QAction("Show", self)
        show_action.triggered.connect(self.show_from_tray)
        tray_menu.addAction(show_action)

        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        tray_menu.addAction(exit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.tray_icon_activated)

    def force_stop_run(self):
        """Stops the main batch process immediately."""
        logger.info("Force stop button clicked.")
        self.force_stop_button.setEnabled(False)
        self.stop_and_cancel_button.setEnabled(False)
        self.stop_run_requested.emit()
        QApplication.instance().quit()  # type: ignore

    def stop_and_cancel_jobs(self):
        """Stops the main batch process and cancels all running jobs."""
        logger.info("Stop and cancel jobs button clicked.")
        self.force_stop_button.setEnabled(False)
        self.stop_and_cancel_button.setEnabled(False)
        self.cancel_jobs_requested.emit()
        # The worker will handle the rest, including quitting the app

    def hide_to_tray(self):
        """Hides the main window and shows the tray icon."""
        logger.info("Hiding window to system tray.")
        self.hide()
        self.tray_icon.show()

    def show_from_tray(self):
        """Shows the main window and hides the tray icon."""
        logger.info("Showing window from system tray.")
        self.show()
        self.tray_icon.hide()

    def tray_icon_activated(self, reason):
        """Handles tray icon activation."""
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            logger.debug("Tray icon clicked, showing window.")
            self.show_from_tray()

    def closeEvent(self, event):
        """Handles the window close event."""
        logger.info("Window close event triggered.")
        self.force_stop_run()
        event.accept()
