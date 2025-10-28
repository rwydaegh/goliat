import json
import os
from typing import Optional

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def deep_merge(source: dict, destination: dict) -> dict:
    """Recursively merges two dictionaries, overwriting destination with source values.

    Args:
        source: The dictionary with values to merge.
        destination: The dictionary to be merged into.

    Returns:
        The merged dictionary.
    """
    for key, value in source.items():
        if isinstance(value, dict) and key in destination and isinstance(destination[key], dict):
            deep_merge(value, destination[key])
        else:
            destination[key] = value
    return destination


class Config:
    """Manages loading and access of hierarchical JSON configurations."""

    def __init__(self, base_dir: str, config_filename: str = "near_field_config.json"):
        """Initializes the Config object by loading all relevant configuration files.

        Args:
            base_dir: The base directory of the project.
            config_filename: The name of the main configuration file to load.
        """
        self.base_dir = base_dir
        self.config_path = self._resolve_config_path(config_filename, self.base_dir)
        self.material_mapping_path = os.path.join(self.base_dir, "data", "material_name_mapping.json")
        self.profiling_config_path = os.path.join(self.base_dir, "configs", "profiling_config.json")

        self.config = self._load_config_with_inheritance(self.config_path)
        self.material_mapping = self._load_json(self.material_mapping_path)
        self.profiling_config = self._load_json(self.profiling_config_path)

    def _resolve_config_path(self, config_filename: str, base_path: str) -> str:
        """Resolves the absolute path to a configuration file.

        Args:
            config_filename: The name or path of the config file.
            base_path: The base directory to resolve relative paths from.

        Returns:
            The absolute path to the configuration file.
        """
        if os.path.isabs(config_filename) or os.path.dirname(config_filename):
            return os.path.join(self.base_dir, config_filename)

        if not config_filename.endswith(".json"):
            config_filename += ".json"

        return os.path.join(self.base_dir, "configs", config_filename)

    def get_setting(self, path: str, default=None):
        """Retrieves a nested setting using a dot-separated path.

        Example:
            `get_setting("simulation_parameters.number_of_point_sensors")`

        Args:
            path: The dot-separated path to the setting.
            default: The default value to return if the setting is not found.

        Returns:
            The value of the setting, or the default value.
        """
        keys = path.split(".")
        current_config = self.config
        for key in keys:
            if isinstance(current_config, dict) and key in current_config:
                current_config = current_config[key]
            else:
                return default
        return current_config

    def _load_config_with_inheritance(self, path: str) -> dict:
        """Loads a JSON config and handles 'extends' for inheritance.

        Args:
            path: The path to the configuration file.

        Returns:
            The fully resolved configuration dictionary.
        """
        config = self._load_json(path)

        if "extends" in config:
            base_config_path = self._resolve_config_path(config["extends"], base_path=os.path.dirname(path))
            base_config = self._load_config_with_inheritance(base_config_path)
            config = deep_merge(config, base_config)

        return config

    def _load_json(self, path: str) -> dict:
        """Loads a JSON file from a given path.

        Args:
            path: The path to the JSON file.

        Raises:
            FileNotFoundError: If the file does not exist.

        Returns:
            The loaded JSON data.
        """
        if not os.path.exists(path):
            raise FileNotFoundError(f"Configuration file not found at: {path}")
        with open(path, "r") as f:
            return json.load(f)

    def get_simulation_parameters(self) -> dict:
        """Gets the 'simulation_parameters' dictionary."""
        return self.config.get("simulation_parameters", {})

    def get_antenna_config(self) -> dict:
        """Gets the 'antenna_config' dictionary."""
        return self.config.get("antenna_config", {})

    def get_gridding_parameters(self) -> dict:
        """Gets the 'gridding_parameters' dictionary."""
        return self.config.get("gridding_parameters", {})

    def get_phantom_definition(self, phantom_name: str) -> dict:
        """Gets the configuration for a specific phantom.

        Args:
            phantom_name: The name of the phantom.

        Returns:
            The configuration for the specified phantom, or an empty dict if not found.
        """
        return self.config.get("phantom_definitions", {}).get(phantom_name, {})

    def get_material_mapping(self, phantom_name: str) -> dict:
        """Gets the material name mapping for a specific phantom.

        Args:
            phantom_name: The name of the phantom.

        Returns:
            The material mapping dictionary.
        """
        if phantom_name in self.material_mapping:
            return self.material_mapping[phantom_name]
        else:
            return self.material_mapping

    def get_solver_settings(self) -> dict:
        """Gets the 'solver_settings' dictionary."""
        return self.config.get("solver_settings", {})

    def get_antenna_component_names(self, antenna_model_type: str) -> list:
        """Gets component names for a specific antenna model type.

        Args:
            antenna_model_type: The type of the antenna model (e.g., 'PIFA').

        Returns:
            A list of component names.
        """
        return self.config.get("antenna_config", {}).get("components", {}).get(antenna_model_type)

    def get_manual_isolve(self) -> bool:
        """Gets the 'manual_isolve' boolean flag."""
        return self.config.get("manual_isolve", False)

    def get_freespace_expansion(self) -> list:
        """Gets the freespace antenna bounding box expansion in millimeters."""
        return self.get_simulation_parameters().get("freespace_antenna_bbox_expansion_mm", [10, 10, 10])

    def get_excitation_type(self) -> str:
        """Gets the simulation excitation type (e.g., 'Harmonic', 'Gaussian')."""
        return self.get_simulation_parameters().get("excitation_type", "Harmonic")

    def get_bandwidth(self) -> float:
        """Gets the simulation bandwidth in MHz for Gaussian excitation."""
        return self.get_simulation_parameters().get("bandwidth_mhz", 50.0)

    def get_placement_scenario(self, scenario_name: str) -> dict:
        """Gets the definition for a specific placement scenario.

        Args:
            scenario_name: The name of the placement scenario.

        Returns:
            The configuration for the placement scenario.
        """
        return self.config.get("placement_scenarios", {}).get(scenario_name)

    def get_profiling_config(self, study_type: str) -> dict:
        """Gets the profiling configuration for a given study type.

        Args:
            study_type: The type of the study (e.g., 'near_field').

        Returns:
            The profiling configuration for the study type.
        """
        if study_type not in self.profiling_config:
            import logging

            logging.warning(f"Profiling configuration not defined for study type: {study_type}. Returning empty configuration.")
            return {}
        return self.profiling_config[study_type]

    def get_line_profiling_config(self) -> dict:
        """Gets the 'line_profiling' settings."""
        return self.get_setting("line_profiling", {}) or {}

    def get_download_email(self) -> str:
        """Gets the download email from environment variables."""
        email = os.getenv("DOWNLOAD_EMAIL")
        if not email:
            raise ValueError("Missing DOWNLOAD_EMAIL. Please set this in your .env file.")
        return email

    def get_osparc_credentials(self) -> dict:
        """Gets oSPARC credentials from environment variables.

        Raises:
            ValueError: If required oSPARC credentials are not set.

        Returns:
            A dictionary containing oSPARC API credentials.
        """
        credentials = {
            "api_key": os.getenv("OSPARC_API_KEY"),
            "api_secret": os.getenv("OSPARC_API_SECRET"),
            "api_server": "https://api.sim4life.science",
            "api_version": "v0",
        }

        missing = [key for key, value in credentials.items() if value is None and key != "api_version"]
        if missing:
            raise ValueError(
                f"Missing oSPARC credentials: {', '.join(missing)}. "
                "Please create a .env file in the project root with your oSPARC API credentials. "
                "See README.md for setup instructions."
            )

        return credentials

    def get_only_write_input_file(self) -> bool:
        """Gets the 'only_write_input_file' flag from 'execution_control'."""
        result = self.get_setting("execution_control.only_write_input_file", False)
        assert isinstance(result, bool)
        return result

    def get_auto_cleanup_previous_results(self) -> list:
        """Gets the 'auto_cleanup_previous_results' setting from 'execution_control'.

        This setting determines which previous simulation files to automatically delete
        to preserve disk space. It should only be used in serial workflows.

        Returns:
            A list of file types to clean up (e.g., ["output", "input"]).
        """
        cleanup_setting = self.get_setting("execution_control.auto_cleanup_previous_results", [])

        # Handle legacy boolean format for backwards compatibility
        if isinstance(cleanup_setting, bool):
            if cleanup_setting:
                # Legacy behavior: only clean output files
                return ["output"]
            else:
                return []

        # Validate that it's a list
        if not isinstance(cleanup_setting, list):
            import logging

            logging.warning(f"'auto_cleanup_previous_results' should be a list, got {type(cleanup_setting)}. Disabling cleanup for safety.")
            return []

        # Validate file types
        valid_types = {"output", "input", "smash"}
        invalid_types = [t for t in cleanup_setting if t not in valid_types]
        if invalid_types:
            import logging

            logging.warning(f"Invalid file types in 'auto_cleanup_previous_results': {invalid_types}. Valid types are: {valid_types}")

        return [t for t in cleanup_setting if t in valid_types]

    def build_simulation_config(
        self,
        phantom_name: str,
        frequency_mhz: int,
        scenario_name: Optional[str] = None,
        position_name: Optional[str] = None,
        orientation_name: Optional[str] = None,
        direction_name: Optional[str] = None,
        polarization_name: Optional[str] = None,
    ) -> dict:
        """Constructs a minimal, simulation-specific configuration dictionary.

        This method is the core of the "Verify and Resume" feature. It creates a
        "surgical" snapshot of the configuration that is unique to a single
        simulation run. This snapshot is then hashed to determine if a valid,
        reusable simulation already exists.

        The key principle is to only include parameters that directly affect the
        outcome of the specific simulation. For example, instead of including the
        entire 'gridding_parameters' block, it surgically extracts only the
        gridding value for the specific 'frequency_mhz' being used. This ensures
        that a change to one frequency's gridding in the main config does not
        invalidate the hashes for other, unaffected frequencies.

        Args:
            phantom_name: The name of the phantom model.
            frequency_mhz: The simulation frequency in MHz.
            scenario_name: (Near-Field) The base name of the placement scenario.
            position_name: (Near-Field) The name of the position within the scenario.
            orientation_name: (Near-Field) The name of the orientation.
            direction_name: (Far-Field) The incident direction of the plane wave.
            polarization_name: (Far-Field) The polarization of the plane wave.

        Returns:
            A dictionary containing the minimal, surgical configuration snapshot.
        """
        surgical_config = {}

        # 1. Copy global parameters
        global_keys = [
            "study_type",
            "simulation_parameters",
            "solver_settings",
            "manual_isolve",
            "export_material_properties",
        ]
        for key in global_keys:
            if key in self.config:
                surgical_config[key] = self.config[key]

        # 4. Surgically handle gridding parameters
        gridding_params = self.get_gridding_parameters()
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

        surgical_config["gridding_parameters"] = surgical_gridding

        # 2. Add simulation-specific identifiers
        surgical_config["phantom"] = phantom_name
        surgical_config["frequency_mhz"] = frequency_mhz

        # 3. Surgically select study-specific parameters
        study_type = self.get_setting("study_type")
        if study_type == "near_field":
            # Select the specific antenna config for the given frequency
            surgical_config["antenna_config"] = self.get_setting(f"antenna_config.{frequency_mhz}")

            # Reconstruct placement_scenarios for the specific placement
            if scenario_name:
                original_scenario = self.get_placement_scenario(scenario_name)
                if original_scenario and position_name and orientation_name:
                    surgical_config["placement_scenarios"] = {
                        scenario_name: {
                            "positions": {position_name: original_scenario["positions"][position_name]},
                            "orientations": {orientation_name: original_scenario["orientations"][orientation_name]},
                            "bounding_box": original_scenario.get("bounding_box", "default"),
                        }
                    }

            # Select the specific phantom definition
            surgical_config["phantom_definitions"] = {phantom_name: self.get_phantom_definition(phantom_name)}

        elif study_type == "far_field":
            # Surgically build the far_field_setup to be robust against future changes
            original_ff_setup = self.get_setting("far_field_setup", {})
            if original_ff_setup:
                surgical_config["far_field_setup"] = {
                    "type": original_ff_setup.get("type"),
                    "environmental": {
                        "incident_directions": [direction_name],
                        "polarizations": [polarization_name],
                    },
                }
            # Also include the specific phantom definition, if it's not empty
            phantom_def = self.get_phantom_definition(phantom_name)
            if phantom_def:
                surgical_config["phantom_definitions"] = {phantom_name: phantom_def}

        return surgical_config
