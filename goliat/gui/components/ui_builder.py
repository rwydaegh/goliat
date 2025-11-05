"""UI builder component for constructing the ProgressGUI interface."""

import os
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QVBoxLayout,
    QWidget,
    QTextEdit,
)

from goliat.gui.components.plots import TimeRemainingPlot, OverallProgressPlot, PieChartsManager
from goliat.gui.components.timings_table import TimingsTable

if TYPE_CHECKING:
    from goliat.gui.progress_gui import ProgressGUI
    from goliat.gui.components.status_manager import StatusManager


class UIBuilder:
    """Builds UI components for ProgressGUI.

    Provides static methods to construct the complete GUI layout, including
    tabs, progress bars, plots, tables, and buttons. Handles styling via
    Qt stylesheets for dark theme appearance.
    """

    STYLESHEET: str = """
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
            background-color: #2b2b2b;
            color: #f0f0f0;
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
        QScrollBar:vertical {
            border: 1px solid #444;
            background: #2b2b2b;
            width: 15px;
            margin: 0px;
        }
        QScrollBar::handle:vertical {
            background: #5a5a5a;
            min-height: 20px;
            border-radius: 7px;
        }
        QScrollBar::handle:vertical:hover {
            background: #6a6a6a;
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            background: #2b2b2b;
            height: 0px;
        }
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
            background: none;
        }
        QScrollBar:horizontal {
            border: 1px solid #444;
            background: #2b2b2b;
            height: 15px;
            margin: 0px;
        }
        QScrollBar::handle:horizontal {
            background: #5a5a5a;
            min-width: 20px;
            border-radius: 7px;
        }
        QScrollBar::handle:horizontal:hover {
            background: #6a6a6a;
        }
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
            background: #2b2b2b;
            width: 0px;
        }
        QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
            background: none;
        }
        QTableWidget {
            gridline-color: #444;
            background-color: #2b2b2b;
            color: #f0f0f0;
        }
        QTableWidget::item {
            background-color: #2b2b2b;
            color: #f0f0f0;
        }
        QTableWidget::item:selected {
            background-color: #3c3c3c;
            color: #f0f0f0;
        }
        QHeaderView::section {
            background-color: #3c3c3c;
            color: #f0f0f0;
            padding: 4px;
            border: 1px solid #444;
        }
        QHeaderView::section:vertical {
            background-color: #3c3c3c;
            color: #f0f0f0;
        }
        QTableCornerButton::section {
            background-color: #3c3c3c;
            border: 1px solid #444;
        }
    """

    @staticmethod
    def get_icon_path() -> str:
        """Gets path to window icon.

        Returns:
            Absolute path to favicon.svg.
        """
        return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "docs", "img", "favicon.svg")

    @staticmethod
    def build(gui_instance: "ProgressGUI", status_manager: "StatusManager") -> None:
        """Builds complete UI for the GUI instance.

        Sets up window properties, applies stylesheet, creates tabs (Progress,
        Timings, Piecharts, Time Remaining, Overall Progress), and adds
        control buttons. Attaches components to gui_instance for later access.

        Args:
            gui_instance: ProgressGUI instance to build UI for.
            status_manager: StatusManager instance for error summary display.
        """
        gui_instance.setWindowTitle(gui_instance.init_window_title)
        gui_instance.resize(800, 900)

        # Set window icon
        icon_path = UIBuilder.get_icon_path()
        if os.path.exists(icon_path):
            gui_instance.setWindowIcon(QIcon(icon_path))

        gui_instance.setStyleSheet(UIBuilder.STYLESHEET)

        main_layout = QVBoxLayout(gui_instance)
        gui_instance.tabs = QTabWidget()
        main_layout.addWidget(gui_instance.tabs)

        # Build tabs
        UIBuilder._build_progress_tab(gui_instance, status_manager)
        UIBuilder._build_timings_tab(gui_instance)
        UIBuilder._build_piecharts_tab(gui_instance)
        UIBuilder._build_time_remaining_tab(gui_instance)
        UIBuilder._build_overall_progress_tab(gui_instance)

        # Build buttons
        UIBuilder._build_buttons(gui_instance, main_layout)

    @staticmethod
    def _build_progress_tab(gui_instance: "ProgressGUI", status_manager: "StatusManager") -> None:
        """Builds the Progress tab with progress bars and status log."""
        progress_widget = QWidget()
        progress_layout = QVBoxLayout(progress_widget)
        gui_instance.tabs.addTab(progress_widget, "Progress")

        # Info Grid with utilization bars on the right
        info_grid = QGridLayout()
        info_grid.setVerticalSpacing(2)  # Reduce vertical spacing between rows

        # Left side: Simulation info
        gui_instance.sim_counter_label = QLabel("Simulation: N/A")
        gui_instance.sim_details_label = QLabel("Current Case: N/A")
        info_grid.addWidget(gui_instance.sim_counter_label, 0, 0)
        info_grid.addWidget(gui_instance.sim_details_label, 1, 0)

        # Right side: System Utilization Widgets (CPU, RAM, GPU) and Error counter
        utilization_layout = QHBoxLayout()
        utilization_layout.setSpacing(8)

        # CPU Utilization
        cpu_container = QWidget()
        cpu_container_layout = QVBoxLayout(cpu_container)
        cpu_container_layout.setContentsMargins(0, 0, 0, 0)
        cpu_container_layout.setSpacing(2)
        gui_instance.cpu_label = QLabel("CPU:")
        gui_instance.cpu_label.setStyleSheet("font-size: 11px;")
        cpu_container_layout.addWidget(gui_instance.cpu_label)
        gui_instance.cpu_bar = QProgressBar(gui_instance)
        gui_instance.cpu_bar.setRange(0, 100)
        gui_instance.cpu_bar.setMaximumHeight(16)
        gui_instance.cpu_bar.setMaximumWidth(80)
        gui_instance.cpu_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #444;
                border-radius: 2px;
                text-align: center;
                font-size: 9px;
                height: 16px;
                background-color: #2b2b2b;
                color: #f0f0f0;
            }
            QProgressBar::chunk {
                background-color: #007acc;
                border-radius: 1px;
            }
        """)
        cpu_container_layout.addWidget(gui_instance.cpu_bar)
        utilization_layout.addWidget(cpu_container)

        # RAM Utilization
        ram_container = QWidget()
        ram_container_layout = QVBoxLayout(ram_container)
        ram_container_layout.setContentsMargins(0, 0, 0, 0)
        ram_container_layout.setSpacing(2)
        gui_instance.ram_label = QLabel("RAM:")
        gui_instance.ram_label.setStyleSheet("font-size: 11px;")
        ram_container_layout.addWidget(gui_instance.ram_label)
        gui_instance.ram_bar = QProgressBar(gui_instance)
        gui_instance.ram_bar.setRange(0, 100)
        gui_instance.ram_bar.setMaximumHeight(16)
        gui_instance.ram_bar.setMaximumWidth(80)
        gui_instance.ram_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #444;
                border-radius: 2px;
                text-align: center;
                font-size: 9px;
                height: 16px;
                background-color: #2b2b2b;
                color: #f0f0f0;
            }
            QProgressBar::chunk {
                background-color: #007acc;
                border-radius: 1px;
            }
        """)
        ram_container_layout.addWidget(gui_instance.ram_bar)
        utilization_layout.addWidget(ram_container)

        # GPU Utilization
        gpu_container = QWidget()
        gpu_container_layout = QVBoxLayout(gpu_container)
        gpu_container_layout.setContentsMargins(0, 0, 0, 0)
        gpu_container_layout.setSpacing(2)
        gui_instance.gpu_label = QLabel("GPU:")
        gui_instance.gpu_label.setStyleSheet("font-size: 11px;")
        gpu_container_layout.addWidget(gui_instance.gpu_label)
        gui_instance.gpu_bar = QProgressBar(gui_instance)
        gui_instance.gpu_bar.setRange(0, 100)
        gui_instance.gpu_bar.setMaximumHeight(16)
        gui_instance.gpu_bar.setMaximumWidth(80)
        gui_instance.gpu_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #444;
                border-radius: 2px;
                text-align: center;
                font-size: 9px;
                height: 16px;
                background-color: #2b2b2b;
                color: #f0f0f0;
            }
            QProgressBar::chunk {
                background-color: #007acc;
                border-radius: 1px;
            }
        """)
        gpu_container_layout.addWidget(gui_instance.gpu_bar)
        utilization_layout.addWidget(gpu_container)

        # Utilization widget container
        utilization_widget = QWidget()
        utilization_widget.setLayout(utilization_layout)

        # Error counter label (includes web status)
        gui_instance.error_counter_label = QLabel(status_manager.get_error_summary())

        # Right side layout: utilization bars above error counter
        right_side_layout = QVBoxLayout()
        right_side_layout.setContentsMargins(0, 0, 0, 0)
        right_side_layout.setSpacing(4)
        right_side_layout.addWidget(utilization_widget)
        right_side_layout.addWidget(gui_instance.error_counter_label)

        right_side_widget = QWidget()
        right_side_widget.setLayout(right_side_layout)

        # Add right side widget to grid
        info_grid.addWidget(right_side_widget, 0, 1, 2, 1, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)

        progress_layout.addLayout(info_grid)

        gui_instance.overall_progress_label = QLabel("Overall Progress:")
        progress_layout.addWidget(gui_instance.overall_progress_label)
        gui_instance.overall_progress_bar = QProgressBar(gui_instance)
        gui_instance.overall_progress_bar.setRange(0, 10000)
        progress_layout.addWidget(gui_instance.overall_progress_bar)

        gui_instance.stage_label = QLabel("Current Stage:")
        progress_layout.addWidget(gui_instance.stage_label)
        gui_instance.stage_progress_bar = QProgressBar(gui_instance)
        gui_instance.stage_progress_bar.setRange(0, 1000)
        progress_layout.addWidget(gui_instance.stage_progress_bar)

        time_layout = QHBoxLayout()
        gui_instance.elapsed_label = QLabel("Elapsed: N/A")
        gui_instance.eta_label = QLabel("Time Remaining: N/A")
        time_layout.addWidget(gui_instance.elapsed_label)
        time_layout.addStretch()
        time_layout.addWidget(gui_instance.eta_label)
        progress_layout.addLayout(time_layout)

        gui_instance.status_log_label = QLabel("High-level progress log:")
        progress_layout.addWidget(gui_instance.status_log_label)
        gui_instance.status_text = QTextEdit(gui_instance)
        gui_instance.status_text.setReadOnly(True)
        progress_layout.addWidget(gui_instance.status_text)

    @staticmethod
    def _build_timings_tab(gui_instance: "ProgressGUI") -> None:
        """Builds the Timings tab with statistics table."""
        timings_widget = QWidget()
        timings_layout = QVBoxLayout(timings_widget)
        gui_instance.tabs.addTab(timings_widget, "Timings")
        timings_table_widget = QTableWidget()
        gui_instance.timings_table = TimingsTable(timings_table_widget)
        timings_layout.addWidget(timings_table_widget)

    @staticmethod
    def _build_piecharts_tab(gui_instance: "ProgressGUI") -> None:
        """Builds the Timings Piecharts tab."""
        piecharts_widget = QWidget()
        piecharts_layout = QVBoxLayout(piecharts_widget)
        gui_instance.tabs.addTab(piecharts_widget, "Timings Piecharts")
        gui_instance.piecharts_manager = PieChartsManager()
        piecharts_layout.addWidget(gui_instance.piecharts_manager.canvas)

    @staticmethod
    def _build_time_remaining_tab(gui_instance: "ProgressGUI") -> None:
        """Builds the Time Remaining tab."""
        time_remaining_widget = QWidget()
        time_remaining_layout = QVBoxLayout(time_remaining_widget)
        gui_instance.tabs.addTab(time_remaining_widget, "Time Remaining")
        gui_instance.time_remaining_plot = TimeRemainingPlot()
        time_remaining_layout.addWidget(gui_instance.time_remaining_plot.canvas)

    @staticmethod
    def _build_overall_progress_tab(gui_instance: "ProgressGUI") -> None:
        """Builds the Overall Progress tab."""
        overall_progress_widget = QWidget()
        overall_progress_layout = QVBoxLayout(overall_progress_widget)
        gui_instance.tabs.addTab(overall_progress_widget, "Overall Progress")
        gui_instance.overall_progress_plot = OverallProgressPlot()
        overall_progress_layout.addWidget(gui_instance.overall_progress_plot.canvas)

    @staticmethod
    def _build_buttons(gui_instance: "ProgressGUI", main_layout: QVBoxLayout) -> None:
        """Builds control buttons (Stop, Run in Background)."""
        gui_instance.button_layout = QHBoxLayout()
        gui_instance.stop_button = QPushButton("Stop")
        gui_instance.stop_button.clicked.connect(gui_instance.stop_study)
        gui_instance.tray_button = QPushButton("Run in Background")
        gui_instance.tray_button.clicked.connect(gui_instance.hide_to_tray)
        gui_instance.button_layout.addWidget(gui_instance.stop_button)
        gui_instance.button_layout.addWidget(gui_instance.tray_button)
        main_layout.addLayout(gui_instance.button_layout)
