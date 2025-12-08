"""System utilization plot component for GUI."""

from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from ._matplotlib_imports import Figure, FigureCanvas, mdates  # type: ignore
from .utils import convert_to_utc_plus_one, validate_timestamp, clean_plot_data


class SystemUtilizationPlot:
    """Manages system utilization plot with real-time updates.

    Creates a matplotlib line plot showing CPU, RAM, GPU utilization,
    and GPU VRAM utilization percentages over time. Updates dynamically as new data points arrive.
    Y-axis extends to 105% (with ticks at 0, 20, 40, 60, 80, 100) to prevent clipping of lines at 100%.
    GPU lines only shown if GPU is available.
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
        self.cpu_data: List[Tuple[datetime, float]] = []
        self.ram_data: List[Tuple[datetime, float]] = []
        self.gpu_data: List[Tuple[datetime, Optional[float]]] = []
        self.gpu_vram_data: List[Tuple[datetime, Optional[float]]] = []
        self.gpu_available: bool = False

        # System info for legend (will be populated when first data point is added)
        self.cpu_cores: int = 0
        self.total_ram_gb: float = 0.0
        self.gpu_name: Optional[str] = None
        self.total_gpu_vram_gb: float = 0.0

        self._setup()

    def _setup(self) -> None:
        """Initializes plot with dark theme styling."""
        self.ax.clear()
        self.ax.set_facecolor("#2b2b2b")
        self.figure.patch.set_facecolor("#2b2b2b")

        self.ax.set_xlabel("Time (UTC+1)", fontsize=12, color="#f0f0f0")
        self.ax.set_ylabel("Utilization (%)", fontsize=12, color="#f0f0f0")
        self.ax.set_title("System Utilization", fontsize=14, color="#f0f0f0", pad=20)

        self.ax.tick_params(colors="#f0f0f0", which="both")
        self.ax.spines["bottom"].set_color("#f0f0f0")
        self.ax.spines["left"].set_color("#f0f0f0")
        self.ax.spines["top"].set_color("#2b2b2b")
        self.ax.spines["right"].set_color("#2b2b2b")

        self.ax.grid(True, alpha=0.2, color="#f0f0f0")
        self.ax.set_ylim(0, 105)
        self.ax.set_yticks([0, 20, 40, 60, 80, 100])

        # Initialize empty plots for legend (labels will be updated with system info when data arrives)
        self.ax.plot([], [], "-", color="#ff4444", linewidth=1.0, label="CPU")
        self.ax.plot([], [], "-", color="#00d4ff", linewidth=1.0, label="RAM")
        self.ax.plot([], [], "-", color="#ffd700", linewidth=1.0, label="GPU")
        self.ax.plot([], [], "-", color="#9d4edd", linewidth=1.0, label="GPU VRAM")
        self.ax.legend(loc="upper left", facecolor="#3c3c3c", edgecolor="#f0f0f0", labelcolor="#f0f0f0", fontsize=9)

        self.canvas.draw()

    def add_data_point(
        self,
        timestamp: datetime,
        cpu_percent: float,
        ram_percent: float,
        gpu_percent: Optional[float] = None,
        gpu_vram_percent: Optional[float] = None,
        cpu_cores: int = 0,
        total_ram_gb: float = 0.0,
        gpu_name: Optional[str] = None,
        total_gpu_vram_gb: float = 0.0,
    ) -> None:
        """Adds data point and refreshes plot.

        Args:
            timestamp: Timestamp for the data point.
            cpu_percent: CPU utilization percentage (0-100).
            ram_percent: RAM utilization percentage (0-100).
            gpu_percent: GPU utilization percentage (0-100), or None if unavailable.
            gpu_vram_percent: GPU VRAM utilization percentage (0-100), or None if unavailable.
            cpu_cores: Number of CPU cores (for legend).
            total_ram_gb: Total RAM in GB (for legend).
            gpu_name: GPU model name (for legend).
            total_gpu_vram_gb: Total GPU VRAM in GB (for legend).
        """
        # Store system info on first data point
        if len(self.cpu_data) == 0:
            self.cpu_cores = cpu_cores
            self.total_ram_gb = total_ram_gb
            self.gpu_name = gpu_name
            self.total_gpu_vram_gb = total_gpu_vram_gb

        # Convert timestamp to UTC+1
        utc_plus_one_timestamp = convert_to_utc_plus_one(timestamp)

        # Validate timestamp: reject if it's anomalously far from the last timestamp
        # This prevents spikes from corrupted timestamps (e.g., from NTP cache issues)
        if self.cpu_data and not validate_timestamp(utc_plus_one_timestamp, self.cpu_data[-1][0]):
            # Skip this data point - timestamp is anomalous
            return

        self.cpu_data.append((utc_plus_one_timestamp, cpu_percent))
        self.ram_data.append((utc_plus_one_timestamp, ram_percent))

        self.gpu_data.append((utc_plus_one_timestamp, gpu_percent))
        if gpu_percent is not None:
            self.gpu_available = True

        self.gpu_vram_data.append((utc_plus_one_timestamp, gpu_vram_percent))
        if gpu_vram_percent is not None:
            self.gpu_available = True

        self._refresh()

    def _refresh(self) -> None:
        """Refreshes plot with current data."""
        if not self.cpu_data:
            return

        self.ax.clear()

        # Clean all data: sort, deduplicate, and filter anomalies
        sorted_cpu_data = clean_plot_data(self.cpu_data)
        sorted_ram_data = clean_plot_data(self.ram_data)

        # Filter GPU data to only include non-None values, then clean
        gpu_times_and_values: List[Tuple[datetime, float]] = [(t, v) for (t, v) in self.gpu_data if v is not None]
        gpu_times_and_values = clean_plot_data(gpu_times_and_values)

        # Filter GPU VRAM data, then clean
        gpu_vram_times_and_values: List[Tuple[datetime, float]] = [(t, v) for (t, v) in self.gpu_vram_data if v is not None]
        gpu_vram_times_and_values = clean_plot_data(gpu_vram_times_and_values)

        # Extract times and values
        times = [t for t, _ in sorted_cpu_data]
        cpu_values = [v for _, v in sorted_cpu_data]
        ram_values = [v for _, v in sorted_ram_data]
        gpu_times = [t for t, _ in gpu_times_and_values]
        gpu_values = [v for _, v in gpu_times_and_values]
        gpu_vram_times = [t for t, _ in gpu_vram_times_and_values]
        gpu_vram_values = [v for _, v in gpu_vram_times_and_values]

        # Build legend labels with system info
        cpu_label = f"CPU ({self.cpu_cores} cores)" if self.cpu_cores > 0 else "CPU"
        ram_label = f"RAM ({self.total_ram_gb:.1f} GB)" if self.total_ram_gb > 0 else "RAM"
        gpu_label = f"GPU ({self.gpu_name})" if self.gpu_name else "GPU"
        gpu_vram_label = f"GPU VRAM ({self.total_gpu_vram_gb:.1f} GB)" if self.total_gpu_vram_gb > 0 else "GPU VRAM"

        # Plot CPU and RAM (always available)
        self.ax.plot(times, cpu_values, "-", color="#ff4444", linewidth=1.0, label=cpu_label)  # type: ignore[arg-type]
        self.ax.plot(times, ram_values, "-", color="#00d4ff", linewidth=1.0, label=ram_label)  # type: ignore[arg-type]

        # Plot GPU only if we have data
        if self.gpu_available and gpu_times:
            self.ax.plot(gpu_times, gpu_values, "-", color="#ffd700", linewidth=1.0, label=gpu_label)  # type: ignore[arg-type]

        # Plot GPU VRAM only if we have data
        if self.gpu_available and gpu_vram_times:
            self.ax.plot(gpu_vram_times, gpu_vram_values, "-", color="#9d4edd", linewidth=1.0, label=gpu_vram_label)  # type: ignore[arg-type]

        self.ax.set_facecolor("#2b2b2b")
        self.ax.set_xlabel("Time (UTC+1)", fontsize=12, color="#f0f0f0")
        self.ax.set_ylabel("Utilization (%)", fontsize=12, color="#f0f0f0")
        self.ax.set_title("System Utilization", fontsize=14, color="#f0f0f0", pad=20)

        self.ax.set_ylim(0, 105)
        self.ax.set_yticks([0, 20, 40, 60, 80, 100])

        # Set x-axis limits based on data range to ensure proper datetime formatting
        if times:
            earliest_time = times[0]
            latest_time = times[-1]
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

        self.ax.legend(loc="upper left", facecolor="#3c3c3c", edgecolor="#f0f0f0", labelcolor="#f0f0f0", fontsize=10)

        self.figure.tight_layout()
        self.canvas.draw()
