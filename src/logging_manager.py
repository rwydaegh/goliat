import logging
import os
from datetime import datetime
from colorama import Fore, Style, init
from .colors import get_color

class ColorFormatter(logging.Formatter):
    """
    A custom formatter that applies colors based on the log_type attribute
    of a log record, and resets the style after each message.
    """
    def format(self, record):
        log_type = getattr(record, 'log_type', 'default')
        color = get_color(log_type)
        message = record.getMessage()
        return f"{color}{message}{Style.RESET_ALL}"

def setup_loggers():
    """
    Sets up two loggers:
    1. 'progress': For high-level progress updates. Logs to console, a .progress.log file, and the main .log file.
    2. 'verbose': For detailed, verbose output. Logs to console and the main .log file.
    """
    init(autoreset=True) # Initialize colorama
    log_dir = 'logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # Create a timestamp for the session. This ensures all log files in a
    # single run share the same timestamp.
    session_timestamp = datetime.now().strftime('%d-%m_%H-%M-%S')

    # --- Log Rotation ---
    # Now managing two types of log files. The total limit is 20 (10 pairs).
    log_files = [os.path.join(log_dir, f) for f in os.listdir(log_dir) if f.endswith('.log')]
    log_files.sort(key=os.path.getctime)
    # We check against 10 because each run creates a pair of files.
    while len(log_files) >= 10:
        try:
            old_log = log_files.pop(0)
            base, _ = os.path.splitext(old_log)
            progress_log = base + '.progress.log'
            
            os.remove(old_log)
            if os.path.exists(progress_log):
                os.remove(progress_log)
        except OSError:
            # File might be locked, skip.
            pass

    # --- Filename Setup ---
    progress_log_filename = os.path.join(log_dir, f'{session_timestamp}.progress.log')
    main_log_filename = os.path.join(log_dir, f'{session_timestamp}.log')

    # --- Formatters ---
    file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    console_formatter = ColorFormatter()

    # --- Main Log File Handler (for both loggers) ---
    main_file_handler = logging.FileHandler(main_log_filename, mode='a')
    main_file_handler.setFormatter(file_formatter)

    # --- Progress Logger ---
    progress_logger = logging.getLogger('progress')
    progress_logger.setLevel(logging.INFO)
    # Remove existing handlers to prevent duplicates
    for handler in progress_logger.handlers[:]:
        progress_logger.removeHandler(handler)
    
    # File handler for progress file
    progress_file_handler = logging.FileHandler(progress_log_filename, mode='a')
    progress_file_handler.setFormatter(file_formatter)
    progress_logger.addHandler(progress_file_handler)
    
    # Add main file handler
    progress_logger.addHandler(main_file_handler)
    
    # Stream handler for progress (console output)
    progress_stream_handler = logging.StreamHandler()
    progress_stream_handler.setFormatter(console_formatter)
    progress_logger.addHandler(progress_stream_handler)
    progress_logger.propagate = False

    # --- Verbose Logger ---
    verbose_logger = logging.getLogger('verbose')
    verbose_logger.setLevel(logging.INFO)
    # Remove existing handlers
    for handler in verbose_logger.handlers[:]:
        verbose_logger.removeHandler(handler)

    # Add main file handler
    verbose_logger.addHandler(main_file_handler)

    # Stream handler for verbose (console output)
    verbose_stream_handler = logging.StreamHandler()
    verbose_stream_handler.setFormatter(console_formatter)
    verbose_logger.addHandler(verbose_stream_handler)
    verbose_logger.propagate = False

    progress_logger.info(f"--- Progress logging started for file: {os.path.abspath(progress_log_filename)} ---")
    verbose_logger.info(f"--- Main logging started for file: {os.path.abspath(main_log_filename)} ---")

    return progress_logger, verbose_logger, session_timestamp

def shutdown_loggers():
    """
    Shuts down all logging handlers to release file locks.
    """
    for name in ['progress', 'verbose']:
        logger = logging.getLogger(name)
        logger.info("--- Logging shutdown ---")
        for handler in logger.handlers[:]:
            handler.close()
            logger.removeHandler(handler)

class LoggingMixin:
    """
    A mixin class to provide a standardized _log method.
    It expects the inheriting class to have 'verbose_logger', 'progress_logger',
    and an optional 'gui' attribute.
    """
    def _log(self, message, level='verbose', log_type='default'):
        """
        Logs a message to the appropriate logger with a specified type for color-coding.
        
        Args:
            message (str): The message to log.
            level (str): The logging level ('progress' or 'verbose').
            log_type (str): The type of log message for color-coding (e.g., 'info', 'warning', 'error').
        """
        extra = {'log_type': log_type}
        
        if level == 'progress':
            self.progress_logger.info(message, extra=extra)
            if hasattr(self, 'gui') and self.gui:
                self.gui.log(message, level='progress')
        else:
            self.verbose_logger.info(message, extra=extra)
            if hasattr(self, 'gui') and self.gui and level != 'progress':
                self.gui.log(message, level='verbose')