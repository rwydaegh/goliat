import os
from abc import ABC, abstractmethod

import pandas as pd


class BaseAnalysisStrategy(ABC):
    """
    Abstract base class for analysis strategies.
    """

    def __init__(self, config, phantom_name):
        """Initializes the analysis strategy.

        Args:
            config (Config): The main configuration object.
            phantom_name (str): The name of the phantom being analyzed.
        """
        self.config = config
        self.phantom_name = phantom_name
        self.base_dir = config.base_dir

    @abstractmethod
    def get_results_base_dir(self):
        """Returns the base directory where results for this strategy are stored."""
        pass

    @abstractmethod
    def get_plots_dir(self):
        """Returns the directory where plots for this strategy should be saved."""
        pass

    @abstractmethod
    def load_and_process_results(self, analyzer):
        """Loads and processes all relevant simulation results for the analysis.

        Args:
            analyzer (Analyzer): The main analyzer instance calling the strategy.
        """
        pass

    @abstractmethod
    def get_normalization_factor(self, frequency_mhz, simulated_power_w):
        """Calculates the normalization factor to apply to SAR values.

        Args:
            frequency_mhz (int): The simulation frequency in MHz.
            simulated_power_w (float): The input power from the simulation in Watts.

        Returns:
            float: The calculated normalization factor.
        """
        pass

    @abstractmethod
    def extract_data(
        self,
        pickle_data,
        frequency_mhz,
        detailed_name,
        scenario_name,
        sim_power,
        norm_factor,
    ):
        """Extracts and structures data from a single simulation's result files.

        Args:
            pickle_data (dict): Data loaded from the .pkl result file.
            frequency_mhz (int): The simulation frequency.
            detailed_name (str): The detailed name of the placement or scenario.
            scenario_name (str): The general scenario name.
            sim_power (float): The simulated input power in Watts.
            norm_factor (float): The normalization factor to apply.

        Returns:
            tuple: A tuple containing the main result entry (dict) and a list of organ-specific entries (list of dicts).
        """
        pass

    @abstractmethod
    def apply_bug_fixes(self, result_entry):
        """Applies any necessary workarounds or fixes for known data inconsistencies.

        Args:
            result_entry (dict): The data entry for a single simulation result.

        Returns:
            dict: The corrected result entry.
        """
        return result_entry

    @abstractmethod
    def calculate_summary_stats(self, results_df):
        """Calculates summary statistics from the aggregated results DataFrame.

        Args:
            results_df (pd.DataFrame): The DataFrame containing all aggregated simulation results.

        Returns:
            pd.DataFrame: A DataFrame with summary statistics.
        """
        pass

    @abstractmethod
    def generate_plots(self, analyzer, plotter, results_df, all_organ_results_df):
        """Generates all plots relevant to this analysis strategy.

        Args:
            analyzer (Analyzer): The main analyzer instance.
            plotter (Plotter): The plotter instance to use for generating plots.
            results_df (pd.DataFrame): The DataFrame with main aggregated results.
            all_organ_results_df (pd.DataFrame): The DataFrame with detailed organ-level results.
        """
        pass