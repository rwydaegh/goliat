import os
import sys
import argparse
import multiprocessing
import traceback
from PySide6.QtWidgets import QApplication

# Ensure the src directory is in the Python path
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__)))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

from src.logging_manager import setup_loggers, shutdown_loggers
from src.gui_manager import ProgressGUI, QueueGUI
from src.startup import run_full_startup
from src.studies.base_study import StudyCancelledError
from src.config import Config
from src.osparc_batch.runner import main as run_osparc_batch

def study_process_wrapper(queue, stop_event, config_filename):
    """
    This function runs in a separate process to execute the study.
    It sets up its own loggers and communicates with the main GUI process via a queue
    and a stop event.
    """
    # Each process needs to set up its own loggers.
    progress_logger, verbose_logger, _ = setup_loggers()
    
    try:
        from src.config import Config
        from src.studies.near_field_study import NearFieldStudy
        from src.studies.far_field_study import FarFieldStudy
        from src.profiler import Profiler

        # Basic setup
        run_full_startup(base_dir)
        
        config = Config(base_dir, config_filename)
        study_type = config.get_setting('study_type')
        
        profiling_config_data = config.get_profiling_config(study_type)
        profiler = Profiler(
            execution_control=config.get_setting('execution_control'),
            profiling_config=profiling_config_data,
            study_type=study_type,
            config_path=config.profiling_config_path
        )

        # The study will use the QueueGUI to send updates back to the main process.
        gui_proxy = QueueGUI(queue, stop_event, profiler, progress_logger, verbose_logger)

        if study_type == 'near_field':
            study = NearFieldStudy(config_filename=config_filename, gui=gui_proxy)
        elif study_type == 'far_field':
            study = FarFieldStudy(config_filename=config_filename, gui=gui_proxy)
        else:
            raise ValueError(f"Unknown or missing study type '{study_type}' in {config_filename}")
        
        study.profiler = profiler
        study.run()

    except StudyCancelledError:
        progress_logger.info("--- Study manually stopped by user ---")
        queue.put({'type': 'status', 'message': 'Study stopped by user.'})
    except Exception as e:
        # Log the fatal error and send it to the GUI
        error_msg = f"FATAL ERROR in study process: {e}\n{traceback.format_exc()}"
        progress_logger.error(error_msg)
        queue.put({'type': 'fatal_error', 'message': str(e)})
    finally:
        # Signal that the process is finished
        queue.put({'type': 'finished'})
        shutdown_loggers()


def main():
    """
    Main entry point for running a study.
    It launches the GUI in the main process and the study in a separate process.
    """
    parser = argparse.ArgumentParser(description="Run a dosimetric assessment study.")
    parser.add_argument('--config', type=str, default="configs/todays_far_field_config.json", help='Path to the configuration file.')
    args = parser.parse_args()
    config_filename = args.config

    # The main process only needs a minimal logger setup for the GUI.
    setup_loggers()

    config = Config(base_dir, config_filename)
    execution_control = config.get_setting('execution_control', {})

    if execution_control.get('batch_run'):
        run_osparc_batch(config_filename)
    else:
        # Use spawn context for compatibility across platforms
        ctx = multiprocessing.get_context('spawn')
        queue = ctx.Queue()
        stop_event = ctx.Event()
        
        # Create and start the study process
        study_process = ctx.Process(target=study_process_wrapper, args=(queue, stop_event, config_filename))
        study_process.start()

        # The GUI runs in the main process
        app = QApplication(sys.argv)
        gui = ProgressGUI(queue, stop_event, study_process)
        gui.show()
        
        app.exec()
        
        # Ensure the study process is cleaned up
        if study_process.is_alive():
            study_process.terminate()
            study_process.join()

if __name__ == '__main__':
    # This is crucial for multiprocessing to work correctly on Windows
    multiprocessing.freeze_support()
    main()