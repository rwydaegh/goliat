from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from ..config import Config
    from .analyzer import Analyzer
    from .plotter import Plotter


class BaseAnalysisStrategy(ABC):
    """Abstract base class for analysis strategies."""

    def __init__(self, config: "Config", phantom_name: str):
        """Initializes the analysis strategy.

        Args:
            config: The main configuration object.
            phantom_name: The name of the phantom being analyzed.
        """
        self.config = config
        self.phantom_name = phantom_name
        self.base_dir = config.base_dir

    @abstractmethod
    def get_results_base_dir(self) -> str:
        """Gets the base directory for results."""
        pass

    @abstractmethod
    def get_plots_dir(self) -> str:
        """Gets the directory for saving plots."""
        pass

    @abstractmethod
    def load_and_process_results(self, analyzer: "Analyzer"):
        """Loads and processes all relevant simulation results.

        Args:
            analyzer: The main analyzer instance calling the strategy.
        """
        pass

    @abstractmethod
    def get_normalization_factor(self, frequency_mhz: int, simulated_power_w: float) -> float:
        """Calculates the normalization factor for SAR values.

        Args:
            frequency_mhz: The simulation frequency in MHz.
            simulated_power_w: The input power from the simulation in Watts.

        Returns:
            The calculated normalization factor.
        """
        pass

    @abstractmethod
    def extract_data(
        self,
        pickle_data: dict,
        frequency_mhz: int,
        detailed_name: str,
        scenario_name: str,
        sim_power: float,
        norm_factor: float,
    ) -> tuple[dict, list]:
        """Extracts and structures data from a single simulation's result files.

        Args:
            pickle_data: Data loaded from the .pkl result file.
            frequency_mhz: The simulation frequency.
            detailed_name: The detailed name of the placement or scenario.
            scenario_name: The general scenario name.
            sim_power: The simulated input power in Watts.
            norm_factor: The normalization factor to apply.

        Returns:
            A tuple containing the main result entry and a list of organ-specific entries.
        """
        pass

    @abstractmethod
    def apply_bug_fixes(self, result_entry: dict) -> dict:
        """Applies workarounds for known data inconsistencies.

        Args:
            result_entry: The data entry for a single simulation result.

        Returns:
            The corrected result entry.
        """
        return result_entry

    @abstractmethod
    def calculate_summary_stats(self, results_df: pd.DataFrame) -> pd.DataFrame:
        """Calculates summary statistics from the aggregated results.

        Args:
            results_df: DataFrame with all aggregated simulation results.

        Returns:
            A DataFrame with summary statistics.
        """
        pass

    @abstractmethod
    def generate_plots(
        self,
        analyzer: "Analyzer",
        plotter: "Plotter",
        results_df: pd.DataFrame,
        all_organ_results_df: pd.DataFrame,
    ):
        """Generates all plots relevant to this analysis strategy.

        Args:
            analyzer: The main analyzer instance.
            plotter: The plotter instance to use for generating plots.
            results_df: DataFrame with main aggregated results.
            all_organ_results_df: DataFrame with detailed organ-level results.
        """
        pass
