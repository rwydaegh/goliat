"""CLI module for creating and uploading super studies to the web dashboard."""

import argparse
import json
import logging
import os
import sys
from copy import deepcopy

import colorama

from goliat.colors import init_colorama

try:
    import requests

    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

# Base directory for config files
from cli.utils import get_base_dir

base_dir = get_base_dir()


def setup_console_logging():
    """Sets up a basic console logger with color."""
    init_colorama()
    logger = logging.getLogger("super_study_logger")
    logger.setLevel(logging.INFO)
    logger.propagate = False  # Prevent propagation to root logger
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
    """
    Splits the configuration file into multiple assignment configs.

    Returns: (base_config, assignment_configs) where assignment_configs is a list of dicts
    """
    if not os.path.exists(config_path):
        logger.error(f"{colorama.Fore.RED}Error: Config file not found at '{config_path}'")
        sys.exit(1)

    with open(config_path, "r") as f:
        base_config = json.load(f)

    # Extract phantoms
    base_phantoms = base_config.get("phantoms", [])
    is_near_field_dict = isinstance(base_phantoms, dict)
    if is_near_field_dict:
        base_phantoms = list(base_phantoms.keys())

    num_phantoms = len(base_phantoms)
    study_type = base_config.get("study_type")

    # Extract frequencies (far-field) or antennas (near-field)
    if study_type == "near_field":
        antenna_configs = base_config.get("antenna_config", {})
        items = list(antenna_configs.keys())
        items_name = "antennas"
    else:
        items = base_config.get("frequencies_mhz", [])
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
        f"Smart split strategy: {phantom_splits} phantom group(s) × {item_splits} {items_name} group(s) = {total_splits} total assignments"
    )

    # Split phantoms and items into groups
    phantom_groups = split_list_into_n(base_phantoms, phantom_splits)
    item_groups = split_list_into_n(items, item_splits)

    logger.info(f"Phantom groups: {[len(g) for g in phantom_groups]}")
    logger.info(f"{items_name.capitalize()} groups: {[len(g) for g in item_groups]}")

    # Create cartesian product of phantom and item groups
    assignment_configs = []
    for i, phantom_group in enumerate(phantom_groups):
        for j, item_group in enumerate(item_groups):
            assignment_config = deepcopy(base_config)

            # Update phantoms
            if is_near_field_dict:
                # Near-field dict format: keep only selected phantoms
                original_phantoms_dict = base_config.get("phantoms", {})
                assignment_config["phantoms"] = {p: original_phantoms_dict[p] for p in phantom_group}
            else:
                # Far-field list format
                assignment_config["phantoms"] = phantom_group

            # Update frequencies or antennas
            if study_type == "near_field":
                original_antenna_config = base_config.get("antenna_config", {})
                assignment_config["antenna_config"] = {key: original_antenna_config[key] for key in item_group}
            else:
                assignment_config["frequencies_mhz"] = item_group

            assignment_configs.append(
                {"config": assignment_config, "phantoms": phantom_group, "items": item_group, "items_name": items_name}
            )

    return base_config, assignment_configs


def upload_super_study(name, description, base_config, assignment_configs, server_url, logger):
    """Upload a super study to the web dashboard."""
    if not REQUESTS_AVAILABLE:
        logger.error(f"{colorama.Fore.RED}Error: requests library is required. Install with: pip install requests")
        sys.exit(1)

    try:
        # Create super study
        payload = {
            "name": name,
            "description": description or "",
            "baseConfig": base_config,
            "assignments": [{"splitConfig": assignment["config"], "status": "PENDING"} for assignment in assignment_configs],
        }

        logger.info(f"Uploading super study '{name}' to {server_url}...")
        response = requests.post(f"{server_url}/api/super-studies", json=payload, timeout=30)

        if response.status_code == 200:
            result = response.json()
            logger.info(f"{colorama.Fore.GREEN}✓ Super study created successfully!")
            logger.info(f"  ID: {result['id']}")
            logger.info(f"  Name: {result['name']}")
            logger.info(f"  Total assignments: {result['totalAssignments']}")
            logger.info(f"\n{colorama.Fore.CYAN}View it on the dashboard: {server_url}/super-studies/{result['id']}")
            logger.info(f"\n{colorama.Fore.YELLOW}Workers can now run:")
            logger.info(f"  goliat worker <N> {name}")
            return result
        else:
            logger.error(f"{colorama.Fore.RED}Error: Server returned status {response.status_code}")
            logger.error(f"Response: {response.text[:500]}")
            sys.exit(1)

    except requests.exceptions.ConnectionError:
        logger.error(f"{colorama.Fore.RED}Error: Could not connect to {server_url}")
        logger.error("Make sure the server is running and accessible.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"{colorama.Fore.RED}Error uploading super study: {e}")
        sys.exit(1)


def main():
    """Main function to create and upload a super study."""
    logger = setup_console_logging()
    parser = argparse.ArgumentParser(description="Create a super study by splitting a config file and uploading it to the web dashboard.")
    parser.add_argument(
        "config",
        type=str,
        help="Path to the configuration file (e.g., configs/near_field_config.json).",
    )
    parser.add_argument(
        "--name",
        type=str,
        required=True,
        help="Name for the super study (used by workers to join).",
    )
    parser.add_argument(
        "--description",
        type=str,
        default="",
        help="Optional description for the super study.",
    )
    parser.add_argument(
        "--num-splits",
        type=int,
        default=4,
        help="Number of assignments to split into (default: 4).",
    )
    parser.add_argument(
        "--server-url",
        type=str,
        default=None,
        help="URL of the monitoring server (default: https://goliat.waves-ugent.be).",
    )

    args = parser.parse_args()

    # Get server URL: command arg > env var > hardcoded default
    server_url = args.server_url or os.getenv("GOLIAT_MONITORING_URL") or "https://goliat.waves-ugent.be"
    server_url = server_url.rstrip("/")

    if args.num_splits < 1:
        logger.error(f"{colorama.Fore.RED}Error: --num-splits must be at least 1.")
        sys.exit(1)

    logger.info(f"{colorama.Fore.CYAN}Creating super study '{args.name}'...")
    logger.info(f"  Config: {args.config}")
    logger.info(f"  Splits: {args.num_splits}")
    logger.info(f"  Server: {server_url}\n")

    # Split the config
    base_config, assignment_configs = split_config(args.config, args.num_splits, logger)

    # Upload to server
    upload_super_study(args.name, args.description, base_config, assignment_configs, server_url, logger)


if __name__ == "__main__":
    main()
