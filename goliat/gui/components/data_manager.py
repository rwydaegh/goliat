"""Data management for GUI: CSV file handling and cleanup."""

import csv
import hashlib
import os
import time
from datetime import datetime
from logging import Logger
from typing import List


class DataManager:
    """Manages CSV data files for time remaining and overall progress tracking.

    Writes timestamped data points to CSV files for plotting and analysis.
    Automatically cleans up old files (keeps last 50) to prevent disk bloat.
    Creates unique session files using timestamp and process hash.
    """

    def __init__(self, data_dir: str, verbose_logger: Logger) -> None:
        """Sets up data manager with session-specific CSV files.

        Args:
            data_dir: Directory where data files will be stored.
            verbose_logger: Logger for verbose messages.
        """
        self.data_dir: str = data_dir
        self.verbose_logger: Logger = verbose_logger
        self.session_hash: str = hashlib.md5(f"{time.time()}_{os.getpid()}".encode()).hexdigest()[:8]
        session_timestamp = datetime.now().strftime("%d-%m_%H-%M-%S")

        # Cleanup old CSV files before creating new ones
        self._cleanup_old_data_files()

        self.time_remaining_file: str = os.path.join(self.data_dir, f"time_remaining_{session_timestamp}_{self.session_hash}.csv")
        self.overall_progress_file: str = os.path.join(self.data_dir, f"overall_progress_{session_timestamp}_{self.session_hash}.csv")

        # Initialize data files
        self._initialize_files()

    def _initialize_files(self) -> None:
        """Initializes CSV files with headers."""
        with open(self.time_remaining_file, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "hours_remaining"])

        with open(self.overall_progress_file, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "progress_percent"])

    def _write_csv_row(self, file_path: str, value: float, value_name: str) -> None:
        """Appends a timestamped data point to a CSV file.

        Args:
            file_path: Path to the CSV file.
            value: The numeric value to write.
            value_name: Name of the value for error messages.
        """
        try:
            current_time = datetime.now()
            with open(file_path, "a", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([current_time.isoformat(), value])
        except Exception as e:
            self.verbose_logger.error(f"Failed to write {value_name} data: {e}")

    def write_time_remaining(self, hours_remaining: float) -> None:
        """Appends a time remaining data point to CSV.

        Writes timestamp and hours remaining to session-specific CSV file.
        Used for plotting ETA trends over time.

        Args:
            hours_remaining: Estimated hours remaining as float.
        """
        self._write_csv_row(self.time_remaining_file, hours_remaining, "time remaining")

    def write_overall_progress(self, progress_percent: float) -> None:
        """Appends an overall progress data point to CSV.

        Writes timestamp and progress percentage to session-specific CSV file.
        Used for plotting progress trends over time.

        Args:
            progress_percent: Overall progress percentage (0-100).
        """
        self._write_csv_row(self.overall_progress_file, progress_percent, "overall progress")

    def _cleanup_old_data_files(self) -> None:
        """Removes old CSV and JSON files when more than 50 exist.

        Keeps disk usage manageable by deleting oldest files first. Only
        removes files matching expected naming patterns (time_remaining_,
        overall_progress_, profiling_config_) to avoid deleting unrelated files.
        """
        try:
            data_files: List[str] = []
            for f in os.listdir(self.data_dir):
                if f.endswith((".csv", ".json")):
                    # Only include files with expected naming pattern
                    if any(prefix in f for prefix in ["time_remaining_", "overall_progress_", "profiling_config_"]):
                        full_path = os.path.join(self.data_dir, f)
                        data_files.append(full_path)

            # Sort by creation time (oldest first)
            data_files.sort(key=os.path.getctime)

            # Remove oldest files if we have more than 50
            while len(data_files) > 50:
                old_file = None
                try:
                    old_file = data_files.pop(0)
                    os.remove(old_file)
                    self.verbose_logger.info(f"Removed old data file: {os.path.basename(old_file)}")
                except OSError as e:
                    if old_file:
                        self.verbose_logger.warning(f"Failed to remove {os.path.basename(old_file)}: {e}")
                    else:
                        self.verbose_logger.warning(f"Failed to remove a file: {e}")
        except Exception as e:
            self.verbose_logger.warning(f"Error during data file cleanup: {e}")
