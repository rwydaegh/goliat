"""Bar chart plot generators."""

import logging

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .base import BasePlotter, LEGEND_LABELS


class BarPlotter(BasePlotter):
    """Generates bar chart plots for SAR analysis."""

    def _detect_broken_axis_needed(self, values: pd.Series | np.ndarray, threshold_ratio: float = 2.0) -> tuple[bool, float, float]:
        """Detects if broken axis is needed when some values are much larger than others.

        Args:
            values: Series or array of values to check.
            threshold_ratio: Ratio threshold (if max/median > threshold, use broken axis).

        Returns:
            Tuple of (needs_break, break_point, max_value).
        """
        values_clean = values.dropna() if isinstance(values, pd.Series) else values[~np.isnan(values)]
        if len(values_clean) < 2:
            return False, 0, values_clean.max() if len(values_clean) > 0 else 0

        max_val = values_clean.max()
        median_val = values_clean.median()

        if median_val > 0 and max_val / median_val > threshold_ratio:
            # Use 90th percentile as break point
            break_point = values_clean.quantile(0.9)
            return True, break_point, max_val

        return False, 0, max_val

    def _add_broken_axis(self, ax, break_point: float, max_value: float):
        """Adds broken axis visualization with curly brackets to y-axis.

        Uses matplotlib's built-in functionality to create a proper broken axis.

        Args:
            ax: Matplotlib axes object.
            break_point: Y-value where the break occurs.
            max_value: Maximum value to show above break.
        """
        # Manual broken axis with curly brackets
        # Set y-axis limits - show up to break_point with some padding
        ax.set_ylim(0, break_point * 1.15)

        # Draw curly bracket break markers on y-axis
        # Position markers near the top of the visible range
        y_marker = break_point * 1.1

        # Draw curly bracket using Path
        from matplotlib.path import Path
        import matplotlib.patches as patches

        # Create curly bracket path (simplified version)
        bracket_height = break_point * 0.05
        bracket_x = -0.02

        # Left side of bracket
        verts = [
            (bracket_x, y_marker - bracket_height / 2),  # Start bottom
            (bracket_x - 0.005, y_marker - bracket_height / 4),  # Curve
            (bracket_x - 0.01, y_marker),  # Middle
            (bracket_x - 0.005, y_marker + bracket_height / 4),  # Curve
            (bracket_x, y_marker + bracket_height / 2),  # End top
        ]
        codes = [Path.MOVETO, Path.CURVE3, Path.CURVE3, Path.CURVE3, Path.CURVE3]
        path = Path(verts, codes)
        patch = patches.PathPatch(
            path, edgecolor="black", facecolor="none", linewidth=1.5, transform=ax.get_yaxis_transform(), clip_on=False
        )
        ax.add_patch(patch)

        # Right side of bracket (mirrored)
        bracket_x_right = 0.02
        verts_right = [
            (bracket_x_right, y_marker - bracket_height / 2),
            (bracket_x_right + 0.005, y_marker - bracket_height / 4),
            (bracket_x_right + 0.01, y_marker),
            (bracket_x_right + 0.005, y_marker + bracket_height / 4),
            (bracket_x_right, y_marker + bracket_height / 2),
        ]
        path_right = Path(verts_right, codes)
        patch_right = patches.PathPatch(
            path_right, edgecolor="black", facecolor="none", linewidth=1.5, transform=ax.get_yaxis_transform(), clip_on=False
        )
        ax.add_patch(patch_right)

        # Add text annotation showing the max value
        ax.text(-0.03, y_marker, f"~{max_value:.1f}", transform=ax.get_yaxis_transform(), ha="right", va="center", fontsize=6, rotation=90)

    def _calculate_boxplot_error_bars(self, scenario_results_df: pd.DataFrame, metric: str, frequencies: list) -> tuple[dict, dict]:
        """Calculates error bars from boxplot statistics (IQR/whiskers).

        Args:
            scenario_results_df: DataFrame with raw data for calculating boxplot stats.
            metric: Column name for the metric.
            frequencies: List of frequencies to calculate for.

        Returns:
            Tuple of (lower_errors, upper_errors) dictionaries keyed by frequency.
        """
        lower_errors = {}
        upper_errors = {}

        for freq in frequencies:
            freq_data = scenario_results_df[scenario_results_df["frequency_mhz"] == freq][metric].dropna()
            if len(freq_data) > 0:
                q1 = freq_data.quantile(0.25)
                q3 = freq_data.quantile(0.75)
                iqr = q3 - q1
                # Whiskers: extend to 1.5*IQR or min/max
                lower_whisker = max(freq_data.min(), q1 - 1.5 * iqr)
                upper_whisker = min(freq_data.max(), q3 + 1.5 * iqr)
                median = freq_data.median()

                lower_errors[freq] = median - lower_whisker
                upper_errors[freq] = upper_whisker - median

        return lower_errors, upper_errors

    def plot_average_sar_bar(
        self, scenario_name: str, avg_results: pd.DataFrame, progress_info: pd.Series, scenario_results_df: pd.DataFrame | None = None
    ):
        """Creates a bar chart of average Head and Trunk SAR by frequency.

        Shows completion progress in x-axis labels. Used for near-field analysis.

        Args:
            scenario_name: Placement scenario name (e.g., 'by_cheek').
            avg_results: DataFrame with average SAR values, indexed by frequency.
            progress_info: Series with completion counts like '5/6' per frequency.
        """
        fig, ax = plt.subplots(figsize=(3.5, 2.5))  # IEEE single-column width

        # Select available columns - exclude SAR_whole_body (same as psSAR10g excludes whole_body)
        sar_cols = []
        legend_labels = []
        sar_metrics_order = ["SAR_head", "SAR_trunk", "SAR_brain", "SAR_skin", "SAR_eyes", "SAR_genitals"]
        for metric in sar_metrics_order:
            if metric in avg_results.columns:
                sar_cols.append(metric)
                # Use trimmed legend labels (remove "SAR" since y-axis already says "SAR")
                legend_labels.append(LEGEND_LABELS.get(metric, metric.replace("SAR_", "").replace("_", " ").title()))

        if sar_cols:
            # Get frequencies for error bar calculation
            if isinstance(avg_results.index, pd.MultiIndex):
                frequencies = sorted(avg_results.index.get_level_values("frequency_mhz").unique())
            else:
                frequencies = sorted(avg_results.index.unique())

            # Calculate error bars from boxplot data if available, otherwise use std
            error_bars_dict = {}
            use_boxplot_errors = False
            stds = None
            if scenario_results_df is not None:
                # Try to calculate boxplot-style error bars
                for metric in sar_cols:
                    if metric in scenario_results_df.columns:
                        lower_errors, upper_errors = self._calculate_boxplot_error_bars(scenario_results_df, metric, frequencies)
                        # Convert to arrays matching avg_results index order
                        lower_arr = []
                        upper_arr = []
                        for freq in frequencies:
                            lower_arr.append(lower_errors.get(freq, 0))
                            upper_arr.append(upper_errors.get(freq, 0))
                        error_bars_dict[metric] = (np.array(lower_arr), np.array(upper_arr))
                        use_boxplot_errors = True

            if not use_boxplot_errors:
                # Fall back to std
                stds = avg_results[sar_cols].std(axis=0) if len(avg_results) > 1 else pd.Series(0, index=sar_cols)
                for metric in sar_cols:
                    error_bars_dict[metric] = stds[metric] if metric in stds.index else 0

            # Plot bars
            if use_boxplot_errors:
                # Plot with asymmetric error bars - need to format as list of tuples
                error_bars_list = []
                for col in sar_cols:
                    if col in error_bars_dict and isinstance(error_bars_dict[col], tuple):
                        error_bars_list.append(error_bars_dict[col])
                    else:
                        error_bars_list.append(None)
                avg_results[sar_cols].plot(
                    kind="bar",
                    ax=ax,
                    color=self._get_academic_colors(len(sar_cols)),
                    yerr=error_bars_list if any(e is not None for e in error_bars_list) else None,
                    capsize=2,
                    error_kw={"elinewidth": 0.8, "capthick": 0.8},
                    legend=False,
                )
            elif len(avg_results) > 1 and stds is not None:
                avg_results[sar_cols].plot(
                    kind="bar",
                    ax=ax,
                    color=self._get_academic_colors(len(sar_cols)),
                    yerr=stds,
                    capsize=2,
                    error_kw={"elinewidth": 0.8, "capthick": 0.8},
                    legend=False,
                )
            else:
                avg_results[sar_cols].plot(kind="bar", ax=ax, color=self._get_academic_colors(len(sar_cols)), legend=False)

            # Handle both single-level and multi-level index
            if isinstance(avg_results.index, pd.MultiIndex):
                # Multi-level index: extract frequency from second level
                progress_labels = [
                    f"{freq}\n({progress_info.get((scenario_name, freq), progress_info.get(freq, '0/0'))})"
                    for scenario, freq in avg_results.index
                ]
            else:
                # Single-level index: assume it's frequency
                progress_labels = [str(freq) for freq in avg_results.index]
            ax.set_xticklabels(progress_labels, rotation=0)

            # Create title with phantom name and formatted scenario
            base_title = "Average normalized SAR for scenario"
            title_full = self._get_title_with_phantom(base_title, scenario_name)
            # Don't set title on plot - will be in caption file
            ax.set_xlabel(self._format_axis_label("Frequency", "MHz"))
            ax.set_ylabel(self._format_axis_label("Normalized SAR", r"mW kg$^{-1}$"))

            # Format legend labels to be human readable (e.g., psSAR10g_eyes -> psSAR10g Eyes)
            formatted_legend_labels = []
            for label in legend_labels:
                # Handle psSAR10g_eyes format - preserve psSAR10g capitalization
                if "pssar10g" in label.lower() or "psSAR10g" in label:
                    # First fix any incorrect capitalization
                    label = label.replace("Pssar10g", "psSAR10g").replace("Pssar", "psSAR")
                    formatted_label = label.replace("psSAR10g", "psSAR10g ").replace("_", " ").title()
                    # Fix capitalization - ensure psSAR10g stays correct
                    formatted_label = formatted_label.replace("Pssar10g", "psSAR10g").replace("Pssar", "psSAR")
                else:
                    formatted_label = (
                        self._format_organ_name(label) if hasattr(self, "_format_organ_name") else label.replace("_", " ").title()
                    )
                formatted_legend_labels.append(formatted_label)

            # Move legend below plot - create handles manually to ensure we get all of them
            from .line import LinePlotter
            import matplotlib.patches as mpatches

            line_plotter = LinePlotter(self.plots_dir, self.phantom_name, self.plot_format)
            # Always create patches manually to ensure we have the correct number and colors
            # This is more reliable than trying to extract from containers which may be incomplete
            handles = []
            # Get colors from academic color palette
            colors = self._get_academic_colors(len(sar_cols))
            for i, col in enumerate(sar_cols):
                # Create a rectangle patch with the color from the academic palette
                patch = mpatches.Patch(facecolor=colors[i], edgecolor="black", linewidth=0.5)
                handles.append(patch)
            # Ensure handles and labels match exactly
            if len(handles) != len(formatted_legend_labels):
                logging.getLogger("progress").warning(
                    f"Mismatch: {len(handles)} handles but {len(formatted_legend_labels)} labels for SAR bar plot. "
                    f"Columns: {sar_cols}, Labels: {formatted_legend_labels}",
                    extra={"log_type": "warning"},
                )
            # Use 2 columns for legend to ensure balanced layout (2x2 for 4 items)
            n_cols = 2 if len(formatted_legend_labels) >= 4 else min(3, len(formatted_legend_labels))
            line_plotter._place_legend_below(
                fig, ax, len(formatted_legend_labels), n_cols=n_cols, handles=handles, labels=formatted_legend_labels
            )

            # Add sample size annotation if available
            if len(avg_results) > 1:
                n_samples = len(avg_results)
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

            # Set y-axis - simple 0 to max + 5%
            y_max = ax.get_ylim()[1]
            ax.set_ylim(0, y_max * 1.05)
        else:
            ax.text(0.5, 0.5, "No SAR data available", ha="center", va="center")
            base_title = "Average normalized SAR for scenario"
            title_full = self._get_title_with_phantom(base_title, scenario_name)
            use_boxplot_errors = False

        plt.tight_layout()
        error_bar_note = (
            "Error bars show boxplot whiskers (IQR-based range)"
            if use_boxplot_errors
            else "Error bars indicate standard deviation when multiple data points are available"
        )
        phantom_name_formatted = self.phantom_name.capitalize() if self.phantom_name else "the phantom"
        caption = f"The bar chart shows average normalized SAR values (Head, Trunk, Brain, Skin, Eyes, Genitals) across frequencies for the {self._format_scenario_name(scenario_name)} scenario for {phantom_name_formatted}. {error_bar_note}."
        self._save_figure(fig, "bar", f"average_sar_bar_{scenario_name}", title=title_full, caption=caption, dpi=300)

        # Save CSV data
        csv_data = avg_results[sar_cols].copy()
        csv_data.index.name = "frequency_mhz"
        self._save_csv_data(csv_data, "bar", f"average_sar_bar_{scenario_name}")

    def plot_average_pssar_bar(
        self, scenario_name: str, avg_results: pd.DataFrame, progress_info: pd.Series, scenario_results_df: pd.DataFrame | None = None
    ):
        """Creates a bar chart of average psSAR10g values by frequency for a scenario.

        Symmetric counterpart to plot_average_sar_bar.

        Args:
            scenario_name: Placement scenario name (e.g., 'by_cheek').
            avg_results: DataFrame with average psSAR10g values, indexed by frequency.
            progress_info: Series with completion counts like '5/6' per frequency.
        """
        fig, ax = plt.subplots(figsize=(3.5, 2.5))  # IEEE single-column width

        # Select all psSAR10g columns for symmetry
        pssar_cols = [col for col in avg_results.columns if col.startswith("psSAR10g")]
        pssar_cols.sort()  # Consistent ordering

        if pssar_cols:
            # Get frequencies for error bar calculation
            if isinstance(avg_results.index, pd.MultiIndex):
                frequencies = sorted(avg_results.index.get_level_values("frequency_mhz").unique())
            else:
                frequencies = sorted(avg_results.index.unique())

            # Calculate error bars from boxplot data if available, otherwise use std
            error_bars_dict = {}
            use_boxplot_errors = False
            stds = None
            if scenario_results_df is not None:
                # Try to calculate boxplot-style error bars
                for metric in pssar_cols:
                    if metric in scenario_results_df.columns:
                        lower_errors, upper_errors = self._calculate_boxplot_error_bars(scenario_results_df, metric, frequencies)
                        # Convert to arrays matching avg_results index order
                        lower_arr = []
                        upper_arr = []
                        for freq in frequencies:
                            lower_arr.append(lower_errors.get(freq, 0))
                            upper_arr.append(upper_errors.get(freq, 0))
                        error_bars_dict[metric] = (np.array(lower_arr), np.array(upper_arr))
                        use_boxplot_errors = True

            if not use_boxplot_errors:
                # Fall back to std
                stds = avg_results[pssar_cols].std(axis=0) if len(avg_results) > 1 else pd.Series(0, index=pssar_cols)
                for metric in pssar_cols:
                    error_bars_dict[metric] = stds[metric] if metric in stds.index else 0

            # Plot bars
            if use_boxplot_errors:
                # Plot with asymmetric error bars - need to format as list of tuples
                error_bars_list = []
                for col in pssar_cols:
                    if col in error_bars_dict and isinstance(error_bars_dict[col], tuple):
                        error_bars_list.append(error_bars_dict[col])
                    else:
                        error_bars_list.append(None)
                avg_results[pssar_cols].plot(
                    kind="bar",
                    ax=ax,
                    color=self._get_academic_colors(len(pssar_cols)),
                    yerr=error_bars_list if any(e is not None for e in error_bars_list) else None,
                    capsize=2,
                    error_kw={"elinewidth": 0.8, "capthick": 0.8},
                    legend=False,
                )
            elif len(avg_results) > 1 and stds is not None:
                avg_results[pssar_cols].plot(
                    kind="bar",
                    ax=ax,
                    color=self._get_academic_colors(len(pssar_cols)),
                    yerr=stds,
                    capsize=2,
                    error_kw={"elinewidth": 0.8, "capthick": 0.8},
                    legend=False,
                )
            else:
                avg_results[pssar_cols].plot(kind="bar", ax=ax, color=self._get_academic_colors(len(pssar_cols)), legend=False)

            # Handle both single-level and multi-level index
            if isinstance(avg_results.index, pd.MultiIndex):
                # Multi-level index: extract frequency from second level
                progress_labels = [
                    f"{freq}\n({progress_info.get((scenario_name, freq), progress_info.get(freq, '0/0'))})"
                    for scenario, freq in avg_results.index
                ]
            else:
                # Single-level index: assume it's frequency
                progress_labels = [str(freq) for freq in avg_results.index]
            ax.set_xticklabels(progress_labels, rotation=0)

            # Create title with phantom name and formatted scenario
            base_title = "Average normalized psSAR10g for scenario"
            title_full = self._get_title_with_phantom(base_title, scenario_name)
            # Don't set title on plot - will be in caption file
            ax.set_xlabel(self._format_axis_label("Frequency", "MHz"))
            ax.set_ylabel(self._format_axis_label("Normalized psSAR10g", r"mW kg$^{-1}$"))
            # Use trimmed legend labels (remove "psSAR10g" since y-axis already says "psSAR10g")
            legend_labels = [LEGEND_LABELS.get(col, col.replace("psSAR10g_", "").replace("_", " ").title()) for col in pssar_cols]

            # Format legend labels to be human readable (e.g., eyes -> Eyes, whole_body -> Whole Body)
            formatted_legend_labels = []
            for label in legend_labels:
                if label is None:
                    continue
                formatted_label = self._format_organ_name(label) if hasattr(self, "_format_organ_name") else label.replace("_", " ").title()
                formatted_legend_labels.append(formatted_label)

            # Move legend below plot - create handles manually to ensure we get all of them
            from .line import LinePlotter
            import matplotlib.patches as mpatches

            line_plotter = LinePlotter(self.plots_dir, self.phantom_name, self.plot_format)
            # Always create patches manually to ensure we have the correct number and colors
            # This is more reliable than trying to extract from containers which may be incomplete
            handles = []
            # Get colors from academic color palette
            colors = self._get_academic_colors(len(pssar_cols))
            for i, col in enumerate(pssar_cols):
                # Create a rectangle patch with the color from the academic palette
                patch = mpatches.Patch(facecolor=colors[i], edgecolor="black", linewidth=0.5)
                handles.append(patch)
            # Ensure handles and labels match exactly
            if len(handles) != len(formatted_legend_labels):
                logging.getLogger("progress").warning(
                    f"Mismatch: {len(handles)} handles but {len(formatted_legend_labels)} labels for psSAR10g bar plot. "
                    f"Columns: {pssar_cols}, Labels: {formatted_legend_labels}",
                    extra={"log_type": "warning"},
                )
            # Use 2 columns for legend to ensure balanced layout (2x2 for 4 items)
            n_cols = 2 if len(formatted_legend_labels) >= 4 else min(3, len(formatted_legend_labels))
            line_plotter._place_legend_below(
                fig, ax, len(formatted_legend_labels), n_cols=n_cols, handles=handles, labels=formatted_legend_labels
            )

            # Add sample size annotation if available
            if len(avg_results) > 1:
                n_samples = len(avg_results)
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

            # Set y-axis - simple 0 to max + 5%
            y_max = ax.get_ylim()[1]
            ax.set_ylim(0, y_max * 1.05)
        else:
            ax.text(0.5, 0.5, "No psSAR10g data available", ha="center", va="center")
            base_title = "Average normalized psSAR10g for scenario"
            title_full = self._get_title_with_phantom(base_title, scenario_name)
            use_boxplot_errors = False

        plt.tight_layout()
        error_bar_note = (
            "Error bars show boxplot whiskers (IQR-based range)"
            if use_boxplot_errors
            else "Error bars indicate standard deviation when multiple data points are available"
        )
        phantom_name_formatted = self.phantom_name.capitalize() if self.phantom_name else "the phantom"
        caption = f"The bar chart shows average normalized psSAR10g values (Eyes, Skin, Brain, Genitals, Whole Body) across frequencies for the {self._format_scenario_name(scenario_name)} scenario for {phantom_name_formatted}. {error_bar_note}."
        self._save_figure(fig, "bar", f"average_pssar_bar_{scenario_name}", title=title_full, caption=caption, dpi=300)

        # Save CSV data
        csv_data = avg_results[pssar_cols].copy()
        csv_data.index.name = "frequency_mhz"
        self._save_csv_data(csv_data, "bar", f"average_pssar_bar_{scenario_name}")

    def plot_whole_body_sar_bar(self, avg_results: pd.DataFrame):
        """Creates a bar chart of average whole-body SAR by frequency."""
        fig, ax = plt.subplots(figsize=(3.5, 2.5))  # IEEE single-column width
        avg_results["SAR_whole_body"].plot(kind="bar", ax=ax, color="skyblue")
        ax.set_xticklabels(avg_results.index.get_level_values("frequency_mhz"), rotation=0)
        title_full = self._get_title_with_phantom("Average whole-body SAR")
        # Don't set title on plot - will be in caption file
        ax.set_xlabel(self._format_axis_label("Frequency", "MHz"))
        ax.set_ylabel(self._format_axis_label("Normalized whole-body SAR", r"mW kg$^{-1}$"))
        # Set y-axis to start at 0 and go to max + 5%
        y_max = ax.get_ylim()[1]
        ax.set_ylim(0, y_max * 1.05)
        plt.tight_layout()
        phantom_name_formatted = self.phantom_name.capitalize() if self.phantom_name else "the phantom"
        caption = f"The bar chart shows average normalized whole-body SAR values across frequencies for {phantom_name_formatted}."
        self._save_figure(fig, "bar", "average_whole_body_sar_bar", title=title_full, caption=caption, dpi=300)

        # Save CSV data
        csv_data = avg_results[["SAR_whole_body"]].copy()
        csv_data.index.name = "frequency_mhz"
        self._save_csv_data(csv_data, "bar", "average_whole_body_sar_bar")
