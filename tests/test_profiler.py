import pytest

from src.profiler import Profiler


@pytest.fixture
def profiler_instance():
    execution_control = {"do_setup": True, "do_run": True, "do_extract": True}
    profiling_config = {"avg_setup_time": 10, "avg_run_time": 20, "avg_extract_time": 5}
    return Profiler(
        execution_control, profiling_config, "near_field", "dummy_path.json"
    )


@pytest.mark.skip_on_ci
def test_profiler_initialization(profiler_instance):
    assert profiler_instance.study_type == "near_field"
    assert "setup" in profiler_instance.phase_weights
    assert "run" in profiler_instance.phase_weights
    assert "extract" in profiler_instance.phase_weights


@pytest.mark.skip_on_ci
def test_get_subtask_estimate(profiler_instance):
    profiler_instance.profiling_config["avg_my_task"] = 15.0
    assert profiler_instance.get_subtask_estimate("my_task") == 15.0
    assert profiler_instance.get_subtask_estimate("non_existent_task") == 1.0


@pytest.mark.skip_on_ci
def test_time_remaining(profiler_instance):
    profiler_instance.start_stage("setup")
    remaining = profiler_instance.get_time_remaining(current_stage_progress=0.5)
    # (10 * 0.5) + 20 + 5 = 30
    assert remaining == 30.0

    profiler_instance.start_stage("run")
    remaining = profiler_instance.get_time_remaining(current_stage_progress=0.25)
    # (20 * 0.75) + 5 = 20
    assert remaining == 20.0
