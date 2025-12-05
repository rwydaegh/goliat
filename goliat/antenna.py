import logging
import os
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import Config

logger = logging.getLogger(__name__)


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

        If the exact frequency file doesn't exist, finds the nearest available frequency
        and shows a warning.

        Args:
            centered_antennas_dir: The directory for centered antenna files.

        Returns:
            The absolute path to the centered antenna model file.

        Raises:
            FileNotFoundError: If no antenna files are found in the directory.
        """
        antenna_filename = f"{self.frequency_mhz}MHz_centered.sab"
        antenna_path = os.path.join(centered_antennas_dir, antenna_filename)

        # Check if exact file exists
        if os.path.exists(antenna_path) and os.path.isfile(antenna_path):
            return antenna_path

        # File doesn't exist, try to find nearest frequency
        logger.warning(f"Antenna file for {self.frequency_mhz} MHz not found: {antenna_path}. Searching for nearest available frequency...")

        # Scan directory for available antenna files
        if not os.path.exists(centered_antennas_dir):
            raise FileNotFoundError(f"Antenna directory does not exist: {centered_antennas_dir}")

        available_files = []
        pattern = re.compile(r"(\d+)MHz_centered\.sab$")

        try:
            for filename in os.listdir(centered_antennas_dir):
                match = pattern.match(filename)
                if match:
                    freq = int(match.group(1))
                    filepath = os.path.join(centered_antennas_dir, filename)
                    if os.path.isfile(filepath):
                        available_files.append((freq, filepath))
        except (OSError, PermissionError) as e:
            raise FileNotFoundError(f"Could not read antenna directory {centered_antennas_dir}: {e}") from e

        if not available_files:
            raise FileNotFoundError(f"No antenna files found in directory: {centered_antennas_dir}")

        # Find nearest frequency
        available_files.sort(key=lambda x: x[0])  # Sort by frequency
        nearest_freq, nearest_path = min(available_files, key=lambda x: abs(x[0] - self.frequency_mhz))

        logger.warning(f"Using antenna file for {nearest_freq} MHz instead of {self.frequency_mhz} MHz. File: {nearest_path}")

        return nearest_path
