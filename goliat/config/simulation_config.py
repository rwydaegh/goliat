"""Simulation-specific configuration building utilities."""

from typing import Optional


def build_surgical_gridding(gridding_params: dict, frequency_mhz: int) -> dict:
    """Extracts frequency-specific gridding parameters.

    This surgically extracts only the gridding value for the specific frequency,
    ensuring that changes to other frequencies don't invalidate hashes.

    Args:
        gridding_params: The full gridding parameters dictionary.
        frequency_mhz: The simulation frequency in MHz.

    Returns:
        A dictionary containing surgical gridding parameters.
    """
    surgical_gridding = {}
    # Copy non-frequency specific gridding params
    for key, value in gridding_params.items():
        if key != "global_gridding_per_frequency":
            surgical_gridding[key] = value

    # Extract only the relevant frequency's gridding value
    if "global_gridding_per_frequency" in gridding_params:
        freq_str = str(frequency_mhz)
        if freq_str in gridding_params["global_gridding_per_frequency"]:
            surgical_gridding["global_gridding_per_frequency"] = {freq_str: gridding_params["global_gridding_per_frequency"][freq_str]}

    return surgical_gridding


def build_near_field_simulation_config(
    config_accessor,
    surgical_config: dict,
    phantom_name: str,
    frequency_mhz: int,
    scenario_name: Optional[str],
    position_name: Optional[str],
    orientation_name: Optional[str],
) -> None:
    """Builds near-field specific configuration components.

    Args:
        config_accessor: Object with __getitem__ method to access config values.
        surgical_config: The configuration dictionary to populate.
        phantom_name: The name of the phantom model.
        frequency_mhz: The simulation frequency in MHz.
        scenario_name: The base name of the placement scenario.
        position_name: The name of the position within the scenario.
        orientation_name: The name of the orientation.
    """
    # Select the specific antenna config for the given frequency
    surgical_config["antenna_config"] = config_accessor[f"antenna_config.{frequency_mhz}"]

    # Reconstruct placement_scenarios for the specific placement
    if scenario_name:
        placement_scenarios = config_accessor["placement_scenarios"] or {}
        original_scenario = placement_scenarios.get(scenario_name) if isinstance(placement_scenarios, dict) else None
        if original_scenario and position_name and orientation_name:
            surgical_config["placement_scenarios"] = {
                scenario_name: {
                    "positions": {position_name: original_scenario["positions"][position_name]},
                    "orientations": {orientation_name: original_scenario["orientations"][orientation_name]},
                    "bounding_box": original_scenario.get("bounding_box", "default"),
                }
            }

    # Select the specific phantom definition
    phantom_definitions = config_accessor["phantom_definitions"] or {}
    surgical_config["phantom_definitions"] = {
        phantom_name: phantom_definitions.get(phantom_name, {}) if isinstance(phantom_definitions, dict) else {}
    }


def build_far_field_simulation_config(
    config_accessor,
    surgical_config: dict,
    phantom_name: str,
    direction_name: Optional[str],
    polarization_name: Optional[str],
) -> None:
    """Builds far-field specific configuration components.

    Args:
        config_accessor: Object with __getitem__ method to access config values.
        surgical_config: The configuration dictionary to populate.
        phantom_name: The name of the phantom model.
        direction_name: The incident direction of the plane wave.
        polarization_name: The polarization of the plane wave.
    """
    # Surgically build the far_field_setup to be robust against future changes
    original_ff_setup = config_accessor["far_field_setup"] or {}
    if original_ff_setup:
        surgical_config["far_field_setup"] = {
            "type": original_ff_setup.get("type"),
            "environmental": {
                "incident_directions": [direction_name],
                "polarizations": [polarization_name],
            },
        }
    # Also include the specific phantom definition, if it's not empty
    phantom_definitions = config_accessor["phantom_definitions"] or {}
    phantom_def = phantom_definitions.get(phantom_name, {}) if isinstance(phantom_definitions, dict) else {}
    if phantom_def:
        surgical_config["phantom_definitions"] = {phantom_name: phantom_def}
