import os


class Antenna:
    """
    Manages antenna-specific properties and configurations within the simulation framework.
    """

    def __init__(self, config, frequency_mhz):
        """
        Initializes the Antenna object.

        Args:
            config (Config): The configuration object containing antenna settings.
            frequency_mhz (int): The operating frequency in MHz.
        """
        self.config = config
        self.frequency_mhz = frequency_mhz
        self.antenna_config = self.config.get_antenna_config()

    def get_config_for_frequency(self):
        """
        Retrieves the specific antenna configuration dictionary for the current frequency.

        Raises:
            ValueError: If no antenna configuration is defined for the specified frequency.

        Returns:
            dict: A dictionary containing configuration details for the antenna at the given frequency.
        """
        freq_str = str(self.frequency_mhz)
        if freq_str not in self.antenna_config:
            raise ValueError(
                f"Antenna configuration not defined for frequency: {self.frequency_mhz} MHz"
            )
        return self.antenna_config[freq_str]

    def get_model_type(self):
        """
        Retrieves the model type of the antenna (e.g., 'PIFA', 'IFA') for the current frequency.

        Returns:
            str: The antenna model type.
        """
        return self.get_config_for_frequency().get("model_type")

    def get_source_entity_name(self):
        """
        Retrieves the name of the source entity within the antenna CAD model for the current frequency.

        Returns:
            str: The name of the source entity.
        """
        return self.get_config_for_frequency().get("source_name")

    def get_centered_antenna_path(self, centered_antennas_dir):
        """
        Constructs the full file path to the centered .sab file for the current frequency.

        Args:
            centered_antennas_dir (str): The base directory where centered antenna files are stored.

        Returns:
            str: The absolute path to the centered antenna model file.
        """
        antenna_filename = f"{self.frequency_mhz}MHz_centered.sab"
        return os.path.join(centered_antennas_dir, antenna_filename)
