from typing import TYPE_CHECKING

from .base_setup import BaseSetup

if TYPE_CHECKING:
    from logging import Logger

    import s4l_v1.simulation.emfdtd as emfdtd

    from ..antenna import Antenna
    from ..config import Config


class SourceSetup(BaseSetup):
    """Configures excitation sources and sensors for the simulation."""

    def __init__(
        self,
        config: "Config",
        simulation: "emfdtd.Simulation",
        frequency_mhz: int,
        antenna: "Antenna",
        verbose_logger: "Logger",
        progress_logger: "Logger",
        free_space: bool = False,
    ):
        super().__init__(config, verbose_logger, progress_logger)
        self.simulation = simulation
        self.frequency_mhz = frequency_mhz
        self.antenna = antenna
        self.free_space = free_space

        import s4l_v1.units

        self.units = s4l_v1.units

    def setup_source_and_sensors(self, antenna_components: dict):
        """Sets up the edge source and sensors based on excitation type.

        Uses excitation_type from config to determine Harmonic or Gaussian excitation.
        For free-space simulations, also adds far-field sensors for Gaussian sources.

        Args:
            antenna_components: Dict mapping component names to entities.
        """
        self._log("Setting up source and sensors...", log_type="progress")

        source_name = self.antenna.get_source_entity_name()
        if source_name not in antenna_components:
            raise RuntimeError(f"Could not find source entity '{source_name}' in antenna group.")
        source_entity = antenna_components[source_name]

        # Source setup
        edge_source_settings = self.emfdtd.EdgeSourceSettings()

        # Get the enum for ExcitationType
        excitation_enum = edge_source_settings.ExcitationType.enum

        # Read excitation type from config (default to Harmonic for backward compatibility)
        excitation_type = self.config["simulation_parameters.excitation_type"] or "Harmonic"
        excitation_type_lower = excitation_type.lower() if isinstance(excitation_type, str) else "harmonic"

        if excitation_type_lower == "gaussian":
            bandwidth_mhz_val = self.config["simulation_parameters.bandwidth_mhz"]
            bandwidth_mhz: float = float(bandwidth_mhz_val) if isinstance(bandwidth_mhz_val, (int, float)) else 50.0
            self._log(f"  - Using Gaussian source (BW: {bandwidth_mhz} MHz).", log_type="info")
            edge_source_settings.ExcitationType = excitation_enum.Gaussian
            edge_source_settings.CenterFrequency = self.frequency_mhz, self.units.MHz
            edge_source_settings.Bandwidth = bandwidth_mhz, self.units.MHz
        else:
            self._log("  - Using Harmonic source.", log_type="info")
            edge_source_settings.ExcitationType = excitation_enum.Harmonic
            edge_source_settings.Frequency = self.frequency_mhz, self.units.MHz
            edge_source_settings.CenterFrequency = self.frequency_mhz, self.units.MHz

        self.simulation.Add(edge_source_settings, [source_entity])

        # Sensor setup
        edge_sensor_settings = self.emfdtd.EdgeSensorSettings()
        self.simulation.Add(edge_sensor_settings, [source_entity])

        # Far-field sensors only for free-space simulations (for radiation patterns)
        if self.free_space:
            far_field_sensor_settings = self.simulation.AddFarFieldSensorSettings()

            # Configure extracted frequencies for Gaussian source
            if excitation_type_lower == "gaussian":
                center_freq_hz = self.frequency_mhz * 1e6
                bandwidth_mhz_val = self.config["simulation_parameters.bandwidth_mhz"]
                if isinstance(bandwidth_mhz_val, (int, float)):
                    bandwidth_mhz: float = float(bandwidth_mhz_val)
                else:
                    bandwidth_mhz = 50.0
                bandwidth_hz = bandwidth_mhz * 1e6
                start_freq_hz = center_freq_hz - (bandwidth_hz / 2)
                end_freq_hz = center_freq_hz + (bandwidth_hz / 2)

                # Create a list of 21 frequencies, including the center frequency
                num_samples = 21
                extracted_frequencies_hz = [start_freq_hz + i * (bandwidth_hz / (num_samples - 1)) for i in range(num_samples)]

                far_field_sensor_settings.ExtractedFrequencies = (
                    extracted_frequencies_hz,
                    self.units.Hz,
                )
                self._log(
                    f"  - Set extracted frequencies from {start_freq_hz / 1e6} MHz to {end_freq_hz / 1e6} MHz.",
                    log_type="info",
                )

        # Point sensors are now handled by the NearFieldSetup class.
