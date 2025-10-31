from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from ..config import Config
    from .analyzer import Analyzer
    from .plotter import Plotter


class BaseAnalysisStrategy(ABC):
    """Base class for analysis strategies.

    Defines interface for loading results, calculating normalization factors,
    and generating plots. Subclasses implement study-type specific logic.
    """

    def __init__(self, config: "Config", phantom_name: str):
        """Sets up the analysis strategy.

        Args:
            config: Configuration object.
            phantom_name: Phantom model name being analyzed.
        """
        self.config = config
        self.phantom_name = phantom_name
        self.base_dir = config.base_dir

    def get_results_base_dir(self) -> str:
        """Returns base directory path for results. Must be implemented by subclasses."""
        raise NotImplementedError

    def get_plots_dir(self) -> str:
        """Returns directory path for saving plots. Must be implemented by subclasses."""
        raise NotImplementedError

    @abstractmethod
    def load_and_process_results(self, analyzer: "Analyzer"):
        """Loads and processes all simulation results.

        Iterates through configured scenarios and calls analyzer._process_single_result()
        for each one.

        Args:
            analyzer: Analyzer instance to process results with.
        """
        pass

    @abstractmethod
    def get_normalization_factor(self, frequency_mhz: int, simulated_power_w: float) -> float:
        """Calculates SAR normalization factor from simulated power.

        Args:
            frequency_mhz: Simulation frequency in MHz.
            simulated_power_w: Input power from simulation in Watts.

        Returns:
            Normalization factor to multiply SAR values by.
        """
        pass

    @abstractmethod
    def extract_data(
        self,
        pickle_data: dict,
        frequency_mhz: int,
        placement_name: str,
        scenario_name: str,
        sim_power: float,
        norm_factor: float,
    ) -> tuple[dict, list]:
        """Extracts and structures data from a single simulation's result files.

        Args:
            pickle_data: Data loaded from the .pkl result file.
            frequency_mhz: Simulation frequency.
            placement_name: Detailed placement name.
            scenario_name: General scenario name.
            sim_power: Simulated input power in Watts.
            norm_factor: Normalization factor to apply.

        Returns:
            Tuple of (main result entry dict, list of organ-specific entries).
        """
        pass

    @abstractmethod
    def apply_bug_fixes(self, result_entry: dict) -> dict:
        """Applies workarounds for known data inconsistencies.

        Args:
            result_entry: Data entry for a single simulation result.

        Returns:
            Corrected result entry.
        """
        return result_entry

    @abstractmethod
    def calculate_summary_stats(self, results_df: pd.DataFrame) -> pd.DataFrame:
        """Calculates summary statistics from aggregated results.

        Args:
            results_df: DataFrame with all aggregated simulation results.

        Returns:
            DataFrame with summary statistics.
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
        """Generates study-type specific plots.

        Args:
            analyzer: Analyzer instance with aggregated data.
            plotter: Plotter instance for creating figures.
            results_df: DataFrame with summary results.
            all_organ_results_df: DataFrame with organ-level details.
        """
        pass
