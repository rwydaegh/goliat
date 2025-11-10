"""Data preparation utilities.

This module handles downloading and preparing data files needed for studies.
"""

import logging
import os
import platform
import subprocess
import sys


def prepare_data(base_dir):
    """
    Ensures all necessary data is downloaded and prepared.
    """
    from .data import download_and_extract_data

    data_dir = os.path.join(base_dir, "data")
    phantoms_dir = os.path.join(data_dir, "phantoms")
    if not os.path.exists(phantoms_dir) or len(os.listdir(phantoms_dir)) < 4:
        logging.info("Phantoms directory is missing or incomplete. Downloading phantoms...")
        download_and_extract_data(base_dir, logging.getLogger(), aws=False)  # Always download standard phantoms
    else:
        logging.info("Phantoms already exist. Skipping download.")

    # If on AWS, download the extra phantom file
    if "aws" in platform.release():
        logging.info("AWS environment detected. Downloading additional phantom...")
        download_and_extract_data(base_dir, logging.getLogger(), aws=True)

    centered_dir = os.path.join(data_dir, "antennas", "centered")
    if not os.path.exists(centered_dir) or not os.listdir(centered_dir):
        logging.info("Centered antenna directory is empty. Preparing antennas...")
        prepare_antennas_script = os.path.join(base_dir, "scripts", "prepare_antennas.py")
        python_exe = sys.executable
        subprocess.run([python_exe, prepare_antennas_script], check=True)
    else:
        logging.info("Centered antennas already exist. Skipping preparation.")
