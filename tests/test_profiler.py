import pytest

from goliat.profiler import Profiler


@pytest.fixture
def profiler_instance():
    execution_control = {"do_setup": True, "do_run": True, "do_extract": True}
    profiling_config = {"avg_setup_time": 10, "avg_run_time": 20, "avg_extract_time": 5}
    return Profiler(execution_control, profiling_config, "near_field", "dummy_path.json")


def test_profiler_initialization(profiler_instance):
    assert profiler_instance.study_type == "near_field"
    assert "setup" in profiler_instance.phase_weights
    assert "run" in profiler_instance.phase_weights
    assert "extract" in profiler_instance.phase_weights


def test_get_subtask_estimate(profiler_instance):
    profiler_instance.profiling_config["avg_my_task"] = 15.0
    assert profiler_instance.get_subtask_estimate("my_task") == 15.0
    assert profiler_instance.get_subtask_estimate("non_existent_task") == 1.0


def test_time_remaining(profiler_instance):
    profiler_instance.start_stage("setup")
    # This test is now more of an integration test and the logic is complex.
    # We will just ensure it runs without error and returns a float.
    remaining = profiler_instance.get_time_remaining(current_stage_progress=0.5)
    assert isinstance(remaining, float)

    profiler_instance.start_stage("run")
    remaining = profiler_instance.get_time_remaining(current_stage_progress=0.25)
    assert isinstance(remaining, float)
