import contextlib
import json
import logging
import os
import sys
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..studies.base_study import BaseStudy


class StudyCancelledError(Exception):
    """Raised when the user cancels a study via the GUI."""

    pass


class Profiler:
    """Tracks execution times and estimates remaining time for a study.

    This is a lightweight profiler used for simpler scenarios. For the main
    study profiler with phase tracking and weighted progress, see goliat.profiler.Profiler.
    """

    def __init__(self, config_path: str, study_type: str = "sensitivity_analysis"):
        """Sets up the profiler with a config file.

        Args:
            config_path: Path to the JSON config file with timing data.
            study_type: Key in the config for this study's timing data.
        """
        self.config_path = config_path
        self.study_type = study_type
        self.profiling_config = self._load_config()

        self.start_time = time.monotonic()
        self.run_times = []
        self.total_runs = 0
        self.completed_runs = 0
        self.current_run_start_time = None

    def _load_config(self) -> dict:
        """Loads profiling config from JSON, returns defaults if missing."""
        try:
            with open(self.config_path, "r") as f:
                full_config = json.load(f)
            return full_config.get(self.study_type, {})
        except (FileNotFoundError, json.JSONDecodeError):
            return {"average_run_time": 60.0}

    def start_study(self, total_runs: int):
        """Resets counters for a new study."""
        self.total_runs = total_runs
        self.completed_runs = 0
        self.run_times = []
        self.start_time = time.monotonic()

    def start_run(self):
        """Marks the start of a run."""
        self.current_run_start_time = time.monotonic()

    def end_run(self):
        """Records the duration of the current run."""
        if self.current_run_start_time:
            duration = time.monotonic() - self.current_run_start_time
            self.run_times.append(duration)
            self.completed_runs += 1
            self.current_run_start_time = None

    def get_average_run_time(self) -> float:
        """Returns average run time from measurements, or falls back to config."""
        if self.run_times:
            return sum(self.run_times) / len(self.run_times)
        return self.profiling_config.get("average_run_time", 60.0)

    def get_time_remaining(self) -> float:
        """Estimates seconds remaining based on completed runs and average time."""
        if self.total_runs == 0:
            return 0

        avg_time = self.get_average_run_time()
        remaining_runs = self.total_runs - self.completed_runs
        return remaining_runs * avg_time

    def save_estimates(self):
        """Writes updated average run time to the config file."""
        if not self.run_times:
            return

        new_avg = self.get_average_run_time()

        try:
            with open(self.config_path, "r") as f:
                full_config = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            full_config = {}

        if self.study_type not in full_config:
            full_config[self.study_type] = {}

        full_config[self.study_type]["average_run_time"] = new_avg

        with open(self.config_path, "w") as f:
            json.dump(full_config, f, indent=4)

    def get_elapsed(self) -> float:
        """Returns elapsed seconds since study start."""
        return time.monotonic() - self.start_time

    @contextlib.contextmanager
    def subtask(self, name: str):
        """Context manager that times a subtask and logs the duration."""
        start_time = time.monotonic()
        try:
            yield
        finally:
            elapsed = time.monotonic() - start_time
            logging.getLogger("verbose").info(f"Subtask '{name}' took {elapsed:.2f}s", extra={"log_type": "verbose"})


def format_time(seconds: float) -> str:
    """Formats seconds into a readable string like '1h 23m 45s' or '2m 30s'."""
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    minutes, seconds = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m {seconds}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m {seconds}s"


def non_blocking_sleep(seconds: int):
    """Sleeps while processing Qt GUI events to keep the UI responsive."""
    from PySide6.QtCore import QCoreApplication, QEventLoop, QTime

    end_time = QTime.currentTime().addSecs(int(seconds))
    while QTime.currentTime() < end_time:  # type: ignore
        QCoreApplication.processEvents(QEventLoop.AllEvents, 50)  # type: ignore
        time.sleep(0.05)


@contextlib.contextmanager
def profile(study: "BaseStudy", phase_name: str):
    """Context manager that profiles a study phase and updates the GUI.

    Tracks timing, logs start/end messages, and syncs progress bars. Use this
    around major phases like setup, run, or extract.

    Args:
        study: The study instance to profile.
        phase_name: Name of the phase (e.g., 'setup', 'run', 'extract').
    """
    study.profiler.start_stage(phase_name)
    if study.gui:
        study.gui.update_profiler()
        study.gui.update_stage_progress(phase_name.capitalize(), 0, 1)
        study.start_stage_animation(phase_name, 100)

    study._log(f"--- Starting: {phase_name} ---", log_type="header")
    start_time = time.monotonic()
    try:
        yield
    finally:
        elapsed = time.monotonic() - start_time
        study._log(f"--- Finished: {phase_name} (took {elapsed:.2f}s) ---", log_type="header")

        study.profiler.end_stage()
        if study.gui:
            study.end_stage_animation()
            study.gui.update_profiler()


def ensure_s4l_running():
    """Starts Sim4Life if it's not already running."""
    from s4l_v1._api import application

    if application.get_app_safe() is None:
        logging.getLogger("verbose").info("Starting Sim4Life application...", extra={"log_type": "info"})
        application.run_application(disable_ui_plugins=True)
        logging.getLogger("verbose").info("Sim4Life application started.", extra={"log_type": "success"})


def open_project(project_path: str):
    """Opens a Sim4Life project file, or creates a new project if missing."""
    import s4l_v1.document

    if not os.path.exists(project_path):
        logging.getLogger("verbose").info(
            f"Project file not found at {project_path}, creating a new one.",
            extra={"log_type": "warning"},
        )
        s4l_v1.document.New()
    else:
        logging.getLogger("verbose").info(f"Opening project: {project_path}", extra={"log_type": "info"})
        s4l_v1.document.Open(project_path)


def delete_project_file(project_path: str):
    """Deletes a project file if it exists."""
    if os.path.exists(project_path):
        logging.getLogger("verbose").info(
            f"Deleting existing project file: {project_path}",
            extra={"log_type": "warning"},
        )
        os.remove(project_path)


@contextlib.contextmanager
def suppress_stdout_stderr():
    """Context manager that suppresses stdout and stderr output."""
    with open(os.devnull, "w") as fnull:
        saved_stdout, saved_stderr = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = fnull, fnull
        try:
            yield
        finally:
            sys.stdout, sys.stderr = saved_stdout, saved_stderr
