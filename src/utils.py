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

class StudyCancelledError(Exception):
    """Custom exception to indicate that the study was cancelled by the user."""
    pass

class Profiler:
    """
    A profiler to track execution time, estimate remaining time, and calculate weighted progress.
    """
    def __init__(self, config):
        self.config = config
        self.execution_control = self.config.get_setting('execution_control', {'do_setup': True, 'do_run': True, 'do_extract': True})
        self.phase_weights = self._get_active_phase_weights()
        self.subtask_estimates = self.config.get_profiling_subtask_estimates()
        self.start_time = time.monotonic()
        self.stage_start_time = None
        self.completed_stages = 0
        self.time_for_completed_stages = 0.0
        self.total_stages = 0  # Total stages for the current phase (e.g., number of simulations in 'run')
        self.total_simulations = 0 # Total simulations for the entire study
        self.current_phase_progress = 0
        self.completed_phases = set()
        self.current_phase = None
        # Use a defaultdict to store lists of times for each named subtask
        self.subtask_times = defaultdict(list)
        # Stack to manage nested subtasks
        self.subtask_stack = []

    def _get_active_phase_weights(self):
        """
        Filters and normalizes phase weights based on execution_control settings.
        """
        all_weights = self.config.get_profiling_weights()
        active_weights = {}
        
        if self.execution_control.get('do_setup'):
            active_weights['setup'] = all_weights.get('setup', 0)
        if self.execution_control.get('do_run'):
            active_weights['run'] = all_weights.get('run', 0)
        if self.execution_control.get('do_extract'):
            active_weights['extract'] = all_weights.get('extract', 0)
            
        total_active_weight = sum(active_weights.values())
        if total_active_weight > 0:
            # Normalize the weights of active phases so they sum to 1
            normalized_weights = {phase: weight / total_active_weight for phase, weight in active_weights.items()}
            return normalized_weights
        return {}

    def set_total_simulations(self, count):
        """Sets the total number of simulations for the entire study."""
        self.total_simulations = count

    def start_stage(self, phase_name, total_stages=None):
        self.current_phase = phase_name
        self.stage_start_time = time.monotonic()
        if total_stages is not None:
            self.total_stages = total_stages
        # When starting the 'run' phase, reset stage counters
        if phase_name == 'run':
            self.completed_stages = 0
            self.time_for_completed_stages = 0.0

    def end_stage(self):
        if not self.stage_start_time or not self.current_phase:
            return 0

        stage_duration = time.monotonic() - self.stage_start_time
        
        if self.current_phase == 'run':
            # This is called for each simulation in the run phase
            self.time_for_completed_stages += stage_duration
            self.completed_stages += 1
            # Reset timer for the next stage, assuming they run sequentially
            self.stage_start_time = time.monotonic()
            # We do NOT complete the phase here. It's completed manually after the loop.
        else:
            # For 'setup' and 'extract', ending the stage means ending the phase.
            self.completed_phases.add(self.current_phase)
            self.current_phase = None
        
        return stage_duration

    def complete_run_phase(self):
        """Manually marks the 'run' phase as complete."""
        if self.current_phase == 'run':
            self.completed_phases.add('run')
            self.current_phase = None

    def start_subtask(self, task_name):
        """Starts timing a named subtask by pushing it onto the stack."""
        self.subtask_stack.append({'name': task_name, 'start_time': time.monotonic()})

    def end_subtask(self):
        """Ends timing the current subtask by popping it from the stack."""
        if not self.subtask_stack:
            return 0
        
        subtask = self.subtask_stack.pop()
        elapsed = time.monotonic() - subtask['start_time']
        self.subtask_times[subtask['name']].append(elapsed)
        return elapsed

    def get_subtask_estimate(self, task_name):
        """Returns the estimated time for a given subtask."""
        return self.subtask_estimates.get(task_name, 0)

    def save_estimates(self):
        """
        Calculates the average time for each subtask and saves the updated
        estimates back to the profiling configuration file.
        """
        # Create a new dictionary for the updated estimates
        updated_estimates = {}
        for task_name, times in self.subtask_times.items():
            if times:
                updated_estimates[task_name] = sum(times) / len(times)
        
        # Preserve estimates for tasks that didn't run in this session
        for task_name, estimate in self.subtask_estimates.items():
            if task_name not in updated_estimates:
                updated_estimates[task_name] = estimate

        # Reload the full config, update it, and save it back
        full_config = self.config.profiling_config
        full_config['subtask_estimates'] = updated_estimates
        
        with open(self.config.profiling_config_path, 'w') as f:
            json.dump(full_config, f, indent=4)

    def get_weighted_progress(self, phase_name, phase_progress):
        """Calculates the overall progress based on phase weights."""
        total_progress = 0
        for phase, weight in self.phase_weights.items():
            if phase == phase_name:
                total_progress += weight * phase_progress
            elif phase in self.completed_phases:
                total_progress += weight
        return total_progress * 100

    def get_time_remaining(self, current_stage_progress=0):
        """
        Calculates the estimated time remaining by combining actual measurements
        for past phases with historical estimates for future phases.
        """
        total_remaining_sec = 0
        
        phase_subtask_map = {
            'setup': 'setup_simulation',
            'run': 'run_simulation_total',
            'extract': 'extract_sar_statistics'
        }

        # 1. Time for the current, in-progress phase
        if self.current_phase and self.current_phase not in self.completed_phases:
            if self.current_phase == 'run':
                if self.completed_stages > 0:
                    avg_time_per_stage = self.time_for_completed_stages / self.completed_stages
                    remaining_stages = self.total_stages - self.completed_stages
                    # Time for the rest of the current stage being processed by SimulationRunner
                    time_for_current_stage = avg_time_per_stage * (1 - current_stage_progress)
                    # Time for all future stages in this phase
                    time_for_future_stages = avg_time_per_stage * (remaining_stages - 1) if remaining_stages > 0 else 0
                    total_remaining_sec += time_for_current_stage + time_for_future_stages
                else:
                    # Use historical estimate if no stages are complete yet
                    run_estimate_per_stage = self.subtask_estimates.get(phase_subtask_map['run'], 0)
                    total_run_estimate = run_estimate_per_stage * self.total_stages
                    # Estimate remaining based on progress of the very first stage
                    progress_of_total_run = current_stage_progress / self.total_stages if self.total_stages > 0 else 0
                    total_remaining_sec += total_run_estimate * (1.0 - progress_of_total_run)
            else:  # For 'setup' and 'extract'
                subtask_name = phase_subtask_map.get(self.current_phase)
                if subtask_name:
                    phase_estimate = self.subtask_estimates.get(subtask_name, 0)
                    # If estimate is 0 (e.g., first run), extrapolate from current progress
                    if phase_estimate == 0 and current_stage_progress > 0.01 and self.stage_start_time:
                        elapsed = time.monotonic() - self.stage_start_time
                        phase_estimate = elapsed / current_stage_progress
                    
                    total_remaining_sec += phase_estimate * (1.0 - current_stage_progress)

        # 2. Add estimates for all future, un-started phases
        future_phases = self.phase_weights.keys() - self.completed_phases - {self.current_phase}
        for phase in future_phases:
            subtask_name = phase_subtask_map.get(phase)
            if not subtask_name:
                continue
            
            estimate = self.subtask_estimates.get(subtask_name, 0)
            
            if phase in ['run', 'extract']:
                # Use the total simulation count for run and extract estimates
                total_remaining_sec += estimate * self.total_simulations
            else:  # setup
                total_remaining_sec += estimate

        return max(0, total_remaining_sec)

    def get_elapsed(self):
        return time.monotonic() - self.start_time

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

    study._log(f"--- Starting: {phase_name} ---")
    start_time = time.monotonic()
    try:
        yield
    finally:
        elapsed = time.monotonic() - start_time
        study._log(f"--- Finished: {phase_name} (took {elapsed:.2f}s) ---")
        
        if phase_name != 'run':
            study.profiler.end_stage()
        
        if study.gui:
            study.gui.update_profiler()


def ensure_s4l_running():
    """
    Ensures that the Sim4Life application is running.
    """
    from s4l_v1._api import application
    
    if application.get_app_safe() is None:
        logging.getLogger('verbose').info("Starting Sim4Life application...")
        application.run_application(disable_ui_plugins=True)
        logging.getLogger('verbose').info("Sim4Life application started.")

def open_project(project_path):
    """
    Opens a Sim4Life project or creates a new one in memory.
    """
    import s4l_v1.document
    if not os.path.exists(project_path):
        logging.getLogger('verbose').info(f"Project file not found at {project_path}, creating a new one.")
        s4l_v1.document.New()
    else:
        logging.getLogger('verbose').info(f"Opening project: {project_path}")
        s4l_v1.document.Open(project_path)

def delete_project_file(project_path):
    """
    Deletes the project file if it exists.
    """
    if os.path.exists(project_path):
        logging.getLogger('verbose').info(f"Deleting existing project file: {project_path}")
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
