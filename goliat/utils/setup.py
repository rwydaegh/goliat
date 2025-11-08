"""Setup utilities for initializing the GOLIAT environment.

This module provides functions for checking Python interpreter, installing the package,
and preparing data files needed for studies.
"""

import logging
import os
import platform
import subprocess
import sys


def check_package_installed():
    """Check if goliat is installed as a package (editable or regular)."""
    try:
        import importlib.util

        # Check if goliat module can be imported
        spec = importlib.util.find_spec("goliat")
        if spec is None:
            return False
        # Check if goliat is installed via pip by checking pip list
        import json

        try:
            result = subprocess.run([sys.executable, "-m", "pip", "list", "--format=json"], capture_output=True, text=True, check=True)

            installed_packages = json.loads(result.stdout)
            # Check if goliat is in the pip list
            return any(pkg["name"].lower() == "goliat" for pkg in installed_packages)
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            # Fallback: check if .egg-info exists in project root
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
            egg_info_dir = os.path.join(base_dir, "goliat.egg-info")
            return os.path.exists(egg_info_dir)
    except ImportError:
        return False


def check_repo_root():
    """
    Checks if the script is running from the root of the repository.
    It does this by checking for the existence of 'configs/' and 'goliat/' directories.
    """
    is_root = os.path.isdir("configs") and os.path.isdir("goliat")
    if not is_root:
        logging.error("This script must be run from the root directory of the GOLIAT repository.")
        sys.exit(1)


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
            import glob

            matches = glob.glob(search_pattern)
            for match in matches:
                if os.path.isdir(match):
                    found_python_dirs.append(match)

    return found_python_dirs


def update_bashrc(selected_python_path):
    """
    Creates/updates a project-local .bashrc file with PATH entries for Sim4Life Python.

    This creates a .bashrc file in the project directory (non-intrusive).
    Users can optionally copy this to their home directory (~/.bashrc) during setup
    to make Sim4Life Python available automatically in all bash sessions.
    """
    bashrc_path = os.path.join(os.getcwd(), ".bashrc")

    # Strip any existing quotes from the input path
    selected_python_path = selected_python_path.strip().strip('"').strip("'")

    # Prepare the new path lines
    drive, path_rest = os.path.splitdrive(selected_python_path)
    # On Linux, os.path.splitdrive may not split Windows paths correctly
    # If drive is empty, extract it manually from the path
    if not drive and path_rest:
        # Check if path starts with a drive letter (e.g., "C:\...")
        if len(path_rest) >= 2 and path_rest[1] == ":":
            drive = path_rest[0:2]  # Get "C:"
            path_rest = path_rest[2:]  # Get rest after "C:"

    # Replace backslashes with forward slashes (works on both Windows and Linux)
    path_rest_normalized = path_rest.replace("\\", "/")
    # Remove colon from drive letter (C: -> C) for bash path conversion
    drive_letter = drive.replace(":", "").upper() if drive else ""
    bash_path = f"/{drive_letter}{path_rest_normalized}"

    # Write BOTH Python and Scripts directories to PATH
    # Python directory: for python.exe itself
    python_line = f'export PATH="{bash_path}:$PATH"\n'
    # Scripts directory: for pip-installed executables like goliat.exe
    scripts_line = f'export PATH="{bash_path}/Scripts:$PATH"\n'

    # Overwrite the file with both paths
    with open(bashrc_path, "w") as f:
        f.write(python_line)
        f.write(scripts_line)

    logging.info("'.bashrc' has been updated. Please restart your shell or run 'source .bashrc'.")


