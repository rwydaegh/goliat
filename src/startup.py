import os
import sys
import subprocess
import pkg_resources
import logging

def check_and_install_packages(requirements_path):
    """
    Checks if the packages listed in requirements.txt are installed and installs them if not.
    """
    with open(requirements_path, 'r') as f:
        requirements = [line.strip() for line in f if line.strip()]
    
    missing_packages = []
    for package in requirements:
        try:
            pkg_resources.get_distribution(package)
        except pkg_resources.DistributionNotFound:
            missing_packages.append(package)

    if missing_packages:
        logging.getLogger('verbose').info(f"Missing packages: {', '.join(missing_packages)}")
        logging.getLogger('verbose').info("Installing missing packages...")
        python_exe = sys.executable
        subprocess.check_call([python_exe, '-m', 'pip', 'install', *missing_packages])
        logging.getLogger('verbose').info("All missing packages installed.")
    else:
        logging.getLogger('verbose').info("All required packages are already installed.")

def prepare_data(base_dir):
    """
    Ensures all necessary data is downloaded and prepared.
    """
    from scripts.download_data import download_and_extract_data
    
    data_dir = os.path.join(base_dir, 'data')
    if not os.path.exists(data_dir):
        logging.getLogger('verbose').info("Data directory not found. Downloading and extracting data...")
        download_and_extract_data(base_dir)
    else:
        logging.getLogger('verbose').info("Data directory already exists. Skipping download.")

    centered_dir = os.path.join(data_dir, 'antennas', 'centered')
    if not os.path.exists(centered_dir) or not os.listdir(centered_dir):
        logging.getLogger('verbose').info("Centered antenna directory is empty. Preparing antennas...")
        prepare_antennas_script = os.path.join(base_dir, 'scripts', 'prepare_antennas.py')
        python_exe = sys.executable
        subprocess.run([python_exe, prepare_antennas_script], check=True)
    else:
        logging.getLogger('verbose').info("Centered antennas already exist. Skipping preparation.")

def run_full_startup(base_dir):
    """
    Runs all startup checks and preparations.
    """
    logging.getLogger('verbose').info("--- Running Project Startup ---")
    
    # 1. Install Packages
    requirements_path = os.path.join(base_dir, 'requirements.txt')
    check_and_install_packages(requirements_path)
    
    # 2. Prepare Data
    prepare_data(base_dir)
    
    logging.getLogger('verbose').info("--- Startup Complete ---")