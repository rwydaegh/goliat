import inspect
import logging
import os
import time
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from colorama import Style

from .colors import get_color, init_colorama

if TYPE_CHECKING:
    from .gui_manager import QueueGUI


class ColorFormatter(logging.Formatter):
    """Custom formatter that colorizes log messages based on log_type.

    Applies colorama color codes to messages and caller info based on the
    log_type attribute (info, warning, error, success, etc.).
    """

    def format(self, record: logging.LogRecord) -> str:
        """Adds color codes to log messages based on log_type."""
        log_type = getattr(record, "log_type", "default")
        message_color = get_color(log_type)
        caller_color = get_color("caller")
        message = record.getMessage()
        caller_info = getattr(record, "caller_info", "")
        return f"{message_color}{message}{Style.RESET_ALL} {caller_color}{caller_info}{Style.RESET_ALL}"


class CustomFormatter(logging.Formatter):
    """Formatter that safely handles optional caller_info attribute."""

    def format(self, record: logging.LogRecord) -> str:
        """Formats the record, safely handling the 'caller_info' attribute."""
        base_message = super().format(record)
        caller_info = getattr(record, "caller_info", "")
        if caller_info:
            return f"{base_message} {caller_info}"
        return base_message


def setup_loggers(process_id: Optional[str] = None) -> tuple[logging.Logger, logging.Logger, str]:
    """Sets up dual logging system with rotation.

    Creates 'progress' and 'verbose' loggers with file and console handlers.
    Rotates old logs when more than 30 exist. Uses lock file for thread-safe
    rotation.

    Args:
        process_id: Optional ID to make log filenames unique for parallel runs.

    Returns:
        Tuple of (progress_logger, verbose_logger, session_timestamp).
    """
    # Initialize colorama with appropriate settings for current environment
    init_colorama()
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


def add_simulation_log_handlers(simulation_dir: str) -> list[logging.Handler]:
    """Adds file handlers for progress and verbose logs to a simulation-specific directory.

    Creates log files in the simulation directory while keeping the main logs/ directory
    handlers intact. Both progress and verbose logs are written to the simulation directory.

    Args:
        simulation_dir: Directory path where simulation-specific logs should be written.

    Returns:
        List of handlers that were added (for later removal via remove_simulation_log_handlers).
    """
    if not os.path.exists(simulation_dir):
        os.makedirs(simulation_dir)

    file_formatter = CustomFormatter("%(asctime)s - %(levelname)s - %(message)s")

    # Create log file paths in the simulation directory
    progress_log_path = os.path.join(simulation_dir, "progress.log")
    verbose_log_path = os.path.join(simulation_dir, "verbose.log")

    # Create handlers
    progress_file_handler = logging.FileHandler(progress_log_path, mode="a")
    progress_file_handler.setFormatter(file_formatter)
    setattr(progress_file_handler, "_is_simulation_handler", True)  # Mark for later removal

    verbose_file_handler = logging.FileHandler(verbose_log_path, mode="a")
    verbose_file_handler.setFormatter(file_formatter)
    setattr(verbose_file_handler, "_is_simulation_handler", True)  # Mark for later removal

    # Add handlers to loggers
    progress_logger = logging.getLogger("progress")
    verbose_logger = logging.getLogger("verbose")

    progress_logger.addHandler(progress_file_handler)
    verbose_logger.addHandler(verbose_file_handler)

    # Log that simulation-specific logging has started
    progress_logger.info(f"--- Simulation-specific progress logging started: {progress_log_path} ---")
    verbose_logger.info(f"--- Simulation-specific verbose logging started: {verbose_log_path} ---")

    return [progress_file_handler, verbose_file_handler]


def remove_simulation_log_handlers(handlers: list[logging.Handler]):
    """Removes simulation-specific log handlers and closes their files.

    Args:
        handlers: List of handlers to remove (typically returned from add_simulation_log_handlers).
    """
    for handler in handlers:
        if hasattr(handler, "_is_simulation_handler") and getattr(handler, "_is_simulation_handler", False):
            # Find and remove from appropriate logger
            progress_logger = logging.getLogger("progress")
            verbose_logger = logging.getLogger("verbose")

            if handler in progress_logger.handlers:
                progress_logger.removeHandler(handler)
            if handler in verbose_logger.handlers:
                verbose_logger.removeHandler(handler)

            handler.close()


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
        else:  # verbose
            self.verbose_logger.info(message, extra=extra)
            # Do not send verbose logs to the GUI status box
