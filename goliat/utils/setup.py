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

# Import config_setup
from .config_setup import setup_configs

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
    - Sets up config files in current directory.
    - Prepares data files.
    """
    # Skip everything in CI/test environment
    if os.environ.get("CI") or os.environ.get("PYTEST_CURRENT_TEST"):
        return

    # Determine base_dir: prefer cwd if it looks like a repo, otherwise use cwd for PyPI installs
    cwd = os.getcwd()
    if os.path.isdir(os.path.join(cwd, "configs")) and os.path.isdir(os.path.join(cwd, "goliat")):
        # Running from repo root
        base_dir = cwd
    else:
        # Running from somewhere else (PyPI install or different directory)
        base_dir = cwd

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
        # Only try editable install if we're in a repo structure
        if os.path.isdir(os.path.join(cwd, "goliat")) and os.path.exists(os.path.join(cwd, "pyproject.toml")):
            print("\nInstalling GOLIAT package and dependencies in editable mode...")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", "-e", base_dir])
                print("✓ GOLIAT package installed successfully!")
            except subprocess.CalledProcessError as e:
                logging.error(f"Failed to install GOLIAT package: {e}")
                sys.exit(1)
        else:
            print("\nInstalling GOLIAT package and dependencies...")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", "goliat"])
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

    # Setup config files in current directory (only if they don't exist)
    configs_dir = os.path.join(base_dir, "configs")
    configs_exist = os.path.isdir(configs_dir) and any(
        f.endswith(".json") for f in os.listdir(configs_dir) if os.path.isfile(os.path.join(configs_dir, f))
    )

    if not configs_exist:
        print("\nSetting up configuration files...")
        try:
            setup_configs(base_dir=base_dir, overwrite=False)
        except Exception as e:
            logging.warning(f"Could not set up config files: {e}")
            logging.info("You can manually copy configs from the repository if needed.")

    # Rest of setup (data preparation, etc.)
    data_dir = os.path.join(base_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    lock_file = os.path.join(data_dir, ".setup_done")

    # Always run prepare_data() - it has its own checks to determine what needs to be done
    # This allows repair of incomplete setups (e.g., if user canceled during antenna preparation)
    prepare_data(base_dir)

    # Only run expensive one-time checks if lock file doesn't exist
    if not os.path.exists(lock_file):
        # Only check repo root if we're in a repo structure (for editable installs)
        if os.path.isdir(os.path.join(base_dir, "goliat")):
            try:
                check_repo_root()
            except SystemExit:
                # If not in repo root, that's OK for PyPI installs
                pass
        # Skip interpreter check in CI/test environment
        if not os.environ.get("CI") and not os.environ.get("PYTEST_CURRENT_TEST"):
            check_python_interpreter(base_dir=base_dir)  # This function now handles AWS detection internally
            # Prompt user about copying .bashrc to home directory (optional)
            prompt_copy_bashrc_to_home(base_dir)
        # Create lock file after all one-time checks pass
        with open(lock_file, "w") as f:
            f.write("Setup complete.")
    else:
        # Skip interpreter check in CI/test environment
        if not os.environ.get("CI") and not os.environ.get("PYTEST_CURRENT_TEST"):
            check_python_interpreter(base_dir=base_dir)  # This function now handles AWS detection internally
