import argparse
import json
import logging
import multiprocessing
import os
import shutil
import subprocess
import sys
from copy import deepcopy

import colorama

from goliat.colors import init_colorama

# Base directory for config files
from cli.utils import get_base_dir

base_dir = get_base_dir()


def setup_console_logging():
    """Sets up a basic console logger with color."""
    init_colorama()
    logger = logging.getLogger("script_logger")
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    if logger.hasHandlers():
        logger.handlers.clear()
    logger.addHandler(handler)
    return logger


def split_list_into_n(items, n):
    """Split a list into n approximately equal parts."""
    if n <= 0 or not items:
        return []
    if n == 1:
        return [items]
    if n >= len(items):
        return [[item] for item in items]

    # Calculate sizes for each part
    base_size = len(items) // n
    remainder = len(items) % n

    splits = []
    start_idx = 0
    for i in range(n):
        # First 'remainder' splits get one extra item
        size = base_size + (1 if i < remainder else 0)
        splits.append(items[start_idx : start_idx + size])
        start_idx += size

    return splits


def calculate_split_factors(num_phantoms, num_items, target_splits):
    """
    Calculate optimal splitting factors for phantoms and items (frequencies/antennas).
    Prioritizes splitting phantoms first, then items.

    Returns: (phantom_splits, item_splits) where phantom_splits * item_splits = target_splits
    """
    # Find all factor pairs of target_splits
    factors = []
    for i in range(1, target_splits + 1):
        if target_splits % i == 0:
            factors.append((i, target_splits // i))

    # Prioritize phantom splitting: choose the largest phantom split factor that's <= num_phantoms
    best_phantom_splits = 1
    best_item_splits = target_splits

    for phantom_factor, item_factor in factors:
        if phantom_factor <= num_phantoms and item_factor <= num_items:
            # Valid split: both dimensions have enough items
            if phantom_factor > best_phantom_splits:
                # Prefer more phantom splits (prioritize phantom splitting)
                best_phantom_splits = phantom_factor
                best_item_splits = item_factor

    return best_phantom_splits, best_item_splits


def split_config(config_path, num_splits, logger):
    """Splits the configuration file into a number of parallel configs using smart algorithm."""
    if not os.path.exists(config_path):
        logger.error(f"{colorama.Fore.RED}Error: Config file not found at '{config_path}'")
        sys.exit(1)

    with open(config_path, "r") as f:
        config = json.load(f)

    config_filename = os.path.basename(config_path).replace(".json", "")
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

    # Extract phantoms
    base_phantoms = config.get("phantoms", [])
    is_near_field_dict = isinstance(base_phantoms, dict)
    if is_near_field_dict:
        base_phantoms = list(base_phantoms.keys())

    num_phantoms = len(base_phantoms)
    study_type = config.get("study_type")

    # Extract frequencies (far-field) or antennas (near-field)
    if study_type == "near_field":
        antenna_configs = config.get("antenna_config", {})
        items = list(antenna_configs.keys())
        items_name = "antennas"
    else:
        items = config.get("frequencies_mhz", [])
        items_name = "frequencies"

    num_items = len(items)

    # Validate inputs
    if num_phantoms == 0:
        logger.error(f"{colorama.Fore.RED}Error: No phantoms found in config.")
        sys.exit(1)

    if num_items == 0:
        logger.error(f"{colorama.Fore.RED}Error: No {items_name} found in config.")
        sys.exit(1)

    # Calculate split factors
    phantom_splits, item_splits = calculate_split_factors(num_phantoms, num_items, num_splits)

    # Validate that we can achieve the target splits
    total_splits = phantom_splits * item_splits
    if total_splits != num_splits:
        logger.error(
            f"{colorama.Fore.RED}Error: Cannot split {num_phantoms} phantom(s) and "
            f"{num_items} {items_name} into exactly {num_splits} parts."
        )
        logger.error(
            f"{colorama.Fore.RED}With the given constraints, the closest achievable split is "
            f"{total_splits} (phantoms={phantom_splits}, {items_name}={item_splits})."
        )
        sys.exit(1)

    logger.info(
        f"Smart split strategy: {phantom_splits} phantom group(s) × {item_splits} {items_name} group(s) = {total_splits} total configs"
    )

    # Split phantoms and items into groups
    phantom_groups = split_list_into_n(base_phantoms, phantom_splits)
    item_groups = split_list_into_n(items, item_splits)

    logger.info(f"Phantom groups: {[len(g) for g in phantom_groups]}")
    logger.info(f"{items_name.capitalize()} groups: {[len(g) for g in item_groups]}")

    # Create cartesian product of phantom and item groups
    config_splits = []
    for phantom_group in phantom_groups:
        for item_group in item_groups:
            config_splits.append((phantom_group, item_group))

    # Create config files
    for i, (phantoms, items_subset) in enumerate(config_splits):
        new_config = deepcopy(config)

        # Update phantoms
        if is_near_field_dict:
            # Near-field dict format: keep only selected phantoms
            original_phantoms_dict = config.get("phantoms", {})
            new_config["phantoms"] = {p: original_phantoms_dict[p] for p in phantoms}
        else:
            # Far-field list format
            new_config["phantoms"] = phantoms

        # Update frequencies or antennas
        if study_type == "near_field":
            original_antenna_config = config.get("antenna_config", {})
            new_config["antenna_config"] = {key: original_antenna_config[key] for key in items_subset}
        else:
            new_config["frequencies_mhz"] = items_subset

        new_config_path = os.path.join(output_dir, f"{config_filename}_{i}.json")
        with open(new_config_path, "w") as f:
            json.dump(new_config, f, indent=2)
        logger.info(f"  - Created: {os.path.basename(new_config_path)} (phantoms: {phantoms}, {items_name}: {len(items_subset)})")

    return output_dir


def run_study_process(args):
    """Runs the study for a given config file."""
    config_file, process_id, no_cache = args
    title = f"[Process {process_id}] "

    # Use the entry point command instead of calling the script directly
    command = [
        "goliat",
        "study",
        config_file,
        "--title",
        title,
        "--pid",
        str(process_id),
    ]
    if no_cache:
        command.append("--no-cache")

    print(f"Running command: {' '.join(command)}")

    # Launch process (output is piped, so no console window needed)
    # Each goliat study will launch its own GUI window
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

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
    parser.add_argument(
        "config",
        type=str,
        nargs="?",
        default="configs/near_field_config.json",
        help="Path or name of the configuration file (e.g., todays_far_field or configs/near_field_config.json).",
    )
    parser.add_argument(
        "--num-splits",
        type=int,
        default=4,
        help="Number of configs to split into (any positive integer that can be factored "
        "given the phantoms and frequencies/antennas available).",
    )
    parser.add_argument(
        "--skip-split",
        action="store_true",
        help="Skip the splitting step and run studies from an existing parallel directory.",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="If set, redo simulations even if the configuration matches a completed run.",
    )

    args = parser.parse_args()

    if not args.skip_split:
        if args.num_splits < 1:
            logger.error(f"{colorama.Fore.RED}Error: --num-splits must be at least 1.")
            sys.exit(1)
        config_dir = split_config(args.config, args.num_splits, logger)
        logger.info(f"{colorama.Fore.GREEN}Config splitting complete.")
    else:
        config_filename = os.path.basename(args.config).replace(".json", "")
        config_dir = os.path.join(os.path.dirname(args.config), f"{config_filename}_parallel")
        logger.info(f"Skipping split, using existing directory: {config_dir}")

    if not os.path.isdir(config_dir):
        logger.error(f"{colorama.Fore.RED}Error: Directory not found at '{config_dir}'")
        sys.exit(1)

    # Get all json files from the directory
    all_json_files = [f for f in os.listdir(config_dir) if f.endswith(".json")]

    # Find the base config name by inspecting the split files
    base_config_name = None
    # Find a file that is NOT a base config to inspect it for the 'extends' key
    sample_split_file = next((f for f in all_json_files if "base" not in f.lower()), None)

    if sample_split_file:
        with open(os.path.join(config_dir, sample_split_file), "r") as f:
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
    lock_files = [f for f in os.listdir(base_dir) if f.endswith(".lock")]
    for lock_file in lock_files:
        lock_file_path = os.path.join(base_dir, lock_file)
        try:
            os.remove(lock_file_path)
            logger.info(f"Removed stale lock file: {lock_file_path}")
        except OSError as e:
            logger.error(f"Error removing stale lock file {lock_file_path}: {e}")

    # Assign a unique ID to each process
    process_args = [(config, i + 1, args.no_cache) for i, config in enumerate(config_files_to_run)]

    # Use a multiprocessing Pool to run the studies in parallel
    with multiprocessing.Pool(processes=len(process_args)) as pool:
        pool.map(run_study_process, process_args)

    logger.info(f"{colorama.Fore.GREEN}All parallel studies completed.")


if __name__ == "__main__":
    # This is crucial for multiprocessing to work correctly, especially on Windows
    multiprocessing.freeze_support()
    main()
