"""Timings table component for displaying profiling statistics."""

from typing import TYPE_CHECKING, Dict, List, Any

import numpy as np
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView

if TYPE_CHECKING:
    from goliat.profiler import Profiler


class TimingsTable:
    """Manages timings table displaying profiling statistics.

    Shows execution time statistics (mean, median, min, max, percentiles) for
    all phases and subtasks. Filters out fake aggregated entries and organizes
    data by phase for easy inspection. Updates automatically when profiler
    state changes via queue messages.
    """

    def __init__(self, table_widget: QTableWidget) -> None:
        """Sets up the timings table widget.

        Args:
            table_widget: QTableWidget instance to populate with timing data.
        """
        self.table: QTableWidget = table_widget
        self._setup_table()

    def _setup_table(self) -> None:
        """Sets up table widget configuration."""
        self.table.setColumnCount(10)
        self.table.setHorizontalHeaderLabels(
            ["Phase", "Subtask", "Mean (s)", "Median (s)", "Min (s)", "Max (s)", "10% (s)", "25% (s)", "75% (s)", "90% (s)"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

    def update(self, profiler: "Profiler") -> None:
        """Populates table with timing statistics from profiler.

        Collects all phase and subtask timing data, computes statistics
        (mean, median, percentiles), and displays in table. Filters out
        fake aggregated entries that shouldn't be shown.

        Statistics computed:
        - Mean, median, min, max
        - 10th, 25th, 75th, 90th percentiles

        Args:
            profiler: Profiler instance containing timing data.
        """
        if not profiler:
            return

        self.table.setRowCount(0)

        # Collect all tasks with their raw timing data
        all_tasks: Dict[str, Dict[str, Any]] = {}
        for phase in ["setup", "run", "extract"]:
            avg_time = profiler.profiling_config.get(f"avg_{phase}_time")
            if avg_time is not None:
                raw_times = profiler.subtask_times.get(phase, [])
                all_tasks[f"{phase}_total"] = {
                    "phase": phase,
                    "subtask": "---",
                    "raw_times": raw_times if raw_times else [avg_time],
                }

        # Filter out fake aggregated entries that shouldn't be displayed
        fake_entries = ["setup_simulation", "run_simulation_total", "extract_results_total"]

        for key, value in profiler.profiling_config.items():
            if key.startswith("avg_") and "_time" not in key:
                task_name = key.replace("avg_", "")

                # Skip fake aggregated entries
                if task_name in fake_entries:
                    continue

                parts = task_name.split("_", 1)
                phase = parts[0]
                subtask_name = parts[1] if len(parts) > 1 else phase
                raw_times = profiler.subtask_times.get(task_name, [])
                all_tasks[key] = {
                    "phase": phase,
                    "subtask": subtask_name,
                    "raw_times": raw_times if raw_times else [value],
                }

        # Populate table with statistics
        for task_info in all_tasks.values():
            row_position = self.table.rowCount()
            self.table.insertRow(row_position)

            times: List[float] = task_info.get("raw_times", [])
            if times:
                times_array = np.array(times)
                mean_val = float(np.mean(times_array))
                median_val = float(np.median(times_array))
                min_val = float(np.min(times_array))
                max_val = float(np.max(times_array))
                p10 = float(np.percentile(times_array, 10))
                p25 = float(np.percentile(times_array, 25))
                p75 = float(np.percentile(times_array, 75))
                p90 = float(np.percentile(times_array, 90))
            else:
                mean_val = median_val = min_val = max_val = p10 = p25 = p75 = p90 = 0.0

            # Create items and set text color to ensure visibility in both light and dark modes
            light_text_color = QColor("#f0f0f0")
            items = [
                QTableWidgetItem(task_info.get("phase", "N/A")),
                QTableWidgetItem(task_info.get("subtask", "---")),
                QTableWidgetItem(f"{mean_val:.2f}"),
                QTableWidgetItem(f"{median_val:.2f}"),
                QTableWidgetItem(f"{min_val:.2f}"),
                QTableWidgetItem(f"{max_val:.2f}"),
                QTableWidgetItem(f"{p10:.2f}"),
                QTableWidgetItem(f"{p25:.2f}"),
                QTableWidgetItem(f"{p75:.2f}"),
                QTableWidgetItem(f"{p90:.2f}"),
            ]
            for item in items:
                item.setForeground(light_text_color)

            self.table.setItem(row_position, 0, items[0])
            self.table.setItem(row_position, 1, items[1])
            self.table.setItem(row_position, 2, items[2])
            self.table.setItem(row_position, 3, items[3])
            self.table.setItem(row_position, 4, items[4])
            self.table.setItem(row_position, 5, items[5])
            self.table.setItem(row_position, 6, items[6])
            self.table.setItem(row_position, 7, items[7])
            self.table.setItem(row_position, 8, items[8])
            self.table.setItem(row_position, 9, items[9])
