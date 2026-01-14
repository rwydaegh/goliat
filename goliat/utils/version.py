"""Sim4Life version detection and compatibility utilities.

This module provides functions for detecting the Sim4Life version and
enabling version-specific behavior throughout GOLIAT.

Supported versions:
- 8.2.x: Original supported version
- 9.2.x: Added in 2026, requires startup order fixes and stdout workarounds

NOT supported:
- 9.0.x: Internal/beta release, not officially supported
"""

import re
import sys
from functools import lru_cache
from typing import Optional, Tuple

# Version constants
SUPPORTED_MAJOR_VERSIONS = [(9, 2), (8, 2)]  # Priority order: prefer 9.2 over 8.2
UNSUPPORTED_VERSIONS = [(9, 0)]  # 9.0 was a transitional release, not supported


@lru_cache(maxsize=1)
def get_sim4life_version() -> Optional[Tuple[int, int, int]]:
    """Detect the current Sim4Life version.

    Tries multiple methods:
    1. From the Python executable path (e.g., C:\\Program Files\\Sim4Life_9.2.0.12345\\Python)
    2. From sys.base_prefix (for venvs with --system-site-packages)
    3. From s4l_v1 module if available

    Returns:
        Tuple of (major, minor, patch) version numbers, or None if not detected.
        Example: (9, 2, 0) for Sim4Life 9.2.0

    Note:
        Results are cached for performance. Call get_sim4life_version.cache_clear()
        to reset if needed (e.g., in tests).
    """
    # Method 1: Check executable path
    version = _parse_version_from_path(sys.executable)
    if version:
        return version

    # Method 2: Check base_prefix (for venvs)
    if hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix:
        version = _parse_version_from_path(sys.base_prefix)
        if version:
            return version

    # Method 3: Try to get from s4l_v1 module (if already imported)
    if "s4l_v1" in sys.modules:
        try:
            import s4l_v1

            version_str = getattr(s4l_v1, "__version__", None) or getattr(s4l_v1, "VERSION", None)
            if version_str:
                return _parse_version_string(version_str)
        except (ImportError, AttributeError):
            pass

    return None


def _parse_version_from_path(path: str) -> Optional[Tuple[int, int, int]]:
    """Extract Sim4Life version from a path containing 'Sim4Life_X.Y.Z'.

    Args:
        path: File system path that may contain Sim4Life version info.

    Returns:
        Tuple of (major, minor, patch) or None if not found.
    """
    if not path:
        return None

    # Match patterns like Sim4Life_8.2.0.16876 or Sim4Life_9.2.0
    match = re.search(r"Sim4Life[_-](\d+)\.(\d+)\.(\d+)", path, re.IGNORECASE)
    if match:
        return (int(match.group(1)), int(match.group(2)), int(match.group(3)))
    return None


def _parse_version_string(version_str: str) -> Optional[Tuple[int, int, int]]:
    """Parse a version string like '9.2.0' into a tuple.

    Args:
        version_str: Version string in format 'X.Y.Z' or 'X.Y.Z.build'.

    Returns:
        Tuple of (major, minor, patch) or None if parsing fails.
    """
    if not version_str:
        return None

    match = re.match(r"(\d+)\.(\d+)\.(\d+)", str(version_str))
    if match:
        return (int(match.group(1)), int(match.group(2)), int(match.group(3)))
    return None


def get_sim4life_major_minor() -> Optional[Tuple[int, int]]:
    """Get just the major.minor version (e.g., (9, 2) for Sim4Life 9.2.x).

    Returns:
        Tuple of (major, minor) or None if version not detected.
    """
    version = get_sim4life_version()
    if version:
        return (version[0], version[1])
    return None


def is_sim4life_92_or_later() -> bool:
    """Check if the current Sim4Life version is 9.2 or later.

    This is useful for enabling 9.2-specific behavior like:
    - Skipping deprecation warnings that were fixed in 9.2
    - Using new API features available only in 9.2+
    - Applying stdout workarounds needed in 9.2+

    Returns:
        True if running on Sim4Life 9.2 or later, False otherwise.
    """
    version = get_sim4life_version()
    if not version:
        return False
    return version >= (9, 2, 0)


def is_version_supported(version: Optional[Tuple[int, int, int]] = None) -> bool:
    """Check if a Sim4Life version is officially supported by GOLIAT.

    Args:
        version: Version tuple to check. If None, checks current version.

    Returns:
        True if the version is supported (8.2.x or 9.2.x), False otherwise.
    """
    if version is None:
        version = get_sim4life_version()

    if version is None:
        return False

    major_minor = (version[0], version[1])

    # Check if it's an unsupported version (like 9.0)
    if major_minor in UNSUPPORTED_VERSIONS:
        return False

    # Check if it's a supported major.minor version
    return major_minor in SUPPORTED_MAJOR_VERSIONS


def get_version_display_string() -> str:
    """Get a human-readable version string for display.

    Returns:
        String like "9.2.0" or "unknown" if version not detected.
    """
    version = get_sim4life_version()
    if version:
        return f"{version[0]}.{version[1]}.{version[2]}"
    return "unknown"


def sort_versions_by_preference(python_paths: list[str]) -> list[str]:
    """Sort a list of Sim4Life Python paths by version preference.

    Prefers newer supported versions (9.2 over 8.2) and filters out
    unsupported versions like 9.0.

    Args:
        python_paths: List of paths to Sim4Life Python directories.

    Returns:
        Sorted list with preferred versions first, unsupported versions removed.
    """

    def version_key(path: str) -> Tuple[int, int, int]:
        version = _parse_version_from_path(path)
        if version:
            # Higher versions get higher priority (will sort to end, then we reverse)
            return version
        # Unknown versions go last
        return (0, 0, 0)

    # Filter out unsupported versions (like 9.0.x)
    filtered = []
    for path in python_paths:
        version = _parse_version_from_path(path)
        if version:
            major_minor = (version[0], version[1])
            if major_minor in UNSUPPORTED_VERSIONS:
                continue  # Skip 9.0.x
        filtered.append(path)

    # Sort by version, highest first
    return sorted(filtered, key=version_key, reverse=True)
