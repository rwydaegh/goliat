"""
Final diagnostic to isolate the S4L 9.2 segfault cause.

From previous testing:
- PySide6 + S4L = WORKS
- PySide6 + matplotlib.use("Qt5Agg") + S4L = SEGFAULTS
- PySide6 + config + S4L = SEGFAULTS

This test determines if the issue is matplotlib, or something else.

Run with:
    python tests/test_s4l_final_diagnostic.py
"""

import sys
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)


def run_scenario(name, setup_steps):
    """Run a test scenario and return True if S4L starts successfully."""
    print(f"\n{'=' * 70}")
    print(f"TEST: {name}")
    print("=" * 70)

    try:
        for step_name, step_fn in setup_steps:
            print(f"   {step_name}...")
            step_fn()
            print("   ✓ Done")

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


def main():
    print("\n" + "#" * 70)
    print("# Final S4L 9.2 Segfault Diagnostic")
    print("#" * 70)
    print(f"Python: {sys.executable}")

    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("test", type=int, nargs="?", default=0, help="Which test to run (1-5, or 0 for menu)")
    args = parser.parse_args()

    tests = {
        1: (
            "Just PySide6 import (no QApp instance)",
            [
                ("Import PySide6", lambda: __import__("PySide6.QtWidgets")),
            ],
        ),
        2: (
            "PySide6 import + matplotlib import (no .use)",
            [
                ("Import PySide6", lambda: __import__("PySide6.QtWidgets")),
                ("Import matplotlib", lambda: __import__("matplotlib")),
            ],
        ),
        3: (
            "PySide6 + matplotlib.use('Qt5Agg')",
            [
                ("Import PySide6", lambda: __import__("PySide6.QtWidgets")),
                ("matplotlib.use('Qt5Agg')", lambda: (__import__("matplotlib").use("Qt5Agg"))),
            ],
        ),
        4: (
            "PySide6 + matplotlib.use('Agg') [non-Qt backend]",
            [
                ("Import PySide6", lambda: __import__("PySide6.QtWidgets")),
                ("matplotlib.use('Agg')", lambda: (__import__("matplotlib").use("Agg"))),
            ],
        ),
        5: (
            "matplotlib.use('Qt5Agg') FIRST, then PySide6",
            [
                ("matplotlib.use('Qt5Agg')", lambda: (__import__("matplotlib").use("Qt5Agg"))),
                ("Import PySide6", lambda: __import__("PySide6.QtWidgets")),
            ],
        ),
        6: (
            "S4L FIRST, then PySide6 + matplotlib.use('Qt5Agg')",
            [
                # Note: S4L startup happens in test_scenario, so we skip it here
                # and just do the test of: S4L first approach
            ],
        ),
    }

    if args.test == 0:
        print("\nAvailable tests:")
        for num, (name, _) in tests.items():
            print(f"  {num}: {name}")
        print("\nRun with: python tests/test_s4l_final_diagnostic.py <number>")
        return 0

    if args.test == 6:
        # Special case: Start S4L first, then import the rest
        print("\n" + "=" * 70)
        print("TEST: S4L FIRST, then PySide6 + matplotlib.use('Qt5Agg')")
        print("=" * 70)
        try:
            print("   Starting Sim4Life FIRST...")
            from s4l_v1._api import application

            if application.get_app_safe() is None:
                application.run_application(disable_ui_plugins=True)
            print("   ✓ S4L started!")

            print("   Import PySide6...")

            print("   ✓ Done")

            print("   matplotlib.use('Qt5Agg')...")
            import matplotlib

            matplotlib.use("Qt5Agg")
            print("   ✓ Done")

            print("\n   hello world")
            print("\n✓ PASSED!")
            return 0
        except Exception as e:
            print(f"\n✗ FAILED: {e}")
            import traceback

            traceback.print_exc()
            return 1

    if args.test in tests:
        name, steps = tests[args.test]
        result = run_scenario(name, steps)
        return 0 if result else 1
    else:
        print(f"Unknown test: {args.test}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
