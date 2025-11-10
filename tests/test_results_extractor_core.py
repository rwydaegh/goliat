"""Tests for goliat.results_extractor module core functionality."""

import json
from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.skip_on_ci
class TestResultsExtractor:
    """Tests for ResultsExtractor class."""

    @pytest.fixture
    def mock_simulation(self):
        """Create a mock simulation object."""
        mock_sim = MagicMock()
        mock_results = MagicMock()
        mock_sim.Results.return_value = mock_results
        return mock_sim

    @pytest.fixture
    def mock_config(self):
        """Create a mock config object."""
        config = MagicMock()
        config.__getitem__.side_effect = lambda key: 0 if "number_of_point_sensors" in key else None
        config.get_auto_cleanup_previous_results.return_value = False
        config.base_dir = "/tmp"
        return config

    def test_results_extractor_initialization(self, mock_config, mock_simulation):
        """Test ResultsExtractor initialization."""
        from goliat.results_extractor import ResultsExtractor

        extractor = ResultsExtractor.from_params(
            config=mock_config,
            simulation=mock_simulation,
            phantom_name="thelonious",
            frequency_mhz=700,
            scenario_name="by_cheek",
            position_name="center",
            orientation_name="vertical",
            study_type="near_field",
            verbose_logger=MagicMock(),
            progress_logger=MagicMock(),
            free_space=False,
            gui=None,
            study=None,
        )

        assert extractor.phantom_name == "thelonious"
        assert extractor.frequency_mhz == 700
        assert extractor.placement_name == "by_cheek_center_vertical"
        assert extractor.study_type == "near_field"
        assert extractor.free_space is False

    def test_results_extractor_get_deliverable_filenames(self):
        """Test get_deliverable_filenames static method."""
        from goliat.results_extractor import ResultsExtractor

        filenames = ResultsExtractor.get_deliverable_filenames()

        assert "json" in filenames
        assert "pkl" in filenames
        assert "html" in filenames
        assert filenames["json"] == "sar_results.json"
        assert filenames["pkl"] == "sar_stats_all_tissues.pkl"
        assert filenames["html"] == "sar_stats_all_tissues.html"

    def test_results_extractor_extract_no_simulation(self, mock_config):
        """Test extract() when simulation is None."""
        from goliat.results_extractor import ResultsExtractor

        extractor = ResultsExtractor.from_params(
            config=mock_config,
            simulation=None,
            phantom_name="thelonious",
            frequency_mhz=700,
            scenario_name="by_cheek",
            position_name="center",
            orientation_name="vertical",
            study_type="near_field",
            verbose_logger=MagicMock(),
            progress_logger=MagicMock(),
            free_space=False,
            gui=None,
            study=None,
        )

        # Should not crash
        extractor.extract()

    def test_results_extractor_free_space(self, mock_config, mock_simulation):
        """Test extract() behavior for free space simulations."""
        from goliat.results_extractor import ResultsExtractor

        extractor = ResultsExtractor.from_params(
            config=mock_config,
            simulation=mock_simulation,
            phantom_name="thelonious",
            frequency_mhz=700,
            scenario_name="by_cheek",
            position_name="center",
            orientation_name="vertical",
            study_type="near_field",
            verbose_logger=MagicMock(),
            progress_logger=MagicMock(),
            free_space=True,  # Free space mode
            gui=None,
            study=None,
        )

        # Mock extractors
        with patch("goliat.results_extractor.PowerExtractor") as mock_power_extractor:
            mock_power_instance = MagicMock()
            mock_power_extractor.return_value = mock_power_instance

            extractor.extract()

            # Power extractor should be called
            assert mock_power_extractor.called

    def test_results_extractor_with_point_sensors(self, mock_config, mock_simulation):
        """Test extract() with point sensors configured."""
        from goliat.results_extractor import ResultsExtractor

        mock_config.__getitem__.side_effect = lambda key: 5 if "number_of_point_sensors" in key else None

        extractor = ResultsExtractor.from_params(
            config=mock_config,
            simulation=mock_simulation,
            phantom_name="thelonious",
            frequency_mhz=700,
            scenario_name="by_cheek",
            position_name="center",
            orientation_name="vertical",
            study_type="near_field",
            verbose_logger=MagicMock(),
            progress_logger=MagicMock(),
            free_space=False,
            gui=None,
            study=None,
        )

        # Mock extractors
        with patch("goliat.results_extractor.PowerExtractor") as mock_power_extractor, patch(
            "goliat.results_extractor.SarExtractor"
        ) as mock_sar_extractor, patch("goliat.results_extractor.SensorExtractor") as mock_sensor_extractor:
            mock_power_instance = MagicMock()
            mock_power_extractor.return_value = mock_power_instance

            mock_sar_instance = MagicMock()
            mock_sar_extractor.return_value = mock_sar_instance

            mock_sensor_instance = MagicMock()
            mock_sensor_extractor.return_value = mock_sensor_instance

            extractor.extract()

            # Sensor extractor should be called when sensors are configured
            assert mock_sensor_extractor.called

    def test_results_extractor_save_json_results(self, mock_config, mock_simulation, tmp_path):
        """Test _save_json_results method."""
        from goliat.results_extractor import ResultsExtractor

        mock_config.base_dir = str(tmp_path)

        extractor = ResultsExtractor.from_params(
            config=mock_config,
            simulation=mock_simulation,
            phantom_name="thelonious",
            frequency_mhz=700,
            scenario_name="by_cheek",
            position_name="center",
            orientation_name="vertical",
            study_type="near_field",
            verbose_logger=MagicMock(),
            progress_logger=MagicMock(),
            free_space=False,
            gui=None,
            study=None,
        )

        results_data = {
            "power": 1.0,
            "frequency": 700,
            "_temp_sar_df": None,  # Temporary data that should be excluded
        }

        # Mock Reporter to return a results directory
        with patch("goliat.results_extractor.Reporter") as mock_reporter_class:
            mock_reporter = MagicMock()
            mock_reporter._get_results_dir.return_value = str(tmp_path / "results")
            mock_reporter_class.return_value = mock_reporter

            extractor._save_json_results(results_data)

            # Check that JSON file was created
            json_file = tmp_path / "results" / "sar_results.json"
            assert json_file.exists()

            # Check that temporary data was excluded
            with open(json_file) as f:
                saved_data = json.load(f)
                assert "_temp_sar_df" not in saved_data
                assert "power" in saved_data
