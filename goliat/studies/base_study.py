import contextlib
import importlib
import io
import logging
import os
import traceback
from typing import TYPE_CHECKING, Optional

from line_profiler import LineProfiler

try:
    import requests

    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    requests = None  # type: ignore

from goliat.config import Config
from goliat.logging_manager import LoggingMixin
from goliat.profiler import Profiler
from goliat.project_manager import ProjectManager
from goliat.simulation_runner import SimulationRunner
from goliat.utils import StudyCancelledError, ensure_s4l_running

if TYPE_CHECKING:
    from ..gui_manager import QueueGUI


class BaseStudy(LoggingMixin):
    """Base class for simulation studies.

    Handles common setup like config loading, profiling, project management,
    and GUI coordination. Subclasses implement _run_study() for specific logic.
    """

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

        # Determine base_dir: prefer cwd if it has configs/, otherwise fallback to package location
        cwd = os.getcwd()
        if os.path.isdir(os.path.join(cwd, "configs")):
            self.base_dir = cwd
        else:
            # Fallback: calculate from package location (for backwards compatibility)
            self.base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

        self.config = Config(
            self.base_dir,
            config_filename if config_filename else f"{self.study_type}_config.json",
        )

        # Get study-specific profiling config
        profiling_config = self.config.get_profiling_config(self.study_type)
        execution_control = self.config["execution_control"] or {"do_setup": True, "do_run": True, "do_extract": True}

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
        is_top_level_subtask = not self.profiler.subtask_stack
        sub_stage_display_name = task_name.replace("_", " ").capitalize()

        if is_top_level_subtask:
            self._log(f"  - {sub_stage_display_name}...", level="progress", log_type="progress")
            if self.gui and self.profiler.current_phase:
                self.gui.update_stage_progress(self.profiler.current_phase.capitalize(), 0, 1, sub_stage=sub_stage_display_name)
                self.start_stage_animation(task_name, 100)

        lp, wrapper = self._setup_line_profiler_if_needed(task_name, instance_to_profile)

        try:
            with self.profiler.subtask(task_name):
                if lp and wrapper:
                    yield wrapper
                else:
                    yield
        finally:
            elapsed = self.profiler.subtask_times[task_name][-1]
            self._log(f"    - Subtask '{task_name}' done in {elapsed:.2f}s", log_type="verbose")

            if is_top_level_subtask:
                self._log(f"    - Done in {elapsed:.2f}s", level="progress", log_type="success")
                if self.gui:
                    self.end_stage_animation()
                    if self.profiler.current_phase:
                        self.gui.update_stage_progress(self.profiler.current_phase.capitalize(), 1, 1)

            if lp:
                self._log_line_profiler_stats(task_name, lp)

    def start_stage_animation(self, task_name: str, end_value: int):
        """Starts progress bar animation for the current stage."""
        if self.gui:
            self.gui.start_stage_animation(task_name, end_value)

    def end_stage_animation(self):
        """Stops the current stage animation."""
        if self.gui:
            self.gui.end_stage_animation()

    def run(self):
        """Main entry point to run the study.

        Ensures Sim4Life is running, calls _run_study(), and handles cleanup
        and error reporting. Catches StudyCancelledError for graceful shutdown.
        """
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
        """Executes the study logic. Must be implemented by subclasses.

        Raises:
            NotImplementedError: If not overridden by subclass.
        """

    def _execute_run_phase(self, simulation):
        """Runs a simulation with consistent GUI updates and profiling.

        Creates a SimulationRunner and executes it, then updates metadata
        to mark the run phase as complete.

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

    def _verify_run_deliverables_before_extraction(self) -> bool:
        """Verifies that run deliverables exist before starting extraction.

        This method checks if the run phase has actually completed by verifying
        that the expected output files (*_Output.h5) exist and are valid.
        This prevents attempting extraction when run phase hasn't completed or
        its deliverables were deleted.

        Returns:
            True if run deliverables exist and are valid, False otherwise.
        """
        if not self.project_manager.project_path:
            self._log(
                "WARNING: Cannot verify run deliverables - project path not set.",
                level="progress",
                log_type="warning",
            )
            return False

        project_dir = os.path.dirname(self.project_manager.project_path)
        project_filename = os.path.basename(self.project_manager.project_path)
        meta_path = os.path.join(project_dir, "config.json")

        # Get setup timestamp from metadata
        setup_timestamp = self.project_manager.get_setup_timestamp_from_metadata(meta_path)
        if setup_timestamp is None:
            # If no timestamp available, use 0 to check for existence only
            self._log(
                "WARNING: Could not get setup timestamp from metadata. Checking for file existence only.",
                log_type="warning",
            )
            setup_timestamp = 0

        # Check deliverables status
        deliverables_status = self.project_manager._get_deliverables_status(project_dir, project_filename, setup_timestamp)

        if not deliverables_status["run_done"]:
            self._log(
                "WARNING: Run deliverables not found. Cannot proceed with extraction. "
                "The run phase must complete successfully before extraction can start.",
                level="progress",
                log_type="warning",
            )
            return False

        self._log("Run deliverables verified. Proceeding with extraction.", log_type="info")
        return True

    def _verify_and_update_metadata(self, stage: str):
        """Updates metadata after a stage completes if deliverables are found.

        Checks for deliverable files on disk and updates the metadata file
        accordingly. This helps the verify-and-resume feature work correctly.

        Args:
            stage: Stage name ('run' or 'extract').
        """
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
            # Upload results if running as part of an assignment
            self._upload_results_if_assignment(project_dir)
        else:
            self._log(f"Deliverables for '{stage}' phase not found. Metadata not updated.", log_type="warning")

    def _upload_results_if_assignment(self, project_dir: str):
        """Upload results to web dashboard if running as part of an assignment.

        Collects deliverable files and uploads them to the monitoring dashboard.
        Only runs if GOLIAT_ASSIGNMENT_ID environment variable is set.

        Args:
            project_dir: Path to the simulation results directory
        """
        assignment_id = os.environ.get("GOLIAT_ASSIGNMENT_ID", "")
        if not assignment_id:
            return  # Not running as part of an assignment

        if not REQUESTS_AVAILABLE or requests is None:
            self._log("WARNING: requests library not available, cannot upload results", log_type="warning")
            return

        # Get monitoring server URL from environment (set by run_worker.py)
        server_url = "https://goliat.waves-ugent.be"

        self._log("Uploading results to web dashboard...", log_type="info")

        # Define files to upload with their expected names
        files_to_upload = [
            "config.json",
            "verbose.log",
            "progress.log",
            "sar_results.json",
            "sar_stats_all_tissues.pkl",
            "sar_stats_all_tissues.html",
        ]

        # Collect files that exist
        files = {}
        for filename in files_to_upload:
            file_path = os.path.join(project_dir, filename)
            if os.path.exists(file_path):
                try:
                    with open(file_path, "rb") as f:
                        files[filename] = f.read()
                except Exception as e:
                    self._log(f"WARNING: Could not read {filename}: {e}", log_type="warning")

        if not files:
            self._log("WARNING: No result files found to upload", log_type="warning")
            return

        # Get relative path from results/ root for directory structure
        # Example: results/near_field/thelonious/700MHz/by_belly_up_vertical
        # Should extract: near_field/thelonious/700MHz/by_belly_up_vertical
        # Find the results/ directory in the path
        if "results" + os.sep in project_dir or "results" + os.altsep in project_dir:
            # Extract path after results/
            parts = project_dir.split("results" + os.sep, 1)
            if len(parts) > 1:
                relative_path = parts[1]
            else:
                # Try with altsep (Windows)
                parts = project_dir.split("results" + os.altsep, 1)
                relative_path = parts[1] if len(parts) > 1 else ""
        else:
            # Fallback: try to find results directory by going up
            results_root = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(project_dir)))), "results")
            try:
                relative_path = os.path.relpath(project_dir, results_root)
                # Remove leading ..\ or ../ if present
                if relative_path.startswith(".." + os.sep) or relative_path.startswith(".." + os.altsep):
                    relative_path = relative_path[3:]
            except ValueError:
                relative_path = ""

        # Normalize path separators to forward slashes for cross-platform compatibility
        relative_path = relative_path.replace(os.sep, "/").replace(os.altsep, "/")

        # Upload files
        try:
            # Prepare multipart form data
            upload_files = []
            for filename, content in files.items():
                upload_files.append(("files", (filename, content)))

            response = requests.post(  # type: ignore[attr-defined]
                f"{server_url}/api/assignments/{assignment_id}/results",
                files=upload_files,
                data={"relativePath": relative_path},
                timeout=30,
            )

            if response.status_code == 200:
                self._log(f"Results uploaded successfully ({len(files)} files)", log_type="success")
            else:
                self._log(f"WARNING: Results upload failed (status {response.status_code}): {response.text[:100]}", log_type="warning")
        except Exception as e:
            self._log(f"WARNING: Error uploading results: {e}", log_type="warning")

    def _setup_line_profiler_if_needed(self, subtask_name: str, instance) -> tuple:
        """Sets up line profiler if configured for this subtask.

        Checks config to see if line profiling is enabled for this subtask
        and if so, wraps specified methods for profiling.

        Args:
            subtask_name: Name of the subtask to check config for.
            instance: Object to profile (needed to get method references).

        Returns:
            Tuple of (LineProfiler instance, wrapper function) or (None, None).
        """
        line_profiling_config = self.config["line_profiling"] or {}
        if not (instance and line_profiling_config.get("enabled", False) and subtask_name in line_profiling_config.get("subtasks", {})):
            return None, None

        self._log(f"    - Activating line profiler for subtask: {subtask_name}", "verbose", "verbose")
        lp = LineProfiler()
        functions_to_profile = line_profiling_config["subtasks"][subtask_name]
        for func_path in functions_to_profile:
            try:
                module_path, class_name, func_name = func_path.rsplit(".", 2)
                module = importlib.import_module(module_path)
                class_obj = getattr(module, class_name)
                func_to_add = getattr(class_obj, func_name)
                self._log(f"    - Adding function to profiler: {class_name}.{func_name} from {module_path}", log_type="verbose")
                lp.add_function(func_to_add)
            except (ImportError, AttributeError, ValueError) as e:
                self._log(
                    f"  - WARNING: Could not find or parse function '{func_path}' for line profiling. Error: {e}",
                    level="progress",
                    log_type="warning",
                )
        return lp, lp.wrap_function

    def _log_line_profiler_stats(self, task_name: str, lp: LineProfiler):
        """Logs line profiler statistics for a completed subtask."""
        self._log(f"      - Line profiler stats for '{task_name}':", "verbose", "verbose")
        s = io.StringIO()
        lp.print_stats(stream=s)
        self.verbose_logger.info(s.getvalue())
