import traceback
from typing import TYPE_CHECKING

import numpy as np

from ..logging_manager import LoggingMixin

if TYPE_CHECKING:
    import s4l_v1.analysis as analysis

    from ..results_extractor import ResultsExtractor


class ResonanceExtractor(LoggingMixin):
    """Extracts antenna resonance frequency and detuning from Gaussian pulse results.

    Analyzes frequency-dependent accepted power to identify resonance peak and
    calculates detuning relative to nominal frequency.
    """

    def __init__(self, parent: "ResultsExtractor", results_data: dict):
        """Sets up the resonance extractor.

        Args:
            parent: Parent ResultsExtractor instance.
            results_data: Dict to store extracted resonance data.
        """
        self.parent = parent
        self.config = parent.config
        self.frequency_mhz = parent.frequency_mhz
        self.verbose_logger = parent.verbose_logger
        self.progress_logger = parent.progress_logger
        self.results_data = results_data
        self.gui = parent.gui

        import s4l_v1.document

        self.document = s4l_v1.document

    def extract_resonance_frequency(self, simulation_extractor: "analysis.Extractor"):  # type: ignore
        """Extract antenna resonant frequency from Gaussian pulse results.

        Analyzes frequency-dependent accepted power to identify resonance peak.
        Calculates detuning relative to nominal frequency.

        Args:
            simulation_extractor: Results extractor from the simulation.

        Returns:
            dict: Contains resonant_freq_mhz, detuning_mhz, max_power_w, freq_resolution_mhz
        """
        try:
            # Extract full frequency spectrum
            input_power_extractor = simulation_extractor["Input Power"]
            self.document.AllAlgorithms.Add(input_power_extractor)
            input_power_extractor.Update()

            input_power_output = input_power_extractor.Outputs["EM Input Power(f)"]
            input_power_output.Update()

            # Get continuous frequency data (automatically from FFT)
            freq_axis_hz = input_power_output.Data.Axis  # Full freq array
            power_data_w = input_power_output.Data.GetComponent(0)  # Power at each freq

            # Convert to MHz
            freq_axis_mhz = freq_axis_hz / 1e6

            # Find resonant frequency (maximum accepted power)
            max_idx = np.argmax(power_data_w)
            resonant_freq_mhz = freq_axis_mhz[max_idx]
            max_power_w = power_data_w[max_idx]

            # Calculate detuning
            freq_mhz = self.frequency_mhz
            nominal_freq_mhz = float(freq_mhz if isinstance(freq_mhz, (int, float)) else np.mean(freq_mhz))
            detuning_mhz = float(resonant_freq_mhz - nominal_freq_mhz)

            # Calculate frequency resolution
            if len(freq_axis_hz) > 1:
                freq_resolution_mhz = (freq_axis_hz[1] - freq_axis_hz[0]) / 1e6
            else:
                freq_resolution_mhz = 0.0

            # Log results
            self._log(f"\n{'=' * 80}", log_type="highlight")
            self._log("  ANTENNA RESONANCE ANALYSIS", log_type="highlight")
            self._log(f"{'=' * 80}", log_type="highlight")
            self._log(f"  Nominal frequency: {nominal_freq_mhz} MHz", log_type="info")
            self._log(f"  Detected resonance: {resonant_freq_mhz:.2f} MHz", log_type="highlight")
            self._log(
                f"  Detuning: {detuning_mhz:+.2f} MHz ({detuning_mhz / nominal_freq_mhz * 100:+.1f}%)",
                log_type="highlight" if abs(detuning_mhz) > 10 else "info",
            )
            self._log(f"  Max power at resonance: {max_power_w * 1000:.2f} mW", log_type="info")
            self._log(f"  Frequency resolution: {freq_resolution_mhz:.2f} MHz", log_type="info")
            self._log(f"  Number of frequency points: {len(freq_axis_hz)}", log_type="info")
            self._log(f"{'=' * 80}\n", log_type="highlight")

            # Warning for severe detuning
            if abs(detuning_mhz) > 50:
                self._log("\n" + "!" * 80, log_type="warning")
                self._log("  WARNING: SIGNIFICANT ANTENNA DETUNING DETECTED!", log_type="warning")
                self._log(
                    f"  The antenna has shifted {detuning_mhz:+.1f} MHz from nominal frequency.",
                    log_type="warning",
                )
                self._log("  Consider:", log_type="warning")
                self._log(
                    f"    1. Re-running simulation at detected resonance ({resonant_freq_mhz:.0f} MHz)",
                    log_type="warning",
                )
                self._log("    2. Verifying antenna design for this placement scenario", log_type="warning")
                self._log(
                    "    3. Checking if SAR pattern is affected by off-resonance operation",
                    log_type="warning",
                )
                self._log("!" * 80 + "\n", log_type="warning")

            # Store results
            resonance_data = {
                "resonant_freq_mhz": float(resonant_freq_mhz),
                "nominal_freq_mhz": float(nominal_freq_mhz),
                "detuning_mhz": float(detuning_mhz),
                "detuning_percent": float(detuning_mhz / nominal_freq_mhz * 100),
                "max_power_w": float(max_power_w),
                "freq_resolution_mhz": float(freq_resolution_mhz),
                "num_freq_points": int(len(freq_axis_hz)),
                "frequency_axis_mhz": freq_axis_mhz.tolist(),  # For plotting
                "power_data_w": power_data_w.tolist(),  # For plotting
            }

            # Clean up
            self.document.AllAlgorithms.Remove(input_power_extractor)

            return resonance_data

        except Exception as e:
            self._log(
                f"  - ERROR: An exception occurred during resonance extraction: {e}",
                log_type="error",
            )
            self.verbose_logger.error(traceback.format_exc())
            return None
