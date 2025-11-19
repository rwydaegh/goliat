"""Plotting components for GUI: time remaining, overall progress, and pie charts."""

from datetime import datetime, timezone, timedelta
from typing import TYPE_CHECKING, List, Tuple, Dict, Optional

import matplotlib

from ...constants import PLOT_Y_AXIS_BUFFER_MULTIPLIER

matplotlib.use("Qt5Agg")
try:
    import matplotlib.dates as mdates
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    from matplotlib.axes import Axes
except ImportError:
    FigureCanvas = None  # type: ignore
    Figure = None  # type: ignore
    mdates = None  # type: ignore
    Axes = None  # type: ignore

if TYPE_CHECKING:
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from goliat.profiler import Profiler


def convert_to_utc_plus_one(timestamp: datetime) -> datetime:
    """Convert a datetime to UTC+1 timezone.

    Handles both naive (assumed UTC) and timezone-aware datetimes.
    Works reliably across VMs worldwide by always normalizing to UTC first.

    Args:
        timestamp: Datetime to convert (can be naive or timezone-aware).
                  If naive, assumes it's already in UTC (recommended usage).

    Returns:
        Datetime in UTC+1 timezone (timezone-aware).
    """
    utc_plus_one_tz = timezone(timedelta(hours=1))

    # If timestamp is naive, assume it's UTC (most reliable for VMs worldwide)
    if timestamp.tzinfo is None:
        # Treat naive datetime as UTC
        utc_timestamp = timestamp.replace(tzinfo=timezone.utc)
    else:
        # Convert timezone-aware datetime to UTC first
        utc_timestamp = timestamp.astimezone(timezone.utc)

    # Convert UTC to UTC+1
    return utc_timestamp.astimezone(utc_plus_one_tz)


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
        self.data.append((utc_plus_one_timestamp, hours_remaining))
        self._refresh()

    def _refresh(self) -> None:
        """Refreshes plot with current data."""
        if not self.data:
            return

        self.ax.clear()

        times = [t for t, _ in self.data]
        hours = [h for _, h in self.data]

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

        self.ax.plot(times, display_values, "-", color="#007acc", linewidth=2.5, label="Time Remaining")  # type: ignore[arg-type]

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
                self.ax.set_xlim(earliest_time, projected_completion_time)
            else:
                # Fallback: if no projection, just use data range
                self.ax.set_xlim(earliest_time, times[-1])

        # Set y-axis limits with appropriate minimum
        y_min_display = 0.1 * 60.0 if use_minutes else 0.1
        self.ax.set_ylim(0, max(y_max_display, y_min_display))

        if mdates is not None:
            self.ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
        self.figure.autofmt_xdate(rotation=45)

        self.ax.grid(True, alpha=0.2, color="#f0f0f0")
        self.ax.tick_params(colors="#f0f0f0", which="both")
        self.ax.spines["bottom"].set_color("#f0f0f0")
        self.ax.spines["left"].set_color("#f0f0f0")
        self.ax.spines["top"].set_color = "#2b2b2b"
        self.ax.spines["right"].set_color = "#2b2b2b"

        self.ax.legend(loc="upper right", facecolor="#3c3c3c", edgecolor="#f0f0f0", labelcolor="#f0f0f0", fontsize=10)

        self.figure.tight_layout()
        self.canvas.draw()


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
        self.data.append((utc_plus_one_timestamp, progress_percent))
        self._refresh()

    def _refresh(self) -> None:
        """Refreshes plot with current data."""
        if not self.data:
            return

        self.ax.clear()

        times = [t for t, _ in self.data]
        progress = [p for _, p in self.data]

        self.ax.plot(times, progress, "-", color="#28a745", linewidth=2.5, label="Overall Progress")  # type: ignore[arg-type]

        self.ax.set_facecolor("#2b2b2b")
        self.ax.set_xlabel("Time (UTC+1)", fontsize=12, color="#f0f0f0")
        self.ax.set_ylabel("Progress (%)", fontsize=12, color="#f0f0f0")
        self.ax.set_title("Overall Progress", fontsize=14, color="#f0f0f0", pad=20)

        self.ax.set_ylim(0, 100)

        if mdates is not None:
            self.ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
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

        # Extract times and values
        times = [t for t, _ in self.cpu_data]
        cpu_values = [v for _, v in self.cpu_data]
        ram_values = [v for _, v in self.ram_data]

        # Filter GPU data to only include non-None values (data points are aligned)
        gpu_times_and_values = [(t, v) for (t, v) in self.gpu_data if v is not None]
        gpu_times = [t for t, _ in gpu_times_and_values]
        gpu_values = [v for _, v in gpu_times_and_values]

        # Filter GPU VRAM data
        gpu_vram_times_and_values = [(t, v) for (t, v) in self.gpu_vram_data if v is not None]
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

        if mdates is not None:
            self.ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
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


