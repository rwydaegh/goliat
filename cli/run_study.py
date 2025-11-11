import argparse
import logging
import multiprocessing
import os
import platform
import sys
import traceback
from typing import Optional


from goliat.utils.setup import initial_setup

# --- Pre-check and Setup ---
# Only run initial_setup if not in test/CI environment
if not os.environ.get("PYTEST_CURRENT_TEST") and not os.environ.get("CI"):
    initial_setup()

try:
    from PySide6.QtWidgets import QApplication
except ImportError:
    # In the cloud, the python executable is not in a path containing "Sim4Life", but we can detect the OS.
    is_sim4life_interpreter = "Sim4Life" in sys.executable or "aws" in platform.release()

    # Don't exit during test collection or CI - let tests handle missing PySide6
    if os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("CI"):
        QApplication = None  # Set to None so tests can mock it
    else:
        print("=" * 80)
        print("ERROR: Could not start the application.")

        if not is_sim4life_interpreter:
            print("You are not using a Sim4Life Python interpreter.")
            print("Please ensure you are using the Python executable from your Sim4Life installation.")
            print("See the documentation for instructions on how to set up your environment.")
        else:
            print("Critical dependencies are missing.")
            print("This can happen if you haven't installed the project dependencies.")
            print("Attempting to install now...")
            print("=" * 80)
            try:
                # Fallback: Try to install the package (only for initial setup phase)
                # This is only reached if PySide6 is missing before initial_setup() completes
                # Get project root (go up from cli to repo root)
                base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
                import subprocess

                print("\nInstalling GOLIAT package and dependencies...")
                subprocess.check_call([sys.executable, "-m", "pip", "install", "-e", base_dir])
                print("\nDependencies installed. Restarting the script...")
                # Restart the script to ensure new packages are loaded
                executable = f'"{sys.executable}"' if " " in sys.executable else sys.executable
                os.execv(executable, [executable] + sys.argv)
            except Exception as e:
                print(f"\nFailed to install dependencies automatically: {e}")
                print("Please run the following command in your terminal:")
                print(f"   {sys.executable} -m pip install -e .")

        print("=" * 80)
        sys.exit(1)
# --- End Pre-check ---

from goliat.config import Config  # noqa: E402
from goliat.logging_manager import LoggingMixin, setup_loggers, shutdown_loggers  # noqa: E402
from goliat.studies.base_study import StudyCancelledError  # noqa: E402

# Import GUI components - will be None if PySide6 not available
from goliat.gui_manager import ProgressGUI, QueueGUI  # noqa: E402

# Only import osparc batch runner if GUI is available (it requires PySide6)
if QApplication is not None:
    from goliat.osparc_batch.runner import main as run_osparc_batch  # noqa: E402
else:
    # Mock function for CI/test environments
    def run_osparc_batch(config_filename):
        raise RuntimeError("oSPARC batch execution requires PySide6 and is not available in CI/test environments")


# Base directory for config files
from cli.utils import get_base_dir

base_dir = get_base_dir()


