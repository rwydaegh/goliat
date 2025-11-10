"""Profiling configuration management."""

import json
import logging
import os


def load_or_create_profiling_config(profiling_config_path: str) -> dict:
    """Loads profiling config from disk, or creates a new one if missing.

    Args:
        profiling_config_path: Path to the profiling config file.

    Returns:
        The profiling config dict, initialized with empty structure if new.
    """
    if os.path.exists(profiling_config_path):
        try:
            with open(profiling_config_path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            # If file is corrupted, start fresh
            pass

    # Create a new profiling config with empty structure
    profiling_config = {}

    # Initialize with empty structure for each study type
    for study_type in ["near_field", "far_field"]:
        profiling_config[study_type] = {}

    # Save the initial config
    try:
        with open(profiling_config_path, "w") as f:
            json.dump(profiling_config, f, indent=4)
    except IOError:
        # If we can't write, just return the empty dict
        pass

    return profiling_config


def get_profiling_config(profiling_config: dict, study_type: str) -> dict:
    """Gets the profiling configuration for a given study type.

    Args:
        profiling_config: The profiling configuration dictionary.
        study_type: The type of the study (e.g., 'near_field').

    Returns:
        The profiling configuration for the study type.
    """
    if study_type not in profiling_config:
        logging.warning(f"Profiling configuration not defined for study type: {study_type}. Returning empty configuration.")
        return {}
    return profiling_config[study_type]
