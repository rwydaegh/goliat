import os
import sys
import gdown
import json
import logging
import colorama

def setup_console_logging():
    """Sets up a basic console logger with color."""
    colorama.init(autoreset=True)
    logger = logging.getLogger('script_logger')
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(message)s'))
    logger.addHandler(handler)
    return logger

def download_and_extract_data(base_dir, logger):
    """
    Downloads folder from Google Drive.
    """
    config_path = os.path.join(base_dir, 'configs/base_config.json')
    with open(config_path, 'r') as f:
        config = json.load(f)

    gdrive_url = config['data_setup']['gdrive_url']
    data_dir = os.path.join(base_dir, config['data_setup']['data_dir'])
    
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)

    # Download the folder content
    logger.info(f"{colorama.Fore.CYAN}Downloading data from {gdrive_url} into {data_dir}...")
    gdown.download_folder(gdrive_url, output=data_dir, quiet=False, fuzzy=True)

    logger.info(f"{colorama.Fore.GREEN}Data download complete.")

if __name__ == '__main__':
    logger = setup_console_logging()
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    download_and_extract_data(project_root, logger)