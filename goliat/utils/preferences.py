"""User preferences management.

This module handles loading and saving user preferences for GOLIAT setup.
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
