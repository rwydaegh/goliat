import json
import os

def deep_merge(source, destination):
    """
    Recursively merges two dictionaries.
    """
    for key, value in source.items():
        if isinstance(value, dict):
            # Get or create the nested dictionary in destination
            node = destination.setdefault(key, {})
            deep_merge(value, node)
        else:
            destination[key] = value
    return destination

class Config:
    """
    Handles loading and validation of configuration files with inheritance.
    """
    def __init__(self, base_dir, config_filename="near_field_config.json"):
        self.base_dir = base_dir
        self.config_path = self._resolve_config_path(config_filename)
        self.material_mapping_path = os.path.join(self.base_dir, 'material_name_mapping.json')
        self.profiling_config_path = os.path.join(self.base_dir, 'configs', 'profiling_config.json')
        
        self.config = self._load_config_with_inheritance(self.config_path)
        self.material_mapping = self._load_json(self.material_mapping_path)
        self.profiling_config = self._load_json(self.profiling_config_path)

    def _resolve_config_path(self, config_filename):
        """
        Resolves the absolute path to the configuration file.
        """
        if os.path.isabs(config_filename):
            return config_filename
        
        # If a relative path with directory components is given
        if os.path.dirname(config_filename):
            return os.path.join(self.base_dir, config_filename)
        
        # If only a filename is given, assume it's in the 'configs' directory
        return os.path.join(self.base_dir, 'configs', config_filename)

    def get_setting(self, path, default=None):
        """
        Retrieves a setting from the configuration using a path-like string.
        Example path: "simulation_parameters.number_of_point_sources"
        """
        keys = path.split('.')
        current_config = self.config
        for key in keys:
            if isinstance(current_config, dict) and key in current_config:
                current_config = current_config[key]
            else:
                return default
        return current_config

    def _load_config_with_inheritance(self, path):
        """
        Loads a JSON configuration file and handles 'extends' for inheritance.
        """
        config = self._load_json(path)
        
        if "extends" in config:
            base_config_path = self._resolve_config_path(config["extends"])
            base_config = self._load_config_with_inheritance(base_config_path)
            
            # Merge the base configuration into the current one
            config = deep_merge(base_config, config)
            
        return config

    def _load_json(self, path):
        """Loads a JSON file."""
        if not os.path.exists(path):
            raise FileNotFoundError(f"Configuration file not found at: {path}")
        with open(path, 'r') as f:
            return json.load(f)

    def get_simulation_parameters(self):
        """Returns the simulation parameters."""
        return self.config.get("simulation_parameters", {})

    def get_antenna_config(self):
        """Returns the antenna configuration."""
        return self.config.get("antenna_config", {})

    def get_gridding_parameters(self):
        """Returns the gridding parameters."""
        return self.config.get("gridding_parameters", {})

    def get_phantom_config(self, phantom_name):
        """Returns the configuration for a specific phantom."""
        return self.config.get("phantoms", {}).get(phantom_name)

    def get_phantom_placements(self, phantom_name):
        """Returns the placement configuration for a specific phantom."""
        phantom_config = self.get_phantom_config(phantom_name)
        if phantom_config:
            return phantom_config.get("placements", {})
        return {}

    def get_material_mapping(self):
        """Returns the material name mapping."""
        return self.material_mapping

    def get_solver_settings(self):
        """Returns the solver settings."""
        return self.config.get("solver_settings", {})

    def get_antenna_component_names(self, antenna_model_type):
        """Returns the component names for a specific antenna model."""
        return self.config.get("antenna_config", {}).get("components", {}).get(antenna_model_type)

    def get_verbose(self):
        """Returns the verbose flag."""
        return self.config.get("verbose", True)

    def get_manual_isolve(self):
        """Returns the manual_isolve flag."""
        return self.config.get("manual_isolve", False)

    def get_freespace_expansion(self):
        """Returns the freespace antenna bounding box expansion in mm."""
        return self.get_simulation_parameters().get("freespace_antenna_bbox_expansion_mm", [10, 10, 10])

    def get_excitation_type(self):
        """Returns the excitation type."""
        return self.get_simulation_parameters().get("excitation_type", "Harmonic")

    def get_bandwidth(self):
        """Returns the bandwidth in MHz."""
        return self.get_simulation_parameters().get("bandwidth_mhz", 50.0)

    def get_placement_scenario(self, scenario_name):
        """Returns the definition for a specific placement scenario."""
        return self.config.get("placement_scenarios", {}).get(scenario_name)

    def get_profiling_weights(self):
        """Returns the profiling weights."""
        return self.profiling_config.get("phase_weights", {})

    def get_profiling_subtask_estimates(self):
        """Returns the subtask time estimates."""
        return self.profiling_config.get("subtask_estimates", {})