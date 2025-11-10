"""Setup utilities for initializing the GOLIAT environment.

This module provides the main initial_setup function that orchestrates all setup procedures.
Individual setup functions are split into separate modules for better organization.
"""

import logging
import os
import subprocess
import sys

from .bashrc import prompt_copy_bashrc_to_home, update_bashrc
from .data_prep import prepare_data
from .package import check_package_installed, check_repo_root
from .python_interpreter import check_python_interpreter, find_sim4life_python_executables

__all__ = [
    "initial_setup",
    "check_package_installed",
    "check_repo_root",
    "find_sim4life_python_executables",
    "update_bashrc",
]


def initial_setup():
    """
    Performs all initial checks and setup procedures.
    - Ensures correct python interpreter is used.
    - Prompts user before installing dependencies.
    - Installs package in editable mode if not already installed.
    - Prepares data files.
    """
    # Skip everything in CI/test environment
    if os.environ.get("CI") or os.environ.get("PYTEST_CURRENT_TEST"):
        return

    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))

    # Check if goliat is installed as a package
    package_installed = check_package_installed()

    if not package_installed:
        # Prompt user for permission to install
        print("=" * 80)
        print("GOLIAT Package Installation")
        print("=" * 80)
        print("GOLIAT needs to be installed as a Python package to work properly.")
        print("This will install:")
        print("  - Python dependencies from pyproject.toml")
        print("  - GOLIAT package in editable mode (allows code modifications)")
        print()
        print("This is a one-time setup. You can modify the code and changes will")
        print("be reflected immediately without reinstalling.")
        print()
        response = input("Do you want to install dependencies and GOLIAT package? [Y/n]: ").strip().lower()

        if response and response != "y" and response != "yes":
            print("Installation cancelled. GOLIAT cannot run without installation.")
            sys.exit(1)

        # Install editable package (this installs dependencies from pyproject.toml automatically)
        print("\nInstalling GOLIAT package and dependencies in editable mode...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-e", base_dir])
            print("✓ GOLIAT package installed successfully!")
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to install GOLIAT package: {e}")
            sys.exit(1)

    # Verify package is importable
    try:
        import importlib.util

        spec = importlib.util.find_spec("goliat")
        if spec is None:
            raise ImportError("goliat module not found")
    except ImportError:
        logging.error("GOLIAT package could not be imported. Please ensure installation completed successfully.")
        sys.exit(1)

    # Rest of setup (data preparation, etc.)
    data_dir = os.path.join(base_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    lock_file = os.path.join(data_dir, ".setup_done")

    if not os.path.exists(lock_file):
        check_repo_root()
        # Skip interpreter check in CI/test environment
        if not os.environ.get("CI") and not os.environ.get("PYTEST_CURRENT_TEST"):
            check_python_interpreter(base_dir=base_dir)  # This function now handles AWS detection internally
            # Prompt user about copying .bashrc to home directory (optional)
            prompt_copy_bashrc_to_home(base_dir)
        prepare_data(base_dir)
        with open(lock_file, "w") as f:
            f.write("Setup complete.")
    else:
        # Skip interpreter check in CI/test environment
        if not os.environ.get("CI") and not os.environ.get("PYTEST_CURRENT_TEST"):
            check_python_interpreter(base_dir=base_dir)  # This function now handles AWS detection internally
