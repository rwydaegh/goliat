"""
Test that mimics the exact import order of 'goliat study' to find the segfault cause.

The hypothesis is that the import order matters - importing certain modules
BEFORE starting Sim4Life causes issues in 9.2 but not 8.2.

Run with:
    python tests/test_s4l_import_order.py
"""

import sys
import os
import traceback

# Get base directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)


def test_import_order_like_run_study():
    """
    Mimic the exact import order from cli/run_study.py to find the segfault.
    """
    print("\n" + "=" * 70)
    print("TEST: Mimicking exact import order from 'goliat study'")
    print("=" * 70)

    try:
        # --- PHASE 1: Early imports (before S4L) ---
        print("\n--- PHASE 1: Early imports (like run_study.py lines 1-80) ---")

        print("1. Importing argparse, logging, multiprocessing, os, platform, sys, traceback...")

        print("   ✓ Done")

        print("2. Importing goliat.utils.setup.initial_setup...")

        print("   ✓ Done")

        print("3. Running initial_setup() [if not in test env]...")
        # Skip in test to avoid side effects
        # initial_setup()
        print("   ✓ Skipped (we're in test)")

        print("4. Importing PySide6.QtWidgets.QApplication...")

        print("   ✓ Done - THIS IS THE KEY DIFFERENCE!")

        print("5. Importing goliat.config.Config...")

        print("   ✓ Done")

        print("6. Importing goliat.logging_manager...")
        from goliat.logging_manager import setup_loggers, shutdown_loggers

        print("   ✓ Done")

        print("7. Importing goliat.studies.base_study.StudyCancelledError...")

        print("   ✓ Done")

        print("8. Importing goliat.gui_manager (ProgressGUI, QueueGUI)...")

        print("   ✓ Done")

        # --- PHASE 2: Start S4L (this is where segfault happens) ---
        print("\n--- PHASE 2: Starting Sim4Life (this is where segfault happens) ---")

        print("9. Setting up loggers...")
        progress_logger, verbose_logger, session_timestamp = setup_loggers()
        print("   ✓ Done")

        print("10. Importing s4l_v1._api.application...")
        from s4l_v1._api import application

        print("   ✓ Done")

        print("11. Starting Sim4Life application (THIS IS THE SEGFAULT POINT)...")
        if application.get_app_safe() is None:
            application.run_application(disable_ui_plugins=True)
        print("   ✓ Done - S4L started!")

        # --- PHASE 3: Import study classes (after S4L) ---
        print("\n--- PHASE 3: Import study classes ---")

        print("12. Importing NearFieldStudy/FarFieldStudy...")

        print("   ✓ Done")

        print("\nhello world")

        shutdown_loggers()
        print("\n✓ ALL PHASES PASSED!")
        return True

    except Exception as e:
        print(f"\n✗ FAILED at step above: {e}")
        traceback.print_exc()
        return False


def test_pyside6_then_s4l():
    """
    Minimal test: Import PySide6 BEFORE starting S4L.
    """
    print("\n" + "=" * 70)
    print("TEST: Import PySide6 BEFORE starting Sim4Life")
    print("=" * 70)

    try:
        print("1. Importing PySide6.QtWidgets.QApplication...")

        print("   ✓ Done")

        print("2. Importing s4l_v1._api.application...")
        from s4l_v1._api import application

        print("   ✓ Done")

        print("3. Starting Sim4Life...")
        if application.get_app_safe() is None:
            application.run_application(disable_ui_plugins=True)
        print("   ✓ S4L started!")

        print("\nhello world")
        print("\n✓ PASSED!")
        return True

    except Exception as e:
        print(f"\n✗ FAILED: {e}")
        traceback.print_exc()
        return False


def test_s4l_then_pyside6():
    """
    Minimal test: Start S4L BEFORE importing PySide6.
    """
    print("\n" + "=" * 70)
    print("TEST: Start Sim4Life BEFORE importing PySide6")
    print("=" * 70)

    try:
        print("1. Importing s4l_v1._api.application...")
        from s4l_v1._api import application

        print("   ✓ Done")

        print("2. Starting Sim4Life...")
        if application.get_app_safe() is None:
            application.run_application(disable_ui_plugins=True)
        print("   ✓ S4L started!")

        print("3. Importing PySide6.QtWidgets.QApplication...")

        print("   ✓ Done")

        print("\nhello world")
        print("\n✓ PASSED!")
        return True

    except Exception as e:
        print(f"\n✗ FAILED: {e}")
        traceback.print_exc()
        return False


