"""Utility functions for GOLIAT.

This module re-exports commonly used utilities from submodules for backward compatibility.
All existing imports from `goliat.utils` will continue to work.
"""

# Re-export all commonly used utilities from core module
from .core import (
    StudyCancelledError,
    Profiler,
    format_time,
    non_blocking_sleep,
    profile,
    ensure_s4l_running,
    open_project,
    delete_project_file,
    suppress_stdout_stderr,
)

# Also expose setup utilities for convenience
from .setup import initial_setup

# Skin voxel utilities for auto-induced exposure
from .skin_voxel_utils import (
    extract_skin_voxels,
    get_skin_voxel_coordinates,
)

# Version detection utilities
from .version import (
    get_sim4life_version,
    get_sim4life_major_minor,
    get_version_display_string,
    is_sim4life_92_or_later,
    is_version_supported,
)

__all__ = [
    "StudyCancelledError",
    "Profiler",
    "format_time",
    "non_blocking_sleep",
    "profile",
    "ensure_s4l_running",
    "open_project",
    "delete_project_file",
    "suppress_stdout_stderr",
    "initial_setup",
    "extract_skin_voxels",
    "get_skin_voxel_coordinates",
    # Version utilities
    "get_sim4life_version",
    "get_sim4life_major_minor",
    "get_version_display_string",
    "is_sim4life_92_or_later",
    "is_version_supported",
]
