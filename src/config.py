import json
import os

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def deep_merge(source, destination):
    """
    Recursively merges two dictionaries.

    Values from the `source` dictionary overwrite values in the `destination`
    dictionary. If a key exists in both dictionaries and its value is a
    dictionary in both, the function will recurse.

    Args:
        source (dict): The dictionary with values to merge.
        destination (dict): The dictionary to be merged into.

    Returns:
        dict: The merged dictionary.
    """
    for key, value in source.items():
        if (
            isinstance(value, dict)
            and key in destination
            and isinstance(destination[key], dict)
        ):
            deep_merge(value, destination[key])
        else:
            destination[key] = value
    return destination


class Config:
    """
    Manages loading, validation, and access of configuration files.

    This class supports a hierarchical configuration system where a main
    configuration file can extend a base file, inheriting its settings and
    overriding them as needed. It also loads material mappings and profiling
    configurations.
    """

    def __init__(self, base_dir, config_filename="near_field_config.json"):
        """
        Initializes the Config object by loading all relevant configuration files.

        Args:
            base_dir (str): The base directory of the project.
            config_filename (str): The name of the main configuration file to load.
        """
        self.base_dir = base_dir
        self.config_path = self._resolve_config_path(config_filename, self.base_dir)
        self.material_mapping_path = os.path.join(
            self.base_dir, "data", "material_name_mapping.json"
        )
        self.profiling_config_path = os.path.join(
            self.base_dir, "configs", "profiling_config.json"
        )

        self.config = self._load_config_with_inheritance(self.config_path)
        self.material_mapping = self._load_json(self.material_mapping_path)
        self.profiling_config = self._load_json(self.profiling_config_path)

    def _resolve_config_path(self, config_filename, base_path):
        """
        Resolves the absolute path to a configuration file.

        - If a full path is given, it's used directly relative to the project root.
        - If a filename without '.json' is given, it's assumed to be in 'configs/'.

        Args:
            config_filename (str): The name or path of the config file.
            base_path (str): The base directory to resolve relative paths from.

        Returns:
            str: The absolute path to the configuration file.
        """
        if os.path.isabs(config_filename) or os.path.dirname(config_filename):
            return os.path.join(self.base_dir, config_filename)

        if not config_filename.endswith(".json"):
            config_filename += ".json"

        return os.path.join(self.base_dir, "configs", config_filename)

    def get_setting(self, path, default=None):
        """
        Retrieves a nested setting from the configuration using a dot-separated path.

        Example:
            `get_setting("simulation_parameters.number_of_point_sensors")`

        Args:
            path (str): The dot-separated path to the setting.
            default (any, optional): The default value to return if the setting is not found.

        Returns:
            any: The value of the setting, or the default value.
        """
        keys = path.split(".")
        current_config = self.config
        for key in keys:
            if isinstance(current_config, dict) and key in current_config:
                current_config = current_config[key]
            else:
                return default
        return current_config

    def _load_config_with_inheritance(self, path):
        """
        Loads a JSON configuration file and handles the 'extends' keyword for inheritance.

        If a config file contains an "extends" key, it recursively loads the base
        configuration and merges the current configuration over it.

        Args:
            path (str): The path to the configuration file.

        Returns:
            dict: The fully resolved configuration dictionary.
        """
        config = self._load_json(path)

        if "extends" in config:
            base_config_path = self._resolve_config_path(
                config["extends"], base_path=os.path.dirname(path)
            )
            base_config = self._load_config_with_inheritance(base_config_path)
            config = deep_merge(config, base_config)

        return config

    def _load_json(self, path):
        """
        Loads a JSON file from a given path.

        Args:
            path (str): The path to the JSON file.

        Raises:
            FileNotFoundError: If the file does not exist.

        Returns:
            dict: The loaded JSON data.
        """
        if not os.path.exists(path):
            raise FileNotFoundError(f"Configuration file not found at: {path}")
        with open(path, "r") as f:
            return json.load(f)

    def get_simulation_parameters(self):
        """Retrieves the 'simulation_parameters' dictionary from the configuration."""
        return self.config.get("simulation_parameters", {})

    def get_antenna_config(self):
        """Retrieves the 'antenna_config' dictionary from the configuration."""
        return self.config.get("antenna_config", {})

    def get_gridding_parameters(self):
        """Retrieves the 'gridding_parameters' dictionary from the configuration."""
        return self.config.get("gridding_parameters", {})

    def get_phantom_config(self, phantom_name):
        """
        Retrieves the configuration for a specific phantom from 'phantom_definitions'.

        Args:
            phantom_name (str): The name of the phantom.

        Returns:
            dict: The configuration dictionary for the specified phantom.
        """
        return self.config.get("phantom_definitions", {}).get(phantom_name)

    def get_phantom_placements(self, phantom_name):
        """
        Retrieves the placement configuration for a specific phantom.

        Args:
            phantom_name (str): The name of the phantom.

        Returns:
            dict: A dictionary of enabled placements for the phantom.
        """
        phantom_config = self.get_phantom_config(phantom_name)
        if phantom_config:
            return phantom_config.get("placements", {})
        return {}

    def get_material_mapping(self, phantom_name):
        """
        Retrieves the material name mapping for a specific phantom.

        Args:
            phantom_name (str): The name of the phantom.

        Returns:
            dict: The material mapping dictionary.
        """
        if phantom_name in self.material_mapping:
            return self.material_mapping[phantom_name]
        else:
            return self.material_mapping

    def get_solver_settings(self):
        """Retrieves the 'solver_settings' dictionary from the configuration."""
        return self.config.get("solver_settings", {})

    def get_antenna_component_names(self, antenna_model_type):
        """
        Retrieves the component names for a specific antenna model type.

        Args:
            antenna_model_type (str): The type of the antenna model (e.g., 'PIFA').

        Returns:
            list: A list of component names.
        """
        return (
            self.config.get("antenna_config", {})
            .get("components", {})
            .get(antenna_model_type)
        )

    def get_manual_isolve(self):
        """Retrieves the 'manual_isolve' boolean flag from the configuration."""
        return self.config.get("manual_isolve", False)

    def get_freespace_expansion(self):
        """Retrieves the freespace antenna bounding box expansion in millimeters."""
        return self.get_simulation_parameters().get(
            "freespace_antenna_bbox_expansion_mm", [10, 10, 10]
        )

    def get_excitation_type(self):
        """Retrieves the simulation excitation type (e.g., 'Harmonic', 'Gaussian')."""
        return self.get_simulation_parameters().get("excitation_type", "Harmonic")

    def get_bandwidth(self):
        """Retrieves the simulation bandwidth in MHz for Gaussian excitation."""
        return self.get_simulation_parameters().get("bandwidth_mhz", 50.0)

    def get_placement_scenario(self, scenario_name):
        """
        Retrieves the definition for a specific placement scenario.

        Args:
            scenario_name (str): The name of the placement scenario.

        Returns:
            dict: The configuration for the placement scenario.
        """
        return self.config.get("placement_scenarios", {}).get(scenario_name)

    def get_profiling_config(self, study_type):
        """
        Retrieves the specific profiling configuration for the given study type.

        Args:
            study_type (str): The type of the study (e.g., 'near_field').

        Returns:
            dict: The profiling configuration for the study type.
        """
        if study_type not in self.profiling_config:
            import logging

            logging.warning(
                f"Profiling configuration not defined for study type: {study_type}. Returning empty configuration."
            )
            return {}
        return self.profiling_config[study_type]

    def get_line_profiling_config(self):
        """Retrieves the 'line_profiling' settings from the main configuration."""
        return self.get_setting("line_profiling", {})

    def get_download_email(self):
        """Retrieves the download email from environment variables."""
        email = os.getenv("DOWNLOAD_EMAIL")
        if not email:
            raise ValueError(
                "Missing DOWNLOAD_EMAIL. Please set this in your .env file."
            )
        return email

    def get_osparc_credentials(self):
        """
        Retrieves oSPARC credentials from environment variables.

        Raises:
            ValueError: If any required oSPARC credentials are not set in the .env file.

        Returns:
            dict: A dictionary containing oSPARC API key, secret, server, and version.
        """
        credentials = {
            "api_key": os.getenv("OSPARC_API_KEY"),
            "api_secret": os.getenv("OSPARC_API_SECRET"),
            "api_server": "https://api.sim4life.science",
            "api_version": "v0",
        }

        missing = [
            key
            for key, value in credentials.items()
            if value is None and key != "api_version"
        ]
        if missing:
            raise ValueError(
                f"Missing oSPARC credentials: {', '.join(missing)}. "
                "Please create a .env file in the project root with your oSPARC API credentials. "
                "See README.md for setup instructions."
            )

        return credentials

    def get_only_write_input_file(self):
        """
        Retrieves the 'only_write_input_file' flag from 'execution_control'.

        This flag determines whether to run the full simulation or only generate
        the solver input files.

        Returns:
            bool: The value of the 'only_write_input_file' flag.
        """
        return self.get_setting("execution_control.only_write_input_file", False)

    def get_auto_cleanup_previous_results(self):
        """
        Retrieves the 'auto_cleanup_previous_results' setting from 'execution_control'.

        This setting determines which previous simulation files to automatically delete
        before starting a new simulation. This helps preserve disk space but should only
        be used in serial workflows where setup, run, and extract are all enabled.

        Valid file types:
        - "output": Deletes *_Output.h5 files (simulation results)
        - "input": Deletes *_Input.h5 files (solver input files)
        - "smash": Deletes *.smash files (project files)

        Returns:
            list: A list of file types to clean up. Empty list means no cleanup.
        """
        cleanup_setting = self.get_setting(
            "execution_control.auto_cleanup_previous_results", []
        )

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

            logging.warning(
                f"'auto_cleanup_previous_results' should be a list, got {type(cleanup_setting)}. "
                "Disabling cleanup for safety."
            )
            return []

        # Validate file types
        valid_types = {"output", "input", "smash"}
        invalid_types = [t for t in cleanup_setting if t not in valid_types]
        if invalid_types:
            import logging

            logging.warning(
                f"Invalid file types in 'auto_cleanup_previous_results': {invalid_types}. "
                f"Valid types are: {valid_types}"
            )

        return [t for t in cleanup_setting if t in valid_types]
