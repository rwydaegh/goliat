"""
Test to verify console logging works from child processes.
Run with: source .bashrc && python tests/test_child_console.py
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
    print(f"[Child] sys.stdout is: {sys.stdout}", file=_ORIGINAL_STDERR)
    print(f"[Child] sys.stderr is: {sys.stderr}", file=_ORIGINAL_STDERR)

    # Direct print
    print("[Child] Direct print to stdout")

    # Logger
    logger = setup_test_logger()
    logger.info("[Child] Logger message via StreamHandler")

    # Flush
    if sys.stdout:
        sys.stdout.flush()


def main():
    print("=== Testing child process console output ===")
    print(f"[Main] sys.stdout is: {sys.stdout}")
    print(f"[Main] sys.stderr is: {sys.stderr}")

    # Create child process
    ctx = multiprocessing.get_context("spawn")
    p = ctx.Process(target=child_process_func)
    p.start()
    p.join()

    print("=== Test complete ===")


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
