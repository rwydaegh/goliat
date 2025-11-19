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

    def __init__(self, config: "Config", phantom_name: str, strategy: "BaseAnalysisStrategy"):
        """Sets up the analyzer with a strategy.

        Args:
            config: Configuration object.
            phantom_name: Phantom model name being analyzed.
            strategy: Strategy implementation for analysis logic.
        """
        self.config = config
        self.base_dir = config.base_dir
        self.phantom_name = phantom_name
        self.strategy = strategy
        self.results_base_dir = self.strategy.get_results_base_dir()
        self.plotter = Plotter(self.strategy.get_plots_dir())
        self.all_results = []
        self.all_organ_results = []
        self.tissue_group_definitions = {
            "eyes_group": ["eye", "cornea", "sclera", "lens", "vitreous"],
            "skin_group": ["skin"],
            "brain_group": [
                "brain",
                "commissura",
                "midbrain",
                "pineal",
                "hypophysis",
                "medulla",
                "pons",
                "thalamus",
                "hippocampus",
                "cerebellum",
            ],
        }

    def run_analysis(self):
        """Runs complete analysis pipeline using the selected strategy.

        Loads results, converts units, exports reports, and generates plots.
        Delegates strategy-specific logic to the strategy instance.
        """
        logging.getLogger("progress").info(
            f"--- Starting Results Analysis for Phantom: {self.phantom_name} ---",
            extra={"log_type": "header"},
        )
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
            )
            result_entry = self.strategy.apply_bug_fixes(result_entry)
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
