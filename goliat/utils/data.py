"""Data downloader for GOLIAT project.

Downloads phantoms and antenna data from Google Drive using gdown.
"""

import json
import logging
import os
import re
import subprocess

import colorama
import gdown

from goliat.colors import init_colorama


def setup_console_logging():
    """Sets up a basic console logger with color."""
    init_colorama()
    logger = logging.getLogger("script_logger")
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    return logger


def _convert_gdrive_url_for_wget(url):
    """
    Convert Google Drive URL to wget-compatible format.

    Args:
        url: Google Drive URL

    Returns:
        wget-compatible URL or None if conversion not possible
    """
    # Extract file ID from various Google Drive URL formats
    # Format 1: https://drive.google.com/uc?id=FILE_ID
    match = re.search(r"[?&]id=([a-zA-Z0-9_-]+)", url)
    if match:
        file_id = match.group(1)
        return f"https://drive.google.com/uc?export=download&id={file_id}"

    # Format 2: https://drive.google.com/drive/folders/FOLDER_ID
    match = re.search(r"/folders/([a-zA-Z0-9_-]+)", url)
    if match:
        # wget doesn't support folder downloads from Google Drive
        return None

    return None


def download_and_extract_data(base_dir, logger, aws=False):
    """
    Downloads folder from Google Drive.

    Args:
        base_dir: Root directory of the project
        logger: Logger instance for output
        aws: If True, downloads AWS-specific phantom file
    """
    config_path = os.path.join(base_dir, "configs/base_config.json")
    with open(config_path, "r") as f:
        config = json.load(f)

    data_dir = os.path.join(base_dir, config["data_setup"]["data_dir"])
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)

    if aws:
        gdrive_url = config["data_setup"]["gdrive_url_aws"]
        phantoms_dir = os.path.join(data_dir, "phantoms")
        if not os.path.exists(phantoms_dir):
            os.makedirs(phantoms_dir)
        output_path = os.path.join(phantoms_dir, "duke_posable.sab")
        logger.info(f"{colorama.Fore.CYAN}Downloading data from {gdrive_url} into {output_path}...")

        try:
            gdown.download(gdrive_url, output=output_path, quiet=False)
        except Exception as e:
            logger.warning(f"{colorama.Fore.YELLOW}gdown failed: {e}")
            logger.info(f"{colorama.Fore.CYAN}Attempting download with wget...")
            wget_url = _convert_gdrive_url_for_wget(gdrive_url)
            if wget_url:
                try:
                    subprocess.run(["wget", "--no-check-certificate", "-O", output_path, wget_url], check=True)
                    logger.info(f"{colorama.Fore.GREEN}Download completed with wget.")
                except (subprocess.CalledProcessError, FileNotFoundError) as wget_error:
                    logger.error(f"{colorama.Fore.RED}wget also failed: {wget_error}")
                    raise
            else:
                logger.error(f"{colorama.Fore.RED}Cannot convert URL for wget. Both download methods failed.")
                raise
    else:
        gdrive_url = config["data_setup"]["gdrive_url"]
        logger.info(f"{colorama.Fore.CYAN}Downloading data from {gdrive_url} into {data_dir}...")

        try:
            gdown.download_folder(gdrive_url, output=data_dir, quiet=False)
        except Exception as e:
            logger.warning(f"{colorama.Fore.YELLOW}gdown failed: {e}")
            logger.warning(f"{colorama.Fore.YELLOW}Note: wget does not support folder downloads from Google Drive.")
            logger.error(f"{colorama.Fore.RED}Folder download failed. Please try again later or use gdown with cookies.")
            raise

    logger.info(f"{colorama.Fore.GREEN}Data download complete.")


if __name__ == "__main__":
    logger = setup_console_logging()
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    download_and_extract_data(project_root, logger)
