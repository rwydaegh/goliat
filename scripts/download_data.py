import os
import sys
import gdown
import json

# Add project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def download_and_extract_data(base_dir):
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
    print(f"Downloading data from {gdrive_url} into {data_dir}...")
    gdown.download_folder(gdrive_url, output=data_dir, quiet=False)

    print("Data download complete.")

if __name__ == '__main__':
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    download_and_extract_data(project_root)