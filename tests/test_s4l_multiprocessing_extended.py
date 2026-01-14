"""
Extended test script to diagnose Sim4Life + multiprocessing issues in GOLIAT.

This test progressively adds more GOLIAT-like components to isolate
what causes segfaults (use_gui=false) or hangs (use_gui=true).

Tests:
1. Basic: Start S4L, print hello world (already passed)
2. With logging: Add GOLIAT's logging setup
3. With config: Add config loading
4. With document operations: Create/open a document
5. With PySide6: Add Qt application (mimics use_gui=true)
6. Full simulation: Run a minimal simulation step

Run with:
    python tests/test_s4l_multiprocessing_extended.py
"""

import multiprocessing
import sys
import time
import os
import traceback

# Get base directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)


def test_1_basic():
    """Test 1: Basic S4L startup (baseline)."""
    print("\n" + "=" * 60)
    print("TEST 1: Basic S4L startup")
    print("=" * 60)

    try:
        from s4l_v1._api import application

        if application.get_app_safe() is None:
            application.run_application(disable_ui_plugins=True)

        print("hello world")
        print("✓ PASS")
        return True
    except Exception as e:
        print(f"✗ FAIL: {e}")
        traceback.print_exc()
        return False


def test_2_with_logging():
    """Test 2: S4L with GOLIAT logging setup."""
    print("\n" + "=" * 60)
    print("TEST 2: S4L with GOLIAT logging")
    print("=" * 60)

    try:
        from goliat.logging_manager import setup_loggers, shutdown_loggers

        progress_logger, verbose_logger, session_timestamp = setup_loggers()
        progress_logger.info("Logging initialized")

        from s4l_v1._api import application

        if application.get_app_safe() is None:
            application.run_application(disable_ui_plugins=True)

        progress_logger.info("hello world")
        print("hello world")

        shutdown_loggers()
        print("✓ PASS")
        return True
    except Exception as e:
        print(f"✗ FAIL: {e}")
        traceback.print_exc()
        return False


def test_3_with_config():
    """Test 3: S4L with GOLIAT config loading."""
    print("\n" + "=" * 60)
    print("TEST 3: S4L with GOLIAT config loading")
    print("=" * 60)

    try:
        from goliat.config import Config

        # Try to load a config (use base_config as fallback)
        config = Config(BASE_DIR, "base_config")
        study_type = config["study_type"] or "near_field"
        print(f"Loaded config, study_type={study_type}")

        from s4l_v1._api import application

        if application.get_app_safe() is None:
            application.run_application(disable_ui_plugins=True)

        print("hello world")
        print("✓ PASS")
        return True
    except Exception as e:
        print(f"✗ FAIL: {e}")
        traceback.print_exc()
        return False


def test_4_with_document():
    """Test 4: S4L with document operations."""
    print("\n" + "=" * 60)
    print("TEST 4: S4L with document operations")
    print("=" * 60)

    try:
        from s4l_v1._api import application
        import s4l_v1.document

        if application.get_app_safe() is None:
            application.run_application(disable_ui_plugins=True)

        print("Creating new document...")
        s4l_v1.document.New()
        print("Document created")

        print("hello world")
        print("✓ PASS")
        return True
    except Exception as e:
        print(f"✗ FAIL: {e}")
        traceback.print_exc()
        return False


def test_5_with_pyside6():
    """Test 5: S4L with PySide6 (mimics use_gui=true scenario)."""
    print("\n" + "=" * 60)
    print("TEST 5: S4L with PySide6 QApplication")
    print("=" * 60)

    try:
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import QTimer

        # Check if QApplication already exists
        app = QApplication.instance()
        if app is None:
            app = QApplication([])

        print("QApplication created")

        from s4l_v1._api import application

        if application.get_app_safe() is None:
            application.run_application(disable_ui_plugins=True)

        print("hello world")

        # Process events briefly then quit
        QTimer.singleShot(100, app.quit)
        # Don't run exec() - just process events once
        app.processEvents()

        print("✓ PASS")
        return True
    except Exception as e:
        print(f"✗ FAIL: {e}")
        traceback.print_exc()
        return False


