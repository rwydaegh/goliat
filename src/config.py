import json
import os

class Config:
    """
    Handles loading and validation of configuration files.
    """
    def __init__(self, base_dir):
        self.base_dir = base_dir
        self.simulation_config_path = os.path.join(self.base_dir, 'simulation_config.json')
        self.phantoms_config_path = os.path.join(self.base_dir, 'phantoms_config.json')
        self.material_mapping_path = os.path.join(self.base_dir, 'material_name_mapping.json')
        
        self.simulation_config = self._load_json(self.simulation_config_path)
        self.phantoms_config = self._load_json(self.phantoms_config_path)
        self.material_mapping = self._load_json(self.material_mapping_path)

    def _load_json(self, path):
        """Loads a JSON file."""
        if not os.path.exists(path):
            raise FileNotFoundError(f"Configuration file not found at: {path}")
        with open(path, 'r') as f:
            return json.load(f)

    def get_simulation_parameters(self):
        """Returns the simulation parameters."""
        return self.simulation_config.get("simulation_parameters", {})

    def get_frequencies(self):
        """Returns the list of frequencies."""
        return self.simulation_config.get("frequencies_mhz", [])

    def get_antenna_config(self):
        """Returns the antenna configuration."""
        return self.simulation_config.get("antenna_config", {})

    def get_gridding_parameters(self):
        """Returns the gridding parameters."""
        return self.simulation_config.get("gridding_parameters", {})

    def get_phantom_config(self, phantom_name):
        """Returns the configuration for a specific phantom."""
        return self.phantoms_config.get(phantom_name)

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
        return self.simulation_config.get("solver_settings", {})

    def get_antenna_component_names(self, antenna_model_name):
        """Returns the component names for a specific antenna model."""
        return self.simulation_config.get("antenna_config", {}).get("components", {}).get(antenna_model_name)

    def get_verbose(self):
        """Returns the verbose flag."""
        return self.simulation_config.get("verbose", True)