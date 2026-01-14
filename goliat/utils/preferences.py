"""User preferences management.

This module handles loading and saving user preferences for GOLIAT setup.

Preferences are stored in data/.goliat_preferences.json and include:
- sync_bashrc_to_home: Whether to auto-sync .bashrc to ~/.bashrc
- sim4life_python_path: Path to the selected Sim4Life Python directory
"""

import json
import logging
import os


def get_user_preferences(base_dir):
    """Load user preferences from data/.goliat_preferences.json"""
    prefs_file = os.path.join(base_dir, "data", ".goliat_preferences.json")
    if os.path.exists(prefs_file):
        try:
            with open(prefs_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_user_preferences(base_dir, preferences):
    """Save user preferences to data/.goliat_preferences.json"""
    prefs_file = os.path.join(base_dir, "data", ".goliat_preferences.json")
    data_dir = os.path.dirname(prefs_file)
    os.makedirs(data_dir, exist_ok=True)
    try:
        with open(prefs_file, "w", encoding="utf-8") as f:
            json.dump(preferences, f, indent=2)
    except Exception as e:
        logging.warning(f"Could not save preferences: {e}")


def get_sim4life_python_path(base_dir):
    """Get the stored Sim4Life Python path from preferences.

    Returns:
        str or None: The stored path, or None if not set.
    """
    prefs = get_user_preferences(base_dir)
    return prefs.get("sim4life_python_path")


def set_sim4life_python_path(base_dir, python_path):
    """Store the selected Sim4Life Python path in preferences.

    Args:
        base_dir: Project base directory.
        python_path: Path to Sim4Life Python directory.
    """
    prefs = get_user_preferences(base_dir)
    prefs["sim4life_python_path"] = python_path
    save_user_preferences(base_dir, prefs)
    logging.info(f"Saved Sim4Life Python path preference: {python_path}")
