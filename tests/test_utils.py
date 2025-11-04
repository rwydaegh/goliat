import pytest

from goliat.utils import StudyCancelledError, format_time


def test_format_time():
    assert format_time(59) == "59s"
    assert format_time(60) == "1m 0s"
    assert format_time(61) == "1m 1s"
    assert format_time(3600) == "1h 0m 0s"
    assert format_time(3661) == "1h 1m 1s"


def test_study_cancelled_error():
    with pytest.raises(StudyCancelledError):
        raise StudyCancelledError("Test")


# Not testing profile, profile_subtask, ensure_s4l_running, open_project,
# delete_project_file, suppress_stdout_stderr as they require more complex
# mocking or interaction with Sim4Life, which is out of scope for these simple tests.
# The simple Profiler in utils.py is also not tested here as the main profiler
# in profiler.py is already covered.
