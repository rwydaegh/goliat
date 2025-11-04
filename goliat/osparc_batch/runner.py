import argparse
import os
import sys

from PySide6.QtCore import QThread

from goliat.osparc_batch.cleanup import clear_log_directory, clear_temp_download_directory
from goliat.osparc_batch.file_finder import find_input_files
from goliat.osparc_batch.gui import BatchGUI
from goliat.osparc_batch.logging_utils import setup_console_logging
from goliat.osparc_batch.main_logic import main_process_logic
from goliat.osparc_batch.osparc_client import (
    download_and_process_results,
    get_osparc_client_config,
)
from goliat.osparc_batch.progress import get_progress_report
from goliat.osparc_batch.worker import Worker

main_logger = setup_console_logging()


def main(config_path: str) -> None:
    """Main entry point: sets up and starts the GUI and the main logic process."""
    from PySide6.QtWidgets import QApplication

    from goliat.config import Config

    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    clear_log_directory(base_dir)

    config = Config(base_dir, config_path)
    input_files = find_input_files(config)

    app = QApplication.instance() or QApplication(sys.argv)

    thread = QThread()
    worker = Worker(
        config_path=config_path,
        logger=main_logger,
        get_osparc_client_config_func=get_osparc_client_config,
        download_and_process_results_func=download_and_process_results,
        get_progress_report_func=get_progress_report,
        main_process_logic_func=main_process_logic,
    )
    worker.config = config  # type: ignore
    worker.input_files = input_files
    worker.moveToThread(thread)

    gui = BatchGUI()

    # Connect signals and slots
    thread.started.connect(worker.run)
    worker.finished.connect(thread.quit)
    worker.finished.connect(worker.deleteLater)
    thread.finished.connect(thread.deleteLater)

    worker.progress.connect(main_logger.info)
    gui.print_progress_requested.connect(worker.request_progress_report)
    gui.stop_run_requested.connect(worker.stop)
    gui.cancel_jobs_requested.connect(worker.cancel_jobs)

    worker.finished.connect(app.quit)

    thread.start()
    gui.show()
    app.exec()

    if thread.isRunning():
        thread.quit()
        thread.wait()

    clear_temp_download_directory(base_dir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run a batch of simulations on oSPARC with a progress GUI. Supports both far-field and near-field studies."
    )
    parser.add_argument(
        "--config",
        type=str,
        required=True,
        help="Path to the configuration file (e.g., 'configs/near_field_config.json' or 'configs/far_field_config.json').",
    )
    args = parser.parse_args()
    main(args.config)
