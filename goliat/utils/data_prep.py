"""Data preparation utilities.

This module handles downloading and preparing data files needed for studies.
"""

import logging
import os
import platform


def prepare_data(base_dir):
    """
    Ensures all necessary data is downloaded and prepared.

    This function is idempotent - it checks what exists and only performs
    missing steps. This allows repair of incomplete setups.

    Args:
        base_dir: Base directory of the project (where data/ directory is located).
    """
    from .data import download_and_extract_data

    data_dir = os.path.join(base_dir, "data")

    # Check and download phantoms if needed
    phantoms_dir = os.path.join(data_dir, "phantoms")
    phantom_files = []
    if os.path.exists(phantoms_dir):
        try:
            phantom_files = [f for f in os.listdir(phantoms_dir) if f.endswith(".sab")]
        except (PermissionError, OSError) as e:
            logging.warning(f"Could not read phantoms directory: {e}. Will attempt to download.")
            phantom_files = []

    if not os.path.exists(phantoms_dir) or len(phantom_files) < 4:
        logging.info("Phantoms directory is missing or incomplete. Downloading phantoms...")
        download_and_extract_data(base_dir, logging.getLogger(), aws=False)  # Always download standard phantoms
    else:
        logging.info(f"Phantoms already exist ({len(phantom_files)} files found). Skipping download.")

    # If on AWS, download the extra phantom file
    if "aws" in platform.release():
        logging.info("AWS environment detected. Downloading additional phantom...")
        download_and_extract_data(base_dir, logging.getLogger(), aws=True)

    # Check and prepare antennas if needed
    centered_dir = os.path.join(data_dir, "antennas", "centered")
    antenna_files = []
    if os.path.exists(centered_dir):
        try:
            antenna_files = [f for f in os.listdir(centered_dir) if f.endswith(".sab")]
        except (PermissionError, OSError) as e:
            logging.warning(f"Could not read antennas directory: {e}. Will attempt to prepare.")
            antenna_files = []

    if not os.path.exists(centered_dir) or len(antenna_files) == 0:
        logging.info("Centered antenna directory is missing or empty. Preparing antennas...")
        from .scripts.prepare_antennas import main as prepare_antennas_main

        prepare_antennas_main(base_dir)
    else:
        logging.info(f"Centered antennas already exist ({len(antenna_files)} files found). Skipping preparation.")
