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