class PieChartsManager:
    """Manages four pie charts displaying timing breakdowns by phase and subtask.

    Shows visual breakdown of execution time:
    - Top-left: Phase weights (setup/run/extract relative durations)
    - Top-right: Setup subtasks breakdown
    - Bottom-left: Run subtasks breakdown
    - Bottom-right: Extract subtasks breakdown

    Updates automatically when profiler state changes. Filters out fake
    aggregated entries. Uses color palette for visual distinction.
    """

    @staticmethod
    def _format_task_label(subtask_key: str) -> str:
        """Formats a subtask key into a properly capitalized label.

        Handles special cases:
        - "isolve" -> "iSolve"
        - "sar" -> "SAR" (when part of "sar_statistics" or similar)

        Args:
            subtask_key: The subtask key (e.g., "run_isolve_execution", "extract_sar_statistics")

        Returns:
            Formatted label (e.g., "Run iSolve execution", "Extract SAR statistics")
        """
        # Replace underscores with spaces and split into words
        words = subtask_key.replace("_", " ").split()

        # Capitalize each word, with special handling for "isolve" and "sar"
        formatted_words = []
        for word in words:
            word_lower = word.lower()
            if word_lower == "isolve":
                formatted_words.append("iSolve")
            elif word_lower == "sar":
                formatted_words.append("SAR")
            else:
                formatted_words.append(word.capitalize())

        return " ".join(formatted_words)

    @staticmethod
    def _group_small_slices(labels: List[str], sizes: List[float], threshold_percent: float = 3.0) -> Tuple[List[str], List[float]]:
        """Groups slices below threshold into an "Others" slice.

        If "Others" ends up containing only one item, uses that item's name instead.

        Args:
            labels: List of slice labels
            sizes: List of slice sizes (in same order as labels)
            threshold_percent: Percentage threshold below which slices are grouped

        Returns:
            Tuple of (new_labels, new_sizes) with small slices grouped
        """
        if not labels or not sizes:
            return labels, sizes

        total = sum(sizes)
        if total == 0:
            return labels, sizes

        threshold_value = total * (threshold_percent / 100.0)

        # Separate large and small slices
        large_labels = []
        large_sizes = []
        small_labels = []
        small_sizes = []

        for label, size in zip(labels, sizes):
            if size >= threshold_value:
                large_labels.append(label)
                large_sizes.append(size)
            else:
                small_labels.append(label)
                small_sizes.append(size)

        # If no small slices, return as-is
        if not small_labels:
            return labels, sizes

        # If only one small slice, use its name instead of "Others"
        if len(small_labels) == 1:
            large_labels.append(small_labels[0])
            large_sizes.append(small_sizes[0])
        else:
            # Multiple small slices -> group as "Others"
            others_total = sum(small_sizes)
            large_labels.append("Others")
            large_sizes.append(others_total)

        return large_labels, large_sizes

    def __init__(self) -> None:
        """Sets up matplotlib figure with 2x2 subplot grid."""
        if Figure is None or FigureCanvas is None:
            raise ImportError("matplotlib is required for plotting")
        from matplotlib.figure import Figure as _Figure
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as _FigureCanvas
        from matplotlib.axes import Axes as _Axes

        self.figure: _Figure = _Figure(figsize=(12, 10), facecolor="#2b2b2b")
        self.canvas: _FigureCanvas = _FigureCanvas(self.figure)
        self.axes: List[_Axes] = [
            self.figure.add_subplot(221),  # Top-left: Phase weights
            self.figure.add_subplot(222),  # Top-right: Setup subtasks
            self.figure.add_subplot(223),  # Bottom-left: Run subtasks
            self.figure.add_subplot(224),  # Bottom-right: Extract subtasks
        ]
        self._setup()

    def _setup(self) -> None:
        """Initializes all four pie charts with dark theme."""
        for ax in self.axes:
            ax.clear()
            ax.set_facecolor("#2b2b2b")
        self.figure.patch.set_facecolor("#2b2b2b")
        self.figure.tight_layout()
        self.canvas.draw()

    def update(self, profiler: "Profiler") -> None:
        """Updates pie charts with timing data from profiler.

        Collects phase weights and subtask timing data, filters out fake
        aggregated entries, and renders pie charts with percentages. Charts
        show relative time spent in each phase/subtask, helping identify
        bottlenecks.

        Args:
            profiler: Profiler instance containing timing data.
        """
        if not profiler:
            return

        colors = ["#ff6b6b", "#4ecdc4", "#45b7d1", "#f9ca24", "#6c5ce7", "#00b894", "#fdcb6e", "#e17055"]

        # Chart 0 (Top-left): Phase Weights
        ax0 = self.axes[0]
        ax0.clear()
        ax0.set_facecolor("#2b2b2b")

        # Get phase weights/times
        phase_weights: Dict[str, float] = {}
        for phase in ["setup", "run", "extract"]:
            avg_time = profiler.profiling_config.get(f"avg_{phase}_time")
            if avg_time is not None:
                phase_weights[phase.capitalize()] = avg_time

        if phase_weights:
            labels = list(phase_weights.keys())
            sizes = list(phase_weights.values())

            # Group small slices into "Others"
            labels, sizes = self._group_small_slices(labels, sizes, threshold_percent=3.0)

            pie_result = ax0.pie(
                sizes,
                labels=labels,
                autopct="%1.1f%%",
                startangle=90,
                colors=["#ff6b6b", "#4ecdc4", "#45b7d1"],
                textprops={"color": "#f0f0f0", "fontsize": 10},
            )

            autotexts = pie_result[2] if len(pie_result) > 2 else []
            for autotext in autotexts:
                autotext.set_color("#2b2b2b")
                autotext.set_fontweight("bold")
                autotext.set_fontsize(9)

            ax0.set_title("Phase Weights", fontsize=12, color="#f0f0f0", pad=10)
        else:
            ax0.text(0.5, 0.5, "No data", ha="center", va="center", fontsize=12, color="#f0f0f0", transform=ax0.transAxes)
            ax0.set_title("Phase Weights", fontsize=12, color="#f0f0f0", pad=10)
            # Hide axes when showing "No data"
            ax0.set_xticks([])
            ax0.set_yticks([])
            ax0.spines["top"].set_visible(False)
            ax0.spines["right"].set_visible(False)
            ax0.spines["bottom"].set_visible(False)
            ax0.spines["left"].set_visible(False)

        # Charts 1-3: Subtasks for each phase
        phases = ["setup", "run", "extract"]
        phase_titles = ["Setup Subtasks", "Run Subtasks", "Extract Subtasks"]

        for i, (phase, title) in enumerate(zip(phases, phase_titles), start=1):
            ax = self.axes[i]
            ax.clear()
            ax.set_facecolor("#2b2b2b")

            # Collect subtask data for this phase
            # Filter out fake aggregated entries
            fake_entries = ["simulation", "simulation_total", "results_total"]

            subtask_data: Dict[str, float] = {}
            for key, value in profiler.profiling_config.items():
                if key.startswith(f"avg_{phase}_") and key != f"avg_{phase}_time":
                    # Extract the subtask name (everything after "avg_{phase}_")
                    subtask_key = key.replace(f"avg_{phase}_", "")

                    # Skip fake aggregated entries
                    if subtask_key in fake_entries:
                        continue

                    task_name = self._format_task_label(subtask_key)
                    subtask_data[task_name] = value

            if subtask_data:
                labels = list(subtask_data.keys())
                sizes = list(subtask_data.values())

                # Group small slices into "Others"
                labels, sizes = self._group_small_slices(labels, sizes, threshold_percent=3.0)

                # Create pie chart
                pie_result = ax.pie(
                    sizes,
                    labels=labels,
                    autopct="%1.1f%%",
                    startangle=90,
                    colors=colors[: len(labels)],
                    textprops={"color": "#f0f0f0", "fontsize": 9},
                )

                # Unpack result safely
                autotexts = pie_result[2] if len(pie_result) > 2 else []

                # Enhance text visibility
                for autotext in autotexts:
                    autotext.set_color("#2b2b2b")
                    autotext.set_fontweight("bold")
                    autotext.set_fontsize(8)

                ax.set_title(title, fontsize=12, color="#f0f0f0", pad=10)
            else:
                ax.text(0.5, 0.5, "No data", ha="center", va="center", fontsize=12, color="#f0f0f0", transform=ax.transAxes)
                ax.set_title(title, fontsize=12, color="#f0f0f0", pad=10)
                # Hide axes when showing "No data"
                ax.set_xticks([])
                ax.set_yticks([])
                ax.spines["top"].set_visible(False)
                ax.spines["right"].set_visible(False)
                ax.spines["bottom"].set_visible(False)
                ax.spines["left"].set_visible(False)

        self.figure.tight_layout()
        self.canvas.draw()
