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


class NearFieldAnalysisStrategy(BaseAnalysisStrategy):
    """Analysis strategy for near-field simulations.

    Handles result loading, normalization, and plot generation for near-field
    studies with placement scenarios, positions, and orientations.
    """

    def __init__(self, config: "Config", phantom_name: str, analysis_config: dict | None = None):
        """Initializes the near-field analysis strategy.

        Args:
            config: Configuration object.
            phantom_name: Phantom model name being analyzed.
            analysis_config: Optional dictionary with plot names as keys and boolean values.
        """
        super().__init__(config, phantom_name, analysis_config)

    def get_results_base_dir(self) -> str:
        """Returns base directory for near-field results."""
        return os.path.join(self.base_dir, "results", "near_field", self.phantom_name)

    def get_plots_dir(self) -> str:
        """Returns directory for near-field plots."""
        return os.path.join(self.base_dir, "plots", "near_field", self.phantom_name)

    def load_and_process_results(self, analyzer: "Analyzer"):
        """Iterates through near-field results and processes each one."""
        antenna_config = self.config["antenna_config"] or {}
        if not antenna_config:
            return
        frequencies = antenna_config.keys()
        placement_scenarios = self.config["placement_scenarios"]
        if not placement_scenarios:
            return

        for freq in frequencies:
            frequency_mhz = int(freq)
            for scenario_name, scenario_def in placement_scenarios.items():
                if not scenario_def:
                    continue
                positions = scenario_def.get("positions", {})
                orientations = scenario_def.get("orientations", {})
                if not positions or not orientations:
                    continue
                for pos_name in positions.keys():
                    for orient_name in orientations.keys():
                        analyzer._process_single_result(frequency_mhz, scenario_name, pos_name, orient_name)

    def get_normalization_factor(self, frequency_mhz: int, simulated_power_w: float) -> float:
        """Calculates the normalization factor based on the target power.

        Args:
            frequency_mhz: The simulation frequency in MHz.
            simulated_power_w: The input power from the simulation in Watts.

        Returns:
            The calculated normalization factor, or 1.0 if not possible.
        """
        antenna_configs = self.config["antenna_config"] or {}
        freq_config = antenna_configs.get(str(frequency_mhz), {})
        target_power_mw = freq_config.get("target_power_mW")
        if target_power_mw is not None and pd.notna(simulated_power_w) and simulated_power_w > 0:
            target_power_w = target_power_mw / 1000.0
            return target_power_w / simulated_power_w
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
        """Extracts and normalizes SAR data from a single near-field result.

        Args:
            pickle_data: Data loaded from the .pkl result file.
            frequency_mhz: The simulation frequency.
            placement_name: The detailed name of the placement.
            scenario_name: The general scenario name (e.g., 'by_cheek').
            sim_power: The simulated input power in Watts.
            norm_factor: The normalization factor to apply to SAR values.
            sar_results: Optional JSON results dict containing power balance data.

        Returns:
            A tuple containing the main result entry and a list of organ-specific entries.
        """
        summary_results = pickle_data.get("summary_results", {})
        grouped_stats = pickle_data.get("grouped_sar_stats", {})
        detailed_df = pickle_data.get("detailed_sar_stats")

        # Check bounding_box setting from config to determine which SAR fields are valid
        placement_scenarios = self.config["placement_scenarios"] or {}
        scenario_config = placement_scenarios.get(scenario_name, {}) if isinstance(placement_scenarios, dict) else {}
        bounding_box_setting = scenario_config.get("bounding_box", "default")

        # Extract SAR values - prioritize JSON over pickle, and respect bounding_box setting
        sar_head = pd.NA
        sar_trunk = pd.NA
        sar_whole_body = pd.NA

        # If whole_body bounding box, only use whole_body_sar (ignore head/trunk from old pickle files)
        if bounding_box_setting == "whole_body":
            # Prefer JSON, fallback to pickle
            sar_whole_body = sar_results.get("whole_body_sar", pd.NA) if sar_results else pd.NA
            if pd.isna(sar_whole_body):
                sar_whole_body = summary_results.get("whole_body_sar", pd.NA)
        else:
            # For head/trunk/default bounding boxes, extract head/trunk SAR
            # Prefer JSON, fallback to pickle
            if sar_results:
                sar_head = sar_results.get("head_SAR", pd.NA)
                sar_trunk = sar_results.get("trunk_SAR", pd.NA)
            if pd.isna(sar_head):
                sar_head = summary_results.get("head_SAR", pd.NA)
            if pd.isna(sar_trunk):
                sar_trunk = summary_results.get("trunk_SAR", pd.NA)

            # Also check for whole_body_sar (might exist from old data)
            if sar_results:
                sar_whole_body = sar_results.get("whole_body_sar", pd.NA)
            if pd.isna(sar_whole_body):
                sar_whole_body = summary_results.get("whole_body_sar", pd.NA)

        result_entry = {
            "frequency_mhz": frequency_mhz,
            "placement": placement_name,
            "scenario": scenario_name,
            "input_power_w": sim_power,
            "SAR_head": sar_head * norm_factor if pd.notna(sar_head) else pd.NA,
            "SAR_trunk": sar_trunk * norm_factor if pd.notna(sar_trunk) else pd.NA,
            "SAR_whole_body": sar_whole_body * norm_factor if pd.notna(sar_whole_body) else pd.NA,
        }
        for group_name, stats in grouped_stats.items():
            key = f"psSAR10g_{group_name.replace('_group', '')}"
            result_entry[key] = stats.get("peak_sar", pd.NA) * norm_factor

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
                organ_entry = {
                    "frequency_mhz": frequency_mhz,
                    "placement": placement_name,
                    "scenario": scenario_name,
                    "tissue": _clean_tissue_name(row["Tissue"]),  # Clean tissue name early
                    "mass_avg_sar_mw_kg": row["Mass-Averaged SAR"] * norm_factor * 1000,
                    "peak_sar_10g_mw_kg": row.get(peak_sar_col, pd.NA) * norm_factor * 1000
                    if pd.notna(row.get(peak_sar_col, pd.NA))
                    else pd.NA,
                    "min_local_sar_mw_kg": row.get("Min. local SAR", pd.NA) * norm_factor * 1000
                    if pd.notna(row.get("Min. local SAR", pd.NA))
                    else pd.NA,
                    "max_local_sar_mw_kg": row.get("Max. local SAR", pd.NA) * norm_factor * 1000
                    if pd.notna(row.get("Max. local SAR", pd.NA))
                    else pd.NA,
                }
                # Add Total Mass, Total Volume, Total Loss, Max Loss Power Density if available
                if "Total Mass" in row.index:
                    organ_entry["Total Mass"] = row["Total Mass"]
                if "Total Volume" in row.index:
                    organ_entry["Total Volume"] = row["Total Volume"]
                if "Total Loss" in row.index:
                    organ_entry["Total Loss"] = row["Total Loss"]
                if "Max Loss Power Density" in row.index:
                    organ_entry["Max Loss Power Density"] = row["Max Loss Power Density"]
                # Add psSAR10g column name for compatibility
                if peak_sar_col in row.index and pd.notna(row[peak_sar_col]):
                    organ_entry["psSAR10g"] = row[peak_sar_col] * norm_factor * 1000
                organ_entries.append(organ_entry)
        return result_entry, organ_entries

    def apply_bug_fixes(self, result_entry: dict) -> dict:
        """Applies a workaround for Head SAR being miscategorized as Trunk SAR.

        NOTE: This method is deprecated for whole_body bounding box scenarios.
        For whole_body scenarios, SAR_head and SAR_trunk should remain NA.

        Args:
            result_entry: The data entry for a single simulation result.

        Returns:
            The corrected result entry.
        """
        # Skip bug fix if whole_body_sar is present (indicates whole_body bounding box)
        if pd.notna(result_entry.get("SAR_whole_body")):
            # For whole_body scenarios, ensure head/trunk are NA
            result_entry["SAR_head"] = pd.NA
            result_entry["SAR_trunk"] = pd.NA
            return result_entry

        # Original bug fix logic for head/trunk bounding boxes
        placement = result_entry.get("placement", "").lower()
        if placement.startswith("front_of_eyes") or placement.startswith("by_cheek"):
            sar_head = result_entry.get("SAR_head")
            sar_trunk = result_entry.get("SAR_trunk")
            if bool(pd.isna(sar_head)) and bool(pd.notna(sar_trunk)):
                result_entry["SAR_head"] = sar_trunk
                result_entry["SAR_trunk"] = pd.NA
        return result_entry

    def calculate_summary_stats(self, results_df: pd.DataFrame) -> pd.DataFrame:
        """Calculates summary statistics, including completion progress.

        Args:
            results_df: DataFrame with all aggregated simulation results.

        Returns:
            A DataFrame with mean SAR values and a 'progress' column.
        """
        placement_scenarios = self.config["placement_scenarios"]
        placements_per_scenario = {}
        logging.getLogger("progress").info(
            "\n--- Calculating Total Possible Placements per Scenario ---",
            extra={"log_type": "header"},
        )
        if placement_scenarios:
            for name, definition in placement_scenarios.items():
                if not definition:
                    continue
                total = len(definition.get("positions", {})) * len(definition.get("orientations", {}))
                placements_per_scenario[name] = total
                logging.getLogger("progress").info(f"- Scenario '{name}': {total} placements", extra={"log_type": "info"})

        summary_stats = results_df.groupby(["scenario", "frequency_mhz"]).mean(numeric_only=True)
        completion_counts = results_df.groupby(["scenario", "frequency_mhz"]).size()

        # Define a mapping function that safely handles potential missing keys
        def get_progress(idx):
            # Index is a tuple (scenario, frequency)
            if isinstance(idx, tuple) and len(idx) == 2:
                scenario_name, _ = idx
            else:
                scenario_name = idx
            completed = completion_counts.get(idx, 0)
            total = placements_per_scenario.get(scenario_name, 0)
            return f"{completed}/{total}"

        if not summary_stats.empty:
            summary_stats["progress"] = summary_stats.index.map(get_progress)  # type: ignore
        return pd.DataFrame(summary_stats)

    def _add_tissue_group_sar(self, results_df: pd.DataFrame, all_organ_results_df: pd.DataFrame, analyzer: "Analyzer") -> pd.DataFrame:
        """Aggregates organ-level SAR by tissue groups and adds to results_df.

        Creates SAR_eyes, SAR_brain, SAR_skin, SAR_genitals columns by averaging
        mass_avg_sar_mw_kg across tissues in each group.

        Uses tissue_group_composition from pickle files (actual tissue names) if available,
        otherwise falls back to keyword-based matching.

        Args:
            results_df: DataFrame with main aggregated results.
            all_organ_results_df: DataFrame with organ-level results.
            analyzer: Analyzer instance containing tissue_group_composition.

        Returns:
            results_df with added SAR_{group} columns.
        """
        if all_organ_results_df.empty or "mass_avg_sar_mw_kg" not in all_organ_results_df.columns:
            return results_df

        # Create a copy to avoid modifying the original
        results_df = results_df.copy()

        # Use tissue_group_composition from pickle files (exact tissue names)
        # This uses the actual tissue names that were matched during extraction
        if not analyzer.tissue_group_composition:
            logging.getLogger("progress").warning(
                "No tissue_group_composition found in pickle files. Skipping tissue group SAR aggregation.",
                extra={"log_type": "warning"},
            )
            return results_df

        # Convert sets to lists for processing
        tissue_groups = {group_name: list(tissues) for group_name, tissues in analyzer.tissue_group_composition.items()}

        # Aggregate SAR by tissue groups for each placement
        # Use exact tissue name matching from pickle files
        group_sar_data = []
        for group_name, tissue_list in tissue_groups.items():
            group_organs = all_organ_results_df[all_organ_results_df["tissue"].isin(tissue_list)]

            if not group_organs.empty:
                # Group by placement and frequency, calculate mean SAR
                group_avg = group_organs.groupby(["placement", "frequency_mhz"])["mass_avg_sar_mw_kg"].mean().reset_index()
                group_avg["group"] = group_name.replace("_group", "")
                group_sar_data.append(group_avg)

        # Expected tissue group SAR columns that should always be present
        expected_sar_columns = ["SAR_brain", "SAR_skin", "SAR_genitals", "SAR_eyes"]

        if group_sar_data:
            # Combine all groups
            combined_group_sar = pd.concat(group_sar_data, ignore_index=True)

            # Pivot to create columns for each group
            group_sar_pivot = combined_group_sar.pivot_table(
                index=["placement", "frequency_mhz"], columns="group", values="mass_avg_sar_mw_kg", aggfunc="mean"
            ).reset_index()

            # Rename columns to SAR_{group}
            rename_dict = {col: f"SAR_{col}" for col in group_sar_pivot.columns if col not in ["placement", "frequency_mhz"]}
            group_sar_pivot = group_sar_pivot.rename(columns=rename_dict)

            # Merge back into results_df
            results_df = results_df.merge(group_sar_pivot, on=["placement", "frequency_mhz"], how="left")

        # Ensure all expected SAR columns exist, even if they're NaN
        # This ensures they appear in plots and legends even when there's no data
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
        """Generates all plots for the near-field analysis.

        Includes bar charts for average SAR, line plots for psSAR, and boxplots
        for SAR distribution.

        Args:
            analyzer: The main analyzer instance.
            plotter: The plotter instance for generating plots.
            results_df: DataFrame with main aggregated results.
            all_organ_results_df: DataFrame with detailed organ-level results.
        """
        # Aggregate organ-level SAR by tissue groups and merge into results_df
        # Uses tissue_group_composition from pickle files if available
        results_df = self._add_tissue_group_sar(results_df, all_organ_results_df, analyzer)

        scenarios_with_results = results_df["scenario"].unique()
        summary_stats = self.calculate_summary_stats(results_df)

        for scenario_name in scenarios_with_results:
            logging.getLogger("progress").info(
                f"\n--- Generating plots for scenario: {scenario_name} ---",
                extra={"log_type": "header"},
            )
            scenario_results_df = results_df[results_df["scenario"] == scenario_name]
            if scenario_name in summary_stats.index:
                scenario_summary_stats = summary_stats.loc[scenario_name]
                avg_results = scenario_summary_stats.drop(columns=["progress"])
                progress_info = scenario_summary_stats["progress"]
                if self.should_generate_plot("plot_average_sar_bar"):
                    plotter.plot_average_sar_bar(scenario_name, pd.DataFrame(avg_results), pd.Series(progress_info), scenario_results_df)
                if self.should_generate_plot("plot_average_pssar_bar"):
                    plotter.plot_average_pssar_bar(scenario_name, pd.DataFrame(avg_results), pd.Series(progress_info), scenario_results_df)
                if self.should_generate_plot("plot_sar_line"):
                    plotter.plot_sar_line(scenario_name, pd.DataFrame(avg_results))
                if self.should_generate_plot("plot_pssar_line"):
                    plotter.plot_pssar_line(scenario_name, pd.DataFrame(avg_results))
            if self.should_generate_plot("plot_sar_distribution_boxplots"):
                plotter.plot_sar_distribution_boxplots(scenario_name, pd.DataFrame(scenario_results_df))

            # Individual variation line plots (one line per placement/direction/polarization)
            # Include all SAR and psSAR10g metrics for symmetry
            pssar_columns = [col for col in scenario_results_df.columns if col.startswith("psSAR10g")]
            sar_columns_for_lines = ["SAR_head", "SAR_trunk", "SAR_whole_body", "SAR_brain", "SAR_skin", "SAR_eyes", "SAR_genitals"]
            # Plot SAR metrics using SAR-specific function
            if self.should_generate_plot("plot_sar_line_individual_variations"):
                for metric_col in sar_columns_for_lines:
                    if metric_col in scenario_results_df.columns:
                        plotter.plot_sar_line_individual_variations(
                            results_df,
                            scenario_name=scenario_name,
                            metric_column=metric_col,
                        )
            # Plot psSAR10g metrics using psSAR10g-specific function
            if self.should_generate_plot("plot_pssar_line_individual_variations"):
                for metric_col in pssar_columns:
                    if metric_col in scenario_results_df.columns:
                        plotter.plot_pssar_line_individual_variations(
                            results_df,
                            scenario_name=scenario_name,
                            metric_column=metric_col,
                        )

        # Generate comprehensive heatmap with all tissues (Min/Avg/Max SAR)
        if not all_organ_results_df.empty and analyzer.tissue_group_composition:
            # Check if required columns exist
            required_cols = ["min_local_sar_mw_kg", "mass_avg_sar_mw_kg", "max_local_sar_mw_kg"]
            missing_cols = [col for col in required_cols if col not in all_organ_results_df.columns]

            if missing_cols:
                logging.getLogger("progress").warning(
                    f"  - WARNING: Missing columns for SAR heatmap: {missing_cols}. Skipping heatmap.",
                    extra={"log_type": "warning"},
                )
            else:
                # Prepare organ-level data with min/avg/max SAR
                # Aggregate across all placements to get mean values per tissue and frequency
                organ_sar_df = (
                    all_organ_results_df.groupby(["tissue", "frequency_mhz"])
                    .agg(
                        min_sar=("min_local_sar_mw_kg", "mean"),
                        avg_sar=("mass_avg_sar_mw_kg", "mean"),
                        max_sar=("max_local_sar_mw_kg", "mean"),
                    )
                    .reset_index()
                )

                # Drop rows where all SAR values are NA (pandas mean() returns NaN if all values are NaN)
                organ_sar_df = organ_sar_df.dropna(subset=["min_sar", "avg_sar", "max_sar"], how="all")

                # Prepare group-level summary data
                tissue_groups = {group_name: list(tissues) for group_name, tissues in analyzer.tissue_group_composition.items()}

                group_summary_data = []
                for group_name, tissues in tissue_groups.items():
                    if not tissues:
                        continue

                    # Filter organs belonging to this group
                    group_df = all_organ_results_df[all_organ_results_df["tissue"].isin(tissues)]

                    if not group_df.empty:
                        summary = group_df.groupby("frequency_mhz").agg(avg_sar=("mass_avg_sar_mw_kg", "mean")).reset_index()
                        summary["group"] = group_name.replace("_group", "").capitalize()
                        group_summary_data.append(summary)

                group_summary_df = pd.concat(group_summary_data, ignore_index=True) if group_summary_data else pd.DataFrame()

                if not organ_sar_df.empty and not group_summary_df.empty:
                    # Use tissue_group_composition for plotter (convert sets to lists)
                    plotter_tissue_groups = {group_name: list(tissues) for group_name, tissues in analyzer.tissue_group_composition.items()}

                    if self.should_generate_plot("plot_sar_heatmap"):
                        logging.getLogger("progress").info(
                            "\n--- Generating comprehensive SAR heatmap (all tissues) ---",
                            extra={"log_type": "header"},
                        )
                        plotter.plot_sar_heatmap(
                            pd.DataFrame(organ_sar_df),
                            pd.DataFrame(group_summary_df),
                            plotter_tissue_groups,
                        )

                    # Also generate psSAR10g heatmap if data is available
                    if "peak_sar_10g_mw_kg" in all_organ_results_df.columns and self.should_generate_plot("plot_peak_sar_heatmap"):
                        organ_pssar_df = (
                            all_organ_results_df.groupby(["tissue", "frequency_mhz"])
                            .agg(peak_sar_10g_mw_kg=("peak_sar_10g_mw_kg", "mean"))
                            .reset_index()
                        )
                        organ_pssar_df = plotter._filter_all_regions(organ_pssar_df, tissue_column="tissue")

                        group_pssar_summary_data = []
                        for group_name, tissues in tissue_groups.items():
                            if not tissues:
                                continue
                            group_df = all_organ_results_df[all_organ_results_df["tissue"].isin(tissues)]
                            if not group_df.empty:
                                summary = (
                                    group_df.groupby("frequency_mhz").agg(peak_sar_10g_mw_kg=("peak_sar_10g_mw_kg", "mean")).reset_index()
                                )
                                summary["group"] = group_name.replace("_group", "").capitalize()
                                group_pssar_summary_data.append(summary)

                        group_pssar_summary_df = (
                            pd.concat(group_pssar_summary_data, ignore_index=True) if group_pssar_summary_data else pd.DataFrame()
                        )

                        if not organ_pssar_df.empty and not group_pssar_summary_df.empty:
                            if self.should_generate_plot("plot_peak_sar_heatmap"):
                                logging.getLogger("progress").info(
                                    "\n--- Generating comprehensive psSAR10g heatmap (all tissues) ---",
                                    extra={"log_type": "header"},
                                )
                                plotter.plot_peak_sar_heatmap(
                                    pd.DataFrame(organ_pssar_df),
                                    pd.DataFrame(group_pssar_summary_df),
                                    plotter_tissue_groups,
                                    value_col="peak_sar_10g_mw_kg",
                                    title="Peak SAR 10g",
                                )
                else:
                    logging.getLogger("progress").warning(
                        "  - WARNING: Insufficient data for SAR heatmap (empty organ or group data).",
                        extra={"log_type": "warning"},
                    )

        # Generate power balance plots for all results
        if self.should_generate_plot("plot_power_balance_overview"):
            plotter.plot_power_balance_overview(results_df)

        # ============================================================================
        # Generate All New Comprehensive Plots
        # ============================================================================

        logging.getLogger("progress").info(
            "\n--- Generating comprehensive analysis plots ---",
            extra={"log_type": "header"},
        )

        # Collect peak location data from all results
        peak_location_data = []
        for result in analyzer.all_results:
            if "peak_sar_details" in result:
                peak_details = result["peak_sar_details"]
                if peak_details and isinstance(peak_details, dict):
                    peak_location_data.append(
                        {
                            "PeakLocation": peak_details.get("PeakLocation", None),
                            "PeakCubeSideLength": peak_details.get("PeakCubeSideLength", None),
                            "PeakValue": peak_details.get("PeakValue", None),
                            "PeakCell": peak_details.get("PeakCell", None),
                            "placement": result.get("placement", ""),
                            "frequency_mhz": result.get("frequency_mhz", None),
                            "scenario": result.get("scenario", ""),
                        }
                    )

        peak_location_df = pd.DataFrame(peak_location_data) if peak_location_data else pd.DataFrame()

        # ============================================================================
        # Spatial Plots
        # ============================================================================
        if not peak_location_df.empty:
            if self.should_generate_plot("plot_peak_location_3d_interactive") or self.should_generate_plot(
                "plot_peak_location_2d_projections"
            ):
                logging.getLogger("progress").info(
                    "  - Generating spatial plots (3D and 2D peak locations)...",
                    extra={"log_type": "info"},
                )
                # First create aggregated plot with all scenarios
                # Calculate axis limits from all data
                axis_limits = plotter.spatial._calculate_axis_limits(peak_location_df)
                # Create aggregated plot
                if self.should_generate_plot("plot_peak_location_3d_interactive"):
                    plotter.plot_peak_location_3d_interactive(peak_location_df, scenario_name=None, axis_limits=axis_limits)

                # Per-scenario spatial plots with inherited axis limits
                for scenario in peak_location_df["scenario"].unique():
                    scenario_peak_data = peak_location_df[peak_location_df["scenario"] == scenario].copy()
                    if not scenario_peak_data.empty and self.should_generate_plot("plot_peak_location_3d_interactive"):
                        plotter.plot_peak_location_3d_interactive(scenario_peak_data, scenario_name=scenario, axis_limits=axis_limits)
                    if self.should_generate_plot("plot_peak_location_2d_projections"):
                        plotter.plot_peak_location_2d_projections(peak_location_df, scenario_name=scenario)

        # ============================================================================
        # Correlation Plots
        # ============================================================================
        if self.should_generate_plot("plot_correlation_head_vs_eye_sar") or self.should_generate_plot(
            "plot_tissue_group_correlation_matrix"
        ):
            logging.getLogger("progress").info(
                "  - Generating correlation plots...",
                extra={"log_type": "info"},
            )
            # Head vs Eye SAR correlation (for front_of_eyes scenario)
            if "front_of_eyes" in scenarios_with_results and self.should_generate_plot("plot_correlation_head_vs_eye_sar"):
                plotter.plot_correlation_head_vs_eye_sar(results_df, scenario_name="front_of_eyes")
            # Tissue group correlation matrix (per scenario only - averaging across scenarios doesn't make sense)
            if self.should_generate_plot("plot_tissue_group_correlation_matrix"):
                for scenario in scenarios_with_results:
                    plotter.plot_tissue_group_correlation_matrix(results_df, scenario_name=scenario)

        # ============================================================================
        # Bubble Plots (Mass vs SAR)
        # ============================================================================
        if not all_organ_results_df.empty and (
            self.should_generate_plot("plot_bubble_mass_vs_sar") or self.should_generate_plot("plot_bubble_mass_vs_sar_interactive")
        ):
            logging.getLogger("progress").info(
                "  - Generating bubble plots (mass vs SAR)...",
                extra={"log_type": "info"},
            )
            # Note: Total Mass, Total Volume, etc. should be included in organ_entries from extract_data

            # Get unique frequencies for frequency-specific plots
            frequencies = (
                sorted(all_organ_results_df["frequency_mhz"].dropna().unique()) if "frequency_mhz" in all_organ_results_df.columns else []
            )

            # SAR columns to plot
            sar_columns = ["mass_avg_sar_mw_kg"]
            if "psSAR10g" in all_organ_results_df.columns:
                sar_columns.append("psSAR10g")
            elif "peak_sar_10g_mw_kg" in all_organ_results_df.columns:
                all_organ_results_df["psSAR10g"] = all_organ_results_df["peak_sar_10g_mw_kg"]
                sar_columns.append("psSAR10g")
            if "max_local_sar_mw_kg" in all_organ_results_df.columns:
                sar_columns.append("max_local_sar_mw_kg")

            for sar_col in sar_columns:
                # Per-scenario variants only (averaging across scenarios doesn't make sense)
                for scenario in scenarios_with_results:
                    # Per-scenario (all frequencies)
                    if self.should_generate_plot("plot_bubble_mass_vs_sar"):
                        plotter.plot_bubble_mass_vs_sar(
                            all_organ_results_df,
                            sar_column=sar_col,
                            scenario_name=scenario,
                        )

                        # Per-scenario AND per-frequency variants
                        for freq in frequencies:
                            plotter.plot_bubble_mass_vs_sar(
                                all_organ_results_df,
                                sar_column=sar_col,
                                scenario_name=scenario,
                                frequency_mhz=freq,
                            )

                    # Interactive plot per scenario
                    if self.should_generate_plot("plot_bubble_mass_vs_sar_interactive"):
                        plotter.plot_bubble_mass_vs_sar_interactive(
                            all_organ_results_df,
                            sar_column=sar_col,
                            scenario_name=scenario,
                        )

        # ============================================================================
        # Ranking Plots
        # ============================================================================
        if not all_organ_results_df.empty and self.should_generate_plot("plot_top20_tissues_ranking"):
            logging.getLogger("progress").info(
                "  - Generating ranking plots (top 20 tissues)...",
                extra={"log_type": "info"},
            )
            # Per-scenario variants only (averaging across scenarios doesn't make sense)
            for scenario in scenarios_with_results:
                if "max_local_sar_mw_kg" in all_organ_results_df.columns:
                    plotter.plot_top20_tissues_ranking(
                        all_organ_results_df,
                        metric="max_local_sar_mw_kg",
                        scenario_name=scenario,
                    )
                # Top 20 by Mass-Averaged SAR
                plotter.plot_top20_tissues_ranking(
                    all_organ_results_df,
                    metric="mass_avg_sar_mw_kg",
                    scenario_name=scenario,
                )
                # Top 20 by Total Loss (if available)
                if "Total Loss" in all_organ_results_df.columns:
                    plotter.plot_top20_tissues_ranking(
                        all_organ_results_df,
                        metric="Total Loss",
                        scenario_name=scenario,
                    )

        # ============================================================================
        # Power Plots
        # ============================================================================
        if self.should_generate_plot("plot_power_efficiency_trends") or self.should_generate_plot("plot_power_absorption_distribution"):
            logging.getLogger("progress").info(
                "  - Generating power analysis plots...",
                extra={"log_type": "info"},
            )
            # Power efficiency trends (per scenario only - averaging across scenarios doesn't make sense)
            if self.should_generate_plot("plot_power_efficiency_trends"):
                for scenario in scenarios_with_results:
                    plotter.plot_power_efficiency_trends(results_df, scenario_name=scenario)

            # Power absorption distribution (per scenario only - averaging across scenarios doesn't make sense)
            if (
                self.should_generate_plot("plot_power_absorption_distribution")
                and not all_organ_results_df.empty
                and "Total Loss" in all_organ_results_df.columns
            ):
                for scenario in scenarios_with_results:
                    plotter.plot_power_absorption_distribution(all_organ_results_df, scenario_name=scenario)

        # ============================================================================
        # Penetration Depth Plot
        # ============================================================================
        if self.should_generate_plot("plot_penetration_depth_ratio"):
            logging.getLogger("progress").info(
                "  - Generating penetration depth plot...",
                extra={"log_type": "info"},
            )
            # Penetration depth ratio (per scenario only - averaging across scenarios doesn't make sense)
            # Generate both psSAR10g and SAR versions for symmetry
            if "psSAR10g_brain" in results_df.columns and "psSAR10g_skin" in results_df.columns:
                for scenario in scenarios_with_results:
                    plotter.plot_penetration_depth_ratio(results_df, scenario_name=scenario, metric_type="psSAR10g")
            if "SAR_brain" in results_df.columns and "SAR_skin" in results_df.columns:
                for scenario in scenarios_with_results:
                    plotter.plot_penetration_depth_ratio(results_df, scenario_name=scenario, metric_type="SAR")

        # ============================================================================
        # Tissue Analysis Plots
        # ============================================================================
        if not all_organ_results_df.empty and (
            self.should_generate_plot("plot_max_local_vs_pssar10g_scatter")
            or self.should_generate_plot("plot_tissue_mass_volume_distribution")
            or self.should_generate_plot("plot_tissue_frequency_response")
        ):
            logging.getLogger("progress").info(
                "  - Generating tissue analysis plots...",
                extra={"log_type": "info"},
            )
            # Max Local SAR vs psSAR10g scatter (per scenario only - averaging across scenarios doesn't make sense)
            if self.should_generate_plot("plot_max_local_vs_pssar10g_scatter") and "max_local_sar_mw_kg" in all_organ_results_df.columns:
                for scenario in scenarios_with_results:
                    plotter.plot_max_local_vs_pssar10g_scatter(all_organ_results_df, scenario_name=scenario)

            # Tissue mass/volume distribution (per scenario only - averaging across scenarios doesn't make sense)
            if (
                self.should_generate_plot("plot_tissue_mass_volume_distribution")
                and "Total Mass" in all_organ_results_df.columns
                and "Total Volume" in all_organ_results_df.columns
            ):
                for scenario in scenarios_with_results:
                    plotter.plot_tissue_mass_volume_distribution(all_organ_results_df, scenario_name=scenario)

            # Tissue frequency response for top tissues (per scenario only - averaging across scenarios doesn't make sense)
            if self.should_generate_plot("plot_tissue_frequency_response") and "mass_avg_sar_mw_kg" in all_organ_results_df.columns:
                # Filter out 'All Regions' before selecting top tissues
                filtered_organs = all_organ_results_df[all_organ_results_df["tissue"] != "All Regions"]
                for scenario in scenarios_with_results:
                    # Get top tissues per scenario
                    scenario_organs = filtered_organs[filtered_organs["scenario"] == scenario]
                    top_tissues = scenario_organs.groupby("tissue")["mass_avg_sar_mw_kg"].mean().nlargest(10).index.tolist()
                    for tissue in top_tissues:
                        plotter.plot_tissue_frequency_response(all_organ_results_df, tissue_name=tissue, scenario_name=scenario)

        # ============================================================================
        # CDF Plots
        # ============================================================================
        if self.should_generate_plot("plot_cdf"):
            logging.getLogger("progress").info(
                "  - Generating CDF plots...",
                extra={"log_type": "info"},
            )
            # Get all available metrics for CDF plots
            cdf_metrics = []
            sar_metrics = [col for col in results_df.columns if col.startswith("SAR_")]
            pssar_metrics = [col for col in results_df.columns if col.startswith("psSAR10g_")]
            cdf_metrics.extend(sar_metrics)
            cdf_metrics.extend(pssar_metrics)

            # Generate CDF plots with various grouping options
            for metric in cdf_metrics:
                if metric not in results_df.columns:
                    continue

                # CDF grouped by scenario (shows all scenarios together for comparison)
                plotter.plot_cdf(results_df, metric, group_by="scenario")

                # Per-scenario CDFs grouped by frequency
                for scenario in scenarios_with_results:
                    plotter.plot_cdf(results_df, metric, group_by="frequency_mhz", scenario_name=scenario)

                # Note: Single CDF (all data) and per-frequency CDFs removed - averaging across scenarios doesn't make sense

        # ============================================================================
        # Outlier Identification
        # ============================================================================
        if self.should_generate_plot("identify_outliers"):
            logging.getLogger("progress").info(
                "  - Identifying outliers...",
                extra={"log_type": "info"},
            )
            # Include all SAR and psSAR10g metrics for symmetry
            outlier_metrics = [
                "psSAR10g_brain",
                "psSAR10g_eyes",
                "psSAR10g_skin",
                "psSAR10g_genitals",
                "psSAR10g_whole_body",
                "SAR_head",
                "SAR_trunk",
                "SAR_whole_body",
                "SAR_brain",
                "SAR_skin",
                "SAR_eyes",
                "SAR_genitals",
            ]
            for metric in outlier_metrics:
                if metric in results_df.columns:
                    outliers = plotter.identify_outliers(results_df, metric)
                    if outliers is not None and not outliers.empty:
                        # Save outliers to CSV
                        subdir = plotter._get_subdir("outliers")
                        filename = f"outliers_{metric}.csv"
                        outliers.to_csv(os.path.join(subdir, filename), index=False)
                        logging.getLogger("progress").info(
                            f"    - Found {len(outliers)} outliers for {metric}",
                            extra={"log_type": "info"},
                        )

        logging.getLogger("progress").info(
            "\n--- Comprehensive analysis plots generation complete ---",
            extra={"log_type": "success"},
        )
