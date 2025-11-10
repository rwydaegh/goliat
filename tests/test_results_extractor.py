from unittest.mock import MagicMock, patch

import pytest

# Mock s4l_v1 and other heavy dependencies
mocks = {
    "s4l_v1": MagicMock(),
    "s4l_v1.analysis": MagicMock(),
    "s4l_v1.document": MagicMock(),
    "s4l_v1.units": MagicMock(),
    "matplotlib": MagicMock(),
    "matplotlib.pyplot": MagicMock(),
    "pandas": MagicMock(),
    "numpy": MagicMock(),
}

with patch.dict("sys.modules", mocks):
    from goliat.results_extractor import ResultsExtractor


@pytest.fixture
def mock_config():
    config = MagicMock()
    config.__getitem__.side_effect = lambda key: 0 if "number_of_point_sensors" in key else None
    config.base_dir = "/tmp"
    return config


@pytest.fixture
def mock_study():
    study = MagicMock()
    # Mock the subtask context manager
    study.subtask.return_value.__enter__.return_value = None
    study.subtask.return_value.__exit__.return_value = None, None, None
    return study


def test_results_extractor_initialization(mock_config, mock_study):
    # This test only checks if the extractor can be initialized without errors.
    try:
        extractor = ResultsExtractor.from_params(
            config=mock_config,
            simulation=MagicMock(),
            phantom_name="test_phantom",
            frequency_mhz=700,
            scenario_name="test_scenario",
            position_name="test_position",
            orientation_name="test_orientation",
            study_type="near_field",
            verbose_logger=MagicMock(),
            progress_logger=MagicMock(),
            gui=None,
            study=mock_study,
        )
        assert extractor is not None
    except Exception as e:
        pytest.fail(f"ResultsExtractor initialization failed: {e}")


def test_extract_no_simulation(mock_config, mock_study):
    # Test the case where the simulation object is None
    extractor = ResultsExtractor.from_params(
        config=mock_config,
        simulation=None,
        phantom_name="test_phantom",
        frequency_mhz=700,
        scenario_name="test_scenario",
        position_name="test_position",
        orientation_name="test_orientation",
        study_type="near_field",
        verbose_logger=MagicMock(),
        progress_logger=MagicMock(),
        gui=None,
        study=mock_study,
    )
    # Should run without raising an exception
    extractor.extract()
