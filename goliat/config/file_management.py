"""File management utilities for configuration."""

import logging
import os


def cleanup_old_data_files(data_dir: str):
    """Removes old CSV/JSON files from data/ when there are more than 50.

    Only cleans files matching specific patterns (time_remaining_, overall_progress_,
    profiling_config_). Files are sorted by creation time and oldest are deleted first.

    Args:
        data_dir: The data directory to clean up.
    """
    try:
        # Get all CSV and JSON files in the data directory
        data_files = []
        for f in os.listdir(data_dir):
            if f.endswith(".csv") or f.endswith(".json"):
                # Only include files with the expected naming pattern
                if any(prefix in f for prefix in ["time_remaining_", "overall_progress_", "profiling_config_"]):
                    full_path = os.path.join(data_dir, f)
                    data_files.append(full_path)

        # Sort by creation time (oldest first)
        data_files.sort(key=os.path.getctime)

        # Remove oldest files if we have more than 50
        while len(data_files) > 50:
            old_file = None
            try:
                old_file = data_files.pop(0)
                os.remove(old_file)
                logging.getLogger("verbose").info(f"Removed old data file: {os.path.basename(old_file)}")
            except OSError as e:
                if old_file:
                    logging.getLogger("verbose").warning(f"Failed to remove {os.path.basename(old_file)}: {e}")
                else:
                    logging.getLogger("verbose").warning(f"Failed to remove a file: {e}")
    except Exception as e:
        logging.getLogger("verbose").warning(f"Error during data file cleanup: {e}")
