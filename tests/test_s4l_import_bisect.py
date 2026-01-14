"""
Binary search test to find exactly which GOLIAT import causes the S4L 9.2 segfault.

From previous testing we know:
- PySide6 + S4L alone: PASSES
- PySide6 + GOLIAT imports + S4L: SEGFAULTS

This test isolates which specific import causes the crash.

Run with:
    python tests/test_s4l_import_bisect.py
"""

import sys
import os

# Get base directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)


def test_with_imports(*import_steps):
    """
    Test S4L startup with specific imports done beforehand.
    Returns True if S4L starts successfully, False otherwise.
    """
    print(f"\n{'=' * 70}")
    print(f"Testing with imports: {', '.join(import_steps) if import_steps else 'None'}")
    print("=" * 70)

    try:
        # Always import PySide6 first (we know this alone doesn't cause the crash)
        print("0. Importing PySide6...")

        print("   ✓ Done")

        for step in import_steps:
            print(f"   Importing {step}...")
            if step == "config":
                pass
            elif step == "logging_manager":
                from goliat.logging_manager import setup_loggers
            elif step == "base_study":
                pass
            elif step == "gui_manager":
                pass
            elif step == "matplotlib_qt5":
                import matplotlib

                matplotlib.use("Qt5Agg")
            elif step == "setup_loggers":
                from goliat.logging_manager import setup_loggers

                progress_logger, verbose_logger, _ = setup_loggers()
            elif step == "initial_setup":
                from goliat.utils.setup import initial_setup
            elif step == "run_initial_setup":
                from goliat.utils.setup import initial_setup

                initial_setup()
            print(f"   ✓ {step} imported")

        print("\n   Starting Sim4Life...")
        from s4l_v1._api import application

        if application.get_app_safe() is None:
            application.run_application(disable_ui_plugins=True)
        print("   ✓ S4L started!")

        print("\n   hello world")
        print("\n✓ PASSED!")
        return True

    except Exception as e:
        print(f"\n✗ FAILED: {e}")
        import traceback

        traceback.print_exc()
        return False


def run_bisect():
    """
    Binary search through imports to find the culprit.
    """
    print("\n" + "#" * 70)
    print("# Binary Search: Finding the problematic import")
    print("#" * 70)

    # List of imports in order (from run_study.py)
    all_imports = [
        "config",  # goliat.config.Config
        "logging_manager",  # goliat.logging_manager
        "base_study",  # goliat.studies.base_study.StudyCancelledError
        "gui_manager",  # goliat.gui_manager (ProgressGUI, QueueGUI)
        "setup_loggers",  # Actually calling setup_loggers()
    ]

    print("\nTesting imports one by one to find the culprit...")
    print("(If a test segfaults, that import is the problem)")

    results = {}

    for i, import_name in enumerate(all_imports):
        # Test with all imports up to and including this one
        imports_to_test = all_imports[: i + 1]
        print(f"\n{'#' * 70}")
        print(f"# Testing with first {i + 1} import(s): {imports_to_test}")
        print("#" * 70)

        result = test_with_imports(*imports_to_test)
        results[import_name] = result

        if not result:
            print(f"\n⚠ FOUND IT! The segfault is caused by: {import_name}")
            print(f"   This was import #{i + 1} in the sequence.")
            return

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    for name, passed in results.items():
        print(f"  {name}: {'PASS ✓' if passed else 'FAIL ✗'}")

    if all(results.values()):
        print("\nAll individual imports passed!")
        print("The issue might be in initial_setup() or something else.")
        print("\nTrying with initial_setup import...")
        test_with_imports("initial_setup", *all_imports)


def run_single_import_tests():
    """
    Test each import individually (not cumulatively).
    """
    print("\n" + "#" * 70)
    print("# Testing each import INDIVIDUALLY")
    print("#" * 70)

    imports = [
        "config",
        "logging_manager",
        "base_study",
        "gui_manager",
        "setup_loggers",
    ]

    results = {}
    for imp in imports:
        print(f"\n{'#' * 70}")
        print(f"# Testing ONLY: {imp}")
        print("#" * 70)
        results[imp] = test_with_imports(imp)

    print("\n" + "=" * 70)
    print("INDIVIDUAL IMPORT RESULTS")
    print("=" * 70)
    for name, passed in results.items():
        print(f"  {name}: {'PASS ✓' if passed else 'FAIL ✗'}")


def main():
    print("\n" + "#" * 70)
    print("# Sim4Life Import Bisect Diagnostic")
    print("#" * 70)
    print(f"Python: {sys.executable}")
    print(f"Base dir: {BASE_DIR}")

    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--single", action="store_true", help="Test each import individually (not cumulative)")
    parser.add_argument(
        "--import",
        dest="single_import",
        type=str,
        choices=[
            "config",
            "logging_manager",
            "base_study",
            "gui_manager",
            "setup_loggers",
            "initial_setup",
            "run_initial_setup",
            "matplotlib_qt5",
        ],
        help="Test a specific single import",
    )
    args = parser.parse_args()

    if args.single_import:
        result = test_with_imports(args.single_import)
        return 0 if result else 1

    if args.single:
        run_single_import_tests()
        return 0

    # Default: run cumulative bisect
    run_bisect()
    return 0


if __name__ == "__main__":
    sys.exit(main())
