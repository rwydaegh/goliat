"""Penetration depth plot generators."""

import logging

import matplotlib.pyplot as plt
import pandas as pd

from .base import BasePlotter


class PenetrationPlotter(BasePlotter):
    """Generates penetration depth plots for SAR analysis."""

    def plot_penetration_depth_ratio(
        self,
        results_df: pd.DataFrame,
        scenario_name: str | None = None,
        metric_type: str = "psSAR10g",
    ):
        """Creates line plot showing SAR penetration depth ratio (Brain/Skin) vs frequency.

        Args:
            results_df: DataFrame with psSAR10g_brain/psSAR10g_skin or SAR_brain/SAR_skin columns.
            scenario_name: Optional scenario name for filtering.
            metric_type: Type of SAR metric to use ('psSAR10g' or 'SAR').
        """
        brain_col = f"{metric_type}_brain"
        skin_col = f"{metric_type}_skin"
        required_cols = ["frequency_mhz", brain_col, skin_col]
        if not all(col in results_df.columns for col in required_cols):
            logging.getLogger("progress").warning(
                f"Missing columns for {metric_type} penetration depth plot: {brain_col}, {skin_col}.",
                extra={"log_type": "warning"},
            )
            return

        if scenario_name:
            plot_df = results_df[results_df["scenario"] == scenario_name].copy()
        else:
            plot_df = results_df.copy()

        # Calculate ratio
        plot_df = plot_df.copy()
        plot_df["penetration_ratio"] = plot_df[brain_col] / plot_df[skin_col]
        plot_df = plot_df.dropna(subset=["penetration_ratio"])
        plot_df = plot_df[plot_df["penetration_ratio"] > 0]  # Remove invalid ratios

        if plot_df.empty:
            return

        # Group by frequency
        avg_ratio = plot_df.groupby("frequency_mhz")["penetration_ratio"].mean().reset_index()

        fig, ax = plt.subplots(figsize=(3.5, 2.5))  # IEEE single-column width

        linestyles = self._get_academic_linestyles(1)
        markers = self._get_academic_markers(1)
        colors = self._get_academic_colors(1)

        ax.plot(
            avg_ratio["frequency_mhz"],
            avg_ratio["penetration_ratio"],
            marker=markers[0],
            linestyle=linestyles[0],
            color=colors[0],
            linewidth=2,
            markersize=4,
        )

        ax.set_xlabel(self._format_axis_label("Frequency", "MHz"))
        ax.set_ylabel(f"Ratio ({metric_type} Brain / {metric_type} Skin)")
        ax.set_yscale("log")
        # Rotate x-axis labels only for actual simulated frequencies
        # Rotate frequency labels (always rotate when x-axis is Frequency)
        plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
        self._adjust_slanted_tick_labels(ax)
        formatted_scenario = self._format_scenario_name(scenario_name) if scenario_name else None
        if formatted_scenario:
            base_title = f"SAR penetration depth brain to skin {metric_type} ratio versus frequency for {formatted_scenario} scenario"
        else:
            base_title = f"SAR penetration depth brain to skin {metric_type} ratio versus frequency"
        title_full = self._get_title_with_phantom(base_title)
        # Don't set title on plot - will be in caption file
        ax.grid(True, which="both", ls="--", alpha=0.3)

        plt.tight_layout()

        filename_base = f"penetration_ratio_{metric_type}_vs_frequency_{scenario_name or 'all'}"
        phantom_name_formatted = self.phantom_name.capitalize() if self.phantom_name else "the phantom"
        caption = f"The line plot shows the SAR penetration depth ratio (Brain/Skin) for {metric_type} as a function of frequency for the {self._format_scenario_name(scenario_name) if scenario_name else 'all scenarios'} scenario for {phantom_name_formatted}. Higher ratios indicate deeper penetration into brain tissue relative to skin."
        filename = self._save_figure(fig, "penetration", filename_base, title=title_full, caption=caption, dpi=300)

        # Save CSV data
        csv_data = avg_ratio[["frequency_mhz", "penetration_ratio"]].copy()
        self._save_csv_data(csv_data, "penetration", filename_base)
        logging.getLogger("progress").info(
            f"  - Generated penetration depth plot: {filename}",
            extra={"log_type": "success"},
        )
