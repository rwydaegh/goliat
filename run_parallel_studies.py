import os
import sys
import json
import argparse
import logging
import colorama
import shutil
import subprocess
import multiprocessing
from copy import deepcopy

# Ensure the src directory is in the Python path
base_dir = os.path.abspath(os.path.dirname(__file__))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

def setup_console_logging():
    """Sets up a basic console logger with color."""
    colorama.init(autoreset=True)
    logger = logging.getLogger('script_logger')
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(message)s'))
    if logger.hasHandlers():
        logger.handlers.clear()
    logger.addHandler(handler)
    return logger

def split_config(config_path, num_splits, logger):
    """Splits the configuration file into a number of parallel configs."""
    if not os.path.exists(config_path):
        logger.error(f"{colorama.Fore.RED}Error: Config file not found at '{config_path}'")
        sys.exit(1)

    with open(config_path, 'r') as f:
        config = json.load(f)

    config_filename = os.path.basename(config_path).replace('.json', '')
    output_dir = os.path.join(os.path.dirname(config_path), f"{config_filename}_parallel")

    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    os.makedirs(output_dir)

    logger.info(f"Creating parallel configs in: {output_dir}")

    # Copy base_config.json to the new directory
    base_config_name = config.get("extends")
    if base_config_name:
        base_config_path = os.path.join(os.path.dirname(config_path), base_config_name)
        if os.path.exists(base_config_path):
            shutil.copy(base_config_path, output_dir)
            logger.info(f"  - Copied: {base_config_name}")

    base_phantoms = config.get('phantoms', [])
    if isinstance(base_phantoms, dict): # near-field case
        base_phantoms = list(base_phantoms.keys())

    if num_splits == 2:
        if len(base_phantoms) < 2:
            logger.error(f"{colorama.Fore.RED}Need at least 2 phantoms for 2 splits.")
            sys.exit(1)
        
        midpoint = len(base_phantoms) // 2
        phantom_splits = [base_phantoms[:midpoint], base_phantoms[midpoint:]]

    elif num_splits == 4:
        if len(base_phantoms) < 4:
            logger.error(f"{colorama.Fore.RED}Need at least 4 phantoms for 4 splits.")
            sys.exit(1)
        phantom_splits = [[p] for p in base_phantoms]

    elif num_splits == 8:
        if not base_phantoms:
            logger.error(f"{colorama.Fore.RED}No phantoms found to split.")
            sys.exit(1)

        frequencies = config.get('frequencies_mhz', [])
        if not frequencies or len(frequencies) < 2:
            logger.error(f"{colorama.Fore.RED}Need at least 2 frequencies for an 8-way split.")
            sys.exit(1)
        
        midpoint = len(frequencies) // 2
        freq_splits = [frequencies[:midpoint], frequencies[midpoint:]]
        
        phantom_splits = []
        for phantom in base_phantoms:
            for f_split in freq_splits:
                phantom_splits.append(([phantom], f_split))

    else:
        logger.error(f"{colorama.Fore.RED}Splitting for {num_splits} is not implemented.")
        sys.exit(1)

    for i, split in enumerate(phantom_splits):
        new_config = deepcopy(config)
        
        if num_splits == 8:
            phantoms, freqs = split
            new_config['phantoms'] = phantoms
            new_config['frequencies_mhz'] = freqs
        else:
            if 'phantoms' in new_config and isinstance(new_config['phantoms'], dict):
                new_config['phantoms'] = {p: new_config['phantoms'][p] for p in split}
            else:
                new_config['phantoms'] = split

        new_config_path = os.path.join(output_dir, f"{config_filename}_{i}.json")
        with open(new_config_path, 'w') as f:
            json.dump(new_config, f, indent=2)
        logger.info(f"  - Created: {new_config_path}")
    
    return output_dir

