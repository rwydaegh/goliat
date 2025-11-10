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