def worker_with_queue_gui(queue, stop_event):
    """Worker that mimics study_process_wrapper more closely."""
    try:
        # Import and setup like in study_process_wrapper
        from goliat.logging_manager import setup_loggers, shutdown_loggers

        progress_logger, verbose_logger, _ = setup_loggers()
        queue.put({"type": "status", "message": "Worker: Loggers initialized"})

        from s4l_v1._api import application

        queue.put({"type": "status", "message": "Worker: Starting S4L..."})
        if application.get_app_safe() is None:
            application.run_application(disable_ui_plugins=True)

        queue.put({"type": "status", "message": "Worker: S4L started"})

        # Try document operations
        import s4l_v1.document

        queue.put({"type": "status", "message": "Worker: Creating document..."})
        s4l_v1.document.New()
        queue.put({"type": "status", "message": "Worker: Document created"})

        queue.put({"type": "status", "message": "Worker: hello world"})
        queue.put({"type": "finished", "success": True})

        shutdown_loggers()

    except Exception as e:
        tb = traceback.format_exc()
        queue.put({"type": "error", "message": f"{e}\n{tb}"})
        queue.put({"type": "finished", "success": False})


def test_6_multiprocess_with_logging():
    """Test 6: Multiprocess with GOLIAT logging (closer to real usage)."""
    print("\n" + "=" * 60)
    print("TEST 6: Multiprocess with GOLIAT logging + document ops")
    print("=" * 60)

    try:
        ctx = multiprocessing.get_context("spawn")
        queue = ctx.Queue()
        stop_event = ctx.Event()

        process = ctx.Process(target=worker_with_queue_gui, args=(queue, stop_event))
        process.start()

        timeout = 120
        start = time.time()
        success = False

        while time.time() - start < timeout:
            try:
                if not queue.empty():
                    msg = queue.get(timeout=1)
                    msg_type = msg.get("type", "unknown")

                    if msg_type == "status":
                        print(f"  {msg.get('message', '')}")
                    elif msg_type == "error":
                        print(f"  ERROR: {msg.get('message', '')}")
                    elif msg_type == "finished":
                        success = msg.get("success", False)
                        break
                else:
                    time.sleep(0.1)
            except Exception:
                time.sleep(0.1)

        if process.is_alive():
            process.terminate()
            process.join(timeout=5)

        if success:
            print("✓ PASS")
        else:
            print("✗ FAIL")
        return success

    except Exception as e:
        print(f"✗ FAIL: {e}")
        traceback.print_exc()
        return False


def worker_full_gui_simulation(queue, stop_event):
    """Worker that simulates the full GUI workflow."""
    try:
        from goliat.logging_manager import setup_loggers, shutdown_loggers
        from goliat.config import Config
        from goliat.profiler import Profiler
        from goliat.gui.queue_gui import QueueGUI

        progress_logger, verbose_logger, _ = setup_loggers()
        queue.put({"type": "status", "message": "Worker: Loggers initialized"})

        # Load config
        config = Config(BASE_DIR, "base_config")
        queue.put({"type": "status", "message": "Worker: Config loaded"})

        # Create profiler
        study_type = config["study_type"] or "near_field"
        profiling_config = config.get_profiling_config(study_type)
        profiler = Profiler(
            execution_control=config["execution_control"] or {},
            profiling_config=profiling_config,
            study_type=study_type,
            config_path=config.profiling_config_path,
        )
        queue.put({"type": "status", "message": "Worker: Profiler created"})

        # Create QueueGUI (this is what studies use)
        gui_proxy = QueueGUI(queue, stop_event, profiler, progress_logger, verbose_logger)
        queue.put({"type": "status", "message": "Worker: QueueGUI created"})

        # Start S4L
        from s4l_v1._api import application

        queue.put({"type": "status", "message": "Worker: Starting S4L..."})
        if application.get_app_safe() is None:
            application.run_application(disable_ui_plugins=True)
        queue.put({"type": "status", "message": "Worker: S4L started"})

        # Use QueueGUI to log
        gui_proxy.log("hello world via QueueGUI", level="progress")

        queue.put({"type": "status", "message": "Worker: hello world"})
        queue.put({"type": "finished", "success": True})

        shutdown_loggers()

    except Exception as e:
        tb = traceback.format_exc()
        queue.put({"type": "error", "message": f"{e}\n{tb}"})
        queue.put({"type": "finished", "success": False})


