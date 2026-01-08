from typing import TYPE_CHECKING

import numpy as np

from .base_setup import BaseSetup
from .boundary_setup import BoundarySetup
from .gridding_setup import GriddingSetup
from .material_setup import MaterialSetup
from .phantom_setup import PhantomSetup

if TYPE_CHECKING:
    from logging import Logger

    import s4l_v1.model as model
    import s4l_v1.simulation.emfdtd as emfdtd

    from ..config import Config
    from ..profiler import Profiler
    from ..project_manager import ProjectManager


class FarFieldSetup(BaseSetup):
    """Configures a far-field simulation for a specific direction and polarization."""

    def __init__(
        self,
        config: "Config",
        phantom_name: str,
        frequency_mhz: int | list[int],
        direction_name: str,
        polarization_name: str,
        project_manager: "ProjectManager",
        verbose_logger: "Logger",
        progress_logger: "Logger",
        profiler: "Profiler",
        gui=None,
    ):
        super().__init__(config, verbose_logger, progress_logger, gui)
        self.phantom_name = phantom_name
        self.frequency_mhz = frequency_mhz
        # For multi-sine, use highest frequency for grid/reference
        self.reference_frequency_mhz = max(frequency_mhz) if isinstance(frequency_mhz, list) else frequency_mhz
        self.is_multisine = isinstance(frequency_mhz, list)
        self.direction_name = direction_name
        self.polarization_name = polarization_name
        self.project_manager = project_manager
        self.profiler = profiler
        self.gui = gui
        self.simulation_type = self.config["far_field_setup.type"]
        if self.simulation_type is None:
            self.simulation_type = "environmental"
        self.document = self.s4l_v1.document

    def run_full_setup(self, project_manager: "ProjectManager") -> "emfdtd.Simulation":
        """Executes the full setup sequence for a single far-field simulation with granular timing."""
        self._log("--- Setting up single Far-Field sim ---", log_type="header")

        # Subtask 1: Load phantom
        self._log("    - Load phantom...", level="progress", log_type="progress")
        with self.profiler.subtask("setup_load_phantom"):
            phantom_setup = PhantomSetup(
                self.config,
                self.phantom_name,
                self.verbose_logger,
                self.progress_logger,
            )
            phantom_setup.ensure_phantom_is_loaded()
        elapsed = self.profiler.subtask_times["setup_load_phantom"][-1]
        self._log(f"      - Subtask 'setup_load_phantom' done in {elapsed:.2f}s", log_type="verbose")
        self._log(f"      - Done in {elapsed:.2f}s", level="progress", log_type="success")

        # Subtask 2: Configure scene
        self._log("    - Configure scene (bbox, plane wave)...", level="progress", log_type="progress")
        with self.profiler.subtask("setup_configure_scene"):
            bbox_entity = self._create_or_get_simulation_bbox()
            simulation = self._create_simulation_entity(bbox_entity)
        elapsed = self.profiler.subtask_times["setup_configure_scene"][-1]
        self._log(f"      - Subtask 'setup_configure_scene' done in {elapsed:.2f}s", log_type="verbose")
        self._log(f"      - Done in {elapsed:.2f}s", level="progress", log_type="success")

        # Subtask 3: Assign materials
        self._log("    - Assign materials...", level="progress", log_type="progress")
        with self.profiler.subtask("setup_materials"):
            material_setup = MaterialSetup(
                self.config,
                simulation,
                None,  # type: ignore
                self.phantom_name,
                self.verbose_logger,
                self.progress_logger,
                free_space=False,
                frequencies_mhz=list(self.frequency_mhz) if self.is_multisine else None,  # type: ignore[arg-type]
            )
            material_setup.assign_materials(phantom_only=True)
        elapsed = self.profiler.subtask_times["setup_materials"][-1]
        self._log(f"      - Subtask 'setup_materials' done in {elapsed:.2f}s", log_type="verbose")
        self._log(f"      - Done in {elapsed:.2f}s", level="progress", log_type="success")

        # Subtask 4: Configure solver
        self._log("    - Configure solver (gridding, boundaries, sensors)...", level="progress", log_type="progress")
        with self.profiler.subtask("setup_solver"):
            gridding_setup = GriddingSetup(
                self.config,
                simulation,
                None,  # type: ignore
                None,  # type: ignore
                self.verbose_logger,
                self.progress_logger,
                frequency_mhz=self.reference_frequency_mhz,
            )
            gridding_setup.setup_gridding()

            boundary_setup = BoundarySetup(self.config, simulation, self.verbose_logger, self.progress_logger)
            boundary_setup.setup_boundary_conditions()

            self._add_point_sensors(simulation, "far_field_simulation_bbox")
            self._setup_solver_settings(simulation)
        elapsed = self.profiler.subtask_times["setup_solver"][-1]
        self._log(f"      - Subtask 'setup_solver' done in {elapsed:.2f}s", log_type="verbose")
        self._log(f"      - Done in {elapsed:.2f}s", level="progress", log_type="success")

        # Subtask 5: Voxelize
        self._log("    - Voxelize simulation...", level="progress", log_type="progress")
        with self.profiler.subtask("setup_voxelize"):
            bbox_entity = next(
                (e for e in self.model.AllEntities() if hasattr(e, "Name") and e.Name == "far_field_simulation_bbox"),
                None,
            )
            if not bbox_entity:
                raise RuntimeError("Could not find 'far_field_simulation_bbox' for voxelization.")

            import XCoreModeling

            phantom_entities = [e for e in self.model.AllEntities() if isinstance(e, XCoreModeling.TriangleMesh)]
            point_sensor_entities = [e for e in self.model.AllEntities() if "Point Sensor Entity" in e.Name]

            all_simulation_parts = phantom_entities + [bbox_entity] + point_sensor_entities

            super()._finalize_setup(self.project_manager, simulation, all_simulation_parts, self.reference_frequency_mhz)
        elapsed = self.profiler.subtask_times["setup_voxelize"][-1]
        self._log(f"      - Subtask 'setup_voxelize' done in {elapsed:.2f}s", log_type="verbose")
        self._log(f"      - Done in {elapsed:.2f}s", level="progress", log_type="success")

        # Subtask 6: Save project
        self._log("    - Save project...", level="progress", log_type="progress")
        with self.profiler.subtask("setup_save_project"):
            project_manager.save()
        elapsed = self.profiler.subtask_times["setup_save_project"][-1]
        self._log(f"      - Subtask 'setup_save_project' done in {elapsed:.2f}s", log_type="verbose")
        self._log(f"      - Done in {elapsed:.2f}s", level="progress", log_type="success")

        self._log("Common settings applied.", log_type="success")
        return simulation

    def _create_simulation_entity(self, bbox_entity: "model.Entity") -> "emfdtd.Simulation":
        """Creates EM-FDTD simulation with plane wave source.

        Configures plane wave direction (theta/phi) and polarization (psi)
        based on direction_name and polarization_name config.
        For multi-sine, uses UserDefined excitation with sum of cosines.

        Args:
            bbox_entity: Simulation bounding box entity.

        Returns:
            Configured simulation object.
        """
        # Format frequency for naming
        if self.is_multisine:
            freq_str = "+".join(str(f) for f in self.frequency_mhz)  # type: ignore
        else:
            freq_str = str(self.frequency_mhz)

        sim_name = f"EM_FDTD_{self.phantom_name}_{freq_str}MHz_{self.direction_name}_{self.polarization_name}"
        self._log(f"  - Creating simulation: {sim_name}", log_type="info")

        simulation = self.emfdtd.Simulation()
        simulation.Name = sim_name

        # Set reference frequency for the simulation (for material properties)
        simulation.Frequency = self.reference_frequency_mhz, self.s4l_v1.units.MHz

        plane_wave_source = self.emfdtd.PlaneWaveSourceSettings()
        # Set CenterFrequency immediately (required for source to work)
        plane_wave_source.CenterFrequency = self.reference_frequency_mhz, self.s4l_v1.units.MHz

        # Calculate direction vector (k) and angles
        # Support both orthogonal directions (x_pos, etc.) and spherical tessellation (theta_phi format)
        orthogonal_direction_map = {
            "x_pos": (0, 90),
            "x_neg": (180, 90),
            "y_pos": (90, 90),
            "y_neg": (270, 90),
            "z_pos": (0, 0),
            "z_neg": (0, 180),
        }

        if self.direction_name in orthogonal_direction_map:
            # Standard orthogonal direction
            phi_deg, theta_deg = orthogonal_direction_map[self.direction_name]
        else:
            # Spherical tessellation format: "theta_phi" in degrees (e.g., "45_90" means theta=45°, phi=90°)
            try:
                parts = self.direction_name.split("_")
                theta_deg = float(parts[0])
                phi_deg = float(parts[1])
                self._log(f"  - Spherical direction: theta={theta_deg}°, phi={phi_deg}°", log_type="verbose")
            except (ValueError, IndexError) as e:
                raise ValueError(
                    f"Invalid direction_name '{self.direction_name}'. Must be one of {list(orthogonal_direction_map.keys())} "
                    f"or a spherical tessellation format 'theta_phi' (e.g., '45_90')."
                ) from e

        plane_wave_source.Theta = theta_deg
        plane_wave_source.Phi = phi_deg

        # Set polarization (psi angle)
        if self.polarization_name == "theta":
            plane_wave_source.Psi = 0
        elif self.polarization_name == "phi":
            plane_wave_source.Psi = 90

        if self.is_multisine:
            # Multi-sine: UserDefined excitation with sum of cosines
            self._log(f"  - Configuring multi-sine excitation: {self.frequency_mhz} MHz", log_type="info")
            frequencies_hz = [f * 1e6 for f in self.frequency_mhz]  # type: ignore

            plane_wave_source.ExcitationType = plane_wave_source.ExcitationType.enum.UserDefined
            plane_wave_source.UserSignalType = plane_wave_source.UserSignalType.enum.FromEquation

            # Multiplicative ramping function to avoid instability/ripples at start
            ramp_periods = self.config["simulation_parameters.multisine_ramp_periods"]
            if ramp_periods is None:
                ramp_periods = 2.0

            # Use lowest frequency for ramping period calculation (safest for stability)
            min_freq_hz = min(frequencies_hz)
            t_ramp = ramp_periods / min_freq_hz

            # Smooth raised-cosine ramp: 0.5 * (1 - cos(pi * t / T_ramp)) for t < T_ramp, then 1.0
            # S4L parser may not support 'min()'. Use robust 'min(a, b) = 0.5 * (a + b - abs(a - b))'
            t_capped = f"0.5 * (_t + {t_ramp:.12e} - abs(_t - {t_ramp:.12e}))"
            ramp_expr = f"0.5 * (1 - cos(pi * {t_capped} / {t_ramp:.12e}))"

            # Create expression: cos(2*pi*f1*_t) + cos(2*pi*f2*_t) + ...
            # Equal amplitude for all frequencies. Use 'pi' constant (Sim4Life built-in)
            terms = [f"cos(2 * pi * {f} * _t)" for f in frequencies_hz]
            sum_expression = " + ".join(terms)

            expression = f"{ramp_expr} * ({sum_expression})"
            self._log(f"    - UserExpression: {expression}", log_type="verbose")
            plane_wave_source.UserExpression = expression

            # CRITICAL: Disable bandwidth filter so all frequency components pass through!
            # The default filter would only pass frequencies near CenterFrequency
            plane_wave_source.ApplyFilter = False

            # Setup overall field sensor with extracted frequencies
            field_sensor_settings = simulation.AddOverallFieldSensorSettings()
            field_sensor_settings.ExtractedFrequencies = frequencies_hz
            field_sensor_settings.OnTheFlyDFT = True
            field_sensor_settings.RecordEField = True
            field_sensor_settings.RecordHField = False
            field_sensor_settings.RecordingDomain = field_sensor_settings.RecordingDomain.enum.RecordInFrequencyDomain
            self._log(f"  - Configured field sensor for frequencies: {self.frequency_mhz} MHz", log_type="info")
        else:
            # Single frequency harmonic
            plane_wave_source.ExcitationType = plane_wave_source.ExcitationType.enum.Harmonic
            plane_wave_source.ApplyFilter = True  # Default, but explicit is safer
            # CenterFrequency already set immediately after creation

        simulation.Add(plane_wave_source, [bbox_entity])
        self.document.AllSimulations.Add(simulation)

        self._apply_simulation_time_and_termination(simulation, bbox_entity, self.frequency_mhz)

        return simulation

    def _get_phantom_height_limit_mm(self, phantom_bbox_min: np.ndarray, phantom_bbox_max: np.ndarray) -> float | None:
        """Determines the phantom height limit for the current frequency.

        Checks for manual per-frequency height limits first, then falls back to
        automatic reduction if enabled. Returns None if no reduction should be applied.

        Args:
            phantom_bbox_min: Original phantom bounding box minimum [x, y, z] in mm.
            phantom_bbox_max: Original phantom bounding box maximum [x, y, z] in mm.

        Returns:
            Height limit in mm (measured from top of head downward), or None for full body.
        """
        bbox_reduction = self.config["gridding_parameters.phantom_bbox_reduction"]
        if not bbox_reduction:
            return None

        freq_mhz = self.reference_frequency_mhz

        # Check for manual per-frequency height limit first
        height_per_freq = bbox_reduction.get("height_limit_per_frequency_mm", {})
        if height_per_freq and isinstance(height_per_freq, dict):
            freq_key = str(int(freq_mhz))
            if freq_key in height_per_freq:
                manual_limit = height_per_freq[freq_key]
                self._log(f"  - Using manual height limit: {manual_limit} mm for {freq_mhz} MHz", log_type="info")
                return manual_limit

        # Check for automatic reduction
        auto_reduce = bbox_reduction.get("auto_reduce_bbox", False)
        if not auto_reduce:
            return None

        # Get reference frequency (the highest frequency where full body fits)
        reference_freq_mhz = bbox_reduction.get("reference_frequency_mhz", 5800)
        if freq_mhz <= reference_freq_mhz:
            self._log(
                f"  - Frequency {freq_mhz} MHz at or below reference ({reference_freq_mhz} MHz), no reduction needed",
                log_type="verbose",
            )
            return None

        # Calculate automatic height limit based on cubic frequency scaling
        height_limit = self._calculate_auto_height_limit(phantom_bbox_min, phantom_bbox_max, freq_mhz, reference_freq_mhz)

        if height_limit is not None:
            full_height = phantom_bbox_max[2] - phantom_bbox_min[2]
            reduction_pct = (1 - height_limit / full_height) * 100
            self._log(
                f"  - Auto-calculated height limit: {height_limit:.1f} mm for {freq_mhz} MHz "
                f"(ref: {reference_freq_mhz} MHz, reduction: {reduction_pct:.1f}%)",
                log_type="info",
            )

        return height_limit

    def _calculate_auto_height_limit(
        self,
        phantom_bbox_min: np.ndarray,
        phantom_bbox_max: np.ndarray,
        freq_mhz: int,
        reference_freq_mhz: int,
    ) -> float | None:
        """Calculates automatic height limit based on cubic frequency scaling.

        Cell count scales cubically with frequency (since cell size ~ 1/freq for constant
        cells per wavelength). To maintain the same cell count as at reference_freq_mhz,
        we reduce the height by the cubic ratio of frequencies.

        Formula: height_factor = (reference_freq / current_freq)^3

        Args:
            phantom_bbox_min: Original phantom bounding box minimum [x, y, z] in mm.
            phantom_bbox_max: Original phantom bounding box maximum [x, y, z] in mm.
            freq_mhz: Current simulation frequency in MHz.
            reference_freq_mhz: Reference frequency where full body fits in memory.

        Returns:
            Height limit in mm, or None if no reduction needed.
        """
        # Calculate full phantom height
        full_height_mm = phantom_bbox_max[2] - phantom_bbox_min[2]

        # Calculate height reduction factor using cubic frequency scaling
        # Cell count at freq_mhz vs reference_freq_mhz scales as (freq/ref)^3
        # To keep same cell count, reduce height by (ref/freq)^3
        height_factor = (reference_freq_mhz / freq_mhz) ** 3

        reduced_height_mm = full_height_mm * height_factor

        # Ensure we keep at least 20% of the body (head + upper torso minimum)
        min_height_mm = full_height_mm * 0.2
        reduced_height_mm = max(reduced_height_mm, min_height_mm)

        self._log(
            f"  - Height scaling: ({reference_freq_mhz}/{freq_mhz})^3 = {height_factor:.4f}",
            log_type="verbose",
        )

        return reduced_height_mm

    def _create_or_get_simulation_bbox(self) -> "model.Entity":
        """Creates simulation bbox from phantom geometry with padding.

        Supports optional phantom height reduction for high frequencies to manage
        computational costs (truncating from bottom). Also supports symmetry reduction
        when `use_symmetry_reduction` is enabled, which cuts the bounding box in half
        along the x-axis to exploit human left-right symmetry.
        """
        bbox_name = "far_field_simulation_bbox"
        self._log("Creating simulation bounding box for far-field...", log_type="progress")
        import XCoreModeling

        phantom_entities = [e for e in self.model.AllEntities() if isinstance(e, XCoreModeling.TriangleMesh)]
        if not phantom_entities:
            raise RuntimeError("No phantom found to create bounding box.")

        bbox_min, bbox_max = self.model.GetBoundingBox(phantom_entities)
        original_bbox_min = np.array(bbox_min)
        original_bbox_max = np.array(bbox_max)

        # Check for phantom height reduction
        height_limit_mm = self._get_phantom_height_limit_mm(original_bbox_min, original_bbox_max)

        if height_limit_mm is not None:
            # Truncate from bottom: keep top (head), reduce from below
            # Z-axis: max is top of head, min is feet
            full_height = original_bbox_max[2] - original_bbox_min[2]
            if height_limit_mm < full_height:
                new_z_min = original_bbox_max[2] - height_limit_mm
                original_bbox_min[2] = new_z_min
                self._log(
                    f"  - Phantom bbox reduced: keeping top {height_limit_mm:.1f} mm "
                    f"(original height: {full_height:.1f} mm, reduction: {(1 - height_limit_mm / full_height) * 100:.1f}%)",
                    log_type="info",
                )

        padding_mm = self.config["simulation_parameters.bbox_padding_mm"]
        if padding_mm is None:
            padding_mm = 50

        sim_bbox_min = original_bbox_min - padding_mm
        sim_bbox_max = original_bbox_max + padding_mm

        # Check for symmetry reduction (cut phantom in half, keep positive x side)
        bbox_reduction = self.config["gridding_parameters.phantom_bbox_reduction"]
        use_symmetry = False
        if bbox_reduction and isinstance(bbox_reduction, dict):
            use_symmetry = bbox_reduction.get("use_symmetry_reduction", False)

        if use_symmetry:
            # Cut the bounding box at x=0, keeping only the positive x (right) side
            # Human phantoms are typically centered at x=0
            original_x_min = sim_bbox_min[0]
            sim_bbox_min[0] = 0.0  # Move x_min to the center (x=0)
            self._log(
                f"  - Symmetry reduction enabled: cutting bbox at x=0 (original x_min: {original_x_min:.1f}mm, new x_min: 0.0mm)",
                log_type="info",
            )

        sim_bbox = XCoreModeling.CreateWireBlock(self.model.Vec3(sim_bbox_min), self.model.Vec3(sim_bbox_max))
        sim_bbox.Name = bbox_name
        self._log(
            f"  - Created far-field simulation BBox with {padding_mm}mm padding.",
            log_type="info",
        )
        return sim_bbox