class ConsoleLogger(LoggingMixin):
    """Minimal console logger for headless environments (no GUI available)."""

    def __init__(self, progress_logger: logging.Logger, verbose_logger: logging.Logger) -> None:
        """Initializes the ConsoleLogger.

        Args:
            progress_logger: Logger for progress messages.
            verbose_logger: Logger for detailed messages.
        """
        super().__init__()
        self.progress_logger: logging.Logger = progress_logger
        self.verbose_logger: logging.Logger = verbose_logger
        self.last_sim_count: int = 0
        self.current_stage: Optional[str] = None

    def _format_box(self, message: str, log_type: str = "default") -> str:
        """Formats message in a colored box with dashes.

        Args:
            message: Message text.
            log_type: Log type for color selection.

        Returns:
            Formatted string with borders and color codes.
        """
        from colorama import Style

        from goliat.colors import get_color

        color = get_color(log_type)
        border = "-" * 70
        return f"\n{color}{border}\n{message}\n{border}{Style.RESET_ALL}\n"

    def log(self, message: str, level: str = "verbose", log_type: str = "default") -> None:
        """Logs message to appropriate logger.

        Args:
            message: Log message text.
            level: Log level (only "progress" shown prominently).
            log_type: Log type for color coding.
        """
        if level == "progress":
            self.progress_logger.info(message)
        else:
            self.verbose_logger.info(message)

    def update_simulation_details(self, sim_count: int, total_sims: int, details: str) -> None:
        """Shows simulation details in formatted box.

        Args:
            sim_count: Current simulation number.
            total_sims: Total number of simulations.
            details: Description of current simulation case.
        """
        if sim_count != self.last_sim_count:
            self.last_sim_count = sim_count
            percent = (sim_count / total_sims * 100) if total_sims > 0 else 0
            message = f"Simulation {sim_count}/{total_sims} ({percent:.1f}%)\n{details}"
            formatted = self._format_box(message, "header")
            self.progress_logger.info(formatted)

    def update_overall_progress(self, current_step: int, total_steps: int) -> None:
        """Shows overall progress at key milestones.

        Args:
            current_step: Current step number.
            total_steps: Total number of steps.
        """
        if total_steps > 0:
            percent = current_step / total_steps * 100
            # Only show at 25%, 50%, 75%, 100% milestones
            if int(percent) in [25, 50, 75] or current_step == total_steps:
                message = f"Overall Progress: {current_step}/{total_steps} ({percent:.1f}%)"
                formatted = self._format_box(message, "progress")
                self.progress_logger.info(formatted)

    def update_stage_progress(self, stage_name: str, current_step: int, total_steps: int, sub_stage: str = "") -> None:
        """Shows stage completion only (not intermediate progress).

        Args:
            stage_name: Name of the stage.
            current_step: Current step within stage.
            total_steps: Total steps for the stage.
            sub_stage: Optional sub-stage description (unused).
        """
        if current_step == total_steps and total_steps > 0:
            # Stage completed
            if stage_name != self.current_stage:
                self.current_stage = stage_name
                message = f"✓ {stage_name} Complete"
                formatted = self._format_box(message, "success")
                self.progress_logger.info(formatted)

    def start_stage_animation(self, task_name: str, end_value: int) -> None:
        """No-op for console mode.

        Args:
            task_name: Task name (unused).
            end_value: End value (unused).
        """
        pass

    def end_stage_animation(self) -> None:
        """No-op for console mode."""
        pass

    def update_profiler(self) -> None:
        """No-op for console mode."""
        pass

    def process_events(self) -> None:
        """No-op for console mode."""
        pass

    def fatal_error(self, message: str) -> None:
        """Shows fatal error in formatted box.

        Args:
            message: Error message text.
        """
        formatted = self._format_box(f"FATAL ERROR: {message}", "fatal")
        self.progress_logger.error(formatted)

    def is_stopped(self) -> bool:
        """Checks if stop has been requested.

        Returns:
            Always False (no GUI to stop from).
        """
        return False


def study_process_wrapper(queue, stop_event, config_filename, process_id, no_cache=False):
    """
    This function runs in a separate process to execute the study.
    It sets up its own loggers and communicates with the main GUI process via a queue
    and a stop event.
    """
    # Each process needs to set up its own loggers.
    progress_logger, verbose_logger, _ = setup_loggers(process_id=process_id)

    try:
        from goliat.config import Config
        from goliat.profiler import Profiler
        from goliat.studies.far_field_study import FarFieldStudy
        from goliat.studies.near_field_study import NearFieldStudy

        config = Config(base_dir, config_filename, no_cache=no_cache)
        study_type = config["study_type"]

        profiling_config_data = config.get_profiling_config(study_type)
        profiler = Profiler(
            execution_control=config["execution_control"] or {},
            profiling_config=profiling_config_data,
            study_type=study_type,
            config_path=config.profiling_config_path,
        )

        # The study will use the QueueGUI to send updates back to the main process.
        # Fallback to ConsoleLogger if GUI not available (CI/test environments)
        if QueueGUI is None:
            gui_proxy = ConsoleLogger(progress_logger, verbose_logger)
        else:
            gui_proxy = QueueGUI(queue, stop_event, profiler, progress_logger, verbose_logger)

        if study_type == "near_field":
            study = NearFieldStudy(study_type="near_field", config_filename=config_filename, gui=gui_proxy, no_cache=no_cache)
        elif study_type == "far_field":
            study = FarFieldStudy(study_type="far_field", config_filename=config_filename, gui=gui_proxy, no_cache=no_cache)
        else:
            raise ValueError(f"Unknown or missing study type '{study_type}' in {config_filename}")

        study.profiler = profiler
        study.run()

    except StudyCancelledError:
        progress_logger.info("--- Study manually stopped by user ---")
        queue.put({"type": "status", "message": "Study stopped by user."})
    except Exception as e:
        # Log the fatal error and send it to the GUI
        error_msg = f"FATAL ERROR in study process: {e}"
        progress_logger.error(error_msg)

        # Explicitly log the traceback to the verbose logger
        tb_str = traceback.format_exc()
        verbose_logger.error(f"Traceback:\n{tb_str}")

        queue.put({"type": "fatal_error", "message": str(e)})
    finally:
        # Signal that the process is finished
        queue.put({"type": "finished"})
        shutdown_loggers()


