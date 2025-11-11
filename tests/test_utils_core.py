"""Tests for goliat.utils.core module."""

import json
import time


from goliat.utils.core import Profiler, format_time, suppress_stdout_stderr


class TestFormatTime:
    """Tests for format_time function."""

    def test_seconds_only(self):
        """Test formatting seconds (< 60)."""
        assert format_time(0) == "0s"
        assert format_time(30) == "30s"
        assert format_time(59) == "59s"

    def test_minutes_and_seconds(self):
        """Test formatting minutes and seconds."""
        assert format_time(60) == "1m 0s"
        assert format_time(61) == "1m 1s"
        assert format_time(90) == "1m 30s"
        assert format_time(3599) == "59m 59s"

    def test_hours_minutes_seconds(self):
        """Test formatting hours, minutes, and seconds."""
        assert format_time(3600) == "1h 0m 0s"
        assert format_time(3661) == "1h 1m 1s"
        assert format_time(3723) == "1h 2m 3s"
        assert format_time(7261) == "2h 1m 1s"


class TestProfiler:
    """Tests for the lightweight Profiler class."""

    def test_profiler_initialization(self, tmp_path):
        """Test profiler initialization with config file."""
        config_path = tmp_path / "profiling_config.json"
        config_data = {"sensitivity_analysis": {"average_run_time": 120.0}}
        with open(config_path, "w") as f:
            json.dump(config_data, f)

        profiler = Profiler(str(config_path), "sensitivity_analysis")
        assert profiler.config_path == str(config_path)
        assert profiler.study_type == "sensitivity_analysis"
        assert profiler.total_runs == 0
        assert profiler.completed_runs == 0

    def test_profiler_initialization_missing_config(self, tmp_path):
        """Test profiler initialization with missing config file."""
        config_path = tmp_path / "missing_config.json"
        profiler = Profiler(str(config_path), "sensitivity_analysis")
        assert profiler.profiling_config == {"average_run_time": 60.0}

    def test_profiler_start_study(self, tmp_path):
        """Test starting a study."""
        config_path = tmp_path / "profiling_config.json"
        profiler = Profiler(str(config_path), "sensitivity_analysis")
        profiler.start_study(total_runs=10)

        assert profiler.total_runs == 10
        assert profiler.completed_runs == 0
        assert profiler.run_times == []
        assert profiler.start_time > 0

    def test_profiler_start_run(self, tmp_path):
        """Test starting a run."""
        config_path = tmp_path / "profiling_config.json"
        profiler = Profiler(str(config_path), "sensitivity_analysis")
        profiler.start_run()

        assert profiler.current_run_start_time is not None
        assert profiler.current_run_start_time > 0

    def test_profiler_end_run(self, tmp_path):
        """Test ending a run."""
        config_path = tmp_path / "profiling_config.json"
        profiler = Profiler(str(config_path), "sensitivity_analysis")
        profiler.start_study(total_runs=5)
        profiler.start_run()

        # Sleep briefly to ensure measurable time difference
        time.sleep(0.05)
        profiler.end_run()

        assert profiler.completed_runs == 1
        assert len(profiler.run_times) == 1
        assert profiler.current_run_start_time is None
        assert profiler.run_times[0] >= 0

    def test_profiler_get_average_run_time_with_data(self, tmp_path):
        """Test getting average run time with recorded times."""
        config_path = tmp_path / "profiling_config.json"
        profiler = Profiler(str(config_path), "sensitivity_analysis")
        profiler.start_study(total_runs=3)
        profiler.start_run()
        time.sleep(0.01)
        profiler.end_run()
        profiler.start_run()
        time.sleep(0.02)
        profiler.end_run()

        avg_time = profiler.get_average_run_time()
        assert avg_time > 0
        assert avg_time < 1.0  # Should be very small

    def test_profiler_get_average_run_time_without_data(self, tmp_path):
        """Test getting average run time without recorded times."""
        config_path = tmp_path / "profiling_config.json"
        config_data = {"sensitivity_analysis": {"average_run_time": 180.0}}
        with open(config_path, "w") as f:
            json.dump(config_data, f)

        profiler = Profiler(str(config_path), "sensitivity_analysis")
        assert profiler.get_average_run_time() == 180.0

    def test_profiler_get_time_remaining(self, tmp_path):
        """Test getting time remaining estimate."""
        config_path = tmp_path / "profiling_config.json"
        # Create config with known average time
        config_data = {"sensitivity_analysis": {"average_run_time": 10.0}}
        with open(config_path, "w") as f:
            json.dump(config_data, f)

        profiler = Profiler(str(config_path), "sensitivity_analysis")
        profiler.start_study(total_runs=5)
        profiler.start_run()
        time.sleep(0.01)
        profiler.end_run()

        remaining = profiler.get_time_remaining()
        assert remaining >= 0

    def test_profiler_get_time_remaining_zero_runs(self, tmp_path):
        """Test getting time remaining with zero total runs."""
        config_path = tmp_path / "profiling_config.json"
        profiler = Profiler(str(config_path), "sensitivity_analysis")
        profiler.start_study(total_runs=0)

        assert profiler.get_time_remaining() == 0

    def test_profiler_get_elapsed(self, tmp_path):
        """Test getting elapsed time."""
        config_path = tmp_path / "profiling_config.json"
        profiler = Profiler(str(config_path), "sensitivity_analysis")
        profiler.start_study(total_runs=1)

        time.sleep(0.05)
        elapsed = profiler.get_elapsed()
        assert elapsed >= 0
        assert elapsed < 1.0

    def test_profiler_save_estimates(self, tmp_path):
        """Test saving estimates to config file."""
        config_path = tmp_path / "profiling_config.json"
        config_data = {"sensitivity_analysis": {}}
        with open(config_path, "w") as f:
            json.dump(config_data, f)

        profiler = Profiler(str(config_path), "sensitivity_analysis")
        profiler.start_study(total_runs=2)
        profiler.start_run()
        time.sleep(0.1)  # Increased sleep time to ensure measurable time difference
        profiler.end_run()

        profiler.save_estimates()

        # Verify the config was updated
        with open(config_path, "r") as f:
            saved_config = json.load(f)
        assert "sensitivity_analysis" in saved_config
        assert "average_run_time" in saved_config["sensitivity_analysis"]
        assert saved_config["sensitivity_analysis"]["average_run_time"] > 0

    def test_profiler_subtask_context_manager(self, tmp_path):
        """Test profiler subtask context manager."""
        config_path = tmp_path / "profiling_config.json"
        profiler = Profiler(str(config_path), "sensitivity_analysis")

        # Subtask context manager exists and doesn't raise
        with profiler.subtask("test_task"):
            time.sleep(0.01)

        # Note: utils.core.Profiler's subtask just logs, doesn't track subtask_times
        # This test just verifies the context manager works without error
        # The subtask method exists and executes without raising exceptions


class TestSuppressStdoutStderr:
    """Tests for suppress_stdout_stderr context manager."""

    def test_suppresses_output(self):
        """Test that stdout and stderr are suppressed."""
        with suppress_stdout_stderr():
            print("This should not appear")
            import sys

            sys.stderr.write("This should not appear either")

    def test_restores_output(self):
        """Test that stdout and stderr are restored after context."""
        import sys

        original_stdout = sys.stdout
        original_stderr = sys.stderr

        with suppress_stdout_stderr():
            pass

        assert sys.stdout == original_stdout
        assert sys.stderr == original_stderr