def run_study_process(args):
    """Runs the study for a given config file."""
    config_file, process_id = args
    title = f"Process {process_id} - Study Runner ({os.path.basename(config_file)})"
    
    # Construct the command to run the main study script
    run_study_script = os.path.join(base_dir, 'run_study.py')
    command = ["python", run_study_script, "--config", config_file, "--title", title, "--pid", str(process_id)]
    
    print(f"Running command: {' '.join(command)}")
    
    # For Windows, use CREATE_NEW_CONSOLE to launch each study in its own window.
    if sys.platform == "win32":
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NEW_CONSOLE)
    else:
        # For other platforms, just run the process. The output will be interleaved in the main console.
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    stdout, stderr = process.communicate()
    if process.returncode != 0:
        print(f"Error running study for {config_file}:")
        print(stderr.decode())
    else:
        print(f"Successfully ran study for {config_file}")
        print(stdout.decode())

def main():
    """Main function to split configs and run studies in parallel."""
    logger = setup_console_logging()
    parser = argparse.ArgumentParser(description="Split a config file and run studies in parallel.")
    parser.add_argument('--config', default="configs/far_field_config.json", help="Path to the target config file.")
    parser.add_argument('--num-splits', type=int, default=8, help="Number of configs to split into (2, 4, or 8).")
    parser.add_argument('--skip-split', action='store_true', help="Skip the splitting step and run studies from an existing parallel directory.")
    
    args = parser.parse_args()

    if not args.skip_split:
        if args.num_splits not in [2, 4, 8]:
            logger.error(f"{colorama.Fore.RED}Error: --num-splits must be 2, 4, or 8.")
            sys.exit(1)
        config_dir = split_config(args.config, args.num_splits, logger)
        logger.info(f"{colorama.Fore.GREEN}Config splitting complete.")
    else:
        config_filename = os.path.basename(args.config).replace('.json', '')
        config_dir = os.path.join(os.path.dirname(args.config), f"{config_filename}_parallel")
        logger.info(f"Skipping split, using existing directory: {config_dir}")

    if not os.path.isdir(config_dir):
        logger.error(f"{colorama.Fore.RED}Error: Directory not found at '{config_dir}'")
        sys.exit(1)

    # Get all json files from the directory
    all_json_files = [f for f in os.listdir(config_dir) if f.endswith('.json')]
    
    # Find the base config name by inspecting the split files
    base_config_name = None
    # Find a file that is NOT a base config to inspect it for the 'extends' key
    sample_split_file = next((f for f in all_json_files if 'base' not in f.lower()), None)

    if sample_split_file:
        with open(os.path.join(config_dir, sample_split_file), 'r') as f:
            try:
                config_data = json.load(f)
                base_config_name = config_data.get("extends")
            except json.JSONDecodeError:
                logger.warning(f"Could not parse {sample_split_file} to find base config.")

    # Exclude the base config file from the list of files to run
    if base_config_name:
        config_files_to_run = [os.path.join(config_dir, f) for f in all_json_files if f != base_config_name]
        logger.info(f"Identified '{base_config_name}' as the base config. It will be excluded from the run.")
    else:
        config_files_to_run = [os.path.join(config_dir, f) for f in all_json_files]
        logger.warning("Could not identify a base config file. All .json files will be treated as studies.")
    
    if not config_files_to_run:
        logger.warning(f"No .json config files found to run in '{config_dir}' (excluding base config).")
        return

    logger.info(f"Found {len(config_files_to_run)} configs to run in parallel.")

    # Clean up any stale lock files before starting
    lock_files = [f for f in os.listdir(base_dir) if f.endswith('.lock')]
    for lock_file in lock_files:
        lock_file_path = os.path.join(base_dir, lock_file)
        try:
            os.remove(lock_file_path)
            logger.info(f"Removed stale lock file: {lock_file_path}")
        except OSError as e:
            logger.error(f"Error removing stale lock file {lock_file_path}: {e}")

    # Assign a unique ID to each process
    process_args = [(config, i+1) for i, config in enumerate(config_files_to_run)]

    # Use a multiprocessing Pool to run the studies in parallel
    with multiprocessing.Pool(processes=len(process_args)) as pool:
        pool.map(run_study_process, process_args)

    logger.info(f"{colorama.Fore.GREEN}All parallel studies completed.")

if __name__ == "__main__":
    # This is crucial for multiprocessing to work correctly, especially on Windows
    multiprocessing.freeze_support()
    main()