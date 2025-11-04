"""Additional tests for goliat.profiler module."""

import json
import time

import pytest

from goliat.profiler import Profiler


@pytest.fixture
def tmp_profiling_config(tmp_path):
    """Create a temporary profiling config file."""
    config_path = tmp_path / "profiling_config.json"
    config_data = {
        "near_field": {
            "avg_setup_time": 10.0,
            "avg_run_time": 60.0,
            "avg_extract_time": 5.0,
        },
        "far_field": {
            "avg_setup_time": 15.0,
            "avg_run_time": 90.0,
            "avg_extract_time": 8.0,
        },
    }
    with open(config_path, "w") as f:
        json.dump(config_data, f)
    return config_path


class TestProfilerPhaseWeights:
    """Tests for phase weight calculation."""

    def test_phase_weights_all_enabled(self, tmp_profiling_config):
        """Test phase weights when all phases are enabled."""
        execution_control = {"do_setup": True, "do_run": True, "do_extract": True}
        profiling_config = {"avg_setup_time": 10, "avg_run_time": 60, "avg_extract_time": 5}
        profiler = Profiler(execution_control, profiling_config, "near_field", str(tmp_profiling_config))

        weights = profiler.phase_weights
        assert "setup" in weights
        assert "run" in weights
        assert "extract" in weights
        # Weights should sum to approximately 1.0
        total_weight = sum(weights.values())
        assert abs(total_weight - 1.0) < 0.01

    def test_phase_weights_partial_enabled(self, tmp_profiling_config):
        """Test phase weights when only some phases are enabled."""
        execution_control = {"do_setup": True, "do_run": False, "do_extract": True}
        profiling_config = {"avg_setup_time": 10, "avg_extract_time": 5}
        profiler = Profiler(execution_control, profiling_config, "near_field", str(tmp_profiling_config))

        weights = profiler.phase_weights
        assert "setup" in weights
        assert "run" not in weights
        assert "extract" in weights
        total_weight = sum(weights.values())
        assert abs(total_weight - 1.0) < 0.01

    def test_phase_weights_no_phases_enabled(self, tmp_profiling_config):
        """Test phase weights when no phases are enabled."""
        execution_control = {"do_setup": False, "do_run": False, "do_extract": False}
        profiling_config = {}
        profiler = Profiler(execution_control, profiling_config, "near_field", str(tmp_profiling_config))

        assert profiler.phase_weights == {}


class TestProfilerSimulationTracking:
    """Tests for simulation tracking."""

    def test_set_total_simulations(self, tmp_profiling_config):
        """Test setting total simulations."""
        execution_control = {"do_setup": True, "do_run": True, "do_extract": True}
        profiling_config = {"avg_setup_time": 10, "avg_run_time": 60, "avg_extract_time": 5}
        profiler = Profiler(execution_control, profiling_config, "near_field", str(tmp_profiling_config))

        profiler.set_total_simulations(100)
        assert profiler.total_simulations == 100

    def test_simulation_completed(self, tmp_profiling_config):
        """Test marking simulation as completed."""
        execution_control = {"do_setup": True, "do_run": True, "do_extract": True}
        profiling_config = {"avg_setup_time": 10, "avg_run_time": 60, "avg_extract_time": 5}
        profiler = Profiler(execution_control, profiling_config, "near_field", str(tmp_profiling_config))

        profiler.set_total_simulations(10)
        assert profiler.completed_simulations == 0

        profiler.simulation_completed()
        assert profiler.completed_simulations == 1

        profiler.simulation_completed()
        assert profiler.completed_simulations == 2


