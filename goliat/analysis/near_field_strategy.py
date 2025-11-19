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
        """Iterates through near-field results and processes each one.
        
        First tries config-based discovery, then falls back to directory scanning
        if config is incomplete or missing.
        """
        antenna_config = self.config["antenna_config"] or {}
        placement_scenarios = self.config["placement_scenarios"] or {}
        
        # Try config-based discovery first
        if antenna_config and placement_scenarios:
            self._load_from_config(analyzer, antenna_config, placement_scenarios)
        else:
            # Fall back to directory discovery
            logging.getLogger("progress").info(
                "  - Config incomplete, using directory discovery mode...",
                extra={"log_type": "info"},
            )
            self._load_from_directory_discovery(analyzer)
    
    def _load_from_config(self, analyzer: "Analyzer", antenna_config: dict, placement_scenarios: dict):
        """Loads results based on config file structure."""
        frequencies = antenna_config.keys()
        
        for freq in frequencies:
            frequency_mhz = int(freq)
            for scenario_name, scenario_def in placement_scenarios.items():
                if not scenario_def:
                    continue
                positions = scenario_def["positions"] if "positions" in scenario_def else {}
                orientations = scenario_def["orientations"] if "orientations" in scenario_def else {}
                if not positions or not orientations:
                    continue
                for pos_name in positions.keys():
                    for orient_name in orientations.keys():
                        analyzer._process_single_result(frequency_mhz, scenario_name, pos_name, orient_name)
    
    def _load_from_directory_discovery(self, analyzer: "Analyzer"):
        """Discovers and processes results by scanning result directories.
        
        Parses placement names automatically and handles partial results gracefully.
        """
        results_base_dir = self.get_results_base_dir()
        if not os.path.exists(results_base_dir):
            logging.getLogger("progress").warning(
                f"  - Results directory not found: {results_base_dir}",
                extra={"log_type": "warning"},
            )
            return
        
        # Scan for frequency directories
        for item in os.listdir(results_base_dir):
            freq_dir = os.path.join(results_base_dir, item)
            if not os.path.isdir(freq_dir):
                continue
            
            # Extract frequency from directory name (e.g., "1450MHz" -> 1450)
            try:
                if item.endswith("MHz"):
                    frequency_mhz = int(item[:-3])
                else:
                    frequency_mhz = int(item)
            except ValueError:
                continue
            
            # Scan for placement directories
            for placement_dir in os.listdir(freq_dir):
                placement_path = os.path.join(freq_dir, placement_dir)
                if not os.path.isdir(placement_path):
                    continue
                
                # Parse placement name to extract scenario, position, orientation
                scenario_name, pos_name, orient_name = self._parse_placement_name(placement_dir)
                
                # Process this result
                analyzer._process_single_result(frequency_mhz, scenario_name, pos_name, orient_name)
    
    def _parse_placement_name(self, placement_name: str) -> tuple[str, str, str]:
        """Parses placement directory name to extract scenario, position, orientation.
        
        Examples:
            "by_belly_up_vertical" -> ("by_belly", "up", "vertical")
            "by_cheek_tragus_cheek_base" -> ("by_cheek_tragus", "cheek", "base")
            "front_of_eyes_center_horizontal" -> ("front_of_eyes", "center", "horizontal")
        
        Args:
            placement_name: Directory name like "by_belly_up_vertical"
        
        Returns:
            Tuple of (scenario_name, position_name, orientation_name)
        """
        parts = placement_name.split("_")
        
        # Common patterns: scenario_pos_orient or scenario_sub_pos_orient
        # Try to identify scenario prefixes
        scenario_prefixes = ["by_", "front_of_", "on_", "near_"]
        
        scenario_end_idx = 1
        for i, part in enumerate(parts):
            if any(prefix in "_".join(parts[:i+1]) for prefix in scenario_prefixes):
                scenario_end_idx = i + 1
        
        # Last two parts are typically position and orientation
        if len(parts) >= 3:
            scenario_name = "_".join(parts[:scenario_end_idx])
            pos_name = "_".join(parts[scenario_end_idx:-1]) if scenario_end_idx < len(parts) - 1 else parts[-2]
            orient_name = parts[-1]
        elif len(parts) == 2:
            scenario_name = parts[0]
            pos_name = parts[1]
            orient_name = ""
        else:
            scenario_name = placement_name
            pos_name = ""
            orient_name = ""
        
        return scenario_name, pos_name, orient_name

    def get_normalization_factor(self, frequency_mhz: int, simulated_power_w: float) -> float:
        """Calculates the normalization factor based on the target power.

        Args:
            frequency_mhz: The simulation frequency in MHz.
            simulated_power_w: The input power from the simulation in Watts.

        Returns:
            The calculated normalization factor, or 1.0 (no normalization) if target power not specified.
        """
        antenna_configs = self.config["antenna_config"] or {}
        freq_config = antenna_configs[str(frequency_mhz)] if str(frequency_mhz) in antenna_configs else {}
        target_power_mw = freq_config["target_power_mW"] if "target_power_mW" in freq_config else None
        
        # Warn if we have results but no input power (unusual situation)
        if pd.isna(simulated_power_w) or simulated_power_w <= 0:
            logging.getLogger("progress").warning(
                f"  - WARNING: Missing or invalid input_power_W ({simulated_power_w}) for {frequency_mhz}MHz. "
                "Cannot normalize SAR values.",
                extra={"log_type": "warning"},
            )
            return 1.0
        
        # Only normalize if target power is specified in config
        if target_power_mw is not None:
            target_power_w = target_power_mw / 1000.0
            return target_power_w / simulated_power_w
        
        # No normalization if target power not specified (this is normal, no warning needed)
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
        
        # Safely extract SAR values with defaults
        # Handle whole_body_sar, head_SAR, and trunk_SAR
        whole_body_sar = summary_results.get("whole_body_sar", pd.NA)
        head_sar = summary_results.get("head_SAR", pd.NA)
        trunk_sar = summary_results.get("trunk_SAR", pd.NA)
        
        # Extract power balance data if available
        power_balance = summary_results.get("power_balance", {})
        
        result_entry = {
            "frequency_mhz": frequency_mhz,
            "placement": placement_name,
            "scenario": scenario_name,
            "input_power_w": sim_power,
            "SAR_head": head_sar * norm_factor if pd.notna(head_sar) else pd.NA,
            "SAR_trunk": trunk_sar * norm_factor if pd.notna(trunk_sar) else pd.NA,
            "SAR_whole_body": whole_body_sar * norm_factor if pd.notna(whole_body_sar) else pd.NA,
            "power_balance_pct": power_balance.get("Balance", pd.NA) if power_balance else pd.NA,
            "power_pin_W": power_balance.get("Pin", pd.NA) if power_balance else pd.NA,
            "power_diel_loss_W": power_balance.get("DielLoss", pd.NA) if power_balance else pd.NA,
            "power_rad_W": power_balance.get("RadPower", pd.NA) if power_balance else pd.NA,
            "power_sibc_loss_W": power_balance.get("SIBCLoss", pd.NA) if power_balance else pd.NA,
        }
        
        # Extract group-level peak SAR
        if grouped_stats:
            for group_name, stats in grouped_stats.items():
                if stats and isinstance(stats, dict):
                    key = f"psSAR10g_{group_name.replace('_group', '')}"
                    peak_sar = stats.get("peak_sar", pd.NA)
                    result_entry[key] = peak_sar * norm_factor if pd.notna(peak_sar) else pd.NA

        organ_entries = []
        if detailed_df is not None and not detailed_df.empty:
            peak_sar_col = "Peak Spatial-Average SAR[IEEE/IEC62704-1] (10g)"
            for _, row in detailed_df.iterrows():
                mass_avg = row.get("Mass-Averaged SAR", pd.NA)
                peak_sar = row.get(peak_sar_col, pd.NA)
                min_sar = row.get("Min. local SAR", pd.NA)
                max_sar = row.get("Max. local SAR", pd.NA)
                
                organ_entries.append(
                    {
                        "frequency_mhz": frequency_mhz,
                        "placement": placement_name,
                        "tissue": row.get("Tissue", "Unknown"),
                        "mass_avg_sar_mw_kg": mass_avg * norm_factor * 1000 if pd.notna(mass_avg) else pd.NA,
                        "peak_sar_10g_mw_kg": peak_sar * norm_factor * 1000 if pd.notna(peak_sar) else pd.NA,
                        "min_local_sar_mw_kg": min_sar * norm_factor * 1000 if pd.notna(min_sar) else pd.NA,
                        "max_local_sar_mw_kg": max_sar * norm_factor * 1000 if pd.notna(max_sar) else pd.NA,
                    }
                )
        return result_entry, organ_entries

    def apply_bug_fixes(self, result_entry: dict) -> dict:
        """Applies bug fixes to result entries.
        
        Currently no bug fixes needed, but method must exist for abstract base class.
        
        Args:
            result_entry: The data entry for a single simulation result.
        
        Returns:
            The (possibly corrected) result entry.
        """
        return result_entry

    def calculate_summary_stats(self, results_df: pd.DataFrame) -> pd.DataFrame:
        """Calculates summary statistics, including completion progress.

        Args:
            results_df: DataFrame with all aggregated simulation results.

        Returns:
            A DataFrame with mean SAR values and a 'progress' column.
        """
        placement_scenarios = self.config["placement_scenarios"] or {}
        placements_per_scenario = {}
        
        # Calculate expected placements from config if available
        logging.getLogger("progress").info(
            "\n--- Calculating Total Possible Placements per Scenario ---",
            extra={"log_type": "header"},
        )
        if placement_scenarios:
            for name, definition in placement_scenarios.items():
                if not definition:
                    continue
                positions = definition["positions"] if "positions" in definition else {}
                orientations = definition["orientations"] if "orientations" in definition else {}
                if positions and orientations:
                    total = len(positions) * len(orientations)
                    placements_per_scenario[name] = total
                    logging.getLogger("progress").info(
                        f"- Scenario '{name}': {total} placements", 
                        extra={"log_type": "info"}
                    )
        
        # Calculate actual counts from data
        summary_stats = results_df.groupby(["scenario", "frequency_mhz"]).mean(numeric_only=True)
        completion_counts = results_df.groupby(["scenario", "frequency_mhz"]).size()

        # Define a mapping function that safely handles potential missing keys
        def get_progress(idx):
            if isinstance(idx, tuple):
                scenario_name = idx[0]  # First element is scenario
            else:
                scenario_name = idx
            completed = completion_counts.get(idx, 0)
            total = placements_per_scenario.get(scenario_name, completed)  # Use completed as fallback
            return f"{completed}/{total}"

        if not summary_stats.empty:
            try:
                summary_stats["progress"] = summary_stats.index.map(get_progress)  # type: ignore
            except Exception as e:
                logging.getLogger("progress").warning(
                    f"  - Could not add progress column: {e}",
                    extra={"log_type": "warning"},
                )
                # Add a simple count instead
                summary_stats["progress"] = completion_counts
        
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
        
        # Generate overall power balance plots for all scenarios
        plotter.plot_power_balance_overview(results_df)
