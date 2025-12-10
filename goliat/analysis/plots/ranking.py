"""Ranking plot generators."""

import logging

import matplotlib.pyplot as plt
import pandas as pd

from .base import BasePlotter


class RankingPlotter(BasePlotter):
    """Generates ranking plots for SAR analysis."""

    def plot_top20_tissues_ranking(
        self,
        organ_results_df: pd.DataFrame,
        metric: str = "max_local_sar_mw_kg",
        scenario_name: str | None = None,
        frequency_mhz: int | None = None,
    ):
        """Creates horizontal bar chart showing top 20 tissues ranked by various metrics.

        Args:
            organ_results_df: DataFrame with tissue-level data.
            metric: Metric to rank by (e.g., 'max_local_sar_mw_kg', 'mass_avg_sar_mw_kg', 'Total Loss').
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

        if metric not in plot_df.columns:
            logging.getLogger("progress").warning(
                f"Metric '{metric}' not found in data.",
                extra={"log_type": "warning"},
            )
            return

        # Aggregate by tissue
        if "placement" in plot_df.columns:
            plot_df = (
                plot_df.groupby("tissue")
                .agg(
                    {
                        metric: "mean",
                    }
                )
                .reset_index()
            )

        # Get top 20
        top20 = plot_df.nlargest(20, metric).sort_values(metric, ascending=True)

        if top20.empty:
            return

        fig, ax = plt.subplots(figsize=(3.5, 4.0))  # IEEE single-column width, taller for ranking

        # Auto-detect unit family based on max value
        max_val_raw = top20[metric].max()
        unit_multiplier = 1.0
        unit_label = r"mW kg$^{-1}$"

        if max_val_raw < 1e-6:
            unit_multiplier = 1e9
            unit_label = r"nW kg$^{-1}$"
        elif max_val_raw < 1e-3:
            unit_multiplier = 1e6
            unit_label = r"$\mu$W kg$^{{-1}}$"
        elif max_val_raw < 1.0:
            unit_multiplier = 1e3
            unit_label = r"mW kg$^{-1}$"
        # else: keep as mW/kg (default)

        # Scale values for display
        top20_scaled = top20.copy()
        top20_scaled[metric] = top20_scaled[metric] * unit_multiplier

        # Detect outliers: if ratio between #1 and #2 > 2.5, cap the display
        outlier_threshold = 2.5
        values_sorted = top20_scaled[metric].sort_values(ascending=False)
        has_outlier = False
        outlier_cap_value = None

        if len(values_sorted) >= 2:
            first_val = values_sorted.iloc[0]
            second_val = values_sorted.iloc[1]
            if second_val > 0 and first_val / second_val > outlier_threshold:
                has_outlier = True
                # Cap at 1.5x the second value for display
                outlier_cap_value = second_val * 1.5

        # Color by tissue group using academic color palette
        colors = self._get_academic_colors(len(top20_scaled))

        # Clean and format tissue names (remove redundant phantom identifiers and format for display)
        top20_clean = top20_scaled.copy()
        top20_clean["tissue_clean"] = top20_clean["tissue"].apply(lambda x: self._format_organ_name(x))

        # Create display values - cap outliers if needed
        display_values = top20_clean[metric].copy()
        outlier_mask = pd.Series([False] * len(display_values), index=display_values.index)

        if has_outlier and outlier_cap_value is not None:
            # Mark the outlier(s) - values that are significantly higher than the cap
            outlier_mask = display_values > outlier_cap_value
            display_values = display_values.clip(upper=outlier_cap_value)

        # Draw bars
        bar_positions = range(len(top20_clean))
        bars = ax.barh(bar_positions, display_values, color=colors, alpha=0.7, edgecolor="black", linewidth=0.5)

        # Add broken bar pattern for outliers
        if has_outlier:
            for i, (bar, is_outlier) in enumerate(zip(bars, outlier_mask.values)):
                if is_outlier:
                    # Add diagonal lines to indicate broken/capped bar
                    bar_height = bar.get_height()
                    bar_y = bar.get_y()
                    bar_width = bar.get_width()

                    # Add break marks at the end of the bar
                    break_x = bar_width * 0.95
                    ax.plot([break_x, break_x], [bar_y + 0.1, bar_y + bar_height - 0.1], color="white", linewidth=2, zorder=3)
                    ax.plot(
                        [break_x - bar_width * 0.02, break_x + bar_width * 0.02],
                        [bar_y + bar_height * 0.3, bar_y + bar_height * 0.7],
                        color="white",
                        linewidth=2,
                        zorder=3,
                    )
                    ax.plot(
                        [break_x - bar_width * 0.02, break_x + bar_width * 0.02],
                        [bar_y + bar_height * 0.7, bar_y + bar_height * 0.3],
                        color="white",
                        linewidth=2,
                        zorder=3,
                    )

        ax.set_yticks(bar_positions)
        ax.set_yticklabels(top20_clean["tissue_clean"], fontsize=9)
        ax.tick_params(axis="y", which="major", length=0)  # Remove y-axis tick marks
        # Reduce top and bottom margins
        ax.margins(y=0.01)  # Minimal top/bottom margins

        # Format x-axis label properly
        metric_display = metric.replace("_mw_kg", "").replace("_", " ")
        # Capitalize properly, preserving SAR and psSAR10g acronyms
        metric_words = metric_display.split()
        metric_formatted = []
        for word in metric_words:
            word_lower = word.lower()
            # Check for psSAR10g in any capitalization variation and fix it
            if "pssar10g" in word_lower:
                # Replace any variation (pssar10g, Pssar10g, PSSAR10G, etc.) with psSAR10g
                metric_formatted.append("psSAR10g")
            elif word.upper() == "SAR":
                metric_formatted.append("SAR")
            else:
                metric_formatted.append(word.capitalize())
        metric_display = " ".join(metric_formatted)
        # Final safety check: replace any incorrect psSAR10g capitalization
        metric_display = metric_display.replace("Pssar10g", "psSAR10g").replace("PSSAR10g", "psSAR10g").replace("Pssar", "psSAR")
        ax.set_xlabel(f"{metric_display} ({unit_label})")
        ax.set_ylabel("Tissue")

        # Create title with phantom name
        base_title = f"top 20 tissues by {metric_display}"
        title_full = self._get_title_with_phantom(base_title, scenario_name)
        # Don't set title on plot - will be in caption file
        ax.grid(True, alpha=0.3, axis="x")

        # Set x-axis range - use capped value if outliers exist
        if has_outlier and outlier_cap_value is not None:
            ax.set_xlim(0, outlier_cap_value * 1.15)  # Extra space for label
        else:
            max_val = top20_clean[metric].max()
            ax.set_xlim(0, max_val * 1.05)

        # Add value labels on bars
        # For the highest bar (last one in sorted order), put label IN the bar, others to the right
        # Find the index position of the max value (it's the last bar since sorted ascending=True)
        max_bar_idx = len(top20_clean) - 1

        for i, (idx, row) in enumerate(top20_clean.iterrows()):
            actual_value = row[metric]
            display_value = display_values.loc[idx]
            is_outlier_bar = outlier_mask.loc[idx] if has_outlier else False

            if is_outlier_bar:
                # Outlier bar: show actual value with asterisk indicator
                # Position label left of break marks (which are at 0.95), use black for readability
                label_text = f"{actual_value:.3f}*"
                ax.text(display_value * 0.85, i, label_text, va="center", ha="right", fontsize=8, color="black", weight="bold")
            elif i == max_bar_idx:  # Highest bar (last position) - only if not outlier
                # Highest bar: label inside, right-aligned, black text
                ax.text(actual_value * 0.95, i, f"{actual_value:.3f}", va="center", ha="right", fontsize=8, color="black", weight="bold")
            else:
                # Other bars: label to the right
                ax.text(actual_value, i, f" {actual_value:.3f}", va="center", fontsize=8)

        plt.tight_layout()

        metric_name = metric.replace("_mw_kg", "").replace("_", "_")
        filename_base = f"ranking_top20_{metric_name}_{scenario_name or 'all'}_{frequency_mhz or 'all'}MHz"
        # Use the properly formatted metric_display and unit_label for caption
        phantom_name_formatted = self.phantom_name.capitalize() if self.phantom_name else "the phantom"
        outlier_note = (
            " Note: values marked with * are outliers that exceed the display scale; the actual value is shown." if has_outlier else ""
        )
        caption = f"The horizontal bar chart ranks the top 20 tissues by {metric_display} ({unit_label}) for the {self._format_scenario_name(scenario_name) if scenario_name else 'all scenarios'} scenario{f' at {frequency_mhz} MHz' if frequency_mhz else ''} for {phantom_name_formatted}.{outlier_note}"
        filename = self._save_figure(fig, "ranking", filename_base, title=title_full, caption=caption, dpi=300)

        # Save CSV data
        csv_data = top20_clean[["tissue_clean", metric]].copy()
        csv_data.columns = ["tissue", metric]
        csv_data = csv_data.sort_values(metric, ascending=True)
        self._save_csv_data(csv_data, "ranking", filename_base)
        logging.getLogger("progress").info(
            f"  - Generated ranking plot: {filename}",
            extra={"log_type": "success"},
        )
