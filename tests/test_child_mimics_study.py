"""
Test that mimics the actual goliat study import flow.
This test imports from cli/run_study.py which triggers module-level S4L init.

Run with: python tests/test_child_mimics_study.py
"""

import sys
import os
import multiprocessing

# Add base dir to path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)


def child_process_func():
    """Function that runs in child process - mimics study_process_wrapper."""
    # This import will trigger the module-level S4L init in run_study.py
    print("[Child] About to import run_study (triggers S4L init)...")
    sys.stdout.flush()

    from cli.run_study import setup_loggers, shutdown_loggers

    print("[Child] Import complete, setting up loggers...")
    sys.stdout.flush()

    progress_logger, verbose_logger, _ = setup_loggers()

    # These should appear in terminal
    progress_logger.info("=== PROGRESS LOGGER TEST MESSAGE ===")
    verbose_logger.info("=== VERBOSE LOGGER TEST MESSAGE ===")

    # Direct print
    print("[Child] Direct print after logger setup")

    shutdown_loggers()
    print("[Child] Done")


def main():
    print("=== Testing child process that mimics goliat study ===")
    print(f"[Main] Python: {sys.executable}")

    # Create child process using spawn (like goliat study does)
    ctx = multiprocessing.get_context("spawn")
    p = ctx.Process(target=child_process_func)
    p.start()
    p.join()

    print("=== Test complete ===")


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
