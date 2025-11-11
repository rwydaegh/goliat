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
    Scans all drives for Sim4Life Python directories (versions 8.2 and 9.0).
    Windows-only function - should not be called on Linux/AWS.
    """
    if sys.platform != "win32":
        return []  # Not on Windows, return empty list

    drive_letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    drives = [f"{d}:\\" for d in drive_letters if os.path.exists(f"{d}:\\")]

    found_python_dirs = []

    for drive in drives:
        for version in ["8.2", "9.0"]:
            # Construct a glob pattern to find the Python directory
            search_pattern = os.path.join(drive, "Program Files", f"Sim4Life_{version}*", "Python")

            # Use glob to find matching directories
            matches = glob.glob(search_pattern)
            for match in matches:
                if os.path.isdir(match):
                    found_python_dirs.append(match)

    return found_python_dirs


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
        python_dir = os.path.dirname(sys.executable)
        s4l_root = os.path.dirname(python_dir)
        # Verify Solvers directory exists
        if os.path.exists(os.path.join(s4l_root, "Solvers", "iSolve.exe")):
            return s4l_root

    # Method 2: Find Sim4Life Python directories and use the first one found
    viable_pythons = find_sim4life_python_executables()
    if viable_pythons:
        # Go up one directory from Python directory to get Sim4Life root
        python_dir = viable_pythons[0]
        s4l_root = os.path.dirname(python_dir)
        # Verify Solvers directory exists
        if os.path.exists(os.path.join(s4l_root, "Solvers", "iSolve.exe")):
            return s4l_root

    # Method 3: Try to infer from s4l_v1 module location (if available)
    try:
        import s4l_v1

        # s4l_v1 is typically in Python/Lib/site-packages or similar
        # Try to find Sim4Life root by going up from module location
        if hasattr(s4l_v1, "__file__") and s4l_v1.__file__ is not None:
            module_path = os.path.dirname(os.path.abspath(s4l_v1.__file__))
            # Navigate up from site-packages to find Sim4Life root
            # This is a fallback and may not always work
            current = module_path
            for _ in range(5):  # Limit search depth
                current = os.path.dirname(current)
                if os.path.exists(os.path.join(current, "Solvers", "iSolve.exe")):
                    return current
    except ImportError:
        pass

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

    # Normalize paths for comparison
    normalized_viable_python_dirs = [os.path.normpath(p) for p in viable_pythons]
    normalized_sys_executable_dir = os.path.normpath(os.path.dirname(sys.executable))

    if "Sim4Life" in sys.executable:
        if normalized_sys_executable_dir in normalized_viable_python_dirs:
            logging.info("Correct Sim4Life Python interpreter detected.")
            return
        else:
            logging.warning(f"You are using an unsupported Sim4Life Python interpreter: {sys.executable}")
            logging.warning("This project requires Sim4Life version 8.2 or 9.0.")
    elif s4l_v1_available:
        # Venv created with Sim4Life Python (--system-site-packages) can import s4l_v1
        logging.info("Sim4Life Python packages detected (venv with system-site-packages).")
        return
    else:
        logging.warning("You are not using a Sim4Life Python interpreter.")

    if not viable_pythons:
        logging.error("No viable Sim4Life Python executables (v8.2, v9.0) found on this system.")
        sys.exit(1)

    print("Found the following supported Sim4Life Python executables (8.2 or 9.0):")
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
