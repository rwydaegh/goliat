"""Progress bar management component."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from goliat.gui.progress_gui import ProgressGUI


class ProgressManager:
    """Manages progress bar updates for overall and stage progress."""

    def __init__(self, gui: "ProgressGUI") -> None:
        """Initializes progress manager.

        Args:
            gui: ProgressGUI instance.
        """
        self.gui = gui

    def update_overall(self, current_step: float, total_steps: int) -> None:
        """Updates overall progress bar across all simulations.

        The progress bar uses a 0-10000 range internally (for finer granularity),
        but displays as percentage. Overall progress accounts for completed
        simulations plus progress within current simulation.

        Args:
            current_step: Current step number (0-100 range) or percentage (0-100).
            total_steps: Total number of steps (typically 100).
        """
        if self.gui.DEBUG:
            self.gui.update_status(f"DEBUG: update_overall_progress received: current={current_step}, total={total_steps}")
        if total_steps > 0:
            progress_percent = (current_step / total_steps) * 100
            self.gui.overall_progress_bar.setValue(int(progress_percent * 100))
            self.gui.overall_progress_bar.setFormat(f"{progress_percent:.2f}%")
            if self.gui.DEBUG:
                self.gui.update_status(f"DEBUG: Overall progress set to: {progress_percent:.2f}%")

    def update_stage(self, stage_name: str, current_step: int, total_steps: int, sub_stage: str = "") -> None:
        """Updates stage-specific progress bar and label.

        Shows progress within current phase (setup/run/extract). Stops any
        active animation when explicit progress is set. Uses 0-1000 range
        internally for finer granularity.

        Args:
            stage_name: Name of current stage (e.g., 'Setup', 'Running Simulation').
            current_step: Current step within stage.
            total_steps: Total steps for the stage.
            sub_stage: Optional sub-stage description (currently unused).
        """
        if self.gui.DEBUG:
            self.gui.update_status(
                f"DEBUG: update_stage_progress received: name='{stage_name}', current={current_step}, total={total_steps}, sub_stage='{sub_stage}'"
            )

        self.gui.stage_label.setText(f"Current Stage: {stage_name}")
        self.gui.total_steps_for_stage = total_steps
        self.gui.progress_animation.stop()

        progress_percent = (current_step / total_steps) if total_steps > 0 else 0
        final_value = int(progress_percent * 1000)

        self.gui.stage_progress_bar.setValue(final_value)
        self.gui.stage_progress_bar.setFormat(f"{progress_percent * 100:.0f}%")
        if self.gui.DEBUG:
            self.gui.update_status(f"DEBUG: Stage '{stage_name}' progress set to: {progress_percent * 100:.0f}%")

    def update_simulation_details(self, sim_count: int, total_sims: int, details: str) -> None:
        """Updates simulation counter and details labels.

        Args:
            sim_count: Current simulation number.
            total_sims: Total number of simulations.
            details: Description of current simulation case.
        """
        self.gui.current_simulation_count = sim_count
        self.gui.total_simulations = total_sims
        self.gui.sim_counter_label.setText(f"Simulation: {sim_count} / {total_sims}")
        self.gui.sim_details_label.setText(f"Current Case: {details}")
