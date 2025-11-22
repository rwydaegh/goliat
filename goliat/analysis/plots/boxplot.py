"""Boxplot generators."""

import logging

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from .base import BasePlotter, METRIC_LABELS


class BoxplotPlotter(BasePlotter):
    """Generates boxplot plots for SAR analysis."""

    def _get_boxplot_kwargs(self):
        """Returns standardized kwargs for seaborn boxplot with black lines.

        All boxplots should use these parameters to ensure consistent black line styling
        natively through seaborn, without needing post-processing.

        Returns:
            Dictionary of kwargs for sns.boxplot().
        """
        return {
            "color": "white",  # White boxes so median line is visible
            "linewidth": 1.0,
            "boxprops": dict(facecolor="white", edgecolor="black", linewidth=1.0),
            "flierprops": dict(marker="o", markerfacecolor="white", markeredgecolor="black", markersize=4, markeredgewidth=1.0, alpha=1.0),
            "whiskerprops": dict(color="black", linewidth=1.0),
            "capprops": dict(color="black", linewidth=1.0),
            "medianprops": dict(color="black", linewidth=1.0),
        }

    def plot_sar_distribution_boxplots(self, scenario_name: str, scenario_results_df: pd.DataFrame):
        """Creates boxplots showing SAR value distributions across placements.

        Generates separate boxplots for Head SAR, Trunk SAR, tissue group SAR (brain, skin, eyes),
        and each psSAR10g metric. Shows spread and outliers for each frequency.

        Args:
            scenario_name: Placement scenario name.
            scenario_results_df: DataFrame with detailed results for all placements.
        """
        pssar_columns = [col for col in scenario_results_df.columns if col.startswith("psSAR10g")]
        # Include all SAR metrics for symmetry with psSAR10g
        sar_metrics_for_boxplot = [
            "SAR_head",
            "SAR_trunk",
            "SAR_whole_body",
            "SAR_brain",
            "SAR_skin",
            "SAR_eyes",
            "SAR_genitals",
        ] + pssar_columns
        for metric in sar_metrics_for_boxplot:
            if metric not in scenario_results_df.columns:
                continue
            if not scenario_results_df[metric].dropna().empty:
                fig, ax = plt.subplots(figsize=(3.5, 2.5))  # IEEE single-column width
                sns.boxplot(data=scenario_results_df, x="frequency_mhz", y=metric, ax=ax, **self._get_boxplot_kwargs())
                metric_label = METRIC_LABELS.get(metric, metric)
                base_title = f"distribution of normalized {metric_label} for scenario"
                title_full = self._get_title_with_phantom(base_title, scenario_name)
                # Don't set title on plot - will be in caption file
                ax.set_xlabel(self._format_axis_label("Frequency", "MHz"))
                ax.set_ylabel(self._format_axis_label("Normalized SAR", r"mW kg$^{-1}$"))

                # Add sample size annotation - use max samples per boxplot

                unique_freqs = sorted(scenario_results_df["frequency_mhz"].unique())
                max_n = 0
                for freq in unique_freqs:
                    freq_data = scenario_results_df[scenario_results_df["frequency_mhz"] == freq][metric].dropna()
                    n_freq = len(freq_data)
                    if n_freq > max_n:
                        max_n = n_freq

                if max_n > 0:
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

                # Set y-axis to start at 0 and go to max + 5%
                y_max = ax.get_ylim()[1]
                ax.set_ylim(0, y_max * 1.05)
                plt.tight_layout()

                phantom_name_formatted = self.phantom_name.capitalize() if self.phantom_name else "the phantom"
                caption = f"The boxplot shows the distribution of normalized {metric_label} values across different frequencies for the {self._format_scenario_name(scenario_name)} scenario for {phantom_name_formatted}. Each box spans from the first quartile (Q1) to the third quartile (Q3), with the median line shown inside the box. The whiskers extend to show the range of the data, and points beyond the whiskers are outliers."
                self._save_figure(fig, "boxplot", f"boxplot_{metric}_{scenario_name}", title=title_full, caption=caption, dpi=300)

                # Save CSV data
                csv_data = scenario_results_df[["frequency_mhz", metric]].copy()
                self._save_csv_data(csv_data, "boxplot", f"boxplot_{metric}_{scenario_name}")

    def plot_far_field_distribution_boxplot(self, results_df: pd.DataFrame, metric: str = "SAR_whole_body"):
        """Creates a boxplot showing distribution of a metric across directions/polarizations."""
        if metric not in results_df.columns or results_df[metric].dropna().empty:
            logging.getLogger("progress").warning(
                f"  - WARNING: No data for metric '{metric}' to generate boxplot.",
                extra={"log_type": "warning"},
            )
            return

        fig, ax = plt.subplots(figsize=(3.5, 2.5))  # IEEE single-column width
        sns.boxplot(data=results_df, x="frequency_mhz", y=metric, ax=ax, **self._get_boxplot_kwargs())
        metric_label = METRIC_LABELS.get(metric, metric)
        title_full = self._get_title_with_phantom(f"distribution of normalized {metric_label}")
        # Don't set title on plot - will be in caption file
        ax.set_xlabel(self._format_axis_label("Frequency", "MHz"))
        ax.set_ylabel(self._format_axis_label("Normalized SAR", r"mW kg$^{-1}$"))
        # Set y-axis to start at 0 and go to max + 5%
        y_max = ax.get_ylim()[1]
        ax.set_ylim(0, y_max * 1.05)
        plt.tight_layout()
        phantom_name_formatted = self.phantom_name.capitalize() if self.phantom_name else "the phantom"
        caption = f"The boxplot shows the distribution of normalized {metric_label} values across different frequencies for {phantom_name_formatted}. Each box spans from the first quartile (Q1) to the third quartile (Q3), with the median line shown inside the box. The whiskers extend to show the range of the data, and points beyond the whiskers are outliers."
        self._save_figure(fig, "boxplot", f"boxplot_{metric}_distribution", title=title_full, caption=caption, dpi=300)
