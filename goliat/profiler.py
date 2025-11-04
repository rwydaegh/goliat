import contextlib
import json
import time
from collections import defaultdict


class Profiler:
    """Manages execution time tracking, ETA estimation, and study phase management.

    This class divides a study into phases (setup, run, extract), calculates
    weighted progress, and estimates the time remaining. It also saves updated
    time estimates to a configuration file after each run, making it
    self-improving.
    """

    def __init__(
        self,
        execution_control: dict,
        profiling_config: dict,
        study_type: str,
        config_path: str,
    ):
        """Sets up the profiler with phase tracking and ETA estimation.

        Args:
            execution_control: Dict indicating which phases are enabled.
            profiling_config: Historical timing data for estimates.
            study_type: Study type ('near_field' or 'far_field').
            config_path: Path where profiling config is saved.
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

    def _calculate_phase_weights(self) -> dict:
        """Calculates normalized weights for each enabled phase.

        Uses historical timing data to weight phases proportionally to their
        expected duration. Used for weighted progress calculation.

        Returns:
            Dict mapping phase names to normalized weights (sum to 1.0).
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

    def set_total_simulations(self, total: int):
        """Sets total simulation count for progress tracking."""
        self.total_simulations = total

    def set_project_scope(self, total_projects: int):
        """Sets total project count for progress tracking."""
        self.total_projects = total_projects

    def set_current_project(self, project_index: int):
        """Sets the current project index."""
        self.current_project = project_index

    def simulation_completed(self):
        """Marks one simulation as completed."""
        self.completed_simulations += 1

    def start_stage(self, phase_name: str, total_stages: int = 1):
        """Starts tracking a new phase (setup/run/extract).

        Args:
            phase_name: Phase name like 'setup', 'run', or 'extract'.
            total_stages: Number of stages within this phase.
        """
        self.current_phase = phase_name
        self.phase_start_time = time.monotonic()
        self.completed_stages_in_phase = 0
        self.total_stages_in_phase = total_stages

    def end_stage(self):
        """Ends current phase and records its duration for future estimates."""
        if self.phase_start_time:
            elapsed = time.monotonic() - self.phase_start_time
            self.profiling_config[f"avg_{self.current_phase}_time"] = elapsed
        self.current_phase = None

    def complete_run_phase(self):
        """Stores the total duration of the 'run' phase from its subtasks."""
        self.run_phase_total_duration = sum(self.subtask_times.get("run_simulation_total", [0]))

    def get_weighted_progress(self, phase_name: str, phase_progress_ratio: float) -> float:
        """Calculates overall study progress using phase weights and simulation count.

        This method handles the complexity that different phases (setup, run, extract)
        take different amounts of time. For example, if setup takes 10 minutes, run takes
        2 hours, and extract takes 5 minutes, then the run phase should account for
        roughly 85% of the progress bar, not 33%.

        The calculation works in two parts:
        1. Progress within current simulation: Sums weights of completed phases,
           plus partial weight for the current phase based on its progress ratio.
        2. Overall progress: Divides (completed_simulations + current_sim_progress)
           by total_simulations to get the overall percentage.

        Args:
            phase_name: The name of the current phase ('setup', 'run', or 'extract').
            phase_progress_ratio: Progress within current phase (0.0 = not started,
                                 1.0 = fully complete).

        Returns:
            Overall progress percentage (0.0 to 100.0).
        """
        if self.total_simulations == 0:
            return 0.0

        # Progress within the current simulation
        progress_current_sim = 0
        for p, w in self.phase_weights.items():
            if p == phase_name:
                progress_current_sim += w * phase_progress_ratio
                break
            progress_current_sim += w

        # Overall progress
        overall_progress = (self.completed_simulations + progress_current_sim) / self.total_simulations
        # print(f"DEBUG: get_weighted_progress: phase={phase_name}, ratio={phase_progress_ratio:.2f}, completed={self.completed_simulations}, total={self.total_simulations}, progress={overall_progress * 100:.1f}%")
        return overall_progress * 100

    def get_subtask_estimate(self, task_name: str) -> float:
        """Retrieves the estimated time for a specific subtask.
        Args:
            task_name: The name of the subtask.
        Returns:
            The estimated duration in seconds.
        """
        return self.profiling_config.get(f"avg_{task_name}", 1.0)

    def get_phase_subtasks(self, phase_name: str) -> list:
        """Gets a list of subtasks for a given phase.
        Args:
            phase_name: The name of the phase.
        Returns:
            A list of subtask names.
        """
        subtasks = []
        for key in self.profiling_config.keys():
            if key.startswith(f"avg_{phase_name}_"):
                subtasks.append(key.replace("avg_", ""))
        return subtasks

    def get_time_remaining(self, current_stage_progress: float = 0.0) -> float:
        """Estimates total time remaining for the entire study.

        Uses historical timing data to predict how long each phase will take,
        then calculates remaining time by subtracting elapsed time from total
        estimated time. This gives a realistic ETA that accounts for the fact
        that different phases take different amounts of time.

        The calculation considers:
        - Time already spent on fully completed simulations
        - Time spent on phases within the current simulation that are done
        - Estimated time remaining in the current phase (based on progress ratio)
        - Estimated time for all future simulations

        Args:
            current_stage_progress: Progress within current stage (0.0 to 1.0).

        Returns:
            Estimated time remaining in seconds.
        """
        if not self.current_phase or self.total_simulations == 0:
            return 0.0

        # Calculate the total estimated time for one simulation
        total_time_per_sim = 0
        for phase in ["setup", "run", "extract"]:
            if self.execution_control.get(f"do_{phase}", False):
                total_time_per_sim += self.profiling_config.get(f"avg_{phase}_time", 60)

        # Calculate the time already spent on completed simulations
        time_for_completed_sims = self.completed_simulations * total_time_per_sim

        # Calculate the time spent on the current simulation so far
        time_spent_on_current_sim = 0
        ordered_phases = [p for p in ["setup", "run", "extract"] if self.execution_control.get(f"do_{p}", False)]
        try:
            current_phase_index = ordered_phases.index(self.current_phase)
        except ValueError:
            current_phase_index = 0

        for i in range(current_phase_index):
            phase = ordered_phases[i]
            time_spent_on_current_sim += self.profiling_config.get(f"avg_{phase}_time", 60)

        current_phase_time = self.profiling_config.get(f"avg_{self.current_phase}_time", 60)
        time_spent_on_current_sim += current_phase_time * current_stage_progress

        # Time elapsed in the current phase
        if self.phase_start_time:
            time_spent_on_current_sim += time.monotonic() - self.phase_start_time

        # Total time elapsed is the sum of time for completed sims and time spent on the current one
        total_elapsed_time = time_for_completed_sims + time_spent_on_current_sim

        # Total estimated time for all simulations
        total_estimated_time = self.total_simulations * total_time_per_sim

        # Estimated time remaining
        eta = total_estimated_time - total_elapsed_time
        return max(0, eta)

    @contextlib.contextmanager
    def subtask(self, task_name: str):
        """A context manager to time a subtask."""
        self.subtask_stack.append({"name": task_name, "start_time": time.monotonic()})
        try:
            yield
        finally:
            subtask = self.subtask_stack.pop()
            elapsed = time.monotonic() - subtask["start_time"]
            self.subtask_times[subtask["name"]].append(elapsed)
            self.update_and_save_estimates()

    def update_and_save_estimates(self):
        """Updates the profiling configuration with the latest average times and saves it.

        This makes the profiler's estimates self-improving over time.
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
                full_config[self.study_type][key] = round(value, 2)

        for task_name, times in self.subtask_times.items():
            if times:
                avg_task_time = sum(times) / len(times)
                avg_key = f"avg_{task_name}"
                full_config[self.study_type][avg_key] = round(avg_task_time, 2)
                # Also update the in-memory profiling_config so it's available when sent to GUI
                self.profiling_config[avg_key] = round(avg_task_time, 2)

        with open(self.config_path, "w") as f:
            json.dump(full_config, f, indent=4)

    def save_estimates(self):
        """Saves the final profiling estimates at the end of the study."""
        self.update_and_save_estimates()
