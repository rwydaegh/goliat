"""Report generation and saving."""

import os
import pickle
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from ..results_extractor import ResultsExtractor


class Reporter:
    """Generates and saves detailed reports from extraction results.

    Creates Pickle files for programmatic access and HTML files for human
    readability. Includes SAR statistics, tissue groups, and peak SAR details.
    """

    def __init__(self, parent: "ResultsExtractor"):
        """Sets up the reporter.

        Args:
            parent: Parent ResultsExtractor instance.
        """
        self.parent = parent

    def save_reports(
        self,
        df: pd.DataFrame,
        tissue_groups: dict,
        group_sar_stats: dict,
        results_data: dict,
    ):
        """Saves Pickle and HTML reports to the results directory.

        Args:
            df: DataFrame with detailed SAR statistics per tissue.
            tissue_groups: Dict mapping group names to tissue lists.
            group_sar_stats: Dict with aggregated SAR stats per group.
            results_data: Dict with summary results and metadata.
        """
        results_dir = self._get_results_dir()
        os.makedirs(results_dir, exist_ok=True)

        self._save_pickle_report(results_dir, df, tissue_groups, group_sar_stats, results_data)
        self._save_html_report(results_dir, df, tissue_groups, group_sar_stats, results_data)

    def _get_results_dir(self) -> str:
        """Returns the results directory path for current simulation."""
        base_path = os.path.join(
            self.parent.config.base_dir,
            "results",
            self.parent.study_type,
            self.parent.phantom_name,
            f"{self.parent.frequency_mhz}MHz",
        )

        if self.parent.study_type == "far_field":
            # For far-field, placement_name is constructed from scenario, polarization, and direction
            # e.g., environmental_theta_x_pos
            placement_name = f"{self.parent.placement_name}"
            return os.path.join(base_path, placement_name)

        # For near-field, placement_name is already the final directory component
        return os.path.join(base_path, self.parent.placement_name)

    def _save_pickle_report(
        self,
        results_dir: str,
        df: pd.DataFrame,
        tissue_groups: dict,
        group_sar_stats: dict,
        results_data: dict,
    ):
        """Saves comprehensive data in pickle format for programmatic access."""
        pickle_data = {
            "detailed_sar_stats": df,
            "tissue_group_composition": tissue_groups,
            "grouped_sar_stats": group_sar_stats,
            "summary_results": results_data,
            "peak_sar_details": results_data.get("peak_sar_details", {}),
            "point_sensor_data": results_data.get("point_sensor_data", {}),
        }
        deliverables = self.parent.get_deliverable_filenames()
        pickle_filepath = os.path.join(results_dir, deliverables["pkl"])

        with open(pickle_filepath, "wb") as f:
            pickle.dump(pickle_data, f)

        self.parent._log(f"  - Pickle report saved to: {pickle_filepath}", log_type="info")

    def _save_html_report(
        self,
        results_dir: str,
        df: pd.DataFrame,
        tissue_groups: dict,
        group_sar_stats: dict,
        results_data: dict,
    ):
        """Saves human-readable HTML report with tables and summaries."""
        html_content = self._build_html_content(df, tissue_groups, group_sar_stats, results_data)
        deliverables = self.parent.get_deliverable_filenames()
        html_filepath = os.path.join(results_dir, deliverables["html"])

        with open(html_filepath, "w", encoding="utf-8") as f:
            f.write(html_content)

        self.parent._log(f"  - HTML report saved to: {html_filepath}", log_type="info")

    def _build_html_content(
        self,
        df: pd.DataFrame,
        tissue_groups: dict,
        group_sar_stats: dict,
        results_data: dict,
    ) -> str:
        """Builds HTML content from DataFrames and dicts."""
        html_content = df.to_html(index=False, border=1)

        html_content += "<h2>Tissue Group Composition</h2>"
        html_content += pd.DataFrame.from_dict(tissue_groups, orient="index").to_html()

        html_content += "<h2>Grouped SAR Statistics</h2>"
        html_content += pd.DataFrame.from_dict(group_sar_stats, orient="index").to_html()

        html_content += "<h2>Peak SAR Details</h2>"
        peak_sar_df = pd.DataFrame.from_dict(results_data.get("peak_sar_details", {}), orient="index")
        peak_sar_df.columns = ["Value"]
        peak_sar_df.index.name = "Parameter"
        html_content += peak_sar_df.to_html()

        return html_content
