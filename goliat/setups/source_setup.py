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

        For phantom simulations, uses harmonic excitation. For free-space,
        uses Gaussian with bandwidth. Also adds edge sensors and optionally
        far-field sensors for free-space simulations.

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

        if self.free_space:
            self._log("  - Using Gaussian source for free-space simulation.", log_type="info")
            excitation_type = "gaussian"
            edge_source_settings.ExcitationType = excitation_enum.Gaussian
            edge_source_settings.CenterFrequency = self.frequency_mhz, self.units.MHz
            edge_source_settings.Bandwidth = 50.0, self.units.MHz
        else:
            self._log("  - Using Harmonic source for phantom simulation.", log_type="info")
            excitation_type = "harmonic"
            edge_source_settings.ExcitationType = excitation_enum.Harmonic
            edge_source_settings.Frequency = self.frequency_mhz, self.units.MHz
            edge_source_settings.CenterFrequency = self.frequency_mhz, self.units.MHz

        self.simulation.Add(edge_source_settings, [source_entity])

        # Sensor setup
        edge_sensor_settings = self.emfdtd.EdgeSensorSettings()
        self.simulation.Add(edge_sensor_settings, [source_entity])

        if self.free_space:
            far_field_sensor_settings = self.simulation.AddFarFieldSensorSettings()

            # Configure extracted frequencies for Gaussian source
            if excitation_type.lower() == "gaussian":
                center_freq_hz = self.frequency_mhz * 1e6
                bandwidth_hz = 50.0 * 1e6
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
