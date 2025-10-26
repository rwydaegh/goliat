import argparse
import logging
import os
import sys
from pprint import pprint

import colorama


def setup_console_logging():
    """Sets up a basic console logger with color."""
    colorama.init(autoreset=True)
    logger = logging.getLogger("script_logger")
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    return logger


def find_results_to_delete(base_dir, include_near_field, include_far_field, frequencies, logger):
    """
    Scans the results directory and identifies .h5 output files to be deleted based on the criteria.
    """
    results_dir = os.path.join(base_dir, "results")
    if not os.path.isdir(results_dir):
        logger.error(f"{colorama.Fore.RED}Error: Results directory not found at '{results_dir}'")
        return []

    to_delete = []
    field_types_to_scan = []
    if include_near_field:
        field_types_to_scan.append("near_field")
    if include_far_field:
        field_types_to_scan.append("far_field")

    for field_type in field_types_to_scan:
        field_path = os.path.join(results_dir, field_type)
        if not os.path.isdir(field_path):
            continue

        for model_name in os.listdir(field_path):
            model_path = os.path.join(field_path, model_name)
            if not os.path.isdir(model_path):
                continue

            for freq_folder in os.listdir(model_path):
                if not freq_folder.endswith("MHz"):
                    continue

                freq_str = freq_folder.replace("MHz", "")
                if frequencies and freq_str not in frequencies:
                    continue

                # Walk through the frequency directory to find result files
                freq_dir_path = os.path.join(model_path, freq_folder)
                for root, dirs, files in os.walk(freq_dir_path):
                    if os.path.basename(root).endswith(".smash_Results"):
                        for file in files:
                            if file.endswith("_Output.h5"):
                                to_delete.append(os.path.join(root, file))

    return to_delete


def main():
    """
    Main function to scan for and delete simulation results.
    """
    logger = setup_console_logging()
    parser = argparse.ArgumentParser(description="Scan and delete simulation results.")
    parser.add_argument("--near-field", action="store_true", help="Include near-field results.")
    parser.add_argument("--far-field", action="store_true", help="Include far-field results.")
    parser.add_argument(
        "--frequencies",
        nargs="+",
        help="A list of frequencies in MHz to delete (e.g., 1450 2140).",
    )

    args = parser.parse_args()

    if not args.near_field and not args.far_field:
        logger.error(f"{colorama.Fore.RED}Error: Please specify at least one field type to clean up (--near-field and/or --far-field).")
        parser.print_help()
        sys.exit(1)

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    paths_to_delete = find_results_to_delete(project_root, args.near_field, args.far_field, args.frequencies, logger)

    if not paths_to_delete:
        logger.info(f"{colorama.Fore.GREEN}No matching result files found to delete.")
        return

    logger.warning(f"{colorama.Fore.YELLOW}The following files will be PERMANENTLY DELETED:")
    pprint(paths_to_delete)
    logger.warning(f"{colorama.Fore.YELLOW}{'-' * 70}")

    try:
        confirm = input("Are you sure you want to delete these files? [y/N]: ")
    except EOFError:
        logger.info(f"{colorama.Fore.CYAN}\nOperation cancelled by user (EOF).")
        sys.exit(1)

    if confirm.lower() == "y":
        logger.info(f"{colorama.Fore.GREEN}\nDeleting files...")
        for path in paths_to_delete:
            try:
                if os.path.isfile(path):
                    os.remove(path)
                    logger.info(f"  - Deleted: {path}")
                else:
                    logger.warning(f"{colorama.Fore.YELLOW}  - Warning: Expected a file, but path is not. Skipping: {path}")
            except OSError as e:
                logger.error(f"{colorama.Fore.RED}  - Error deleting {path}: {e}")
        logger.info(f"{colorama.Fore.GREEN}\nCleanup complete.")
    else:
        logger.info(f"{colorama.Fore.CYAN}\nOperation cancelled by user.")


if __name__ == "__main__":
    main()
