import time
import json
from collections import defaultdict

class Profiler:
    """
    A profiler to track execution time, estimate remaining time, and manage study phases.
    """
    def __init__(self, execution_control, profiling_config, study_type, config_path):
        self.execution_control = execution_control
        self.profiling_config = profiling_config
        self.study_type = study_type
        self.config_path = config_path

        self.phase_weights = self._calculate_phase_weights()
        self.subtask_times = defaultdict(list)
        self.subtask_stack = []
        
        self.total_simulations = 0
        self.completed_simulations = 0
        self.total_projects = 0
        self.current_project = 0
        self.completed_phases = set()
        
        self.start_time = time.monotonic()
        self.current_phase = None
        self.phase_start_time = None
        self.run_phase_total_duration = 0

    def _calculate_phase_weights(self):
        """Calculate the relative weight of each enabled study phase."""
        weights = {}
        total_weight = 0
        for phase in ['setup', 'run', 'extract']:
            if self.execution_control.get(f'do_{phase}', False):
                weight = self.profiling_config.get(f'avg_{phase}_time', 1)
                weights[phase] = weight
                total_weight += weight
        
        if total_weight > 0:
            for phase in weights:
                weights[phase] /= total_weight
        return weights

    def set_total_simulations(self, total):
        self.total_simulations = total

    def set_project_scope(self, total_projects):
        self.total_projects = total_projects

    def set_current_project(self, project_index):
        self.current_project = project_index

    def start_stage(self, phase_name, total_stages=1):
        self.current_phase = phase_name
        self.phase_start_time = time.monotonic()
        self.completed_stages_in_phase = 0
        self.total_stages_in_phase = total_stages

    def end_stage(self):
        if self.phase_start_time:
            elapsed = time.monotonic() - self.phase_start_time
            self.profiling_config[f'avg_{self.current_phase}_time'] = elapsed
        self.current_phase = None

    def complete_run_phase(self):
        self.run_phase_total_duration = sum(self.subtask_times.get('run_simulation_total', [0]))

    def get_weighted_progress(self, phase_name, phase_progress_ratio):
        """Calculates the overall progress based on the current phase's weight and progress."""
        progress = 0
        # Add the weight of all completed phases
        for p, w in self.phase_weights.items():
            if p == phase_name:
                progress += w * phase_progress_ratio
                break
            progress += w
        return progress * 100

    def get_subtask_estimate(self, task_name):
        """
        Gets the estimated time for a specific subtask from the profiling config.
        Returns a default value if not found.
        """
        return self.profiling_config.get(f'avg_{task_name}', 1.0) # Default to 1 second

    def get_time_remaining(self, current_stage_progress=0.0):
        """
        Estimates the total time remaining for the study by considering completed phases,
        the progress of the current phase, and the estimated time for future phases.
        """
        if not self.current_phase:
            return 0

        # Find the index of the current phase in the execution order
        ordered_phases = [p for p in ['setup', 'run', 'extract'] if self.execution_control.get(f'do_{p}', False)]
        try:
            current_phase_index = ordered_phases.index(self.current_phase)
        except ValueError:
            return 0 # Current phase not in the expected list

        # 1. Time remaining in the current phase
        current_phase_total_time = self.profiling_config.get(f'avg_{self.current_phase}_time', 60)
        time_in_current_phase = current_phase_total_time * (1 - current_stage_progress)

        # 2. Time for all future phases
        time_for_future_phases = 0
        for i in range(current_phase_index + 1, len(ordered_phases)):
            future_phase = ordered_phases[i]
            time_for_future_phases += self.profiling_config.get(f'avg_{future_phase}_time', 60)

        # 3. Total ETA
        eta = time_in_current_phase + time_for_future_phases
        return max(0, eta)

    def save_estimates(self):
        """Saves the updated average times to the configuration file."""
        try:
            with open(self.config_path, 'r') as f:
                full_config = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            full_config = {}

        if self.study_type not in full_config:
            full_config[self.study_type] = {}

        # Update averages
        for key, value in self.profiling_config.items():
            if key.startswith('avg_'):
                full_config[self.study_type][key] = value
        
        # Update subtask averages
        for task_name, times in self.subtask_times.items():
            if times:
                avg_task_time = sum(times) / len(times)
                full_config[self.study_type][f'avg_{task_name}'] = avg_task_time

        with open(self.config_path, 'w') as f:
            json.dump(full_config, f, indent=4)