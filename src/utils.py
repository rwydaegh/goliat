import os
import sys
import contextlib
import time
import json
from datetime import timedelta
import subprocess
import pkg_resources
from collections import defaultdict
import logging
import io


class StudyCancelledError(Exception):
    """Custom exception to indicate that the study was cancelled by the user."""
    pass

class Profiler:
    """
    A simple profiler to track execution time and estimate remaining time for a series of runs.
    """
    def __init__(self, config_path, study_type='sensitivity_analysis'):
        self.config_path = config_path
        self.study_type = study_type
        self.profiling_config = self._load_config()
        
        self.start_time = time.monotonic()
        self.run_times = []
        self.total_runs = 0
        self.completed_runs = 0
        self.current_run_start_time = None

    def _load_config(self):
        """Loads the profiling configuration for the specific study type."""
        try:
            with open(self.config_path, 'r') as f:
                full_config = json.load(f)
            return full_config.get(self.study_type, {})
        except (FileNotFoundError, json.JSONDecodeError):
            return {"average_run_time": 60.0} # Default value

    def start_study(self, total_runs):
        """Starts a new study, resetting counters."""
        self.total_runs = total_runs
        self.completed_runs = 0
        self.run_times = []
        self.start_time = time.monotonic()

    def start_run(self):
        """Marks the beginning of a single run."""
        self.current_run_start_time = time.monotonic()

    def end_run(self):
        """Marks the end of a single run and records its duration."""
        if self.current_run_start_time:
            duration = time.monotonic() - self.current_run_start_time
            self.run_times.append(duration)
            self.completed_runs += 1
            self.current_run_start_time = None

    def get_average_run_time(self):
        """
        Gets the average run time, prioritizing measured times over historical estimates.
        """
        if self.run_times:
            return sum(self.run_times) / len(self.run_times)
        return self.profiling_config.get("average_run_time", 60.0)

    def get_time_remaining(self):
        """Estimates the time remaining for the entire study."""
        if self.total_runs == 0:
            return 0
        
        avg_time = self.get_average_run_time()
        remaining_runs = self.total_runs - self.completed_runs
        return remaining_runs * avg_time

    def save_estimates(self):
        """Saves the new average run time to the configuration file."""
        if not self.run_times:
            return # Nothing to save

        new_avg = self.get_average_run_time()
        
        try:
            with open(self.config_path, 'r') as f:
                full_config = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            full_config = {}
            
        if self.study_type not in full_config:
            full_config[self.study_type] = {}
            
        full_config[self.study_type]['average_run_time'] = new_avg
        
        with open(self.config_path, 'w') as f:
            json.dump(full_config, f, indent=4)

    def get_elapsed(self):
        return time.monotonic() - self.start_time

    @contextlib.contextmanager
    def subtask(self, name):
        """A context manager to time a subtask."""
        # This is a simplified version for the simple profiler, it does not need a stack.
        start_time = time.monotonic()
        try:
            yield
        finally:
            elapsed = time.monotonic() - start_time
            # We can just log the subtask time for now.
            logging.getLogger('verbose').info(f"Subtask '{name}' took {elapsed:.2f}s", extra={'log_type': 'verbose'})

def format_time(seconds):
    """Formats seconds into a human-readable string (e.g., 1m 23s)."""
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    minutes, seconds = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m {seconds}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m {seconds}s"

def non_blocking_sleep(seconds):
    """
    A non-blocking sleep that processes GUI events.
    """
    from PySide6.QtCore import QCoreApplication, QTime, QEventLoop

    end_time = QTime.currentTime().addSecs(int(seconds))
    while QTime.currentTime() < end_time:
        QCoreApplication.processEvents(QEventLoop.AllEvents, 50)
        time.sleep(0.05)

