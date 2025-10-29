import traceback
from typing import TYPE_CHECKING

import numpy as np

from ..logging_manager import LoggingMixin

if TYPE_CHECKING:
    import s4l_v1.analysis as analysis

    from ..results_extractor import ResultsExtractor


class PowerExtractor(LoggingMixin):
    """Handles the extraction of input power and power balance."""

    def __init__(self, parent: "ResultsExtractor", results_data: dict):
        """Initializes the PowerExtractor.

        Args:
            parent: The parent ResultsExtractor instance.
            results_data: The dictionary to store the extracted data.
        """
        self.parent = parent
        self.config = parent.config
        self.simulation = parent.simulation
        self.study_type = parent.study_type
        self.placement_name = parent.placement_name
        self.frequency_mhz = parent.frequency_mhz
        self.verbose_logger = parent.verbose_logger
        self.progress_logger = parent.progress_logger
        self.results_data = results_data

        import s4l_v1.document

        self.document = s4l_v1.document

    def extract_input_power(self, simulation_extractor: "analysis.Extractor"):  # type: ignore
        """Extracts the input power from the simulation results.

        For far-field, it calculates a theoretical input power. For near-field,
        it extracts power from the port sensor.

        Args:
            simulation_extractor: The results extractor from the simulation object.
        """
        self._log("    - Extract input power...", level="progress", log_type="progress")
        with self.parent.study.subtask("extract_input_power"):  # type: ignore
            try:
                if self.study_type == "far_field":
                    self._extract_far_field_power()
                    return

                self._extract_near_field_power(simulation_extractor)
            except Exception as e:
                self._log(
                    f"  - ERROR: An exception occurred during input power extraction: {e}",
                    level="progress",
                    log_type="error",
                )
                self.verbose_logger.error(traceback.format_exc())

    def _extract_far_field_power(self):
        """Calculates theoretical input power for far-field simulations."""
        self._log(
            "  - Far-field study: using theoretical model for input power.",
            log_type="info",
        )
        import s4l_v1.model

        try:
            bbox_entity = next(
                (e for e in s4l_v1.model.AllEntities() if hasattr(e, "Name") and e.Name == "far_field_simulation_bbox"),
                None,
            )
            if not bbox_entity:
                raise RuntimeError("Could not find 'far_field_simulation_bbox' entity in the project.")
            sim_bbox = s4l_v1.model.GetBoundingBox([bbox_entity])
        except RuntimeError as e:
            self._log(
                f"  - WARNING: Could not calculate theoretical input power. {e}",
                log_type="warning",
            )
            return
        # sim_bbox is a list of two points: [min_corner, max_corner]
        sim_min, sim_max = np.array(sim_bbox[0]), np.array(sim_bbox[1])
        padding_bottom = np.array(
            self.config.get_setting(
                "gridding_parameters.padding.manual_bottom_padding_mm",
            )
        )
        padding_top = np.array(
            self.config.get_setting(
                "gridding_parameters.padding.manual_top_padding_mm",
            )
        )
        total_min = sim_min - padding_bottom
        total_max = sim_max + padding_top

        e_field_v_m, z0 = 1.0, 377.0
        power_density_w_m2 = (e_field_v_m**2) / (2 * z0)

        # e.g., 'environmental_x_pos_theta' -> 'x'
        direction = self.parent.orientation_name
        dims = total_max - total_min  # This is a 3-element array [dx, dy, dz]

        if "x" in direction:
            # Area of the YZ plane
            area_m2 = (dims[1] * dims[2]) / 1e6
        elif "y" in direction:
            # Area of the XZ plane
            area_m2 = (dims[0] * dims[2]) / 1e6
        else:  # Default to z-direction
            # Area of the XY plane
            area_m2 = (dims[0] * dims[1]) / 1e6

        total_input_power = power_density_w_m2 * area_m2
        self.results_data.update(
            {
                "input_power_W": float(total_input_power),
                "input_power_frequency_MHz": float(self.frequency_mhz),
            }
        )
        self._log(
            f"  - Calculated theoretical input power: {float(total_input_power):.4e} W",
            log_type="highlight",
        )

    def _extract_near_field_power(self, simulation_extractor: "analysis.Extractor"):  # type: ignore
        """Extracts input power for near-field simulations from port sensors."""
        input_power_extractor = simulation_extractor["Input Power"]
        self.document.AllAlgorithms.Add(input_power_extractor)
        input_power_extractor.Update()

        if hasattr(input_power_extractor, "GetPower"):
            power_w, _ = input_power_extractor.GetPower(0)
            self.results_data.update(
                {
                    "input_power_W": float(power_w),
                    "input_power_frequency_MHz": float(self.frequency_mhz),
                }
            )
        else:
            self._log(
                "  - GetPower() not available, falling back to manual extraction.",
                log_type="warning",
            )
            input_power_output = input_power_extractor.Outputs["EM Input Power(f)"]
            input_power_output.Update()

            if hasattr(input_power_output, "GetHarmonicData"):
                power_complex = input_power_output.GetHarmonicData(0)
                self.results_data.update(
                    {
                        "input_power_W": float(abs(power_complex)),
                        "input_power_frequency_MHz": float(self.frequency_mhz),
                    }
                )
            else:
                power_data = input_power_output.Data.GetComponent(0)
                if power_data is not None and power_data.size > 0:
                    if power_data.size == 1:
                        input_power_w, freq_mhz = (
                            power_data.item(),
                            self.frequency_mhz,
                        )
                    else:
                        center_freq_hz = self.frequency_mhz * 1e6
                        axis = input_power_output.Data.Axis
                        target_index = np.argmin(np.abs(axis - center_freq_hz))
                        input_power_w, freq_mhz = (
                            power_data[target_index],
                            axis[target_index] / 1e6,
                        )
                    self.results_data.update(
                        {
                            "input_power_W": float(input_power_w),
                            "input_power_frequency_MHz": float(freq_mhz),
                        }
                    )
                else:
                    self._log(
                        "  - WARNING: Could not extract input power values.",
                        log_type="warning",
                    )

    def extract_power_balance(self, simulation_extractor: "analysis.Extractor"):  # type: ignore
        """Extracts the power balance to verify energy conservation.

        Args:
            simulation_extractor: The results extractor from the simulation object.
        """
        self._log("    - Extract power balance...", level="progress", log_type="progress")
        try:
            em_sensor_extractor = simulation_extractor["Overall Field"]
            power_balance_extractor = em_sensor_extractor.Outputs["Power Balance"]
            power_balance_extractor.Update()

            power_balance_data = {
                key: power_balance_extractor.Data.DataSimpleDataCollection.FieldValue(key, 0)
                for key in power_balance_extractor.Data.DataSimpleDataCollection.Keys()
                if key != "Balance"
            }

            if self.parent.study_type == "far_field" and "input_power_W" in self.results_data:
                power_balance_data["Pin"] = self.results_data["input_power_W"]
                self._log(
                    f"    - Overwriting Pin with theoretical value: {float(power_balance_data['Pin']):.4e} W",
                    log_type="info",
                )

            pin = power_balance_data.get("Pin", 0.0)
            p_out = power_balance_data.get("DielLoss", 0.0) + power_balance_data.get("RadPower", 0.0)
            balance = 100 * (p_out / pin) if pin > 1e-9 else float("nan")

            power_balance_data["Balance"] = balance
            self._log(f"    - Final Balance: {balance:.2f}%", log_type="highlight")
            self.results_data["power_balance"] = power_balance_data

        except Exception as e:
            self._log(f"  - WARNING: Could not extract power balance: {e}", log_type="warning")
            self.verbose_logger.error(traceback.format_exc())