def test_7_full_gui_workflow():
    """Test 7: Full GUI workflow (QueueGUI + Profiler)."""
    print("\n" + "=" * 60)
    print("TEST 7: Full GUI workflow (QueueGUI + Profiler + Config)")
    print("=" * 60)

    try:
        ctx = multiprocessing.get_context("spawn")
        queue = ctx.Queue()
        stop_event = ctx.Event()

        process = ctx.Process(target=worker_full_gui_simulation, args=(queue, stop_event))
        process.start()

        timeout = 120
        start = time.time()
        success = False

        while time.time() - start < timeout:
            try:
                if not queue.empty():
                    msg = queue.get(timeout=1)
                    msg_type = msg.get("type", "unknown")

                    if msg_type == "status":
                        print(f"  {msg.get('message', '')}")
                    elif msg_type == "error":
                        print(f"  ERROR: {msg.get('message', '')}")
                    elif msg_type == "finished":
                        success = msg.get("success", False)
                        break
                else:
                    time.sleep(0.1)
            except Exception:
                time.sleep(0.1)

        if process.is_alive():
            print("  Process still alive, terminating...")
            process.terminate()
            process.join(timeout=5)

        if success:
            print("✓ PASS")
        else:
            print("✗ FAIL")
        return success

    except Exception as e:
        print(f"✗ FAIL: {e}")
        traceback.print_exc()
        return False


def test_8_headless_study_init():
    """Test 8: Initialize NearFieldStudy headless (use_gui=false equivalent)."""
    print("\n" + "=" * 60)
    print("TEST 8: NearFieldStudy init (headless, like use_gui=false)")
    print("=" * 60)

    try:
        from goliat.logging_manager import setup_loggers, shutdown_loggers

        progress_logger, verbose_logger, _ = setup_loggers()
        print("Loggers initialized")

        # Create a simple console logger (like run_study.py does for headless)
        class SimpleConsoleLogger:
            def log(self, msg, level="verbose", log_type="default"):
                print(f"  [LOG] {msg}")

            def update_simulation_details(self, *args, **kwargs):
                pass

            def update_overall_progress(self, *args, **kwargs):
                pass

            def update_stage_progress(self, *args, **kwargs):
                pass

            def start_stage_animation(self, *args, **kwargs):
                pass

            def end_stage_animation(self, *args, **kwargs):
                pass

            def update_profiler(self, *args, **kwargs):
                pass

            def process_events(self, *args, **kwargs):
                pass

            def is_stopped(self):
                return False

        SimpleConsoleLogger()  # Verify it can be instantiated
        print("ConsoleLogger created")

        # Start S4L first
        from s4l_v1._api import application

        print("Starting S4L...")
        if application.get_app_safe() is None:
            application.run_application(disable_ui_plugins=True)
        print("S4L started")

        # Try importing NearFieldStudy
        print("Importing NearFieldStudy...")

        print("NearFieldStudy imported")

        # Note: We don't actually instantiate the study because it requires a valid config
        # with phantoms, antennas, etc. Just importing is enough to catch module-level issues.

        print("hello world")

        shutdown_loggers()
        print("✓ PASS")
        return True
    except Exception as e:
        print(f"✗ FAIL: {e}")
        traceback.print_exc()
        return False


def worker_study_init(queue, stop_event):
    """Worker that initializes NearFieldStudy like study_process_wrapper does."""
    try:
        from goliat.logging_manager import setup_loggers, shutdown_loggers
        from goliat.config import Config
        from goliat.profiler import Profiler
        from goliat.gui.queue_gui import QueueGUI

        progress_logger, verbose_logger, _ = setup_loggers()
        queue.put({"type": "status", "message": "Worker: Loggers initialized"})

        # Load config
        config = Config(BASE_DIR, "base_config")
        study_type = config["study_type"] or "near_field"
        queue.put({"type": "status", "message": f"Worker: Config loaded, study_type={study_type}"})

        # Create profiler
        profiling_config = config.get_profiling_config(study_type)
        profiler = Profiler(
            execution_control=config["execution_control"] or {},
            profiling_config=profiling_config,
            study_type=study_type,
            config_path=config.profiling_config_path,
        )
        queue.put({"type": "status", "message": "Worker: Profiler created"})

        # Create QueueGUI (verify it can be instantiated)
        QueueGUI(queue, stop_event, profiler, progress_logger, verbose_logger)
        queue.put({"type": "status", "message": "Worker: QueueGUI created"})

        # Start S4L
        from s4l_v1._api import application

        queue.put({"type": "status", "message": "Worker: Starting S4L..."})
        if application.get_app_safe() is None:
            application.run_application(disable_ui_plugins=True)
        queue.put({"type": "status", "message": "Worker: S4L started"})

        # Import NearFieldStudy
        queue.put({"type": "status", "message": "Worker: Importing NearFieldStudy..."})

        queue.put({"type": "status", "message": "Worker: NearFieldStudy imported"})

        queue.put({"type": "status", "message": "Worker: hello world"})
        queue.put({"type": "finished", "success": True})

        shutdown_loggers()

    except Exception as e:
        tb = traceback.format_exc()
        queue.put({"type": "error", "message": f"{e}\n{tb}"})
        queue.put({"type": "finished", "success": False})


