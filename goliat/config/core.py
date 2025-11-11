import hashlib
import json
import os
import time
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv

from goliat.config.credentials import get_download_email, get_osparc_credentials
from goliat.config.file_management import cleanup_old_data_files
from goliat.config.merge import deep_merge
from goliat.config.profiling import get_profiling_config, load_or_create_profiling_config
from goliat.config.simulation_config import (
    build_far_field_simulation_config,
    build_near_field_simulation_config,
    build_surgical_gridding,
)

# Load environment variables from .env file
load_dotenv()

# Re-export deep_merge for backward compatibility
__all__ = ["Config", "deep_merge"]


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
        cleanup_old_data_files(data_dir)

        self.profiling_config_path = os.path.join(data_dir, f"profiling_config_{session_timestamp}_{session_hash}.json")

        self.config = self._load_config_with_inheritance(self.config_path)

        # Load material mapping - provide helpful error if missing
        try:
            self.material_mapping = self._load_json(self.material_mapping_path)
        except FileNotFoundError:
            raise FileNotFoundError(
                f"Material mapping file not found at: {self.material_mapping_path}\nPlease run 'goliat init' to set up the required files."
            )

        # Load or initialize profiling config
        self.profiling_config = load_or_create_profiling_config(self.profiling_config_path)

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
        return get_profiling_config(self.profiling_config, study_type)

    def get_download_email(self) -> str:
        """Returns the download email from environment variables.

        Raises:
            ValueError: If DOWNLOAD_EMAIL is not set in the environment.
        """
        return get_download_email()

    def get_osparc_credentials(self) -> dict:
        """Gets oSPARC credentials from environment variables.

        Raises:
            ValueError: If required oSPARC credentials are not set.

        Returns:
            A dictionary containing oSPARC API credentials.
        """
        return get_osparc_credentials()

    def get_only_write_input_file(self) -> bool:
        """Returns whether to only write input files without running simulations."""
        result = self["execution_control.only_write_input_file"]
        if result is None:
            result = False
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

        # 2. Surgically handle gridding parameters
        gridding_params = self["gridding_parameters"] or {}
        surgical_config["gridding_parameters"] = build_surgical_gridding(gridding_params, frequency_mhz)

        # 3. Add simulation-specific identifiers
        surgical_config["phantom"] = phantom_name
        surgical_config["frequency_mhz"] = frequency_mhz

        # 4. Surgically select study-specific parameters
        study_type = self["study_type"]
        if study_type == "near_field":
            build_near_field_simulation_config(
                self, surgical_config, phantom_name, frequency_mhz, scenario_name, position_name, orientation_name
            )
        elif study_type == "far_field":
            build_far_field_simulation_config(self, surgical_config, phantom_name, direction_name, polarization_name)

        return surgical_config
