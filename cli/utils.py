"""Utility functions for CLI commands."""

import os


def get_base_dir():
    """Get base directory, preferring current working directory.

    For PyPI installs, users run commands from their working directory where
    configs/ and data/ are located. For editable installs, this also works
    when running from repo root.

    The function checks for both configs/ and data/ directories to ensure
    we're in the right location. If not found in cwd, it searches upwards
    from cwd to handle cases where commands are run from subdirectories.

    Returns:
        Base directory path (usually current working directory).
    """

    def _is_goliat_dir(path):
        """Check if a directory looks like a GOLIAT project root."""
        configs_dir = os.path.join(path, "configs")
        data_dir = os.path.join(path, "data")
        return os.path.isdir(configs_dir) and os.path.isdir(data_dir)

    cwd = os.getcwd()

    # Check if cwd is a GOLIAT project directory
    if _is_goliat_dir(cwd):
        return cwd

    # Search upwards from cwd for GOLIAT project directory
    # This handles cases where commands are run from subdirectories
    current = os.path.abspath(cwd)
    while True:
        parent = os.path.dirname(current)
        if parent == current:  # Reached filesystem root
            break
        if _is_goliat_dir(parent):
            return parent
        current = parent

    # Fallback: use cwd anyway (will fail with helpful error messages if wrong)
    # This is better than falling back to package location which would be wrong
    # for PyPI installs (would point to site-packages/)
    return cwd
