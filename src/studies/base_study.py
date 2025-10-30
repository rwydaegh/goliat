import contextlib
import importlib
import io
import logging
import os
import traceback
from typing import TYPE_CHECKING, Optional

from line_profiler import LineProfiler

from src.config import Config
from src.logging_manager import LoggingMixin
from src.profiler import Profiler
from src.project_manager import ProjectManager
from src.simulation_runner import SimulationRunner
from src.utils import StudyCancelledError, ensure_s4l_running

if TYPE_CHECKING:
    from ..gui_manager import QueueGUI


class BaseStudy(LoggingMixin):
    """Abstract base class for all studies."""

    def __init__(
        self,
        study_type: str,
        config_filename: Optional[str] = None,
        gui: Optional["QueueGUI"] = None,
        profiler=None,
        no_cache: bool = False,
    ):
        self.study_type = study_type
        self.gui = gui
        self.verbose_logger = logging.getLogger("verbose")
        self.progress_logger = logging.getLogger("progress")
        self.no_cache = no_cache

        self.base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

        self.config = Config(
            self.base_dir,
            config_filename if config_filename else f"{self.study_type}_config.json",
        )

        # Get study-specific profiling config
        profiling_config = self.config.get_profiling_config(self.study_type)
        execution_control = self.config.get_setting("execution_control", {"do_setup": True, "do_run": True, "do_extract": True})

        self.profiler = Profiler(
            execution_control,  # type: ignore
            profiling_config,
            self.study_type,
            self.config.profiling_config_path,
        )
        self.line_profiler = None

        self.project_manager = ProjectManager(
            self.config,
            self.verbose_logger,
            self.progress_logger,
            self.gui,
            no_cache=self.no_cache,
        )

    def _check_for_stop_signal(self):
        """Checks if the GUI has requested a stop."""
        if self.gui and self.gui.is_stopped():
            raise StudyCancelledError("Study cancelled by user.")

    @contextlib.contextmanager
    def subtask(self, task_name: str, instance_to_profile=None):
        """A context manager for a 'subtask' within a phase."""
        sub_stage_display_name = task_name.replace("_", " ").capitalize()
        self._log(f"  - {sub_stage_display_name}...", level="progress", log_type="progress")
        if self.gui and self.profiler.current_phase:
            self.gui.update_stage_progress(
                self.profiler.current_phase.capitalize(), 0, 1, sub_stage=sub_stage_display_name
            )

        lp = None
        wrapper = None
        line_profiling_config = self.config.get_line_profiling_config()
        if instance_to_profile and line_profiling_config.get("enabled", False) and task_name in line_profiling_config.get("subtasks", {}):
            self._log(f"    - Activating line profiler for subtask: {task_name}", "verbose", "verbose")
            lp, wrapper = self._setup_line_profiler(task_name, instance_to_profile)

        try:
            with self.profiler.subtask(task_name):
                if lp and wrapper:
                    yield wrapper
                else:
                    yield lambda func: func
        finally:
            elapsed = self.profiler.subtask_times[task_name][-1]
            self._log(f"    - Subtask '{task_name}' done in {elapsed:.2f}s", log_type="verbose")
            self._log(f"    - Done in {elapsed:.2f}s", level="progress", log_type="success")
            if lp:
                self._log(f"      - Line profiler stats for '{task_name}':", "verbose", "verbose")
                s = io.StringIO()
                lp.print_stats(stream=s)
                self.verbose_logger.info(s.getvalue())

    def start_stage_animation(self, task_name: str, end_value: int):
        """Starts the GUI animation for a stage."""
        if self.gui:
            self._log(f"DEBUG: BaseStudy.start_stage_animation: task={task_name}, end_value={end_value}", level="progress")
            self.gui.start_stage_animation(task_name, end_value)

    def end_stage_animation(self):
        """Ends the GUI animation for a stage."""
        if self.gui:
            self._log("DEBUG: BaseStudy.end_stage_animation", level="progress")
            self.gui.end_stage_animation()

    def run(self):
        """Main method to run the study."""
        ensure_s4l_running()
        try:
            self._run_study()
        except StudyCancelledError:
            self._log(
                "--- Study execution cancelled by user. ---",
                level="progress",
                log_type="warning",
            )
        except Exception as e:
            self._log(f"--- FATAL ERROR in study: {e} ---", level="progress", log_type="fatal")
            self.verbose_logger.error(traceback.format_exc())
        finally:
            self._log(
                f"\n--- {self.__class__.__name__} Finished ---",
                level="progress",
                log_type="success",
            )
            self.profiler.save_estimates()
            self.project_manager.cleanup()
            if self.gui:
                self.gui.update_profiler()  # Send final profiler state

    def _run_study(self):
        """Executes the specific study. Must be implemented by subclasses."""
        raise NotImplementedError("The '_run_study' method must be implemented by a subclass.")

    def _execute_run_phase(self, simulation):
        """Executes the run phase with consistent GUI management and profiling.

        Args:
            simulation: The simulation object to run.
        """
        with self.subtask("run_simulation_total"):
            runner = SimulationRunner(
                self.config,
                self.project_manager.project_path,  # type: ignore
                simulation,
                self.profiler,
                self.verbose_logger,
                self.progress_logger,
                self.gui,
            )
            runner.run()

        self.profiler.complete_run_phase()
        self._verify_and_update_metadata("run")
        self.end_stage_animation()
        if self.gui:
            self.gui.update_stage_progress("Running Simulation", 1, 1)

    def _verify_and_update_metadata(self, stage: str):
        """Verifies deliverables for a stage and updates metadata if they exist."""
        if not self.project_manager.project_path:
            return

        project_dir = os.path.dirname(self.project_manager.project_path)
        project_filename = os.path.basename(self.project_manager.project_path)

        # We need a timestamp for the check, but it's only used to check if files are newer.
        # For this purpose, we can use a very old timestamp to just check for existence.
        # A more robust solution might involve getting the setup timestamp from the metadata.
        # However, for the purpose of updating after a run/extract, checking for existence is sufficient.
        creation_timestamp = 0

        deliverables_status = self.project_manager._get_deliverables_status(project_dir, project_filename, creation_timestamp)

        if stage == "run" and deliverables_status["run_done"]:
            self._log("Run deliverables verified. Updating metadata.", log_type="warning")
            self.project_manager.update_simulation_metadata(os.path.join(project_dir, "config.json"), run_done=True)
        elif stage == "extract" and deliverables_status["extract_done"]:
            self._log("Extract deliverables verified. Updating metadata.", log_type="warning")
            self.project_manager.update_simulation_metadata(os.path.join(project_dir, "config.json"), extract_done=True)
        else:
            self._log(f"Deliverables for '{stage}' phase not found. Metadata not updated.", log_type="warning")

    def _setup_line_profiler(self, subtask_name: str, instance) -> tuple:
        """Sets up the line profiler for a specific subtask if configured."""
        line_profiling_config = self.config.get_line_profiling_config()

        if not line_profiling_config.get("enabled", False) or subtask_name not in line_profiling_config.get("subtasks", {}):
            return None, lambda func: func

        self._log(
            f"  - Setting up line profiler for subtask: {subtask_name}",
            level="verbose",
            log_type="verbose",
        )

        lp = LineProfiler()
        functions_to_profile = line_profiling_config["subtasks"][subtask_name]

        for func_path in functions_to_profile:
            try:
                module_path, class_name, func_name = func_path.rsplit(".", 2)

                # Dynamically import the module and get the class
                module = importlib.import_module(module_path)
                class_obj = getattr(module, class_name)

                # Get the function object from the class
                func_to_add = getattr(class_obj, func_name)

                self._log(
                    f"    - Adding function to profiler: {class_name}.{func_name} from {module_path}",
                    log_type="verbose",
                )
                lp.add_function(func_to_add)

            except (ImportError, AttributeError, ValueError) as e:
                self._log(
                    f"  - WARNING: Could not find or parse function '{func_path}' for line profiling. Error: {e}",
                    level="progress",
                    log_type="warning",
                )

        return lp, lp.wrap_function
