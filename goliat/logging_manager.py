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


class QueueLogHandler(logging.Handler):
    """Logging handler that forwards records to a multiprocessing queue.

    Used in child processes on S4L 9.2 where stdout is broken. Sends log
    messages through the queue to the main process for terminal output.
    """

    def __init__(self, queue, level: str = "verbose"):
        """Initialize the handler.

        Args:
            queue: Multiprocessing queue to send messages to.
            level: Log level name ('progress' or 'verbose') for message type.
        """
        super().__init__()
        self.queue = queue
        self.level_name = level

    def emit(self, record: logging.LogRecord) -> None:
        """Send log record through the queue."""
        try:
            import time as time_module

            log_type = getattr(record, "log_type", "default")

            # 'status' updates GUI AND prints to terminal
            # 'terminal_only' only prints to terminal
            msg_type = "status" if self.level_name == "progress" else "terminal_only"

            # For GUI messages, send raw message without caller_info
            # For terminal-only, include caller_info for debugging
            if msg_type == "status":
                # Raw message without formatting (GUI handles its own colors)
                message = record.getMessage()
            else:
                # Full formatted message with caller_info for terminal
                message = self.format(record)

            self.queue.put(
                {
                    "type": msg_type,
                    "message": message,
                    "log_type": log_type,
                    "timestamp": time_module.time(),
                }
            )
        except Exception:
            self.handleError(record)


def setup_loggers(
    process_id: Optional[str] = None, session_timestamp: Optional[str] = None, queue=None
) -> tuple[logging.Logger, logging.Logger, str]:
    """Sets up dual logging system with rotation.

    Creates 'progress' and 'verbose' loggers with file and console handlers.
    Rotates old logs when more than 30 exist. Uses lock file for thread-safe
    rotation.

    Args:
        process_id: Optional ID to make log filenames unique for parallel runs.
        session_timestamp: Optional timestamp to use for log filenames. If not provided,
            generates a new timestamp. Useful for ensuring multiple processes use the same log file.
        queue: Optional multiprocessing queue. If provided, adds QueueLogHandler to both
            loggers so messages are forwarded to main process for terminal output.
            This is needed on S4L 9.2 where child process stdout is broken.

    Returns:
        Tuple of (progress_logger, verbose_logger, session_timestamp).
    """
    # Initialize colorama with appropriate settings for current environment
    init_colorama()
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    if session_timestamp is None:
        session_timestamp = datetime.now().strftime("%d-%m_%H-%M-%S")
        if process_id:
            session_timestamp = f"{session_timestamp}_{process_id}"
    elif process_id:
        # If both are provided, append process_id to the existing timestamp
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

    # Add queue handler if provided (for S4L 9.2 child process terminal output)
    if queue is not None:
        progress_queue_handler = QueueLogHandler(queue, level="progress")
        progress_queue_handler.setFormatter(console_formatter)
        progress_logger.addHandler(progress_queue_handler)
    else:
        # Only add StreamHandler if not using queue (main process or S4L 8.2)
        progress_stream_handler = logging.StreamHandler()
        progress_stream_handler.setFormatter(console_formatter)
        progress_logger.addHandler(progress_stream_handler)
    progress_logger.propagate = False

    verbose_logger = logging.getLogger("verbose")
    verbose_logger.setLevel(logging.INFO)
    for handler in verbose_logger.handlers[:]:
        verbose_logger.removeHandler(handler)

    verbose_logger.addHandler(main_file_handler)

    # Add queue handler if provided (for S4L 9.2 child process terminal output)
    if queue is not None:
        verbose_queue_handler = QueueLogHandler(queue, level="verbose")
        verbose_queue_handler.setFormatter(console_formatter)
        verbose_logger.addHandler(verbose_queue_handler)
    else:
        # Only add StreamHandler if not using queue (main process or S4L 8.2)
        verbose_stream_handler = logging.StreamHandler()
        verbose_stream_handler.setFormatter(console_formatter)
        verbose_logger.addHandler(verbose_stream_handler)
    verbose_logger.propagate = False

    # Log startup messages only to files, not to GUI/terminal
    # These are internal setup messages that shouldn't clutter the GUI
    progress_startup_record = logging.LogRecord(
        "progress", logging.INFO, "", 0, f"--- Progress logging started for file: {os.path.abspath(progress_log_filename)} ---", None, None
    )
    progress_file_handler.emit(progress_startup_record)
    main_file_handler.emit(progress_startup_record)

    verbose_startup_record = logging.LogRecord(
        "verbose", logging.INFO, "", 0, f"--- Main logging started for file: {os.path.abspath(main_log_filename)} ---", None, None
    )
    main_file_handler.emit(verbose_startup_record)

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

    # Log that simulation-specific logging has started (only to file, not GUI)
    # Use the file handlers directly to avoid sending to queue/GUI
    file_formatter = CustomFormatter("%(asctime)s - %(levelname)s - %(message)s")
    progress_record = logging.LogRecord(
        "progress", logging.INFO, "", 0, f"--- Simulation-specific progress logging started: {progress_log_path} ---", None, None
    )
    progress_file_handler.emit(progress_record)
    verbose_record = logging.LogRecord(
        "verbose", logging.INFO, "", 0, f"--- Simulation-specific verbose logging started: {verbose_log_path} ---", None, None
    )
    verbose_file_handler.emit(verbose_record)

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
            # Note: Terminal output is handled by QueueLogHandler (added to logger in setup_loggers)
            # GUI status box update: QueueLogHandler sends 'status' type for progress level
        else:  # verbose
            self.verbose_logger.info(message, extra=extra)
            # Note: Terminal output is handled by QueueLogHandler (added to logger in setup_loggers)
            # Verbose logs use 'terminal_only' type, so they don't update GUI status box
