"""Sim4Life Python interpreter detection and management.

This module provides functions for finding and checking Sim4Life Python interpreters.
"""

import glob
import logging
import os
import platform
import sys

from .bashrc import update_bashrc


def find_sim4life_python_executables():
    """
    Scans all drives for Sim4Life Python directories (version 8.2).
    Windows-only function - should not be called on Linux/AWS.
    """
    if sys.platform != "win32":
        return []

    drives = [f"{d}:\\" for d in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if os.path.exists(f"{d}:\\")]
    found_python_dirs = []

    for drive in drives:
        pattern = os.path.join(drive, "Program Files", "Sim4Life_8.2*", "Python")
        found_python_dirs.extend(m for m in glob.glob(pattern) if os.path.isdir(m))

    return found_python_dirs


def _verify_s4l_root(path):
    """Verify that a path is a valid Sim4Life root directory."""
    return path and os.path.exists(os.path.join(path, "Solvers", "iSolve.exe"))


def find_sim4life_root():
    """
    Finds the Sim4Life installation root directory.

    Works for both direct Sim4Life Python usage and venvs created with
    Sim4Life Python using --system-site-packages.

    Returns:
        str: Path to Sim4Life root directory (e.g., C:\\Program Files\\Sim4Life_8.2.0.16876)

    Raises:
        FileNotFoundError: If Sim4Life installation cannot be found
    """
    # Method 1: If sys.executable is directly Sim4Life Python, go up two directories
    if "Sim4Life" in sys.executable:
        s4l_root = os.path.dirname(os.path.dirname(sys.executable))
        if _verify_s4l_root(s4l_root):
            return s4l_root

    # Method 2: If in a venv, check sys.base_prefix (points to original Python that created venv)
    if hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix:
        base_prefix = os.path.normpath(sys.base_prefix)
        if "Sim4Life" in base_prefix:
            # Try parent directory if base_prefix is Python directory, otherwise try both
            candidates = (
                [os.path.dirname(base_prefix)] if os.path.basename(base_prefix) == "Python" else [base_prefix, os.path.dirname(base_prefix)]
            )
            for s4l_root in candidates:
                if _verify_s4l_root(s4l_root):
                    return s4l_root

    raise FileNotFoundError("Could not find Sim4Life installation root directory. Please ensure Sim4Life is installed and accessible.")


def check_python_interpreter(base_dir=None):
    """
    Checks if the correct Sim4Life Python interpreter is being used.
    If not, it prompts the user to select a valid one and updates .bashrc.

    Args:
        base_dir: Optional base directory of the project. If provided, will check
                  user preferences for auto-syncing .bashrc to home directory.
    """
    # Bypass check if running in the Sim4Life cloud environment
    if "aws" in platform.release():
        logging.info("AWS environment detected, bypassing Sim4Life interpreter check.")
        return

    viable_pythons = find_sim4life_python_executables()

    # Check if s4l_v1 can be imported (indicates Sim4Life packages are available)
    # This handles venvs created with Sim4Life Python using --system-site-packages
    try:
        import s4l_v1  # noqa: F401

        s4l_v1_available = True
    except ImportError:
        s4l_v1_available = False

    if "Sim4Life" in sys.executable:
        sys_executable_dir = os.path.normpath(os.path.dirname(sys.executable))
        viable_dirs = [os.path.normpath(p) for p in viable_pythons]
        if sys_executable_dir in viable_dirs:
            logging.info("Correct Sim4Life Python interpreter detected.")
            return
        logging.warning(f"You are using an unsupported Sim4Life Python interpreter: {sys.executable}")
        logging.warning("This project requires Sim4Life version 8.2.")
    elif s4l_v1_available:
        logging.info("Sim4Life Python packages detected (venv with system-site-packages).")
        return
    else:
        logging.warning("You are not using a Sim4Life Python interpreter.")

    if not viable_pythons:
        logging.error("No viable Sim4Life Python executables (v8.2) found on this system.")
        sys.exit(1)

    print("Found the following supported Sim4Life Python executables (8.2):")
    for i, p in enumerate(viable_pythons):
        print(f"  [{i + 1}] {p}")

    try:
        choice = input("Select the version to use (e.g., '1') or press Enter to cancel: ")
        if not choice:
            print("Operation cancelled by user.")
            sys.exit(0)

        selected_index = int(choice) - 1
        if not 0 <= selected_index < len(viable_pythons):
            raise ValueError

        selected_python = viable_pythons[selected_index]

        update_bashrc(selected_python, base_dir=base_dir)

        print(
            "\n .bashrc file updated. Please restart your terminal, run source .bashrc, and run the script again this time with the correct python."
        )
        sys.exit(0)

    except (ValueError, IndexError):
        print("Invalid selection. Exiting.")
        sys.exit(1)
