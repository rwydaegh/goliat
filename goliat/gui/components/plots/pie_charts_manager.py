"""Pie charts manager component for GUI."""

from typing import TYPE_CHECKING, Dict, List, Tuple

from ._matplotlib_imports import Figure, FigureCanvas  # type: ignore

if TYPE_CHECKING:
    from goliat.profiler import Profiler


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
        - "sapd" -> "SAPD" (Surface Absorbed Power Density)

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
            elif word_lower == "sapd":
                formatted_words.append("SAPD")
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