@contextlib.contextmanager
def profile(study, phase_name):
    """
    A context manager to profile a block of code (a 'phase').
    """
    # The 'run' phase is further divided into stages (simulations), so we don't start a master stage for it.
    if phase_name != 'run':
        study.profiler.start_stage(phase_name)
        # Send the updated profiler to the GUI immediately so it knows the phase has started.
        if study.gui:
            study.gui.update_profiler()

    study._log(f"--- Starting: {phase_name} ---", log_type='header')
    start_time = time.monotonic()
    try:
        yield
    finally:
        elapsed = time.monotonic() - start_time
        study._log(f"--- Finished: {phase_name} (took {elapsed:.2f}s) ---", log_type='header')
        
        # For 'setup' and 'extract', ending the stage means ending the phase.
        # For 'run', the phase is completed manually after the simulation loop.
        if phase_name != 'run':
            study.profiler.end_stage()
        else:
            # This ensures the 'run' phase duration is recorded correctly
            study.profiler.complete_run_phase()
        
        if study.gui:
            study.gui.update_profiler()

@contextlib.contextmanager
def profile_subtask(study, task_name, instance_to_profile=None):
    """
    A comprehensive context manager for a 'subtask'. It handles:
    - High-level timing via study.profiler.
    - GUI stage animation.
    - Optional, detailed line-by-line profiling if configured.
    """
    study.start_stage_animation(task_name, 1)
    study.profiler.subtask_stack.append({'name': task_name, 'start_time': time.monotonic()})
    
    lp = None
    wrapper = None

    # Check if line profiling is enabled for this specific subtask
    line_profiling_config = study.config.get_line_profiling_config()
    if (instance_to_profile and
        line_profiling_config.get("enabled", False) and
        task_name in line_profiling_config.get("subtasks", {})):
        
        study._log(f"  - Activating line profiler for subtask: {task_name}", level='verbose', log_type='verbose')
        lp, wrapper = study._setup_line_profiler(task_name, instance_to_profile)

    try:
        # If line profiler is active, yield its wrapper. Otherwise, yield a dummy function.
        if lp and wrapper:
            yield wrapper
        else:
            yield lambda func: func
            
    finally:
        subtask = study.profiler.subtask_stack.pop()
        elapsed = time.monotonic() - subtask['start_time']
        study.profiler.subtask_times[subtask['name']].append(elapsed)
        study._log(f"    - Subtask '{task_name}' done in {elapsed:.2f}s", level='progress', log_type='progress')

        # If the line profiler was active, print its stats
        if lp:
            study._log(f"    - Line profiler stats for '{task_name}':", level='verbose', log_type='verbose')
            s = io.StringIO()
            lp.print_stats(stream=s)
            study.verbose_logger.info(s.getvalue())
            
        study.end_stage_animation()


def ensure_s4l_running():
    """
    Ensures that the Sim4Life application is running.
    """
    from s4l_v1._api import application
    
    if application.get_app_safe() is None:
        logging.getLogger('verbose').info("Starting Sim4Life application...", extra={'log_type': 'info'})
        application.run_application(disable_ui_plugins=True)
        logging.getLogger('verbose').info("Sim4Life application started.", extra={'log_type': 'success'})

def open_project(project_path):
    """
    Opens a Sim4Life project or creates a new one in memory.
    """
    import s4l_v1.document
    if not os.path.exists(project_path):
        logging.getLogger('verbose').info(f"Project file not found at {project_path}, creating a new one.", extra={'log_type': 'warning'})
        s4l_v1.document.New()
    else:
        logging.getLogger('verbose').info(f"Opening project: {project_path}", extra={'log_type': 'info'})
        s4l_v1.document.Open(project_path)

def delete_project_file(project_path):
    """
    Deletes the project file if it exists.
    """
    if os.path.exists(project_path):
        logging.getLogger('verbose').info(f"Deleting existing project file: {project_path}", extra={'log_type': 'warning'})
        os.remove(project_path)

@contextlib.contextmanager
def suppress_stdout_stderr():
    """A context manager that redirects stdout and stderr to devnull."""
    with open(os.devnull, 'w') as fnull:
        saved_stdout, saved_stderr = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = fnull, fnull
        try:
            yield
        finally:
            sys.stdout, sys.stderr = saved_stdout, saved_stderr