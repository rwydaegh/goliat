import os
import sys
import subprocess
import logging

def install_requirements(requirements_path):
    """
    Checks if the packages listed in requirements.txt are installed and installs them if not.
    """
    import pkg_resources
    if not os.path.exists(requirements_path):
        logging.warning(f"requirements.txt not found at '{requirements_path}'. Skipping installation.")
        return

    with open(requirements_path, 'r') as f:
        requirements = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    
    missing_packages = []
    for package in requirements:
        try:
            # Attempt to parse the requirement to get the package name
            req = pkg_resources.Requirement.parse(package)
            pkg_resources.get_distribution(req.project_name)
        except pkg_resources.DistributionNotFound:
            missing_packages.append(package)
        except ValueError:
            logging.warning(f"Could not parse package requirement: {package}")


    if missing_packages:
        logging.info(f"Missing packages: {', '.join(missing_packages)}. Installing...")
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', *missing_packages])
            logging.info("All missing packages installed.")
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to install packages: {e}")
            sys.exit(1)
    else:
        logging.info("All required packages are already installed.")

def check_repo_root():
    """
    Checks if the script is running from the root of the repository.
    It does this by checking for the existence of 'configs/' and 'src/' directories.
    """
    is_root = os.path.isdir('configs') and os.path.isdir('src')
    if not is_root:
        logging.error("This script must be run from the root directory of the GOLIAT repository.")
        sys.exit(1)

def find_sim4life_python_executables():
    """
    Scans all drives for Sim4Life Python directories (versions 8.2 and 9.0).
    """
    drive_letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    drives = [f'{d}:\\' for d in drive_letters if os.path.exists(f'{d}:\\')]
    
    found_python_dirs = []
    
    for drive in drives:
        for version in ["8.2", "9.0"]:
            # Construct a glob pattern to find the Python directory
            search_pattern = os.path.join(drive, 'Program Files', f'Sim4Life_{version}*', 'Python')
            
            # Use glob to find matching directories
            import glob
            matches = glob.glob(search_pattern)
            for match in matches:
                if os.path.isdir(match):
                    found_python_dirs.append(match)
            
    return found_python_dirs

def update_bashrc(selected_python_path):
    """
    Overwrites the .bashrc file with a single line to set the Python path.
    """
    bashrc_path = os.path.join(os.getcwd(), '.bashrc')
    
    # Prepare the new path line
    drive, path_rest = os.path.splitdrive(selected_python_path)
    bash_path = f'/{drive.strip(":")}{path_rest.replace(os.sep, "/")}'
    new_path_line = f'export PATH="{bash_path}:$PATH"\n'

    # Overwrite the file with just the new path
    with open(bashrc_path, 'w') as f:
        f.write(new_path_line)
    
    logging.info("'.bashrc' has been updated. Please restart your shell or run 'source .bashrc'.")


def check_python_interpreter():
    """
    Checks if the correct Sim4Life Python interpreter is being used.
    If not, it prompts the user to select a valid one and updates .bashrc.
    """
    viable_pythons = find_sim4life_python_executables()
    
    # Normalize paths for comparison
    normalized_viable_python_dirs = [os.path.normpath(p) for p in viable_pythons]
    normalized_sys_executable_dir = os.path.normpath(os.path.dirname(sys.executable))

    if "Sim4Life" in sys.executable:
        if normalized_sys_executable_dir in normalized_viable_python_dirs:
            logging.info("Correct Sim4Life Python interpreter detected.")
            return
        else:
            logging.warning(f"You are using an unsupported Sim4Life Python interpreter: {sys.executable}")
            logging.warning("This project requires Sim4Life version 8.2 or 9.0.")
    else:
        logging.warning("You are not using a Sim4Life Python interpreter.")

    if not viable_pythons:
        logging.error("No viable Sim4Life Python executables (v8.2, v9.0) found on this system.")
        sys.exit(1)

    print("Found the following supported Sim4Life Python executables (8.2 or 9.0):")
    for i, p in enumerate(viable_pythons):
        print(f"  [{i+1}] {p}")

    try:
        choice = input("Select the version to use (e.g., '1') or press Enter to cancel: ")
        if not choice:
            print("Operation cancelled by user.")
            sys.exit(0)
        
        selected_index = int(choice) - 1
        if not 0 <= selected_index < len(viable_pythons):
            raise ValueError
        
        selected_python = viable_pythons[selected_index]
        
        update_bashrc(selected_python)
        
        print("\nConfiguration updated. Please restart your terminal and run the script again.")
        sys.exit(0)

    except (ValueError, IndexError):
        print("Invalid selection. Exiting.")
        sys.exit(1)

def prepare_data(base_dir):
    """
    Ensures all necessary data is downloaded and prepared.
    """
    from scripts.download_data import download_and_extract_data
    
    data_dir = os.path.join(base_dir, 'data')
    phantoms_dir = os.path.join(data_dir, 'phantoms')
    if not os.path.exists(phantoms_dir) or len(os.listdir(phantoms_dir)) < 4:
        logging.getLogger('verbose').info("Phantoms directory is missing or incomplete. Downloading phantoms...", extra={'log_type': 'info'})
        download_and_extract_data(base_dir, logging.getLogger('verbose'))
    else:
        logging.getLogger('verbose').info("Phantoms already exist. Skipping download.", extra={'log_type': 'info'})

    centered_dir = os.path.join(data_dir, 'antennas', 'centered')
    if not os.path.exists(centered_dir) or not os.listdir(centered_dir):
        logging.getLogger('verbose').info("Centered antenna directory is empty. Preparing antennas...", extra={'log_type': 'info'})
        prepare_antennas_script = os.path.join(base_dir, 'scripts', 'prepare_antennas.py')
        python_exe = sys.executable
        subprocess.run([python_exe, prepare_antennas_script], check=True)
    else:
        logging.getLogger('verbose').info("Centered antennas already exist. Skipping preparation.", extra={'log_type': 'info'})

def initial_setup():
    """
    Runs all initial checks and setup procedures, but only if a lock file is not present.
    """
    lock_file = os.path.join(os.getcwd(), '.setup_done')
    if os.path.exists(lock_file):
        logging.info("Setup has already been performed. Skipping.")
        return

    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    check_repo_root()
    check_python_interpreter()
    install_requirements(os.path.join(os.getcwd(), 'requirements.txt'))
    prepare_data(os.getcwd())
    
    # Create the lock file to indicate setup is complete
    with open(lock_file, 'w') as f:
        f.write('Setup complete.')