def prompt_copy_bashrc_to_home(base_dir):
    """
    Prompts user if they want to copy project .bashrc to their home directory.
    This makes Sim4Life Python available automatically in all new bash sessions.
    """
    project_bashrc = os.path.join(base_dir, ".bashrc")
    home_bashrc = os.path.join(os.path.expanduser("~"), ".bashrc")

    # Only prompt if project .bashrc exists
    if not os.path.exists(project_bashrc):
        return

    print("\n" + "=" * 80)
    print("Optional: Make Sim4Life Python available automatically")
    print("=" * 80)
    print("GOLIAT has created a .bashrc file in the project directory.")
    print("This file adds Sim4Life Python to your PATH.")
    print()
    print("OPTION 1 (Recommended for beginners):")
    print("  Copy this configuration to your home directory (~/.bashrc)")
    print("  ✓ Sim4Life Python will be available automatically in ALL new bash windows")
    print("  ✓ You won't need to remember to run 'source .bashrc' each time")
    print("  ⚠ This modifies your global bash configuration")
    print()
    print("OPTION 2 (Default):")
    print("  Keep using the project-local .bashrc file")
    print("  ✓ Non-intrusive - doesn't modify your global bash config")
    print("  ⚠ You must run 'source .bashrc' each time you open a new bash terminal")
    print("     (or navigate to the project directory and source it)")
    print()

    response = input("Copy .bashrc to your home directory? [y/N]: ").strip().lower()

    if response in ["y", "yes"]:
        # Read project .bashrc content
        try:
            with open(project_bashrc, "r", encoding="utf-8") as f:
                bashrc_content = f.read()
        except Exception as e:
            logging.warning(f"Could not read project .bashrc: {e}")
            return

        # Check if content already exists in home .bashrc
        existing_content = ""
        if os.path.exists(home_bashrc):
            try:
                with open(home_bashrc, "r", encoding="utf-8") as f:
                    existing_content = f.read()
            except Exception as e:
                logging.warning(f"Could not read existing ~/.bashrc: {e}")

        # Check if Sim4Life paths are already present
        if "Sim4Life" in existing_content or any(
            line.strip() in existing_content for line in bashrc_content.split("\n") if line.strip() and not line.strip().startswith("#")
        ):
            print("\n⚠ Sim4Life Python paths already found in ~/.bashrc")
            overwrite = input("  Do you want to update them? [y/N]: ").strip().lower()
            if overwrite not in ["y", "yes"]:
                print("  Skipped. Using existing ~/.bashrc configuration.")
                return

        # Append to home .bashrc (or create if doesn't exist)
        try:
            with open(home_bashrc, "a", encoding="utf-8") as f:
                f.write("\n# GOLIAT: Sim4Life Python PATH (added automatically)\n")
                f.write(bashrc_content)
                f.write("\n")

            print("\n✓ Copied .bashrc configuration to ~/.bashrc")
            print("  New bash windows will automatically have Sim4Life Python in PATH.")
            print("  You can remove these lines from ~/.bashrc anytime if needed.")
        except Exception as e:
            logging.error(f"Failed to write to ~/.bashrc: {e}")
            print(f"\n⚠ Could not write to ~/.bashrc: {e}")
            print("  You can manually copy the content from .bashrc to ~/.bashrc if desired.")
    else:
        print("\n✓ Keeping project-local .bashrc")
        print("  Remember to run 'source .bashrc' when opening new bash terminals,")
        print("  or navigate to the project directory first.")
        print("  You can manually copy .bashrc to ~/.bashrc later if desired.")


def check_python_interpreter():
    """
    Checks if the correct Sim4Life Python interpreter is being used.
    If not, it prompts the user to select a valid one and updates .bashrc.
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

        update_bashrc(selected_python)

        print(
            "\n .bashrc file updated. Please restart your terminal, run source .bashrc, and run the script again this time with the correct python."
        )
        sys.exit(0)

    except (ValueError, IndexError):
        print("Invalid selection. Exiting.")
        sys.exit(1)


def prepare_data(base_dir):
    """
    Ensures all necessary data is downloaded and prepared.
    """
    from .data import download_and_extract_data

    data_dir = os.path.join(base_dir, "data")
    phantoms_dir = os.path.join(data_dir, "phantoms")
    if not os.path.exists(phantoms_dir) or len(os.listdir(phantoms_dir)) < 4:
        logging.info("Phantoms directory is missing or incomplete. Downloading phantoms...")
        download_and_extract_data(base_dir, logging.getLogger(), aws=False)  # Always download standard phantoms
    else:
        logging.info("Phantoms already exist. Skipping download.")

    # If on AWS, download the extra phantom file
    if "aws" in platform.release():
        logging.info("AWS environment detected. Downloading additional phantom...")
        download_and_extract_data(base_dir, logging.getLogger(), aws=True)

    centered_dir = os.path.join(data_dir, "antennas", "centered")
    if not os.path.exists(centered_dir) or not os.listdir(centered_dir):
        logging.info("Centered antenna directory is empty. Preparing antennas...")
        prepare_antennas_script = os.path.join(base_dir, "scripts", "prepare_antennas.py")
        python_exe = sys.executable
        subprocess.run([python_exe, prepare_antennas_script], check=True)
    else:
        logging.info("Centered antennas already exist. Skipping preparation.")


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
            check_python_interpreter()  # This function now handles AWS detection internally
            # Prompt user about copying .bashrc to home directory (optional)
            prompt_copy_bashrc_to_home(base_dir)
        prepare_data(base_dir)
        with open(lock_file, "w") as f:
            f.write("Setup complete.")
    else:
        # Skip interpreter check in CI/test environment
        if not os.environ.get("CI") and not os.environ.get("PYTEST_CURRENT_TEST"):
            check_python_interpreter()  # This function now handles AWS detection internally
