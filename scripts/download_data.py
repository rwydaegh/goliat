import json
import logging
import os

import colorama
import gdown


def setup_console_logging():
    """Sets up a basic console logger with color."""
    colorama.init(autoreset=True)
    logger = logging.getLogger("script_logger")
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    return logger


def download_and_extract_data(base_dir, logger, aws=False):
    """
    Downloads folder from Google Drive.
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
        gdown.download(gdrive_url, output=output_path, quiet=False)
    else:
        gdrive_url = config["data_setup"]["gdrive_url"]
        logger.info(f"{colorama.Fore.CYAN}Downloading data from {gdrive_url} into {data_dir}...")
        gdown.download_folder(gdrive_url, output=data_dir, quiet=False)

    logger.info(f"{colorama.Fore.GREEN}Data download complete.")


if __name__ == "__main__":
    logger = setup_console_logging()
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    download_and_extract_data(project_root, logger)