def main():
    """
    Main entry point for running a study.
    It launches the GUI in the main process and the study in a separate process.
    """
    parser = argparse.ArgumentParser(description="Run a dosimetric assessment study.")
    parser.add_argument(
        "config",
        type=str,
        nargs="?",
        default="near_field_config",
        help="Path or name of the configuration file (e.g., todays_far_field or configs/near_field_config.json).",
    )
    parser.add_argument(
        "--title",
        type=str,
        default="",
        help="Set the title of the GUI window.",
    )
    parser.add_argument("--pid", type=str, default=None, help="The process ID for logging.")
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="If set, redo simulations even if the configuration matches a completed run.",
    )
    args = parser.parse_args()
    config_filename = args.config
    process_id = args.pid

    # Clean up any stale lock files before starting
    lock_files = [f for f in os.listdir(base_dir) if f.endswith(".lock")]
    for lock_file in lock_files:
        lock_file_path = os.path.join(base_dir, lock_file)
        if lock_file != "uv.lock":
            try:
                os.remove(lock_file_path)
                print(f"Removed stale lock file: {lock_file_path}")
            except OSError as e:
                print(f"Error removing stale lock file {lock_file_path}: {e}")

    # The main process only needs a minimal logger setup for the GUI.
    progress_logger, verbose_logger, _ = setup_loggers(process_id=process_id)

    config = Config(base_dir, config_filename)
    execution_control = config["execution_control"] or {}
    use_gui = config["use_gui"]
    if use_gui is None:
        use_gui = True

    if execution_control.get("batch_run"):
        run_osparc_batch(config_filename)
    elif use_gui:
        # Check if GUI is available
        if QApplication is None or ProgressGUI is None:
            # Fallback to console mode if GUI not available
            progress_logger.info("GUI not available, running in console mode...")
            use_gui = False
        else:
            # Use spawn context for compatibility across platforms
            ctx = multiprocessing.get_context("spawn")
            queue = ctx.Queue()
            stop_event = ctx.Event()

            # Create and start the study process
            study_process = ctx.Process(
                target=study_process_wrapper,
                args=(queue, stop_event, config_filename, process_id, args.no_cache),
            )
            study_process.start()

            # The GUI runs in the main process
            app = QApplication(sys.argv)
            gui = ProgressGUI(queue, stop_event, study_process, init_window_title=args.title)
            gui.show()

            app.exec()

            # Ensure the study process is cleaned up
            if study_process.is_alive():
                study_process.terminate()
                study_process.join()
    else:
        try:
            from goliat.profiler import Profiler
            from goliat.studies.far_field_study import FarFieldStudy
            from goliat.studies.near_field_study import NearFieldStudy

            study_type = config["study_type"]

            profiling_config_data = config.get_profiling_config(study_type)
            profiler = Profiler(
                execution_control=config["execution_control"] or {},
                profiling_config=profiling_config_data,
                study_type=study_type,
                config_path=config.profiling_config_path,
            )

            console_logger = ConsoleLogger(progress_logger, verbose_logger)

            if study_type == "near_field":
                study = NearFieldStudy(study_type="near_field", config_filename=config_filename, gui=console_logger, no_cache=args.no_cache)
            elif study_type == "far_field":
                study = FarFieldStudy(study_type="far_field", config_filename=config_filename, gui=console_logger, no_cache=args.no_cache)
            else:
                raise ValueError(f"Unknown or missing study type '{study_type}' in {config_filename}")

            study.profiler = profiler
            study.run()

        except StudyCancelledError:
            progress_logger.info("--- Study manually stopped by user ---")
        except Exception as e:
            error_msg = f"FATAL ERROR in study process: {e}"
            progress_logger.error(error_msg)
            tb_str = traceback.format_exc()
            verbose_logger.error(f"Traceback:\n{tb_str}")
            print(error_msg)
            print(f"Traceback:\n{tb_str}")
        finally:
            shutdown_loggers()


if __name__ == "__main__":
    # This is crucial for multiprocessing to work correctly on Windows
    multiprocessing.freeze_support()
    main()
