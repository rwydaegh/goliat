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
        """Calculates input power for a plane wave using configurable method.

        Far-field simulations use plane waves with a fixed E-field amplitude (1 V/m).
        This method supports two approaches for defining "input power" for power balance:

        1. "bounding_box" (default): Uses the projected area of the simulation bounding box
           as seen from the incident direction. This is consistent with Sim4Life's RadPower
           output, which includes all power flux through the boundaries (not just scattered).
           Gives ~100% power balance but the metric depends on simulation domain size.

        2. "phantom_cross_section": Uses the phantom's projected cross-sectional area.
           Represents actual power intercepted by the body, but gives >100% balance because
           RadPower includes power that bypassed the phantom entirely.

        The method is configured via config["power_balance.input_method"].

        See docs/technical/power_normalization_philosophy.md for full discussion.

        Args:
            simulation_extractor: Results extractor from the simulation.
        """
        import os

        # Determine which method to use
        input_method = self.config["power_balance.input_method"] or "bounding_box"
        self._log(
            f"  - Far-field study: calculating input power using '{input_method}' method.",
            log_type="info",
        )

        # Power density at E = 1 V/m
        e_field_v_m, z0 = 1.0, 377.0
        power_density_w_m2 = (e_field_v_m**2) / (2 * z0)

        # Parse direction from position_name
        direction = self.parent.position_name.replace("environmental_", "")

        # Extract direction part by checking for known patterns
        direction_part = None
        for candidate in ["x_pos", "x_neg", "y_pos", "y_neg", "z_pos", "z_neg"]:
            if direction.startswith(candidate):
                direction_part = candidate
                break

        # If no orthogonal match, assume spherical format (e.g., "45_90")
        if direction_part is None:
            direction_part = direction.rsplit("_", 1)[0] if "_" in direction else direction

        # Convert direction to (theta, phi) in radians
        orthogonal_map = {
            "x_pos": (np.pi / 2, 0),
            "x_neg": (np.pi / 2, np.pi),
            "y_pos": (np.pi / 2, np.pi / 2),
            "y_neg": (np.pi / 2, 3 * np.pi / 2),
            "z_pos": (0, 0),
            "z_neg": (np.pi, 0),
        }

        if direction_part in orthogonal_map:
            theta_rad, phi_rad = orthogonal_map[direction_part]
        else:
            try:
                parts = direction_part.split("_")
                theta_rad = np.deg2rad(float(parts[0]))
                phi_rad = np.deg2rad(float(parts[1]))
            except (ValueError, IndexError):
                self._log(
                    f"  - WARNING: Could not parse direction '{direction_part}'.",
                    log_type="warning",
                )
                theta_rad, phi_rad = np.pi / 2, 0  # Default to x_pos

        # Calculate area based on selected method
        if input_method == "bounding_box":
            area_m2, area_source = self._calculate_bbox_cross_section(theta_rad, phi_rad, direction_part)
        else:  # phantom_cross_section
            area_m2, area_source = self._calculate_phantom_cross_section(theta_rad, phi_rad, os)

        theoretical_power = power_density_w_m2 * area_m2
        self.results_data.update(
            {
                "input_power_W": float(theoretical_power),
                "input_power_frequency_MHz": float(self.frequency_mhz),  # type: ignore
                "power_balance_input_method": input_method,
                "cross_section_m2": float(area_m2),
                "cross_section_source": area_source,
            }
        )
        self._log(
            f"  - Input power (at 1 V/m): {float(theoretical_power):.4e} W ({area_source}: {area_m2:.4f} m2)",
            log_type="info",
        )

    def _calculate_bbox_cross_section(self, theta_rad: float, phi_rad: float, direction_part: str) -> tuple[float, str]:
        """Calculates the projected cross-sectional area of the bounding box.

        For orthogonal directions, this is simply the area of the corresponding face.
        For non-orthogonal directions (spherical tessellation), computes the projected
        area of the axis-aligned bbox onto a plane perpendicular to the incident direction.

        Args:
            theta_rad: Polar angle in radians (0 = +z, pi = -z).
            phi_rad: Azimuthal angle in radians (0 = +x, pi/2 = +y).
            direction_part: Direction string (e.g., "x_pos", "45_90").

        Returns:
            Tuple of (area in m², description string).
        """
        import s4l_v1.model

        try:
            bbox_entity = next(
                (e for e in s4l_v1.model.AllEntities() if hasattr(e, "Name") and e.Name == "far_field_simulation_bbox"),
                None,
            )
            if not bbox_entity:
                raise RuntimeError("Could not find 'far_field_simulation_bbox' entity.")
            sim_bbox = s4l_v1.model.GetBoundingBox([bbox_entity])
        except RuntimeError as e:
            self._log(f"  - WARNING: Could not get bbox: {e}. Using fallback.", log_type="warning")
            return 0.5, "fallback"

        sim_min, sim_max = np.array(sim_bbox[0]), np.array(sim_bbox[1])
        padding_bottom = np.array(self.config["gridding_parameters.padding.manual_bottom_padding_mm"] or [0, 0, 0])
        padding_top = np.array(self.config["gridding_parameters.padding.manual_top_padding_mm"] or [0, 0, 0])
        total_min = sim_min - padding_bottom
        total_max = sim_max + padding_top
        dims_mm = total_max - total_min  # [dx, dy, dz] in mm

        # Face areas in m² (dims are in mm)
        A_yz = (dims_mm[1] * dims_mm[2]) / 1e6  # x-facing
        A_xz = (dims_mm[0] * dims_mm[2]) / 1e6  # y-facing
        A_xy = (dims_mm[0] * dims_mm[1]) / 1e6  # z-facing

        # Orthogonal directions: use the perpendicular face directly
        orthogonal_areas = {
            "x_pos": A_yz,
            "x_neg": A_yz,
            "y_pos": A_xz,
            "y_neg": A_xz,
            "z_pos": A_xy,
            "z_neg": A_xy,
        }

        if direction_part in orthogonal_areas:
            area_m2 = orthogonal_areas[direction_part]
            self._log(f"  - Bbox cross-section ({direction_part}): {area_m2:.4f} m2", log_type="verbose")
            return area_m2, f"bbox_{direction_part}"

        # Non-orthogonal: compute projected area
        # Incident direction unit vector (where wave comes FROM, pointing toward origin)
        # In spherical coords: n = (sin(theta)*cos(phi), sin(theta)*sin(phi), cos(theta))
        n_x = np.sin(theta_rad) * np.cos(phi_rad)
        n_y = np.sin(theta_rad) * np.sin(phi_rad)
        n_z = np.cos(theta_rad)

        # Projected area = |n·x̂|*A_yz + |n·ŷ|*A_xz + |n·ẑ|*A_xy
        area_m2 = abs(n_x) * A_yz + abs(n_y) * A_xz + abs(n_z) * A_xy
        self._log(
            f"  - Bbox projected cross-section (theta={np.degrees(theta_rad):.1f} deg, phi={np.degrees(phi_rad):.1f} deg): {area_m2:.4f} m2",
            log_type="verbose",
        )
        return area_m2, f"bbox_projected_{direction_part}"

    def _calculate_phantom_cross_section(self, theta_rad: float, phi_rad: float, os_module) -> tuple[float, str]:
        """Calculates the phantom's projected cross-sectional area for the direction.

        Loads pre-computed cross-section pattern from data/phantom_skins/.

        Args:
            theta_rad: Polar angle in radians.
            phi_rad: Azimuthal angle in radians.
            os_module: The os module (passed to avoid reimport).

        Returns:
            Tuple of (area in m², description string).
        """
        import json

        phantom_name = str(self.config["phantom_name"] or self.parent.phantom_name)
        cross_section_path = os_module.path.join(
            str(self.config.base_dir), "data", "phantom_skins", phantom_name, "cross_section_pattern.json"
        )

        if not os_module.path.exists(cross_section_path):
            self._log(f"  - WARNING: Cross-section data not found at {cross_section_path}", log_type="warning")
            return 0.5, "phantom_fallback"

        try:
            with open(cross_section_path) as f:
                cs_data = json.load(f)

            theta_grid = np.array(cs_data["theta"])
            phi_grid = np.array(cs_data["phi"])
            areas = np.array(cs_data["areas"])

            # Normalize phi to [0, 2π]
            phi_rad_norm = phi_rad % (2 * np.pi)

            # Find closest indices
            theta_vals = theta_grid[:, 0]
            phi_vals = phi_grid[0, :]
            i_theta = int(np.argmin(np.abs(theta_vals - theta_rad)))
            i_phi = int(np.argmin(np.abs(phi_vals - phi_rad_norm)))

            area_m2 = float(areas[i_theta, i_phi])
            self._log(
                f"  - Phantom cross-section ({phantom_name}) at theta={np.degrees(theta_rad):.1f} deg, "
                f"phi={np.degrees(phi_rad_norm):.1f} deg: {area_m2:.4f} m2",
                log_type="verbose",
            )
            return area_m2, f"phantom_{phantom_name}"
        except Exception as e:
            self._log(f"  - WARNING: Could not load cross-section data: {e}", log_type="warning")
            return 0.5, "phantom_fallback"

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
