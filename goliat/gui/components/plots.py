"""Plotting components for GUI: time remaining, overall progress, and pie charts."""

from datetime import datetime
from typing import TYPE_CHECKING, List, Tuple, Dict

import matplotlib

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

        self.ax.set_xlabel("Time", fontsize=12, color="#f0f0f0")
        self.ax.set_ylabel("Hours Remaining", fontsize=12, color="#f0f0f0")
        self.ax.set_title("Estimated Time Remaining", fontsize=14, color="#f0f0f0", pad=20)

        self.ax.tick_params(colors="#f0f0f0", which="both")
        self.ax.spines["bottom"].set_color("#f0f0f0")
        self.ax.spines["left"].set_color("#f0f0f0")
        self.ax.spines["top"].set_color("#2b2b2b")
        self.ax.spines["right"].set_color("#2b2b2b")

        self.ax.grid(True, alpha=0.2, color="#f0f0f0")

        self.ax.plot([], [], "o-", color="#007acc", linewidth=2, markersize=4, label="Time Remaining")
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
        self.data.append((timestamp, hours_remaining))
        self._refresh()

    def _refresh(self) -> None:
        """Refreshes plot with current data."""
        if not self.data:
            return

        self.ax.clear()

        times = [t for t, _ in self.data]
        hours = [h for _, h in self.data]

        self.ax.plot(times, hours, "o-", color="#007acc", linewidth=2, markersize=4, label="Time Remaining")  # type: ignore[arg-type]

        self.ax.set_facecolor("#2b2b2b")
        self.ax.set_xlabel("Time", fontsize=12, color="#f0f0f0")
        self.ax.set_ylabel("Hours Remaining", fontsize=12, color="#f0f0f0")
        self.ax.set_title("Estimated Time Remaining", fontsize=14, color="#f0f0f0", pad=20)

        y_max = self.max_time_remaining_seen * 1.1
        self.ax.set_ylim(0, max(y_max, 0.1))

        if mdates is not None:
            self.ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
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

        self.ax.set_xlabel("Time", fontsize=12, color="#f0f0f0")
        self.ax.set_ylabel("Progress (%)", fontsize=12, color="#f0f0f0")
        self.ax.set_title("Overall Progress", fontsize=14, color="#f0f0f0", pad=20)

        self.ax.tick_params(colors="#f0f0f0", which="both")
        self.ax.spines["bottom"].set_color("#f0f0f0")
        self.ax.spines["left"].set_color("#f0f0f0")
        self.ax.spines["top"].set_color("#2b2b2b")
        self.ax.spines["right"].set_color("#2b2b2b")

        self.ax.grid(True, alpha=0.2, color="#f0f0f0")
        self.ax.set_ylim(0, 100)

        self.ax.plot([], [], "o-", color="#28a745", linewidth=2, markersize=4, label="Overall Progress")
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
        self.data.append((timestamp, progress_percent))
        self._refresh()

    def _refresh(self) -> None:
        """Refreshes plot with current data."""
        if not self.data:
            return

        self.ax.clear()

        times = [t for t, _ in self.data]
        progress = [p for _, p in self.data]

        self.ax.plot(times, progress, "o-", color="#28a745", linewidth=2, markersize=4, label="Overall Progress")  # type: ignore[arg-type]

        self.ax.set_facecolor("#2b2b2b")
        self.ax.set_xlabel("Time", fontsize=12, color="#f0f0f0")
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

                    task_name = subtask_key.replace("_", " ").capitalize()
                    subtask_data[task_name] = value

            if subtask_data:
                labels = list(subtask_data.keys())
                sizes = list(subtask_data.values())

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

        self.figure.tight_layout()
        self.canvas.draw()
