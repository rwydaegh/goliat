"""Tray icon management component."""

import os
from typing import Callable

from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon, QWidget


class TrayManager:
    """Manages system tray icon and menu.

    Handles system tray integration for background operation. Shows tray icon
    with favicon, provides context menu (Show/Exit), and handles click events
    to restore window. Allows users to minimize GUI to tray and continue
    monitoring via icon.
    """

    def __init__(self, parent_widget: QWidget, show_callback: Callable[[], None], close_callback: Callable[[], None]) -> None:
        """Sets up tray icon with menu.

        Args:
            parent_widget: Parent widget (ProgressGUI window).
            show_callback: Function to call when restoring window.
            close_callback: Function to call when exiting application.
        """
        self.parent: QWidget = parent_widget
        self.tray_icon: QSystemTrayIcon = QSystemTrayIcon(parent_widget)

        # Set icon
        icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "docs", "img", "favicon.svg")
        if os.path.exists(icon_path):
            self.tray_icon.setIcon(QIcon(icon_path))
        else:
            style = parent_widget.style()
            icon = style.standardIcon(style.StandardPixmap.SP_ComputerIcon)
            self.tray_icon.setIcon(icon)
        self.tray_icon.setToolTip("Simulation is running...")

        # Create menu
        tray_menu = QMenu(parent_widget)
        show_action = QAction("Show", parent_widget)
        show_action.triggered.connect(show_callback)
        tray_menu.addAction(show_action)

        exit_action = QAction("Exit", parent_widget)
        exit_action.triggered.connect(close_callback)
        tray_menu.addAction(exit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(lambda reason: self._tray_icon_activated(reason, show_callback))

    def show(self) -> None:
        """Shows the tray icon."""
        self.tray_icon.show()

    def hide(self) -> None:
        """Hides the tray icon."""
        self.tray_icon.hide()

    def is_visible(self) -> bool:
        """Checks if tray icon is visible.

        Returns:
            True if visible, False otherwise.
        """
        return self.tray_icon.isVisible()

    def _tray_icon_activated(self, reason: QSystemTrayIcon.ActivationReason, show_callback: Callable[[], None]) -> None:
        """Handles tray icon activation.

        Args:
            reason: Activation reason.
            show_callback: Callback to show window.
        """
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            show_callback()
