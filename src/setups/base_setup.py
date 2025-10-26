import os
import pickle
from typing import TYPE_CHECKING

import numpy as np

from src.logging_manager import LoggingMixin

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
    """Abstract base class for all simulation setups."""

    def __init__(self, config: "Config", verbose_logger: "Logger", progress_logger: "Logger"):
        """Initializes the base setup.

        Args:
            config: The configuration object for the study.
            verbose_logger: Logger for verbose output.
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
        """Calculates and applies simulation time and termination settings."""
        sim_params = self.config.get_simulation_parameters()

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
        """Configures solver settings, including kernel."""
        self._log("  - Configuring solver settings...", log_type="progress")
        solver_settings = self.config.get_solver_settings()
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

        Args:
            project_manager: The project manager for file operations.

        Returns:
            The main simulation object.
        """
        raise NotImplementedError("The 'run_full_setup' method must be implemented by a subclass.")

    def _add_point_sensors(self, simulation: "emfdtd.Simulation", sim_bbox_entity_name: str):
        """Adds point sensors at the corners of the simulation bounding box."""
        num_points = self.config.get_setting("simulation_parameters.number_of_point_sensors", 0)
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

        point_source_order = self.config.get_setting("simulation_parameters.point_source_order", list(corner_map.keys()))

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

            point_entity = self.model.CreatePoint(self.model.Vec3(corner_coords[0][0], corner_coords[1][1], corner_coords[2][2]))
            point_entity.Name = point_entity_name
            point_sensor = self.emfdtd.PointSensorSettings()
            point_sensor.Name = f"Point Sensor {i + 1}"
            simulation.Add(point_sensor, [point_entity])
            self._log(
                f"  - Added point sensor at {corner_coords} ({corner_name})",
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
        """Performs the final voxelization and grid update for a simulation."""
        self._log("    - Finalizing setup...", log_type="progress")

        voxeler_settings = self.emfdtd.AutomaticVoxelerSettings()
        simulation.Add(voxeler_settings, all_simulation_parts)

        import XCore

        old_log_level = XCore.SetLogLevel(XCore.eLogCategory.Error)
        simulation.UpdateAllMaterials()
        XCore.SetLogLevel(old_log_level)

        if self.config.get_setting("export_material_properties"):
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
