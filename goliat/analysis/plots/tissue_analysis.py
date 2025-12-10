"""Tissue analysis plot generators."""

import logging

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from mpl_toolkits.axes_grid1.inset_locator import inset_axes

from .base import BasePlotter


class TissueAnalysisPlotter(BasePlotter):
    """Generates tissue analysis plots for SAR analysis."""

    def plot_max_local_vs_pssar10g_scatter(
        self,
        organ_results_df: pd.DataFrame,
        scenario_name: str | None = None,
        frequency_mhz: int | None = None,
    ):
        """Creates scatter plot showing relationship between Max Local SAR and psSAR10g.

        Args:
            organ_results_df: DataFrame with max_local_sar_mw_kg and psSAR10g columns.
            scenario_name: Optional scenario name for filtering.
            frequency_mhz: Optional frequency for filtering.
        """
        # Check for required columns, try alternative names
        if "max_local_sar_mw_kg" not in organ_results_df.columns:
            if "Max. local SAR" in organ_results_df.columns:
                organ_results_df = organ_results_df.rename(columns={"Max. local SAR": "max_local_sar_mw_kg"})

        if "psSAR10g" not in organ_results_df.columns:
            if "peak_sar_10g_mw_kg" in organ_results_df.columns:
                organ_results_df["psSAR10g"] = organ_results_df["peak_sar_10g_mw_kg"]
            elif "Peak Spatial-Average SAR[IEEE/IEC62704-1] (10g)" in organ_results_df.columns:
                organ_results_df["psSAR10g"] = organ_results_df["Peak Spatial-Average SAR[IEEE/IEC62704-1] (10g)"]

        required_cols = ["max_local_sar_mw_kg", "psSAR10g"]
        if not all(col in organ_results_df.columns for col in required_cols):
            logging.getLogger("progress").warning(
                "Missing columns for Max Local SAR vs psSAR10g scatter plot.",
                extra={"log_type": "warning"},
            )
            return

        plot_df = organ_results_df.copy()

        if frequency_mhz is not None:
            plot_df = plot_df[plot_df["frequency_mhz"] == frequency_mhz].copy()

        plot_df = plot_df.dropna(subset=required_cols)
        plot_df = plot_df[(plot_df["max_local_sar_mw_kg"] > 0) & (plot_df["psSAR10g"] > 0)]

        if plot_df.empty:
            return

        # Filter out extreme outliers in Max Local SAR (using iterative ratio method)
        # This removes points where the max value is > 2x the average of the next 30 points
        if len(plot_df) >= 6:
            iteration = 0
            original_count = len(plot_df)

            while len(plot_df) >= 6:
                iteration += 1
                # Sort by Max Local SAR descending
                plot_df = plot_df.sort_values("max_local_sar_mw_kg", ascending=False)

                # Get the top value and the next 30
                top_row = plot_df.iloc[0]
                top_val = top_row["max_local_sar_mw_kg"]

                next_n = plot_df.iloc[1:31]
                avg_next_n = next_n["max_local_sar_mw_kg"].mean()

                if avg_next_n <= 0:
                    break

                ratio = top_val / avg_next_n

                if ratio > 2.0:
                    # Found an outlier - remove the top row
                    plot_df = plot_df.iloc[1:].copy()
                else:
                    # Ratio is acceptable, stop checking
                    break

            new_count = len(plot_df)
            if new_count < original_count:
                logging.getLogger("progress").info(
                    f"  - Filtered {original_count - new_count} extreme outlier(s) using iterative ratio method (>2.0x avg of next 30).",
                    extra={"log_type": "info"},
                )

        if plot_df.empty:
            return

        # Check for outliers and dense clusters
        max_x = plot_df["max_local_sar_mw_kg"].max()
        max_y = plot_df["psSAR10g"].max()

        # Identify dense region (95th percentile)
        x_p95 = plot_df["max_local_sar_mw_kg"].quantile(0.95)
        y_p95 = plot_df["psSAR10g"].quantile(0.95)

        # Set minimum axis values to avoid overplotting at origin
        x_min_val = plot_df["max_local_sar_mw_kg"].quantile(0.01)

        # Create main plot with inset for dense region
        fig = plt.figure(figsize=(3.5, 3.0))  # IEEE single-column width
        ax = fig.add_subplot(111)

        # Color by frequency if available
        if "frequency_mhz" in plot_df.columns and len(plot_df["frequency_mhz"].unique()) > 1:
            scatter_plot = ax.scatter(
                plot_df["max_local_sar_mw_kg"],
                plot_df["psSAR10g"],
                c=plot_df["frequency_mhz"],
                cmap="jet",
                alpha=0.6,
                s=30,
            )
            # Create colorbar with proper positioning to avoid extra subplot
            cbar = plt.colorbar(scatter_plot, ax=ax, pad=0.02)
            cbar.set_label("Frequency (MHz)")
        else:
            ax.scatter(plot_df["max_local_sar_mw_kg"], plot_df["psSAR10g"], alpha=0.6, s=30)

        # Add diagonal reference line (y=x) - limit to reasonable range
        max_val = max(x_p95, y_p95)
        ax.plot([x_min_val, max_val], [x_min_val, max_val], "r--", linewidth=2, label="y=x (No Spatial Averaging)")

        # Set axis limits: start at 0 for SAR values, go to max + 5%
        ax.set_xlim(0, max_x * 1.05)
        ax.set_ylim(0, max_y * 1.05)

        ax.set_xlabel(r"Max Local SAR (mW kg$^{-1}$)")
        ax.set_ylabel(r"psSAR10g (mW kg$^{-1}$)")

        # Create title with phantom name
        base_title = "max local SAR vs psSAR10g"
        title_full = self._get_title_with_phantom(base_title, scenario_name)
        # Don't set title on plot - will be in caption file
        ax.legend()
        ax.grid(True, alpha=0.3)

        # Add inset for dense region if there's significant clustering
        if x_p95 < max_x * 0.5 or y_p95 < max_y * 0.5:
            ax_inset = inset_axes(ax, width="40%", height="40%", loc="upper right", borderpad=2)

            # Filter data for inset (include a bit more than p95)
            inset_limit_x = x_p95 * 1.1
            inset_limit_y = y_p95 * 1.1

            inset_df = plot_df[(plot_df["max_local_sar_mw_kg"] <= inset_limit_x) & (plot_df["psSAR10g"] <= inset_limit_y)]

            if not inset_df.empty:
                if "frequency_mhz" in inset_df.columns and len(inset_df["frequency_mhz"].unique()) > 1:
                    ax_inset.scatter(
                        inset_df["max_local_sar_mw_kg"],
                        inset_df["psSAR10g"],
                        c=inset_df["frequency_mhz"],
                        cmap="jet",
                        alpha=0.6,
                        s=20,
                    )
                else:
                    ax_inset.scatter(inset_df["max_local_sar_mw_kg"], inset_df["psSAR10g"], alpha=0.6, s=20)

            # Reference line in inset
            min_val = 0
            inset_max_ref = min(inset_limit_x, inset_limit_y)
            ax_inset.plot([min_val, inset_max_ref], [min_val, inset_max_ref], "r--", linewidth=1, alpha=0.5)

            # Set limits
            ax_inset.set_xlim(0, inset_limit_x)
            ax_inset.set_ylim(0, inset_limit_y)

            # Ensure 0 is shown as a tick if possible, but rely mainly on limits
            # Manual checking of tick labels can be fragile with tight layouts

            ax_inset.set_xlabel("Max Local SAR", fontsize=8)
            ax_inset.set_ylabel("psSAR10g", fontsize=8)
            ax_inset.tick_params(labelsize=7)
            ax_inset.grid(True, alpha=0.3)
            ax_inset.set_title("Zoomed View\n(95th percentile)", fontsize=8)

        plt.tight_layout()

        filename_base = f"scatter_MaxLocal_vs_psSAR10g_{scenario_name or 'all'}_{frequency_mhz or 'all'}MHz"
        phantom_name_formatted = self.phantom_name.capitalize() if self.phantom_name else "the phantom"
        caption = f"The scatter plot compares Max Local SAR and psSAR10g values for tissues in the {self._format_scenario_name(scenario_name) if scenario_name else 'all scenarios'} scenario{f' at {frequency_mhz} MHz' if frequency_mhz else ''} for {phantom_name_formatted}. The red dashed line represents y=x (no spatial averaging). Points are colored by frequency when multiple frequencies are present."
        filename = self._save_figure(fig, "tissue_analysis", filename_base, title=title_full, caption=caption, dpi=300)

        # Save CSV data - use actual columns that exist
        csv_cols = ["max_local_sar_mw_kg", "psSAR10g"]
        if "frequency_mhz" in plot_df.columns:
            csv_cols.append("frequency_mhz")
        csv_data = plot_df[csv_cols].copy()
        self._save_csv_data(csv_data, "tissue_analysis", filename_base)
        logging.getLogger("progress").info(
            f"  - Generated scatter plot: {filename}",
            extra={"log_type": "success"},
        )

    def plot_tissue_frequency_response(
        self,
        organ_results_df: pd.DataFrame,
        tissue_name: str,
        scenario_name: str | None = None,
    ):
        """Creates line plot showing how a specific tissue responds across frequencies.

        Args:
            organ_results_df: DataFrame with tissue-level data.
            tissue_name: Name of the tissue to plot.
            scenario_name: Optional scenario name for filtering.
        """
        # Skip if trying to plot 'All Regions' - it's not a real tissue
        if tissue_name == "All Regions":
            return

        plot_df = organ_results_df[organ_results_df["tissue"] == tissue_name].copy()

        if plot_df.empty:
            return

        if scenario_name:
            plot_df = plot_df[plot_df["scenario"] == scenario_name].copy()

        if plot_df.empty:
            return

        # Aggregate by frequency
        sar_cols = ["min_local_sar_mw_kg", "mass_avg_sar_mw_kg", "max_local_sar_mw_kg"]
        available_cols = [col for col in sar_cols if col in plot_df.columns]

        if not available_cols:
            # Try alternative column names
            if "Min. local SAR" in plot_df.columns:
                plot_df["min_local_sar_mw_kg"] = plot_df["Min. local SAR"]
                available_cols.append("min_local_sar_mw_kg")
            if "Mass-Averaged SAR" in plot_df.columns:
                plot_df["mass_avg_sar_mw_kg"] = plot_df["Mass-Averaged SAR"]
                available_cols.append("mass_avg_sar_mw_kg")
            if "Max. local SAR" in plot_df.columns:
                plot_df["max_local_sar_mw_kg"] = plot_df["Max. local SAR"]
                available_cols.append("max_local_sar_mw_kg")

        if not available_cols:
            return

        freq_summary = plot_df.groupby("frequency_mhz")[available_cols].mean().reset_index()

        fig, ax = plt.subplots(figsize=(3.5, 2.5))  # IEEE single-column width

        colors = self._get_academic_colors(len(available_cols))
        linestyles = self._get_academic_linestyles(len(available_cols))
        markers = self._get_academic_markers(len(available_cols))

        for idx, col in enumerate(available_cols):
            # Format label properly: remove "_mw_kg", preserve SAR acronym
            label_base = col.replace("_mw_kg", "").replace("_", " ")
            # Capitalize properly, preserving SAR acronym
            label_words = label_base.split()
            label_formatted = []
            for word in label_words:
                if word.upper() == "SAR":
                    label_formatted.append("SAR")
                else:
                    label_formatted.append(word.capitalize())
            label = " ".join(label_formatted)
            ax.plot(
                freq_summary["frequency_mhz"],
                freq_summary[col],
                marker=markers[idx],
                linestyle=linestyles[idx],
                color=colors[idx],
                label=label,
                linewidth=2,
                markersize=4,
            )

        ax.set_xlabel(self._format_axis_label("Frequency", "MHz"))
        ax.set_ylabel(self._format_axis_label("SAR", r"mW kg$^{-1}$"))
        # Rotate x-axis labels for real number line frequencies
        # Rotate x-axis labels only for actual simulated frequencies
        # Rotate frequency labels (always rotate when x-axis is Frequency)
        plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
        self._adjust_slanted_tick_labels(ax)

        # Clean tissue name and create title with phantom name
        tissue_clean = self._clean_tissue_name(tissue_name)
        formatted_scenario = self._format_scenario_name(scenario_name) if scenario_name else None
        if formatted_scenario:
            base_title = f"frequency response for {tissue_clean} in {formatted_scenario} scenario"
        else:
            base_title = f"frequency response for {tissue_clean}"
        title_full = self._get_title_with_phantom(base_title)
        # Don't set title on plot - will be in caption file
        ax.legend()
        ax.grid(True, alpha=0.3)
        # Set y-axis to start at 0 and go to max + 5%
        y_max = ax.get_ylim()[1]
        ax.set_ylim(0, y_max * 1.05)

        plt.tight_layout()

        safe_tissue_name = tissue_name.replace("/", "_").replace(" ", "_")
        filename_base = f"tissue_frequency_response_{safe_tissue_name}_{scenario_name or 'all'}"
        phantom_name_formatted = self.phantom_name.capitalize() if self.phantom_name else "the phantom"
        caption = f"The line plot shows the frequency response of SAR metrics (Min Local SAR, Mass-Averaged SAR, Max Local SAR) for {tissue_clean} in the {self._format_scenario_name(scenario_name) if scenario_name else 'all scenarios'} scenario for {phantom_name_formatted}."
        filename = self._save_figure(fig, "tissue_analysis", filename_base, title=title_full, caption=caption, dpi=300)

        # Save CSV data
        csv_data = freq_summary.copy()
        csv_data.index.name = "frequency_mhz"
        self._save_csv_data(csv_data, "tissue_analysis", filename_base)
        logging.getLogger("progress").info(
            f"  - Generated tissue frequency response: {filename}",
            extra={"log_type": "success"},
        )

    def plot_tissue_mass_volume_distribution(
        self,
        organ_results_df: pd.DataFrame,
        scenario_name: str | None = None,
    ):
        """Creates histograms and scatter plot showing tissue mass and volume distributions.

        Args:
            organ_results_df: DataFrame with 'Total Mass' and 'Total Volume' columns.
            scenario_name: Optional scenario name for filtering.
        """
        required_cols = ["Total Mass", "Total Volume"]
        if not all(col in organ_results_df.columns for col in required_cols):
            logging.getLogger("progress").warning(
                "Missing columns for mass/volume distribution plot.",
                extra={"log_type": "warning"},
            )
            return

        plot_df = organ_results_df.copy()
        # Filter out 'All Regions' - it's a whole-body aggregate, not a real tissue
        plot_df = self._filter_all_regions(plot_df, tissue_column="tissue")
        plot_df = plot_df.dropna(subset=required_cols)
        plot_df = plot_df[(plot_df["Total Mass"] > 0) & (plot_df["Total Volume"] > 0)]

        if plot_df.empty:
            return

        # Aggregate by tissue if multiple placements
        if "placement" in plot_df.columns:
            plot_df = (
                plot_df.groupby("tissue")
                .agg(
                    {
                        "Total Mass": "mean",
                        "Total Volume": "mean",
                    }
                )
                .reset_index()
            )

        # Vertical arrangement: 3 rows, 1 column, variable height
        subplot_height = 2.5  # Height per subplot
        total_height = 3 * subplot_height
        fig, axes = plt.subplots(3, 1, figsize=(3.5, total_height))  # IEEE single-column width, vertical arrangement

        # Histogram of Total Mass - use log-spaced bins for constant bin size on log scale
        mass_min = plot_df["Total Mass"].min()
        mass_max = plot_df["Total Mass"].max()
        # Create logarithmically spaced bins
        mass_bins = np.logspace(np.log10(mass_min), np.log10(mass_max), 31)  # 31 edges = 30 bins
        axes[0].hist(plot_df["Total Mass"], bins=mass_bins, edgecolor="black", alpha=0.7)
        axes[0].set_xscale("log")
        axes[0].set_xlabel("Total Mass (kg)")
        axes[0].set_ylabel("Frequency")
        axes[0].set_title("Distribution of Total Mass")  # Subplot title - keep it
        axes[0].grid(True, alpha=0.3)

        # Histogram of Total Volume - use log-spaced bins for constant bin size on log scale
        vol_min = plot_df["Total Volume"].min()
        vol_max = plot_df["Total Volume"].max()
        # Create logarithmically spaced bins
        vol_bins = np.logspace(np.log10(vol_min), np.log10(vol_max), 31)  # 31 edges = 30 bins
        axes[1].hist(plot_df["Total Volume"], bins=vol_bins, edgecolor="black", alpha=0.7)
        axes[1].set_xscale("log")
        axes[1].set_xlabel("Total Volume (m$^3$)")
        axes[1].set_ylabel("Frequency")
        axes[1].set_title("Distribution of Total Volume")  # Subplot title - keep it
        axes[1].grid(True, alpha=0.3)

        # Scatter: Volume vs Mass
        axes[2].scatter(plot_df["Total Volume"], plot_df["Total Mass"], alpha=0.6, s=30, edgecolors="black", linewidth=0.5)
        axes[2].set_xscale("log")
        axes[2].set_yscale("log")
        axes[2].set_xlabel("Total Volume (m$^3$)")
        axes[2].set_ylabel("Total Mass (kg)")
        axes[2].set_title("Volume vs Mass (Density Analysis)")  # Subplot title - keep it

        # Add reference line for water density (1000 kg m$^{-3}$)
        vol_range = [plot_df["Total Volume"].min(), plot_df["Total Volume"].max()]
        mass_water = [v * 1000 for v in vol_range]
        axes[2].plot(vol_range, mass_water, "r--", linewidth=2, label="Water Density (1000 kg m$^{-3}$)")
        axes[2].legend()
        axes[2].grid(True, alpha=0.3)

        base_title = "tissue mass/volume distribution"
        title_full = self._get_title_with_phantom(base_title, scenario_name)
        # Don't set suptitle - will be in caption file
        plt.tight_layout()

        filename_base = f"distribution_mass_volume_{scenario_name or 'all'}"
        phantom_name_formatted = self.phantom_name.capitalize() if self.phantom_name else "the phantom"
        caption = f"The distribution analysis shows histograms of tissue total mass and total volume (log scale), and a scatter plot of volume vs mass with water density reference line for the {self._format_scenario_name(scenario_name) if scenario_name else 'all scenarios'} scenario for {phantom_name_formatted}."
        filename = self._save_figure(fig, "tissue_analysis", filename_base, title=title_full, caption=caption, dpi=300)

        # Save CSV data
        csv_data = plot_df[["tissue", "Total Mass", "Total Volume"]].copy()
        self._save_csv_data(csv_data, "tissue_analysis", filename_base)
        logging.getLogger("progress").info(
            f"  - Generated mass/volume distribution: {filename}",
            extra={"log_type": "success"},
        )