def test_9_multiprocess_study_init():
    """Test 9: Initialize NearFieldStudy in spawned process (use_gui=true equivalent)."""
    print("\n" + "=" * 60)
    print("TEST 9: NearFieldStudy init in spawned process (like use_gui=true)")
    print("=" * 60)

    try:
        ctx = multiprocessing.get_context("spawn")
        queue = ctx.Queue()
        stop_event = ctx.Event()

        process = ctx.Process(target=worker_study_init, args=(queue, stop_event))
        process.start()

        timeout = 120
        start = time.time()
        success = False

        while time.time() - start < timeout:
            try:
                if not queue.empty():
                    msg = queue.get(timeout=1)
                    msg_type = msg.get("type", "unknown")

                    if msg_type == "status":
                        print(f"  {msg.get('message', '')}")
                    elif msg_type == "error":
                        print(f"  ERROR: {msg.get('message', '')}")
                    elif msg_type == "finished":
                        success = msg.get("success", False)
                        break
                else:
                    time.sleep(0.1)
            except Exception:
                time.sleep(0.1)

        if process.is_alive():
            print("  Process still alive, terminating...")
            process.terminate()
            process.join(timeout=5)

        if success:
            print("✓ PASS")
        else:
            print("✗ FAIL")
        return success

    except Exception as e:
        print(f"✗ FAIL: {e}")
        traceback.print_exc()
        return False


def run_headless_tests():
    """Run tests in headless mode (use_gui=false scenario)."""
    print("\n" + "#" * 60)
    print("# HEADLESS MODE TESTS (use_gui=false)")
    print("#" * 60)

    results = {}

    results["1_basic"] = test_1_basic()
    results["2_logging"] = test_2_with_logging()
    results["3_config"] = test_3_with_config()
    results["4_document"] = test_4_with_document()
    results["6_mp_logging"] = test_6_multiprocess_with_logging()
    results["7_full_workflow"] = test_7_full_gui_workflow()
    results["8_headless_study"] = test_8_headless_study_init()
    results["9_mp_study"] = test_9_multiprocess_study_init()

    return results


def run_gui_tests():
    """Run tests with PySide6 (use_gui=true scenario)."""
    print("\n" + "#" * 60)
    print("# GUI MODE TEST (use_gui=true)")
    print("#" * 60)

    results = {}
    results["5_pyside6"] = test_5_with_pyside6()

    return results


def main():
    print("\n" + "#" * 60)
    print("# Extended Sim4Life + Multiprocessing Diagnostic")
    print("#" * 60)
    print(f"Python: {sys.executable}")
    print(f"Version: {sys.version}")
    print(f"Base dir: {BASE_DIR}")

    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--gui", action="store_true", help="Run GUI tests (PySide6)")
    parser.add_argument("--test", type=int, help="Run specific test number (1-7)")
    args = parser.parse_args()

    if args.test:
        # Run specific test
        tests = {
            1: test_1_basic,
            2: test_2_with_logging,
            3: test_3_with_config,
            4: test_4_with_document,
            5: test_5_with_pyside6,
            6: test_6_multiprocess_with_logging,
            7: test_7_full_gui_workflow,
            8: test_8_headless_study_init,
            9: test_9_multiprocess_study_init,
        }
        if args.test in tests:
            result = tests[args.test]()
            print(f"\nTest {args.test}: {'PASS ✓' if result else 'FAIL ✗'}")
        else:
            print(f"Unknown test: {args.test}")
        return

    if args.gui:
        results = run_gui_tests()
    else:
        results = run_headless_tests()

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for name, passed in results.items():
        print(f"  {name}: {'PASS ✓' if passed else 'FAIL ✗'}")

    all_passed = all(results.values())
    if all_passed:
        print("\n✓ All tests passed!")
    else:
        failed = [k for k, v in results.items() if not v]
        print(f"\n✗ Failed tests: {', '.join(failed)}")
        print("\nThe first failing test indicates where the issue starts.")


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
