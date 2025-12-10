"""Power balance plot generators."""

import logging
from typing import cast

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from .base import BasePlotter


class PowerPlotter(BasePlotter):
    """Generates power balance plots for SAR analysis."""

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

    def plot_power_efficiency_trends(
        self,
        results_df: pd.DataFrame,
        scenario_name: str | None = None,
    ):
        """Creates line plot showing antenna efficiency and power component percentages across frequencies.

        Args:
            results_df: DataFrame with power balance columns.
            scenario_name: Optional scenario name for filtering.
        """
        if scenario_name:
            plot_df = results_df[results_df["scenario"] == scenario_name].copy()
        else:
            plot_df = results_df.copy()

        required_cols = ["frequency_mhz", "power_pin_W", "power_rad_W", "power_diel_loss_W", "power_sibc_loss_W"]
        missing_cols = [col for col in required_cols if col not in plot_df.columns]
        if missing_cols:
            logging.getLogger("progress").warning(
                f"Missing columns for power efficiency plot: {missing_cols}",
                extra={"log_type": "warning"},
            )
            return

        # Calculate efficiency and percentages
        plot_df = plot_df.copy()
        plot_df["efficiency"] = (plot_df["power_rad_W"] / plot_df["power_pin_W"]) * 100
        plot_df["diel_loss_pct"] = (plot_df["power_diel_loss_W"] / plot_df["power_pin_W"]) * 100
        plot_df["sibc_loss_pct"] = (plot_df["power_sibc_loss_W"] / plot_df["power_pin_W"]) * 100
        plot_df["rad_pct"] = (plot_df["power_rad_W"] / plot_df["power_pin_W"]) * 100

        # Group by frequency
        freq_summary = (
            plot_df.groupby("frequency_mhz")
            .agg(
                {
                    "efficiency": "mean",
                    "diel_loss_pct": "mean",
                    "sibc_loss_pct": "mean",
                    "rad_pct": "mean",
                }
            )
            .reset_index()
        )

        fig, axes = plt.subplots(2, 1, figsize=(3.5, 4.5))  # IEEE single-column width, taller for 2 subplots

        # Top plot: Efficiency
        ax1 = axes[0]
        markers = self._get_academic_markers(1)
        linestyles = self._get_academic_linestyles(1)
        colors = self._get_academic_colors(1)
        ax1.plot(
            freq_summary["frequency_mhz"],
            freq_summary["efficiency"],
            marker=markers[0],
            linestyle=linestyles[0],
            linewidth=2,
            markersize=4,
            label="Antenna Efficiency",
            color=colors[0],
        )
        ax1.set_xlabel(self._format_axis_label("Frequency", "MHz"))
        ax1.set_ylabel(self._format_axis_label("Efficiency", "%"))
        ax1.set_title("Antenna efficiency vs frequency")  # Subplot title - keep it
        # Set explicit x-axis limits fitted to frequencies
        freq_min = freq_summary["frequency_mhz"].min()
        freq_max = freq_summary["frequency_mhz"].max()
        freq_range = freq_max - freq_min
        ax1.set_xlim(freq_min - freq_range * 0.05, freq_max + freq_range * 0.05)
        # Rotate x-axis labels for real number line frequencies
        plt.setp(ax1.get_xticklabels(), rotation=45, ha="right")
        self._adjust_slanted_tick_labels(ax1)
        ax1.grid(True, alpha=0.3)
        ax1.legend()
        # Set y-axis to go up to 100%
        ax1.set_ylim(0, 100)

        # Bottom plot: Grouped bar chart for better visibility
        ax2 = axes[1]
        # Force x-axis to start at first frequency and end at last frequency
        ax2.set_xlim(freq_min, freq_max)

        # Check if SIBC loss is consistently very small (< 2%)
        sibc_max = freq_summary["sibc_loss_pct"].max()
        if sibc_max < 2.0:
            # Plot SIBC as a separate line on secondary y-axis for visibility
            ax2_twin = ax2.twinx()
            ax2.fill_between(
                freq_summary["frequency_mhz"], 0, freq_summary["diel_loss_pct"], label="Dielectric Loss", alpha=0.7, color="#00008B"
            )  # Dark blue
            ax2.fill_between(
                freq_summary["frequency_mhz"],
                freq_summary["diel_loss_pct"],
                100,
                label="Radiated Power",
                alpha=0.7,
                color="purple",  # Purple instead of green
            )
            # Use distinct markers for SIBC line
            markers = self._get_academic_markers(2)  # Get 2 to pick a different one if needed, or just use index 1
            linestyles = self._get_academic_linestyles(2)
            ax2_twin.plot(
                freq_summary["frequency_mhz"],
                freq_summary["sibc_loss_pct"],
                marker=markers[1] if len(markers) > 1 else "s",
                linestyle=linestyles[1] if len(linestyles) > 1 else "--",
                label="SIBC Loss",
                color="orange",
                linewidth=2,
                markersize=4,
            )
            ax2_twin.set_ylabel("SIBC Loss (%)", color="orange", fontsize=10)
            ax2_twin.tick_params(axis="y", labelcolor="orange")
            ax2_twin.set_ylim(0, max(sibc_max * 1.2, 0.5))
            # Combine legends - move to top right
            lines1, labels1 = ax2.get_legend_handles_labels()
            lines2, labels2 = ax2_twin.get_legend_handles_labels()
            ax2.legend(lines1 + lines2, labels1 + labels2, loc="upper right")
        else:
            # Normal stacked area chart
            ax2.fill_between(freq_summary["frequency_mhz"], 0, freq_summary["diel_loss_pct"], label="Dielectric Loss", alpha=0.7)
            ax2.fill_between(
                freq_summary["frequency_mhz"],
                freq_summary["diel_loss_pct"],
                freq_summary["diel_loss_pct"] + freq_summary["sibc_loss_pct"],
                label="SIBC Loss",
                alpha=0.7,
            )
            ax2.fill_between(
                freq_summary["frequency_mhz"],
                freq_summary["diel_loss_pct"] + freq_summary["sibc_loss_pct"],
                100,
                label="Radiated Power",
                alpha=0.7,
            )
            ax2.legend(loc="upper right")

        ax2.set_xlabel(self._format_axis_label("Frequency", "MHz"))
        ax2.set_ylabel(self._format_axis_label("Percentage of input power", "%"))
        ax2.set_title("Power component breakdown vs frequency")  # Subplot title - keep it
        # Rotate x-axis labels for real number line frequencies
        # Rotate x-axis labels only for actual simulated frequencies
        # Rotate frequency labels (always rotate when x-axis is Frequency)
        plt.setp(ax2.get_xticklabels(), rotation=45, ha="right")
        self._adjust_slanted_tick_labels(ax2)
        ax2.set_ylim(0, 100)  # Already starts at 0, max is 100%
        ax2.grid(True, alpha=0.3)

        # Create title with phantom name
        base_title = "power efficiency trends"
        title_full = self._get_title_with_phantom(base_title, scenario_name)
        # Don't set suptitle - will be in caption file
        plt.tight_layout()

        filename_base = f"power_efficiency_{scenario_name or 'all'}"
        phantom_name_formatted = self.phantom_name.capitalize() if self.phantom_name else "the phantom"
        caption = f"The power efficiency analysis shows antenna efficiency and power component breakdown (dielectric loss, SIBC loss, radiated power) as a function of frequency for the {self._format_scenario_name(scenario_name) if scenario_name else 'all scenarios'} scenario for {phantom_name_formatted}."
        filename = self._save_figure(fig, "power", filename_base, title=title_full, caption=caption, dpi=300)

        # Save CSV data
        csv_data = pd.DataFrame(
            {
                "frequency_mhz": freq_summary["frequency_mhz"],
                "efficiency": freq_summary["efficiency"],
                "dielectric_loss": freq_summary.get("dielectric_loss", np.nan),
                "sibc_loss": freq_summary.get("sibc_loss", np.nan),
                "radiated_power": freq_summary.get("radiated_power", np.nan),
            }
        )
        self._save_csv_data(csv_data, "power", filename_base)
        logging.getLogger("progress").info(
            f"  - Generated power efficiency plot: {filename}",
            extra={"log_type": "success"},
        )

    def plot_power_absorption_distribution(
        self,
        organ_results_df: pd.DataFrame,
        scenario_name: str | None = None,
        frequency_mhz: int | None = None,
    ):
        """Creates pie chart or stacked bar chart showing how total power is distributed across tissue groups.

        Pie charts are kept as-is (not using scienceplots) as they work well with default matplotlib.

        Args:
            organ_results_df: DataFrame with tissue-level data including 'Total Loss' column.
            scenario_name: Optional scenario name for filtering.
            frequency_mhz: Optional frequency for filtering.
        """
        if organ_results_df.empty or "Total Loss" not in organ_results_df.columns:
            logging.getLogger("progress").warning(
                "No 'Total Loss' data available for power absorption plot.",
                extra={"log_type": "warning"},
            )
            return

        plot_df = organ_results_df.copy()
        # Filter out 'All Regions' - it's a whole-body aggregate and would double-count in pie charts
        plot_df = self._filter_all_regions(plot_df, tissue_column="tissue")

        # Filter by frequency if provided
        if frequency_mhz is not None:
            plot_df = plot_df[plot_df["frequency_mhz"] == frequency_mhz].copy()

        # Aggregate by tissue group if available, otherwise by tissue
        if "tissue_group" in plot_df.columns:
            group_loss = plot_df.groupby("tissue_group")["Total Loss"].sum().reset_index()
            group_loss = group_loss[group_loss["Total Loss"] > 0]
        else:
            # Use individual tissues
            group_loss = plot_df.groupby("tissue")["Total Loss"].sum().reset_index()
            group_loss = group_loss[group_loss["Total Loss"] > 0]
            group_loss = group_loss.nlargest(10, "Total Loss")  # Top 10 tissues

        if group_loss.empty:
            return

        # Vertical arrangement: 2 rows, 1 column, variable height
        subplot_height = 2.5  # Height per subplot
        total_height = 2 * subplot_height
        fig, axes = plt.subplots(2, 1, figsize=(3.5, total_height))  # IEEE single-column width, vertical arrangement

        # Pie chart - group tissues <5% into "Others"
        ax1 = axes[0]
        group_loss_copy = group_loss.copy()
        group_loss_copy = group_loss_copy.sort_values("Total Loss", ascending=False)
        total_loss_sum = group_loss_copy["Total Loss"].sum()
        threshold = total_loss_sum * 0.05  # 5% threshold

        # Separate into main groups and others
        main_groups = group_loss_copy[group_loss_copy["Total Loss"] >= threshold]
        others_group = group_loss_copy[group_loss_copy["Total Loss"] < threshold]

        # Combine others if any exist
        if not others_group.empty and len(others_group) > 0:
            others_sum = others_group["Total Loss"].sum()
            others_row = pd.DataFrame({group_loss_copy.columns[0]: ["Others"], "Total Loss": [others_sum]})
            pie_data = pd.concat([main_groups, others_row], ignore_index=True)
        else:
            pie_data = main_groups

        # Generate colors - use Set3 colormap
        n_colors = len(pie_data)
        colors = plt.cm.Set3(np.linspace(0, 1, n_colors))

        wedges, texts, autotexts = ax1.pie(
            pie_data["Total Loss"],
            labels=pie_data.iloc[:, 0],
            autopct="%1.1f%%",
            colors=colors,
            startangle=90,
        )
        ax1.set_title("Power Absorption Distribution (Pie Chart)")

        # Stacked bar chart by frequency
        ax2 = axes[1]
        if frequency_mhz is None and "frequency_mhz" in plot_df.columns:
            # Aggregate across frequencies
            if "tissue_group" in plot_df.columns:
                freq_group_loss = plot_df.groupby(["frequency_mhz", "tissue_group"])["Total Loss"].sum().reset_index()
                freq_group_loss = freq_group_loss.pivot(index="frequency_mhz", columns="tissue_group", values="Total Loss").fillna(0)
            else:
                # Use top tissues
                top_tissues = plot_df.groupby("tissue")["Total Loss"].sum().nlargest(5).index
                plot_df_top = plot_df[plot_df["tissue"].isin(top_tissues)]
                freq_group_loss = plot_df_top.groupby(["frequency_mhz", "tissue"])["Total Loss"].sum().reset_index()
                freq_group_loss = freq_group_loss.pivot(index="frequency_mhz", columns="tissue", values="Total Loss").fillna(0)

            # Use same colors as pie chart - create color mapping
            # Get column order from pie chart (main groups + Others if exists)
            pie_cols = pie_data.iloc[:, 0].tolist()
            color_map = dict(zip(pie_cols, colors[: len(pie_cols)]))

            # Reorder freq_group_loss columns to match pie chart order
            freq_cols = freq_group_loss.columns.tolist()
            # Put pie chart columns first, then others
            ordered_cols = [col for col in pie_cols if col in freq_cols] + [col for col in freq_cols if col not in pie_cols]
            freq_group_loss_ordered = freq_group_loss[ordered_cols]

            # Create color list matching column order
            bar_colors = [color_map.get(col, plt.cm.Set3(0.5)) for col in ordered_cols]

            freq_group_loss_ordered.plot(kind="bar", stacked=True, ax=ax2, color=bar_colors)
            ax2.set_xlabel("Frequency (MHz)")
            ax2.set_ylabel("Total Loss (W)")
            ax2.set_title("Power Absorption Distribution by Frequency (Stacked)")
            # Format legend labels to be human readable and place below subfigure
            legend = ax2.get_legend()
            if legend:
                # Get current labels and format them
                current_labels = [t.get_text() for t in legend.get_texts()]
                formatted_labels = []
                for label in current_labels:
                    # Format tissue group names
                    formatted_label = (
                        self._format_organ_name(label) if hasattr(self, "_format_organ_name") else label.replace("_", " ").title()
                    )
                    formatted_labels.append(formatted_label)
                # Remove old legend and create new one below
                legend.remove()
                legend_new = ax2.legend(
                    title="Tissue Group",
                    labels=formatted_labels,
                    loc="upper center",
                    bbox_to_anchor=(0.5, -0.25),
                    ncol=min(3, len(formatted_labels)),
                    fontsize=8,
                )
                legend_new.get_frame().set_linewidth(0.5)
                legend_new.get_frame().set_edgecolor("black")
                # Adjust subplot to accommodate legend
                fig.subplots_adjust(bottom=0.3)
            else:
                legend_new = ax2.legend(title="Tissue Group", loc="upper center", bbox_to_anchor=(0.5, -0.25))
                legend_new.get_frame().set_linewidth(0.5)
                legend_new.get_frame().set_edgecolor("black")
                fig.subplots_adjust(bottom=0.3)
            # Rotate frequency labels (always rotate when x-axis is Frequency)
            plt.setp(ax2.get_xticklabels(), rotation=45, ha="right")
            self._adjust_slanted_tick_labels(ax2)
        else:
            ax2.text(0.5, 0.5, "Single frequency - use pie chart", ha="center", va="center", transform=ax2.transAxes)
            ax2.set_title("Power Absorption Distribution")

        base_title = "power absorption distribution"
        title_full = self._get_title_with_phantom(base_title, scenario_name)
        plt.tight_layout()

        filename_base = f"power_absorption_{scenario_name or 'all'}_{frequency_mhz or 'all'}MHz"
        phantom_name_formatted = self.phantom_name.capitalize() if self.phantom_name else "the phantom"
        caption = f"The power absorption distribution analysis shows pie chart of total power loss by tissue group and stacked bar chart by frequency for the {self._format_scenario_name(scenario_name) if scenario_name else 'all scenarios'} scenario{f' at {frequency_mhz} MHz' if frequency_mhz else ''} for {phantom_name_formatted}."
        filename = self._save_figure(fig, "power", filename_base, title=title_full, caption=caption, dpi=300)

        # Save CSV data
        csv_data = (
            plot_df[["tissue_group", "Total Loss", "frequency_mhz"]].copy()
            if "tissue_group" in plot_df.columns
            else plot_df[["tissue", "Total Loss", "frequency_mhz"]].copy()
        )
        self._save_csv_data(csv_data, "power", filename_base)
        logging.getLogger("progress").info(
            f"  - Generated power absorption plot: {filename}",
            extra={"log_type": "success"},
        )

    def plot_power_balance_overview(self, results_df: pd.DataFrame):
        """Creates comprehensive power balance overview heatmap.

        Args:
            results_df: DataFrame with power balance columns.
        """
        power_df = self._prepare_power_data(results_df)
        if power_df is None:
            return

        # Group by frequency and scenario
        balance_summary = (
            power_df.groupby(["frequency_mhz", "scenario"])
            .agg(
                {
                    "power_balance_pct": ["mean", "std", "min", "max"],
                    "power_pin_W": "mean",
                    "power_rad_W": "mean",
                    "power_diel_loss_W": "mean",
                    "power_sibc_loss_W": "mean",
                }
            )
            .reset_index()
        )

        # Flatten column names
        balance_summary.columns = ["_".join(col).strip("_") if col[1] else col[0] for col in balance_summary.columns.values]

        # Vertical arrangement: 3 rows, 1 column for heatmaps only
        subplot_height = 2.5  # Height per subplot
        total_height = 3 * subplot_height
        fig, axes = plt.subplots(3, 1, figsize=(3.5, total_height))  # IEEE single-column width, vertical arrangement

        # Balance percentage heatmap - round to one decimal, start at 0, red to green colormap
        balance_pivot = balance_summary.pivot(index="scenario", columns="frequency_mhz", values="power_balance_pct_mean")
        sns.heatmap(balance_pivot, annot=True, fmt=".1f", cmap="RdYlGn", center=100, vmin=0, ax=axes[0], cbar_kws={"label": "Balance (%)"})
        axes[0].set_title("Power Balance Percentage")
        axes[0].set_ylabel("Scenario")
        axes[0].tick_params(which="minor", length=0)  # No minor ticks

        # Input power heatmap - convert to mW, start at 0
        pin_pivot = balance_summary.pivot(index="scenario", columns="frequency_mhz", values="power_pin_W_mean")
        pin_pivot_mW = pin_pivot * 1000  # Convert W to mW
        sns.heatmap(pin_pivot_mW, annot=True, fmt=".1f", cmap="jet", vmin=0, ax=axes[1], cbar_kws={"label": "Power (mW)"})
        axes[1].set_title("Input Power")
        axes[1].set_ylabel("Scenario")
        axes[1].tick_params(which="minor", length=0)  # No minor ticks

        # Radiated power heatmap - convert to mW, start at 0
        rad_pivot = balance_summary.pivot(index="scenario", columns="frequency_mhz", values="power_rad_W_mean")
        rad_pivot_mW = rad_pivot * 1000  # Convert W to mW
        sns.heatmap(rad_pivot_mW, annot=True, fmt=".1f", cmap="jet", vmin=0, ax=axes[2], cbar_kws={"label": "Power (mW)"})
        axes[2].set_title("Radiated Power")
        axes[2].set_xlabel(self._format_axis_label("Frequency", "MHz"))
        axes[2].set_ylabel("Scenario")
        axes[2].tick_params(which="minor", length=0)  # No minor ticks

        base_title = "power balance overview"
        title_full = self._get_title_with_phantom(base_title)
        # Don't set suptitle - will be in caption file
        plt.tight_layout()

        phantom_name_formatted = self.phantom_name.capitalize() if self.phantom_name else "the phantom"
        caption = f"The power balance overview shows heatmaps of power balance percentage, input power, and radiated power across scenarios and frequencies for {phantom_name_formatted}."
        filename = self._save_figure(fig, "power", "power_balance_overview", title=title_full, caption=caption, dpi=300)

        # Now create separate figure for Power Loss Breakdown
        loss_diel_pivot = (
            balance_summary.pivot(index="scenario", columns="frequency_mhz", values="power_diel_loss_W_mean") * 1000
        )  # Convert to mW
        loss_sibc_pivot = (
            balance_summary.pivot(index="scenario", columns="frequency_mhz", values="power_sibc_loss_W_mean") * 1000
        )  # Convert to mW

        if not loss_diel_pivot.empty:
            # Sum across frequencies for each scenario
            loss_diel_sum = loss_diel_pivot.sum(axis=1)
            loss_sibc_sum = loss_sibc_pivot.sum(axis=1)

            # Create DataFrame for stacked bar chart
            loss_combined = pd.DataFrame({"Dielectric": loss_diel_sum, "SIBC": loss_sibc_sum})

            # Create separate figure for Power Loss Breakdown
            fig_loss, ax_loss = plt.subplots(figsize=(3.5, 2.5))  # IEEE single-column width
            loss_combined.plot(kind="bar", stacked=True, ax=ax_loss, color=["#00008B", "orange"])  # Dark blue instead of blue
            ax_loss.set_title("Power Loss Breakdown")
            ax_loss.set_xlabel("Scenario")
            ax_loss.set_ylabel("Power Loss (mW)")
            ax_loss.legend(title="Loss Type", labels=["Dielectric", "SIBC"])
            ax_loss.set_ylim(bottom=0)  # Start at 0
            plt.setp(ax_loss.get_xticklabels(), rotation=45, ha="right")
            self._adjust_slanted_tick_labels(ax_loss)

            base_title_loss = "power loss breakdown"
            title_full_loss = self._get_title_with_phantom(base_title_loss)
            plt.tight_layout()

            phantom_name_formatted_loss = self.phantom_name.capitalize() if self.phantom_name else "the phantom"
            caption_loss = f"The power loss breakdown shows stacked bar chart of dielectric and SIBC power losses summed across frequencies for each scenario for {phantom_name_formatted_loss}."
            filename_loss = self._save_figure(
                fig_loss, "power", "power_loss_breakdown", title=title_full_loss, caption=caption_loss, dpi=300
            )
            logging.getLogger("progress").info(
                "  - Generated power loss breakdown",
                extra={"log_type": "success"},
            )

        # Save CSV data - save the power balance data
        csv_data = power_df.copy() if "power_df" in locals() else pd.DataFrame()
        if not csv_data.empty:
            self._save_csv_data(csv_data, "power", "power_balance_overview")
        logging.getLogger("progress").info(
            "  - Generated power balance overview",
            extra={"log_type": "success"},
        )
