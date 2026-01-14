"""Sim4Life Python interpreter detection and management.

This module provides functions for finding and checking Sim4Life Python interpreters.

Supported versions:
- 8.2.x: Original supported version
- 9.2.x: Added in 2026

NOT supported:
- 9.0.x: Internal/beta release
"""

import glob
import logging
import os
import platform
import sys

from .bashrc import update_bashrc
from .version import (
    get_sim4life_version,
    get_version_display_string,
    is_sim4life_92_or_later,
    is_version_supported,
    sort_versions_by_preference,
)


def find_sim4life_python_executables():
    """
    Scans all drives for Sim4Life Python directories (versions 8.2 and 9.2).
    Windows-only function - should not be called on Linux/AWS.

    Returns paths sorted by preference (9.2 before 8.2), excluding unsupported
    versions like 9.0.

    Returns:
        list: Sorted list of paths to Sim4Life Python directories.
    """
    if sys.platform != "win32":
        return []

    drives = [f"{d}:\\" for d in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if os.path.exists(f"{d}:\\")]
    found_python_dirs = []

    for drive in drives:
        # Support both 8.x and 9.x versions
        for version_pattern in ["Sim4Life_8.*", "Sim4Life_9.*"]:
            pattern = os.path.join(drive, "Program Files", version_pattern, "Python")
            found_python_dirs.extend(m for m in glob.glob(pattern) if os.path.isdir(m))

    # Sort by preference (9.2 first) and filter out unsupported versions (9.0)
    return sort_versions_by_preference(found_python_dirs)


def _verify_s4l_root(path):
    """Verify that a path is a valid Sim4Life root directory."""
    return path and os.path.exists(os.path.join(path, "Solvers", "iSolve.exe"))


def find_sim4life_root():
    """
    Finds the Sim4Life installation root directory.

    Works for both direct Sim4Life Python usage and venvs created with
    Sim4Life Python using --system-site-packages.

    Returns:
        str: Path to Sim4Life root directory (e.g., C:\\Program Files\\Sim4Life_9.2.0.12345)

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

    Supports Sim4Life 8.2 and 9.2. Version 9.0 is explicitly not supported.

    Args:
        base_dir: Optional base directory of the project. If provided, will check
                  user preferences for auto-syncing .bashrc to home directory.
    """
    # Bypass check if running in the Sim4Life cloud environment
    if "aws" in platform.release():
        logging.info("AWS environment detected, bypassing Sim4Life interpreter check.")
        return

    viable_pythons = find_sim4life_python_executables()

    # Check if s4l_v1 is available without importing it (avoids triggering S4L initialization/license check)
    # This handles venvs created with Sim4Life Python using --system-site-packages
    import importlib.util

    s4l_v1_available = importlib.util.find_spec("s4l_v1") is not None

    if "Sim4Life" in sys.executable:
        sys_executable_dir = os.path.normpath(os.path.dirname(sys.executable))
        viable_dirs = [os.path.normpath(p) for p in viable_pythons]

        # Check if current interpreter is in the list of viable (supported) interpreters
        if sys_executable_dir in viable_dirs:
            detected_version = get_version_display_string()
            if is_sim4life_92_or_later():
                logging.info(f"Sim4Life {detected_version} detected (9.2+ mode enabled).")
            else:
                logging.info(f"Sim4Life {detected_version} detected.")
            return

        # Current interpreter is Sim4Life but not in viable list (e.g., 9.0.x)
        detected_version = get_sim4life_version()
        if detected_version and not is_version_supported(detected_version):
            logging.warning(f"You are using Sim4Life {get_version_display_string()}, which is not officially supported.")
            logging.warning("GOLIAT supports Sim4Life versions 8.2 and 9.2. Version 9.0 is not supported.")
        else:
            logging.warning(f"You are using an unsupported Sim4Life Python interpreter: {sys.executable}")
            logging.warning("GOLIAT supports Sim4Life versions 8.2 and 9.2.")

    elif s4l_v1_available:
        # Running in a venv with system-site-packages
        detected_version = get_version_display_string()
        if is_sim4life_92_or_later():
            logging.info(f"Sim4Life {detected_version} packages detected via venv (9.2+ mode enabled).")
        else:
            logging.info(f"Sim4Life {detected_version} packages detected (venv with system-site-packages).")
        return
    else:
        logging.warning("You are not using a Sim4Life Python interpreter.")

    if not viable_pythons:
        logging.warning("No supported Sim4Life Python executables (v8.2 or v9.2) found on this system.")
        logging.warning("Continuing with current interpreter - some features may not work as expected.")
        return

    # Show helpful header
    print("\n" + "=" * 70)
    print("GOLIAT - Sim4Life Version Selection")
    print("=" * 70)
    print("\nGOLIAT needs to use a Sim4Life Python interpreter.")
    print("The following supported versions were found on your system:\n")

    for i, p in enumerate(viable_pythons):
        # Extract version from path for cleaner display
        import re

        match = re.search(r"Sim4Life[_-](\d+\.\d+\.\d+)", p)
        version_str = match.group(1) if match else "unknown"
        recommended = " (recommended)" if i == 0 else ""
        print(f"  [{i + 1}] Sim4Life {version_str}{recommended}")
        print(f"      Path: {p}")

    print("\n" + "-" * 70)
    print("TIP: Version 9.2 is recommended for new projects.")
    print("     You can change this later by running: goliat config set-version")
    print("-" * 70)

    try:
        choice = input("\nSelect a version (e.g., '1'), or press Enter for recommended: ")

        if not choice:
            # Default to first (recommended) option
            selected_index = 0
            print(f"\nUsing recommended version: {viable_pythons[0]}")
        else:
            selected_index = int(choice) - 1
            if not 0 <= selected_index < len(viable_pythons):
                raise ValueError

        selected_python = viable_pythons[selected_index]

        # Save to preferences
        from .preferences import set_sim4life_python_path

        set_sim4life_python_path(base_dir, selected_python)

        # Update bashrc
        update_bashrc(selected_python, base_dir=base_dir)

        print("\n" + "=" * 70)
        print("SUCCESS! Your Sim4Life version has been configured.")
        print("=" * 70)
        print(f"\nSelected: {selected_python}")
        print("\nNext steps:")
        print("  1. Open a new terminal window")
        print("     (If you haven't synced .bashrc to home, run: source .bashrc)")
        print("  2. Reinstall GOLIAT for the new Python:")
        print("     pip install goliat          # or")
        print("     pip install -e .            # for editable install")
        print("  3. Run your GOLIAT command")
        print("\nTo change versions later, run: goliat config set-version")
        print("=" * 70)
        sys.exit(0)

    except (ValueError, IndexError):
        print("\nInvalid selection. Please enter a number from the list.")
        print("You can run GOLIAT again to retry.")
        sys.exit(1)
