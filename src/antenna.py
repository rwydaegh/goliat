import os

class Antenna:
    """
    Helper class for antenna properties.
    """
    def __init__(self, config, frequency_mhz):
        self.config = config
        self.frequency_mhz = frequency_mhz
        self.antenna_config = self.config.get_antenna_config()

    def get_model_name(self):
        """
        Determines the antenna model type (PIFA or IFA) based on the frequency.
        """
        for model_type, freqs in self.antenna_config.get("models", {}).items():
            if self.frequency_mhz in freqs:
                return model_type
        raise ValueError(f"Antenna model not defined for frequency: {self.frequency_mhz} MHz")

    def get_source_entity_name(self):
        """
        Determines the source entity name based on the frequency.
        """
        for source_name, freqs in self.antenna_config.get("sources", {}).items():
            if self.frequency_mhz in freqs:
                return source_name
        raise ValueError(f"Antenna source not defined for frequency: {self.frequency_mhz} MHz")

    def get_centered_antenna_path(self, centered_antennas_dir):
        """
        Returns the full path to the centered .sab file for the current frequency.
        """
        # The filename is assumed to be like 'IFA_1450MHz_centered.sab'
        # We derive this from the model type and frequency.
        model_name = self.get_model_name()
        antenna_filename = f"{model_name}_{self.frequency_mhz}MHz_centered.sab"
        return os.path.join(centered_antennas_dir, antenna_filename)