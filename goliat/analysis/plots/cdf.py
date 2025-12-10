"""CDF (Cumulative Distribution Function) plot generators."""

import logging

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .base import BasePlotter, METRIC_LABELS


class CdfPlotter(BasePlotter):
    """Generates CDF plots for SAR analysis."""

    def plot_cdf(
        self,
        results_df: pd.DataFrame,
        metric: str,
        group_by: str | list[str] | None = None,
        scenario_name: str | None = None,
        frequency_mhz: int | None = None,
    ):
        """Creates CDF plot for a metric with optional aggregation by independent variables.

        Args:
            results_df: DataFrame with simulation results.
            metric: Column name for the metric to plot.
            group_by: Column name(s) to group by for multiple CDF lines (e.g., 'scenario', 'frequency_mhz', 'placement').
                     Can be a single string or list of strings. If None, plots single CDF.
            scenario_name: Optional scenario name for filtering.
            frequency_mhz: Optional frequency for filtering.
        """
        if metric not in results_df.columns:
            logging.getLogger("progress").warning(
                f"Metric '{metric}' not found for CDF plot.",
                extra={"log_type": "warning"},
            )
            return

        plot_df = results_df.copy()

        # Filter by scenario if provided
        if scenario_name:
            plot_df = plot_df[plot_df["scenario"] == scenario_name].copy()

        # Filter by frequency if provided
        if frequency_mhz is not None:
            plot_df = plot_df[plot_df["frequency_mhz"] == frequency_mhz].copy()

        # Remove missing values
        plot_df = plot_df.dropna(subset=[metric])
        plot_df = plot_df[plot_df[metric] > 0]  # Only positive values

        if plot_df.empty:
            return

        fig, ax = plt.subplots(figsize=(3.5, 2.5))  # IEEE single-column width

        # If group_by is specified, create multiple CDF lines
        if group_by:
            if isinstance(group_by, str):
                group_by = [group_by]

            # Get unique combinations of grouping variables
            if all(col in plot_df.columns for col in group_by):
                groups = plot_df.groupby(group_by)

                # Generate colors and linestyles for each group using academic palettes
                n_groups = len(groups)
                colors = self._get_academic_colors(n_groups)
                linestyles = self._get_academic_linestyles(n_groups)

                formatted_labels = []
                handles_list = []
                for idx, ((group_vals, group_df), color) in enumerate(zip(groups, colors)):
                    if isinstance(group_vals, tuple):
                        # Format each value to be human readable
                        formatted_vals = []
                        for col, val in zip(group_by, group_vals):
                            # Format value based on column type
                            if col == "frequency_mhz":
                                formatted_vals.append(f"{val} MHz")
                            elif col == "scenario":
                                val_formatted = (
                                    self._format_organ_name(str(val))
                                    if hasattr(self, "_format_organ_name")
                                    else str(val).replace("_", " ").title()
                                )
                                formatted_vals.append(val_formatted)
                            else:
                                val_formatted = (
                                    self._format_organ_name(str(val))
                                    if hasattr(self, "_format_organ_name")
                                    else str(val).replace("_", " ").title()
                                )
                                formatted_vals.append(val_formatted)
                        label = " | ".join(formatted_vals)
                    else:
                        # Format single value
                        if group_by[0] == "frequency_mhz":
                            label = f"{group_vals} MHz"
                        elif group_by[0] == "scenario":
                            label = (
                                self._format_organ_name(str(group_vals))
                                if hasattr(self, "_format_organ_name")
                                else str(group_vals).replace("_", " ").title()
                            )
                        else:
                            label = (
                                self._format_organ_name(str(group_vals))
                                if hasattr(self, "_format_organ_name")
                                else str(group_vals).replace("_", " ").title()
                            )

                    formatted_labels.append(label)

                    # Calculate CDF
                    sorted_values = np.sort(group_df[metric].values)
                    n = len(sorted_values)
                    y = np.arange(1, n + 1) / n

                    line = ax.plot(sorted_values, y, label=label, linewidth=2, color=color, linestyle=linestyles[idx], alpha=0.8)
                    handles_list.append(line[0])

                # Place legend below plot - use 2 columns for frequencies or when there are 4 items
                from .line import LinePlotter

                line_plotter = LinePlotter(self.plots_dir, self.phantom_name, self.plot_format)
                # Use 2 columns for frequencies, or when there are 4 items for balanced layout
                n_cols = (
                    2
                    if (
                        (isinstance(group_by, list) and "frequency_mhz" in group_by)
                        or (isinstance(group_by, str) and group_by == "frequency_mhz")
                        or len(formatted_labels) == 4
                    )
                    else min(3, len(formatted_labels))
                )
                line_plotter._place_legend_below(
                    fig, ax, len(formatted_labels), n_cols=n_cols, handles=handles_list, labels=formatted_labels
                )

                # Add n= label - use max sample size across groups
                max_n = max(len(group_df) for _, group_df in groups)
                ax.text(
                    0.95,
                    0.95,
                    f"n = {max_n}",
                    transform=ax.transAxes,
                    fontsize=8,
                    verticalalignment="top",
                    horizontalalignment="right",
                    bbox=dict(boxstyle="square,pad=0.4", facecolor="white", edgecolor="black", linewidth=0.5, alpha=1.0),
                )
            else:
                # Fallback: single CDF
                sorted_values = np.sort(plot_df[metric].values)
                n = len(sorted_values)
                y = np.arange(1, n + 1) / n
                ax.plot(sorted_values, y, linewidth=2)
        else:
            # Single CDF
            sorted_values = np.sort(plot_df[metric].values)
            n = len(sorted_values)
            y = np.arange(1, n + 1) / n
            ax.plot(sorted_values, y, linewidth=2)

        metric_label = METRIC_LABELS.get(metric, metric.replace("_", " ").title())
        ax.set_xlabel(f"{metric_label} (mW kg$^{{-1}}$)")
        ax.set_ylabel("Cumulative Probability")

        # xlim should start at 0
        if ax.get_lines():
            x_max = 0
            for line in ax.get_lines():
                x_data = line.get_xdata()
                if len(x_data) > 0:
                    x_max = max(x_max, x_data.max())
            ax.set_xlim(0, x_max * 1.05)

        # For CDF plots, y-axis should start at first y value (not 0) and go to 1.0
        y_min = 0.0  # Default value
        if ax.get_lines():
            # Get all y values from plotted lines
            y_min = 1.0
            for line in ax.get_lines():
                y_data = line.get_ydata()
                if len(y_data) > 0:
                    y_min = min(y_min, y_data[0])
            ax.set_ylim(y_min, 1.0)
        else:
            # Fallback if no lines
            ax.set_ylim(0, 1.0)

        # Add inset for "all scenarios, all frequencies" plots to zoom in on non-outliers
        # Detect if this is an "all_allMHz" plot (scenario_name is None and frequency_mhz is None)
        is_all_all_plot = scenario_name is None and frequency_mhz is None and group_by

        if is_all_all_plot and ax.get_lines() and len(ax.get_lines()) > 1:
            from mpl_toolkits.axes_grid1.inset_locator import inset_axes

            # Get max x value for each line to detect outlier
            line_maxes = []
            for line in ax.get_lines():
                x_data = line.get_xdata()
                if len(x_data) > 0:
                    line_maxes.append((x_data.max(), line))

            if len(line_maxes) >= 2:
                # Sort by max value
                line_maxes.sort(key=lambda x: x[0], reverse=True)
                max_val = line_maxes[0][0]
                second_max = line_maxes[1][0]

                # Check if there's an outlier (max is > 2x the second highest)
                if max_val > second_max * 2.0:
                    # Create inset zoomed to the non-outlier range
                    ax_inset = inset_axes(ax, width="40%", height="40%", loc="lower right", borderpad=1.5)

                    # Replot all lines in the inset with reduced linewidth
                    colors = self._get_academic_colors(len(ax.get_lines()))
                    linestyles = self._get_academic_linestyles(len(ax.get_lines()))
                    for idx, line in enumerate(ax.get_lines()):
                        x_data = line.get_xdata()
                        y_data = line.get_ydata()
                        ax_inset.plot(x_data, y_data, linewidth=1, color=colors[idx], linestyle=linestyles[idx], alpha=0.8)

                    # Set inset limits to zoom on non-outlier data (up to 95th percentile of second highest)
                    # Use second_max * 1.1 as max x to include some margin
                    inset_x_max = second_max * 1.1
                    ax_inset.set_xlim(0, inset_x_max)
                    ax_inset.set_ylim(y_min, 1.0)
                    ax_inset.tick_params(labelsize=6)
                    ax_inset.grid(True, alpha=0.3)
                    ax_inset.set_title("Zoomed (excl. outlier)", fontsize=7, pad=2)

        # Add n= label for single CDF
        if not group_by:
            n_samples = len(plot_df)
            ax.text(
                0.95,
                0.95,
                f"n = {n_samples}",
                transform=ax.transAxes,
                fontsize=8,
                verticalalignment="top",
                horizontalalignment="right",
                bbox=dict(boxstyle="square,pad=0.4", facecolor="white", edgecolor="black", linewidth=0.5, alpha=1.0),
            )

        ax.grid(True, alpha=0.3, which="both")

        # Create title with phantom name - format as sentence without colons or underscores
        metric_label = METRIC_LABELS.get(metric, metric.replace("_", " ").title())
        # Format scenario name to remove underscores
        formatted_scenario = self._format_scenario_name(scenario_name) if scenario_name else None
        # Build title parts - no colon, flow as sentence
        if formatted_scenario:
            if frequency_mhz:
                base_title = f"cumulative distribution function for {metric_label} in {formatted_scenario} scenario at {frequency_mhz} MHz"
            else:
                base_title = f"cumulative distribution function for {metric_label} in {formatted_scenario} scenario"
        else:
            if frequency_mhz:
                base_title = f"cumulative distribution function for {metric_label} at {frequency_mhz} MHz"
            else:
                base_title = f"cumulative distribution function for {metric_label}"
        title_full = self._get_title_with_phantom(base_title)
        # Don't set title on plot - will be in caption file

        plt.tight_layout()

        metric_safe = metric.replace("SAR", "").replace("psSAR10g_", "").replace("_", "_")
        group_suffix = "_".join(group_by) if group_by else "all"
        scenario_suffix = scenario_name or "all"
        freq_suffix = f"{frequency_mhz}MHz" if frequency_mhz else "allMHz"
        filename_base = f"cdf_{metric_safe}_{group_suffix}_{scenario_suffix}_{freq_suffix}"
        # Format group_by for caption - replace underscores and format nicely
        if group_by:
            if isinstance(group_by, str):
                group_by_list = [group_by]
            else:
                group_by_list = group_by
            # Format each group_by item - replace frequency_mhz with frequency, format others
            formatted_groups = []
            for gb in group_by_list:
                if gb == "frequency_mhz":
                    formatted_groups.append("frequency")
                elif gb == "scenario":
                    formatted_groups.append("scenario")
                else:
                    # Format other group_by columns nicely
                    formatted_groups.append(gb.replace("_", " "))
            group_text = ", ".join(formatted_groups)
            group_suffix_text = f"Grouped by {group_text}."
        else:
            group_suffix_text = ""
        phantom_name_formatted = self.phantom_name.capitalize() if self.phantom_name else "the phantom"
        caption = f"The cumulative distribution function (CDF) plot shows the probability distribution of {metric_label} values for {phantom_name_formatted}. {group_suffix_text}"
        filename = self._save_figure(fig, "cdf", filename_base, title=title_full, caption=caption, dpi=300)

        # Save CSV data - save the raw plot data
        csv_data = plot_df[[metric]].copy()
        if group_by:
            if isinstance(group_by, str):
                group_by = [group_by]
            for col in group_by:
                if col in plot_df.columns:
                    csv_data[col] = plot_df[col]
        self._save_csv_data(csv_data, "cdf", filename_base)
        logging.getLogger("progress").info(
            f"  - Generated CDF plot: {filename}",
            extra={"log_type": "success"},
        )
