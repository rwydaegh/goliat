import argparse
import os
import sys
import multiprocessing

# Ensure the project root directory is in the Python path
base_dir = os.path.dirname(os.path.abspath(__file__))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

from src.startup import run_full_startup
from src.logging_manager import setup_loggers, shutdown_loggers
from src.studies.far_field_study import FarFieldStudy
from src.studies.near_field_study import NearFieldStudy
from src.utils import ensure_s4l_running
import atexit

def main():
    """
    Main entry point for running simulation studies without the GUI.
    """
    parser = argparse.ArgumentParser(description="Run near-field or far-field simulation studies without a GUI.")
    parser.add_argument(
        '--skip-startup',
        action='store_true',
        help="Skip the startup checks for dependencies and data."
    )
    parser.add_argument(
        '--config',
        type=str,
        default=None,
        help="Path to a custom configuration file."
    )

    args = parser.parse_args()

    # Setup logging and ensure it's shut down on exit
    progress_logger, verbose_logger, main_log_file = setup_loggers()
    atexit.register(shutdown_loggers)

    # Run startup checks
    if not args.skip_startup:
        run_full_startup(base_dir)

    # Ensure Sim4Life is running
    ensure_s4l_running()

    config_filename = args.config if args.config else "todays_near_field_config.json"

    # A simple console-based logger to substitute for the GUI
    class ConsoleLogger:
        def log(self, message, level='verbose'):
            if level == 'progress':
                progress_logger.info(message)
                print(message)
            else:
                verbose_logger.info(message)

        def update_overall_progress(self, current_step, total_steps):
            pass  # Not implemented for console

        def update_stage_progress(self, stage_name, current_step, total_steps):
            pass  # Not implemented for console
            
        def start_stage_animation(self, task_name, end_value):
            pass

        def end_stage_animation(self):
            pass

        def update_profiler(self):
            pass # Not implemented for console

        def update_profiler(self):
            pass # Not implemented for console

    from src.config import Config
    config = Config(base_dir, config_filename=config_filename)
    study_type = config.get_setting('study_type')

    if study_type == 'near_field':
        study = NearFieldStudy(config_filename=config_filename, gui=ConsoleLogger())
        # Manually set up the project path for the no-gui version
        phantom_name = config.get_setting('phantoms')[0]
        frequency_mhz = list(config.get_setting('antenna_config').keys())[0]
        # A placement name is required for near-field studies
        placement_name = "front_of_eyes_center_vertical" # A default, adjust if needed
        study.project_manager.create_or_open_project(phantom_name, frequency_mhz, placement_name)
    elif study_type == 'far_field':
        study = FarFieldStudy(config_filename=config_filename, gui=ConsoleLogger())
        # Manually set up the project path for the no-gui version
        phantom_name = config.get_setting('phantoms')[0]
        frequency_mhz = config.get_setting('frequencies_mhz')[0]
        study.project_manager.create_or_open_project(phantom_name, frequency_mhz)
    else:
        print(f"Error: Unknown or missing study type '{study_type}' in {config_filename}")
        return

    study.run()

if __name__ == "__main__":
    # This is crucial for multiprocessing to work correctly on Windows
    multiprocessing.freeze_support()
    main()