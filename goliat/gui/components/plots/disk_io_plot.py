"""Disk I/O plot component for GUI."""

from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from ._matplotlib_imports import Figure, FigureCanvas, mdates  # type: ignore
from .utils import convert_to_utc_plus_one, validate_timestamp, clean_plot_data


class DiskIOPlot:
    """Manages disk I/O throughput plot with real-time updates.

    Creates a matplotlib line plot showing SSD read and write throughput
    over time. Updates dynamically as new data points arrive.

    Y-axis: Disk I/O throughput (MB/s) for SSD Read/Write
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

        self.disk_read_data: List[Tuple[datetime, Optional[float]]] = []
        self.disk_write_data: List[Tuple[datetime, Optional[float]]] = []
        self.disk_available: bool = False

        self._setup()

    def _setup(self) -> None:
        """Initializes plot with dark theme styling."""
        self.ax.clear()
        self.ax.set_facecolor("#2b2b2b")
        self.figure.patch.set_facecolor("#2b2b2b")

        self.ax.set_xlabel("Time (UTC+1)", fontsize=12, color="#f0f0f0")
        self.ax.set_ylabel("Disk I/O (MB/s)", fontsize=12, color="#f0f0f0")
        self.ax.set_title("Disk I/O Throughput", fontsize=14, color="#f0f0f0", pad=20)

        self.ax.tick_params(colors="#f0f0f0", which="both")
        self.ax.spines["bottom"].set_color("#f0f0f0")
        self.ax.spines["left"].set_color("#f0f0f0")
        self.ax.spines["top"].set_color("#2b2b2b")
        self.ax.spines["right"].set_color("#2b2b2b")

        self.ax.grid(True, alpha=0.2, color="#f0f0f0")

        # Initialize empty plots for legend
        self.ax.plot([], [], "--", color="#00ff88", linewidth=1.5, label="Disk Read")
        self.ax.plot([], [], "--", color="#ff8800", linewidth=1.5, label="Disk Write")
        self.ax.legend(loc="upper left", facecolor="#3c3c3c", edgecolor="#f0f0f0", labelcolor="#f0f0f0", fontsize=10)

        self.canvas.draw()

    def add_data_point(
        self,
        timestamp: datetime,
        disk_read_mbps: Optional[float] = None,
        disk_write_mbps: Optional[float] = None,
    ) -> None:
        """Adds data point and refreshes plot.

        Args:
            timestamp: Timestamp for the data point.
            disk_read_mbps: Disk read throughput in MB/s, or None if unavailable.
            disk_write_mbps: Disk write throughput in MB/s, or None if unavailable.
        """
        # Convert timestamp to UTC+1
        utc_plus_one_timestamp = convert_to_utc_plus_one(timestamp)

        # Validate timestamp: reject if it's anomalously far from the last timestamp
        # This prevents spikes from corrupted timestamps (e.g., from NTP cache issues)
        if self.disk_read_data and not validate_timestamp(utc_plus_one_timestamp, self.disk_read_data[-1][0]):
            # Skip this data point - timestamp is anomalous
            return

        self.disk_read_data.append((utc_plus_one_timestamp, disk_read_mbps))
        self.disk_write_data.append((utc_plus_one_timestamp, disk_write_mbps))

        if disk_read_mbps is not None or disk_write_mbps is not None:
            self.disk_available = True

        self._refresh()

    def _refresh(self) -> None:
        """Refreshes plot with current data."""
        if not self.disk_read_data:
            return

        self.ax.clear()

        # Filter disk I/O data to only include non-None values, then clean
        disk_read_times_and_values: List[Tuple[datetime, float]] = [(t, v) for (t, v) in self.disk_read_data if v is not None]
        disk_read_times_and_values = clean_plot_data(disk_read_times_and_values)
        disk_write_times_and_values: List[Tuple[datetime, float]] = [(t, v) for (t, v) in self.disk_write_data if v is not None]
        disk_write_times_and_values = clean_plot_data(disk_write_times_and_values)

        # Extract times and values
        disk_read_times = [t for t, _ in disk_read_times_and_values]
        disk_read_values = [v for _, v in disk_read_times_and_values]
        disk_write_times = [t for t, _ in disk_write_times_and_values]
        disk_write_values = [v for _, v in disk_write_times_and_values]

        lines = []
        labels = []

        # Plot disk read
        if disk_read_times:
            (line_read,) = self.ax.plot(disk_read_times, disk_read_values, "--", color="#00ff88", linewidth=1.5, label="Disk Read")  # type: ignore[arg-type]
            lines.append(line_read)
            labels.append("Disk Read")

        # Plot disk write
        if disk_write_times:
            (line_write,) = self.ax.plot(disk_write_times, disk_write_values, "--", color="#ff8800", linewidth=1.5, label="Disk Write")  # type: ignore[arg-type]
            lines.append(line_write)
            labels.append("Disk Write")

        # Configure axis
        self.ax.set_facecolor("#2b2b2b")
        self.ax.set_xlabel("Time (UTC+1)", fontsize=12, color="#f0f0f0")
        self.ax.set_ylabel("Disk I/O (MB/s)", fontsize=12, color="#f0f0f0")
        self.ax.set_title("Disk I/O Throughput", fontsize=14, color="#f0f0f0", pad=20)

        # Set reasonable y-limit for disk I/O (auto-scale with some headroom)
        all_disk_values = disk_read_values + disk_write_values
        if all_disk_values:
            max_disk = max(all_disk_values)
            # Set min of 100 MB/s or 20% above max, whichever is larger
            disk_ylim = max(100, max_disk * 1.2)
            self.ax.set_ylim(0, disk_ylim)

        # Set x-axis limits based on data range to ensure proper datetime formatting
        all_times = disk_read_times + disk_write_times
        if all_times:
            earliest_time = min(all_times)
            latest_time = max(all_times)
            # Add small padding (1% of time range) for better visualization
            time_range = latest_time - earliest_time
            if time_range.total_seconds() > 0:
                padding = time_range * 0.01
                self.ax.set_xlim(earliest_time - padding, latest_time + padding)  # type: ignore[arg-type]
            else:
                # If all times are the same, add a small window around it
                padding = timedelta(seconds=1)
                self.ax.set_xlim(earliest_time - padding, earliest_time + padding)  # type: ignore[arg-type]

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

        # Legend
        if lines:
            self.ax.legend(lines, labels, loc="upper left", facecolor="#3c3c3c", edgecolor="#f0f0f0", labelcolor="#f0f0f0", fontsize=10)

        self.figure.tight_layout()
        self.canvas.draw()
