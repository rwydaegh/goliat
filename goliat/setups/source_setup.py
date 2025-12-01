from typing import TYPE_CHECKING, Optional

import numpy as np

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
        phantom_name: Optional[str] = None,
        placement_name: Optional[str] = None,
    ):
        super().__init__(config, verbose_logger, progress_logger)
        self.simulation = simulation
        self.frequency_mhz = frequency_mhz
        self.antenna = antenna
        self.free_space = free_space
        self.phantom_name = phantom_name
        self.placement_name = placement_name

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
            bandwidth_mhz_val = self.config["simulation_parameters.bandwidth_mhz"] or 50.0
            bandwidth_mhz = float(bandwidth_mhz_val) if not isinstance(bandwidth_mhz_val, dict) else 50.0
            k_val = self.config["simulation_parameters.gaussian_pulse_k"] or 3
            k = int(k_val) if not isinstance(k_val, dict) else 3

            if k == 5:
                # Use Sim4Life built-in Gaussian (forced k=5)
                self._log(f"  - Using Sim4Life built-in Gaussian source (BW: {bandwidth_mhz} MHz, k=5).", log_type="info")
                edge_source_settings.ExcitationType = excitation_enum.Gaussian
                edge_source_settings.CenterFrequency = self.frequency_mhz, self.units.MHz
                edge_source_settings.Bandwidth = bandwidth_mhz, self.units.MHz
            else:
                # Use custom Gaussian waveform with user-defined k (faster pulse)
                self._log(f"  - Using custom Gaussian source (BW: {bandwidth_mhz} MHz, k={k}).", log_type="info")
                edge_source_settings.ExcitationType = excitation_enum.UserDefined

                # Set up user-defined signal from equation
                user_signal_enum = edge_source_settings.UserSignalType.enum
                edge_source_settings.UserSignalType = user_signal_enum.FromEquation

                # Calculate parameters for Gaussian pulse
                # σ = 0.94/(π·BW), t₀ = k·σ (to start near zero)
                bandwidth_hz = bandwidth_mhz * 1e6
                center_freq_hz = self.frequency_mhz * 1e6
                sigma = 0.94 / (np.pi * bandwidth_hz)
                t0 = float(k) * sigma

                # Create Gaussian-modulated pulse expression: A * exp(-(_t-t₀)²/(2σ²)) * cos(2π·f₀·_t)
                # Using Sim4Life expression syntax with '_t' as time variable
                # Note: Using ** for exponentiation (Python-style) instead of ^
                amplitude = 1.0
                expression = f"{amplitude} * exp(-(_t - {t0})**2 / (2 * {sigma}**2)) * cos(2 * pi * {center_freq_hz} * _t)"
                edge_source_settings.UserExpression = expression

                # Set center frequency for reference (used by post-processing)
                edge_source_settings.CenterFrequency = self.frequency_mhz, self.units.MHz
        else:
            self._log("  - Using Harmonic source.", log_type="info")
            # Frequency already has detuning applied in NearFieldSetup if enabled
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
                bandwidth_mhz_val = self.config["simulation_parameters.bandwidth_mhz"] or 50.0
                bandwidth_mhz_ff = float(bandwidth_mhz_val) if not isinstance(bandwidth_mhz_val, dict) else 50.0
                bandwidth_hz = bandwidth_mhz_ff * 1e6
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
