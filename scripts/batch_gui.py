import sys
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QPushButton, QHBoxLayout,
                                 QSystemTrayIcon, QMenu, QTextEdit)
from PySide6.QtGui import QAction

class BatchGUI(QWidget):
    """A simple GUI for the oSPARC batch run."""
    print_progress_requested = Signal()
    stop_run_requested = Signal()

    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        """Initializes the user interface components."""
        self.setWindowTitle("oSPARC Batch Runner")
        self.layout = QVBoxLayout()

        self.button_layout = QHBoxLayout()
        self.progress_button = QPushButton("Print Progress")
        self.progress_button.clicked.connect(self.print_progress_requested.emit)
        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.stop_run)
        self.tray_button = QPushButton("Move to Tray")
        self.tray_button.clicked.connect(self.hide_to_tray)
        
        self.button_layout.addWidget(self.progress_button)
        self.button_layout.addWidget(self.stop_button)
        self.button_layout.addWidget(self.tray_button)
        self.layout.addLayout(self.button_layout)

        self.setLayout(self.layout)

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

    def stop_run(self):
        """Stops the main batch process."""
        self.stop_button.setEnabled(False)
        self.stop_run_requested.emit()

    def hide_to_tray(self):
        """Hide the main window and show the tray icon."""
        self.hide()
        self.tray_icon.show()

    def show_from_tray(self):
        """Show the main window and hide the tray icon."""
        self.show()
        self.tray_icon.hide()

    def tray_icon_activated(self, reason):
        """Handle tray icon activation."""
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show_from_tray()

    def closeEvent(self, event):
        """Handle the window close event."""
        self.stop_run_requested.emit()
        if self.tray_icon.isVisible():
            self.tray_icon.hide()
        QApplication.instance().quit()
        event.accept()