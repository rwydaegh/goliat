import os

class Antenna:
    """
    Helper class for antenna properties.
    """
    def __init__(self, config, frequency_mhz):
        self.config = config
        self.frequency_mhz = frequency_mhz
        self.antenna_config = self.config.get_antenna_config()

    def get_config_for_frequency(self):
        """
        Returns the specific antenna configuration for the given frequency.
        """
        freq_str = str(self.frequency_mhz)
        if freq_str not in self.antenna_config:
            raise ValueError(f"Antenna configuration not defined for frequency: {self.frequency_mhz} MHz")
        return self.antenna_config[freq_str]

    def get_model_type(self):
        """
        Returns the antenna model type (e.g., 'PIFA', 'IFA') for the current frequency.
        """
        return self.get_config_for_frequency().get("model_type")

    def get_source_entity_name(self):
        """
        Returns the source entity name for the current frequency.
        """
        return self.get_config_for_frequency().get("source_name")

    def get_centered_antenna_path(self, centered_antennas_dir):
        """
        Returns the full path to the centered .sab file for the current frequency.
        """
        antenna_filename = f"{self.frequency_mhz}MHz_centered.sab"
        return os.path.join(centered_antennas_dir, antenna_filename)