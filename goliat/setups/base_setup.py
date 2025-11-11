import os
import pickle
from typing import TYPE_CHECKING

import numpy as np

from goliat.logging_manager import LoggingMixin

if TYPE_CHECKING:
    from logging import Logger

    import s4l_v1.model as model
    import s4l_v1.simulation.emfdtd as emfdtd

    from ..config import Config
    from ..project_manager import ProjectManager

# Define a dummy 'profile' decorator if the script is not run with kernprof
try:
    # This will succeed if the script is run with kernprof
    profile  # type: ignore
except NameError:
    # If not, define a dummy decorator that does nothing
    def profile(func):
        return func


class BaseSetup(LoggingMixin):
    """Base class for simulation setup modules.

    Provides common functionality like solver configuration, time/termination
    setup, point sensor creation, and final voxelization. Subclasses implement
    run_full_setup() for specific setup logic.
    """

    def __init__(self, config: "Config", verbose_logger: "Logger", progress_logger: "Logger"):
        """Sets up the base setup.

        Args:
            config: Configuration object.
            verbose_logger: Logger for detailed output.
            progress_logger: Logger for progress updates.
        """
        self.config = config
        self.verbose_logger = verbose_logger
        self.progress_logger = progress_logger
        import s4l_v1

        self.s4l_v1 = s4l_v1
        self.emfdtd = self.s4l_v1.simulation.emfdtd
        self.model = self.s4l_v1.model

    def _apply_simulation_time_and_termination(
        self,
        simulation: "emfdtd.Simulation",
        sim_bbox_entity: "model.Entity",
        frequency_mhz: int,
    ):
        """Sets simulation time and termination criteria based on bbox size.

        Calculates time from bbox diagonal length and frequency, then sets
        termination level (weak/medium/strong/user-defined) from config.

        Args:
            simulation: Simulation object to configure.
            sim_bbox_entity: Bounding box entity for size calculation.
            frequency_mhz: Simulation frequency in MHz.
        """
        sim_params = self.config["simulation_parameters"] or {}

        # Time Calculation
        time_multiplier = sim_params.get("simulation_time_multiplier", 5)
        self._log(f"  - Using simulation time multiplier: {time_multiplier}", log_type="info")

        bbox = self.model.GetBoundingBox([sim_bbox_entity])
        if not bbox or len(bbox) < 2:
            self._log(
                f"  - ERROR: Could not get a valid bounding box for entity '{sim_bbox_entity.Name}'. Skipping time calculation.",
                log_type="error",
            )
            return
        bbox_min, bbox_max = bbox

        diagonal_length_m = np.linalg.norm(np.array(bbox_max) - np.array(bbox_min)) / 1000.0

        time_to_travel_s = (time_multiplier * diagonal_length_m) / 299792458
        sim_time_periods = time_to_travel_s / (1 / (frequency_mhz * 1e6))
        simulation.SetupSettings.SimulationTime = (
            sim_time_periods,
            self.s4l_v1.units.Periods,
        )
        self._log(
            f"  - Simulation time set to {sim_time_periods:.2f} periods.",
            log_type="info",
        )

        # Termination Criteria
        term_level = sim_params.get("global_auto_termination", "GlobalAutoTerminationWeak")
        self._log(f"  - Setting termination criteria to: {term_level}", log_type="info")
        term_options = simulation.SetupSettings.GlobalAutoTermination.enum
        if hasattr(term_options, term_level):
            simulation.SetupSettings.GlobalAutoTermination = getattr(term_options, term_level)

        if term_level == "GlobalAutoTerminationUserDefined":
            convergence_db = sim_params.get("convergence_level_dB", -30)
            simulation.SetupSettings.ConvergenceLevel = convergence_db
            self._log(f"    - Convergence level set to: {convergence_db} dB", log_type="info")

    def _setup_solver_settings(self, simulation: "emfdtd.Simulation"):
        """Configures solver kernel (Software/CUDA/Acceleware) from config."""
        self._log("  - Configuring solver settings...", log_type="progress")
        solver_settings = self.config["solver_settings"] or {}
        if not solver_settings:
            return

        solver = simulation.SolverSettings

        # Setup Kernel
        kernel_type = solver_settings.get("kernel", "Software").lower()

        if kernel_type == "acceleware":
            solver.Kernel = solver.Kernel.enum.AXware
            self._log("    - Solver kernel set to: Acceleware (AXware)", log_type="info")
        elif kernel_type == "cuda":
            solver.Kernel = solver.Kernel.enum.Cuda
            self._log("    - Solver kernel set to: Cuda", log_type="info")
        else:
            solver.Kernel = solver.Kernel.enum.Software
            self._log("    - Solver kernel set to: Software", log_type="info")

    def run_full_setup(self, project_manager: "ProjectManager"):
        """Prepares the simulation scene. Must be implemented by subclasses.

        Returns:
            The configured simulation object.

        Raises:
            NotImplementedError: If not overridden by subclass.
        """
        raise NotImplementedError("The 'run_full_setup' method must be implemented by a subclass.")

    def _add_point_sensors(self, simulation: "emfdtd.Simulation", sim_bbox_entity_name: str):
        """Adds point sensors at bbox corners for E-field monitoring.

        Creates sensors at positions specified by point_source_order config.
        Skips if number_of_point_sensors is 0.

        Args:
            simulation: Simulation to add sensors to.
            sim_bbox_entity_name: Name of simulation bbox entity.
        """
        num_points = self.config["simulation_parameters.number_of_point_sensors"] or 0
        if num_points == 0:
            self._log(
                "  - Skipping point sensor creation (0 points requested).",
                log_type="info",
            )
            return

        sim_bbox_entity = next(
            (e for e in self.model.AllEntities() if sim_bbox_entity_name in e.Name),
            None,
        )
        if not sim_bbox_entity:
            self._log(
                f"  - WARNING: Could not find simulation bounding box '{sim_bbox_entity_name}' to add point sensors.",
                log_type="warning",
            )
            return

        bbox_min, bbox_max = self.model.GetBoundingBox([sim_bbox_entity])

        # Calculate bounding box center
        bbox_min_arr = np.array([bbox_min[0], bbox_min[1], bbox_min[2]])
        bbox_max_arr = np.array([bbox_max[0], bbox_max[1], bbox_max[2]])
        bbox_center = (bbox_min_arr + bbox_max_arr) / 2.0

        corner_map = {
            "lower_left_bottom": (bbox_min, bbox_min, bbox_min),
            "lower_right_bottom": (bbox_max, bbox_min, bbox_min),
            "lower_left_up": (bbox_min, bbox_max, bbox_min),
            "lower_right_up": (bbox_max, bbox_max, bbox_min),
            "top_left_bottom": (bbox_min, bbox_min, bbox_max),
            "top_right_bottom": (bbox_max, bbox_min, bbox_max),
            "top_left_up": (bbox_min, bbox_max, bbox_max),
            "top_right_up": (bbox_max, bbox_max, bbox_max),
        }

        point_source_order = self.config["simulation_parameters.point_source_order"]
        if point_source_order is None:
            point_source_order = list(corner_map.keys())

        for i in range(int(num_points)):  # type: ignore
            if point_source_order is None:
                continue
            corner_name = point_source_order[i]
            corner_coords = corner_map.get(corner_name)
            if corner_coords is None:
                self._log(
                    f"  - WARNING: Invalid corner name '{corner_name}' in point_source_order. Skipping.",
                    log_type="warning",
                )
                continue

            point_entity_name = f"Point Sensor Entity {i + 1} ({corner_name})"

            existing_entity = next(
                (e for e in self.model.AllEntities() if hasattr(e, "Name") and e.Name == point_entity_name),
                None,
            )

            if existing_entity:
                self._log(
                    f"  - Point sensor '{point_entity_name}' already exists. Skipping creation.",
                    log_type="info",
                )
                continue

            # Convert corner coordinates to numpy array
            corner_pos = np.array([corner_coords[0][0], corner_coords[1][1], corner_coords[2][2]])

            # Calculate vector from center to corner
            center_to_corner = corner_pos - bbox_center
            distance_to_corner = np.linalg.norm(center_to_corner)

            # Calculate 2% reduction distance
            reduction_distance = distance_to_corner * 0.02
            min_distance_from_center = 10.0  # 10 mm minimum

            # Determine final distance: 2% less, but at least 10 mm from center
            if reduction_distance < min_distance_from_center:
                final_distance = distance_to_corner - min_distance_from_center
            else:
                final_distance = distance_to_corner * 0.98

            # Ensure final distance is positive
            final_distance = max(final_distance, min_distance_from_center)

            # Calculate adjusted position along center-to-corner vector
            if distance_to_corner > 0:
                unit_vector = center_to_corner / distance_to_corner
                adjusted_pos = bbox_center + unit_vector * final_distance
            else:
                adjusted_pos = corner_pos

            point_entity = self.model.CreatePoint(self.model.Vec3(adjusted_pos[0], adjusted_pos[1], adjusted_pos[2]))
            point_entity.Name = point_entity_name
            point_sensor = self.emfdtd.PointSensorSettings()
            point_sensor.Name = f"Point Sensor {i + 1}"
            simulation.Add(point_sensor, [point_entity])
            self._log(
                f"  - Added point sensor at ({adjusted_pos[0]:.2f}, {adjusted_pos[1]:.2f}, {adjusted_pos[2]:.2f}) ({corner_name})",
                log_type="info",
            )

    @profile  # type: ignore
    def _finalize_setup(
        self,
        project_manager: "ProjectManager",
        simulation: "emfdtd.Simulation",
        all_simulation_parts: list,
        frequency_mhz: int,
    ):
        """Finalizes setup by voxelizing and updating materials/grid.

        Runs automatic voxelization, updates material properties, optionally
        exports material properties to pickle, then creates voxels and saves.

        Args:
            project_manager: Project manager for saving.
            simulation: Simulation object to finalize.
            all_simulation_parts: List of entities to voxelize.
            frequency_mhz: Frequency for material property export filename.
        """
        self._log("    - Finalizing setup...", log_type="progress")

        voxeler_settings = self.emfdtd.AutomaticVoxelerSettings()
        simulation.Add(voxeler_settings, all_simulation_parts)

        import XCore

        old_log_level = XCore.SetLogLevel(XCore.eLogCategory.Error)
        simulation.UpdateAllMaterials()
        XCore.SetLogLevel(old_log_level)

        if self.config["export_material_properties"]:
            self._log(
                "--- Extracting Material Properties ---",
                level="progress",
                log_type="header",
            )
            material_properties = []
            for settings in simulation.AllSettings:
                if isinstance(settings, self.emfdtd.MaterialSettings):
                    try:
                        self._log(f"  - Material: '{settings.Name}'", log_type="info")
                        self._log(
                            f"    - Relative Permittivity: {settings.ElectricProps.RelativePermittivity:.4f}",
                            log_type="verbose",
                        )
                        self._log(
                            f"    - Electric Conductivity (S/m): {settings.ElectricProps.Conductivity:.4f}",
                            log_type="verbose",
                        )
                        self._log(
                            f"    - Mass Density (kg/m^3): {settings.MassDensity:.2f}",
                            log_type="verbose",
                        )
                        material_properties.append(
                            {
                                "Name": settings.Name,
                                "RelativePermittivity": settings.ElectricProps.RelativePermittivity,
                                "Conductivity": settings.ElectricProps.Conductivity,
                                "MassDensity": settings.MassDensity,
                            }
                        )
                    except Exception as e:
                        self._log(
                            f"    - Could not extract properties for '{settings.Name}': {e}",
                            log_type="warning",
                        )
            self._log(
                "--- Finished Extracting Material Properties ---",
                level="progress",
                log_type="header",
            )

            output_dir = "analysis/cpw/data"
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
            output_path = os.path.join(output_dir, f"material_properties_{frequency_mhz}.pkl")
            with open(output_path, "wb") as f:
                pickle.dump(material_properties, f)
            self._log(
                f"--- Exported Material Properties to {output_path} ---",
                level="progress",
                log_type="success",
            )

        simulation.UpdateGrid()
        project_manager.save()
        simulation.CreateVoxels()
        self._log("    - Finalizing setup complete.", log_type="success")
