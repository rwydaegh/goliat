"""Matplotlib imports with fallback handling for plotting components."""

from typing import TYPE_CHECKING

import matplotlib
import os
import sys

# Check for headless environment (CI or Linux without DISPLAY)
# On Windows, DISPLAY is not used, so we assume GUI is available unless CI is set
is_headless = os.environ.get("CI") or (sys.platform != "win32" and not os.environ.get("DISPLAY"))

if is_headless:
    matplotlib.use("Agg")
else:
    try:
        matplotlib.use("Qt5Agg")
    except Exception:
        # Fallback to Agg if Qt5Agg fails
        try:
            matplotlib.use("Agg")
        except Exception:
            pass

Figure = None
FigureCanvas = None
Axes = None
mdates = None

try:
    import matplotlib.dates as mdates
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    from matplotlib.axes import Axes
except ImportError:
    pass

if TYPE_CHECKING:
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas

__all__ = ["Figure", "FigureCanvas", "Axes", "mdates"]