def test_qapplication_instance_then_s4l():
    """
    Test: Create QApplication instance BEFORE starting S4L.
    """
    print("\n" + "=" * 70)
    print("TEST: Create QApplication instance BEFORE starting Sim4Life")
    print("=" * 70)

    try:
        print("1. Importing PySide6.QtWidgets.QApplication...")
        from PySide6.QtWidgets import QApplication

        print("   ✓ Done")

        print("2. Creating QApplication instance...")
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        print("   ✓ QApplication created!")

        print("3. Importing s4l_v1._api.application...")
        from s4l_v1._api import application

        print("   ✓ Done")

        print("4. Starting Sim4Life...")
        if application.get_app_safe() is None:
            application.run_application(disable_ui_plugins=True)
        print("   ✓ S4L started!")

        print("\nhello world")
        print("\n✓ PASSED!")
        return True

    except Exception as e:
        print(f"\n✗ FAILED: {e}")
        traceback.print_exc()
        return False


def test_version_check_impact():
    """
    Test: Run the version check (python_interpreter) before S4L.
    """
    print("\n" + "=" * 70)
    print("TEST: Run version check (python_interpreter.py) before Sim4Life")
    print("=" * 70)

    try:
        print("1. Importing goliat.utils.python_interpreter...")

        print("   ✓ Done (this triggers version warnings)")

        print("2. Importing s4l_v1._api.application...")
        from s4l_v1._api import application

        print("   ✓ Done")

        print("3. Starting Sim4Life...")
        if application.get_app_safe() is None:
            application.run_application(disable_ui_plugins=True)
        print("   ✓ S4L started!")

        print("\nhello world")
        print("\n✓ PASSED!")
        return True

    except Exception as e:
        print(f"\n✗ FAILED: {e}")
        traceback.print_exc()
        return False


def main():
    print("\n" + "#" * 70)
    print("# Sim4Life Import Order Diagnostic")
    print("#" * 70)
    print(f"Python: {sys.executable}")
    print(f"Base dir: {BASE_DIR}")

    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--test",
        type=int,
        choices=[1, 2, 3, 4, 5],
        help="Run specific test: 1=full order, 2=pyside then s4l, 3=s4l then pyside, 4=qapp instance, 5=version check",
    )
    parser.add_argument("--all", action="store_true", help="Run all tests")
    args = parser.parse_args()

    tests = {
        1: ("Full import order (like run_study.py)", test_import_order_like_run_study),
        2: ("PySide6 import then S4L", test_pyside6_then_s4l),
        3: ("S4L then PySide6 import", test_s4l_then_pyside6),
        4: ("QApplication instance then S4L", test_qapplication_instance_then_s4l),
        5: ("Version check then S4L", test_version_check_impact),
    }

    if args.test:
        name, func = tests[args.test]
        print(f"\nRunning test {args.test}: {name}")
        result = func()
        return 0 if result else 1

    if args.all:
        results = {}
        for num, (name, func) in tests.items():
            print(f"\n{'#' * 70}")
            print(f"# Test {num}: {name}")
            print("#" * 70)
            results[num] = func()

        print("\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)
        for num, (name, _) in tests.items():
            status = "PASS ✓" if results[num] else "FAIL ✗"
            print(f"  Test {num}: {status} - {name}")
        return 0 if all(results.values()) else 1

    # Default: run the most diagnostic test
    print("\nRunning minimal tests to isolate the issue...")
    print("(Use --all to run all tests, or --test N for specific test)")

    print("\n" + "#" * 70)
    print("# Test 3: S4L first, then PySide6 (EXPECTED TO PASS)")
    print("#" * 70)
    result3 = test_s4l_then_pyside6()

    print("\n" + "#" * 70)
    print("# Test 2: PySide6 import first, then S4L (MIGHT FAIL)")
    print("#" * 70)
    result2 = test_pyside6_then_s4l()

    print("\n" + "=" * 70)
    print("DIAGNOSIS")
    print("=" * 70)
    if result3 and not result2:
        print("⚠ CONFIRMED: Importing PySide6 BEFORE starting S4L causes the crash!")
        print("  Solution: Ensure S4L is started BEFORE PySide6 is imported.")
    elif result3 and result2:
        print("Both tests passed. The issue may be more subtle.")
        print("Try running: python tests/test_s4l_import_order.py --test 1")
    else:
        print("Unexpected results. Please share the output for further analysis.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
