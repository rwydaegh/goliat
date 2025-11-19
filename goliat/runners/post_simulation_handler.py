"""Post-simulation handling for waiting and reloading projects."""

import gc
from typing import TYPE_CHECKING

try:
    import psutil
except ImportError:
    psutil = None  # type: ignore

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
        the project to load results into Sim4Life. Only reloads if memory
        usage is above 60% to free memory.
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

        # Check memory usage and reload only if above threshold
        should_reload = False
        if psutil is not None:
            try:
                memory = psutil.virtual_memory()
                memory_percent = memory.percent
                if memory_percent > 60.0:
                    should_reload = True
                    self._log(
                        f"    - Memory usage at {memory_percent:.1f}%, reloading project to free memory...",
                        level="progress",
                        log_type="progress",
                    )
            except Exception:
                # If memory check fails, reload anyway to be safe
                should_reload = True
        else:
            # If psutil not available, reload anyway
            should_reload = True

        if should_reload:
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

            # Force garbage collection after reload to free memory
            gc.collect()

            self._log(
                "Project reloaded and results are available.",
                log_type="success",
            )
        else:
            self._log(
                "Memory usage acceptable, skipping reload.",
                log_type="verbose",
            )
