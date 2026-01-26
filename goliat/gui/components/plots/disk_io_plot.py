"""Disk I/O plot component for GUI."""

from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from ._matplotlib_imports import Figure, FigureCanvas, mdates  # type: ignore
from .utils import convert_to_utc_plus_one, validate_timestamp, clean_plot_data


class DiskIOPlot:
    """Manages disk I/O throughput plot with real-time updates.

    Creates a matplotlib line plot showing SSD read and write throughput
    over time, with a secondary Y-axis for page faults per second.
    Updates dynamically as new data points arrive.

    Left Y-axis: Disk I/O throughput (MB/s) for SSD Read/Write
    Right Y-axis: Page faults per second (indicates memory pressure)
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
        self.ax2: Optional[_Axes] = None  # Secondary Y-axis for page faults

        self.disk_read_data: List[Tuple[datetime, Optional[float]]] = []
        self.disk_write_data: List[Tuple[datetime, Optional[float]]] = []
        self.page_faults_data: List[Tuple[datetime, Optional[float]]] = []
        self.disk_available: bool = False
        self.page_faults_available: bool = False

        self._setup()

    def _setup(self) -> None:
        """Initializes plot with dark theme styling."""
        self.ax.clear()
        self.ax.set_facecolor("#2b2b2b")
        self.figure.patch.set_facecolor("#2b2b2b")

        self.ax.set_xlabel("Time (UTC+1)", fontsize=12, color="#f0f0f0")
        self.ax.set_ylabel("Disk I/O (MB/s)", fontsize=12, color="#f0f0f0")
        self.ax.set_title("Disk I/O & Memory Pressure", fontsize=14, color="#f0f0f0", pad=20)

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
        page_faults_per_sec: Optional[float] = None,
    ) -> None:
        """Adds data point and refreshes plot.

        Args:
            timestamp: Timestamp for the data point.
            disk_read_mbps: Disk read throughput in MB/s, or None if unavailable.
            disk_write_mbps: Disk write throughput in MB/s, or None if unavailable.
            page_faults_per_sec: Page faults per second, or None if unavailable.
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
        self.page_faults_data.append((utc_plus_one_timestamp, page_faults_per_sec))

        if disk_read_mbps is not None or disk_write_mbps is not None:
            self.disk_available = True

        if page_faults_per_sec is not None:
            self.page_faults_available = True

        self._refresh()

    def _refresh(self) -> None:
        """Refreshes plot with current data."""
        if not self.disk_read_data:
            return

        self.ax.clear()
        # Clear secondary axis if it exists
        if self.ax2 is not None:
            self.ax2.remove()
            self.ax2 = None

        # Filter disk I/O data to only include non-None values, then clean
        disk_read_times_and_values: List[Tuple[datetime, float]] = [(t, v) for (t, v) in self.disk_read_data if v is not None]
        disk_read_times_and_values = clean_plot_data(disk_read_times_and_values)
        disk_write_times_and_values: List[Tuple[datetime, float]] = [(t, v) for (t, v) in self.disk_write_data if v is not None]
        disk_write_times_and_values = clean_plot_data(disk_write_times_and_values)

        # Filter page faults data
        page_faults_times_and_values: List[Tuple[datetime, float]] = [(t, v) for (t, v) in self.page_faults_data if v is not None]
        page_faults_times_and_values = clean_plot_data(page_faults_times_and_values)

        # Extract times and values
        disk_read_times = [t for t, _ in disk_read_times_and_values]
        disk_read_values = [v for _, v in disk_read_times_and_values]
        disk_write_times = [t for t, _ in disk_write_times_and_values]
        disk_write_values = [v for _, v in disk_write_times_and_values]
        page_faults_times = [t for t, _ in page_faults_times_and_values]
        page_faults_values = [v for _, v in page_faults_times_and_values]

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

        # Configure primary axis
        self.ax.set_facecolor("#2b2b2b")
        self.ax.set_xlabel("Time (UTC+1)", fontsize=12, color="#f0f0f0")
        self.ax.set_ylabel("Disk I/O (MB/s)", fontsize=12, color="#f0f0f0")
        self.ax.set_title("Disk I/O & Memory Pressure", fontsize=14, color="#f0f0f0", pad=20)

        # Set reasonable y-limit for disk I/O (auto-scale with some headroom)
        all_disk_values = disk_read_values + disk_write_values
        if all_disk_values:
            max_disk = max(all_disk_values)
            # Set min of 100 MB/s or 20% above max, whichever is larger
            disk_ylim = max(100, max_disk * 1.2)
            self.ax.set_ylim(0, disk_ylim)

        # Plot page faults on secondary Y-axis if we have data
        if self.page_faults_available and page_faults_times:
            self.ax2 = self.ax.twinx()

            (line_faults,) = self.ax2.plot(  # type: ignore[union-attr]
                page_faults_times, page_faults_values, "-", color="#ff4444", linewidth=1.5, label="Page Faults/s"
            )  # type: ignore[arg-type]
            lines.append(line_faults)
            labels.append("Page Faults/s")

            # Configure secondary axis
            self.ax2.set_ylabel("Page Faults/s", fontsize=12, color="#ff4444")  # type: ignore[union-attr]
            self.ax2.tick_params(colors="#ff4444", which="both")  # type: ignore[union-attr]
            self.ax2.spines["right"].set_color("#ff4444")  # type: ignore[union-attr]

            # Set reasonable y-limit for page faults (auto-scale with some headroom)
            if page_faults_values:
                max_faults = max(page_faults_values)
                # Set min of 10 faults/s or 20% above max, whichever is larger
                faults_ylim = max(10, max_faults * 1.2)
                self.ax2.set_ylim(0, faults_ylim)  # type: ignore[union-attr]

        # Set x-axis limits based on data range to ensure proper datetime formatting
        all_times = disk_read_times + disk_write_times + page_faults_times
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
        # Right spine colored based on whether we have page faults data
        if self.ax2 is not None:
            self.ax.spines["right"].set_color("#2b2b2b")  # Hide primary right spine
        else:
            self.ax.spines["right"].set_color("#2b2b2b")

        # Combined legend for both axes
        if lines:
            self.ax.legend(lines, labels, loc="upper left", facecolor="#3c3c3c", edgecolor="#f0f0f0", labelcolor="#f0f0f0", fontsize=10)

        self.figure.tight_layout()
        self.canvas.draw()
