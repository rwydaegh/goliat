import logging
import os
from typing import TYPE_CHECKING

import pandas as pd

from .base_strategy import BaseAnalysisStrategy

if TYPE_CHECKING:
    from .analyzer import Analyzer
    from .plotter import Plotter


class NearFieldAnalysisStrategy(BaseAnalysisStrategy):
    """Analysis strategy for near-field simulations.

    Handles result loading, normalization, and plot generation for near-field
    studies with placement scenarios, positions, and orientations.
    """

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
    ) -> tuple[dict, list]:
        """Extracts and normalizes SAR data from a single near-field result.

        Args:
            pickle_data: Data loaded from the .pkl result file.
            frequency_mhz: The simulation frequency.
            placement_name: The detailed name of the placement.
            scenario_name: The general scenario name (e.g., 'by_cheek').
            sim_power: The simulated input power in Watts.
            norm_factor: The normalization factor to apply to SAR values.

        Returns:
            A tuple containing the main result entry and a list of organ-specific entries.
        """
        summary_results = pickle_data.get("summary_results", {})
        grouped_stats = pickle_data.get("grouped_sar_stats", {})
        detailed_df = pickle_data.get("detailed_sar_stats")
        result_entry = {
            "frequency_mhz": frequency_mhz,
            "placement": placement_name,
            "scenario": scenario_name,
            "input_power_w": sim_power,
            "SAR_head": summary_results.get("head_SAR", pd.NA) * norm_factor,
            "SAR_trunk": summary_results.get("trunk_SAR", pd.NA) * norm_factor,
        }
        for group_name, stats in grouped_stats.items():
            key = f"psSAR10g_{group_name.replace('_group', '')}"
            result_entry[key] = stats.get("peak_sar", pd.NA) * norm_factor

        organ_entries = []
        if detailed_df is not None:
            peak_sar_col = "Peak Spatial-Average SAR[IEEE/IEC62704-1] (10g)"
            for _, row in detailed_df.iterrows():
                organ_entries.append(
                    {
                        "frequency_mhz": frequency_mhz,
                        "placement": placement_name,
                        "tissue": row["Tissue"],
                        "mass_avg_sar_mw_kg": row["Mass-Averaged SAR"] * norm_factor * 1000,
                        "peak_sar_10g_mw_kg": row.get(peak_sar_col, pd.NA) * norm_factor * 1000,
                        "min_local_sar_mw_kg": row.get("Min. local SAR", pd.NA) * norm_factor * 1000,
                        "max_local_sar_mw_kg": row.get("Max. local SAR", pd.NA) * norm_factor * 1000,
                    }
                )
        return result_entry, organ_entries

    # def apply_bug_fixes(self, result_entry: dict) -> dict:
    #     """Applies a workaround for Head SAR being miscategorized as Trunk SAR.
    #
    #     Args:
    #         result_entry: The data entry for a single simulation result.
    #
    #     Returns:
    #         The corrected result entry.
    #     """
    #     placement = result_entry.get("placement", "").lower()
    #     if placement.startswith("front_of_eyes") or placement.startswith("by_cheek"):
    #         sar_head = result_entry.get("SAR_head")
    #         sar_trunk = result_entry.get("SAR_trunk")
    #         if bool(pd.isna(sar_head)) and bool(pd.notna(sar_trunk)):
    #             result_entry["SAR_head"] = sar_trunk
    #             result_entry["SAR_trunk"] = pd.NA
    #     return result_entry

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
            scenario_name = idx  # Index is a tuple (scenario, frequency)
            completed = completion_counts.get(idx, 0)
            total = placements_per_scenario.get(scenario_name, 0)
            return f"{completed}/{total}"

        if not summary_stats.empty:
            summary_stats["progress"] = summary_stats.index.map(get_progress)  # type: ignore
        return pd.DataFrame(summary_stats)

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
                plotter.plot_average_sar_bar(scenario_name, pd.DataFrame(avg_results), pd.Series(progress_info))
                plotter.plot_pssar_line(scenario_name, pd.DataFrame(avg_results))
            plotter.plot_sar_distribution_boxplots(scenario_name, pd.DataFrame(scenario_results_df))
