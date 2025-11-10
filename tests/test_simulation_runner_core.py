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

    def test_simulation_runner_initialization(self, mock_config, mock_simulation, mock_profiler):
        """Test SimulationRunner initialization."""
        from goliat.simulation_runner import SimulationRunner

        runner = SimulationRunner(
            config=mock_config,
            project_path="/tmp/test.smash",
            simulation=mock_simulation,
            profiler=mock_profiler,
            verbose_logger=MagicMock(),
            progress_logger=MagicMock(),
            gui=None,
        )

        assert runner.config == mock_config
        assert runner.project_path == "/tmp/test.smash"
        assert runner.simulation == mock_simulation
        assert runner.profiler == mock_profiler

    def test_simulation_runner_no_simulation(self, mock_config, mock_profiler):
        """Test run() when simulation is None."""
        from goliat.simulation_runner import SimulationRunner

        runner = SimulationRunner(
            config=mock_config,
            project_path="/tmp/test.smash",
            simulation=None,
            profiler=mock_profiler,
            verbose_logger=MagicMock(),
            progress_logger=MagicMock(),
            gui=None,
        )

        # Should not crash
        runner.run()

    def test_simulation_runner_write_input_file(self, mock_config, mock_simulation, mock_profiler):
        """Test write input file functionality."""
        from goliat.simulation_runner import SimulationRunner

        mock_document = MagicMock()
        mock_document.SaveAs = MagicMock()

        # Patch s4l_v1.document at the module level before importing
        with patch("s4l_v1.document", mock_document):
            runner = SimulationRunner(
                config=mock_config,
                project_path="/tmp/test.smash",
                simulation=mock_simulation,
                profiler=mock_profiler,
                verbose_logger=MagicMock(),
                progress_logger=MagicMock(),
                gui=None,
            )

            # Mock only_write_input_file to return True
            mock_config.get_only_write_input_file.return_value = True

            runner.run()

            # Verify WriteInputFile was called
            assert mock_simulation.WriteInputFile.called
            # Verify SaveAs was called
            assert mock_document.SaveAs.called

    def test_simulation_runner_only_write_input_file_early_return(self, mock_config, mock_simulation, mock_profiler):
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
            gui=None,
        )

        runner.run()

        # Verify WriteInputFile was called
        assert mock_simulation.WriteInputFile.called

    def test_simulation_runner_manual_isolve(self, mock_config, mock_simulation, mock_profiler):
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
            gui=None,
        )

        # Mock the _run_isolve_manual method
        with patch.object(runner, "_run_isolve_manual") as mock_isolve:
            runner.run()
            # Should call manual isolve if configured
            assert mock_isolve.called

    def test_simulation_runner_with_gui(self, mock_config, mock_simulation, mock_profiler):
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
            gui=mock_gui,
        )

        assert runner.gui == mock_gui
