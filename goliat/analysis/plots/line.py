"""Line plot generators."""

import logging
import math

import matplotlib.pyplot as plt
import pandas as pd

from .base import BasePlotter, METRIC_LABELS, LEGEND_LABELS


class LinePlotter(BasePlotter):
    """Generates line plots for SAR analysis."""

    def _calculate_legend_height(self, n_items: int, n_cols: int = 3, item_height: float = 0.25) -> float:
        """Calculates the height needed for a legend below the plot.

        Args:
            n_items: Number of legend items.
            n_cols: Number of columns in the legend grid (default: 3).
            item_height: Height per legend row in inches (default: 0.25).

        Returns:
            Total height needed for the legend in inches.
        """
        n_rows = math.ceil(n_items / n_cols)
        return n_rows * item_height + 0.2  # Add small padding

    def _place_legend_below(self, fig, ax, handles_labels_or_n_items, n_cols: int = 3, handles=None, labels=None):
        """Places legend below the plot in a grid layout.

        Ensures legend width doesn't exceed figsize and positions it lower to avoid x-axis label overlap.
        Uses solid black line for legend box.

        Args:
            fig: Matplotlib figure object.
            ax: Matplotlib axes object.
            handles_labels_or_n_items: Either number of items (int) or tuple of (handles, labels).
            n_cols: Number of columns in the legend grid (default: 3).
            handles: Optional legend handles (if not provided, will get from ax).
            labels: Optional legend labels (if not provided, will get from ax).
        """
        # Get handles and labels
        if handles is None or labels is None:
            handles, labels = ax.get_legend_handles_labels()

        # Determine number of items
        if isinstance(handles_labels_or_n_items, int):
            n_items = handles_labels_or_n_items
        else:
            n_items = len(handles)

        # Remove existing legend if any
        if ax.get_legend() is not None:
            ax.get_legend().remove()

        # Calculate legend width to ensure it fits within figsize
        fig_width = fig.get_size_inches()[0]
        # Estimate max label width (rough estimate: longest label * fontsize * 0.01 inches per char)
        max_label_len = max(len(str(label)) for label in labels) if labels else 10
        estimated_label_width = max_label_len * 8 * 0.01  # fontsize 8, ~0.01 inches per char
        # Adjust n_cols if needed to fit within figure width
        while n_cols > 1 and (estimated_label_width * n_cols) > (fig_width * 0.8):
            n_cols -= 1

        # Format labels to be human readable
        formatted_labels = []
        for label in labels:
            # Preserve "MHz" before any title() conversion
            label_preserved = label.replace(" MHz", " __MHZ__").replace("MHz", "__MHZ__")
            # Convert underscores to spaces and capitalize properly
            formatted_label = (
                self._format_organ_name(label_preserved)
                if hasattr(self, "_format_organ_name")
                else label_preserved.replace("_", " ").title()
            )
            # Restore "MHz" (case-sensitive)
            formatted_label = formatted_label.replace("__MHZ__", "MHz").replace(" Mhz", " MHz")
            # Handle psSAR10g_eyes -> psSAR10g Eyes (preserve capitalization)
            # Fix any incorrect capitalization like "Pssar10g" -> "psSAR10g"
            formatted_label = formatted_label.replace("Pssar10g", "psSAR10g").replace("Pssar", "psSAR")
            formatted_label = formatted_label.replace("psSAR10g", "psSAR10g ").replace("  ", " ")
            formatted_labels.append(formatted_label)

        # Filter out None handles, but ensure we maintain the correct count
        # If handles were explicitly passed, they should match labels in length
        # Only filter None if handles were auto-extracted from axes
        if handles is not None and len(handles) == len(formatted_labels):
            # Handles were explicitly passed and match labels - use them as-is
            valid_handles = handles
            valid_labels = formatted_labels
        else:
            # Handles were auto-extracted or don't match - filter None and match lengths
            valid_handles = [h for h in handles if h is not None] if handles else []
            # If we have fewer handles than labels, create patches for missing ones
            if len(valid_handles) < len(formatted_labels):
                import matplotlib.patches as mpatches

                # Get colors - use academic colors
                colors = self._get_academic_colors(len(formatted_labels))
                for i in range(len(valid_handles), len(formatted_labels)):
                    patch = mpatches.Patch(facecolor=colors[i], edgecolor="black", linewidth=0.5)
                    valid_handles.append(patch)
            # Ensure labels match handles length
            valid_labels = formatted_labels[: len(valid_handles)] if len(valid_handles) <= len(formatted_labels) else formatted_labels

        # Place legend below the plot - positioned much lower to avoid x-axis label overlap
        legend = ax.legend(
            valid_handles,
            valid_labels,
            loc="upper center",
            bbox_to_anchor=(0.5, -0.25),  # Much lower position to avoid x-axis label overlap
            ncol=n_cols,
            fontsize=8,
            frameon=True,
            fancybox=False,
            shadow=False,
            edgecolor="black",  # Solid black line for legend box
            facecolor="white",
            framealpha=1.0,
            borderpad=0.5,
        )
        # Set legend border linewidth to match figure lines (typically 0.5-1.0)
        legend.get_frame().set_linewidth(0.5)

        # Calculate legend height and adjust subplot
        legend_height_inches = self._calculate_legend_height(n_items, n_cols)
        fig_height = fig.get_size_inches()[1]
        # Add more bottom margin to accommodate lower legend position
        # Ensure bottom_margin stays reasonable (max 0.5 to avoid bottom >= top error)
        bottom_margin = min(0.25 + (legend_height_inches / fig_height), 0.5)
        fig.subplots_adjust(bottom=bottom_margin)

    def plot_peak_sar_line(self, summary_stats: pd.DataFrame):
        """Plots peak SAR trend across frequencies for far-field analysis."""
        fig, ax = plt.subplots(figsize=(3.5, 2.5))  # IEEE single-column width
        title_full = self._get_title_with_phantom("average peak SAR (10g) across all tissues")
        if "peak_sar" in summary_stats.columns:
            summary_stats["peak_sar"].plot(kind="line", marker="o", ax=ax, color="purple")
            # Don't set title on plot - will be in caption file
            ax.set_xlabel(self._format_axis_label("Frequency", "MHz"))
            ax.set_ylabel(self._format_axis_label("Normalized peak SAR", r"mW kg$^{-1}$"))
            ax.set_xticks(summary_stats.index)
            # Rotate x-axis labels only for actual simulated frequencies (1450, 2140, 2450, etc.)
            # Check if frequencies are actual simulated values (not auto-generated)
            freq_values = summary_stats.index.tolist()
            simulated_freqs = [1450, 2140, 2450]
            if freq_values and any(isinstance(f, (int, float)) and f in simulated_freqs for f in freq_values):
                plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
                self._adjust_slanted_tick_labels(ax)
            ax.grid(True, which="both", linestyle="--", linewidth=0.5)
            # Set y-axis to start at 0 and go to max + 5%
            y_max = ax.get_ylim()[1]
            ax.set_ylim(0, y_max * 1.05)
        else:
            ax.text(0.5, 0.5, "No Peak SAR data found", ha="center", va="center")
        plt.tight_layout()
        phantom_name_formatted = self.phantom_name.capitalize() if self.phantom_name else "the phantom"
        caption = f"The line plot shows the trend of average peak SAR (10g) values across all tissues as a function of frequency for {phantom_name_formatted}."
        self._save_figure(fig, "line", "line_peak_sar_summary", title=title_full, caption=caption, dpi=300)

        # Save CSV data
        csv_data = summary_stats[["peak_sar"]].copy() if "peak_sar" in summary_stats.columns else pd.DataFrame()
        csv_data.index.name = "frequency_mhz"
        if not csv_data.empty:
            self._save_csv_data(csv_data, "line", "line_peak_sar_summary")

    def plot_pssar_line(self, scenario_name: str, avg_results: pd.DataFrame):
        """Plots average psSAR10g trends for tissue groups by frequency.

        Shows how peak spatial-average SAR varies with frequency for eyes,
        skin, and brain groups.

        Args:
            scenario_name: Placement scenario name.
            avg_results: DataFrame with average psSAR10g values.
        """
        pssar_columns = [col for col in avg_results.columns if col.startswith("psSAR10g")]
        base_title = "average normalized psSAR10g for scenario"
        title_full = self._get_title_with_phantom(base_title, scenario_name)

        # Calculate dynamic height based on legend size
        n_items = len(pssar_columns) if pssar_columns else 0
        legend_height = self._calculate_legend_height(n_items, n_cols=3) if n_items > 0 else 0
        base_height = 2.5  # Base plot height
        total_height = base_height + legend_height

        fig, ax = plt.subplots(figsize=(3.5, total_height))  # IEEE single-column width, dynamic height
        if pssar_columns:
            colors = self._get_academic_colors(len(pssar_columns))
            linestyles = self._get_academic_linestyles(len(pssar_columns))
            markers = self._get_academic_markers(len(pssar_columns))
            for idx, col in enumerate(pssar_columns):
                avg_results[col].plot(
                    kind="line",
                    marker=markers[idx],
                    linestyle=linestyles[idx],
                    ax=ax,
                    color=colors[idx],
                    label=LEGEND_LABELS.get(col, col),
                )
            # Don't set title on plot - will be in caption file
            ax.set_xlabel(self._format_axis_label("Frequency", "MHz"))
            ax.set_ylabel(self._format_axis_label("Normalized psSAR10g", r"mW kg$^{-1}$"))
            legend_labels = [label for col in pssar_columns if (label := LEGEND_LABELS.get(col, col)) is not None]
            # Use 2 columns for legend when there are 4 items to ensure balanced layout
            n_cols = 2 if len(legend_labels) == 4 else min(3, len(legend_labels))
            # Place legend below in grid format (will get handles/labels from ax)
            self._place_legend_below(fig, ax, len(legend_labels), n_cols=n_cols)
            ax.set_xticks(avg_results.index)
            # Rotate frequency labels (always rotate when x-axis is Frequency)
            plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
            self._adjust_slanted_tick_labels(ax)
            # Set y-axis to start at 0 and go to max + 5%
            y_max = ax.get_ylim()[1]
            ax.set_ylim(0, y_max * 1.05)
        else:
            ax.text(0.5, 0.5, "No psSAR10g data found", ha="center", va="center")
        plt.tight_layout()
        phantom_name_formatted = self.phantom_name.capitalize() if self.phantom_name else "the phantom"
        caption = f"The line plot shows average normalized psSAR10g trends for different tissue groups (Eyes, Skin, Brain, Genitals, Whole Body) across frequencies for the {self._format_scenario_name(scenario_name)} scenario for {phantom_name_formatted}."
        self._save_figure(fig, "line", f"pssar10g_line_{scenario_name}", title=title_full, caption=caption, dpi=300)

        # Save CSV data
        csv_data = avg_results[pssar_columns].copy()
        csv_data.index.name = "frequency_mhz"
        self._save_csv_data(csv_data, "line", f"pssar10g_line_{scenario_name}")

    def plot_sar_line(self, scenario_name: str, avg_results: pd.DataFrame):
        """Plots average SAR trends for tissue groups by frequency.

        Symmetric counterpart to plot_pssar_line.

        Args:
            scenario_name: Placement scenario name.
            avg_results: DataFrame with average SAR values.
        """
        sar_columns = [col for col in avg_results.columns if col.startswith("SAR_")]
        base_title = "average normalized SAR for scenario"
        title_full = self._get_title_with_phantom(base_title, scenario_name)

        # Calculate dynamic height based on legend size
        n_items = len(sar_columns) if sar_columns else 0
        legend_height = self._calculate_legend_height(n_items, n_cols=3) if n_items > 0 else 0
        base_height = 2.5  # Base plot height
        total_height = base_height + legend_height

        fig, ax = plt.subplots(figsize=(3.5, total_height))  # IEEE single-column width, dynamic height
        if sar_columns:
            colors = self._get_academic_colors(len(sar_columns))
            linestyles = self._get_academic_linestyles(len(sar_columns))
            markers = self._get_academic_markers(len(sar_columns))
            for idx, col in enumerate(sar_columns):
                avg_results[col].plot(
                    kind="line",
                    marker=markers[idx],
                    linestyle=linestyles[idx],
                    ax=ax,
                    color=colors[idx],
                    label=LEGEND_LABELS.get(col, col),
                )
            # Don't set title on plot - will be in caption file
            ax.set_xlabel(self._format_axis_label("Frequency", "MHz"))
            ax.set_ylabel(self._format_axis_label("Normalized SAR", r"mW kg$^{-1}$"))
            # Use trimmed legend labels (remove "SAR" since y-axis already says "SAR")
            legend_labels = [LEGEND_LABELS.get(col, col.replace("SAR_", "").replace("_", " ").title()) for col in sar_columns]
            # Use 2 columns for legend when there are 4 items to ensure balanced layout
            n_cols = 2 if len(legend_labels) == 4 else min(3, len(legend_labels))
            # Place legend below in grid format (will get handles/labels from ax)
            self._place_legend_below(fig, ax, len(legend_labels), n_cols=n_cols)
            ax.set_xticks(avg_results.index)
            # Rotate frequency labels (always rotate when x-axis is Frequency)
            plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
            self._adjust_slanted_tick_labels(ax)
            # Set y-axis to start at 0 and go to max + 5%
            y_max = ax.get_ylim()[1]
            ax.set_ylim(0, y_max * 1.05)
        else:
            ax.text(0.5, 0.5, "No SAR data found", ha="center", va="center")
        plt.tight_layout()
        phantom_name_formatted = self.phantom_name.capitalize() if self.phantom_name else "the phantom"
        caption = f"The line plot shows average normalized SAR trends for different tissue groups (Head, Trunk, Whole-Body, Brain, Skin, Eyes, Genitals) across frequencies for the {self._format_scenario_name(scenario_name)} scenario for {phantom_name_formatted}."
        self._save_figure(fig, "line", f"sar_line_{scenario_name}", title=title_full, caption=caption, dpi=300)

        # Save CSV data
        csv_data = avg_results[sar_columns].copy()
        csv_data.index.name = "frequency_mhz"
        self._save_csv_data(csv_data, "line", f"sar_line_{scenario_name}")

    def plot_pssar_line_individual_variations(
        self,
        results_df: pd.DataFrame,
        scenario_name: str,
        metric_column: str = "psSAR10g_eyes",
    ):
        """Plots individual variation lines for each placement/direction/polarization.

        Similar to boxplots but shows individual lines instead of aggregating variability.
        Each placement variation gets its own line with a legend entry.

        Args:
            results_df: DataFrame with detailed results including 'placement' column.
            scenario_name: Scenario name for filtering.
            metric_column: Column name for the metric to plot (e.g., 'psSAR10g_eyes').
        """
        if metric_column not in results_df.columns:
            logging.getLogger("progress").warning(
                f"Column '{metric_column}' not found for individual variation plot.",
                extra={"log_type": "warning"},
            )
            return

        # Filter by scenario
        plot_df = results_df[results_df["scenario"] == scenario_name].copy()

        if plot_df.empty:
            return

        # Group by frequency and placement
        if "placement" not in plot_df.columns:
            logging.getLogger("progress").warning(
                "No 'placement' column found for individual variation plot.",
                extra={"log_type": "warning"},
            )
            return

        # Get unique placements
        placements = sorted(plot_df["placement"].unique())

        # Create pivot table: frequency vs placement
        pivot_data = plot_df.pivot_table(
            index="frequency_mhz",
            columns="placement",
            values=metric_column,
            aggfunc="mean",
        )

        if pivot_data.empty:
            return

        # Calculate dynamic height based on legend size
        # Use 2 columns for legend layout
        n_items = len(placements)
        n_cols = 2  # Always use 2 columns for legend
        legend_height = self._calculate_legend_height(n_items, n_cols=n_cols)
        # Use IEEE standard single-column width (3.5 inches) - height will be adjusted dynamically
        # Base height for proper font rendering at IEEE single-column width
        base_height = 2.5
        total_height = base_height + legend_height

        fig, ax = plt.subplots(figsize=(3.5, total_height))  # IEEE single-column width (3.5"), dynamic height

        # Plot each placement as a separate line

        colors = self._get_academic_colors(len(placements))
        linestyles = self._get_academic_linestyles(len(placements))
        markers = self._get_academic_markers(len(placements))
        for idx, placement in enumerate(placements):
            if placement in pivot_data.columns:
                # Format placement name to be human readable
                placement_formatted = (
                    self._format_organ_name(placement) if hasattr(self, "_format_organ_name") else placement.replace("_", " ").title()
                )
                ax.plot(
                    pivot_data.index,
                    pivot_data[placement],
                    marker=markers[idx],
                    linestyle=linestyles[idx],
                    label=placement_formatted,
                    linewidth=1.5,
                    markersize=4,
                    color=colors[idx],
                    alpha=0.7,
                )

        ax.set_xlabel(self._format_axis_label("Frequency", "MHz"))
        metric_label = METRIC_LABELS.get(metric_column, metric_column)
        ax.set_ylabel(self._format_axis_label(metric_label, r"mW kg$^{-1}$"))
        formatted_scenario = self._format_scenario_name(scenario_name) if scenario_name else None
        if formatted_scenario:
            base_title = f"individual variations for {metric_label} in {formatted_scenario} scenario"
        else:
            base_title = f"individual variations for {metric_label}"
        title_full = self._get_title_with_phantom(base_title)
        # Don't set title on plot - will be in caption file
        # Place legend below in grid format
        self._place_legend_below(fig, ax, n_items, n_cols=n_cols)

        # Rotate frequency labels (always rotate when x-axis is Frequency)
        plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
        self._adjust_slanted_tick_labels(ax)

        ax.grid(True, alpha=0.3)
        # Set y-axis to start at 0 and go to max + 5%
        y_max = ax.get_ylim()[1]
        ax.set_ylim(0, y_max * 1.05)

        plt.tight_layout()

        metric_safe = metric_column.replace("SAR_", "").replace("psSAR10g_", "").replace("_", "_")
        prefix = "sar" if metric_column.startswith("SAR_") else "pssar10g"
        filename_base = f"{prefix}_line_individual_{metric_safe}_{scenario_name}"
        phantom_name_formatted = self.phantom_name.capitalize() if self.phantom_name else "the phantom"
        caption = f"The line plot shows individual variation lines for each placement/direction/polarization combination for {metric_label} across frequencies in the {self._format_scenario_name(scenario_name)} scenario for {phantom_name_formatted}. Each line represents a specific placement variation."
        filename = self._save_figure(fig, "line", filename_base, title=title_full, caption=caption, dpi=300)

        # Save CSV data
        csv_data = pivot_data.copy()
        csv_data.index.name = "frequency_mhz"
        self._save_csv_data(csv_data, "line", filename_base)
        logging.getLogger("progress").info(
            f"  - Generated individual variation line plot: {filename}",
            extra={"log_type": "success"},
        )

    def plot_sar_line_individual_variations(
        self,
        results_df: pd.DataFrame,
        scenario_name: str,
        metric_column: str = "SAR_head",
    ):
        """Plots individual variation lines for SAR metrics.

        Symmetric counterpart to plot_pssar_line_individual_variations for SAR metrics.

        Args:
            results_df: DataFrame with detailed results including 'placement' column.
            scenario_name: Scenario name for filtering.
            metric_column: Column name for the SAR metric to plot (e.g., 'SAR_head').
        """
        # Delegate to the generic function
        self.plot_pssar_line_individual_variations(results_df, scenario_name, metric_column)
