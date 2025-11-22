"""Bubble plot generators."""

import logging
import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .base import BasePlotter


class BubblePlotter(BasePlotter):
    """Generates bubble plots for SAR analysis."""

    def plot_bubble_mass_vs_sar(
        self,
        organ_results_df: pd.DataFrame,
        sar_column: str = "mass_avg_sar_mw_kg",
        scenario_name: str | None = None,
        frequency_mhz: int | None = None,
    ):
        """Creates bubble plot showing how tissue mass affects SAR values.

        Args:
            organ_results_df: DataFrame with columns: ['tissue', 'Total Mass', 'Total Volume',
                          sar_column, 'frequency_mhz']
            sar_column: Column name for SAR values (default: 'mass_avg_sar_mw_kg').
            scenario_name: Optional scenario name for filtering.
            frequency_mhz: Optional frequency for filtering.
        """
        if organ_results_df.empty:
            return

        plot_df = organ_results_df.copy()
        # Filter out 'All Regions' - it's a whole-body aggregate, not a real tissue
        plot_df = self._filter_all_regions(plot_df, tissue_column="tissue")

        # Filter by frequency if provided
        if frequency_mhz is not None:
            plot_df = plot_df[plot_df["frequency_mhz"] == frequency_mhz].copy()

        # Check required columns
        required_cols = ["tissue", "Total Mass", "Total Volume", sar_column]
        missing_cols = [col for col in required_cols if col not in plot_df.columns]
        if missing_cols:
            logging.getLogger("progress").warning(
                f"Missing columns for bubble plot: {missing_cols}",
                extra={"log_type": "warning"},
            )
            return

        # Remove rows with missing data
        plot_df = plot_df.dropna(subset=required_cols)
        plot_df = plot_df[plot_df["Total Mass"] > 0]
        plot_df = plot_df[plot_df[sar_column] > 0]

        if plot_df.empty:
            return

        # Aggregate by tissue (mean across placements if multiple)
        if "placement" in plot_df.columns:
            plot_df = (
                plot_df.groupby("tissue")
                .agg(
                    {
                        "Total Mass": "mean",
                        "Total Volume": "mean",
                        sar_column: "mean",
                        "frequency_mhz": "first",
                    }
                )
                .reset_index()
            )

        # Only create log-scale version on x-axis (removed linear version)
        # Use IEEE single-column width (3.5 inches)
        fig_log, ax_log = plt.subplots(figsize=(3.5, 4.8))  # IEEE single-column width, taller for legend

        # Scale bubble size - use power of 0.75 (between sqrt and linear) for moderate scaling
        volumes_log = plot_df["Total Volume"].values
        vol_min_log, vol_max_log = volumes_log.min(), volumes_log.max()
        if vol_max_log > vol_min_log:
            normalized_volumes_log = (volumes_log - vol_min_log) / (vol_max_log - vol_min_log)
            bubble_sizes_log = np.power(normalized_volumes_log, 0.75) * 50 + 10  # Scale to 10-60 range
        else:
            bubble_sizes_log = np.full(len(volumes_log), 30)  # Default size if all same

        # Scatter plot without colorbar (volume shown by bubble size only)
        ax_log.scatter(
            plot_df[sar_column],
            plot_df["Total Mass"],
            s=bubble_sizes_log,
            c="gray",  # Single color - volume shown by size only
            alpha=0.7,
            edgecolors="black",
            linewidth=0.5,
        )

        ax_log.set_xscale("log")
        ax_log.set_yscale("log")
        # Format SAR column name properly (preserve SAR and psSAR10g acronyms)
        sar_display = sar_column.replace("_mw_kg", "").replace("_", " ")
        # Capitalize properly, preserving SAR and psSAR10g acronyms
        sar_words = sar_display.split()
        sar_formatted = []
        for word in sar_words:
            word_lower = word.lower()
            # Check for psSAR10g in any capitalization variation and fix it
            if "pssar10g" in word_lower:
                # Replace any variation (pssar10g, Pssar10g, PSSAR10G, etc.) with psSAR10g
                sar_formatted.append("psSAR10g")
            elif word.upper() == "SAR":
                sar_formatted.append("SAR")
            else:
                sar_formatted.append(word.capitalize())
        sar_display_final = " ".join(sar_formatted)
        # Final safety check: replace any incorrect psSAR10g capitalization in the final string
        sar_display_final = sar_display_final.replace("Pssar10g", "psSAR10g").replace("PSSAR10g", "psSAR10g").replace("Pssar", "psSAR")
        ax_log.set_xlabel(f"{sar_display_final} (mW kg$^{{-1}}$)")
        ax_log.set_ylabel("Total Mass (kg)")

        # Add extra space to x-axis max value for label visibility
        x_min, x_max = ax_log.get_xlim()
        ax_log.set_xlim(x_min, x_max * 1.15)  # Add 15% extra space on right

        ax_log.grid(True, alpha=0.3)

        # Add bubble size legend with updated scaling
        volumes_legend = plot_df["Total Volume"].values
        vol_min_legend, vol_max_legend = volumes_legend.min(), volumes_legend.max()
        if vol_max_legend > vol_min_legend:
            # Use quantiles for legend sizes
            q25 = plot_df["Total Volume"].quantile(0.25)
            q75 = plot_df["Total Volume"].quantile(0.75)
            vol_max_legend_val = plot_df["Total Volume"].max()

            # Normalize and apply power scaling
            def scale_volume(v):
                normalized = (v - vol_min_legend) / (vol_max_legend - vol_min_legend) if vol_max_legend > vol_min_legend else 0.5
                return np.power(normalized, 0.75) * 50 + 10

            sizes_for_legend = [scale_volume(q25), scale_volume(q75), scale_volume(vol_max_legend_val)]
            labels_for_legend = [f"{q25 * 1e6:.1e} m$^3$", f"{q75 * 1e6:.1e} m$^3$", f"{vol_max_legend_val * 1e6:.1e} m$^3$"]
        else:
            sizes_for_legend = [30]
            labels_for_legend = [f"{vol_min_legend * 1e6:.1e} m$^3$"]

        legend_elements_log = [
            plt.scatter([], [], s=s, c="gray", alpha=0.7, edgecolors="black", linewidth=0.5, label=label)
            for s, label in zip(sizes_for_legend, labels_for_legend)
        ]
        # Place legend below the plot
        legend_log = ax_log.legend(
            handles=legend_elements_log,
            title="Bubble Size (Volume)",
            loc="upper center",
            bbox_to_anchor=(0.5, -0.15),
            ncol=len(legend_elements_log),
            fontsize=8,
            frameon=True,
            fancybox=False,
            shadow=False,
            edgecolor="black",
            facecolor="white",
            framealpha=1.0,
        )
        legend_log.get_frame().set_linewidth(0.5)
        # Adjust figure to accommodate legend
        fig_log.subplots_adjust(bottom=0.2)

        # Label ALL tissues/organ with smaller fontsize
        for _, row in plot_df.iterrows():
            tissue_clean = self._format_organ_name(row["tissue"])
            ax_log.annotate(
                tissue_clean,
                (row[sar_column], row["Total Mass"]),
                fontsize=5,  # Reduced from 6 to 5
                alpha=0.8,
                textcoords="offset points",
                xytext=(3, 3),
                ha="left",
                bbox=dict(boxstyle="square,pad=0.2", facecolor="white", alpha=0.7, edgecolor="gray", linewidth=0.3),  # No rounded corners
            )

        plt.tight_layout()

        # Create safe filename from sar_column
        sar_name_safe = sar_column.replace("_mw_kg", "").replace("_", "_")
        filename_base_log = f"bubble_mass_vs_{sar_name_safe}_{scenario_name or 'all'}_{frequency_mhz or 'all'}MHz_log"

        # Remove title from plot - will be in caption file
        ax_log.set_title("")  # Remove title

        base_title_log = "Tissue Mass vs SAR Bubble Plot (Log Scale)"
        title_full_log = self._get_title_with_phantom(base_title_log, scenario_name)
        phantom_name_formatted = self.phantom_name.capitalize() if self.phantom_name else "the phantom"
        caption_log = f"The bubble plot shows tissue mass vs {sar_display_final} with bubble size proportional to tissue volume (log scale on both axes) for the {self._format_scenario_name(scenario_name) if scenario_name else 'all scenarios'} scenario{f' at {frequency_mhz} MHz' if frequency_mhz else ''} for {phantom_name_formatted}."

        filename_log = self._save_figure(fig_log, "bubble", filename_base_log, title=title_full_log, caption=caption_log, dpi=300)

        # Save CSV data
        csv_data = plot_df[["tissue", "Total Mass", "Total Volume", sar_column, "frequency_mhz"]].copy()
        self._save_csv_data(csv_data, "bubble", filename_base_log)
        logging.getLogger("progress").info(
            f"  - Generated bubble plot (log scale): {filename_log}",
            extra={"log_type": "success"},
        )

    def plot_bubble_mass_vs_sar_interactive(
        self,
        organ_results_df: pd.DataFrame,
        sar_column: str = "mass_avg_sar_mw_kg",
        scenario_name: str | None = None,
    ):
        """Creates an interactive bubble plot (plotly) with common axis limits across frequencies.

        Uses Plotly for interactive visualization (not affected by scienceplots).

        Args:
            organ_results_df: DataFrame with columns: ['tissue', 'Total Mass', 'Total Volume',
                          sar_column, 'frequency_mhz', 'placement']
            sar_column: Column name for SAR values (default: 'mass_avg_sar_mw_kg').
            scenario_name: Optional scenario name for filtering.
        """
        try:
            import plotly.graph_objects as go
            from plotly.subplots import make_subplots
        except ImportError:
            logging.getLogger("progress").warning(
                "Plotly not available. Skipping interactive bubble plot. Install with: pip install plotly",
                extra={"log_type": "warning"},
            )
            return

        if organ_results_df.empty:
            return

        plot_df = organ_results_df.copy()
        # Filter out 'All Regions'
        plot_df = self._filter_all_regions(plot_df, tissue_column="tissue")

        if scenario_name:
            plot_df = plot_df[plot_df["scenario"] == scenario_name].copy()

        # Check required columns
        required_cols = ["tissue", "Total Mass", "Total Volume", sar_column, "frequency_mhz"]
        missing_cols = [col for col in required_cols if col not in plot_df.columns]
        if missing_cols:
            logging.getLogger("progress").warning(
                f"Missing columns for interactive bubble plot: {missing_cols}",
                extra={"log_type": "warning"},
            )
            return

        # Remove rows with missing data
        plot_df = plot_df.dropna(subset=required_cols)
        plot_df = plot_df[plot_df["Total Mass"] > 0]
        plot_df = plot_df[plot_df[sar_column] > 0]

        if plot_df.empty:
            return

        # Get common axis limits across all frequencies
        x_min = plot_df[sar_column].min()
        x_max = plot_df[sar_column].max()
        y_min = plot_df["Total Mass"].min()
        y_max = plot_df["Total Mass"].max()

        # Format SAR column name properly (preserve SAR and psSAR10g acronyms)
        sar_display = sar_column.replace("_mw_kg", "").replace("_", " ")
        # Capitalize properly, preserving SAR and psSAR10g acronyms
        sar_words = sar_display.split()
        sar_formatted = []
        for word in sar_words:
            word_lower = word.lower()
            # Check for psSAR10g in any capitalization variation and fix it
            if "pssar10g" in word_lower:
                # Replace any variation (pssar10g, Pssar10g, PSSAR10G, etc.) with psSAR10g
                sar_formatted.append("psSAR10g")
            elif word.upper() == "SAR":
                sar_formatted.append("SAR")
            else:
                sar_formatted.append(word.capitalize())
        sar_display_final = " ".join(sar_formatted)
        # Final safety check: replace any incorrect psSAR10g capitalization in the final string
        sar_display_final = sar_display_final.replace("Pssar10g", "psSAR10g").replace("PSSAR10g", "psSAR10g").replace("Pssar", "psSAR")

        # Get unique frequencies
        frequencies = sorted(plot_df["frequency_mhz"].unique())

        # Create subplots - one per frequency
        n_freqs = len(frequencies)
        cols = min(3, n_freqs)
        rows = (n_freqs + cols - 1) // cols

        fig = make_subplots(
            rows=rows,
            cols=cols,
            subplot_titles=[f"{freq} MHz" for freq in frequencies],
            horizontal_spacing=0.1,
            vertical_spacing=0.12,
        )

        # Color scale for frequencies
        colorscale = "Jet"

        for idx, freq in enumerate(frequencies):
            freq_data = plot_df[plot_df["frequency_mhz"] == freq].copy()

            # Aggregate by tissue (mean across placements if multiple)
            if "placement" in freq_data.columns:
                freq_data = (
                    freq_data.groupby("tissue")
                    .agg(
                        {
                            "Total Mass": "mean",
                            "Total Volume": "mean",
                            sar_column: "mean",
                        }
                    )
                    .reset_index()
                )

            row = (idx // cols) + 1
            col = (idx % cols) + 1

            # Scale bubble size - use power of 0.75 (between sqrt and linear) for moderate scaling
            volumes = freq_data["Total Volume"].values
            # Normalize volumes to 0-1 range, then apply power scaling
            vol_min, vol_max = volumes.min(), volumes.max()
            if vol_max > vol_min:
                normalized_volumes = (volumes - vol_min) / (vol_max - vol_min)
                bubble_sizes = np.power(normalized_volumes, 0.75) * 50 + 10  # Scale to 10-60 range
            else:
                bubble_sizes = np.full(len(volumes), 30)  # Default size if all same

            fig.add_trace(
                go.Scatter(
                    x=freq_data[sar_column],
                    y=freq_data["Total Mass"],
                    mode="markers",
                    marker=dict(
                        size=bubble_sizes,
                        sizemode="diameter",
                        sizeref=1.0,  # Direct size reference
                        sizemin=4,
                        color=freq,
                        colorscale=colorscale,
                        showscale=(idx == 0),
                        colorbar=dict(title="Frequency (MHz)") if idx == 0 else None,
                        line=dict(width=0.5, color="black"),
                    ),
                    text=[self._format_organ_name(t) for t in freq_data["tissue"]],
                    hovertemplate="<b>%{text}</b><br>"
                    + f"{sar_display_final}: %{{x:.2f}} mW/kg<br>"
                    + "Mass: %{y:.4f} kg<br>"
                    + "Volume: %{marker.size:.2e} m³<extra></extra>",
                    name=f"{freq} MHz",
                    showlegend=False,
                ),
                row=row,
                col=col,
            )

            # Set common axis limits
            fig.update_xaxes(
                type="log",
                range=[np.log10(x_min * 0.9), np.log10(x_max * 1.1)],
                title_text=f"{sar_display_final} (mW/kg)",
                row=row,
                col=col,
            )
            fig.update_yaxes(
                type="log",
                range=[np.log10(y_min * 0.9), np.log10(y_max * 1.1)],
                title_text="Total Mass (kg)",
                row=row,
                col=col,
            )

        # Update layout
        base_title = "Tissue Mass vs SAR Bubble Plot (Interactive)"
        title_with_phantom = self._get_title_with_phantom(base_title, scenario_name)
        # Don't set title on plot - will be in caption file
        fig.update_layout(
            title="",
            height=300 * rows,
            showlegend=False,
        )

        subdir = self._get_subdir("bubble")
        sar_name_safe = sar_column.replace("_mw_kg", "").replace("_", "_")
        filename = f"bubble_mass_vs_{sar_name_safe}_{scenario_name or 'all'}_interactive.html"
        fig.write_html(os.path.join(subdir, filename))

        # Create caption file for HTML plot
        caption_filename = filename.replace(".html", ".txt")
        caption_path = os.path.join(subdir, caption_filename)
        # Format SAR column name properly for caption (preserve SAR and psSAR10g acronyms)
        sar_display_interactive = sar_column.replace("_mw_kg", "").replace("_", " ")
        sar_words_interactive = sar_display_interactive.split()
        sar_formatted_interactive = []
        for word in sar_words_interactive:
            word_lower = word.lower()
            # Check for psSAR10g in any capitalization variation and fix it
            if "pssar10g" in word_lower:
                # Replace any variation (pssar10g, Pssar10g, PSSAR10G, etc.) with psSAR10g
                sar_formatted_interactive.append("psSAR10g")
            elif word.upper() == "SAR":
                sar_formatted_interactive.append("SAR")
            else:
                sar_formatted_interactive.append(word.capitalize())
        sar_display_final_interactive = " ".join(sar_formatted_interactive)
        # Final safety check: replace any incorrect psSAR10g capitalization in the final string
        sar_display_final_interactive = (
            sar_display_final_interactive.replace("Pssar10g", "psSAR10g").replace("PSSAR10g", "psSAR10g").replace("Pssar", "psSAR")
        )
        phantom_name_formatted = self.phantom_name.capitalize() if self.phantom_name else "the phantom"
        caption = f"Interactive bubble plot showing tissue mass vs {sar_display_final_interactive} with bubble size proportional to tissue volume (log scale on both axes) for the {self._format_scenario_name(scenario_name) if scenario_name else 'all scenarios'} scenario for {phantom_name_formatted}. Each subplot corresponds to a different frequency, with common axis limits for comparison."
        with open(caption_path, "w", encoding="utf-8") as f:
            f.write(f"Title: {title_with_phantom}\n\n")
            f.write(f"Caption: {caption}\n")

        logging.getLogger("progress").info(
            f"  - Generated interactive bubble plot: {filename}",
            extra={"log_type": "success"},
        )
