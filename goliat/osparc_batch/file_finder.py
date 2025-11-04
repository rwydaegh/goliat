import statistics
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import colorama

from goliat.osparc_batch.logging_utils import setup_console_logging

if TYPE_CHECKING:
    from goliat.config import Config

main_logger = setup_console_logging()


def find_input_files(config: "Config") -> list[Path]:
    """Finds solver input files (.h5) and cleans up older files.

    Supports both far-field and near-field study types.
    """
    main_logger.info(f"{colorama.Fore.MAGENTA}--- Searching for input files based on configuration ---")
    results_base_dir = Path(config.base_dir) / "results"
    study_type = config.get_setting("study_type")
    phantoms = config.get_setting("phantoms", [])

    # Get frequencies based on study type
    if study_type == "far_field":
        frequencies = config.get_setting("frequencies_mhz", [])
        if not frequencies:
            raise ValueError("Far-field config must specify 'frequencies_mhz'.")
    elif study_type == "near_field":
        # Near-field uses antenna_config keys as frequencies
        antenna_config = config.get_setting("antenna_config", {})
        if not antenna_config:
            raise ValueError("Near-field config must specify 'antenna_config'.")
        frequencies = [int(freq_str) for freq_str in antenna_config.keys()]
    else:
        raise ValueError(f"Unknown study_type: {study_type}")

    if not all([study_type, phantoms]):
        raise ValueError("Config must specify 'study_type' and 'phantoms'.")

    all_input_files: list[Path] = []
    if phantoms:
        for phantom in phantoms:
            for freq in frequencies:
                if study_type == "far_field":
                    all_input_files.extend(_find_far_field_input_files(config, results_base_dir, phantom, freq))
                elif study_type == "near_field":
                    all_input_files.extend(_find_near_field_input_files(config, results_base_dir, phantom, freq))

    if not all_input_files:
        main_logger.error(f"{colorama.Fore.RED}ERROR: Could not find any input files to process.")
        sys.exit(1)

    main_logger.info(f"{colorama.Fore.GREEN}--- Found a total of {len(all_input_files)} input files to process. ---")
    return all_input_files


def _find_far_field_input_files(config: "Config", results_base_dir: Path, phantom: str, freq: int) -> list[Path]:
    """Finds input files for far-field simulations.

    Far-field has multiple files per phantom/frequency (one for each
    direction/polarization).
    """
    project_dir = results_base_dir / "far_field" / phantom.lower() / f"{freq}MHz"
    project_filename_base = f"far_field_{phantom.lower()}_{freq}MHz"
    results_folder = project_dir / f"{project_filename_base}.smash_Results"

    if not results_folder.exists():
        main_logger.warning(f"{colorama.Fore.YELLOW}WARNING: Results directory does not exist: {results_folder}")
        return []

    found_files = list(results_folder.glob("*_Input.h5"))
    if not found_files:
        main_logger.warning(f"{colorama.Fore.YELLOW}WARNING: No input files found in: {results_folder}")
        return []

    main_logger.info(f"{colorama.Fore.CYAN}Found {len(found_files)} raw input file(s) in: {results_folder}")

    # --- Grouping Logic ---
    far_field_setup_config = config.get_setting("far_field_setup", {})
    if not far_field_setup_config:
        main_logger.warning(f"{colorama.Fore.YELLOW}WARNING: No 'far_field_setup' in config. Using all found files.")
        return found_files

    far_field_setup = far_field_setup_config.get("environmental", {})
    if not far_field_setup:
        main_logger.warning(f"{colorama.Fore.YELLOW}WARNING: No 'environmental' far-field setup in config. Using all found files.")
        return found_files

    inc_dirs = far_field_setup.get("incident_directions", [])
    pols = far_field_setup.get("polarizations", [])
    expected_count = len(inc_dirs) * len(pols)
    main_logger.info(f"Expected file count per batch: {expected_count} ({len(inc_dirs)} dirs x {len(pols)} pols)")

    if len(found_files) < expected_count:
        main_logger.warning(
            f"{colorama.Fore.YELLOW}WARNING: Not enough files for a full batch ({len(found_files)}/{expected_count}). Using all available."
        )
        return found_files

    files_with_mtime = sorted([(f, f.stat().st_mtime) for f in found_files], key=lambda x: x, reverse=True)

    main_logger.info("Analyzing file timestamps to find the latest batch...")
    latest_files = files_with_mtime[:expected_count]

    # Simple approach: take the N youngest files
    selected_files = [f for f, _ in latest_files]
    main_logger.info(f"{colorama.Fore.GREEN}Selected the latest {len(selected_files)} files based on modification time.")

    # --- Time Gap Analysis ---
    if len(latest_files) > 1:
        time_diffs = [latest_files[i] - latest_files[i + 1] for i in range(len(latest_files) - 1)]  # type: ignore
        time_diffs_str = ", ".join([f"{diff:.2f}s" for diff in time_diffs])
        main_logger.info(f"{colorama.Fore.YELLOW}Time gaps between files: [{time_diffs_str}].")

        if len(time_diffs) > 3:
            max_diff = max(time_diffs)
            other_diffs = [d for d in time_diffs if d != max_diff]

            if len(other_diffs) > 1:
                mean_diff = statistics.mean(other_diffs)

                if max_diff > 2 * mean_diff:
                    main_logger.warning(
                        f"{colorama.Back.RED}{colorama.Fore.WHITE}CRITICAL WARNING: "
                        f"Potential old input file detected!{colorama.Style.RESET_ALL}"
                    )
                    main_logger.warning(
                        f"The largest time gap ({max_diff:.2f}s) is significantly larger than expected (mean: {mean_diff:.2f}s)."
                    )
                    main_logger.warning("Please verify the input files are from the correct batch.")

                    response = input("Do you want to continue anyway? (y/n): ").lower()
                    if response != "y":
                        main_logger.error("Aborting due to user request.")
                        sys.exit(1)

    # --- Cleanup Logic ---
    unselected_files = [f for f, _ in files_with_mtime[expected_count:]]
    if unselected_files:
        main_logger.info(f"{colorama.Fore.YELLOW}--- Deleting {len(unselected_files)} older input files ---")
        for f in unselected_files:
            try:
                f.unlink()
                main_logger.info(f"Deleted: {f.name}")
            except OSError as e:
                main_logger.error(f"Error deleting file {f}: {e}")

    return selected_files


