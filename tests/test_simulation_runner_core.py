"""Tests for goliat.simulation_runner module core functionality."""

from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.skip_on_ci
class TestSimulationRunner:
    """Tests for SimulationRunner class."""

    @pytest.fixture
    def mock_simulation(self):
        """Create a mock simulation object."""
        mock_sim = MagicMock()
        mock_sim.Name = "TestSimulation"
        mock_sim.WriteInputFile = MagicMock()
        return mock_sim

    @pytest.fixture
    def mock_config(self):
        """Create a mock config object."""
        config = MagicMock()
        config.__getitem__.side_effect = lambda key: {
            "solver_settings": {"server": "localhost"},
            "execution_control.only_write_input_file": False,
            "manual_isolve": False,
        }.get(key)
        config.get_only_write_input_file.return_value = False
        config.get_manual_isolve = lambda: False
        return config

    @pytest.fixture
    def mock_profiler(self):
        """Create a mock profiler."""
        profiler = MagicMock()
        profiler.subtask = MagicMock()
        profiler.subtask.__enter__ = MagicMock(return_value=None)
        profiler.subtask.__exit__ = MagicMock(return_value=None)
        profiler.subtask_times = {"run_write_input_file": [1.5]}
        return profiler

    @pytest.fixture
    def mock_project_manager(self):
        """Create a mock project manager."""
        pm = MagicMock()
        pm.project_path = "/tmp/test.smash"
        pm.save = MagicMock()
        return pm

    def test_simulation_runner_initialization(self, mock_config, mock_simulation, mock_profiler, mock_project_manager):
        """Test SimulationRunner initialization."""
        from goliat.simulation_runner import SimulationRunner

        runner = SimulationRunner(
            config=mock_config,
            project_path="/tmp/test.smash",
            simulation=mock_simulation,
            profiler=mock_profiler,
            verbose_logger=MagicMock(),
            progress_logger=MagicMock(),
            project_manager=mock_project_manager,
            gui=None,
        )

        assert runner.config == mock_config
        assert runner.project_path == "/tmp/test.smash"
        assert runner.simulation == mock_simulation
        assert runner.profiler == mock_profiler

    def test_simulation_runner_no_simulation(self, mock_config, mock_profiler, mock_project_manager):
        """Test run() when simulation is None."""
        from goliat.simulation_runner import SimulationRunner

        runner = SimulationRunner(
            config=mock_config,
            project_path="/tmp/test.smash",
            simulation=None,
            profiler=mock_profiler,
            verbose_logger=MagicMock(),
            progress_logger=MagicMock(),
            project_manager=mock_project_manager,
            gui=None,
        )

        # Should not crash
        runner.run()

    def test_simulation_runner_write_input_file(self, mock_config, mock_simulation, mock_profiler, mock_project_manager):
        """Test write input file functionality."""
        from goliat.simulation_runner import SimulationRunner

        runner = SimulationRunner(
            config=mock_config,
            project_path="/tmp/test.smash",
            simulation=mock_simulation,
            profiler=mock_profiler,
            verbose_logger=MagicMock(),
            progress_logger=MagicMock(),
            project_manager=mock_project_manager,
            gui=None,
        )

        # Mock only_write_input_file to return True
        mock_config.get_only_write_input_file.return_value = True

        runner.run()

        # Verify WriteInputFile was called
        assert mock_simulation.WriteInputFile.called
        # Verify project_manager.save() was called (replaces document.SaveAs)
        assert mock_project_manager.save.called

    def test_simulation_runner_only_write_input_file_early_return(self, mock_config, mock_simulation, mock_profiler, mock_project_manager):
        """Test early return when only_write_input_file is True."""
        from goliat.simulation_runner import SimulationRunner

        mock_config.get_only_write_input_file.return_value = True

        runner = SimulationRunner(
            config=mock_config,
            project_path="/tmp/test.smash",
            simulation=mock_simulation,
            profiler=mock_profiler,
            verbose_logger=MagicMock(),
            progress_logger=MagicMock(),
            project_manager=mock_project_manager,
            gui=None,
        )

        runner.run()

        # Verify WriteInputFile was called
        assert mock_simulation.WriteInputFile.called

    def test_simulation_runner_manual_isolve(self, mock_config, mock_simulation, mock_profiler, mock_project_manager):
        """Test manual iSolve execution path."""
        from goliat.simulation_runner import SimulationRunner

        mock_config.__getitem__.side_effect = lambda key: {
            "solver_settings": {"server": "localhost"},
            "execution_control.only_write_input_file": False,
            "manual_isolve": True,
        }.get(key)
        mock_config.get_manual_isolve = lambda: True
        mock_config.get_only_write_input_file.return_value = False

        runner = SimulationRunner(
            config=mock_config,
            project_path="/tmp/test.smash",
            simulation=mock_simulation,
            profiler=mock_profiler,
            verbose_logger=MagicMock(),
            progress_logger=MagicMock(),
            project_manager=mock_project_manager,
            gui=None,
        )

        # Create a mock strategy and patch _create_execution_strategy to return it
        mock_strategy = MagicMock()
        mock_strategy.run = MagicMock()

        with patch.object(runner, "_create_execution_strategy", return_value=mock_strategy):
            runner.run()
            # Should create ISolveManualStrategy and call its run method if configured
            assert mock_strategy.run.called

    def test_simulation_runner_with_gui(self, mock_config, mock_simulation, mock_profiler, mock_project_manager):
        """Test SimulationRunner with GUI."""
        from goliat.simulation_runner import SimulationRunner

        mock_gui = MagicMock()
        mock_gui.is_stopped.return_value = False

        runner = SimulationRunner(
            config=mock_config,
            project_path="/tmp/test.smash",
            simulation=mock_simulation,
            profiler=mock_profiler,
            verbose_logger=MagicMock(),
            progress_logger=MagicMock(),
            project_manager=mock_project_manager,
            gui=mock_gui,
        )

        assert runner.gui == mock_gui
