import json
import time
from collections import defaultdict


class Profiler:
    """
    Manages execution time tracking, ETA estimation, and study phase management.

    This class provides a comprehensive system for profiling the execution of a
    study. It divides the study into phases (setup, run, extract), calculates
    weighted progress, and estimates the time remaining. It also features a
    self-improving mechanism by saving updated time estimates to a configuration
    file after each run.
    """

    def __init__(self, execution_control, profiling_config, study_type, config_path):
        """
        Initializes the Profiler.

        Args:
            execution_control (dict): A dictionary indicating which study phases are active.
            profiling_config (dict): A dictionary with historical timing data for phases and subtasks.
            study_type (str): The type of the study (e.g., 'near_field').
            config_path (str): The file path to the profiling configuration.
        """
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
        """
        Calculates the relative weight of each enabled study phase based on historical data.

        Returns:
            dict: A dictionary mapping phase names to their normalized weights.
        """
        weights = {}
        total_weight = 0
        for phase in ["setup", "run", "extract"]:
            if self.execution_control.get(f"do_{phase}", False):
                weight = self.profiling_config.get(f"avg_{phase}_time", 1)
                weights[phase] = weight
                total_weight += weight

        if total_weight > 0:
            for phase in weights:
                weights[phase] /= total_weight
        return weights

    def set_total_simulations(self, total):
        """Sets the total number of simulations for the entire study."""
        self.total_simulations = total

    def set_project_scope(self, total_projects):
        """Sets the total number of projects to be processed."""
        self.total_projects = total_projects

    def set_current_project(self, project_index):
        """Sets the index of the currently processing project."""
        self.current_project = project_index

    def start_stage(self, phase_name, total_stages=1):
        """
        Marks the beginning of a new study phase or stage.

        Args:
            phase_name (str): The name of the phase being started.
            total_stages (int): The total number of stages within this phase.
        """
        self.current_phase = phase_name
        self.phase_start_time = time.monotonic()
        self.completed_stages_in_phase = 0
        self.total_stages_in_phase = total_stages

    def end_stage(self):
        """Marks the end of a study phase or stage and records its duration."""
        if self.phase_start_time:
            elapsed = time.monotonic() - self.phase_start_time
            self.profiling_config[f"avg_{self.current_phase}_time"] = elapsed
        self.current_phase = None

    def complete_run_phase(self):
        """Calculates and stores the total duration of the 'run' phase from its subtasks."""
        self.run_phase_total_duration = sum(
            self.subtask_times.get("run_simulation_total", [0])
        )

    def get_weighted_progress(self, phase_name, phase_progress_ratio):
        """
        Calculates the overall study progress based on the weight of the current phase.

        Args:
            phase_name (str): The name of the current phase.
            phase_progress_ratio (float): The progress of the current phase (0.0 to 1.0).

        Returns:
            float: The total weighted progress percentage.
        """
        progress = 0
        for p, w in self.phase_weights.items():
            if p == phase_name:
                progress += w * phase_progress_ratio
                break
            progress += w
        return progress * 100

    def get_subtask_estimate(self, task_name):
        """
        Retrieves the estimated time for a specific subtask from the profiling configuration.

        Args:
            task_name (str): The name of the subtask.

        Returns:
            float: The estimated duration in seconds.
        """
        return self.profiling_config.get(f"avg_{task_name}", 1.0)

    def get_time_remaining(self, current_stage_progress=0.0):
        """
        Estimates the total time remaining for the study.

        This estimation considers completed phases, the progress of the current
        phase, and the estimated time for all future phases.

        Args:
            current_stage_progress (float): The progress of the current stage (0.0 to 1.0).

        Returns:
            float: The estimated time remaining in seconds.
        """
        if not self.current_phase:
            return 0

        ordered_phases = [
            p
            for p in ["setup", "run", "extract"]
            if self.execution_control.get(f"do_{p}", False)
        ]
        try:
            current_phase_index = ordered_phases.index(self.current_phase)
        except ValueError:
            return 0

        current_phase_total_time = self.profiling_config.get(
            f"avg_{self.current_phase}_time", 60
        )
        time_in_current_phase = current_phase_total_time * (1 - current_stage_progress)

        time_for_future_phases = 0
        for i in range(current_phase_index + 1, len(ordered_phases)):
            future_phase = ordered_phases[i]
            time_for_future_phases += self.profiling_config.get(
                f"avg_{future_phase}_time", 60
            )

        eta = time_in_current_phase + time_for_future_phases
        return max(0, eta)

    def update_and_save_estimates(self):
        """
        Updates the profiling configuration with the latest average times and saves it to a file.
        This method makes the profiler's estimates self-improving over time.
        """
        try:
            with open(self.config_path, "r") as f:
                full_config = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            full_config = {}

        if self.study_type not in full_config:
            full_config[self.study_type] = {}

        for key, value in self.profiling_config.items():
            if key.startswith("avg_"):
                full_config[self.study_type][key] = value

        for task_name, times in self.subtask_times.items():
            if times:
                avg_task_time = sum(times) / len(times)
                full_config[self.study_type][f"avg_{task_name}"] = avg_task_time

        with open(self.config_path, "w") as f:
            json.dump(full_config, f, indent=4)

    def save_estimates(self):
        """
        Ensures the final profiling estimates are saved at the end of the study.
        """
        self.update_and_save_estimates()
