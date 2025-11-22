"""Correlation plot generators."""

import logging

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from .base import BasePlotter, METRIC_LABELS, LEGEND_LABELS


class CorrelationPlotter(BasePlotter):
    """Generates correlation plots for SAR analysis."""

    def plot_correlation_head_vs_eye_sar(
        self,
        results_df: pd.DataFrame,
        scenario_name: str = "front_of_eyes",
    ):
        """Creates scatter plot showing correlation between Head SAR and Eye psSAR10g with linear regression.

        Args:
            results_df: DataFrame with columns: ['SAR_head', 'psSAR10g_eyes', 'frequency_mhz', 'scenario']
            scenario_name: Scenario to filter for (default: 'front_of_eyes').
        """
        from scipy import stats

        if scenario_name:
            plot_df = results_df[results_df["scenario"] == scenario_name].copy()
        else:
            plot_df = results_df.copy()

        plot_df["SAR_head"] = pd.to_numeric(plot_df["SAR_head"], errors="coerce")
        plot_df["psSAR10g_eyes"] = pd.to_numeric(plot_df["psSAR10g_eyes"], errors="coerce")
        correlation_df = plot_df.dropna(subset=["SAR_head", "psSAR10g_eyes"])

        if correlation_df.empty:
            logging.getLogger("progress").warning(
                f"No valid data for correlation plot (scenario: {scenario_name})",
                extra={"log_type": "warning"},
            )
            return

        # Perform linear regression
        slope, intercept, r_value, p_value, std_err = stats.linregress(correlation_df["SAR_head"], correlation_df["psSAR10g_eyes"])
        r_squared = r_value**2

        fig, ax = plt.subplots(figsize=(3.5, 2.5))  # IEEE single-column width

        # Scatter plot colored by frequency
        if "frequency_mhz" in correlation_df.columns:
            scatter = ax.scatter(
                correlation_df["SAR_head"],
                correlation_df["psSAR10g_eyes"],
                c=correlation_df["frequency_mhz"],
                cmap="jet",
                s=30,
                alpha=0.7,
            )
            cbar = plt.colorbar(scatter, ax=ax)
            cbar.set_label("Frequency (MHz)")
        else:
            ax.scatter(correlation_df["SAR_head"], correlation_df["psSAR10g_eyes"], s=30, alpha=0.7)

        # Plot regression line
        x_vals = np.array(ax.get_xlim())
        y_vals = intercept + slope * x_vals
        ax.plot(x_vals, y_vals, "--", color="red", linewidth=2, label=f"Linear Fit (R²={r_squared:.4f})")

        formatted_scenario = self._format_scenario_name(scenario_name)
        base_title = "correlation between head SAR and eye psSAR10g"
        title_full = self._get_title_with_phantom(base_title, scenario_name)
        # Don't set title on plot - will be in caption file
        ax.set_xlabel(self._format_axis_label("Normalized head SAR", r"mW kg$^{-1}$"))
        ax.set_ylabel(self._format_axis_label("Normalized psSAR10g eyes", r"mW kg$^{-1}$"))

        # Add R² value annotation
        ax.text(
            0.98,
            0.98,
            f"R² = {r_squared:.4f}\np = {p_value:.4f}",
            transform=ax.transAxes,
            fontsize=8,
            verticalalignment="top",
            horizontalalignment="right",
            bbox=dict(boxstyle="square", facecolor="white", edgecolor="black", linewidth=0.5, pad=0.3),
        )

        ax.legend()
        ax.grid(True, alpha=0.3)

        plt.tight_layout()

        filename_base = f"correlation_head_vs_eye_sar_{scenario_name}"
        phantom_name_formatted = self.phantom_name.capitalize() if self.phantom_name else "the phantom"
        caption = f"The scatter plot shows the correlation between normalized head SAR and normalized eye psSAR10g values for the {formatted_scenario} scenario for {phantom_name_formatted}. Points are colored by frequency. The red dashed line shows the linear fit with R² and p-value annotations."
        filename = self._save_figure(fig, "correlation", filename_base, title=title_full, caption=caption, dpi=300)

        # Save CSV data
        csv_data = correlation_df[["SAR_head", "psSAR10g_eyes"]].copy()
        if "frequency_mhz" in correlation_df.columns:
            csv_data["frequency_mhz"] = correlation_df["frequency_mhz"]
        self._save_csv_data(csv_data, "correlation", filename_base)
        logging.getLogger("progress").info(
            f"  - Generated correlation plot: {filename}",
            extra={"log_type": "success"},
        )

    def plot_tissue_group_correlation_matrix(
        self,
        results_df: pd.DataFrame,
        scenario_name: str | None = None,
    ):
        """Creates heatmap showing correlation coefficients between different tissue group SAR values.

        Args:
            results_df: DataFrame with tissue group SAR columns (SAR_eyes, SAR_brain, etc.)
            scenario_name: Optional scenario name for filtering.
        """
        # Filter by scenario if provided
        if scenario_name:
            plot_df = results_df[results_df["scenario"] == scenario_name].copy()
        else:
            plot_df = results_df.copy()

        # Find all SAR columns
        sar_cols = [col for col in plot_df.columns if col.startswith("SAR_") or col.startswith("psSAR10g_")]
        sar_cols = [col for col in sar_cols if col in plot_df.columns]

        # Exclude columns that are all NaN
        valid_sar_cols = []
        for col in sar_cols:
            if not plot_df[col].isna().all():
                valid_sar_cols.append(col)

        if len(valid_sar_cols) < 2:
            logging.getLogger("progress").warning(
                "Not enough valid SAR columns for correlation matrix.",
                extra={"log_type": "warning"},
            )
            return

        # Convert pd.NA to np.nan and drop rows with all NaN
        sar_data = plot_df[valid_sar_cols].copy()
        sar_data = sar_data.replace(pd.NA, np.nan)
        sar_data = sar_data.dropna(how="all")

        if sar_data.empty or len(sar_data) < 2:
            logging.getLogger("progress").warning(
                "Not enough valid data for correlation matrix.",
                extra={"log_type": "warning"},
            )
            return

        # Calculate correlation matrix (only numeric columns)
        # Use pairwise deletion to handle missing values better
        correlation_matrix = sar_data.corr(method="pearson", min_periods=2)

        # Create human-readable labels for columns
        def get_human_readable_label(col_name):
            """Convert column name to human-readable label."""
            # Try METRIC_LABELS first (full labels)
            if col_name in METRIC_LABELS:
                return METRIC_LABELS[col_name]
            # Try LEGEND_LABELS (trimmed labels)
            if col_name in LEGEND_LABELS:
                label = LEGEND_LABELS[col_name]
                # Add "SAR" or "psSAR10g" prefix if needed for clarity
                if col_name.startswith("SAR_"):
                    return f"{label} SAR"
                elif col_name.startswith("psSAR10g_"):
                    return f"psSAR10g {label}"
                return label
            # Fallback: format the column name
            return col_name.replace("SAR_", "").replace("psSAR10g_", "psSAR10g ").replace("_", " ").title()

        # Rename columns and index with human-readable labels
        correlation_matrix_labeled = correlation_matrix.copy()
        readable_labels = [get_human_readable_label(col) for col in correlation_matrix.columns]
        correlation_matrix_labeled.columns = readable_labels
        correlation_matrix_labeled.index = readable_labels

        # Create heatmap
        fig, ax = plt.subplots(figsize=(7.16, 5.5))  # IEEE two-column width for correlation matrix
        sns.heatmap(
            correlation_matrix_labeled,
            annot=True,
            fmt=".3f",
            cmap="RdBu_r",
            center=0,
            vmin=-1,
            vmax=1,
            square=True,
            linewidths=0.5,
            cbar_kws={"label": "Correlation Coefficient"},
            ax=ax,
        )

        base_title = "tissue group correlation matrix"
        title_full = self._get_title_with_phantom(base_title, scenario_name)
        # Don't set title on plot - will be in caption file
        plt.tight_layout()

        filename_base = f"correlation_matrix_tissue_groups_{scenario_name}" if scenario_name else "correlation_matrix_tissue_groups"
        phantom_name_formatted = self.phantom_name.capitalize() if self.phantom_name else "the phantom"
        caption = f"The heatmap shows Pearson correlation coefficients between different tissue group SAR values for the {self._format_scenario_name(scenario_name) if scenario_name else 'all scenarios'} scenario for {phantom_name_formatted}. Values range from -1 (perfect negative correlation) to +1 (perfect positive correlation)."
        filename = self._save_figure(fig, "correlation", filename_base, title=title_full, caption=caption, dpi=300)

        # Save CSV data
        self._save_csv_data(correlation_matrix, "correlation", filename_base)
        logging.getLogger("progress").info(
            f"  - Generated correlation matrix: {filename}",
            extra={"log_type": "success"},
        )
