import hashlib
import json
import logging
import os
import time
from datetime import datetime
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

    def __init__(self, base_dir: str, config_filename: str = "near_field_config.json", no_cache: bool = False):
        """Initializes the Config object by loading all relevant configuration files.

        Args:
            base_dir: The base directory of the project.
            config_filename: The name of the main configuration file to load.
            no_cache: This parameter is accepted but not used directly by the Config class.
                      It's used by other managers to control caching behavior.
        """
        self.base_dir = base_dir
        self.config_path = self._resolve_config_path(config_filename, self.base_dir)
        self.material_mapping_path = os.path.join(self.base_dir, "data", "material_name_mapping.json")

        # Generate session hash for profiling config (similar to GUI session tracking)
        session_hash = hashlib.md5(f"{time.time()}_{os.getpid()}".encode()).hexdigest()[:8]
        data_dir = os.path.join(self.base_dir, "data")
        os.makedirs(data_dir, exist_ok=True)

        # Generate timestamp for filename
        session_timestamp = datetime.now().strftime("%d-%m_%H-%M-%S")

        # Cleanup old JSON files before creating new one
        self._cleanup_old_data_files(data_dir)

        self.profiling_config_path = os.path.join(data_dir, f"profiling_config_{session_timestamp}_{session_hash}.json")

        self.config = self._load_config_with_inheritance(self.config_path)
        self.material_mapping = self._load_json(self.material_mapping_path)

        # Load or initialize profiling config
        self.profiling_config = self._load_or_create_profiling_config()

    def _resolve_config_path(self, config_filename: str, base_path: str) -> str:
        """Resolves the absolute path to a config file.

        Handles both absolute paths and relative paths. If the filename doesn't
        end with .json, it's added automatically.

        Args:
            config_filename: Filename or relative path to the config.
            base_path: Base directory for resolving relative paths.

        Returns:
            Absolute path to the config file.
        """
        if os.path.isabs(config_filename) or os.path.dirname(config_filename):
            return os.path.join(self.base_dir, config_filename)

        if not config_filename.endswith(".json"):
            config_filename += ".json"

        return os.path.join(self.base_dir, "configs", config_filename)

    def __getitem__(self, path: str):
        """Allows dictionary-style access to config settings with dot-notation support.

        Returns None if the key/path doesn't exist, allowing for fallback patterns:
        - `config["simulation_parameters"] or {}`
        - `config["simulation_parameters.excitation_type"] or "Harmonic"`

        Args:
            path: The dot-separated path to the setting (e.g., "simulation_parameters" or "simulation_parameters.excitation_type").

        Returns:
            The value of the setting, or None if not found.

        Raises:
            KeyError: If the path is empty or invalid.
        """
        if not path:
            raise KeyError("Empty path")
        keys = path.split(".")
        current_config = self.config
        for key in keys:
            if isinstance(current_config, dict) and key in current_config:
                current_config = current_config[key]
            else:
                return None
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

    def _cleanup_old_data_files(self, data_dir: str):
        """Removes old CSV/JSON files from data/ when there are more than 50.

        Only cleans files matching specific patterns (time_remaining_, overall_progress_,
        profiling_config_). Files are sorted by creation time and oldest are deleted first.
        """
        try:
            # Get all CSV and JSON files in the data directory
            data_files = []
            for f in os.listdir(data_dir):
                if f.endswith(".csv") or f.endswith(".json"):
                    # Only include files with the expected naming pattern
                    if any(prefix in f for prefix in ["time_remaining_", "overall_progress_", "profiling_config_"]):
                        full_path = os.path.join(data_dir, f)
                        data_files.append(full_path)

            # Sort by creation time (oldest first)
            data_files.sort(key=os.path.getctime)

            # Remove oldest files if we have more than 50
            while len(data_files) > 50:
                old_file = None
                try:
                    old_file = data_files.pop(0)
                    os.remove(old_file)
                    logging.getLogger("verbose").info(f"Removed old data file: {os.path.basename(old_file)}")
                except OSError as e:
                    if old_file:
                        logging.getLogger("verbose").warning(f"Failed to remove {os.path.basename(old_file)}: {e}")
                    else:
                        logging.getLogger("verbose").warning(f"Failed to remove a file: {e}")
        except Exception as e:
            logging.getLogger("verbose").warning(f"Error during data file cleanup: {e}")

    def _load_or_create_profiling_config(self) -> dict:
        """Loads profiling config from disk, or creates a new one if missing.

        Returns:
            The profiling config dict, initialized with empty structure if new.
        """
        if os.path.exists(self.profiling_config_path):
            try:
                with open(self.profiling_config_path, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                # If file is corrupted, start fresh
                pass

        # Create a new profiling config with empty structure
        profiling_config = {}

        # Initialize with empty structure for each study type
        for study_type in ["near_field", "far_field"]:
            profiling_config[study_type] = {}

        # Save the initial config
        try:
            with open(self.profiling_config_path, "w") as f:
                json.dump(profiling_config, f, indent=4)
        except IOError:
            # If we can't write, just return the empty dict
            pass

        return profiling_config

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

    def get_download_email(self) -> str:
        """Returns the download email from environment variables.

        Raises:
            ValueError: If DOWNLOAD_EMAIL is not set in the environment.
        """
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
        """Returns whether to only write input files without running simulations."""
        result = self["execution_control.only_write_input_file"] or False
        assert isinstance(result, bool)
        return result

    def get_auto_cleanup_previous_results(self) -> list:
        """Gets the 'auto_cleanup_previous_results' setting from 'execution_control'.

        This setting determines which previous simulation files to automatically delete
        to preserve disk space. It should only be used in serial workflows.

        Returns:
            A list of file types to clean up (e.g., ["output", "input"]).
        """
        cleanup_setting = self["execution_control.auto_cleanup_previous_results"] or []

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
                surgical_config[key] = self[key]

        # 4. Surgically handle gridding parameters
        gridding_params = self["gridding_parameters"] or {}
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
        study_type = self["study_type"]
        if study_type == "near_field":
            # Select the specific antenna config for the given frequency
            surgical_config["antenna_config"] = self[f"antenna_config.{frequency_mhz}"]

            # Reconstruct placement_scenarios for the specific placement
            if scenario_name:
                placement_scenarios = self["placement_scenarios"] or {}
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
            phantom_definitions = self["phantom_definitions"] or {}
            surgical_config["phantom_definitions"] = {
                phantom_name: phantom_definitions.get(phantom_name, {}) if isinstance(phantom_definitions, dict) else {}
            }

        elif study_type == "far_field":
            # Surgically build the far_field_setup to be robust against future changes
            original_ff_setup = self["far_field_setup"] or {}
            if original_ff_setup:
                surgical_config["far_field_setup"] = {
                    "type": original_ff_setup.get("type"),
                    "environmental": {
                        "incident_directions": [direction_name],
                        "polarizations": [polarization_name],
                    },
                }
            # Also include the specific phantom definition, if it's not empty
            phantom_definitions = self["phantom_definitions"] or {}
            phantom_def = phantom_definitions.get(phantom_name, {}) if isinstance(phantom_definitions, dict) else {}
            if phantom_def:
                surgical_config["phantom_definitions"] = {phantom_name: phantom_def}

        return surgical_config
