"""Tests for goliat.analysis.analyzer module."""

from unittest.mock import MagicMock, patch

import pytest

from goliat.analysis.analyzer import Analyzer


@pytest.fixture
def mock_config():
    """Create a mock config."""
    config = MagicMock()
    config.base_dir = "/tmp"
    return config


@pytest.fixture
def mock_strategy():
    """Create a mock strategy."""
    strategy = MagicMock()
    strategy.get_results_base_dir.return_value = "/tmp/results"
    strategy.get_plots_dir.return_value = "/tmp/plots"
    return strategy


class TestAnalyzer:
    """Tests for Analyzer class."""

    def test_analyzer_initialization(self, mock_config, mock_strategy):
        """Test analyzer initialization."""
        analyzer = Analyzer(mock_config, "thelonious", mock_strategy)

        assert analyzer.config == mock_config
        assert analyzer.phantom_name == "thelonious"
        assert analyzer.strategy == mock_strategy
        assert analyzer.all_results == []
        assert analyzer.all_organ_results == []
        assert "eyes_group" in analyzer.tissue_group_definitions
        assert "brain_group" in analyzer.tissue_group_definitions
        assert "skin_group" in analyzer.tissue_group_definitions

    def test_analyzer_tissue_group_definitions(self, mock_config, mock_strategy):
        """Test that tissue group definitions are correct."""
        analyzer = Analyzer(mock_config, "thelonious", mock_strategy)

        # Check eyes group
        assert "eye" in analyzer.tissue_group_definitions["eyes_group"]
        assert "cornea" in analyzer.tissue_group_definitions["eyes_group"]
        assert "lens" in analyzer.tissue_group_definitions["eyes_group"]

        # Check brain group
        assert "brain" in analyzer.tissue_group_definitions["brain_group"]
        assert "cerebellum" in analyzer.tissue_group_definitions["brain_group"]
        assert "hippocampus" in analyzer.tissue_group_definitions["brain_group"]

        # Check skin group
        assert analyzer.tissue_group_definitions["skin_group"] == ["skin"]

    def test_analyzer_process_single_result_near_field(self, mock_config, mock_strategy):
        """Test processing single result for near-field."""
        mock_strategy.__class__.__name__ = "NearFieldAnalysisStrategy"
        analyzer = Analyzer(mock_config, "thelonious", mock_strategy)

        # Mock file system
        with patch("os.path.exists", return_value=False):
            analyzer._process_single_result(700, "by_cheek", "center", "vertical")

        # Should handle missing files gracefully
        assert len(analyzer.all_results) == 0

    def test_analyzer_process_single_result_far_field(self, mock_config, mock_strategy):
        """Test processing single result for far-field."""
        mock_strategy.__class__.__name__ = "FarFieldAnalysisStrategy"
        analyzer = Analyzer(mock_config, "thelonious", mock_strategy)

        # Mock file system
        with patch("os.path.exists", return_value=False):
            analyzer._process_single_result(700, "scenario", "full_placement_name", "orient")

        # Should handle missing files gracefully
        assert len(analyzer.all_results) == 0

    @patch("goliat.analysis.analyzer.pd.DataFrame")
    @patch("goliat.analysis.analyzer.logging")
    def test_analyzer_run_analysis_no_results(self, mock_logging, mock_df, mock_config, mock_strategy):
        """Test running analysis with no results."""
        analyzer = Analyzer(mock_config, "thelonious", mock_strategy)
        analyzer.all_results = []  # No results

        analyzer.run_analysis()

        # Should log warning about no results
        mock_logging.getLogger.return_value.info.assert_called()

    @patch("goliat.analysis.analyzer.pd.DataFrame")
    @patch("goliat.analysis.analyzer.logging")
    def test_analyzer_run_analysis_with_results(self, mock_logging, mock_df, mock_config, mock_strategy):
        """Test running analysis with results."""
        analyzer = Analyzer(mock_config, "thelonious", mock_strategy)
        analyzer.all_results = [{"test": "data"}]

        # Mock DataFrame
        mock_df_instance = MagicMock()
        mock_df.return_value = mock_df_instance

        # Mock strategy methods
        mock_strategy.load_and_process_results = MagicMock()
        analyzer._convert_units_and_cache = MagicMock(return_value=mock_df_instance)
        analyzer._export_reports = MagicMock()
        mock_strategy.generate_plots = MagicMock()

        analyzer.run_analysis()

        # Should call strategy methods
        mock_strategy.load_and_process_results.assert_called_once()
        analyzer._convert_units_and_cache.assert_called_once()
        analyzer._export_reports.assert_called_once()
        mock_strategy.generate_plots.assert_called_once()
