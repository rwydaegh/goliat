import sys
from pathlib import Path
from typing import TYPE_CHECKING

import colorama

from goliat.osparc_batch.logging_utils import setup_console_logging

if TYPE_CHECKING:
    from goliat.config import Config

main_logger = setup_console_logging()


def _select_input_file(found_files: list[Path], results_folder: Path) -> Path:
    """Selects the most recent input file from multiple candidates and cleans up older files.

    Args:
        found_files: List of candidate input files found in the results folder.
        results_folder: Path to the results folder (for logging).

    Returns:
        The selected input file (most recent by modification time).
    """
    if len(found_files) > 1:
        main_logger.warning(
            f"{colorama.Fore.YELLOW}WARNING: Found {len(found_files)} input files in {results_folder}, expected 1. Using the most recent."
        )
        # Sort by modification time and take the most recent
        found_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        selected_file = found_files[0]

        # Delete older files
        for old_file in found_files[1:]:
            try:
                old_file.unlink()
                main_logger.info(f"Deleted older file: {old_file.name}")
            except OSError as e:
                main_logger.error(f"Error deleting file {old_file}: {e}")
    else:
        selected_file = found_files[0]

    return selected_file


def find_input_files(config: "Config") -> list[Path]:
    """Finds solver input files (.h5) and cleans up older files.

    Supports both far-field and near-field study types.
    """
    main_logger.info(f"{colorama.Fore.MAGENTA}--- Searching for input files based on configuration ---")
    results_base_dir = Path(config.base_dir) / "results"
    study_type = config["study_type"]
    phantoms = config["phantoms"] or []

    # Get frequencies based on study type
    if study_type == "far_field":
        frequencies = config["frequencies_mhz"] or []
        if not frequencies:
            raise ValueError("Far-field config must specify 'frequencies_mhz'.")
    elif study_type == "near_field":
        # Near-field uses antenna_config keys as frequencies
        antenna_config = config["antenna_config"] or {}
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

    Far-field has one file per phantom/frequency/direction/polarization combination.
    Each direction/polarization combination has its own project directory.
    """
    input_files: list[Path] = []

    # Get far-field setup configuration
    far_field_setup_config = config["far_field_setup"] or {}
    if not far_field_setup_config:
        main_logger.warning(f"{colorama.Fore.YELLOW}WARNING: No 'far_field_setup' in config.")
        return []

    far_field_setup = far_field_setup_config.get("environmental", {})
    if not far_field_setup:
        main_logger.warning(f"{colorama.Fore.YELLOW}WARNING: No 'environmental' far-field setup in config.")
        return []

    incident_directions = far_field_setup.get("incident_directions", [])
    polarizations = far_field_setup.get("polarizations", [])

    if not incident_directions or not polarizations:
        main_logger.warning(f"{colorama.Fore.YELLOW}WARNING: No incident directions or polarizations configured.")
        return []

    scenario_name = "environmental"
    total_combinations = len(incident_directions) * len(polarizations)
    main_logger.info(f"Looking for {total_combinations} direction/polarization combination(s) for {phantom} at {freq}MHz")

    # Search for input files in each direction/polarization directory
    for polarization_name in polarizations:
        for direction_name in incident_directions:
            # Placement name format: environmental_{polarization}_{direction}
            placement_name = f"{scenario_name}_{polarization_name}_{direction_name}"
            project_dir = results_base_dir / "far_field" / phantom.lower() / f"{freq}MHz" / placement_name
            project_filename_base = f"far_field_{phantom.lower()}_{freq}MHz_{placement_name}"
            results_folder = project_dir / f"{project_filename_base}.smash_Results"

            if not results_folder.exists():
                main_logger.warning(f"{colorama.Fore.YELLOW}WARNING: Results directory does not exist: {results_folder}")
                continue

            found_files = list(results_folder.glob("*_Input.h5"))
            if not found_files:
                main_logger.warning(f"{colorama.Fore.YELLOW}WARNING: No input files found in: {results_folder}")
                continue

            # For far-field, we expect exactly one input file per direction/polarization
            selected_file = _select_input_file(found_files, results_folder)

            main_logger.info(f"{colorama.Fore.CYAN}Found input file: {selected_file.name} ({placement_name})")
            input_files.append(selected_file)

    return input_files


def _find_near_field_input_files(config: "Config", results_base_dir: Path, phantom: str, freq: int) -> list[Path]:
    """Finds input files for near-field simulations.

    Near-field has one file per phantom/frequency/placement combination.
    """
    input_files: list[Path] = []

    # Get placement scenarios from config
    all_scenarios = config["placement_scenarios"] or {}
    phantom_definition = (config["phantom_definitions"] or {}).get(phantom, {})
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
        selected_file = _select_input_file(found_files, results_folder)

        main_logger.info(f"{colorama.Fore.CYAN}Found input file: {selected_file.name} ({placement_name})")
        input_files.append(selected_file)

    return input_files
