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
import atexit

def main():
    """
    Main entry point for running simulation studies.
    """
    parser = argparse.ArgumentParser(description="Run near-field or far-field simulation studies.")
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
    setup_loggers()
    atexit.register(shutdown_loggers)

    # Run startup checks before importing other modules that might have dependencies
    if not args.skip_startup:
        run_full_startup(base_dir)

    # Now that dependencies are installed, we can import the other modules
    from src.gui_manager import ProgressGUI
    from PySide6.QtWidgets import QApplication

    if args.config:
        config_filename = args.config
    else:
        config_filename = os.path.join("configs", "todays_near_field_config.json")

    # The GUI now handles the study execution in a separate process
    app = QApplication(sys.argv)
    # The ProgressGUI will determine the study_type from the config file
    gui = ProgressGUI(config_filename=config_filename)
    gui.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    # This is crucial for multiprocessing to work correctly on Windows
    multiprocessing.freeze_support()
    main()