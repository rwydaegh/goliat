import inspect
import logging
import os
import time
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from colorama import Style, init

from .colors import get_color

if TYPE_CHECKING:
    from .gui_manager import QueueGUI


class ColorFormatter(logging.Formatter):
    """A custom log formatter that applies color to terminal output."""

    def format(self, record: logging.LogRecord) -> str:
        """Formats the log record by adding color codes.

        Args:
            record: The log record to format.

        Returns:
            The formatted and colorized log message.
        """
        log_type = getattr(record, "log_type", "default")
        message_color = get_color(log_type)
        caller_color = get_color("caller")
        message = record.getMessage()
        caller_info = getattr(record, "caller_info", "")
        return f"{message_color}{message}{Style.RESET_ALL} {caller_color}{caller_info}{Style.RESET_ALL}"


class CustomFormatter(logging.Formatter):
    """A custom formatter to handle missing record attributes."""

    def format(self, record: logging.LogRecord) -> str:
        """Formats the record, safely handling the 'caller_info' attribute."""
        # First, format the base message
        base_message = super().format(record)
        # If caller_info is present, append it
        caller_info = getattr(record, "caller_info", "")
        if caller_info:
            return f"{base_message} {caller_info}"
        return base_message


def setup_loggers(process_id: Optional[str] = None) -> tuple[logging.Logger, logging.Logger, str]:
    """Initializes and configures the dual-logging system.

    Sets up two loggers:
    1. 'progress': For high-level, user-facing updates.
    2. 'verbose': For detailed, internal debugging information.

    Also handles log rotation to prevent excessive disk usage.

    Args:
        process_id: An identifier for the process to ensure unique log
                    filenames in parallel runs.

    Returns:
        A tuple containing the progress logger, verbose logger, and the
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
        log_files = [os.path.join(log_dir, f) for f in os.listdir(log_dir) if f.endswith(".log")]
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

    file_formatter = CustomFormatter("%(asctime)s - %(levelname)s - %(message)s")
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

    progress_logger.info(f"--- Progress logging started for file: {os.path.abspath(progress_log_filename)} ---")
    verbose_logger.info(f"--- Main logging started for file: {os.path.abspath(main_log_filename)} ---")

    return progress_logger, verbose_logger, session_timestamp


def shutdown_loggers():
    """Safely shuts down all logging handlers to release file locks."""
    for name in ["progress", "verbose"]:
        logger = logging.getLogger(name)
        logger.info("--- Logging shutdown ---")
        for handler in logger.handlers[:]:
            handler.close()
            logger.removeHandler(handler)


class LoggingMixin:
    """A mixin class that provides a standardized logging interface.

    Provides a `_log` method that directs messages to the appropriate logger
    ('progress' or 'verbose') and, if available, to the GUI.
    """

    progress_logger: logging.Logger
    verbose_logger: logging.Logger
    gui: Optional["QueueGUI"]

    def _log(self, message: str, level: str = "verbose", log_type: str = "default"):
        """Logs a message with a specified level and color-coding type.

        Args:
            message: The message to be logged.
            level: The logging level ('progress' or 'verbose').
            log_type: A string key that maps to a color for terminal output.
        """
        extra = {"log_type": log_type}
        log_origin = ""

        # Always try to get caller info for verbose logs
        current_frame = inspect.currentframe()
        if current_frame:
            caller_frame = current_frame.f_back
            if caller_frame:
                caller_method_name = caller_frame.f_code.co_name
                if "self" in caller_frame.f_locals:
                    caller_class_name = caller_frame.f_locals["self"].__class__.__name__
                    log_origin = f"{caller_class_name}.{caller_method_name}"
                else:
                    log_origin = caller_method_name
        extra["caller_info"] = f"[{log_origin}]"

        if level == "progress":
            self.progress_logger.info(message, extra=extra)
            if hasattr(self, "gui") and self.gui:
                # Send to GUI with log_type for counters
                self.gui.log(message, level="progress", log_type=log_type)
        else: # verbose
            self.verbose_logger.info(message, extra=extra)
            # Do not send verbose logs to the GUI status box
