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
    A profiler to track execution time, estimate remaining time, and calculate weighted progress.
    """
    def __init__(self, execution_control, profiling_config, study_type, config_path):
        self.execution_control = execution_control
        self.profiling_config = profiling_config
        self.study_type = study_type
        self.config_path = config_path
        self.phase_weights = self._get_active_phase_weights()
        self.subtask_estimates = self.profiling_config.get("subtask_estimates", {})
        self.start_time = time.monotonic()
        self.stage_start_time = None
        self.completed_stages = 0
        self.time_for_completed_stages = 0.0
        self.total_stages = 0  # Total stages for the current phase (e.g., number of simulations in 'run')
        self.total_simulations = 0 # Total simulations for the entire study
        self.current_phase_progress = 0
        self.completed_phases = set()
        self.current_phase = None
        self.total_projects = 1
        self.current_project_index = 1
        # Use a defaultdict to store lists of times for each named subtask
        self.subtask_times = defaultdict(list)
        # Stack to manage nested subtasks
        self.subtask_stack = []
        self.phase_durations = {}

    def _get_active_phase_weights(self):
        """
        Filters and normalizes phase weights based on execution_control settings.
        """
        all_weights = self.profiling_config.get("phase_weights", {})
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

    def set_project_scope(self, count):
        """Sets the total number of projects for the entire study."""
        self.total_projects = count if count > 0 else 1

    def set_current_project(self, index):
        """Sets the current project number (1-based)."""
        self.current_project_index = index

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
            self.phase_durations[self.current_phase] = stage_duration
            self.completed_phases.add(self.current_phase)
            self.current_phase = None
        
        return stage_duration

    def complete_run_phase(self):
        """Manually marks the 'run' phase as complete."""
        if self.current_phase == 'run':
            self.phase_durations['run'] = self.time_for_completed_stages
            self.completed_phases.add('run')
            self.current_phase = None


    def get_subtask_estimate(self, task_name):
        """Returns the estimated time for a given subtask."""
        return self.subtask_estimates.get(task_name, 0)

    def save_estimates(self):
        """
        Calculates the average time for each subtask and the relative weight of each phase,
        then saves the updated estimates back to the profiling configuration file.
        """
        # --- 1. Update Subtask Estimates ---
        updated_estimates = {}
        for task_name, times in self.subtask_times.items():
            if times:
                updated_estimates[task_name] = sum(times) / len(times)
        
        # Preserve estimates for tasks that didn't run in this session
        for task_name, estimate in self.subtask_estimates.items():
            if task_name not in updated_estimates:
                updated_estimates[task_name] = estimate

        # --- 2. Update Phase Weights ---
        total_study_time = sum(self.phase_durations.values())
        updated_weights = self.phase_weights.copy() # Start with existing weights

        if total_study_time > 0:
            # Calculate new weights only for phases that actually ran
            for phase, duration in self.phase_durations.items():
                updated_weights[phase] = duration / total_study_time
        
        # Normalize the weights to ensure they sum to 1
        total_weight = sum(updated_weights.values())
        if total_weight > 0:
            final_weights = {phase: weight / total_weight for phase, weight in updated_weights.items()}
        else:
            final_weights = updated_weights

        # --- 3. Save to File ---
        try:
            with open(self.config_path, 'r') as f:
                full_config = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            # If the file doesn't exist or is empty, create a new structure
            full_config = {}

        # Ensure the study type key exists
        if self.study_type not in full_config:
            full_config[self.study_type] = {}
            
        full_config[self.study_type]['subtask_estimates'] = updated_estimates
        full_config[self.study_type]['phase_weights'] = final_weights
        
        # Save the full config back
        with open(self.config_path, 'w') as f:
            json.dump(full_config, f, indent=4)

    def get_weighted_progress(self, phase_name, phase_progress):
        """
        Calculates the overall progress based on phase weights and project progress.
        """
        # Progress from already completed projects (current_project_index is 1-based)
        progress_from_completed_projects = (self.current_project_index - 1) / self.total_projects if self.total_projects > 0 else 0

        # Progress within the current project
        current_project_phase_progress = 0
        for phase, weight in self.phase_weights.items():
            if phase == phase_name:
                current_project_phase_progress += weight * phase_progress
            elif phase in self.completed_phases:
                current_project_phase_progress += weight
        
        # The progress of the current project contributes only its fraction of the total
        progress_from_current_project = current_project_phase_progress / self.total_projects if self.total_projects > 0 else 0

        total_progress = progress_from_completed_projects + progress_from_current_project
        
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
        if self.current_phase and self.current_phase not in self.completed_phases and self.stage_start_time is not None:
            # Always use real-time progress to estimate the current phase's total time.
            # This is more accurate than historical estimates and works on the first run.
            elapsed_in_phase = time.monotonic() - self.stage_start_time
            
            if self.current_phase == 'run':
                # Calculate progress within the 'run' phase itself
                progress_of_run_phase = (self.completed_stages + current_stage_progress) / self.total_stages if self.total_stages > 0 else 0
                
                if progress_of_run_phase > 0.01: # Avoid division by zero
                    # Project total time for the entire 'run' phase based on current progress
                    projected_total_time_for_run = elapsed_in_phase / progress_of_run_phase
                    remaining_time_for_run = projected_total_time_for_run - elapsed_in_phase
                    total_remaining_sec += remaining_time_for_run
                else:
                    # Fallback to historical estimate if we have no progress yet
                    run_estimate_per_stage = self.subtask_estimates.get(phase_subtask_map['run'], 0)
                    total_remaining_sec += run_estimate_per_stage * self.total_stages

            else:  # For 'setup' and 'extract'
                if current_stage_progress > 0.01: # Avoid division by zero
                    projected_total_time_for_phase = elapsed_in_phase / current_stage_progress
                    remaining_time_for_phase = projected_total_time_for_phase - elapsed_in_phase
                    total_remaining_sec += remaining_time_for_phase
                else:
                    # Fallback to historical estimate
                    subtask_name = phase_subtask_map.get(self.current_phase)
                    if subtask_name:
                        total_remaining_sec += self.subtask_estimates.get(subtask_name, 0)

        # 2. Add estimates for all future, un-started phases
        # If we are in a phase, future_phases are the ones after it.
        # If we are BETWEEN phases (current_phase is None), future_phases are all non-completed ones.
        if self.current_phase:
            future_phases = self.phase_weights.keys() - self.completed_phases - {self.current_phase}
        else:
            future_phases = self.phase_weights.keys() - self.completed_phases
            
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
        
        study._log(f"  - Activating line profiler for subtask: {task_name}", level='verbose')
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
        study._log(f"    - Subtask '{task_name}' done in {elapsed:.2f}s", level='progress')

        # If the line profiler was active, print its stats
        if lp:
            study._log(f"    - Line profiler stats for '{task_name}':", level='verbose')
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
