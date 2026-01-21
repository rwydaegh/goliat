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

    def plot_far_field_direction_polarization_lines(
        self,
        results_df: pd.DataFrame,
        metric: str = "SAR_whole_body",
        group_by: str = "direction",  # "direction", "polarization", or "both"
    ):
        """Creates line plots showing frequency dependence for far-field direction/polarization.

        This visualization shows how SAR varies with frequency for each direction/polarization
        combination, enabling comparison of frequency-dependent effects.

        Args:
            results_df: DataFrame with 'placement' column containing direction/polarization info.
            metric: SAR metric to plot (default: 'SAR_whole_body').
            group_by: How to group lines - 'direction' (one line per direction, panels for polarization),
                      'polarization' (one line per polarization, panels for direction),
                      or 'both' (all combinations on one plot).
        """
        if metric not in results_df.columns or results_df[metric].dropna().empty:
            logging.getLogger("progress").warning(
                f"  - WARNING: No data for metric '{metric}' for direction/polarization line plot.",
                extra={"log_type": "warning"},
            )
            return

        # Parse placement column to extract direction and polarization
        df = results_df.copy()

        def parse_placement(placement: str) -> tuple[str, str]:
            """Parse placement string like 'environmental_x_pos_theta' to ('From left', 'Theta')."""
            # Direction labels describe where the wave is coming FROM (not propagation direction)
            direction_labels = {
                "x_pos": "From left",
                "x_neg": "From right",
                "y_pos": "From back",
                "y_neg": "From front",
                "z_pos": "From below",
                "z_neg": "From above",
            }
            parts = placement.replace("environmental_", "").split("_")
            if len(parts) >= 3:
                dir_key = f"{parts[0]}_{parts[1]}"
                direction = direction_labels.get(dir_key, f"{parts[0].upper()}{'+' if parts[1] == 'pos' else '-'}")
                pol = "Theta" if parts[2] == "theta" else "Phi"
                return direction, pol
            return placement, "Unknown"

        df[["direction", "polarization"]] = df["placement"].apply(lambda x: pd.Series(parse_placement(x)))

        # Get metric label
        metric_label = METRIC_LABELS.get(metric, metric)

        if group_by == "both":
            # All direction/polarization combinations on one plot
            self._plot_far_field_all_combinations(df, metric, metric_label)
        elif group_by == "direction":
            # One panel per polarization, lines for each direction
            self._plot_far_field_by_polarization(df, metric, metric_label)
        else:  # group_by == "polarization"
            # One panel per direction, lines for each polarization
            self._plot_far_field_by_direction(df, metric, metric_label)

    def _plot_far_field_all_combinations(
        self,
        df: pd.DataFrame,
        metric: str,
        metric_label: str,
    ):
        """Plots all direction/polarization combinations on one plot."""
        # Create combined label
        df["combo"] = df["direction"] + " " + df["polarization"]

        # Pivot to get frequency vs combo
        pivot = df.pivot_table(
            index="frequency_mhz",
            columns="combo",
            values=metric,
            aggfunc="mean",
        )

        if pivot.empty:
            return

        # Sort columns for consistent ordering
        direction_order = ["From left", "From right", "From back", "From front", "From below", "From above"]
        pol_order = ["Theta", "Phi"]
        ordered_cols = []
        for d in direction_order:
            for p in pol_order:
                col = f"{d} {p}"
                if col in pivot.columns:
                    ordered_cols.append(col)
        pivot = pivot[ordered_cols]

        # Calculate dynamic height
        n_items = len(pivot.columns)
        n_cols = 3  # Legend columns
        legend_height = self._calculate_legend_height(n_items, n_cols=n_cols)
        total_height = 3.0 + legend_height

        fig, ax = plt.subplots(figsize=(7.16, total_height))  # Two-column width for many lines

        colors = self._get_academic_colors(len(pivot.columns))
        linestyles = self._get_academic_linestyles(len(pivot.columns))
        markers = self._get_academic_markers(len(pivot.columns))

        for idx, col in enumerate(pivot.columns):
            ax.plot(
                pivot.index,
                pivot[col],
                marker=markers[idx],
                linestyle=linestyles[idx],
                color=colors[idx],
                label=col,
                linewidth=1.0,
                markersize=3,
                alpha=0.8,
            )

        ax.set_xlabel(self._format_axis_label("Frequency", "MHz"))
        ax.set_ylabel(self._format_axis_label(metric_label, r"mW kg$^{-1}$"))
        ax.set_xticks(pivot.index)
        plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
        self._adjust_slanted_tick_labels(ax)
        ax.grid(True, alpha=0.3)

        # Set y-axis to start at 0
        y_max = ax.get_ylim()[1]
        ax.set_ylim(0, y_max * 1.05)

        self._place_legend_below(fig, ax, n_items, n_cols=n_cols)
        plt.tight_layout()

        base_title = f"far-field {metric_label} vs frequency by direction and polarization"
        title_full = self._get_title_with_phantom(base_title)
        phantom_name_formatted = self.phantom_name.capitalize() if self.phantom_name else "the phantom"
        caption = (
            f"The line plot shows normalized {metric_label} values for {phantom_name_formatted} "
            f"across frequencies for each far-field incident direction and polarization combination. "
            f"Each line represents a specific direction (from left/right, front/back, above/below) and polarization (Theta, Phi) configuration."
        )

        filename_base = f"line_direction_polarization_{metric}_all"
        filename = self._save_figure(fig, "line", filename_base, title=title_full, caption=caption, dpi=300)

        # Save CSV
        pivot.index.name = "frequency_mhz"
        self._save_csv_data(pivot, "line", filename_base)

        logging.getLogger("progress").info(
            f"  - Generated direction/polarization line plot: {filename}",
            extra={"log_type": "success"},
        )

    def _plot_far_field_by_polarization(
        self,
        df: pd.DataFrame,
        metric: str,
        metric_label: str,
    ):
        """Creates side-by-side panels: one for Theta, one for Phi, with direction lines."""
        import matplotlib.gridspec as gridspec

        # Get unique polarizations
        polarizations = ["Theta", "Phi"]
        direction_order = ["From left", "From right", "From back", "From front", "From below", "From above"]

        fig = plt.figure(figsize=(7.16, 4.0))  # Slightly taller to accommodate legend
        gs = gridspec.GridSpec(1, 2, wspace=0.3, bottom=0.22)

        colors = self._get_academic_colors(len(direction_order))
        linestyles = self._get_academic_linestyles(len(direction_order))
        markers = self._get_academic_markers(len(direction_order))

        legend_handles = []
        legend_labels = []

        for panel_idx, pol in enumerate(polarizations):
            ax = fig.add_subplot(gs[0, panel_idx])

            pol_df = df[df["polarization"] == pol]
            pivot = pol_df.pivot_table(
                index="frequency_mhz",
                columns="direction",
                values=metric,
                aggfunc="mean",
            )

            # Reorder columns
            ordered_cols = [d for d in direction_order if d in pivot.columns]
            pivot = pivot[ordered_cols]

            for idx, direction in enumerate(ordered_cols):
                (line,) = ax.plot(
                    pivot.index,
                    pivot[direction],
                    marker=markers[idx],
                    linestyle=linestyles[idx],
                    color=colors[idx],
                    linewidth=1.2,
                    markersize=4,
                )
                # Collect legend items from first panel
                if panel_idx == 0:
                    legend_handles.append(line)
                    legend_labels.append(direction)

            ax.set_xlabel(self._format_axis_label("Frequency", "MHz"))
            if panel_idx == 0:
                ax.set_ylabel(self._format_axis_label(metric_label, r"mW kg$^{-1}$"))
            ax.set_title(f"{pol} Polarization", fontsize=10, fontweight="bold")
            ax.set_xticks(pivot.index)
            plt.setp(ax.get_xticklabels(), rotation=45, ha="right", fontsize=7)
            ax.grid(True, alpha=0.3)

            # Set y-axis to start at 0
            y_max = ax.get_ylim()[1]
            ax.set_ylim(0, y_max * 1.05)

        # Add shared legend below both panels
        fig.legend(
            legend_handles,
            legend_labels,
            loc="lower center",
            ncol=len(legend_labels),
            fontsize=8,
            frameon=True,
            fancybox=False,
            edgecolor="black",
            bbox_to_anchor=(0.5, 0.02),
        )

        base_title = f"far-field {metric_label} vs frequency by direction grouped by polarization"
        title_full = self._get_title_with_phantom(base_title)
        phantom_name_formatted = self.phantom_name.capitalize() if self.phantom_name else "the phantom"
        caption = (
            f"The dual-panel line plot shows normalized {metric_label} values for {phantom_name_formatted} "
            f"across frequencies. Left panel shows Theta polarization, right panel shows Phi polarization. "
            f"Each line represents a different incident direction (from left/right, front/back, above/below)."
        )

        filename_base = f"line_direction_polarization_{metric}_by_polarization"
        filename = self._save_figure(fig, "line", filename_base, title=title_full, caption=caption, dpi=300)

        logging.getLogger("progress").info(
            f"  - Generated direction lines by polarization: {filename}",
            extra={"log_type": "success"},
        )

    def _plot_far_field_by_direction(
        self,
        df: pd.DataFrame,
        metric: str,
        metric_label: str,
    ):
        """Creates multi-panel figure: one panel per direction, lines for polarizations."""
        import matplotlib.gridspec as gridspec

        direction_order = ["From left", "From right", "From back", "From front", "From below", "From above"]
        polarizations = ["Theta", "Phi"]

        # 2x3 grid of panels with room for legend
        fig = plt.figure(figsize=(7.16, 5.5))
        gs = gridspec.GridSpec(2, 3, hspace=0.45, wspace=0.3, bottom=0.15)

        colors = self._get_academic_colors(len(polarizations))
        linestyles = self._get_academic_linestyles(len(polarizations))
        markers = self._get_academic_markers(len(polarizations))

        legend_handles = []
        legend_labels = []

        for panel_idx, direction in enumerate(direction_order):
            row = panel_idx // 3
            col = panel_idx % 3
            ax = fig.add_subplot(gs[row, col])

            dir_df = df[df["direction"] == direction]
            pivot = dir_df.pivot_table(
                index="frequency_mhz",
                columns="polarization",
                values=metric,
                aggfunc="mean",
            )

            # Reorder columns
            ordered_cols = [p for p in polarizations if p in pivot.columns]
            if ordered_cols:
                pivot = pivot[ordered_cols]

            for idx, pol in enumerate(ordered_cols):
                (line,) = ax.plot(
                    pivot.index,
                    pivot[pol],
                    marker=markers[idx],
                    linestyle=linestyles[idx],
                    color=colors[idx],
                    linewidth=1.2,
                    markersize=4,
                )
                # Collect legend items from first panel
                if panel_idx == 0:
                    legend_handles.append(line)
                    legend_labels.append(pol)

            ax.set_title(f"Direction: {direction}", fontsize=9, fontweight="bold")
            if row == 1:
                ax.set_xlabel("Freq (MHz)", fontsize=8)
            if col == 0:
                ax.set_ylabel(f"{metric_label[:15]}..." if len(metric_label) > 15 else metric_label, fontsize=8)
            ax.tick_params(labelsize=7)
            ax.set_xticks(pivot.index)
            plt.setp(ax.get_xticklabels(), rotation=45, ha="right", fontsize=6)
            ax.grid(True, alpha=0.3)

            # Set y-axis to start at 0
            y_max = ax.get_ylim()[1]
            ax.set_ylim(0, y_max * 1.05)

        # Add shared legend below all panels
        fig.legend(
            legend_handles,
            legend_labels,
            loc="lower center",
            ncol=len(legend_labels),
            fontsize=8,
            frameon=True,
            fancybox=False,
            edgecolor="black",
            bbox_to_anchor=(0.5, 0.02),
        )

        base_title = f"far-field {metric_label} vs frequency comparing polarizations by direction"
        title_full = self._get_title_with_phantom(base_title)
        phantom_name_formatted = self.phantom_name.capitalize() if self.phantom_name else "the phantom"
        caption = (
            f"The multi-panel line plot shows normalized {metric_label} values for {phantom_name_formatted} "
            f"across frequencies. Each panel represents a different incident direction (from left/right, front/back, above/below). "
            f"The two lines in each panel compare Theta vs Phi polarization."
        )

        filename_base = f"line_direction_polarization_{metric}_by_direction"
        filename = self._save_figure(fig, "line", filename_base, title=title_full, caption=caption, dpi=300)

        logging.getLogger("progress").info(
            f"  - Generated polarization lines by direction: {filename}",
            extra={"log_type": "success"},
        )

    def plot_far_field_direction_polarization_comparison(
        self,
        results_df: pd.DataFrame,
        metrics: list[str] | None = None,
    ):
        """Generates frequency-dependent comparison plots for all direction/polarization combos.

        Creates multiple line plots showing how SAR varies with frequency for different
        direction/polarization combinations.

        Args:
            results_df: DataFrame with 'placement' column containing direction/polarization info.
            metrics: List of metrics to plot. If None, uses common metrics.
        """
        if metrics is None:
            # Include both SAR tissue groups and psSAR10g metrics
            # SAR tissue groups are added during analysis via _add_tissue_group_sar()
            possible_metrics = [
                # Whole-body and peak metrics
                "SAR_whole_body",
                "peak_sar",
                # SAR tissue groups (average SAR per tissue group)
                "SAR_brain",
                "SAR_skin",
                "SAR_eyes",
                "SAR_genitals",
                # psSAR10g metrics (peak spatial-average SAR)
                "psSAR10g_brain",
                "psSAR10g_skin",
                "psSAR10g_eyes",
                "psSAR10g_genitals",
            ]
            metrics = [m for m in possible_metrics if m in results_df.columns and results_df[m].notna().any()]

        if not metrics:
            logging.getLogger("progress").warning(
                "  - WARNING: No valid metrics for direction/polarization comparison.",
                extra={"log_type": "warning"},
            )
            return

        logging.getLogger("progress").info(
            "  - Generating direction/polarization frequency comparison plots...",
            extra={"log_type": "info"},
        )

        for metric in metrics:
            # Generate the "by polarization" view - most useful for comparing directions
            self.plot_far_field_direction_polarization_lines(results_df, metric=metric, group_by="direction")

    def plot_cross_phantom_comparison(
        self,
        all_phantom_data: dict[str, pd.DataFrame],
        metrics: list[str] | None = None,
    ):
        """Plots SAR vs frequency comparing different phantoms.

        Creates line plots showing how SAR varies with frequency for each phantom,
        revealing age/body-size dependent absorption patterns.

        Args:
            all_phantom_data: Dictionary mapping phantom names to their results DataFrames.
            metrics: List of metrics to plot. If None, uses common metrics.
        """
        if not all_phantom_data:
            logging.getLogger("progress").warning(
                "  - WARNING: No phantom data for cross-phantom comparison.",
                extra={"log_type": "warning"},
            )
            return

        if metrics is None:
            # Default metrics - check what's available in first phantom
            first_df = list(all_phantom_data.values())[0]
            possible_metrics = [
                "SAR_whole_body",
                "SAR_brain",
                "SAR_eyes",
                "SAR_skin",
                "SAR_genitals",
            ]
            metrics = [m for m in possible_metrics if m in first_df.columns and first_df[m].notna().any()]

        if not metrics:
            return

        # Phantom display names: simplified (Adult/Child Male/Female)
        phantom_info = {
            "duke": ("Duke", "Adult male"),
            "ella": ("Ella", "Adult female"),
            "eartha": ("Eartha", "Child female"),
            "thelonious": ("Thelonious", "Child male"),
        }

        # Use standard academic colors: black, red, dark blue, purple
        academic_colors = self._get_academic_colors(4)
        phantom_colors = {
            "duke": academic_colors[0],  # black (adult male)
            "ella": academic_colors[2],  # dark blue (adult female)
            "eartha": academic_colors[3],  # purple (child female)
            "thelonious": academic_colors[1],  # red (child male)
        }

        # Use standard academic markers and linestyles
        academic_markers = self._get_academic_markers(4)
        academic_linestyles = self._get_academic_linestyles(4)
        phantom_markers = {
            "duke": academic_markers[0],  # circle
            "ella": academic_markers[1],  # square
            "eartha": academic_markers[2],  # triangle
            "thelonious": academic_markers[3],  # diamond
        }
        phantom_linestyles = {
            "duke": academic_linestyles[0],  # solid
            "ella": academic_linestyles[1],  # dashed
            "eartha": academic_linestyles[2],  # dotted
            "thelonious": academic_linestyles[3],  # dashdot
        }

        for metric in metrics:
            # Create figure
            fig, ax = plt.subplots(figsize=(5, 3.5))

            # Combine data from all phantoms
            for phantom_name, df in all_phantom_data.items():
                if metric not in df.columns or df[metric].isna().all():
                    continue

                # Compute statistics per frequency: mean, 25th, 75th percentile
                freq_stats = df.groupby("frequency_mhz")[metric].agg(["mean", lambda x: x.quantile(0.25), lambda x: x.quantile(0.75)])
                freq_stats.columns = ["mean", "p25", "p75"]

                display_name, description = phantom_info.get(phantom_name.lower(), (phantom_name.capitalize(), ""))
                label = f"{display_name} ({description})" if description else display_name
                color = phantom_colors.get(phantom_name.lower(), "gray")

                # Plot line with markers and linestyle
                ax.plot(
                    freq_stats.index,
                    freq_stats["mean"].values,
                    marker=phantom_markers.get(phantom_name.lower(), "o"),
                    linestyle=phantom_linestyles.get(phantom_name.lower(), "solid"),
                    color=color,
                    label=label,
                    linewidth=1.5,
                    markersize=5,
                )

                # Add 25-75th percentile whiskers (simple error bars)
                ax.errorbar(
                    freq_stats.index,
                    freq_stats["mean"].values,
                    yerr=[freq_stats["mean"] - freq_stats["p25"], freq_stats["p75"] - freq_stats["mean"]],
                    fmt="none",  # No markers, just error bars
                    color=color,
                    capsize=3,
                    capthick=0.7,
                    elinewidth=0.7,
                    alpha=0.8,
                )

            # Format axes
            ax.set_xlabel("Frequency (MHz)", fontsize=9)
            metric_label = METRIC_LABELS.get(metric, metric.replace("_", " ").title())
            ax.set_ylabel(f"{metric_label} (mW/kg)", fontsize=9)
            ax.tick_params(axis="both", labelsize=8)

            # Y-axis starts from 0
            ax.set_ylim(bottom=0)

            # Set x-axis to log scale if frequencies span wide range
            frequencies = list(all_phantom_data.values())[0]["frequency_mhz"].unique()
            if max(frequencies) / min(frequencies) > 5:
                ax.set_xscale("log")
                ax.set_xticks(sorted(frequencies))
                ax.set_xticklabels([str(int(f)) for f in sorted(frequencies)], rotation=45, ha="right")

            ax.grid(True, alpha=0.3, linestyle="--")
            ax.legend(fontsize=7, loc="upper right", frameon=True, fancybox=False, edgecolor="black")

            plt.tight_layout()

            # Save
            filename = f"line_cross_phantom_{metric}"
            title = self._get_title_with_phantom(f"Cross-Phantom Comparison: {metric_label}")
            caption = (
                f"Cross-phantom comparison of {metric_label.lower()} as a function of frequency. "
                f"Lines show means across all incident directions and polarizations. "
                f"Whiskers indicate 25th-75th percentile range. "
                f"Children show approximately 1.5-2× higher absorption than adults."
            )
            self._save_figure(fig, "line", filename, title=title, caption=caption, dpi=300)

        logging.getLogger("progress").info(
            f"  - Generated {len(metrics)} cross-phantom comparison plots",
            extra={"log_type": "info"},
        )

    def plot_polarization_ratio_lines(
        self,
        results_df: pd.DataFrame,
        metrics: list[str] | None = None,
    ):
        """Plots theta/phi polarization ratio vs frequency for each direction.

        Shows how the polarization sensitivity changes with frequency for different
        incident directions. This is unique to far-field analysis.

        Args:
            results_df: DataFrame with placement column containing direction and polarization info.
            metrics: List of metrics to analyze. If None, uses common metrics.
        """
        if results_df.empty:
            return

        # Parse placement to extract direction and polarization
        def parse_placement(placement: str) -> tuple[str | None, str | None]:
            parts = placement.split("_")
            if len(parts) >= 4:
                direction = f"{parts[1]}_{parts[2]}"  # e.g., "x_pos"
                pol = parts[3]  # "theta" or "phi"
                return direction, pol
            return None, None

        df = results_df.copy()
        df[["direction", "polarization"]] = df["placement"].apply(lambda x: pd.Series(parse_placement(x)))
        df = df.dropna(subset=["direction", "polarization"])

        if df.empty:
            return

        if metrics is None:
            possible_metrics = ["SAR_whole_body", "psSAR10g_brain", "psSAR10g_eyes", "psSAR10g_skin", "psSAR10g_genitals"]
            metrics = [m for m in possible_metrics if m in df.columns and df[m].notna().any()]

        if not metrics:
            return

        # Direction display names (human-readable: describes where wave comes FROM)
        direction_names = {
            "x_pos": "From left",
            "x_neg": "From right",
            "y_pos": "From back",
            "y_neg": "From front",
            "z_pos": "From below",
            "z_neg": "From above",
        }

        direction_order = ["x_pos", "x_neg", "y_pos", "y_neg", "z_pos", "z_neg"]
        available_directions = [d for d in direction_order if d in df["direction"].unique()]

        # Use standard academic colors, markers, and linestyles for metrics
        academic_colors = self._get_academic_colors(5)
        academic_markers = self._get_academic_markers(5)
        academic_linestyles = self._get_academic_linestyles(5)
        metrics_list = ["SAR_whole_body", "psSAR10g_brain", "psSAR10g_eyes", "psSAR10g_skin", "psSAR10g_genitals"]
        metric_colors = {m: academic_colors[i] for i, m in enumerate(metrics_list)}
        metric_markers = {m: academic_markers[i] for i, m in enumerate(metrics_list)}
        metric_linestyles = {m: academic_linestyles[i] for i, m in enumerate(metrics_list)}

        # First pass: compute global max ratio across all panels
        global_max_ratio = 0.0
        all_ratios = {}
        for direction in available_directions[:6]:
            dir_df = df[df["direction"] == direction]
            all_ratios[direction] = {}
            for metric in metrics:
                if metric not in dir_df.columns:
                    continue
                pivot = dir_df.pivot_table(values=metric, index="frequency_mhz", columns="polarization", aggfunc="mean")
                if "theta" in pivot.columns and "phi" in pivot.columns:
                    ratio = pivot["theta"] / pivot["phi"]
                    ratio = ratio.dropna()
                    if not ratio.empty:
                        all_ratios[direction][metric] = ratio
                        global_max_ratio = max(global_max_ratio, ratio.max())

        # Add some headroom to max
        y_max = max(global_max_ratio * 1.1, 1.5)

        # Create 2x3 panel figure with more vertical space and room for legend
        fig = plt.figure(figsize=(8, 6))
        gs = fig.add_gridspec(2, 3, hspace=0.45, wspace=0.3, bottom=0.18)

        legend_handles = []
        legend_labels = []

        for panel_idx, direction in enumerate(available_directions[:6]):
            row = panel_idx // 3
            col = panel_idx % 3
            ax = fig.add_subplot(gs[row, col])

            for metric in metrics:
                if direction not in all_ratios or metric not in all_ratios[direction]:
                    continue

                ratio = all_ratios[direction][metric]
                color = metric_colors.get(metric, "gray")
                marker = metric_markers.get(metric, "o")
                linestyle = metric_linestyles.get(metric, "solid")
                label = metric.replace("SAR_", "").replace("psSAR10g_", "").replace("_", " ").title()

                (line,) = ax.plot(
                    ratio.index,
                    ratio.values,
                    marker=marker,
                    linestyle=linestyle,
                    color=color,
                    linewidth=1.0,
                    markersize=3,
                )

                # Collect legend items only once (from first panel)
                if panel_idx == 0:
                    legend_handles.append(line)
                    legend_labels.append(label)

            # Reference line at ratio=1.0
            ax.axhline(y=1.0, color="gray", linestyle="--", linewidth=0.8, alpha=0.7)

            # Formatting
            ax.set_title(direction_names.get(direction, direction), fontsize=9)
            ax.set_xlabel("Frequency (MHz)", fontsize=8)
            if col == 0:
                ax.set_ylabel("Theta/Phi Ratio", fontsize=8)
            ax.tick_params(axis="both", labelsize=7)

            # Y-axis: start from 0, use global max
            ax.set_ylim(0, y_max)

            # Log scale for x-axis
            frequencies = sorted(df["frequency_mhz"].unique())
            if len(frequencies) > 1 and max(frequencies) / min(frequencies) > 5:
                ax.set_xscale("log")
                ax.set_xticks(frequencies)
                ax.set_xticklabels([str(int(f)) for f in frequencies], rotation=45, ha="right", fontsize=6)

            ax.grid(True, alpha=0.3, linestyle="--")

        # Add shared legend below all subplots
        fig.legend(
            legend_handles,
            legend_labels,
            loc="lower center",
            ncol=len(legend_labels),
            fontsize=8,
            frameon=True,
            fancybox=False,
            edgecolor="black",
            bbox_to_anchor=(0.5, 0.02),
        )

        # Save
        filename = "line_polarization_ratio_by_direction"
        title = self._get_title_with_phantom("Polarization Ratio vs Frequency by Direction")
        caption = (
            "Theta/phi polarization ratio as a function of frequency for each incident direction. "
            "Ratio > 1.0 indicates theta polarization gives higher SAR; ratio < 1.0 indicates phi dominates. "
            "The gray dashed line marks the equal polarization reference (ratio = 1.0). "
            "Significant frequency-dependent variations indicate complex polarization sensitivity."
        )
        self._save_figure(fig, "line", filename, title=title, caption=caption, dpi=300)

        logging.getLogger("progress").info(
            "  - Generated polarization ratio line plot",
            extra={"log_type": "info"},
        )
