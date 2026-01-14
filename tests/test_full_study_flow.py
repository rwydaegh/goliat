"""
Test that mimics the FULL goliat study flow.
Both main AND child processes do the module-level S4L init.

Run with: python tests/test_full_study_flow.py
"""

import sys
import os
import multiprocessing

# Add base dir to path before any imports
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

# This import triggers module-level S4L init in the MAIN process
# (just like when you run `goliat study`)
print("[Main] About to import run_study (triggers S4L init in main)...")
from cli.run_study import setup_loggers, shutdown_loggers  # noqa: E402

print("[Main] Import complete")


def child_process_func(queue):
    """Function that runs in child process - mimics study_process_wrapper."""
    # The child process also re-imports run_study.py due to spawn context
    # This will trigger module-level S4L init again in the child
    print("[Child] Child process starting...")
    sys.stdout.flush()

    print("[Child] Setting up loggers...")
    sys.stdout.flush()

    progress_logger, verbose_logger, _ = setup_loggers()

    # These should appear in terminal
    progress_logger.info("=== PROGRESS LOGGER TEST MESSAGE ===")
    verbose_logger.info("=== VERBOSE LOGGER TEST MESSAGE ===")

    # Direct print
    print("[Child] Direct print after logger setup")

    # Send a message through the queue (like QueueGUI does)
    queue.put({"type": "status", "message": "Test message from child"})

    shutdown_loggers()
    print("[Child] Done")
    queue.put({"type": "finished"})


def main():
    print("=== Testing FULL goliat study flow ===")
    print(f"[Main] Python: {sys.executable}")

    # Create queue and child process (like goliat study does)
    ctx = multiprocessing.get_context("spawn")
    queue = ctx.Queue()
    p = ctx.Process(target=child_process_func, args=(queue,))
    p.start()

    # Wait for messages from child (like the GUI would)

    while True:
        try:
            msg = queue.get(timeout=1)
            print(f"[Main] Received from queue: {msg}")
            if msg.get("type") == "finished":
                break
        except Exception:
            if not p.is_alive():
                break

    p.join()
    print("=== Test complete ===")


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
