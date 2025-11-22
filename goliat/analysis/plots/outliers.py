"""Outlier detection and visualization."""

import logging

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .base import BasePlotter, METRIC_LABELS


class OutliersPlotter(BasePlotter):
    """Generates outlier detection plots for SAR analysis."""

    def identify_outliers(
        self,
        results_df: pd.DataFrame,
        metrics: str | list[str],
        scenario_name: str | None = None,
        method: str = "iqr",
        threshold: float = 1.5,
    ):
        """Identifies and visualizes outliers in SAR metrics.

        Args:
            results_df: DataFrame with simulation results.
            metrics: Single metric column name or list of metric column names to check for outliers.
            scenario_name: Optional scenario name for filtering.
            method: Method for outlier detection ('iqr' for Interquartile Range, 'zscore' for Z-score).
            threshold: Threshold multiplier for IQR method or Z-score threshold.

        Returns:
            DataFrame containing outlier rows, or None if no outliers found.
        """
        plot_df = results_df.copy()

        if scenario_name:
            plot_df = plot_df[plot_df["scenario"] == scenario_name].copy()

        if plot_df.empty:
            return pd.DataFrame()  # Return empty DataFrame instead of None

        # Normalize metrics to list
        if isinstance(metrics, str):
            metrics = [metrics]

        outlier_summary = []
        all_outlier_dfs = []  # Collect all outlier DataFrames

        for metric in metrics:
            if metric not in plot_df.columns:
                continue

            metric_data = plot_df[metric].dropna()
            if metric_data.empty:
                continue

            if method == "iqr":
                Q1 = metric_data.quantile(0.25)
                Q3 = metric_data.quantile(0.75)
                IQR = Q3 - Q1
                lower_bound = Q1 - threshold * IQR
                upper_bound = Q3 + threshold * IQR
                outliers = plot_df[(plot_df[metric] < lower_bound) | (plot_df[metric] > upper_bound)]
            elif method == "zscore":
                mean_val = metric_data.mean()
                std_val = metric_data.std()
                if std_val == 0:
                    continue
                z_scores = np.abs((plot_df[metric] - mean_val) / std_val)
                outliers = plot_df[z_scores > threshold]
            else:
                continue

            if not outliers.empty:
                outlier_summary.append(
                    {
                        "metric": metric,
                        "count": len(outliers),
                        "outliers": outliers,
                    }
                )
                all_outlier_dfs.append(outliers)

        if not outlier_summary:
            logging.getLogger("progress").info(
                f"  - No outliers detected for metrics: {', '.join(metrics)}",
                extra={"log_type": "info"},
            )
            return pd.DataFrame()  # Return empty DataFrame instead of None

        # Collect all outlier rows into a single DataFrame
        if all_outlier_dfs:
            all_outliers = pd.concat(all_outlier_dfs, ignore_index=True)
            # Drop duplicates based on hashable columns only (avoid unhashable types like dicts)
            # Get list of columns that are hashable (numeric, string, etc.)
            hashable_cols = []
            for col in all_outliers.columns:
                try:
                    # Try to hash a sample value to check if column is hashable
                    sample_val = all_outliers[col].dropna().iloc[0] if not all_outliers[col].dropna().empty else None
                    if sample_val is not None:
                        hash(sample_val)
                        hashable_cols.append(col)
                except (TypeError, IndexError):
                    # Column contains unhashable types, skip it
                    continue

            # Drop duplicates using only hashable columns, or all columns if none are hashable
            if hashable_cols:
                try:
                    all_outliers = all_outliers.drop_duplicates(subset=hashable_cols)
                except (TypeError, ValueError):
                    # If still fails, just return all outliers without deduplication
                    pass
            # If no hashable columns, just return all outliers (no deduplication possible)
        else:
            all_outliers = pd.DataFrame()

        # Create visualization
        n_metrics = len(outlier_summary)
        fig, axes = plt.subplots(n_metrics, 1, figsize=(3.5, 2.0 * n_metrics))  # IEEE single-column width
        if n_metrics == 1:
            axes = [axes]

        for idx, summary in enumerate(outlier_summary):
            ax = axes[idx]
            metric = summary["metric"]
            outliers = summary["outliers"]

            # Boxplot with outliers highlighted
            plot_data = plot_df[metric].dropna()
            bp = ax.boxplot([plot_data], vert=True, patch_artist=True, showfliers=True)
            bp["boxes"][0].set_facecolor("lightblue")
            bp["boxes"][0].set_alpha(0.7)

            # Highlight outliers
            outlier_values = outliers[metric].dropna()
            if not outlier_values.empty:
                ax.scatter([1] * len(outlier_values), outlier_values.values, color="red", s=30, alpha=0.7, marker="x", label="Outliers")

            ax.set_ylabel(f"{METRIC_LABELS.get(metric, metric)} (mW kg$^{{-1}}$)")
            # Don't set title on plot - will be in caption file
            ax.grid(True, alpha=0.3, axis="y")
            if not outlier_values.empty:
                ax.legend()
            # Set y-axis to start at 0 and go to max + 5%
            y_max = ax.get_ylim()[1]
            ax.set_ylim(0, y_max * 1.05)

        plt.tight_layout()

        filename_base = f"outliers_{method}_{scenario_name or 'all'}"
        metrics_list = ", ".join(str(METRIC_LABELS.get(s["metric"], s["metric"])) for s in outlier_summary)
        phantom_name_formatted = self.phantom_name.capitalize() if self.phantom_name else "the phantom"
        caption = f"The outlier detection plots show metrics {metrics_list} using {method} method for the {self._format_scenario_name(scenario_name) if scenario_name else 'all scenarios'} scenario for {phantom_name_formatted}. Outliers are marked with red 'x' markers."
        title_full = self._get_title_with_phantom(f"outlier detection ({method} method)")
        filename = self._save_figure(fig, "outliers", filename_base, title=title_full, caption=caption, dpi=300)

        # Save CSV data
        if not all_outliers.empty:
            self._save_csv_data(all_outliers, "outliers", filename_base)
        logging.getLogger("progress").info(
            f"  - Generated outlier detection plot: {filename}",
            extra={"log_type": "success"},
        )

        # Return DataFrame of all outliers
        return all_outliers
