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
        self.phase_skipped = False
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
        self.phase_skipped = False
        self.completed_stages_in_phase = 0
        self.total_stages_in_phase = total_stages

    def end_stage(self):
        """Ends current phase and records its duration for future estimates."""
        if self.phase_start_time:
            elapsed = time.monotonic() - self.phase_start_time

            # For setup phase: if it was cached/skipped, don't add to statistics
            # (cached phases pollute real execution time statistics)
            if self.current_phase == "setup" and self.phase_skipped:
                # Cached setup: don't pollute statistics
                # avg_{phase}_time remains unchanged (uses previous real measurements)
                pass
            else:
                # Real phase: add to statistics and compute simple average for display
                self.subtask_times[self.current_phase].append(elapsed)
                times = self.subtask_times[self.current_phase]
                # Store simple average for pie charts, timings table, etc.
                self.profiling_config[f"avg_{self.current_phase}_time"] = sum(times) / len(times)

        self.current_phase = None
        self.phase_skipped = False  # Reset for next phase

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

    def _get_smart_phase_estimate(self, phase: str) -> float:
        """Computes a robust, recent-weighted estimate for a phase.

        Emphasizes the last 3 simulations while using all available data.
        Uses weighted average where recent measurements get higher weights.

        Args:
            phase: Phase name ('setup', 'run', or 'extract')

        Returns:
            Estimated time in seconds for this phase
        """
        times = self.subtask_times.get(phase, [])

        if not times:
            # No data yet - use saved average or default
            return self.profiling_config.get(f"avg_{phase}_time", 60)

        if len(times) == 1:
            # Only one measurement - use it
            return times[0]

        # Emphasize last 3 simulations with weighted average
        # Last 3 get 70% of total weight, remaining get 30%
        # Within last 3: most recent gets highest weight (0.5), then 0.3, then 0.2

        if len(times) >= 3:
            # Get last 3 measurements (oldest to newest)
            last_3 = times[-3:]
            # Weights: [oldest of last 3, middle, most recent]
            # Most recent (last element) gets highest weight
            last_3_weights = [0.2, 0.3, 0.5]  # Most recent gets highest weight
            last_3_total_weight = sum(last_3_weights)

            # Remaining measurements (all except last 3) get equal weight
            remaining = times[:-3]
            if remaining:
                remaining_avg = sum(remaining) / len(remaining)
                # Remaining gets 30% of total weight, last 3 gets 70%
                remaining_weight = 0.3
                last_3_weight = 0.7

                # Normalize last_3 weights to sum to last_3_weight (0.7)
                normalized_last_3_weights = [w * last_3_weight / last_3_total_weight for w in last_3_weights]
                last_3_weighted_sum = sum(t * w for t, w in zip(last_3, normalized_last_3_weights))

                estimate = last_3_weighted_sum + remaining_avg * remaining_weight
            else:
                # Only 3 measurements total - use weighted average
                estimate = sum(t * w for t, w in zip(last_3, last_3_weights)) / last_3_total_weight
        else:
            # Less than 3 measurements - use weighted average of what we have
            # Most recent gets higher weight
            weights = [0.6, 0.4] if len(times) == 2 else [1.0]
            estimate = sum(t * w for t, w in zip(times, weights)) / sum(weights)

        return estimate

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

        # Calculate the total estimated time for one simulation using smart estimates
        total_time_per_sim = 0
        for phase in ["setup", "run", "extract"]:
            if self.execution_control.get(f"do_{phase}", False):
                total_time_per_sim += self._get_smart_phase_estimate(phase)

        # Calculate estimated time remaining in the current simulation
        ordered_phases = [p for p in ["setup", "run", "extract"] if self.execution_control.get(f"do_{p}", False)]
        try:
            current_phase_index = ordered_phases.index(self.current_phase)
        except ValueError:
            current_phase_index = 0

        # Estimated time remaining in current phase (based on progress)
        # Clamp progress to [0.0, 1.0] to handle edge cases
        progress = max(0.0, min(1.0, current_stage_progress))
        current_phase_time = self._get_smart_phase_estimate(self.current_phase)
        time_remaining_in_current_sim = current_phase_time * (1.0 - progress)

        # Add time for phases not yet started in current simulation
        for i in range(current_phase_index + 1, len(ordered_phases)):
            phase = ordered_phases[i]
            time_remaining_in_current_sim += self._get_smart_phase_estimate(phase)

        # Calculate remaining simulations (excluding current one)
        remaining_simulations = self.total_simulations - self.completed_simulations - 1

        # Estimated time remaining = time left in current sim + time for all remaining sims
        eta = time_remaining_in_current_sim + (remaining_simulations * total_time_per_sim)
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
