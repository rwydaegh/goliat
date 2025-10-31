import shutil
from pathlib import Path

from goliat.osparc_batch.logging_utils import setup_console_logging

main_logger = setup_console_logging()


def clear_log_directory(base_dir: str) -> None:
    """Deletes all files in the osparc_submission_logs directory."""
    log_dir = Path(base_dir) / "logs" / "osparc_submission_logs"
    if log_dir.exists():
        main_logger.info(f"--- Clearing log directory: {log_dir} ---")
        for item in log_dir.iterdir():
            if item.is_file():
                try:
                    item.unlink()
                except OSError as e:
                    main_logger.error(f"Error deleting file {item}: {e}")
            elif item.is_dir():
                try:
                    shutil.rmtree(item)
                except OSError as e:
                    main_logger.error(f"Error deleting directory {item}: {e}")


def clear_temp_download_directory(base_dir: str) -> None:
    """Deletes the temporary download directory."""
    temp_dir = Path(base_dir) / "tmp_download"
    if temp_dir.exists():
        main_logger.info(f"--- Clearing temporary download directory: {temp_dir} ---")
        try:
            shutil.rmtree(temp_dir)
        except OSError as e:
            main_logger.error(f"Error deleting directory {temp_dir}: {e}")
