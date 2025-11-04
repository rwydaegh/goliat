"""Tests for goliat.analysis strategy classes."""

from unittest.mock import MagicMock, patch


from goliat.analysis.far_field_strategy import FarFieldAnalysisStrategy
from goliat.analysis.near_field_strategy import NearFieldAnalysisStrategy


class TestNearFieldAnalysisStrategy:
    """Tests for NearFieldAnalysisStrategy class."""

    def test_get_results_base_dir(self):
        """Test get_results_base_dir method."""
        mock_config = MagicMock()
        mock_config.base_dir = "/tmp"

        # Mock the abstract methods that are required
        with patch.object(NearFieldAnalysisStrategy, "__abstractmethods__", set()):
            strategy = NearFieldAnalysisStrategy(mock_config, "thelonious")

            results_dir = strategy.get_results_base_dir()
            assert "results" in results_dir
            assert "near_field" in results_dir
            assert "thelonious" in results_dir

    def test_get_plots_dir(self):
        """Test get_plots_dir method."""
        mock_config = MagicMock()
        mock_config.base_dir = "/tmp"

        with patch.object(NearFieldAnalysisStrategy, "__abstractmethods__", set()):
            strategy = NearFieldAnalysisStrategy(mock_config, "thelonious")

            plots_dir = strategy.get_plots_dir()
            assert "plots" in plots_dir
            assert "near_field" in plots_dir
            assert "thelonious" in plots_dir


class TestFarFieldAnalysisStrategy:
    """Tests for FarFieldAnalysisStrategy class."""

    def test_get_results_base_dir(self):
        """Test get_results_base_dir method."""
        mock_config = MagicMock()
        mock_config.base_dir = "/tmp"

        with patch.object(FarFieldAnalysisStrategy, "__abstractmethods__", set()):
            strategy = FarFieldAnalysisStrategy(mock_config, "thelonious")

            results_dir = strategy.get_results_base_dir()
            assert "results" in results_dir
            assert "far_field" in results_dir
            assert "thelonious" in results_dir

    def test_get_plots_dir(self):
        """Test get_plots_dir method."""
        mock_config = MagicMock()
        mock_config.base_dir = "/tmp"

        with patch.object(FarFieldAnalysisStrategy, "__abstractmethods__", set()):
            strategy = FarFieldAnalysisStrategy(mock_config, "thelonious")

            plots_dir = strategy.get_plots_dir()
            assert "plots" in plots_dir
            assert "far_field" in plots_dir
            assert "thelonious" in plots_dir