def _find_near_field_input_files(config: "Config", results_base_dir: Path, phantom: str, freq: int) -> list[Path]:
    """Finds input files for near-field simulations.

    Near-field has one file per phantom/frequency/placement combination.
    """
    input_files: list[Path] = []

    # Get placement scenarios from config
    all_scenarios = config.get_setting("placement_scenarios", {})
    phantom_definition = config.get_phantom_definition(phantom)
    placements_config = phantom_definition.get("placements", {}) if phantom_definition else {}

    if not placements_config:
        main_logger.warning(f"{colorama.Fore.YELLOW}WARNING: No placement config found for phantom '{phantom}'.")
        return []

    # Build list of enabled placements
    enabled_placements = []
    if all_scenarios:
        for scenario_name, scenario_details in all_scenarios.items():
            if placements_config.get(f"do_{scenario_name}"):
                positions = scenario_details.get("positions", {})
                orientations = scenario_details.get("orientations", {})
                for pos_name in positions.keys():
                    for orient_name in orientations.keys():
                        placement_name = f"{scenario_name}_{pos_name}_{orient_name}"
                        enabled_placements.append(placement_name)

    if not enabled_placements:
        main_logger.warning(f"{colorama.Fore.YELLOW}WARNING: No enabled placements found for phantom '{phantom}'.")
        return []

    main_logger.info(f"Looking for {len(enabled_placements)} placement(s) for {phantom} at {freq}MHz")

    # Search for input files in each placement directory
    for placement_name in enabled_placements:
        project_dir = results_base_dir / "near_field" / phantom.lower() / f"{freq}MHz" / placement_name
        project_filename_base = f"near_field_{phantom.lower()}_{freq}MHz_{placement_name}"
        results_folder = project_dir / f"{project_filename_base}.smash_Results"

        if not results_folder.exists():
            main_logger.warning(f"{colorama.Fore.YELLOW}WARNING: Results directory does not exist: {results_folder}")
            continue

        found_files = list(results_folder.glob("*_Input.h5"))
        if not found_files:
            main_logger.warning(f"{colorama.Fore.YELLOW}WARNING: No input files found in: {results_folder}")
            continue

        # For near-field, we expect exactly one input file per placement
        if len(found_files) > 1:
            main_logger.warning(
                f"{colorama.Fore.YELLOW}WARNING: Found {len(found_files)} input files in {results_folder}, "
                f"expected 1. Using the most recent."
            )
            # Sort by modification time and take the most recent
            found_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
            selected_file = found_files

            # Delete older files
            for old_file in found_files[1:]:
                try:
                    old_file.unlink()
                    main_logger.info(f"Deleted older file: {old_file.name}")
                except OSError as e:
                    main_logger.error(f"Error deleting file {old_file}: {e}")
        else:
            selected_file = found_files

        main_logger.info(f"{colorama.Fore.CYAN}Found input file: {selected_file.name}")  # type: ignore
        input_files.append(selected_file)  # type: ignore

    return input_files
