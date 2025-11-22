import logging
import os
from typing import TYPE_CHECKING

import pandas as pd

from .base_strategy import BaseAnalysisStrategy

if TYPE_CHECKING:
    from ..config import Config
    from .analyzer import Analyzer
    from .plotter import Plotter


def _clean_tissue_name(tissue_name: str) -> str:
    """Removes phantom identifiers from tissue names.

    Removes patterns like "(Thelonious_6y_V6)", "(Thelonious_by_V6)", etc.
    This should be applied early in data extraction to avoid repeated cleaning.

    Args:
        tissue_name: Original tissue name (may contain phantom identifier).

    Returns:
        Cleaned tissue name without phantom identifier.
    """
    if not tissue_name:
        return tissue_name

    import re

    # Pattern matches: (PhantomName_...) or (PhantomName) at the end
    pattern = r"\s*\([^)]*\)\s*$"
    cleaned = re.sub(pattern, "", tissue_name).strip()
    return cleaned if cleaned else tissue_name


class FarFieldAnalysisStrategy(BaseAnalysisStrategy):
    """Analysis strategy for far-field simulations.

    Handles result loading, normalization, and plot generation for far-field
    studies with incident directions and polarizations.
    """

    def __init__(self, config: "Config", phantom_name: str, analysis_config: dict | None = None):
        """Initializes the far-field analysis strategy.

        Args:
            config: Configuration object.
            phantom_name: Phantom model name being analyzed.
            analysis_config: Optional dictionary with plot names as keys and boolean values.
        """
        super().__init__(config, phantom_name, analysis_config)

    def get_results_base_dir(self) -> str:
        """Returns base directory for far-field results."""
        return os.path.join(self.base_dir, "results", "far_field", self.phantom_name)

    def get_plots_dir(self) -> str:
        """Returns directory for far-field plots."""
        return os.path.join(self.base_dir, "plots", "far_field", self.phantom_name)

    def load_and_process_results(self, analyzer: "Analyzer"):
        """Iterates through far-field results and processes each one."""
        frequencies = self.config["frequencies_mhz"]
        far_field_params = self.config["far_field_setup.environmental"]
        if not far_field_params:
            return
        incident_directions = far_field_params.get("incident_directions", [])
        polarizations = far_field_params.get("polarizations", [])

        if not frequencies:
            return

        for freq in frequencies:
            if not incident_directions:
                continue
            for direction_name in incident_directions:
                if not polarizations:
                    continue
                for polarization_name in polarizations:
                    placement_name = f"environmental_{direction_name}_{polarization_name}"
                    analyzer._process_single_result(freq, "environmental", placement_name, "")

    def get_normalization_factor(self, frequency_mhz: int, simulated_power_w: float) -> float:
        """Returns normalization factor for far-field (always 1.0).

        Far-field simulations are normalized to 1 W/m^2 in the simulation itself,
        so no additional normalization is needed.
        """
        return 1.0

    def extract_data(
        self,
        pickle_data: dict,
        frequency_mhz: int,
        placement_name: str,
        scenario_name: str,
        sim_power: float,
        norm_factor: float,
        sar_results: dict | None = None,
    ) -> tuple[dict, list]:
        summary_results = pickle_data.get("summary_results", {})
        detailed_df = pickle_data.get("detailed_sar_stats")

        result_entry = {
            "frequency_mhz": frequency_mhz,
            "placement": placement_name,
            "scenario": scenario_name,
            "input_power_w": sim_power,
            "SAR_whole_body": summary_results.get("whole_body_sar", pd.NA),
            "peak_sar": summary_results.get("peak_sar_10g_W_kg", pd.NA),
        }

        # Extract power balance data if available
        power_balance = None
        if sar_results and "power_balance" in sar_results:
            power_balance = sar_results["power_balance"]
        elif summary_results and "power_balance" in summary_results:
            power_balance = summary_results["power_balance"]

        if power_balance:
            result_entry["power_balance_pct"] = power_balance.get("Balance", pd.NA)
            result_entry["power_pin_W"] = power_balance.get("Pin", pd.NA)
            result_entry["power_diel_loss_W"] = power_balance.get("DielLoss", pd.NA)
            result_entry["power_rad_W"] = power_balance.get("RadPower", pd.NA)
            result_entry["power_sibc_loss_W"] = power_balance.get("SIBCLoss", pd.NA)

        organ_entries = []
        if detailed_df is not None:
            peak_sar_col = "Peak Spatial-Average SAR[IEEE/IEC62704-1] (10g)"
            for _, row in detailed_df.iterrows():
                organ_entries.append(
                    {
                        "frequency_mhz": frequency_mhz,
                        "placement": placement_name,
                        "tissue": _clean_tissue_name(row["Tissue"]),  # Clean tissue name early
                        "mass_avg_sar_mw_kg": row["Mass-Averaged SAR"] * 1000,  # Already normalized in extractor
                        "peak_sar_10g_mw_kg": row.get(peak_sar_col, pd.NA) * 1000,  # Already normalized
                    }
                )
        return result_entry, organ_entries

    def apply_bug_fixes(self, result_entry: dict) -> dict:
        """No bug fixes needed for far-field data."""
        return result_entry

    def calculate_summary_stats(self, results_df: pd.DataFrame) -> pd.DataFrame:
        """Calculates summary statistics for far-field results."""
        summary = results_df.groupby("frequency_mhz").mean(numeric_only=True)
        return pd.DataFrame(summary)

    def generate_plots(
        self,
        analyzer: "Analyzer",
        plotter: "Plotter",
        results_df: pd.DataFrame,
        all_organ_results_df: pd.DataFrame,
    ):
        logging.getLogger("progress").info(
            "\n--- Generating plots for far-field analysis ---",
            extra={"log_type": "header"},
        )
        summary_stats = self.calculate_summary_stats(results_df)
        if self.should_generate_plot("plot_whole_body_sar_bar"):
            plotter.plot_whole_body_sar_bar(summary_stats)
        if self.should_generate_plot("plot_peak_sar_line"):
            plotter.plot_peak_sar_line(summary_stats)
        if self.should_generate_plot("plot_far_field_distribution_boxplot"):
            plotter.plot_far_field_distribution_boxplot(results_df, metric="SAR_whole_body")
            plotter.plot_far_field_distribution_boxplot(results_df, metric="peak_sar")

        # Prepare data for heatmaps
        organ_sar_df = all_organ_results_df.groupby(["tissue", "frequency_mhz"]).agg(avg_sar=("mass_avg_sar_mw_kg", "mean")).reset_index()

        organ_pssar_df = all_organ_results_df.groupby(["tissue", "frequency_mhz"])["peak_sar_10g_mw_kg"].mean().reset_index()

        group_summary_data = []
        # Use tissue_group_composition from pickle files (exact tissue names)
        if not analyzer.tissue_group_composition:
            logging.getLogger("progress").warning(
                "No tissue_group_composition found in pickle files. Skipping tissue group heatmaps.",
                extra={"log_type": "warning"},
            )
        else:
            # Convert sets to lists for processing
            tissue_groups = {group_name: list(tissues) for group_name, tissues in analyzer.tissue_group_composition.items()}

            for group_name, tissues in tissue_groups.items():
                if not tissues:
                    continue

                # Exact tissue name matching (from pickle files)
                group_df = all_organ_results_df[all_organ_results_df["tissue"].isin(tissues)]

                if not group_df.empty:
                    summary = (
                        group_df.groupby("frequency_mhz")
                        .agg(
                            avg_sar=("mass_avg_sar_mw_kg", "mean"),
                            peak_sar_10g_mw_kg=("peak_sar_10g_mw_kg", "mean"),
                        )
                        .reset_index()
                    )
                    summary["group"] = group_name.replace("_group", "").capitalize()
                    group_summary_data.append(summary)

        group_summary_df = pd.concat(group_summary_data, ignore_index=True) if group_summary_data else pd.DataFrame()

        if not group_summary_df.empty and analyzer.tissue_group_composition:
            group_sar_summary = group_summary_df[["group", "frequency_mhz", "avg_sar"]]
            group_pssar_summary = group_summary_df[["group", "frequency_mhz", "peak_sar_10g_mw_kg"]]

            # Use tissue_group_composition for plotter (convert sets to lists)
            plotter_tissue_groups = {group_name: list(tissues) for group_name, tissues in analyzer.tissue_group_composition.items()}

            if self.should_generate_plot("plot_peak_sar_heatmap"):
                plotter.plot_peak_sar_heatmap(
                    pd.DataFrame(organ_sar_df),
                    pd.DataFrame(group_sar_summary),
                    plotter_tissue_groups,
                    value_col="avg_sar",
                    title="Average SAR",
                )
                plotter.plot_peak_sar_heatmap(
                    pd.DataFrame(organ_pssar_df),
                    pd.DataFrame(group_pssar_summary),
                    plotter_tissue_groups,
                    value_col="peak_sar_10g_mw_kg",
                    title="Peak SAR 10g",
                )
        else:
            logging.getLogger("progress").warning(
                "  - WARNING: No data found for tissue groups, skipping heatmaps.",
                extra={"log_type": "warning"},
            )

        # Generate power balance plots for all results
        if self.should_generate_plot("plot_power_balance_overview"):
            plotter.plot_power_balance_overview(results_df)
