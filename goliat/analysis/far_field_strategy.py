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
        """Returns normalization factor for far-field.

        Far-field simulations run at E = 1 V/m (power density = 1.326 mW/m²).
        To normalize to 1 W/m² (our "1 W" convention for comparison with near-field),
        we scale by 754 (since SAR scales as E², and E for 1 W/m² is 27.46 V/m).

        See docs/technical/power_normalization_philosophy.md for full derivation.
        """
        return 754.0

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
        grouped_stats = pickle_data.get("grouped_sar_stats", {})
        detailed_df = pickle_data.get("detailed_sar_stats")

        result_entry = {
            "frequency_mhz": frequency_mhz,
            "placement": placement_name,
            "scenario": scenario_name,
            "input_power_w": sim_power,
            "SAR_whole_body": summary_results.get("whole_body_sar", pd.NA) * norm_factor
            if pd.notna(summary_results.get("whole_body_sar"))
            else pd.NA,
            "peak_sar": summary_results.get("peak_sar_10g_W_kg", pd.NA) * norm_factor
            if pd.notna(summary_results.get("peak_sar_10g_W_kg"))
            else pd.NA,
        }

        # Extract psSAR10g for each tissue group (brain, eyes, skin, genitals)
        # This mirrors the near-field strategy for symmetry
        for group_name, stats in grouped_stats.items():
            if isinstance(stats, dict):
                key = f"psSAR10g_{group_name.replace('_group', '')}"
                peak_sar = stats.get("peak_sar", pd.NA)
                result_entry[key] = peak_sar * norm_factor * 1000 if pd.notna(peak_sar) else pd.NA

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
                        "mass_avg_sar_mw_kg": row["Mass-Averaged SAR"] * norm_factor * 1000,
                        "peak_sar_10g_mw_kg": row.get(peak_sar_col, pd.NA) * norm_factor * 1000
                        if pd.notna(row.get(peak_sar_col))
                        else pd.NA,
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

    def _add_tissue_group_sar(self, results_df: pd.DataFrame, all_organ_results_df: pd.DataFrame, analyzer: "Analyzer") -> pd.DataFrame:
        """Aggregates organ-level SAR by tissue groups and adds to results_df.

        Creates SAR_eyes, SAR_brain, SAR_skin, SAR_genitals columns by averaging
        mass_avg_sar_mw_kg across tissues in each group.

        Args:
            results_df: DataFrame with main aggregated results.
            all_organ_results_df: DataFrame with organ-level results.
            analyzer: Analyzer instance containing tissue_group_composition.

        Returns:
            results_df with added SAR_{group} columns.
        """
        if all_organ_results_df.empty or "mass_avg_sar_mw_kg" not in all_organ_results_df.columns:
            return results_df

        results_df = results_df.copy()

        if not analyzer.tissue_group_composition:
            logging.getLogger("progress").warning(
                "No tissue_group_composition found. Skipping tissue group SAR aggregation.",
                extra={"log_type": "warning"},
            )
            return results_df

        tissue_groups = {group_name: list(tissues) for group_name, tissues in analyzer.tissue_group_composition.items()}

        group_sar_data = []
        for group_name, tissue_list in tissue_groups.items():
            group_organs = all_organ_results_df[all_organ_results_df["tissue"].isin(tissue_list)]

            if not group_organs.empty:
                group_avg = group_organs.groupby(["placement", "frequency_mhz"])["mass_avg_sar_mw_kg"].mean().reset_index()
                group_avg["group"] = group_name.replace("_group", "")
                group_sar_data.append(group_avg)

        expected_sar_columns = ["SAR_brain", "SAR_skin", "SAR_genitals", "SAR_eyes"]

        if group_sar_data:
            combined_group_sar = pd.concat(group_sar_data, ignore_index=True)
            group_sar_pivot = combined_group_sar.pivot_table(
                index=["placement", "frequency_mhz"], columns="group", values="mass_avg_sar_mw_kg", aggfunc="mean"
            ).reset_index()
            rename_dict = {col: f"SAR_{col}" for col in group_sar_pivot.columns if col not in ["placement", "frequency_mhz"]}
            group_sar_pivot = group_sar_pivot.rename(columns=rename_dict)
            results_df = results_df.merge(group_sar_pivot, on=["placement", "frequency_mhz"], how="left")

        for col in expected_sar_columns:
            if col not in results_df.columns:
                results_df[col] = pd.NA

        return results_df

    def generate_plots(
        self,
        analyzer: "Analyzer",
        plotter: "Plotter",
        results_df: pd.DataFrame,
        all_organ_results_df: pd.DataFrame,
    ):
        """Generates comprehensive plots for far-field analysis.

        Includes bar charts, line plots, boxplots, heatmaps, ranking plots,
        CDF plots, correlation matrices, bubble plots, and tissue analysis.
        """
        logging.getLogger("progress").info(
            "\n--- Generating plots for far-field analysis ---",
            extra={"log_type": "header"},
        )

        # Add tissue group SAR columns to results_df
        results_df = self._add_tissue_group_sar(results_df, all_organ_results_df, analyzer)

        summary_stats = self.calculate_summary_stats(results_df)

        # ============================================================================
        # Basic Bar and Line Plots
        # ============================================================================
        if self.should_generate_plot("plot_whole_body_sar_bar"):
            plotter.plot_whole_body_sar_bar(summary_stats)
        if self.should_generate_plot("plot_peak_sar_line"):
            plotter.plot_peak_sar_line(summary_stats)
        if self.should_generate_plot("plot_far_field_distribution_boxplot"):
            plotter.plot_far_field_distribution_boxplot(results_df, metric="SAR_whole_body")
            plotter.plot_far_field_distribution_boxplot(results_df, metric="peak_sar")
            # Also generate boxplots for tissue groups (symmetric with near-field)
            for metric in ["SAR_brain", "SAR_eyes", "SAR_skin", "SAR_genitals"]:
                if metric in results_df.columns and results_df[metric].notna().any():
                    plotter.plot_far_field_distribution_boxplot(results_df, metric=metric)

        # Tissue group bar plots (symmetric with near-field: brain, eyes, skin, genitals)
        if self.should_generate_plot("plot_average_sar_bar"):
            plotter.plot_average_sar_bar("environmental", summary_stats, None, results_df)
        if self.should_generate_plot("plot_average_pssar_bar"):
            plotter.plot_average_pssar_bar("environmental", summary_stats, None, results_df)

        # ============================================================================
        # Individual Variation Line Plots (one line per direction/polarization)
        # ============================================================================
        sar_columns_for_lines = ["SAR_whole_body", "SAR_brain", "SAR_skin", "SAR_eyes", "SAR_genitals"]
        if self.should_generate_plot("plot_sar_line_individual_variations"):
            for metric_col in sar_columns_for_lines:
                if metric_col in results_df.columns and results_df[metric_col].notna().any():
                    plotter.plot_sar_line_individual_variations(
                        results_df,
                        scenario_name=None,  # No scenario for far-field
                        metric_column=metric_col,
                    )

        # psSAR10g individual variation plots for tissue groups (symmetric with near-field)
        pssar_columns = [col for col in results_df.columns if col.startswith("psSAR10g")]
        if self.should_generate_plot("plot_pssar_line_individual_variations"):
            for metric_col in pssar_columns:
                if metric_col in results_df.columns and results_df[metric_col].notna().any():
                    plotter.plot_pssar_line_individual_variations(
                        results_df,
                        scenario_name=None,
                        metric_column=metric_col,
                    )

        # ============================================================================
        # Heatmaps
        # ============================================================================
        organ_sar_df = all_organ_results_df.groupby(["tissue", "frequency_mhz"]).agg(avg_sar=("mass_avg_sar_mw_kg", "mean")).reset_index()
        organ_pssar_df = all_organ_results_df.groupby(["tissue", "frequency_mhz"])["peak_sar_10g_mw_kg"].mean().reset_index()

        group_summary_data = []
        if analyzer.tissue_group_composition:
            tissue_groups = {group_name: list(tissues) for group_name, tissues in analyzer.tissue_group_composition.items()}

            for group_name, tissues in tissue_groups.items():
                if not tissues:
                    continue
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

            if not group_summary_df.empty:
                plotter_tissue_groups = {group_name: list(tissues) for group_name, tissues in analyzer.tissue_group_composition.items()}

                if self.should_generate_plot("plot_peak_sar_heatmap"):
                    plotter.plot_peak_sar_heatmap(
                        pd.DataFrame(organ_sar_df),
                        group_summary_df[["group", "frequency_mhz", "avg_sar"]],
                        plotter_tissue_groups,
                        value_col="avg_sar",
                        title="Average SAR",
                    )
                    plotter.plot_peak_sar_heatmap(
                        pd.DataFrame(organ_pssar_df),
                        group_summary_df[["group", "frequency_mhz", "peak_sar_10g_mw_kg"]],
                        plotter_tissue_groups,
                        value_col="peak_sar_10g_mw_kg",
                        title="Peak SAR 10g",
                    )
                # SAR heatmap (symmetric with NF)
                if self.should_generate_plot("plot_sar_heatmap"):
                    plotter.plot_sar_heatmap(
                        pd.DataFrame(organ_sar_df),
                        group_summary_df[["group", "frequency_mhz", "avg_sar"]],
                        plotter_tissue_groups,
                    )

        # ============================================================================
        # SAR/psSAR Line Plots (symmetric with NF)
        # ============================================================================
        if self.should_generate_plot("plot_sar_line"):
            plotter.plot_sar_line("environmental", summary_stats)
        if self.should_generate_plot("plot_pssar_line"):
            plotter.plot_pssar_line("environmental", summary_stats)

        # ============================================================================
        # SAR Distribution Boxplots (symmetric with NF)
        # ============================================================================
        if self.should_generate_plot("plot_sar_distribution_boxplots"):
            plotter.plot_sar_distribution_boxplots("environmental", results_df)

        # ============================================================================
        # Power Balance Plots
        # ============================================================================
        if self.should_generate_plot("plot_power_balance_overview"):
            plotter.plot_power_balance_overview(results_df)
        if self.should_generate_plot("plot_power_efficiency_trends"):
            plotter.plot_power_efficiency_trends(results_df, scenario_name=None)
        if self.should_generate_plot("plot_power_absorption_distribution"):
            plotter.plot_power_absorption_distribution(results_df, scenario_name=None)

        # ============================================================================
        # Ranking Plots (Top 20 Tissues)
        # ============================================================================
        if not all_organ_results_df.empty and self.should_generate_plot("plot_top20_tissues_ranking"):
            logging.getLogger("progress").info(
                "  - Generating ranking plots (top 20 tissues)...",
                extra={"log_type": "info"},
            )
            plotter.plot_top20_tissues_ranking(all_organ_results_df, metric="mass_avg_sar_mw_kg", scenario_name=None)
            if "peak_sar_10g_mw_kg" in all_organ_results_df.columns:
                plotter.plot_top20_tissues_ranking(all_organ_results_df, metric="peak_sar_10g_mw_kg", scenario_name=None)

        # ============================================================================
        # CDF Plots
        # ============================================================================
        if self.should_generate_plot("plot_cdf"):
            logging.getLogger("progress").info(
                "  - Generating CDF plots...",
                extra={"log_type": "info"},
            )
            # Include both SAR and psSAR10g metrics for symmetry with near-field
            sar_metrics = [col for col in results_df.columns if col.startswith("SAR_")]
            pssar_metrics = [col for col in results_df.columns if col.startswith("psSAR10g")]
            cdf_metrics = sar_metrics + pssar_metrics + (["peak_sar"] if "peak_sar" in results_df.columns else [])
            for metric in cdf_metrics:
                if metric in results_df.columns and results_df[metric].notna().any():
                    # CDF grouped by frequency
                    plotter.plot_cdf(results_df, metric, group_by="frequency_mhz", scenario_name=None)

        # ============================================================================
        # Correlation Plots
        # ============================================================================
        if self.should_generate_plot("plot_tissue_group_correlation_matrix"):
            logging.getLogger("progress").info(
                "  - Generating correlation matrix...",
                extra={"log_type": "info"},
            )
            plotter.plot_tissue_group_correlation_matrix(results_df, scenario_name=None)

        # ============================================================================
        # Bubble Plots (Mass vs SAR)
        # ============================================================================
        if not all_organ_results_df.empty and self.should_generate_plot("plot_bubble_mass_vs_sar"):
            if "Total Mass" in all_organ_results_df.columns:
                logging.getLogger("progress").info(
                    "  - Generating bubble plots (mass vs SAR)...",
                    extra={"log_type": "info"},
                )
                plotter.plot_bubble_mass_vs_sar(all_organ_results_df, sar_column="mass_avg_sar_mw_kg", scenario_name=None)
                if "peak_sar_10g_mw_kg" in all_organ_results_df.columns:
                    plotter.plot_bubble_mass_vs_sar(all_organ_results_df, sar_column="peak_sar_10g_mw_kg", scenario_name=None)
        # Interactive bubble plots (symmetric with NF)
        if not all_organ_results_df.empty and self.should_generate_plot("plot_bubble_mass_vs_sar_interactive"):
            if "Total Mass" in all_organ_results_df.columns:
                plotter.plot_bubble_mass_vs_sar_interactive(all_organ_results_df, sar_column="mass_avg_sar_mw_kg", scenario_name=None)

        # ============================================================================
        # Penetration Depth Ratio (symmetric with NF)
        # ============================================================================
        if self.should_generate_plot("plot_penetration_depth_ratio"):
            plotter.plot_penetration_depth_ratio(results_df, scenario_name=None, metric_type="psSAR10g")
            plotter.plot_penetration_depth_ratio(results_df, scenario_name=None, metric_type="SAR")

        # ============================================================================
        # Max Local vs psSAR Scatter (symmetric with NF)
        # ============================================================================
        if self.should_generate_plot("plot_max_local_vs_pssar10g_scatter"):
            plotter.plot_max_local_vs_pssar10g_scatter(results_df, scenario_name=None)

        # ============================================================================
        # Tissue Analysis Plots
        # ============================================================================
        if not all_organ_results_df.empty:
            # Tissue frequency response for top tissues
            if self.should_generate_plot("plot_tissue_frequency_response") and "mass_avg_sar_mw_kg" in all_organ_results_df.columns:
                logging.getLogger("progress").info(
                    "  - Generating tissue frequency response plots...",
                    extra={"log_type": "info"},
                )
                filtered_organs = all_organ_results_df[all_organ_results_df["tissue"] != "All Regions"]
                top_tissues = filtered_organs.groupby("tissue")["mass_avg_sar_mw_kg"].mean().nlargest(10).index.tolist()
                for tissue in top_tissues:
                    plotter.plot_tissue_frequency_response(all_organ_results_df, tissue_name=tissue, scenario_name=None)
            # Tissue mass/volume distribution (symmetric with NF)
            if self.should_generate_plot("plot_tissue_mass_volume_distribution"):
                plotter.plot_tissue_mass_volume_distribution(all_organ_results_df, scenario_name=None)

        # ============================================================================
        # Outlier Identification
        # ============================================================================
        if self.should_generate_plot("identify_outliers"):
            logging.getLogger("progress").info(
                "  - Identifying outliers...",
                extra={"log_type": "info"},
            )
            # Include both SAR and psSAR10g metrics for symmetry with near-field
            sar_outlier_metrics = ["SAR_whole_body", "peak_sar", "SAR_brain", "SAR_skin", "SAR_eyes", "SAR_genitals"]
            pssar_outlier_metrics = ["psSAR10g_brain", "psSAR10g_eyes", "psSAR10g_skin", "psSAR10g_genitals"]
            outlier_metrics = sar_outlier_metrics + pssar_outlier_metrics
            for metric in outlier_metrics:
                if metric in results_df.columns and results_df[metric].notna().any():
                    plotter.identify_outliers(results_df, metric, scenario_name=None)
