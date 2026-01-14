"""
Test to verify console logging works from child processes WITH S4L initialization.
Run with: source .bashrc && python tests/test_child_console_s4l.py
"""

import sys
import multiprocessing
import logging

# Store original stdout/stderr before any imports
_ORIGINAL_STDOUT = sys.stdout
_ORIGINAL_STDERR = sys.stderr


def setup_test_logger():
    """Setup a simple logger with stream handler."""
    logger = logging.getLogger("test_logger")
    logger.setLevel(logging.INFO)

    # Clear existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Add stream handler - this should output to console
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(logging.Formatter("%(name)s - %(message)s"))
    logger.addHandler(stream_handler)

    return logger


def child_process_func():
    """Function that runs in child process."""
    print(f"[Child] BEFORE S4L - sys.stdout is: {type(sys.stdout)}", file=_ORIGINAL_STDERR)

    # Start S4L (like run_study.py does)
    try:
        from s4l_v1._api import application

        if application.get_app_safe() is None:
            application.run_application(disable_ui_plugins=True)
        print(f"[Child] AFTER S4L - sys.stdout is: {type(sys.stdout)}", file=_ORIGINAL_STDERR)
    except ImportError:
        print("[Child] S4L not available", file=_ORIGINAL_STDERR)

    # Direct print
    print("[Child] Direct print to stdout after S4L")

    # Logger
    logger = setup_test_logger()
    logger.info("[Child] Logger message via StreamHandler after S4L")

    # Flush
    if sys.stdout:
        sys.stdout.flush()


def main():
    print("=== Testing child process console output WITH S4L ===")
    print(f"[Main] sys.stdout is: {sys.stdout}")

    # Create child process
    ctx = multiprocessing.get_context("spawn")
    p = ctx.Process(target=child_process_func)
    p.start()
    p.join()

    print("=== Test complete ===")


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
