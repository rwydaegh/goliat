import logging
import os
from typing import cast

import matplotlib.gridspec as gridspec
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.colors import LogNorm

METRIC_LABELS = {
    "SAR_head": "Head SAR",
    "SAR_trunk": "Trunk SAR",
    "SAR_whole_body": "Whole-Body SAR",
    "psSAR10g_eyes": "psSAR10g Eyes",
    "psSAR10g_skin": "psSAR10g Skin",
    "psSAR10g_brain": "psSAR10g Brain",
    "peak_sar": "Peak SAR (10g)",
}
LEGEND_LABELS = {
    "psSAR10g_eyes": "Eyes",
    "psSAR10g_skin": "Skin",
    "psSAR10g_brain": "Brain",
}


class Plotter:
    """Generates publication-ready plots from simulation results.

    Creates bar charts, line plots, boxplots, and heatmaps for SAR analysis.
    All plots are saved to the configured plots directory.
    """

    def __init__(self, plots_dir: str):
        """Sets up the plotter and creates output directory.

        Args:
            plots_dir: Directory where all plots will be saved.
        """
        self.plots_dir = plots_dir
        os.makedirs(self.plots_dir, exist_ok=True)
        logging.getLogger("progress").info(
            f"--- Plots will be saved to '{self.plots_dir}' directory. ---",
            extra={"log_type": "info"},
        )

    def plot_average_sar_bar(self, scenario_name: str, avg_results: pd.DataFrame, progress_info: pd.Series):
        """Creates a bar chart of average Head and Trunk SAR by frequency.

        Shows completion progress in x-axis labels. Used for near-field analysis.

        Args:
            scenario_name: Placement scenario name (e.g., 'by_cheek').
            avg_results: DataFrame with average SAR values, indexed by frequency.
            progress_info: Series with completion counts like '5/6' per frequency.
        """
        fig, ax = plt.subplots(figsize=(12, 7))

        # Select available columns
        sar_cols = []
        legend_labels = []
        if "SAR_head" in avg_results.columns:
            sar_cols.append("SAR_head")
            legend_labels.append("Head SAR")
        if "SAR_trunk" in avg_results.columns:
            sar_cols.append("SAR_trunk")
            legend_labels.append("Trunk SAR")
        if "SAR_whole_body" in avg_results.columns:
            sar_cols.append("SAR_whole_body")
            legend_labels.append("Whole-Body SAR")

        if sar_cols:
            avg_results[sar_cols].plot(kind="bar", ax=ax, colormap="viridis")
            progress_labels = [f"{freq} MHz\n({progress_info.get(freq, '0/0')})" for freq in avg_results.index]
            ax.set_xticklabels(progress_labels, rotation=0)
            ax.set_title(f"Average Normalized SAR for Scenario: {scenario_name}")
            ax.set_xlabel("Frequency (MHz) and Completion Progress")
            ax.set_ylabel("Normalized SAR (mW/kg)")
            ax.legend(legend_labels)
        else:
            ax.text(0.5, 0.5, "No SAR data available", ha="center", va="center")
            ax.set_title(f"Average Normalized SAR for Scenario: {scenario_name}")

        plt.tight_layout()
        fig.savefig(os.path.join(self.plots_dir, f"average_sar_bar_{scenario_name}.png"))
        plt.close(fig)

    def plot_whole_body_sar_bar(self, avg_results: pd.DataFrame):
        """Creates a bar chart of average whole-body SAR by frequency."""
        fig, ax = plt.subplots(figsize=(12, 7))
        avg_results["SAR_whole_body"].plot(kind="bar", ax=ax, color="skyblue")
        ax.set_xticklabels(avg_results.index.get_level_values("frequency_mhz"), rotation=0)
        ax.set_title("Average Whole-Body SAR")
        ax.set_xlabel("Frequency (MHz)")
        ax.set_ylabel("Normalized Whole-Body SAR (mW/kg)")
        plt.tight_layout()
        fig.savefig(os.path.join(self.plots_dir, "average_whole_body_sar_bar.png"))
        plt.close(fig)

    def _prepare_power_data(self, results_df: pd.DataFrame) -> pd.DataFrame | None:
        """Prepares power balance data for plotting.

        Args:
            results_df: DataFrame with all simulation results.

        Returns:
            Filtered DataFrame with power balance data, or None if no data available.
        """
        if "power_balance_pct" not in results_df.columns:
            logging.getLogger("progress").warning(
                "  - No power balance data found, skipping power balance plots",
                extra={"log_type": "warning"},
            )
            return None

        power_df = cast(
            pd.DataFrame,
            results_df[
                [
                    "frequency_mhz",
                    "scenario",
                    "placement",
                    "power_balance_pct",
                    "power_pin_W",
                    "power_diel_loss_W",
                    "power_rad_W",
                    "power_sibc_loss_W",
                ]
            ].copy(),
        )
        power_df = power_df.dropna(subset=["power_balance_pct"])

        if power_df.empty:
            logging.getLogger("progress").warning(
                "  - No valid power balance data found, skipping power balance plots",
                extra={"log_type": "warning"},
            )
            return None

        return power_df

    def _plot_balance_distribution(self, power_df: pd.DataFrame):
        """Plots balance percentage distribution by frequency and scenario.

        Args:
            power_df: DataFrame with power balance data.
        """
        fig, axes = plt.subplots(2, 1, figsize=(14, 10))

        # Top plot: Boxplot of balance by frequency
        ax1 = axes[0]
        if len(power_df["frequency_mhz"].unique()) > 1:
            sns.boxplot(
                data=power_df,
                x="frequency_mhz",
                y="power_balance_pct",
                ax=ax1,
                palette="viridis",
            )
            ax1.axhline(y=100, color="r", linestyle="--", linewidth=2, label="100% (Ideal)")
            ax1.set_title("Power Balance Distribution by Frequency", fontsize=14, fontweight="bold")
            ax1.set_xlabel("Frequency (MHz)")
            ax1.set_ylabel("Power Balance (%)")
            ax1.legend()
            ax1.grid(True, alpha=0.3)
        else:
            # Single frequency - use bar chart
            freq = power_df["frequency_mhz"].iloc[0]
            balance_values = power_df["power_balance_pct"].values
            ax1.bar(range(len(balance_values)), balance_values, color="skyblue", alpha=0.7)
            ax1.axhline(y=100, color="r", linestyle="--", linewidth=2, label="100% (Ideal)")
            ax1.set_title(f"Power Balance Distribution at {freq} MHz", fontsize=14, fontweight="bold")
            ax1.set_xlabel("Simulation Index")
            ax1.set_ylabel("Power Balance (%)")
            ax1.legend()
            ax1.grid(True, alpha=0.3)

        # Bottom plot: Balance by scenario
        ax2 = axes[1]
        if len(power_df["scenario"].unique()) > 1:
            sns.boxplot(
                data=power_df,
                x="scenario",
                y="power_balance_pct",
                ax=ax2,
                hue="scenario",
                palette="Set2",
                legend=False,
            )
            ax2.axhline(y=100, color="r", linestyle="--", linewidth=2, label="100% (Ideal)")
            ax2.set_title("Power Balance Distribution by Scenario", fontsize=14, fontweight="bold")
            ax2.set_xlabel("Scenario")
            ax2.set_ylabel("Power Balance (%)")
            ax2.legend()
            ax2.grid(True, alpha=0.3)
            ax2.tick_params(axis="x", rotation=45)
        else:
            ax2.text(0.5, 0.5, "Single scenario - insufficient data for comparison", ha="center", va="center", transform=ax2.transAxes)
            ax2.set_title("Power Balance by Scenario", fontsize=14, fontweight="bold")

        plt.tight_layout()
        fig.savefig(os.path.join(self.plots_dir, "power_balance_distribution.png"), dpi=150, bbox_inches="tight")
        plt.close(fig)

    def _plot_power_components(self, power_df: pd.DataFrame):
        """Plots power components breakdown as grouped bar charts.

        Args:
            power_df: DataFrame with power balance data.
        """
        power_cols = ["power_pin_W", "power_diel_loss_W", "power_rad_W", "power_sibc_loss_W"]
        available_cols = [col for col in power_cols if col in power_df.columns and bool(power_df[col].notna().any())]

        if len(available_cols) < 2:
            return

        # Only create plot if we have multiple frequencies and scenarios
        if len(power_df["frequency_mhz"].unique()) <= 1 or len(power_df["scenario"].unique()) <= 1:
            return

        # Group by frequency and scenario, calculate means
        summary_power = power_df.groupby(["frequency_mhz", "scenario"])[available_cols].mean().reset_index()

        # Create figure with subplots for each frequency
        frequencies = sorted(power_df["frequency_mhz"].unique())
        n_freqs = len(frequencies)
        n_cols = min(3, n_freqs)
        n_rows = (n_freqs + n_cols - 1) // n_cols

        fig, axes_array = plt.subplots(n_rows, n_cols, figsize=(6 * n_cols, 5 * n_rows))

        # Normalize axes to always be a list
        axes = self._normalize_axes_array(axes_array, n_freqs)

        for idx, freq in enumerate(frequencies):
            if idx >= len(axes):
                break
            ax = axes[idx]

            freq_data = cast(pd.DataFrame, summary_power[summary_power["frequency_mhz"] == freq])
            if freq_data.empty:
                continue

            self._plot_single_frequency_components(ax, freq_data, available_cols, freq)

        # Hide unused subplots
        for idx in range(len(frequencies), len(axes)):
            axes[idx].set_visible(False)

        plt.tight_layout()
        fig.savefig(os.path.join(self.plots_dir, "power_components_breakdown.png"), dpi=150, bbox_inches="tight")
        plt.close(fig)

    def _normalize_axes_array(self, axes_array, n_freqs: int) -> list:
        """Normalizes axes array to always be a list.

        Args:
            axes_array: Axes array from plt.subplots (can be single Axes, 1D array, or 2D array).
            n_freqs: Number of frequencies.

        Returns:
            List of axes.
        """
        if n_freqs == 1:
            return [axes_array]
        elif isinstance(axes_array, np.ndarray):
            if axes_array.ndim == 1:
                return axes_array.tolist()
            else:
                return axes_array.flatten().tolist()
        else:
            return [axes_array]

    def _plot_single_frequency_components(self, ax, freq_data: pd.DataFrame, available_cols: list, freq: int):
        """Plots power components for a single frequency.

        Args:
            ax: Matplotlib axes to plot on.
            freq_data: DataFrame filtered to single frequency.
            available_cols: List of available power column names.
            freq: Frequency value for title.
        """
        x = np.arange(len(freq_data))
        width = 0.2

        for i, col in enumerate(available_cols):
            offset = (i - len(available_cols) / 2) * width + width / 2
            col_data = freq_data[col]
            values = col_data.to_numpy() if isinstance(col_data, pd.Series) else np.asarray(col_data)
            label = col.replace("power_", "").replace("_W", "").replace("_", " ").title()
            ax.bar(x + offset, values, width, label=label)

        ax.set_xlabel("Scenario")
        ax.set_ylabel("Power (W)")
        ax.set_title(f"Power Components at {freq} MHz")
        ax.set_xticks(x)
        ax.set_xticklabels(freq_data["scenario"], rotation=45, ha="right")
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3, axis="y")

    def _plot_balance_heatmap(self, power_df: pd.DataFrame):
        """Plots heatmap of balance by frequency and scenario.

        Args:
            power_df: DataFrame with power balance data.
        """
        if len(power_df["frequency_mhz"].unique()) <= 1 or len(power_df["scenario"].unique()) <= 1:
            return

        pivot_balance = power_df.pivot_table(values="power_balance_pct", index="scenario", columns="frequency_mhz", aggfunc="mean")

        fig, ax = plt.subplots(figsize=(10, 6))
        sns.heatmap(
            pivot_balance,
            annot=True,
            fmt=".1f",
            cmap="RdYlGn",
            vmin=95,
            vmax=105,
            center=100,
            cbar_kws={"label": "Power Balance (%)"},
            ax=ax,
            linewidths=0.5,
        )
        ax.set_title("Average Power Balance by Scenario and Frequency", fontsize=14, fontweight="bold")
        ax.set_xlabel("Frequency (MHz)")
        ax.set_ylabel("Scenario")
        plt.tight_layout()
        fig.savefig(os.path.join(self.plots_dir, "power_balance_heatmap.png"), dpi=150, bbox_inches="tight")
        plt.close(fig)

    def plot_power_balance_overview(self, results_df: pd.DataFrame):
        """Creates comprehensive plots showing power balance across all simulations.

        Generates multiple plots:
        1. Balance percentage distribution (boxplot/bar chart)
        2. Power components breakdown (stacked bar or grouped bar)
        3. Balance vs frequency/scenario heatmap

        Args:
            results_df: DataFrame with all simulation results including power balance columns.
        """
        power_df = self._prepare_power_data(results_df)
        if power_df is None:
            return

        self._plot_balance_distribution(power_df)
        self._plot_power_components(power_df)
        self._plot_balance_heatmap(power_df)

        logging.getLogger("progress").info(
            "  - Power balance plots generated",
            extra={"log_type": "success"},
        )

    def plot_peak_sar_line(self, summary_stats: pd.DataFrame):
        """Plots peak SAR trend across frequencies for far-field analysis."""
        fig, ax = plt.subplots(figsize=(12, 7))
        if "peak_sar" in summary_stats.columns:
            summary_stats["peak_sar"].plot(kind="line", marker="o", ax=ax, color="purple")
            ax.set_title("Average Peak SAR (10g) Across All Tissues")
            ax.set_xlabel("Frequency (MHz)")
            ax.set_ylabel("Normalized Peak SAR (mW/kg)")
            ax.set_xticks(summary_stats.index)
            ax.grid(True, which="both", linestyle="--", linewidth=0.5)
        else:
            ax.text(0.5, 0.5, "No Peak SAR data found", ha="center", va="center")
            ax.set_title("Average Peak SAR (10g) Across All Tissues")
        plt.tight_layout()
        fig.savefig(os.path.join(self.plots_dir, "line_peak_sar_summary.png"))
        plt.close(fig)

    def plot_pssar_line(self, scenario_name: str, avg_results: pd.DataFrame):
        """Plots average psSAR10g trends for tissue groups by frequency.

        Shows how peak spatial-average SAR varies with frequency for eyes,
        skin, and brain groups.

        Args:
            scenario_name: Placement scenario name.
            avg_results: DataFrame with average psSAR10g values.
        """
        fig, ax = plt.subplots(figsize=(12, 7))
        pssar_columns = [col for col in avg_results.columns if col.startswith("psSAR10g")]
        if pssar_columns:
            avg_results[pssar_columns].plot(kind="line", marker="o", ax=ax, colormap="viridis")
            ax.set_title(f"Average Normalized psSAR10g for Scenario: {scenario_name}")
            ax.set_xlabel("Frequency (MHz)")
            ax.set_ylabel("Normalized psSAR10g (mW/kg)")
            ax.legend([label for col in pssar_columns if (label := LEGEND_LABELS.get(col, col)) is not None])
            ax.set_xticks(avg_results.index)
        else:
            ax.text(0.5, 0.5, "No psSAR10g data found", ha="center", va="center")
            ax.set_title(f"Average Normalized psSAR10g for Scenario: {scenario_name}")
        plt.tight_layout()
        fig.savefig(os.path.join(self.plots_dir, f"pssar10g_line_{scenario_name}.png"))
        plt.close(fig)

    def plot_sar_distribution_boxplots(self, scenario_name: str, scenario_results_df: pd.DataFrame):
        """Creates boxplots showing SAR value distributions across placements.

        Generates separate boxplots for Head SAR, Trunk SAR, and each psSAR10g
        metric. Shows spread and outliers for each frequency.

        Args:
            scenario_name: Placement scenario name.
            scenario_results_df: DataFrame with detailed results for all placements.
        """
        pssar_columns = [col for col in scenario_results_df.columns if col.startswith("psSAR10g")]
        sar_metrics_for_boxplot = ["SAR_head", "SAR_trunk", "SAR_whole_body"] + pssar_columns
        for metric in sar_metrics_for_boxplot:
            if not scenario_results_df[metric].dropna().empty:
                fig, ax = plt.subplots(figsize=(12, 7))
                sns.boxplot(
                    data=scenario_results_df,
                    x="frequency_mhz",
                    y=metric,
                    ax=ax,
                    hue="frequency_mhz",
                    palette="viridis",
                    legend=False,
                )
                ax.set_title(f"Distribution of Normalized {METRIC_LABELS.get(metric, metric)} for Scenario: {scenario_name}")
                ax.set_xlabel("Frequency (MHz)")
                ax.set_ylabel("Normalized SAR (mW/kg)")
                plt.tight_layout()
                fig.savefig(os.path.join(self.plots_dir, f"boxplot_{metric}_{scenario_name}.png"))
                plt.close(fig)

    def plot_far_field_distribution_boxplot(self, results_df: pd.DataFrame, metric: str = "SAR_whole_body"):
        """Creates a boxplot showing distribution of a metric across directions/polarizations."""
        if metric not in results_df.columns or results_df[metric].dropna().empty:
            logging.getLogger("progress").warning(
                f"  - WARNING: No data for metric '{metric}' to generate boxplot.",
                extra={"log_type": "warning"},
            )
            return

        fig, ax = plt.subplots(figsize=(12, 7))
        sns.boxplot(
            data=results_df,
            x="frequency_mhz",
            y=metric,
            ax=ax,
            hue="frequency_mhz",
            palette="viridis",
            legend=False,
        )
        ax.set_title(f"Distribution of Normalized {METRIC_LABELS.get(metric, metric)}")
        ax.set_xlabel("Frequency (MHz)")
        ax.set_ylabel("Normalized SAR (mW/kg)")
        plt.tight_layout()
        fig.savefig(os.path.join(self.plots_dir, f"boxplot_{metric}_distribution.png"))
        plt.close(fig)

    def _plot_heatmap(self, fig, ax, data: pd.DataFrame, title: str, cbar: bool = True, cbar_ax=None):
        """Helper that plots a single heatmap with log-scale normalization."""
        sns.heatmap(
            data,
            ax=ax,
            annot=True,
            fmt=".2f",
            cmap="viridis",
            linewidths=0.5,
            norm=LogNorm(vmin=data[data > 0].min().min(), vmax=data.max().max()),
            cbar=cbar,
            cbar_ax=cbar_ax if cbar else None,
        )
        ax.set_title(title, pad=20)
        return ax

    def plot_sar_heatmap(self, organ_df: pd.DataFrame, group_df: pd.DataFrame, tissue_groups: dict):
        """Creates a combined heatmap showing Min/Avg/Max SAR per tissue and frequency.

        Two-panel heatmap: top shows individual tissues with color coding by group,
        bottom shows group summaries. Uses log-scale colormap for better visibility.
        """
        organ_pivot = organ_df.pivot_table(
            index="tissue",
            columns="frequency_mhz",
            values=["min_sar", "avg_sar", "max_sar"],
        )
        organ_pivot = organ_pivot.loc[(organ_pivot > 0.01).any(axis=1)]
        mean_organ_sar = organ_pivot.mean(axis=1).sort_values(ascending=False)
        organ_pivot = organ_pivot.reindex(mean_organ_sar.index)
        organ_pivot = organ_pivot.reorder_levels([1, 0], axis=1)
        metric_order = ["min_sar", "avg_sar", "max_sar"]
        sorted_columns = sorted(organ_pivot.columns, key=lambda x: (x[0], metric_order.index(x[1])))
        organ_pivot = organ_pivot[sorted_columns]

        group_pivot = group_df.pivot_table(index="group", columns="frequency_mhz", values="avg_sar")
        if isinstance(group_pivot, pd.DataFrame) and not group_pivot.empty:
            mean_group_sar = group_pivot.mean(axis=1)
            if isinstance(mean_group_sar, pd.Series):
                mean_group_sar = mean_group_sar.sort_values(ascending=False)
                group_pivot = group_pivot.reindex(mean_group_sar.index)

        if organ_pivot.empty:
            return

        fig = plt.figure(figsize=(24, 12 + len(organ_pivot) * 0.4))
        gs = gridspec.GridSpec(
            2,
            2,
            height_ratios=[len(organ_pivot), len(group_pivot) + 1],
            width_ratios=[0.95, 0.05],
            hspace=0.1,
        )
        ax_organ = fig.add_subplot(gs[0, 0])
        ax_group = fig.add_subplot(gs[1, 0])
        cbar_ax = fig.add_subplot(gs[:, 1])

        ax_organ = self._plot_heatmap(
            fig,
            ax_organ,
            organ_pivot,
            "Min, Avg, and Max SAR (mW/kg) per Tissue",
            cbar=True,
            cbar_ax=cbar_ax,
        )
        ax_organ.set_xlabel("")
        x_labels = [metric.replace("_sar", "") for freq, metric in organ_pivot.columns]
        ax_organ.set_xticks(np.arange(len(x_labels)) + 0.5)
        ax_organ.set_xticklabels(x_labels, rotation=0)
        ax_organ.set_ylabel("Tissue")

        group_colors = {"eyes_group": "r", "skin_group": "g", "brain_group": "b"}
        tissue_to_group = {tissue: group for group, tissues in tissue_groups.items() for tissue in tissues}
        for tick_label in ax_organ.get_yticklabels():
            group = tissue_to_group.get(tick_label.get_text())
            if group in group_colors:
                tick_label.set_color(group_colors[group])

        ax_group = self._plot_heatmap(fig, ax_group, group_pivot, "Organ Group Summary (Avg SAR)", cbar=False)
        ax_group.set_xlabel("Frequency (MHz)")
        ax_group.set_ylabel("")
        for tick_label in ax_group.get_yticklabels():
            tick_label.set_rotation(0)
            tick_label.set_color(group_colors.get(f"{tick_label.get_text().lower()}_group", "black"))

        plt.tight_layout(rect=(0, 0, 0.95, 0.98))
        fig.savefig(os.path.join(self.plots_dir, "heatmap_sar_summary.png"))
        plt.close(fig)

    def plot_peak_sar_heatmap(
        self,
        organ_df: pd.DataFrame,
        group_df: pd.DataFrame,
        tissue_groups: dict,
        value_col: str = "peak_sar_10g_mw_kg",
        title: str = "Peak SAR",
    ):
        """Creates a heatmap for peak SAR values across tissues and frequencies.

        Similar structure to plot_sar_heatmap but focused on peak SAR metrics.
        Shows individual tissues and group summaries in separate panels.

        Args:
            organ_df: DataFrame with organ-level peak SAR data.
            group_df: DataFrame with group-level summaries.
            tissue_groups: Dict mapping groups to tissue lists.
            value_col: Column name containing the peak SAR values.
            title: Title for the plot.
        """
        organ_pivot = organ_df.pivot_table(index="tissue", columns="frequency_mhz", values=value_col)
        organ_pivot = organ_pivot.loc[(organ_pivot > 0.01).any(axis=1)]
        mean_organ_sar = organ_pivot.mean(axis=1).sort_values(ascending=False)
        organ_pivot = organ_pivot.reindex(mean_organ_sar.index)

        group_pivot = group_df.pivot_table(index="group", columns="frequency_mhz", values=value_col)
        if isinstance(group_pivot, pd.DataFrame) and not group_pivot.empty:
            mean_group_sar = group_pivot.mean(axis=1)
            if isinstance(mean_group_sar, pd.Series):
                mean_group_sar = mean_group_sar.sort_values(ascending=False)
                group_pivot = group_pivot.reindex(mean_group_sar.index)

        if organ_pivot.empty:
            return

        fig = plt.figure(figsize=(18, 10 + len(organ_pivot) * 0.3))
        gs = gridspec.GridSpec(
            2,
            2,
            height_ratios=[len(organ_pivot), len(group_pivot) + 1],
            width_ratios=[0.95, 0.05],
            hspace=0.1,
        )
        ax_organ = fig.add_subplot(gs[0, 0])
        ax_group = fig.add_subplot(gs[1, 0])
        cbar_ax = fig.add_subplot(gs[:, 1])

        ax_organ = self._plot_heatmap(
            fig,
            ax_organ,
            organ_pivot,
            f"{title} (mW/kg) per Tissue",
            cbar=True,
            cbar_ax=cbar_ax,
        )
        ax_organ.set_xlabel("")
        ax_organ.set_xticklabels([])
        ax_organ.set_ylabel("Tissue")

        group_colors = {"eyes_group": "r", "skin_group": "g", "brain_group": "b"}
        tissue_to_group = {tissue: group for group, tissues in tissue_groups.items() for tissue in tissues}
        for tick_label in ax_organ.get_yticklabels():
            group = tissue_to_group.get(tick_label.get_text())
            if group in group_colors:
                tick_label.set_color(group_colors[group])

        ax_group = self._plot_heatmap(fig, ax_group, group_pivot, f"Organ Group Summary ({title})", cbar=False)
        ax_group.set_xlabel("Frequency (MHz)")
        ax_group.set_ylabel("")
        for tick_label in ax_group.get_yticklabels():
            tick_label.set_rotation(0)
            tick_label.set_color(group_colors.get(f"{tick_label.get_text().lower()}_group", "black"))

        plt.tight_layout(rect=(0, 0, 0.95, 0.98))
        fig.savefig(os.path.join(self.plots_dir, f"heatmap_{value_col}_summary.png"))
        plt.close(fig)
