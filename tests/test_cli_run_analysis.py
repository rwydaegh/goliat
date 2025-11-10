"""Tests for CLI run_analysis module."""

from unittest.mock import MagicMock, patch

import pytest

# Note: We mock the strategy and analyzer classes, so we don't need to import them


@pytest.fixture
def cli_run_analysis_module():
    """Fixture to import cli.run_analysis with initial_setup patched."""
    with patch("goliat.utils.setup.initial_setup"):
        import cli.run_analysis

        return cli.run_analysis


class TestRunAnalysis:
    """Tests for run_analysis CLI module."""

    def test_main_near_field(self, cli_run_analysis_module):
        """Test main function with near-field study."""
        # Setup mocks
        mock_config = MagicMock()
        mock_config.__getitem__.side_effect = lambda key: {
            "phantoms": ["thelonious"],
            "study_type": "near_field",
        }.get(key)

        # Mock the strategy and analyzer imports
        with patch("cli.run_analysis.initial_setup"), patch("cli.run_analysis.setup_loggers"), patch(
            "cli.run_analysis.Config", return_value=mock_config
        ), patch("cli.run_analysis.NearFieldAnalysisStrategy") as mock_strategy, patch("cli.run_analysis.Analyzer") as mock_analyzer:
            mock_strategy_instance = MagicMock()
            mock_strategy.return_value = mock_strategy_instance
            mock_analyzer_instance = MagicMock()
            mock_analyzer.return_value = mock_analyzer_instance

            # Mock argparse
            with patch("sys.argv", ["run_analysis.py", "--config", "test_config.json"]):
                cli_run_analysis_module.main()

    def test_main_far_field(self, cli_run_analysis_module):
        """Test main function with far-field study."""
        mock_config = MagicMock()
        mock_config.__getitem__.side_effect = lambda key: {
            "phantoms": ["thelonious"],
            "study_type": "far_field",
        }.get(key)

        with patch("cli.run_analysis.initial_setup"), patch("cli.run_analysis.setup_loggers"), patch(
            "cli.run_analysis.Config", return_value=mock_config
        ), patch("cli.run_analysis.FarFieldAnalysisStrategy") as mock_strategy, patch("cli.run_analysis.Analyzer") as mock_analyzer:
            mock_strategy_instance = MagicMock()
            mock_strategy.return_value = mock_strategy_instance
            mock_analyzer_instance = MagicMock()
            mock_analyzer.return_value = mock_analyzer_instance

            with patch("sys.argv", ["run_analysis.py", "--config", "test_config.json"]):
                cli_run_analysis_module.main()

    def test_main_no_phantoms(self, cli_run_analysis_module):
        """Test main function with no phantoms."""
        mock_config = MagicMock()
        mock_config.__getitem__.side_effect = lambda key: {
            "phantoms": [],
            "study_type": "near_field",
        }.get(key)

        mock_logger = MagicMock()

        with patch("cli.run_analysis.initial_setup"), patch("cli.run_analysis.setup_loggers"), patch(
            "cli.run_analysis.Config", return_value=mock_config
        ), patch("cli.run_analysis.logging") as mock_logging:
            mock_logging.getLogger.return_value = mock_logger

            with patch("sys.argv", ["run_analysis.py", "--config", "test_config.json"]):
                cli_run_analysis_module.main()

        # Should log error
        mock_logger.error.assert_called()

    def test_main_no_study_type(self, cli_run_analysis_module):
        """Test main function with no study_type."""
        mock_config = MagicMock()
        mock_config.__getitem__.side_effect = lambda key: {
            "phantoms": ["thelonious"],
            "study_type": None,
        }.get(key)

        mock_logger = MagicMock()

        with patch("cli.run_analysis.initial_setup"), patch("cli.run_analysis.setup_loggers"), patch(
            "cli.run_analysis.Config", return_value=mock_config
        ), patch("cli.run_analysis.logging") as mock_logging:
            mock_logging.getLogger.return_value = mock_logger

            with patch("sys.argv", ["run_analysis.py", "--config", "test_config.json"]):
                cli_run_analysis_module.main()

        # Should log error
        mock_logger.error.assert_called()
