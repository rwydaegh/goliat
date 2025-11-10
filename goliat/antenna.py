import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import Config


class Antenna:
    """Manages antenna-specific properties and configurations."""

    def __init__(self, config: "Config", frequency_mhz: int):
        """Initializes the Antenna object.

        Args:
            config: The configuration object containing antenna settings.
            frequency_mhz: The operating frequency in MHz.
        """
        self.config = config
        self.frequency_mhz = frequency_mhz
        self.antenna_config = self.config["antenna_config"] or {}

    def get_config_for_frequency(self) -> dict:
        """Gets the antenna configuration for the current frequency.

        Raises:
            ValueError: If no configuration is defined for the frequency.

        Returns:
            The antenna configuration dictionary.
        """
        freq_str = str(self.frequency_mhz)
        if freq_str not in self.antenna_config:
            raise ValueError(f"Antenna configuration not defined for frequency: {self.frequency_mhz} MHz")
        return self.antenna_config[freq_str]

    def get_model_type(self) -> str:
        """Returns the antenna model type string."""
        return str(self.get_config_for_frequency().get("model_type"))

    def get_source_entity_name(self) -> str:
        """Returns the source entity name from the antenna config."""
        return str(self.get_config_for_frequency().get("source_name"))

    def get_centered_antenna_path(self, centered_antennas_dir: str) -> str:
        """Constructs the path to the centered .sab antenna file.

        Args:
            centered_antennas_dir: The directory for centered antenna files.

        Returns:
            The absolute path to the centered antenna model file.
        """
        antenna_filename = f"{self.frequency_mhz}MHz_centered.sab"
        return os.path.join(centered_antennas_dir, antenna_filename)
