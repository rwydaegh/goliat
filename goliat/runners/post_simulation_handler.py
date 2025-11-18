"""Post-simulation handling for waiting and reloading projects."""

from typing import TYPE_CHECKING

from ..logging_manager import LoggingMixin
from ..utils import non_blocking_sleep, open_project

if TYPE_CHECKING:
    from logging import Logger

    from ..profiler import Profiler


class PostSimulationHandler(LoggingMixin):
    """Handles post-simulation tasks: waiting for results and reloading project."""

    def __init__(
        self,
        project_path: str,
        profiler: "Profiler",
        verbose_logger: "Logger",
        progress_logger: "Logger",
    ):
        """Initialize post-simulation handler.

        Args:
            project_path: Path to project file to reload.
            profiler: Profiler for timing subtasks.
            verbose_logger: Logger for verbose output.
            progress_logger: Logger for progress output.
        """
        self.project_path = project_path
        self.profiler = profiler
        self.verbose_logger = verbose_logger
        self.progress_logger = progress_logger
        import s4l_v1.document

        self.document = s4l_v1.document

    def wait_and_reload(self) -> None:
        """Wait for results and reload project.

        Waits 5 seconds for results to be written, then closes and reopens
        the project to load results into Sim4Life.
        """
        self._log(
            "    - Wait for results...",
            level="progress",
            log_type="progress",
        )
        with self.profiler.subtask("run_wait_for_results"):
            non_blocking_sleep(5)
        elapsed = self.profiler.subtask_times["run_wait_for_results"][-1]
        self._log(f"      - Subtask 'run_wait_for_results' done in {elapsed:.2f}s", log_type="verbose")
        self._log(f"      - Done in {elapsed:.2f}s", level="progress", log_type="success")

        self._log(
            "    - Reload project...",
            level="progress",
            log_type="progress",
        )
        with self.profiler.subtask("run_reload_project"):
            self.document.Close()
            open_project(self.project_path)
        elapsed = self.profiler.subtask_times["run_reload_project"][-1]
        self._log(f"      - Subtask 'run_reload_project' done in {elapsed:.2f}s", log_type="verbose")
        self._log(f"      - Done in {elapsed:.2f}s", level="progress", log_type="success")

        self._log(
            "Project reloaded and results are available.",
            log_type="success",
        )
