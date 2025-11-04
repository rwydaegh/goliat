"""QueueGUI proxy for worker process communication."""

from typing import TYPE_CHECKING
from logging import Logger
from multiprocessing import Queue
from multiprocessing.synchronize import Event

from goliat.logging_manager import LoggingMixin

if TYPE_CHECKING:
    from goliat.profiler import Profiler


class QueueGUI(LoggingMixin):
    """Proxy for ProgressGUI that operates in a separate process.

    Mimics the ProgressGUI interface but routes all calls through a multiprocessing
    queue, enabling thread-safe communication between worker and GUI processes.
    All methods serialize their arguments and send them via queue for the GUI process
    to handle.
    """

    def __init__(
        self,
        queue: Queue,
        stop_event: Event,
        profiler: "Profiler",
        progress_logger: Logger,
        verbose_logger: Logger,
    ) -> None:
        """Sets up the queue GUI proxy.

        Args:
            queue: Multiprocessing queue for IPC.
            stop_event: Event flagging user cancellation.
            profiler: Profiler for ETA calculations.
            progress_logger: Logger for progress-level messages.
            verbose_logger: Logger for detailed messages.
        """
        self.queue: Queue = queue
        self.stop_event: Event = stop_event
        self.profiler: "Profiler" = profiler
        self.progress_logger: Logger = progress_logger
        self.verbose_logger: Logger = verbose_logger

    def log(self, message: str, level: str = "verbose", log_type: str = "default") -> None:
        """Sends a log message to the GUI via queue.

        Only 'progress' level messages are forwarded to reduce queue traffic.

        Args:
            message: Log message text.
            level: Log level (only 'progress' forwarded).
            log_type: Type for color coding in GUI.
        """
        if level == "progress":
            self.queue.put({"type": "status", "message": message, "log_type": log_type})

    def update_simulation_details(self, sim_count: int, total_sims: int, details: str) -> None:
        """Sends current simulation case details to GUI.

        Args:
            sim_count: Current simulation number (1-indexed).
            total_sims: Total simulations in study.
            details: Human-readable description of current case.
        """
        self.queue.put(
            {
                "type": "sim_details",
                "count": sim_count,
                "total": total_sims,
                "details": details,
            }
        )

    def update_overall_progress(self, current_step: float, total_steps: int) -> None:
        """Updates overall study progress bar.

        Args:
            current_step: Current step number or percentage (0-100).
            total_steps: Total steps in study.
        """
        self.queue.put({"type": "overall_progress", "current": current_step, "total": total_steps})

    def update_stage_progress(self, stage_name: str, current_step: int, total_steps: int, sub_stage: str = "") -> None:
        """Updates progress for a specific stage (setup/run/extract).

        Args:
            stage_name: Stage name like 'Setup' or 'Running Simulation'.
            current_step: Current step within stage.
            total_steps: Total steps for stage.
            sub_stage: Optional sub-stage description.
        """
        self.queue.put(
            {
                "type": "stage_progress",
                "name": stage_name,
                "current": current_step,
                "total": total_steps,
                "sub_stage": sub_stage,
            }
        )

    def start_stage_animation(self, task_name: str, end_value: int) -> None:
        """Starts animated progress bar for a stage.

        Looks up time estimate from profiler and starts animation that
        progresses toward end_value over that duration.

        Args:
            task_name: Task name ('setup', 'run', 'extract', or subtask name).
            end_value: Target progress value (typically 100).
        """
        if task_name in ["setup", "run", "extract"]:
            estimate = self.profiler.profiling_config.get(f"avg_{task_name}_time", 60)
        else:
            estimate = self.profiler.get_subtask_estimate(task_name)
        self.queue.put({"type": "start_animation", "estimate": estimate, "end_value": end_value})

    def end_stage_animation(self) -> None:
        """Stops the current animated progress bar."""
        self.queue.put({"type": "end_animation"})

    def update_profiler(self) -> None:
        """Sends profiler state to GUI for ETA display."""
        self.queue.put({"type": "profiler_update", "profiler": self.profiler})

    def process_events(self) -> None:
        """No-op for interface compatibility with ProgressGUI."""
        pass

    def is_stopped(self) -> bool:
        """Checks if user requested cancellation via GUI."""
        return self.stop_event.is_set()
