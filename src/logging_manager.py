import logging
import os
import time
from datetime import datetime

from colorama import Style, init

from .colors import get_color


class ColorFormatter(logging.Formatter):
    """
    A custom log formatter that applies color to terminal output.

    This formatter uses the `log_type` attribute of a log record to determine
    the appropriate color from the `COLOR_MAP`. It ensures that each log
    message is colorized and the style is reset afterward.
    """

    def format(self, record):
        """
        Formats the log record by adding color codes.

        Args:
            record (logging.LogRecord): The log record to format.

        Returns:
            str: The formatted and colorized log message.
        """
        log_type = getattr(record, "log_type", "default")
        color = get_color(log_type)
        message = record.getMessage()
        return f"{color}{message}{Style.RESET_ALL}"


def setup_loggers(process_id=None):
    """
    Initializes and configures the dual-logging system for the application.

    This function sets up two distinct loggers:
    1. 'progress': For high-level, user-facing progress updates.
    2. 'verbose': For detailed, internal debugging information.

    It also handles log rotation to prevent excessive disk usage.

    Args:
        process_id (str, optional): An identifier for the process to ensure
            unique log filenames in parallel runs.

    Returns:
        tuple: A tuple containing the progress logger, verbose logger, and the
               session timestamp.
    """
    init(autoreset=True)
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    session_timestamp = datetime.now().strftime("%d-%m_%H-%M-%S")
    if process_id:
        session_timestamp = f"{session_timestamp}_{process_id}"

    lock_file_path = os.path.join(log_dir, "log_rotation.lock")

    while True:
        try:
            with open(lock_file_path, "x"):
                break
        except FileExistsError:
            time.sleep(0.1)

    try:
        log_files = [
            os.path.join(log_dir, f) for f in os.listdir(log_dir) if f.endswith(".log")
        ]
        log_files.sort(key=os.path.getctime)
        while len(log_files) >= 30:
            try:
                old_log = log_files.pop(0)
                base, _ = os.path.splitext(old_log)
                progress_log = base + ".progress.log"

                if os.path.exists(old_log):
                    os.remove(old_log)
                if os.path.exists(progress_log):
                    os.remove(progress_log)
            except OSError:
                pass
    finally:
        if os.path.exists(lock_file_path):
            os.remove(lock_file_path)

    progress_log_filename = os.path.join(log_dir, f"{session_timestamp}.progress.log")
    main_log_filename = os.path.join(log_dir, f"{session_timestamp}.log")

    file_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    console_formatter = ColorFormatter()

    main_file_handler = logging.FileHandler(main_log_filename, mode="a")
    main_file_handler.setFormatter(file_formatter)

    progress_logger = logging.getLogger("progress")
    progress_logger.setLevel(logging.INFO)
    for handler in progress_logger.handlers[:]:
        progress_logger.removeHandler(handler)

    progress_file_handler = logging.FileHandler(progress_log_filename, mode="a")
    progress_file_handler.setFormatter(file_formatter)
    progress_logger.addHandler(progress_file_handler)

    progress_logger.addHandler(main_file_handler)

    progress_stream_handler = logging.StreamHandler()
    progress_stream_handler.setFormatter(console_formatter)
    progress_logger.addHandler(progress_stream_handler)
    progress_logger.propagate = False

    verbose_logger = logging.getLogger("verbose")
    verbose_logger.setLevel(logging.INFO)
    for handler in verbose_logger.handlers[:]:
        verbose_logger.removeHandler(handler)

    verbose_logger.addHandler(main_file_handler)

    verbose_stream_handler = logging.StreamHandler()
    verbose_stream_handler.setFormatter(console_formatter)
    verbose_logger.addHandler(verbose_stream_handler)
    verbose_logger.propagate = False

    progress_logger.info(
        f"--- Progress logging started for file: {os.path.abspath(progress_log_filename)} ---"
    )
    verbose_logger.info(
        f"--- Main logging started for file: {os.path.abspath(main_log_filename)} ---"
    )

    return progress_logger, verbose_logger, session_timestamp


def shutdown_loggers():
    """
    Safely shuts down all logging handlers to release file locks.

    This function should be called at the end of the application's lifecycle
    to ensure that all log files are properly closed.
    """
    for name in ["progress", "verbose"]:
        logger = logging.getLogger(name)
        logger.info("--- Logging shutdown ---")
        for handler in logger.handlers[:]:
            handler.close()
            logger.removeHandler(handler)


class LoggingMixin:
    """
    A mixin class that provides a standardized logging interface.

    This mixin is intended to be inherited by classes that require logging
    capabilities. It provides a `_log` method that abstracts the underlying
    logging mechanism and directs messages to the appropriate logger ('progress'
    or 'verbose') and, if available, to the GUI.
    """

    def _log(self, message, level="verbose", log_type="default"):
        """
        Logs a message with a specified level and color-coding type.

        Args:
            message (str): The message to be logged.
            level (str): The logging level, either 'progress' for user-facing
                         messages or 'verbose' for detailed internal messages.
            log_type (str): A string key that maps to a color in the
                          `COLOR_MAP` for terminal output.
        """
        extra = {"log_type": log_type}

        if level == "progress":
            self.progress_logger.info(message, extra=extra)
            if hasattr(self, "gui") and self.gui:
                self.gui.log(message, level="progress")
        else:
            self.verbose_logger.info(message, extra=extra)
            if hasattr(self, "gui") and self.gui and level != "progress":
                self.gui.log(message, level="verbose")
