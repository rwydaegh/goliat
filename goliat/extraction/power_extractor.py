import traceback
from typing import TYPE_CHECKING

import numpy as np

from ..logging_manager import LoggingMixin

if TYPE_CHECKING:
    import s4l_v1.analysis as analysis

    from ..results_extractor import ResultsExtractor


class PowerExtractor(LoggingMixin):
    """Extracts input power and power balance from simulation results.

    For near-field, reads power from port sensors. For far-field, calculates
    theoretical power from plane wave parameters. Also extracts power balance
    to verify energy conservation.
    """

    def __init__(self, parent: "ResultsExtractor", results_data: dict):
        """Sets up the power extractor.

        Args:
            parent: Parent ResultsExtractor instance.
            results_data: Dict to store extracted power data.
        """
        self.parent = parent
        self.config = parent.config
        self.simulation = parent.simulation
        self.study_type = parent.study_type
        self.placement_name = parent.placement_name
        self.frequency_mhz = parent.frequency_mhz
        self.verbose_logger = parent.verbose_logger
        self.progress_logger = parent.progress_logger
        self.gui = parent.gui
        self.results_data = results_data

        import s4l_v1.document

        self.document = s4l_v1.document

    def extract_input_power(self, simulation_extractor: "analysis.Extractor"):  # type: ignore
        """Extracts input power, delegating to study-type specific methods.

        Args:
            simulation_extractor: Results extractor from the simulation.
        """
        self._log("    - Extract input power...", level="progress", log_type="progress")

        try:
            elapsed = 0.0
            if self.parent.study:
                with self.parent.study.profiler.subtask("extract_input_power"):  # type: ignore
                    if self.study_type == "far_field":
                        self._extract_far_field_power(simulation_extractor)
                    else:
                        self._extract_near_field_power(simulation_extractor)

                elapsed = self.parent.study.profiler.subtask_times["extract_input_power"][-1]

            self._log(f"      - Subtask 'extract_input_power' done in {elapsed:.2f}s", log_type="verbose")
            self._log(f"      - Done in {elapsed:.2f}s", level="progress", log_type="success")
        except Exception as e:
            self._log(
                f"  - ERROR: An exception occurred during input power extraction: {e}",
                level="progress",
                log_type="error",
            )
            self.verbose_logger.error(traceback.format_exc())

    def _extract_far_field_power(self, simulation_extractor: "analysis.Extractor"):  # type: ignore
        """Calculates input power for a plane wave using phantom cross-section.

        Far-field simulations use plane waves with a fixed E-field amplitude (1 V/m).
        This method calculates the power intercepted by the phantom based on the
        power density and the phantom's projected cross-sectional area for the
        given direction of incidence.

        The calculation:
        1. Loads pre-computed phantom cross-section data from data/phantom_skins/
        2. Converts incident direction to (theta, phi) angles
        3. Looks up the cross-sectional area for that direction
        4. Calculates power: P = S × A_phantom where S = E²/(2×Z₀)

        This gives a physically meaningful "input power" for power balance
        calculations, representing the actual power intercepted by the body.

        See docs/technical/power_normalization_philosophy.md for full discussion.

        Args:
            simulation_extractor: Results extractor from the simulation.
        """
        import os
        import pickle

        self._log(
            "  - Far-field study: calculating input power from phantom cross-section.",
            log_type="info",
        )

        # Power density at E = 1 V/m
        e_field_v_m, z0 = 1.0, 377.0
        power_density_w_m2 = (e_field_v_m**2) / (2 * z0)

        # Get direction from position_name
        # Format can be: 'environmental_x_pos_theta', 'x_pos_theta', 'x_pos', etc.
        direction = self.parent.position_name
        # Remove 'environmental_' prefix if present
        direction = direction.replace("environmental_", "")

        # Extract direction part by checking for known patterns
        # Try to match orthogonal directions first
        direction_part = None
        for candidate in ["x_pos", "x_neg", "y_pos", "y_neg", "z_pos", "z_neg"]:
            if direction.startswith(candidate):
                direction_part = candidate
                break

        # If no orthogonal match, assume spherical format (e.g., "45_90")
        if direction_part is None:
            # Remove trailing polarization suffix if present (e.g., "45_90_theta" -> "45_90")
            direction_part = direction.rsplit("_", 1)[0] if "_" in direction else direction

        # Convert direction to (theta, phi) in radians
        # Standard orthogonal directions
        orthogonal_map = {
            "x_pos": (np.pi / 2, 0),  # θ=90°, φ=0° (front)
            "x_neg": (np.pi / 2, np.pi),  # θ=90°, φ=180° (back)
            "y_pos": (np.pi / 2, np.pi / 2),  # θ=90°, φ=90° (left)
            "y_neg": (np.pi / 2, 3 * np.pi / 2),  # θ=90°, φ=270° (right)
            "z_pos": (0, 0),  # θ=0° (top)
            "z_neg": (np.pi, 0),  # θ=180° (bottom)
        }

        if direction_part in orthogonal_map:
            theta_rad, phi_rad = orthogonal_map[direction_part]
        else:
            # Spherical tessellation format: "theta_phi" in degrees
            try:
                parts = direction_part.split("_")
                theta_rad = np.deg2rad(float(parts[0]))
                phi_rad = np.deg2rad(float(parts[1]))
            except (ValueError, IndexError):
                self._log(
                    f"  - WARNING: Could not parse direction '{direction_part}', using mean cross-section.",
                    log_type="warning",
                )
                theta_rad, phi_rad = None, None

        # Load phantom cross-section data
        phantom_name = str(self.config["phantom_name"] or self.parent.phantom_name)
        cross_section_path = os.path.join(str(self.config.base_dir), "data", "phantom_skins", phantom_name, "cross_section_pattern.pkl")

        area_m2 = None
        if os.path.exists(cross_section_path):
            try:
                with open(cross_section_path, "rb") as f:
                    # Try standard load first
                    try:
                        cs_data = pickle.load(f)
                    except ModuleNotFoundError:
                        # Numpy version mismatch - try with encoding fallback
                        f.seek(0)
                        cs_data = pickle.load(f, encoding="latin1")

                if theta_rad is not None and phi_rad is not None:
                    # Find nearest grid point
                    theta_grid = cs_data["theta"]  # (n_theta, n_phi)
                    phi_grid = cs_data["phi"]
                    areas = cs_data["areas"]

                    # Normalize phi to [0, 2π]
                    phi_rad = phi_rad % (2 * np.pi)

                    # Find closest indices
                    theta_vals = theta_grid[:, 0]  # Unique theta values
                    phi_vals = phi_grid[0, :]  # Unique phi values
                    i_theta = np.argmin(np.abs(theta_vals - theta_rad))
                    i_phi = np.argmin(np.abs(phi_vals - phi_rad))

                    area_m2 = areas[i_theta, i_phi]
                    self._log(
                        f"  - Phantom cross-section at θ={np.degrees(theta_rad):.1f}°, φ={np.degrees(phi_rad):.1f}°: {area_m2:.4f} m²",
                        log_type="verbose",
                    )
                else:
                    # Use mean cross-section as fallback
                    area_m2 = cs_data["stats"]["mean"]
                    self._log(
                        f"  - Using mean phantom cross-section: {area_m2:.4f} m²",
                        log_type="verbose",
                    )
            except Exception as e:
                self._log(
                    f"  - WARNING: Could not load cross-section data: {e}",
                    log_type="warning",
                )

        if area_m2 is None:
            # Fallback to typical adult frontal area
            area_m2 = 0.5
            self._log(
                f"  - WARNING: Using fallback cross-section: {area_m2} m²",
                log_type="warning",
            )

        theoretical_power = power_density_w_m2 * area_m2
        self.results_data.update(
            {
                "input_power_W": float(theoretical_power),
                "input_power_frequency_MHz": float(self.frequency_mhz),  # type: ignore
                "phantom_cross_section_m2": float(area_m2),
            }
        )
        self._log(
            f"  - Input power (at 1 V/m): {float(theoretical_power):.4e} W (cross-section: {area_m2:.4f} m²)",
            log_type="info",
        )

        # NOTE: Manual power extraction from S4L is disabled.
        # The "EM Input Power(f)" output is not available for far-field plane wave simulations
        # in either Sim4Life 8.2 or 9.2. See docs/technical/power_normalization_philosophy.md
        # for discussion of far-field power normalization.
        #
        # # Extract power from s4l for comparison
        # manual_power = None
        # try:
        #     em_sensor_extractor = simulation_extractor["Overall Field"]
        #     self.document.AllAlgorithms.Add(em_sensor_extractor)
        #     em_sensor_extractor.Update()
        #
        #     input_power_output = em_sensor_extractor.Outputs["EM Input Power(f)"]
        #
        #     if input_power_output:
        #         input_power_output.Update()
        #         power_data = input_power_output.Data.GetComponent(0)
        #
        #         if power_data is not None and power_data.size > 0:
        #             if power_data.size == 1:
        #                 manual_power = power_data.item()
        #             else:
        #                 center_freq_hz = self.frequency_mhz * 1e6  # type: ignore
        #                 axis = input_power_output.Data.Axis
        #                 target_index = np.argmin(np.abs(axis - center_freq_hz))
        #                 manual_power = power_data[target_index]
        #
        #             self._log(
        #                 f"  - MANUAL input power (from s4l): {float(manual_power):.4e} W",
        #                 log_type="info",
        #             )
        #         else:
        #             self._log(
        #                 "  - WARNING: Could not extract manual input power from s4l (empty data).",
        #                 log_type="warning",
        #             )
        #     else:
        #         self._log(
        #             "  - WARNING: 'EM Input Power(f)' output not available from Overall Field sensor.",
        #             log_type="warning",
        #         )
        # except Exception as e:
        #     self._log(
        #         f"  - WARNING: Could not extract manual input power from s4l: {e}",
        #         log_type="warning",
        #     )
        #     self.verbose_logger.error(traceback.format_exc())

    def _extract_near_field_power(self, simulation_extractor: "analysis.Extractor"):  # type: ignore
        """Extracts input power from port sensor for near-field simulations.

        Tries GetPower() first, falls back to manual extraction from harmonic
        data if needed. Handles both single-frequency and multi-frequency cases.

        Args:
            simulation_extractor: Results extractor from the simulation.
        """
        input_power_extractor = simulation_extractor["Input Power"]
        self.document.AllAlgorithms.Add(input_power_extractor)
        input_power_extractor.Update()

        if hasattr(input_power_extractor, "GetPower"):
            power_w, _ = input_power_extractor.GetPower(0)
            self.results_data.update(
                {
                    "input_power_W": float(power_w),
                    "input_power_frequency_MHz": float(self.frequency_mhz),  # type: ignore
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
                        "input_power_frequency_MHz": float(self.frequency_mhz),  # type: ignore
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
                        center_freq_hz = self.frequency_mhz * 1e6  # type: ignore
                        axis = input_power_output.Data.Axis
                        target_index = np.argmin(np.abs(axis - center_freq_hz))
                        input_power_w, freq_mhz = (
                            power_data[target_index],
                            axis[target_index] / 1e6,
                        )
                        self._log(
                            f"  - Selected frequency: {freq_mhz:.2f} MHz from {power_data.size} points",
                            log_type="info",
                        )
                    self.results_data.update(
                        {
                            "input_power_W": float(input_power_w),
                            "input_power_frequency_MHz": float(freq_mhz),  # type: ignore
                        }
                    )
                else:
                    self._log(
                        "  - WARNING: Could not extract input power values.",
                        log_type="warning",
                    )

    def extract_power_balance(self, simulation_extractor: "analysis.Extractor"):  # type: ignore
        """Extracts power balance to verify energy conservation.

        Power balance is a sanity check: the power going into the simulation should
        equal the power coming out (as losses and radiation). This helps catch
        numerical errors or convergence issues.

        The balance is calculated as: balance = (P_out / P_in) × 100%

        Where P_out includes:
        - Dielectric losses (power absorbed by materials)
        - Radiated power (power escaping the simulation volume)

        For far-field studies, uses the theoretical input power (from plane wave
        calculation) rather than extracted power, since plane waves don't have a
        traditional "input port" sensor.

        A balance close to 100% indicates good energy conservation. Values significantly
        different suggest convergence issues or numerical errors.

        Args:
            simulation_extractor: Results extractor from the simulation.
        """
        self._log("    - Extract power balance...", level="progress", log_type="progress")
        try:
            elapsed = 0.0
            if self.parent.study:
                with self.parent.study.profiler.subtask("extract_power_balance"):  # type: ignore
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

                elapsed = self.parent.study.profiler.subtask_times["extract_power_balance"][-1]
            self._log(f"      - Subtask 'extract_power_balance' done in {elapsed:.2f}s", log_type="verbose")
            self._log(f"      - Done in {elapsed:.2f}s", level="progress", log_type="success")

        except Exception as e:
            self._log(f"  - WARNING: Could not extract power balance: {e}", log_type="warning")
            self.verbose_logger.error(traceback.format_exc())
