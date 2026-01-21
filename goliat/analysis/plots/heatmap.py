"""Heatmap generators."""

import logging
import os

import matplotlib.gridspec as gridspec
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from matplotlib.colors import LogNorm

from .base import BasePlotter


class HeatmapPlotter(BasePlotter):
    """Generates heatmap plots for SAR analysis."""

    def _plot_heatmap(self, fig, ax, data: pd.DataFrame, title: str, cbar: bool = True, cbar_ax=None):
        """Helper that plots a single heatmap with log-scale normalization."""
        sns.heatmap(
            data,
            ax=ax,
            annot=True,
            fmt=".2f",
            cmap="jet",
            linewidths=0.5,
            norm=LogNorm(vmin=data[data > 0].min().min(), vmax=data.max().max()),
            cbar=cbar,
            cbar_ax=cbar_ax if cbar else None,
        )
        # Title removed per user request
        return ax

    def plot_sar_heatmap(self, organ_df: pd.DataFrame, group_df: pd.DataFrame, tissue_groups: dict):
        """Creates separate heatmaps for Min, Avg, and Max SAR per tissue and frequency.

        Generates three separate heatmaps instead of a combined summary.
        Each heatmap has two panels: top shows individual tissues, bottom shows group summaries.
        Uses log-scale colormap for better visibility.
        """
        # Generate separate heatmaps for min, avg, and max
        self._plot_sar_heatmap_single(organ_df, group_df, tissue_groups, "min_sar", "Min")
        self._plot_sar_heatmap_single(organ_df, group_df, tissue_groups, "avg_sar", "Avg")
        self._plot_sar_heatmap_single(organ_df, group_df, tissue_groups, "max_sar", "Max")

    def _plot_sar_heatmap_single(
        self, organ_df: pd.DataFrame, group_df: pd.DataFrame, tissue_groups: dict, value_col: str, metric_label: str
    ):
        """Creates a single heatmap for a specific SAR metric (min/avg/max).

        Args:
            organ_df: DataFrame with organ-level SAR data.
            group_df: DataFrame with group-level SAR data.
            tissue_groups: Dictionary mapping group names to tissue lists.
            value_col: Column name for the metric ('min_sar', 'avg_sar', or 'max_sar').
            metric_label: Display label for the metric ('Min', 'Avg', or 'Max').
        """
        # Filter out 'All Regions' - it's a whole-body aggregate, not a real tissue
        organ_df = self._filter_all_regions(organ_df, tissue_column="tissue")

        # Clean and format tissue names before pivoting (remove phantom identifiers and format for display)
        organ_df_clean = organ_df.copy()
        organ_df_clean["tissue"] = organ_df_clean["tissue"].apply(lambda x: self._format_organ_name(x))

        # Create pivot table for the specific metric
        if value_col not in organ_df_clean.columns:
            logging.getLogger("progress").warning(
                f"  - WARNING: Column '{value_col}' not found for heatmap.",
                extra={"log_type": "warning"},
            )
            return

        organ_pivot = organ_df_clean.pivot_table(
            index="tissue",
            columns="frequency_mhz",
            values=value_col,
        )
        organ_pivot = organ_pivot.loc[(organ_pivot > 0.01).any(axis=1)]
        mean_organ_sar = organ_pivot.mean(axis=1).sort_values(ascending=False)
        organ_pivot = organ_pivot.reindex(mean_organ_sar.index)

        # For group summary, use the same metric (or avg_sar if the metric doesn't exist in group_df)
        group_value_col = value_col if value_col in group_df.columns else "avg_sar"
        group_pivot = group_df.pivot_table(index="group", columns="frequency_mhz", values=group_value_col)
        if isinstance(group_pivot, pd.DataFrame) and not group_pivot.empty:
            mean_group_sar = group_pivot.mean(axis=1)
            if isinstance(mean_group_sar, pd.Series):
                mean_group_sar = mean_group_sar.sort_values(ascending=False)
                group_pivot = group_pivot.reindex(mean_group_sar.index)
        if isinstance(group_pivot, pd.DataFrame) and not group_pivot.empty:
            mean_group_sar = group_pivot.mean(axis=1)
            if isinstance(mean_group_sar, pd.Series):
                mean_group_sar = mean_group_sar.sort_values(ascending=False)
                group_pivot = group_pivot.reindex(mean_group_sar.index)

        if organ_pivot.empty:
            return

        # Use two-column width for wide heatmaps, scale height dynamically based on content
        # Calculate height: base height + height per row (with reduced row height for compact cells)
        min_row_height = 0.25  # Reduced from 0.35 - minimum inches per row for readability
        base_height = 2.0  # Base height for titles, spacing, group summary
        organ_height = max(len(organ_pivot) * min_row_height, len(organ_pivot) * 0.08)  # Reduced from 0.12 - dynamic per-row height
        group_height = max(len(group_pivot) * 0.25, 0.8) if not group_pivot.empty else 0  # Reduced from 0.4 and 1.0
        total_height = base_height + organ_height + group_height
        fig = plt.figure(figsize=(7.16, total_height))
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

        # Create title with phantom name
        base_title = f"{metric_label} SAR (mW kg$^{{-1}}$) per tissue"
        title_with_phantom = self._get_title_with_phantom(base_title)

        # Plot heatmap without title (removed subplot titles)
        sns.heatmap(
            organ_pivot,
            ax=ax_organ,
            annot=True,
            fmt=".2f",
            cmap="jet",
            linewidths=0.5,
            norm=LogNorm(vmin=organ_pivot[organ_pivot > 0].min().min(), vmax=organ_pivot.max().max()),
            cbar=True,
            cbar_ax=cbar_ax,
            xticklabels=False,  # Remove x tickmarks
            yticklabels=True,  # Keep y labels but reduce fontsize
            square=False,  # Allow rectangular cells for more compact vertical layout
        )
        ax_organ.set_xlabel(self._format_axis_label("Frequency", "MHz"))
        ax_organ.set_ylabel("Tissue")
        ax_organ.tick_params(labelsize=6, which="minor", length=0)  # Reduced fontsize, no minor ticks

        # Color mapping for tissue groups: eyes=red, skin=green, brain=blue, genitals=purple
        group_colors = {"eyes": "red", "skin": "green", "brain": "blue", "genitals": "purple"}
        tissue_to_group = {}
        for group, tissues in tissue_groups.items():
            for tissue in tissues:
                tissue_clean = self._format_organ_name(tissue)
                tissue_to_group[tissue_clean] = group.lower().replace("_group", "").replace("group", "")

        for tick_label in ax_organ.get_yticklabels():
            tissue_name = tick_label.get_text()
            group_name = tissue_to_group.get(tissue_name, "")
            if group_name in group_colors:
                tick_label.set_color(group_colors[group_name])
            tick_label.set_fontsize(6)  # Reduced fontsize

        # Plot group summary without title
        sns.heatmap(
            group_pivot,
            ax=ax_group,
            annot=True,
            fmt=".2f",
            cmap="jet",
            linewidths=0.5,
            norm=LogNorm(vmin=group_pivot[group_pivot > 0].min().min(), vmax=group_pivot.max().max()) if not group_pivot.empty else None,
            cbar=False,
            xticklabels=False,  # Remove x tickmarks
            yticklabels=True,  # Keep y labels but reduce fontsize
            square=False,  # Allow rectangular cells for more compact vertical layout
        )
        ax_group.set_xlabel(self._format_axis_label("Frequency", "MHz"))
        ax_group.set_ylabel("")
        ax_group.tick_params(labelsize=6)  # Reduced fontsize
        for tick_label in ax_group.get_yticklabels():
            tick_label.set_rotation(0)
            group_name = tick_label.get_text().lower().replace("_group", "").replace("group", "")
            if group_name in group_colors:
                tick_label.set_color(group_colors[group_name])
            tick_label.set_fontsize(6)  # Reduced fontsize

        plt.tight_layout(rect=(0, 0, 0.95, 0.98))
        phantom_name_formatted = self.phantom_name.capitalize() if self.phantom_name else "the phantom"
        caption = f"The heatmap shows {metric_label.lower()} SAR values per tissue across frequencies for {phantom_name_formatted}. The top panel shows individual tissues, and the bottom panel shows organ group summaries. Tissues are colored by group (red=eyes, green=skin, blue=brain, purple=genitals)."
        filename_base = f"heatmap_sar_{value_col.replace('_sar', '')}"
        filename = self._save_figure(fig, "heatmap", filename_base, title=title_with_phantom, caption=caption, dpi=300)

        # Save CSV data - combine organ and group pivots
        csv_data_list = []
        if not organ_pivot.empty:
            organ_csv = organ_pivot.copy()
            organ_csv.insert(0, "Type", "Individual Tissue")
            csv_data_list.append(organ_csv)
        if not group_pivot.empty:
            group_csv = group_pivot.copy()
            group_csv.insert(0, "Type", "Group Summary")
            csv_data_list.append(group_csv)
        if csv_data_list:
            csv_data = pd.concat(csv_data_list)
            self._save_csv_data(csv_data, "heatmap", filename_base)
        logging.getLogger("progress").info(
            f"  - Generated {metric_label} SAR heatmap: {filename}",
            extra={"log_type": "success"},
        )

        # Also create HTML version
        try:
            import plotly.graph_objects as go
            from plotly.subplots import make_subplots

            # Create HTML version
            fig_html = make_subplots(
                rows=2,
                cols=1,
                subplot_titles=["", ""],  # Remove subplot titles
                vertical_spacing=0.15,
            )

            # Organ heatmap
            z_min_organ = organ_pivot[organ_pivot > 0].min().min() if (organ_pivot > 0).any().any() else 0.01
            z_max_organ = organ_pivot.max().max()
            fig_html.add_trace(
                go.Heatmap(
                    z=organ_pivot.values,
                    x=organ_pivot.columns.tolist(),
                    y=organ_pivot.index.tolist(),
                    colorscale="Jet",
                    zmin=z_min_organ,
                    zmax=z_max_organ,
                    colorbar=dict(title="SAR (mW/kg)", len=0.5, y=0.75),
                    text=organ_pivot.values,
                    texttemplate="%{text:.2f}",
                    textfont={"size": 8},
                ),
                row=1,
                col=1,
            )

            # Group heatmap
            if not group_pivot.empty:
                z_min_group = group_pivot[group_pivot > 0].min().min() if (group_pivot > 0).any().any() else 0.01
                z_max_group = group_pivot.max().max()
                fig_html.add_trace(
                    go.Heatmap(
                        z=group_pivot.values,
                        x=group_pivot.columns.tolist(),
                        y=group_pivot.index.tolist(),
                        colorscale="Jet",
                        zmin=z_min_group,
                        zmax=z_max_group,
                        colorbar=dict(title="SAR (mW/kg)", len=0.5, y=0.25),
                        text=group_pivot.values,
                        texttemplate="%{text:.2f}",
                        textfont={"size": 10},
                    ),
                    row=2,
                    col=1,
                )

            fig_html.update_layout(
                title="",  # Don't set title - will be in caption file
                height=600 + len(organ_pivot) * 15,
            )

            subdir = self._get_subdir("heatmap")
            filename_html = f"heatmap_sar_{value_col.replace('_sar', '')}.html"
            fig_html.write_html(os.path.join(subdir, filename_html))

            # Create caption file for HTML plot
            caption_filename_html = filename_html.replace(".html", ".txt")
            caption_path_html = os.path.join(subdir, caption_filename_html)
            phantom_name_formatted_html = self.phantom_name.capitalize() if self.phantom_name else "the phantom"
            caption_html = f"The interactive heatmap shows {metric_label.lower()} SAR values per tissue across frequencies for {phantom_name_formatted_html}. The top panel shows individual tissues, and the bottom panel shows organ group summaries."
            with open(caption_path_html, "w", encoding="utf-8") as f:
                f.write(f"Title: {title_with_phantom}\n\n")
                f.write(f"Caption: {caption_html}\n")

            logging.getLogger("progress").info(
                f"  - Generated HTML heatmap: {filename_html}",
                extra={"log_type": "success"},
            )
        except ImportError:
            logging.getLogger("progress").warning(
                "Plotly not available. Skipping HTML heatmap. Install with: pip install plotly",
                extra={"log_type": "warning"},
            )

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
        'All Regions' is excluded as it's a whole-body aggregate, not a real tissue.

        Args:
            organ_df: DataFrame with organ-level peak SAR data.
            group_df: DataFrame with group-level summaries.
            tissue_groups: Dict mapping groups to tissue lists.
            value_col: Column name containing the peak SAR values.
            title: Title for the plot.
        """
        # Filter out 'All Regions' - it's a whole-body aggregate, not a real tissue
        organ_df = self._filter_all_regions(organ_df, tissue_column="tissue")

        # Clean and format tissue names before pivoting (remove phantom identifiers and format for display)
        organ_df_clean = organ_df.copy()
        organ_df_clean["tissue"] = organ_df_clean["tissue"].apply(lambda x: self._format_organ_name(x))

        organ_pivot = organ_df_clean.pivot_table(index="tissue", columns="frequency_mhz", values=value_col)
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

        # Use two-column width for wide heatmaps, scale height dynamically based on content
        # Calculate height: base height + height per row (with reduced row height for compact cells)
        min_row_height = 0.25  # Reduced from 0.35 - minimum inches per row for readability
        base_height = 2.0  # Base height for titles, spacing, group summary
        organ_height = max(len(organ_pivot) * min_row_height, len(organ_pivot) * 0.08)  # Reduced from 0.12 - dynamic per-row height
        group_height = max(len(group_pivot) * 0.25, 0.8) if not group_pivot.empty else 0  # Reduced from 0.4 and 1.0
        total_height = base_height + organ_height + group_height
        fig = plt.figure(figsize=(7.16, total_height))
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

        # Create title with phantom name
        base_title = f"{title} (mW kg$^{{-1}}$) per tissue"
        title_with_phantom = self._get_title_with_phantom(base_title)

        # Plot organ heatmap without title
        sns.heatmap(
            organ_pivot,
            ax=ax_organ,
            annot=True,
            fmt=".2f",
            cmap="jet",
            linewidths=0.5,
            norm=LogNorm(vmin=organ_pivot[organ_pivot > 0].min().min(), vmax=organ_pivot.max().max()),
            cbar=True,
            cbar_ax=cbar_ax,
            xticklabels=False,  # Remove x tickmarks
            yticklabels=True,  # Keep y labels but reduce fontsize
            square=False,  # Allow rectangular cells for more compact vertical layout
        )
        ax_organ.set_xlabel("")
        ax_organ.set_ylabel("Tissue")
        ax_organ.tick_params(labelsize=6, which="minor", length=0)  # Reduced fontsize, no minor ticks

        # Color tissue labels by group
        group_colors_peak = {"eyes": "red", "skin": "green", "brain": "blue", "genitals": "purple"}
        tissue_to_group = {}
        for group, tissues in tissue_groups.items():
            for tissue in tissues:
                tissue_clean = self._format_organ_name(tissue)
                tissue_to_group[tissue_clean] = group.lower().replace("_group", "").replace("group", "")

        for tick_label in ax_organ.get_yticklabels():
            tissue_name = tick_label.get_text()
            group_name = tissue_to_group.get(tissue_name, "")
            if group_name in group_colors_peak:
                tick_label.set_color(group_colors_peak[group_name])
            tick_label.set_fontsize(6)  # Reduced fontsize

        # Plot group summary without title
        sns.heatmap(
            group_pivot,
            ax=ax_group,
            annot=True,
            fmt=".2f",
            cmap="jet",
            linewidths=0.5,
            norm=LogNorm(vmin=group_pivot[group_pivot > 0].min().min(), vmax=group_pivot.max().max()) if not group_pivot.empty else None,
            cbar=False,
            xticklabels=False,  # Remove x tickmarks
            yticklabels=True,  # Keep y labels but reduce fontsize
            square=False,  # Allow rectangular cells for more compact vertical layout
        )
        ax_group.set_xlabel(self._format_axis_label("Frequency", "MHz"))
        ax_group.set_ylabel("")
        ax_group.tick_params(labelsize=6, which="minor", length=0)  # Reduced fontsize, no minor ticks
        # Color group labels
        for tick_label in ax_group.get_yticklabels():
            tick_label.set_rotation(0)
            group_name = tick_label.get_text().lower().replace("_group", "").replace("group", "")
            if group_name in group_colors_peak:
                tick_label.set_color(group_colors_peak[group_name])
            tick_label.set_fontsize(6)  # Reduced fontsize

        plt.tight_layout(rect=(0, 0, 0.95, 0.98))
        filename_base = f"heatmap_{value_col}_summary"
        phantom_name_formatted = self.phantom_name.capitalize() if self.phantom_name else "the phantom"
        caption = f"The heatmap shows {title} values per tissue across frequencies for {phantom_name_formatted}. The top panel shows individual tissues, and the bottom panel shows organ group summaries. Tissues are colored by group (red=eyes, green=skin, blue=brain, purple=genitals)."
        filename = self._save_figure(fig, "heatmap", filename_base, title=title_with_phantom, caption=caption, dpi=300)
        logging.getLogger("progress").info(
            f"  - Generated {title} heatmap: {filename}",
            extra={"log_type": "success"},
        )

        # Also create HTML version
        try:
            import plotly.graph_objects as go
            from plotly.subplots import make_subplots

            # Create HTML version
            fig_html = make_subplots(
                rows=2,
                cols=1,
                subplot_titles=["", ""],  # Remove subplot titles
                vertical_spacing=0.15,
            )

            # Organ heatmap
            z_min_organ = organ_pivot[organ_pivot > 0].min().min() if (organ_pivot > 0).any().any() else 0.01
            z_max_organ = organ_pivot.max().max()
            fig_html.add_trace(
                go.Heatmap(
                    z=organ_pivot.values,
                    x=organ_pivot.columns.tolist(),
                    y=organ_pivot.index.tolist(),
                    colorscale="Jet",
                    zmin=z_min_organ,
                    zmax=z_max_organ,
                    colorbar=dict(title=f"{title} (mW/kg)", len=0.5, y=0.75),
                    text=organ_pivot.values,
                    texttemplate="%{text:.2f}",
                    textfont={"size": 8},
                ),
                row=1,
                col=1,
            )

            # Group heatmap
            if not group_pivot.empty:
                z_min_group = group_pivot[group_pivot > 0].min().min() if (group_pivot > 0).any().any() else 0.01
                z_max_group = group_pivot.max().max()
                fig_html.add_trace(
                    go.Heatmap(
                        z=group_pivot.values,
                        x=group_pivot.columns.tolist(),
                        y=group_pivot.index.tolist(),
                        colorscale="Jet",
                        zmin=z_min_group,
                        zmax=z_max_group,
                        colorbar=dict(title=f"{title} (mW/kg)", len=0.5, y=0.25),
                        text=group_pivot.values,
                        texttemplate="%{text:.2f}",
                        textfont={"size": 10},
                    ),
                    row=2,
                    col=1,
                )

            fig_html.update_layout(
                title=self._get_title_with_phantom(f"{title} per tissue"),
                height=600 + len(organ_pivot) * 15,
            )

            subdir = self._get_subdir("heatmap")
            html_filename = f"heatmap_{value_col}_summary.html"
            fig_html.write_html(os.path.join(subdir, html_filename))
            logging.getLogger("progress").info(
                f"  - Generated {title} heatmap (HTML): {html_filename}",
                extra={"log_type": "success"},
            )
        except ImportError:
            logging.getLogger("progress").warning(
                "Plotly not available. Skipping HTML heatmap. Install with: pip install plotly",
                extra={"log_type": "warning"},
            )

    def plot_far_field_direction_polarization_heatmap(
        self,
        results_df: pd.DataFrame,
        metric: str = "SAR_whole_body",
        frequency_mhz: int | None = None,
    ):
        """Creates a heatmap comparing SAR values across incident directions and polarizations.

        This visualization is specific to far-field analysis where simulations are run
        for different incident wave directions (from left, right, front, back, above, below) and polarizations
        (theta, phi). The heatmap shows where SAR is highest and lowest.

        Args:
            results_df: DataFrame with 'placement' column containing direction/polarization info.
            metric: SAR metric to plot (default: 'SAR_whole_body').
            frequency_mhz: Optional frequency to filter. If None, averages across all frequencies.
        """
        if metric not in results_df.columns or results_df[metric].dropna().empty:
            logging.getLogger("progress").warning(
                f"  - WARNING: No data for metric '{metric}' to generate direction/polarization heatmap.",
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

        # Filter by frequency if specified
        if frequency_mhz is not None:
            df = df[df["frequency_mhz"] == frequency_mhz]
            freq_suffix = f"_{frequency_mhz}MHz"
        else:
            freq_suffix = "_allMHz"

        if df.empty:
            logging.getLogger("progress").warning(
                f"  - WARNING: No data after filtering for heatmap (metric={metric}, freq={frequency_mhz}).",
                extra={"log_type": "warning"},
            )
            return

        # Create pivot table: direction x polarization
        # If multiple frequencies, take the mean
        pivot = df.pivot_table(
            index="direction",
            columns="polarization",
            values=metric,
            aggfunc="mean",
        )

        # Reorder directions for logical display
        direction_order = ["From left", "From right", "From back", "From front", "From below", "From above"]
        pivot = pivot.reindex([d for d in direction_order if d in pivot.index])

        # Reorder polarizations (Theta, Phi)
        pol_order = ["Theta", "Phi"]
        pivot = pivot[[p for p in pol_order if p in pivot.columns]]

        if pivot.empty:
            logging.getLogger("progress").warning(
                "  - WARNING: Empty pivot table for direction/polarization heatmap.",
                extra={"log_type": "warning"},
            )
            return

        # Create figure - compact size since we only have 6x2 cells
        fig, ax = plt.subplots(figsize=(3.5, 4.0))

        # Use a diverging colormap centered on the mean
        vmin = pivot.min().min()
        vmax = pivot.max().max()

        # Use log scale if values span more than 2 orders of magnitude
        use_log = vmax / vmin > 100 if vmin > 0 else False

        if use_log:
            from matplotlib.colors import LogNorm

            norm = LogNorm(vmin=vmin, vmax=vmax)
        else:
            norm = None

        sns.heatmap(
            pivot,
            ax=ax,
            annot=True,
            fmt=".1f",
            cmap="RdYlGn_r",  # Red=high SAR, Green=low SAR
            linewidths=1.0,
            linecolor="white",
            cbar_kws={"label": f"{self._format_organ_name(metric)} (mW/kg)"},
            norm=norm,
            square=True,
        )

        # Styling
        ax.set_xlabel("Polarization", fontsize=9)
        ax.set_ylabel("Incident Direction", fontsize=9)
        ax.tick_params(labelsize=8)

        # Rotate y-axis labels for better readability
        ax.set_yticklabels(ax.get_yticklabels(), rotation=0)

        plt.tight_layout()

        # Create title and caption
        from .base import METRIC_LABELS

        metric_label = METRIC_LABELS.get(metric, metric)
        freq_text = f"at {frequency_mhz} MHz" if frequency_mhz else "averaged across all frequencies"
        base_title = f"far-field {metric_label} by incident direction and polarization {freq_text}"
        title_full = self._get_title_with_phantom(base_title)

        phantom_name_formatted = self.phantom_name.capitalize() if self.phantom_name else "the phantom"
        caption = (
            f"The heatmap compares normalized {metric_label} values for {phantom_name_formatted} "
            f"across different far-field incident wave directions (from left, right, front, back, above, below) and polarizations (Theta, Phi) "
            f"{freq_text}. Red indicates higher SAR absorption, green indicates lower SAR absorption. "
            f"This visualization helps identify which exposure configurations result in the highest and lowest SAR values."
        )

        filename_base = f"heatmap_direction_polarization_{metric}{freq_suffix}"
        filename = self._save_figure(fig, "heatmap", filename_base, title=title_full, caption=caption, dpi=300)

        # Save CSV data
        self._save_csv_data(pivot, "heatmap", filename_base)

        logging.getLogger("progress").info(
            f"  - Generated direction/polarization heatmap: {filename}",
            extra={"log_type": "success"},
        )

        return filename

    def plot_far_field_direction_polarization_summary(
        self,
        results_df: pd.DataFrame,
        metrics: list[str] | None = None,
    ):
        """Creates a multi-panel summary comparing SAR metrics across directions/polarizations.

        Generates both individual metric heatmaps and a combined multi-panel figure.

        Args:
            results_df: DataFrame with 'placement' column containing direction/polarization info.
            metrics: List of metrics to plot. If None, plots common metrics.
        """
        if metrics is None:
            # Default metrics to plot - includes tissue group SAR and psSAR10g metrics
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
                "  - WARNING: No valid metrics for direction/polarization summary.",
                extra={"log_type": "warning"},
            )
            return

        # Generate individual heatmaps for each metric
        for metric in metrics:
            self.plot_far_field_direction_polarization_heatmap(results_df, metric=metric)

        # Create a multi-panel combined figure
        self._plot_far_field_direction_polarization_combined(results_df, metrics)

    def _plot_far_field_direction_polarization_combined(
        self,
        results_df: pd.DataFrame,
        metrics: list[str],
    ):
        """Creates a combined multi-panel heatmap for multiple metrics.

        Args:
            results_df: DataFrame with placement and metric data.
            metrics: List of metrics to include.
        """
        import matplotlib.gridspec as gridspec

        # Parse placement column
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

        # Create pivot tables for each metric
        pivots = {}
        for metric in metrics:
            if metric in df.columns and df[metric].notna().any():
                pivot = df.pivot_table(
                    index="direction",
                    columns="polarization",
                    values=metric,
                    aggfunc="mean",
                )
                # Reorder
                direction_order = ["From left", "From right", "From back", "From front", "From below", "From above"]
                pivot = pivot.reindex([d for d in direction_order if d in pivot.index])
                pol_order = ["Theta", "Phi"]
                pivot = pivot[[p for p in pol_order if p in pivot.columns]]
                if not pivot.empty:
                    pivots[metric] = pivot

        if not pivots:
            return

        # Layout: grid of heatmaps
        n_metrics = len(pivots)
        n_cols = min(3, n_metrics)
        n_rows = (n_metrics + n_cols - 1) // n_cols

        fig = plt.figure(figsize=(3.5 * n_cols, 3.5 * n_rows))
        gs = gridspec.GridSpec(n_rows, n_cols, hspace=0.4, wspace=0.3)

        from .base import METRIC_LABELS

        for idx, (metric, pivot) in enumerate(pivots.items()):
            row = idx // n_cols
            col = idx % n_cols
            ax = fig.add_subplot(gs[row, col])

            # Normalize within each metric for comparable coloring
            vmin = pivot.min().min()
            vmax = pivot.max().max()

            sns.heatmap(
                pivot,
                ax=ax,
                annot=True,
                fmt=".1f",
                cmap="RdYlGn_r",
                linewidths=0.5,
                linecolor="white",
                cbar=False,  # Skip colorbar for space
                vmin=vmin,
                vmax=vmax,
                square=True,
                annot_kws={"size": 7},
            )

            # Title shows metric name
            metric_label = METRIC_LABELS.get(metric, metric)
            ax.set_title(metric_label, fontsize=9, fontweight="bold")
            ax.set_xlabel("Pol." if row == n_rows - 1 else "", fontsize=8)
            ax.set_ylabel("Dir." if col == 0 else "", fontsize=8)
            ax.tick_params(labelsize=7)
            ax.set_yticklabels(ax.get_yticklabels(), rotation=0)

        plt.tight_layout()

        base_title = "far-field SAR comparison by incident direction and polarization"
        title_full = self._get_title_with_phantom(base_title)
        phantom_name_formatted = self.phantom_name.capitalize() if self.phantom_name else "the phantom"
        caption = (
            f"The combined heatmap compares normalized SAR values for {phantom_name_formatted} "
            f"across different far-field incident wave directions (from left/right, front/back, above/below) and polarizations (Theta, Phi). "
            f"Each panel shows a different SAR metric. Red indicates higher SAR absorption, green indicates lower."
        )

        filename = self._save_figure(fig, "heatmap", "heatmap_direction_polarization_summary", title=title_full, caption=caption, dpi=300)

        logging.getLogger("progress").info(
            f"  - Generated combined direction/polarization summary: {filename}",
            extra={"log_type": "success"},
        )

    def plot_polarization_ratio_heatmap(
        self,
        results_df: pd.DataFrame,
        metrics: list[str] | None = None,
    ):
        """Plots heatmap of theta/phi polarization ratio for each direction and metric.

        Creates a heatmap showing frequency-averaged polarization ratios.
        Ratios > 1.0 indicate theta dominates; < 1.0 indicates phi dominates.

        Args:
            results_df: DataFrame with placement column containing direction and polarization info.
            metrics: List of metrics to analyze. If None, uses common metrics.
        """
        if results_df.empty:
            return

        # Parse placement to extract direction and polarization
        def parse_placement(placement: str) -> tuple[str, str]:
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

        # Direction display names and order (human-readable: describes where wave comes FROM)
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

        # Compute ratio for each direction and metric (averaged across frequencies)
        ratio_data = {}
        for direction in available_directions:
            dir_df = df[df["direction"] == direction]
            direction_ratios = {}

            for metric in metrics:
                if metric not in dir_df.columns:
                    continue

                pivot = dir_df.pivot_table(values=metric, index="frequency_mhz", columns="polarization", aggfunc="mean")

                if "theta" not in pivot.columns or "phi" not in pivot.columns:
                    continue

                # Average ratio across frequencies
                ratios = pivot["theta"] / pivot["phi"]
                avg_ratio = ratios.mean()
                direction_ratios[metric] = avg_ratio

            if direction_ratios:
                ratio_data[direction_names.get(direction, direction)] = direction_ratios

        if not ratio_data:
            return

        # Create DataFrame for heatmap
        ratio_df = pd.DataFrame(ratio_data).T

        # Rename columns for display
        metric_labels = {
            "SAR_whole_body": "Whole Body",
            "SAR_brain": "Brain",
            "SAR_eyes": "Eyes",
            "SAR_skin": "Skin",
            "SAR_genitals": "Genitals",
            "psSAR10g_brain": "Brain",
            "psSAR10g_eyes": "Eyes",
            "psSAR10g_skin": "Skin",
            "psSAR10g_genitals": "Genitals",
        }
        ratio_df = ratio_df.rename(columns=metric_labels)

        # Reorder rows
        row_order = ["From left", "From right", "From back", "From front", "From below", "From above"]
        ratio_df = ratio_df.reindex([r for r in row_order if r in ratio_df.index])

        # Create figure
        fig, ax = plt.subplots(figsize=(6, 4))

        # Colormap starting from 0, centered at 1.0
        from matplotlib.colors import TwoSlopeNorm

        vmin = 0.0  # Start from 0
        vmax = max(ratio_df.max().max(), 2.0)  # Ensure we show at least up to 2.0
        vcenter = 1.0

        norm = TwoSlopeNorm(vmin=vmin, vcenter=vcenter, vmax=vmax)

        sns.heatmap(
            ratio_df,
            ax=ax,
            annot=True,
            fmt=".2f",
            cmap="RdBu_r",  # Red for theta dominates (>1), Blue for phi dominates (<1)
            norm=norm,
            linewidths=0.5,
            cbar_kws={"label": "Polarization Ratio (Theta/Phi)"},
        )

        ax.set_xlabel("Tissue Group", fontsize=10)
        ax.set_ylabel("Incident Direction", fontsize=10)
        ax.tick_params(axis="both", labelsize=9, which="both")
        ax.minorticks_off()  # Remove minor ticks

        plt.tight_layout()

        # Save
        phantom_name_formatted = self.phantom_name.capitalize() if self.phantom_name else "the phantom"
        title = self._get_title_with_phantom("Polarization Ratio (Theta/Phi) by Direction")
        caption = (
            f"Heatmap showing the theta/phi polarization ratio for {phantom_name_formatted}, "
            f"averaged across all frequencies. "
            f"Ratio > 1.0 (red) indicates theta polarization gives higher SAR. "
            f"Ratio < 1.0 (blue) indicates phi polarization dominates. "
            f"Note: These are frequency-averaged values; significant frequency-dependent variations exist."
        )

        filename = self._save_figure(fig, "heatmap", "heatmap_polarization_ratio", title=title, caption=caption, dpi=300)

        logging.getLogger("progress").info(
            f"  - Generated polarization ratio heatmap: {filename}",
            extra={"log_type": "success"},
        )

    def plot_polarization_ratio_heatmaps_per_frequency(
        self,
        results_df: pd.DataFrame,
        metrics: list[str] | None = None,
    ):
        """Plots polarization ratio heatmaps for each frequency separately.

        Creates individual heatmaps showing theta/phi ratios for each frequency,
        allowing detailed analysis of frequency-dependent polarization effects.

        Args:
            results_df: DataFrame with placement column containing direction and polarization info.
            metrics: List of metrics to analyze. If None, uses common metrics.
        """
        if results_df.empty:
            return

        # Parse placement to extract direction and polarization
        def parse_placement(placement: str) -> tuple[str, str]:
            parts = placement.split("_")
            if len(parts) >= 4:
                direction = f"{parts[1]}_{parts[2]}"
                pol = parts[3]
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

        frequencies = sorted(df["frequency_mhz"].unique())

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

        metric_labels = {
            "SAR_whole_body": "Whole Body",
            "SAR_brain": "Brain",
            "SAR_eyes": "Eyes",
            "SAR_skin": "Skin",
            "SAR_genitals": "Genitals",
            "psSAR10g_brain": "Brain",
            "psSAR10g_eyes": "Eyes",
            "psSAR10g_skin": "Skin",
            "psSAR10g_genitals": "Genitals",
        }

        from matplotlib.colors import TwoSlopeNorm

        for freq in frequencies:
            freq_df = df[df["frequency_mhz"] == freq]

            # Compute ratio for each direction and metric
            ratio_data = {}
            for direction in available_directions:
                dir_df = freq_df[freq_df["direction"] == direction]
                direction_ratios = {}

                for metric in metrics:
                    if metric not in dir_df.columns:
                        continue

                    theta_val = dir_df[dir_df["polarization"] == "theta"][metric].mean()
                    phi_val = dir_df[dir_df["polarization"] == "phi"][metric].mean()

                    if pd.notna(theta_val) and pd.notna(phi_val) and phi_val != 0:
                        direction_ratios[metric] = theta_val / phi_val

                if direction_ratios:
                    ratio_data[direction_names.get(direction, direction)] = direction_ratios

            if not ratio_data:
                continue

            ratio_df = pd.DataFrame(ratio_data).T
            ratio_df = ratio_df.rename(columns=metric_labels)
            row_order = ["From left", "From right", "From back", "From front", "From below", "From above"]
            ratio_df = ratio_df.reindex([r for r in row_order if r in ratio_df.index])

            # Create figure
            fig, ax = plt.subplots(figsize=(5, 3.5))

            # Colormap starting from 0, centered at 1.0
            vmin = 0.0
            vmax = max(ratio_df.max().max(), 2.0)
            vcenter = 1.0

            norm = TwoSlopeNorm(vmin=vmin, vcenter=vcenter, vmax=vmax)

            sns.heatmap(
                ratio_df,
                ax=ax,
                annot=True,
                fmt=".2f",
                cmap="RdBu_r",
                norm=norm,
                linewidths=0.5,
                cbar_kws={"label": "Polarization Ratio (Theta/Phi)"},
                annot_kws={"fontsize": 8},
            )

            ax.set_xlabel("Tissue Group", fontsize=9)
            ax.set_ylabel("Incident Direction", fontsize=9)
            ax.set_title(f"{int(freq)} MHz", fontsize=10, fontweight="bold")
            ax.tick_params(axis="both", labelsize=8, which="both")
            ax.minorticks_off()  # Remove minor ticks

            plt.tight_layout()

            filename = f"heatmap_polarization_ratio_{int(freq)}MHz"
            self._save_figure(fig, "heatmap", filename, dpi=200)

        logging.getLogger("progress").info(
            f"  - Generated {len(frequencies)} per-frequency polarization ratio heatmaps",
            extra={"log_type": "info"},
        )
