import argparse
import multiprocessing
import os
import sys
import traceback


def initial_setup():
    """
    Performs all initial checks and setup procedures.
    - Ensures correct python interpreter is used.
    - Installs dependencies if missing.
    - Prepares data files.
    """
    # Temporarily add scripts to path to find utils
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__)))
    scripts_dir = os.path.join(base_dir, "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)

    from utils import (
        check_python_interpreter,
        check_repo_root,
        install_requirements,
        prepare_data,
    )

    data_dir = os.path.join(os.getcwd(), "data")
    os.makedirs(data_dir, exist_ok=True)
    lock_file = os.path.join(data_dir, ".setup_done")

    if not os.path.exists(lock_file):
        check_repo_root()
        check_python_interpreter()
        install_requirements(os.path.join(os.getcwd(), "requirements.txt"))
        prepare_data(os.getcwd())
        with open(lock_file, "w") as f:
            f.write("Setup complete.")
    else:
        check_python_interpreter()


# --- Pre-check and Setup ---
initial_setup()

try:
    from PySide6.QtWidgets import QApplication
except ImportError:
    is_sim4life_interpreter = "Sim4Life" in sys.executable
    print("=" * 80)
    print("ERROR: Could not start the application.")

    if not is_sim4life_interpreter:
        print("You are not using a Sim4Life Python interpreter.")
        print("Please ensure you are using the Python executable from your Sim4Life installation.")
        print("See the documentation for instructions on how to set up your environment.")
    else:
        print("Critical dependencies are missing.")
        print("This can happen if you haven't installed the project requirements.")
        print("Attempting to install now...")
        print("=" * 80)
        try:
            # Temporarily add scripts to path to find utils
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__)))
            scripts_dir = os.path.join(base_dir, "scripts")
            if scripts_dir not in sys.path:
                sys.path.insert(0, scripts_dir)
            from utils import install_requirements

            install_requirements(os.path.join(base_dir, "requirements.txt"))
            print("\nDependencies installed. Restarting the script...")
            # Restart the script to ensure new packages are loaded
            executable = f'"{sys.executable}"' if " " in sys.executable else sys.executable
            os.execv(executable, [executable] + sys.argv)
        except Exception as e:
            print(f"\nFailed to install dependencies automatically: {e}")
            print("Please run the following command in your terminal:")
            print(f"   {sys.executable} -m pip install -r requirements.txt")

    print("=" * 80)
    sys.exit(1)
# --- End Pre-check ---

from src.config import Config  # noqa: E402
from src.gui_manager import ProgressGUI, QueueGUI  # noqa: E402
from src.logging_manager import setup_loggers, shutdown_loggers  # noqa: E402
from src.osparc_batch.runner import main as run_osparc_batch  # noqa: E402
from src.studies.base_study import StudyCancelledError  # noqa: E402

# Ensure the src directory is in the Python path
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__)))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)


class ConsoleLogger:
    """A console-based logger to substitute for the GUI."""

    def __init__(self, progress_logger, verbose_logger):
        self.progress_logger = progress_logger
        self.verbose_logger = verbose_logger

    def log(self, message, level="verbose", log_type="default"):
        if level == "progress":
            self.progress_logger.info(message)
        else:
            self.verbose_logger.info(message)

    def update_overall_progress(self, current_step, total_steps):
        self.progress_logger.info(f"Overall Progress: {current_step}/{total_steps}")

    def update_stage_progress(self, stage_name, current_step, total_steps):
        self.progress_logger.info(f"Stage '{stage_name}': {current_step}/{total_steps}")

    def start_stage_animation(self, task_name, end_value):
        self.progress_logger.info(f"Starting: {task_name}")

    def end_stage_animation(self):
        pass

    def update_profiler(self):
        pass

    def fatal_error(self, message):
        self.progress_logger.error(f"FATAL ERROR: {message}")

    def is_stopped(self):
        return False  # No GUI to stop it


def study_process_wrapper(queue, stop_event, config_filename, process_id, no_cache=False):
    """
    This function runs in a separate process to execute the study.
    It sets up its own loggers and communicates with the main GUI process via a queue
    and a stop event.
    """
    # Each process needs to set up its own loggers.
    progress_logger, verbose_logger, _ = setup_loggers(process_id=process_id)

    try:
        from src.config import Config
        from src.profiler import Profiler
        from src.studies.far_field_study import FarFieldStudy
        from src.studies.near_field_study import NearFieldStudy

        config = Config(base_dir, config_filename, no_cache=no_cache)
        study_type = config.get_setting("study_type")

        profiling_config_data = config.get_profiling_config(study_type)
        profiler = Profiler(
            execution_control=config.get_setting("execution_control"),
            profiling_config=profiling_config_data,
            study_type=study_type,
            config_path=config.profiling_config_path,
        )

        # The study will use the QueueGUI to send updates back to the main process.
        gui_proxy = QueueGUI(queue, stop_event, profiler, progress_logger, verbose_logger)

        if study_type == "near_field":
            study = NearFieldStudy(config_filename=config_filename, gui=gui_proxy, no_cache=no_cache)
        elif study_type == "far_field":
            study = FarFieldStudy(config_filename=config_filename, gui=gui_proxy, no_cache=no_cache)
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
        default="Simulation Progress",
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
    execution_control = config.get_setting("execution_control", {})
    use_gui = config.get_setting("use_gui", True)

    if execution_control.get("batch_run"):
        run_osparc_batch(config_filename)
    elif use_gui:
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
        gui = ProgressGUI(queue, stop_event, study_process, window_title=args.title)
        gui.show()

        app.exec()

        # Ensure the study process is cleaned up
        if study_process.is_alive():
            study_process.terminate()
            study_process.join()
    else:
        try:
            from src.profiler import Profiler
            from src.studies.far_field_study import FarFieldStudy
            from src.studies.near_field_study import NearFieldStudy

            study_type = config.get_setting("study_type")

            profiling_config_data = config.get_profiling_config(study_type)
            profiler = Profiler(
                execution_control=config.get_setting("execution_control"),
                profiling_config=profiling_config_data,
                study_type=study_type,
                config_path=config.profiling_config_path,
            )

            console_logger = ConsoleLogger(progress_logger, verbose_logger)

            if study_type == "near_field":
                study = NearFieldStudy(config_filename=config_filename, gui=console_logger, no_cache=args.no_cache)
            elif study_type == "far_field":
                study = FarFieldStudy(config_filename=config_filename, gui=console_logger, no_cache=args.no_cache)
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