class TestProfilerStageTracking:
    """Tests for stage tracking."""

    def test_start_stage(self, tmp_profiling_config):
        """Test starting a stage."""
        execution_control = {"do_setup": True, "do_run": True, "do_extract": True}
        profiling_config = {"avg_setup_time": 10, "avg_run_time": 60, "avg_extract_time": 5}
        profiler = Profiler(execution_control, profiling_config, "near_field", str(tmp_profiling_config))

        profiler.start_stage("setup")
        assert profiler.current_phase == "setup"
        assert profiler.phase_start_time is not None

    def test_end_stage(self, tmp_profiling_config):
        """Test ending a stage."""
        execution_control = {"do_setup": True, "do_run": True, "do_extract": True}
        profiling_config = {"avg_setup_time": 10, "avg_run_time": 60, "avg_extract_time": 5}
        profiler = Profiler(execution_control, profiling_config, "near_field", str(tmp_profiling_config))

        profiler.start_stage("setup")
        time.sleep(0.01)
        profiler.end_stage()

        assert profiler.current_phase is None
        # Profiling config should be updated with actual time
        assert "avg_setup_time" in profiler.profiling_config

    def test_start_stage_with_total_stages(self, tmp_profiling_config):
        """Test starting a stage with total stages parameter."""
        execution_control = {"do_setup": True, "do_run": True, "do_extract": True}
        profiling_config = {"avg_setup_time": 10, "avg_run_time": 60, "avg_extract_time": 5}
        profiler = Profiler(execution_control, profiling_config, "near_field", str(tmp_profiling_config))

        profiler.start_stage("setup", total_stages=5)
        assert profiler.current_phase == "setup"
        assert profiler.total_stages_in_phase == 5


class TestProfilerSubtaskTracking:
    """Tests for subtask tracking."""

    def test_subtask_context_manager(self, tmp_profiling_config):
        """Test subtask context manager."""
        execution_control = {"do_setup": True, "do_run": True, "do_extract": True}
        profiling_config = {"avg_setup_time": 10, "avg_run_time": 60, "avg_extract_time": 5}
        profiler = Profiler(execution_control, profiling_config, "near_field", str(tmp_profiling_config))

        with profiler.subtask("test_subtask"):
            time.sleep(0.05)

        assert "test_subtask" in profiler.subtask_times
        assert len(profiler.subtask_times["test_subtask"]) == 1
        assert profiler.subtask_times["test_subtask"][0] >= 0

    def test_subtask_nested(self, tmp_profiling_config):
        """Test nested subtasks."""
        execution_control = {"do_setup": True, "do_run": True, "do_extract": True}
        profiling_config = {"avg_setup_time": 10, "avg_run_time": 60, "avg_extract_time": 5}
        profiler = Profiler(execution_control, profiling_config, "near_field", str(tmp_profiling_config))

        with profiler.subtask("outer_task"):
            time.sleep(0.005)
            with profiler.subtask("inner_task"):
                time.sleep(0.005)

        assert "outer_task" in profiler.subtask_times
        assert "inner_task" in profiler.subtask_times
        assert len(profiler.subtask_times["outer_task"]) == 1
        assert len(profiler.subtask_times["inner_task"]) == 1


class TestProfilerWeightedProgress:
    """Tests for weighted progress calculation."""

    def test_get_weighted_progress_no_simulations(self, tmp_profiling_config):
        """Test weighted progress with zero simulations."""
        execution_control = {"do_setup": True, "do_run": True, "do_extract": True}
        profiling_config = {"avg_setup_time": 10, "avg_run_time": 60, "avg_extract_time": 5}
        profiler = Profiler(execution_control, profiling_config, "near_field", str(tmp_profiling_config))

        progress = profiler.get_weighted_progress("setup", 0.5)
        assert progress == 0.0

    def test_get_weighted_progress_first_simulation(self, tmp_profiling_config):
        """Test weighted progress for first simulation."""
        execution_control = {"do_setup": True, "do_run": True, "do_extract": True}
        profiling_config = {"avg_setup_time": 10, "avg_run_time": 60, "avg_extract_time": 5}
        profiler = Profiler(execution_control, profiling_config, "near_field", str(tmp_profiling_config))

        profiler.set_total_simulations(10)
        progress = profiler.get_weighted_progress("setup", 0.5)

        assert 0 <= progress <= 100
        assert progress > 0  # Should have some progress

    def test_get_weighted_progress_completed_simulations(self, tmp_profiling_config):
        """Test weighted progress with completed simulations."""
        execution_control = {"do_setup": True, "do_run": True, "do_extract": True}
        profiling_config = {"avg_setup_time": 10, "avg_run_time": 60, "avg_extract_time": 5}
        profiler = Profiler(execution_control, profiling_config, "near_field", str(tmp_profiling_config))

        profiler.set_total_simulations(10)
        profiler.completed_simulations = 5
        progress = profiler.get_weighted_progress("setup", 0.0)

        assert progress >= 50  # Should be at least 50% complete


