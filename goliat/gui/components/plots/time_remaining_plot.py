"""Time remaining plot component for GUI."""

from datetime import datetime, timedelta, timezone
from typing import List, Tuple

from goliat.constants import PLOT_Y_AXIS_BUFFER_MULTIPLIER
from ._matplotlib_imports import Figure, FigureCanvas, mdates  # type: ignore
from .utils import convert_to_utc_plus_one, validate_timestamp, clean_plot_data


class TimeRemainingPlot:
    """Manages time remaining plot with real-time updates.

    Creates a matplotlib line plot showing ETA trends over time. Updates
    dynamically as new data points arrive, maintaining dark theme styling
    consistent with GUI. Tracks maximum time seen to set appropriate Y-axis
    limits.
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
        self.max_time_remaining_seen: float = 0.0
        self._setup()

    def _setup(self) -> None:
        """Initializes plot with dark theme styling."""
        self.ax.clear()
        self.ax.set_facecolor("#2b2b2b")
        self.figure.patch.set_facecolor("#2b2b2b")

        self.ax.set_xlabel("Time (UTC+1)", fontsize=12, color="#f0f0f0")
        self.ax.set_ylabel("Hours Remaining", fontsize=12, color="#f0f0f0")
        self.ax.set_title("Estimated Time Remaining", fontsize=14, color="#f0f0f0", pad=20)

        self.ax.tick_params(colors="#f0f0f0", which="both")
        self.ax.spines["bottom"].set_color("#f0f0f0")
        self.ax.spines["left"].set_color("#f0f0f0")
        self.ax.spines["top"].set_color("#2b2b2b")
        self.ax.spines["right"].set_color("#2b2b2b")

        self.ax.grid(True, alpha=0.2, color="#f0f0f0")

        self.ax.plot([], [], "-", color="#007acc", linewidth=2.5, label="Time Remaining")
        self.ax.legend(loc="upper right", facecolor="#3c3c3c", edgecolor="#f0f0f0", labelcolor="#f0f0f0", fontsize=10)

        self.canvas.draw()

    def add_data_point(self, timestamp: datetime, hours_remaining: float) -> None:
        """Adds data point and refreshes plot.

        Args:
            timestamp: Timestamp for the data point.
            hours_remaining: Hours remaining as float.
        """
        if hours_remaining > self.max_time_remaining_seen:
            self.max_time_remaining_seen = hours_remaining
        # Convert timestamp to UTC+1
        utc_plus_one_timestamp = convert_to_utc_plus_one(timestamp)

        # Validate timestamp: reject if it's anomalously far from the last timestamp
        # This prevents spikes from corrupted timestamps (e.g., from NTP cache issues)
        if self.data and not validate_timestamp(utc_plus_one_timestamp, self.data[-1][0]):
            # Skip this data point - timestamp is anomalous
            return

        self.data.append((utc_plus_one_timestamp, hours_remaining))
        self._refresh()

    def _refresh(self) -> None:
        """Refreshes plot with current data."""
        if not self.data:
            return

        self.ax.clear()

        # Clean data: sort, deduplicate, and filter anomalies
        cleaned_data = clean_plot_data(self.data)
        times = [t for t, _ in cleaned_data]
        hours = [h for _, h in cleaned_data]

        # Determine if we should display in minutes (if max y-axis value < 1 hour)
        y_max = self.max_time_remaining_seen * PLOT_Y_AXIS_BUFFER_MULTIPLIER
        use_minutes = y_max < 1.0

        # Convert to minutes if needed for visualization
        if use_minutes:
            display_values = [h * 60.0 for h in hours]  # Convert hours to minutes
            y_max_display = y_max * 60.0
            y_label = "Minutes Remaining"
        else:
            display_values = hours
            y_max_display = y_max
            y_label = "Hours Remaining"

        self.ax.plot(times, display_values, "-", color="#007acc", linewidth=2.5, label="Time Remaining")  # type: ignore[arg-type, call-overload]

        # Draw dashed projection line from latest point to zero time remaining
        projected_completion_time = None
        if times and hours:
            latest_time = times[-1]
            latest_hours = hours[-1]

            # Calculate projected completion time: current time + hours remaining
            projected_completion_time = latest_time + timedelta(hours=latest_hours)

            # Convert latest value for display
            latest_display = latest_hours * 60.0 if use_minutes else latest_hours

            # Draw dashed line from (latest_time, latest_display) to (projected_completion_time, 0)
            self.ax.plot(
                [latest_time, projected_completion_time],
                [latest_display, 0.0],
                "--",
                color="#007acc",
                linewidth=2.0,
                alpha=0.6,
                label="Projected Completion",
            )  # type: ignore[arg-type]

        self.ax.set_facecolor("#2b2b2b")
        self.ax.set_xlabel("Time (UTC+1)", fontsize=12, color="#f0f0f0")
        self.ax.set_ylabel(y_label, fontsize=12, color="#f0f0f0")
        self.ax.set_title("Estimated Time Remaining", fontsize=14, color="#f0f0f0", pad=20)

        # Set x-axis limits: from first data point to projected completion time
        if times:
            earliest_time = times[0]
            if projected_completion_time is not None:
                self.ax.set_xlim(earliest_time, projected_completion_time)  # type: ignore[arg-type]
            else:
                # Fallback: if no projection, just use data range
                self.ax.set_xlim(earliest_time, times[-1])  # type: ignore[arg-type]

        # Set y-axis limits with appropriate minimum
        y_min_display = 0.1 * 60.0 if use_minutes else 0.1
        self.ax.set_ylim(0, max(y_max_display, y_min_display))

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

        self.ax.legend(loc="upper right", facecolor="#3c3c3c", edgecolor="#f0f0f0", labelcolor="#f0f0f0", fontsize=10)

        self.figure.tight_layout()
        self.canvas.draw()
