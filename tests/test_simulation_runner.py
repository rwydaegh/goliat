from unittest.mock import MagicMock, patch

import pytest

# Mock s4l_v1
mocks = {
    "s4l_v1": MagicMock(),
    "s4l_v1.document": MagicMock(),
}

with patch.dict("sys.modules", mocks):
    from goliat.simulation_runner import SimulationRunner


@pytest.fixture
def mock_config():
    config = MagicMock()
    config.get_server.return_value = "localhost"
    config.__getitem__.side_effect = lambda key: {
        "manual_isolve": False,
        "execution_control.only_write_input_file": False,
    }.get(key)
    config.get_manual_isolve = lambda: False
    config.get_only_write_input_file.return_value = False
    return config


@pytest.fixture
def mock_study():
    study = MagicMock()
    study.subtask.return_value.__enter__.return_value = None
    study.subtask.return_value.__exit__.return_value = None, None, None
    return study


@pytest.fixture
def mock_project_manager():
    """Create a mock project manager."""
    pm = MagicMock()
    pm.project_path = "/tmp/project.smash"
    pm.save = MagicMock()
    return pm


def test_simulation_runner_initialization(mock_config, mock_study, mock_project_manager):
    runner = SimulationRunner(
        config=mock_config,
        project_path="/tmp/project.smash",
        simulation=MagicMock(),
        profiler=MagicMock(),
        verbose_logger=MagicMock(),
        progress_logger=MagicMock(),
        project_manager=mock_project_manager,
        gui=None,
    )
    assert runner is not None


def test_run_no_simulation(mock_config, mock_study, mock_project_manager):
    runner = SimulationRunner(
        config=mock_config,
        project_path="/tmp/project.smash",
        simulation=None,
        profiler=MagicMock(),
        verbose_logger=MagicMock(),
        progress_logger=MagicMock(),
        project_manager=mock_project_manager,
        gui=None,
    )
    # This should run without error
    runner.run()
