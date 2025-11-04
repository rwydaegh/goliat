"""GUI components for the ProgressGUI."""

from goliat.gui.components.data_manager import DataManager
from goliat.gui.components.status_manager import StatusManager
from goliat.gui.components.progress_animation import ProgressAnimation
from goliat.gui.components.plots import TimeRemainingPlot, OverallProgressPlot, PieChartsManager

__all__ = [
    "DataManager",
    "StatusManager",
    "ProgressAnimation",
    "TimeRemainingPlot",
    "OverallProgressPlot",
    "PieChartsManager",
]
