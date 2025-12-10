import json
import logging
import os
import pickle
from typing import TYPE_CHECKING

import pandas as pd

from .plotter import Plotter

if TYPE_CHECKING:
    from ..config import Config
    from .base_strategy import BaseAnalysisStrategy


class Analyzer:
    """Analyzes simulation results using a strategy pattern.

    Delegates to strategy-specific implementations for loading results and
    generating plots. Handles unit conversion, caching, and report export.
    """

    def __init__(self, config: "Config", phantom_name: str, strategy: "BaseAnalysisStrategy", plot_format: str = "pdf"):
        """Sets up the analyzer with a strategy.

        Args:
            config: Configuration object.
            phantom_name: Phantom model name being analyzed.
            strategy: Strategy implementation for analysis logic.
            plot_format: Output format for plots ('pdf' or 'png'), default 'pdf'.
        """
        self.config = config
        self.base_dir = config.base_dir
        self.phantom_name = phantom_name
        self.strategy = strategy
        self.results_base_dir = self.strategy.get_results_base_dir()
        self.plotter = Plotter(self.strategy.get_plots_dir(), phantom_name=self.phantom_name, plot_format=plot_format)
        self.all_results = []
        self.all_organ_results = []
        # Will be populated from pickle files - contains actual tissue names from extraction
        # This is the authoritative source, computed during extraction using material_name_mapping.json
        self.tissue_group_composition = {}

    def run_analysis(self):
        """Runs complete analysis pipeline using the selected strategy.

        Loads results, converts units, exports reports, and generates plots.
        Delegates strategy-specific logic to the strategy instance.
        """
        logging.getLogger("progress").info(
            f"--- Starting Results Analysis for Phantom: {self.phantom_name} ---",
            extra={"log_type": "header"},
        )

        # Check if we should load data or use cache instead
        load_data = self.strategy.analysis_config.get("load_data", True)

        if not load_data:
            logging.getLogger("progress").info(
                "--- Skipping data loading phase, loading from cache ---",
                extra={"log_type": "info"},
            )
            results_df, all_organ_results_df = self._load_from_cache()
            if results_df is None:
                logging.getLogger("progress").error(
                    "--- Failed to load cached results. Run analysis with load_data=True first. ---",
                    extra={"log_type": "error"},
                )
                return
        else:
            self.strategy.load_and_process_results(self)

            if not self.all_results:
                logging.getLogger("progress").info("--- No results found to analyze. ---", extra={"log_type": "warning"})
                return

            results_df = pd.DataFrame(self.all_results)
            all_organ_results_df = pd.DataFrame(self.all_organ_results) if self.all_organ_results else pd.DataFrame()

            results_df = self._convert_units_and_cache(results_df, all_organ_results_df)
            self._export_reports(results_df, all_organ_results_df)

        self.strategy.generate_plots(self, self.plotter, results_df, all_organ_results_df)

        logging.getLogger("progress").info("--- Analysis Finished ---", extra={"log_type": "success"})

    def _process_single_result(self, frequency_mhz: int, scenario_name: str, pos_name: str, orient_name: str):
        """Processes one simulation result file.

        Locates JSON/PKL files, extracts data via strategy, applies bug fixes,
        and adds to aggregator lists. Handles missing files and errors gracefully.

        Args:
            frequency_mhz: Simulation frequency in MHz.
            scenario_name: Placement scenario name (e.g., 'by_cheek').
            pos_name: Position name within scenario.
            orient_name: Orientation name within scenario.
        """
        if self.strategy.__class__.__name__ == "FarFieldAnalysisStrategy":
            # For far-field, pos_name is the full placement directory name
            detailed_placement_name = pos_name
        else:
            if pos_name and orient_name:
                detailed_placement_name = f"{scenario_name}_{pos_name}_{orient_name}"
            elif pos_name:
                detailed_placement_name = f"{scenario_name}_{pos_name}"
            else:
                detailed_placement_name = scenario_name

        results_dir = os.path.join(self.results_base_dir, f"{frequency_mhz}MHz", detailed_placement_name)
        pickle_path = os.path.join(results_dir, "sar_stats_all_tissues.pkl")
        json_path = os.path.join(results_dir, "sar_results.json")

        # Check if files exist - skip silently if missing (partial results)
        if not os.path.exists(json_path):
            logging.getLogger("progress").debug(
                f"  - Skipping (no JSON): {frequency_mhz}MHz, {detailed_placement_name}",
                extra={"log_type": "debug"},
            )
            return

        if not os.path.exists(pickle_path):
            logging.getLogger("progress").warning(
                f"  - Warning: PKL file missing for {frequency_mhz}MHz, {detailed_placement_name}",
                extra={"log_type": "warning"},
            )
            # Try to process with JSON only (limited data)
            pickle_data = {}

        logging.getLogger("progress").info(
            f"  - Processing: {frequency_mhz}MHz, {detailed_placement_name}",
            extra={"log_type": "progress"},
        )
        try:
            # Load JSON (required)
            with open(json_path, "r") as f:
                sar_results = json.load(f)

            # Load PKL if available
            if os.path.exists(pickle_path):
                with open(pickle_path, "rb") as f:
                    pickle_data = pickle.load(f)

                # Collect tissue_group_composition from pickle files
                # This contains the actual tissue names that were matched during extraction
                # Clean tissue names early to avoid repeated cleaning later
                if "tissue_group_composition" in pickle_data:
                    import re

                    def clean_tissue_name(name: str) -> str:
                        """Remove phantom identifiers from tissue names."""
                        if not name:
                            return name
                        pattern = r"\s*\([^)]*\)\s*$"
                        cleaned = re.sub(pattern, "", name).strip()
                        return cleaned if cleaned else name

                    for group_name, tissues in pickle_data["tissue_group_composition"].items():
                        if group_name not in self.tissue_group_composition:
                            self.tissue_group_composition[group_name] = set()
                        # Clean tissue names and add to composition
                        cleaned_tissues = {clean_tissue_name(t) for t in tissues}
                        self.tissue_group_composition[group_name].update(cleaned_tissues)
            else:
                # Create minimal pickle_data structure from JSON
                pickle_data = {
                    "summary_results": {
                        "head_SAR": sar_results.get("head_SAR", None),
                        "trunk_SAR": sar_results.get("trunk_SAR", None),
                        "whole_body_sar": sar_results.get("whole_body_sar", None),
                        "peak_sar_10g_W_kg": sar_results.get("peak_sar_10g_W_kg", None),
                        "power_balance": sar_results.get("power_balance", None),
                    },
                    "grouped_sar_stats": {},
                    "detailed_sar_stats": None,
                }
                # Try to extract group stats from JSON
                for key, value in sar_results.items():
                    if key.endswith("_peak_sar") or key.endswith("_weighted_avg_sar"):
                        group_name = key.replace("_peak_sar", "").replace("_weighted_avg_sar", "")
                        if group_name not in pickle_data["grouped_sar_stats"]:
                            pickle_data["grouped_sar_stats"][f"{group_name}_group"] = {}
                        if key.endswith("_peak_sar"):
                            pickle_data["grouped_sar_stats"][f"{group_name}_group"]["peak_sar"] = value

            simulated_power_w = sar_results.get("input_power_W", float("nan"))

            # For low frequencies (<=1000 MHz), use P_effective instead of Pin
            # because antenna mismatch causes Pin >> deposited power
            # P_effective = DielLoss + SIBCLoss + RadPower (the actual absorbed + radiated power)
            LOW_FREQ_THRESHOLD_MHZ = 1000
            power_balance = sar_results.get("power_balance", {})

            if frequency_mhz <= LOW_FREQ_THRESHOLD_MHZ and power_balance:
                diel_loss = power_balance.get("DielLoss", 0.0) or 0.0
                sibc_loss = power_balance.get("SIBCLoss", 0.0) or 0.0
                rad_power = power_balance.get("RadPower", 0.0) or 0.0
                p_effective = diel_loss + sibc_loss + rad_power

                if p_effective > 0:
                    original_pin = simulated_power_w
                    simulated_power_w = p_effective
                    logging.getLogger("progress").debug(
                        f"    - Low freq ({frequency_mhz}MHz): Using P_effective={p_effective:.4e}W "
                        f"instead of Pin={original_pin:.4e}W for normalization",
                        extra={"log_type": "debug"},
                    )

            # Warn if results exist but input power is missing (unusual)
            if pd.isna(simulated_power_w) or simulated_power_w <= 0:
                logging.getLogger("progress").warning(
                    f"    - WARNING: Missing or invalid input_power_W in JSON for {detailed_placement_name} at {frequency_mhz}MHz. "
                    "This is unusual - results may not be normalized correctly.",
                    extra={"log_type": "warning"},
                )

            normalization_factor = self.strategy.get_normalization_factor(frequency_mhz, simulated_power_w)
            result_entry, organ_entries = self.strategy.extract_data(
                pickle_data,
                frequency_mhz,
                detailed_placement_name,
                scenario_name,
                simulated_power_w,
                normalization_factor,
                sar_results=sar_results,
            )
            result_entry = self.strategy.apply_bug_fixes(result_entry)

            # Store peak_sar_details for spatial plots
            if "peak_sar_details" in pickle_data:
                result_entry["peak_sar_details"] = pickle_data["peak_sar_details"]
            elif "peak_sar_details" in sar_results:
                result_entry["peak_sar_details"] = sar_results["peak_sar_details"]

            self.all_results.append(result_entry)
            if organ_entries:
                self.all_organ_results.extend(organ_entries)
        except json.JSONDecodeError as e:
            logging.getLogger("progress").error(
                f"    - ERROR: Invalid JSON for {detailed_placement_name} at {frequency_mhz}MHz: {e}",
                extra={"log_type": "error"},
            )
        except Exception as e:
            logging.getLogger("progress").error(
                f"    - ERROR: Could not process data for {detailed_placement_name} at {frequency_mhz}MHz: {e}",
                extra={"log_type": "error"},
            )
            import traceback

            logging.getLogger("progress").debug(traceback.format_exc(), extra={"log_type": "debug"})

    def _load_from_cache(self) -> tuple[pd.DataFrame | None, pd.DataFrame | None]:
        """Loads aggregated results from cached pickle file.

        Returns:
            Tuple of (results_df, organ_results_df) or (None, None) if cache not found.
        """
        output_pickle_path = os.path.join(self.results_base_dir, "aggregated_results.pkl")

        if not os.path.exists(output_pickle_path):
            return None, None

        try:
            with open(output_pickle_path, "rb") as f:
                cached_data = pickle.load(f)

            results_df = cached_data.get("summary_results")
            organ_results_df = cached_data.get("organ_results")

            if results_df is not None:
                logging.getLogger("progress").info(
                    f"--- Loaded {len(results_df)} cached results from: {output_pickle_path} ---",
                    extra={"log_type": "success"},
                )

            return results_df, organ_results_df
        except Exception as e:
            logging.getLogger("progress").error(
                f"--- Error loading cache: {e} ---",
                extra={"log_type": "error"},
            )
            return None, None

    def _convert_units_and_cache(self, results_df: pd.DataFrame, organ_results_df: pd.DataFrame) -> pd.DataFrame:
        """Converts SAR units to mW/kg and caches summary and organ-level results."""
        sar_columns = [col for col in results_df.columns if "SAR" in col]
        results_df[sar_columns] = results_df[sar_columns] * 1000

        output_pickle_path = os.path.join(self.results_base_dir, "aggregated_results.pkl")
        os.makedirs(os.path.dirname(output_pickle_path), exist_ok=True)

        cached_data = {"summary_results": results_df, "organ_results": organ_results_df}
        with open(output_pickle_path, "wb") as f:
            pickle.dump(cached_data, f)

        logging.getLogger("progress").info(
            f"\n--- Aggregated summary and organ results (in mW/kg) cached to: {output_pickle_path} ---",
            extra={"log_type": "success"},
        )
        return results_df

    def _export_reports(self, results_df: pd.DataFrame, all_organ_results_df: pd.DataFrame):
        """Exports aggregated results to CSV files and logs summaries.

        Args:
            results_df: DataFrame with main aggregated results.
            all_organ_results_df: DataFrame with detailed organ-level results.
        """
        # Drop columns that might not exist
        cols_to_drop = []
        if "input_power_w" in results_df.columns:
            cols_to_drop.append("input_power_w")
        if "scenario" in results_df.columns:
            cols_to_drop.append("scenario")

        results_for_export = results_df.drop(columns=cols_to_drop) if cols_to_drop else results_df

        logging.getLogger("progress").info(
            "\n--- Full Normalized Results per Simulation (in mW/kg) ---",
            extra={"log_type": "header"},
        )
        with pd.option_context("display.max_rows", None, "display.max_columns", None, "display.width", 1000):
            sort_cols = [c for c in ["frequency_mhz", "placement"] if c in results_for_export.columns]
            if sort_cols:
                logging.getLogger("progress").info(results_for_export.sort_values(by=sort_cols))
            else:
                logging.getLogger("progress").info(results_for_export)

        summary_stats = self.strategy.calculate_summary_stats(results_df)
        logging.getLogger("progress").info(
            "\n--- Summary Statistics (Mean) of Normalized SAR per Scenario and Frequency (in mW/kg) ---",
            extra={"log_type": "header"},
        )
        with pd.option_context("display.max_rows", None, "display.max_columns", None, "display.width", 1000):
            logging.getLogger("progress").info(summary_stats)

        detailed_csv_path = os.path.join(self.results_base_dir, "normalized_results_detailed.csv")
        summary_csv_path = os.path.join(self.results_base_dir, "normalized_results_summary.csv")
        organ_csv_path = os.path.join(self.results_base_dir, "normalized_results_organs.csv")

        results_for_export.to_csv(detailed_csv_path, index=False)
        summary_stats.to_csv(summary_csv_path)

        if not all_organ_results_df.empty:
            all_organ_results_df.to_csv(organ_csv_path, index=False)
            logging.getLogger("progress").info(
                f"--- Organ-level results saved to: {organ_csv_path} ---",
                extra={"log_type": "success"},
            )

        logging.getLogger("progress").info(
            f"\n--- Detailed results saved to: {detailed_csv_path} ---",
            extra={"log_type": "success"},
        )
        logging.getLogger("progress").info(
            f"--- Summary statistics saved to: {summary_csv_path} ---",
            extra={"log_type": "success"},
        )

    def _generate_plots(self, results_df: pd.DataFrame, all_organ_results_df: pd.DataFrame):
        """Delegates plot generation to the current analysis strategy.

        Args:
            results_df: DataFrame with main aggregated results.
            all_organ_results_df: DataFrame with detailed organ-level results.
        """
        # This method is now delegated to the strategy
        self.strategy.generate_plots(self, self.plotter, results_df, all_organ_results_df)
