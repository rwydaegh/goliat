"""Package installation and repository checks.

This module provides functions for checking if the GOLIAT package is installed
and verifying the repository structure.
"""

import importlib.util
import json
import logging
import os
import subprocess
import sys


def check_package_installed():
    """Check if goliat is installed as a package (editable or regular)."""
    try:
        # Check if goliat module can be imported
        spec = importlib.util.find_spec("goliat")
        if spec is None:
            return False
        # Check if goliat is installed via pip by checking pip list
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