class TestProfilerTimeRemaining:
    """Tests for time remaining estimation."""

    def test_get_time_remaining_no_current_phase(self, tmp_profiling_config):
        """Test time remaining when no current phase."""
        execution_control = {"do_setup": True, "do_run": True, "do_extract": True}
        profiling_config = {"avg_setup_time": 10, "avg_run_time": 60, "avg_extract_time": 5}
        profiler = Profiler(execution_control, profiling_config, "near_field", str(tmp_profiling_config))

        remaining = profiler.get_time_remaining()
        assert remaining == 0.0

    def test_get_time_remaining_with_current_phase(self, tmp_profiling_config):
        """Test time remaining with current phase."""
        execution_control = {"do_setup": True, "do_run": True, "do_extract": True}
        profiling_config = {"avg_setup_time": 10, "avg_run_time": 60, "avg_extract_time": 5}
        profiler = Profiler(execution_control, profiling_config, "near_field", str(tmp_profiling_config))

        profiler.set_total_simulations(10)
        profiler.start_stage("setup")
        remaining = profiler.get_time_remaining(current_stage_progress=0.5)

        assert remaining >= 0


class TestProfilerSaveEstimates:
    """Tests for saving estimates."""

    def test_update_and_save_estimates(self, tmp_profiling_config):
        """Test updating and saving estimates."""
        execution_control = {"do_setup": True, "do_run": True, "do_extract": True}
        profiling_config = {"avg_setup_time": 10, "avg_run_time": 60, "avg_extract_time": 5}
        profiler = Profiler(execution_control, profiling_config, "near_field", str(tmp_profiling_config))

        profiler.start_stage("setup")
        time.sleep(0.01)
        profiler.end_stage()

        profiler.update_and_save_estimates()

        # Verify config was saved
        with open(tmp_profiling_config, "r") as f:
            saved_config = json.load(f)
        assert "near_field" in saved_config
        assert "avg_setup_time" in saved_config["near_field"]

    def test_save_estimates(self, tmp_profiling_config):
        """Test save_estimates method."""
        execution_control = {"do_setup": True, "do_run": True, "do_extract": True}
        profiling_config = {"avg_setup_time": 10, "avg_run_time": 60, "avg_extract_time": 5}
        profiler = Profiler(execution_control, profiling_config, "near_field", str(tmp_profiling_config))

        profiler.start_stage("setup")
        time.sleep(0.01)
        profiler.end_stage()

        profiler.save_estimates()

        # Verify config was saved
        with open(tmp_profiling_config, "r") as f:
            saved_config = json.load(f)
        assert "near_field" in saved_config


class TestProfilerProjectTracking:
    """Tests for project tracking."""

    def test_set_project_scope(self, tmp_profiling_config):
        """Test setting project scope."""
        execution_control = {"do_setup": True, "do_run": True, "do_extract": True}
        profiling_config = {"avg_setup_time": 10, "avg_run_time": 60, "avg_extract_time": 5}
        profiler = Profiler(execution_control, profiling_config, "near_field", str(tmp_profiling_config))

        profiler.set_project_scope(5)
        assert profiler.total_projects == 5

    def test_set_current_project(self, tmp_profiling_config):
        """Test setting current project."""
        execution_control = {"do_setup": True, "do_run": True, "do_extract": True}
        profiling_config = {"avg_setup_time": 10, "avg_run_time": 60, "avg_extract_time": 5}
        profiler = Profiler(execution_control, profiling_config, "near_field", str(tmp_profiling_config))

        profiler.set_current_project(2)
        assert profiler.current_project == 2

    def test_complete_run_phase(self, tmp_profiling_config):
        """Test completing run phase."""
        execution_control = {"do_setup": True, "do_run": True, "do_extract": True}
        profiling_config = {"avg_setup_time": 10, "avg_run_time": 60, "avg_extract_time": 5}
        profiler = Profiler(execution_control, profiling_config, "near_field", str(tmp_profiling_config))

        profiler.subtask_times["run_simulation_total"] = [30.0, 35.0, 40.0]
        profiler.complete_run_phase()

        assert profiler.run_phase_total_duration == 105.0
