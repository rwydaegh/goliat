"""Overall progress plot component for GUI."""

from datetime import datetime, timezone, timedelta
from typing import List, Tuple

from ._matplotlib_imports import Figure, FigureCanvas, mdates  # type: ignore
from .utils import convert_to_utc_plus_one, validate_timestamp, clean_plot_data


class OverallProgressPlot:
    """Manages overall progress plot with real-time updates.

    Creates a matplotlib line plot showing progress percentage trends over time.
    Updates dynamically as new data points arrive. Uses green color scheme
    to distinguish from time remaining plot. Y-axis fixed at 0-100%.
    """

    def __init__(self) -> None:
        """Sets up matplotlib figure and axes with dark theme."""
        if Figure is None or FigureCanvas is None:
            raise ImportError("matplotlib is required for plotting")
        from matplotlib.figure import Figure as _Figure
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as _FigureCanvas
        from matplotlib.axes import Axes as _Axes

        self.figure: _Figure = _Figure(figsize=(10, 6), facecolor="#2b2b2b")
        self.canvas: _FigureCanvas = _FigureCanvas(self.figure)
        self.ax: _Axes = self.figure.add_subplot(111)
        self.data: List[Tuple[datetime, float]] = []
        self.max_progress_seen: float = 0.0
        self._setup()

    def _setup(self) -> None:
        """Initializes plot with dark theme styling."""
        self.ax.clear()
        self.ax.set_facecolor("#2b2b2b")
        self.figure.patch.set_facecolor("#2b2b2b")

        self.ax.set_xlabel("Time (UTC+1)", fontsize=12, color="#f0f0f0")
        self.ax.set_ylabel("Progress (%)", fontsize=12, color="#f0f0f0")
        self.ax.set_title("Overall Progress", fontsize=14, color="#f0f0f0", pad=20)

        self.ax.tick_params(colors="#f0f0f0", which="both")
        self.ax.spines["bottom"].set_color("#f0f0f0")
        self.ax.spines["left"].set_color("#f0f0f0")
        self.ax.spines["top"].set_color("#2b2b2b")
        self.ax.spines["right"].set_color("#2b2b2b")

        self.ax.grid(True, alpha=0.2, color="#f0f0f0")
        self.ax.set_ylim(0, 100)

        self.ax.plot([], [], "-", color="#28a745", linewidth=2.5, label="Overall Progress")
        self.ax.legend(loc="lower right", facecolor="#3c3c3c", edgecolor="#f0f0f0", labelcolor="#f0f0f0", fontsize=10)

        self.canvas.draw()

    def add_data_point(self, timestamp: datetime, progress_percent: float) -> None:
        """Adds data point and refreshes plot.

        Args:
            timestamp: Timestamp for the data point.
            progress_percent: Progress percentage as float.
        """
        if progress_percent > self.max_progress_seen:
            self.max_progress_seen = progress_percent
        # Convert timestamp to UTC+1
        utc_plus_one_timestamp = convert_to_utc_plus_one(timestamp)

        # Validate timestamp: reject if it's anomalously far from the last timestamp
        # This prevents spikes from corrupted timestamps (e.g., from NTP cache issues)
        if self.data and not validate_timestamp(utc_plus_one_timestamp, self.data[-1][0]):
            # Skip this data point - timestamp is anomalous
            return

        self.data.append((utc_plus_one_timestamp, progress_percent))
        self._refresh()

    def _refresh(self) -> None:
        """Refreshes plot with current data."""
        if not self.data:
            return

        self.ax.clear()

        # Clean data: sort, deduplicate, and filter anomalies
        cleaned_data = clean_plot_data(self.data)
        times = [t for t, _ in cleaned_data]
        progress = [p for _, p in cleaned_data]

        self.ax.plot(times, progress, "-", color="#28a745", linewidth=2.5, label="Overall Progress")  # type: ignore[arg-type]

        self.ax.set_facecolor("#2b2b2b")
        self.ax.set_xlabel("Time (UTC+1)", fontsize=12, color="#f0f0f0")
        self.ax.set_ylabel("Progress (%)", fontsize=12, color="#f0f0f0")
        self.ax.set_title("Overall Progress", fontsize=14, color="#f0f0f0", pad=20)

        self.ax.set_ylim(0, 100)

        if mdates is not None:
            utc_plus_one_tz = timezone(timedelta(hours=1))
            self.ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S", tz=utc_plus_one_tz))
        self.figure.autofmt_xdate(rotation=45)

        self.ax.grid(True, alpha=0.2, color="#f0f0f0")
        self.ax.tick_params(colors="#f0f0f0", which="both")
        self.ax.spines["bottom"].set_color("#f0f0f0")
        self.ax.spines["left"].set_color("#f0f0f0")
        self.ax.spines["top"].set_color("#2b2b2b")
        self.ax.spines["right"].set_color("#2b2b2b")

        self.ax.legend(loc="lower right", facecolor="#3c3c3c", edgecolor="#f0f0f0", labelcolor="#f0f0f0", fontsize=10)

        self.figure.tight_layout()
        self.canvas.draw()
