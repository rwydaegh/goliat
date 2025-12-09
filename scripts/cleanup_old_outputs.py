#!/usr/bin/env python3
"""
Cleanup script for old _Output.h5 files in results/ directory.

Waits 2.5 hours before starting, then continuously checks for and deletes
_Output.h5 files that are older than 45 minutes.

Usage:
    python cleanup_old_outputs.py

Set TESTING = False to enable actual file deletion.
"""

import os
import shutil
import sys
import time
import logging
from pathlib import Path
from datetime import datetime, timedelta

# ============== CONFIGURATION ==============
TESTING = False  # Set to False to actually delete files
INITIAL_DELAY_HOURS = 2.5
FILE_AGE_THRESHOLD_MINUTES = 45
CHECK_INTERVAL_SECONDS = 300  # Check every 5 minutes after initial delay
# ===========================================

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
logger = logging.getLogger(__name__)


def get_results_dir() -> Path:
    """Get the results directory path robustly."""
    # Try relative to script location first
    script_dir = Path(__file__).resolve().parent
    results_dir = script_dir.parent / "results"

    if results_dir.exists():
        return results_dir

    # Fallback: try current working directory
    cwd_results = Path.cwd() / "results"
    if cwd_results.exists():
        return cwd_results

    # Return the expected path even if it doesn't exist yet
    return results_dir


def get_file_age_minutes(file_path: Path) -> float | None:
    """Get the age of a file in minutes based on creation time.

    Returns None if the file cannot be accessed.
    """
    try:
        # On Windows, st_ctime is creation time; on Unix it's metadata change time
        creation_time = os.path.getctime(file_path)
        age_seconds = time.time() - creation_time
        return age_seconds / 60
    except OSError as e:
        logger.warning(f"Could not get age of {file_path}: {e}")
        return None


def get_file_size_mb(file_path: Path) -> float:
    """Get file size in MB, returns 0 if file cannot be accessed."""
    try:
        return file_path.stat().st_size / (1024 * 1024)
    except OSError:
        return 0.0


def find_old_output_files(results_dir: Path, age_threshold_minutes: float) -> list[tuple[Path, float]]:
    """Find all _Output.h5 files older than the specified threshold.

    Returns list of (file_path, age_in_minutes) tuples.
    """
    old_files = []

    if not results_dir.exists():
        logger.warning(f"Results directory does not exist: {results_dir}")
        return old_files

    if not results_dir.is_dir():
        logger.error(f"Results path is not a directory: {results_dir}")
        return old_files

    try:
        for h5_file in results_dir.rglob("*_Output.h5"):
            try:
                # Skip if file is currently being written (check if accessible)
                if not h5_file.is_file():
                    continue

                age_minutes = get_file_age_minutes(h5_file)
                if age_minutes is not None and age_minutes > age_threshold_minutes:
                    old_files.append((h5_file, age_minutes))
            except PermissionError:
                logger.warning(f"Permission denied accessing: {h5_file}")
            except OSError as e:
                logger.warning(f"Error accessing {h5_file}: {e}")
    except Exception as e:
        logger.error(f"Error scanning directory {results_dir}: {e}")

    return old_files


def cleanup_files(results_dir: Path, testing: bool = True) -> int:
    """Main cleanup function.

    Returns the number of files deleted (or would be deleted in testing mode).
    """
    logger.info("=" * 60)
    logger.info("Scanning for old _Output.h5 files")
    logger.info(f"Results directory: {results_dir}")
    logger.info(f"Age threshold: {FILE_AGE_THRESHOLD_MINUTES} minutes")
    logger.info(f"Mode: {'TESTING (no deletion)' if testing else 'LIVE (will delete files)'}")

    # Show disk space before cleanup
    try:
        disk_usage = shutil.disk_usage("C:/")
        free_gb = disk_usage.free / (1024**3)
        total_gb = disk_usage.total / (1024**3)
        logger.info(f"C: drive free space: {free_gb:.1f} GB / {total_gb:.1f} GB")
    except Exception as e:
        logger.warning(f"Could not get disk space: {e}")

    logger.info("=" * 60)

    old_files = find_old_output_files(results_dir, FILE_AGE_THRESHOLD_MINUTES)

    if not old_files:
        logger.info("No old _Output.h5 files found.")
        return 0

    logger.info(f"Found {len(old_files)} old _Output.h5 file(s):")

    total_size = 0.0
    for file_path, age_minutes in old_files:
        size_mb = get_file_size_mb(file_path)
        total_size += size_mb
        logger.info(f"  [{age_minutes:.1f} min old] [{size_mb:.1f} MB] {file_path}")

    logger.info(f"Total size: {total_size:.1f} MB")

    deleted_count = 0
    if testing:
        logger.warning("TESTING MODE: Files were NOT deleted.")
    else:
        logger.info("Deleting files...")
        for file_path, _ in old_files:
            try:
                file_path.unlink()
                logger.info(f"  Deleted: {file_path}")
                deleted_count += 1
            except PermissionError:
                logger.error(f"  Permission denied deleting: {file_path}")
            except FileNotFoundError:
                logger.warning(f"  File already gone: {file_path}")
            except OSError as e:
                logger.error(f"  Error deleting {file_path}: {e}")
        logger.info(f"Deleted {deleted_count}/{len(old_files)} files.")

        # Show disk space after cleanup
        try:
            disk_usage = shutil.disk_usage("C:/")
            free_gb = disk_usage.free / (1024**3)
            logger.info(f"C: drive free space after cleanup: {free_gb:.1f} GB")
        except Exception as e:
            logger.warning(f"Could not get disk space: {e}")

    return len(old_files) if testing else deleted_count


def main():
    """Main entry point."""
    results_dir = get_results_dir()

    logger.info("Cleanup script started")
    logger.info(f"TESTING mode: {TESTING}")
    logger.info(f"Results directory: {results_dir}")
    logger.info(f"Initial delay: {INITIAL_DELAY_HOURS} hours ({INITIAL_DELAY_HOURS * 60:.0f} minutes)")
    logger.info(f"File age threshold: {FILE_AGE_THRESHOLD_MINUTES} minutes")
    logger.info(f"Check interval: {CHECK_INTERVAL_SECONDS} seconds")

    # Verify results directory exists or warn
    if not results_dir.exists():
        logger.warning(f"Results directory does not exist yet: {results_dir}")
        logger.info("Will continue and check periodically...")

    # Wait for initial delay (short wait if TESTING)
    if TESTING:
        logger.info("TESTING mode: Waiting 5 seconds before running...")
        time.sleep(5)
    else:
        delay_seconds = INITIAL_DELAY_HOURS * 3600
        target_time = datetime.now() + timedelta(hours=INITIAL_DELAY_HOURS)
        logger.info(f"Waiting {INITIAL_DELAY_HOURS} hours before first cleanup...")
        logger.info(f"First cleanup will run at approximately: {target_time.strftime('%Y-%m-%d %H:%M:%S')}")
        time.sleep(delay_seconds)

    # Run cleanup once
    try:
        cleanup_files(results_dir, testing=TESTING)
    except KeyboardInterrupt:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during cleanup: {e}")

    logger.info("Cleanup complete. Exiting.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\nScript terminated by user.")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
