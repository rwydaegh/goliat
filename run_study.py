import argparse
import os
import sys
import multiprocessing

# Ensure the project root directory is in the Python path
base_dir = os.path.dirname(os.path.abspath(__file__))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

from src.startup import run_full_startup
from src.gui_manager import ProgressGUI
from PySide6.QtWidgets import QApplication
from src.logging_manager import setup_loggers, shutdown_loggers
import atexit

def main():
    """
    Main entry point for running simulation studies.
    """
    parser = argparse.ArgumentParser(description="Run near-field or far-field simulation studies.")
    parser.add_argument(
        'study_type',
        type=str,
        choices=['near_field', 'far_field'],
        help="The type of study to run."
    )
    parser.add_argument(
        '--skip-startup',
        action='store_true',
        help="Skip the startup checks for dependencies and data."
    )
    parser.add_argument(
        '--no-gui',
        action='store_true',
        help="Run the study without the GUI."
    )
    parser.add_argument(
        '--config',
        type=str,
        default=None,
        help="Path to a custom configuration file."
    )

    args = parser.parse_args()

    config_filename = args.config if args.config else f"{args.study_type}_config.json"

    # Setup logging and ensure it's shut down on exit
    setup_loggers()
    atexit.register(shutdown_loggers)

    if not args.skip_startup:
        run_full_startup(base_dir)

    if not args.no_gui:
        # The GUI now handles the study execution in a separate process
        app = QApplication(sys.argv)
        # The GUI needs to be updated to handle the custom config path
        # For now, we assume it will use the default if args.config is None
        gui = ProgressGUI(args.study_type, config_filename=config_filename)
        gui.show()
        sys.exit(app.exec())
    else:
        # For command-line execution, run the study directly
        if args.study_type == 'near_field':
            from src.studies.near_field_study import NearFieldStudy
            study = NearFieldStudy(config_filename=config_filename, verbose=True)
            study.run()
        elif args.study_type == 'far_field':
            from src.studies.far_field_study import FarFieldStudy
            study = FarFieldStudy(config_filename=config_filename, verbose=True)
            study.run()

if __name__ == "__main__":
    # This is crucial for multiprocessing to work correctly on Windows
    multiprocessing.freeze_support()
    main()