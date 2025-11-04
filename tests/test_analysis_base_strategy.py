"""Tests for goliat.analysis.base_strategy module."""

from unittest.mock import MagicMock

import pytest

from goliat.analysis.base_strategy import BaseAnalysisStrategy


class TestBaseAnalysisStrategy:
    """Tests for BaseAnalysisStrategy base class."""

    def test_base_strategy_initialization(self):
        """Test BaseAnalysisStrategy initialization."""
        mock_config = MagicMock()
        mock_config.base_dir = "/tmp"

        # Create a concrete implementation for testing
        class TestStrategy(BaseAnalysisStrategy):
            def get_results_base_dir(self):
                return "/tmp/results"

            def get_plots_dir(self):
                return "/tmp/plots"

            def load_and_process_results(self, analyzer):
                pass

            def get_normalization_factor(self, frequency_mhz, simulated_power_w):
                return 1.0

            def extract_data(self, pickle_data, frequency_mhz, placement_name, scenario_name, sim_power, norm_factor):
                return {}, []

            def apply_bug_fixes(self, result_entry):
                return result_entry

            def calculate_summary_stats(self, results_df):
                return results_df

            def generate_plots(self, analyzer, plotter, results_df, all_organ_results_df):
                pass

        strategy = TestStrategy(mock_config, "thelonious")

        assert strategy.config == mock_config
        assert strategy.phantom_name == "thelonious"
        assert strategy.base_dir == "/tmp"

    def test_base_strategy_abstract_methods(self):
        """Test that abstract methods prevent instantiation when not implemented."""
        mock_config = MagicMock()
        mock_config.base_dir = "/tmp"

        # Test that we can't instantiate incomplete strategy
        # Python's ABC will raise TypeError at instantiation time
        class IncompleteStrategy(BaseAnalysisStrategy):
            def get_results_base_dir(self):
                return "/tmp/results"

            def get_plots_dir(self):
                return "/tmp/plots"

        # Should raise TypeError because abstract methods are not implemented
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            IncompleteStrategy(mock_config, "thelonious")
