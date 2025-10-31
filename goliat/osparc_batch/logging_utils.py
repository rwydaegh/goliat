import logging

import colorama

from goliat.colors import init_colorama


def setup_console_logging() -> logging.Logger:
    """Sets up a basic console logger with color."""
    init_colorama()
    logger = logging.getLogger("osparc_batch")
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    return logger


def setup_job_logging(base_dir: str, job_id: str) -> logging.Logger:
    """Sets up a unique log file for each job in a specific subdirectory."""
    from pathlib import Path

    log_dir = Path(base_dir) / "logs" / "osparc_submission_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file_path = log_dir / f"job_{job_id}.log"

    job_logger = logging.getLogger(f"job_{job_id}")
    job_logger.setLevel(logging.INFO)
    job_logger.propagate = False

    if job_logger.hasHandlers():
        job_logger.handlers.clear()

    file_handler = logging.FileHandler(log_file_path, mode="w")
    file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    job_logger.addHandler(file_handler)

    return job_logger


STATUS_COLORS = {
    "PENDING": colorama.Fore.YELLOW,
    "PUBLISHED": colorama.Fore.LIGHTYELLOW_EX,
    "WAITING_FOR_CLUSTER": colorama.Fore.MAGENTA,
    "WAITING_FOR_RESOURCES": colorama.Fore.LIGHTMAGENTA_EX,
    "STARTED": colorama.Fore.CYAN,
    "SUCCESS": colorama.Fore.GREEN,
    "FAILED": colorama.Fore.RED,
    "RETRYING": colorama.Fore.LIGHTRED_EX,
    "DOWNLOADING": colorama.Fore.BLUE,
    "FINISHED": colorama.Fore.GREEN,
    "COMPLETED": colorama.Fore.GREEN,
    "UNKNOWN": colorama.Fore.WHITE,
}
