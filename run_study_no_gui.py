import os
import sys
import argparse
import traceback

# Ensure the src directory is in the Python path
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__)))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

# --- Early Startup: Install Dependencies ---
from src.startup import check_and_install_packages
check_and_install_packages(os.path.join(base_dir, 'requirements.txt'))
# --- End Early Startup ---

from src.logging_manager import setup_loggers, shutdown_loggers
from src.startup import run_full_startup
from src.studies.base_study import StudyCancelledError
from src.config import Config
from src.osparc_batch.runner import main as run_osparc_batch

class ConsoleLogger:
    """A console-based logger to substitute for the GUI."""
    def __init__(self, progress_logger, verbose_logger):
        self.progress_logger = progress_logger
        self.verbose_logger = verbose_logger

    def log(self, message, level='verbose', log_type='default'):
        if level == 'progress':
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
        return False # No GUI to stop it

def main():
    """
    Main entry point for running a study without a GUI.
    """
    parser = argparse.ArgumentParser(description="Run a dosimetric assessment study without a GUI.")
    parser.add_argument('--config', type=str, default="configs/todays_far_field_config.json", help='Path to the configuration file.')
    parser.add_argument('--pid', type=str, default=None, help='The process ID for logging.')
    args = parser.parse_args()
    config_filename = args.config
    process_id = args.pid

    # Clean up any stale lock files
    lock_files = [f for f in os.listdir(base_dir) if f.endswith('.lock')]
    for lock_file in lock_files:
        lock_file_path = os.path.join(base_dir, lock_file)
        try:
            os.remove(lock_file_path)
            print(f"Removed stale lock file: {lock_file_path}")
        except OSError as e:
            print(f"Error removing stale lock file {lock_file_path}: {e}")

    progress_logger, verbose_logger, _ = setup_loggers(process_id=process_id)

    try:
        config = Config(base_dir, config_filename)
        execution_control = config.get_setting('execution_control', {})

        if execution_control.get('batch_run'):
            run_osparc_batch(config_filename)
            return

        from src.studies.near_field_study import NearFieldStudy
        from src.studies.far_field_study import FarFieldStudy
        from src.profiler import Profiler

        run_full_startup(base_dir)
        
        study_type = config.get_setting('study_type')
        
        profiling_config_data = config.get_profiling_config(study_type)
        profiler = Profiler(
            execution_control=config.get_setting('execution_control'),
            profiling_config=profiling_config_data,
            study_type=study_type,
            config_path=config.profiling_config_path
        )

        console_logger = ConsoleLogger(progress_logger, verbose_logger)

        if study_type == 'near_field':
            study = NearFieldStudy(config_filename=config_filename, gui=console_logger)
        elif study_type == 'far_field':
            study = FarFieldStudy(config_filename=config_filename, gui=console_logger)
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

if __name__ == '__main__':
    main()