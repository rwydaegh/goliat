from typing import TYPE_CHECKING

import numpy as np

from .base_setup import BaseSetup
from .boundary_setup import BoundarySetup
from .gridding_setup import GriddingSetup
from .material_setup import MaterialSetup

if TYPE_CHECKING:
    from logging import Logger

    import s4l_v1.model as model
    import s4l_v1.simulation.emfdtd as emfdtd

    from ..config import Config
    from ..project_manager import ProjectManager
    from .phantom_setup import PhantomSetup


class FarFieldSetup(BaseSetup):
    """Configures a far-field simulation for a specific direction and polarization."""

    def __init__(
        self,
        config: "Config",
        phantom_name: str,
        frequency_mhz: int,
        direction_name: str,
        polarization_name: str,
        project_manager: "ProjectManager",
        verbose_logger: "Logger",
        progress_logger: "Logger",
    ):
        super().__init__(config, verbose_logger, progress_logger)
        self.phantom_name = phantom_name
        self.frequency_mhz = frequency_mhz
        self.direction_name = direction_name
        self.polarization_name = polarization_name
        self.project_manager = project_manager
        self.simulation_type = self.config.get_setting("far_field_setup/type", "environmental")
        self.document = self.s4l_v1.document

    def run_full_setup(self, phantom_setup: "PhantomSetup") -> "emfdtd.Simulation":
        """Executes the full setup sequence for a single far-field simulation."""
        self._log("--- Setting up single Far-Field sim ---", log_type="header")

        # The phantom is now loaded once per project in the study.
        # This setup will just add a simulation to the currently open project.
        bbox_entity = self._create_or_get_simulation_bbox()

        simulation = self._create_simulation_entity(bbox_entity)

        self._apply_common_settings(simulation)

        return simulation

    def _create_simulation_entity(self, bbox_entity: "model.Entity") -> "emfdtd.Simulation":
        """Creates the EM FDTD simulation entity and its plane wave source."""
        sim_name = f"EM_FDTD_{self.phantom_name}_{self.frequency_mhz}MHz_{self.direction_name}_{self.polarization_name}"
        self._log(f"  - Creating simulation: {sim_name}", log_type="info")

        simulation = self.emfdtd.Simulation()
        simulation.Name = sim_name

        # Set frequency for the entire simulation FIRST. This influences material properties.
        simulation.Frequency = self.frequency_mhz, self.s4l_v1.units.MHz

        plane_wave_source = self.emfdtd.PlaneWaveSourceSettings()
        plane_wave_source.CenterFrequency = self.frequency_mhz, self.s4l_v1.units.MHz

        # Calculate direction vector (k) and angles
        direction_map = {
            "x_pos": (0, 90),
            "x_neg": (180, 90),
            "y_pos": (90, 90),
            "y_neg": (270, 90),
            "z_pos": (0, 0),
            "z_neg": (0, 180),
        }
        phi_deg, theta_deg = direction_map[self.direction_name]

        plane_wave_source.Theta = theta_deg
        plane_wave_source.Phi = phi_deg

        # Set polarization (psi angle)
        if self.polarization_name == "theta":
            plane_wave_source.Psi = 0
        elif self.polarization_name == "phi":
            plane_wave_source.Psi = 90

        simulation.Add(plane_wave_source, [bbox_entity])
        self.document.AllSimulations.Add(simulation)

        self._apply_simulation_time_and_termination(simulation, bbox_entity, self.frequency_mhz)

        return simulation

    def _create_or_get_simulation_bbox(self) -> "model.Entity":
        """Creates the simulation bounding box."""
        bbox_name = "far_field_simulation_bbox"
        self._log("Creating simulation bounding box for far-field...", log_type="progress")
        import XCoreModeling

        phantom_entities = [e for e in self.model.AllEntities() if isinstance(e, XCoreModeling.TriangleMesh)]
        if not phantom_entities:
            raise RuntimeError("No phantom found to create bounding box.")

        bbox_min, bbox_max = self.model.GetBoundingBox(phantom_entities)

        padding_mm = self.config.get_setting("simulation_parameters.bbox_padding_mm", 50)

        sim_bbox_min = np.array(bbox_min) - padding_mm
        sim_bbox_max = np.array(bbox_max) + padding_mm

        sim_bbox = XCoreModeling.CreateWireBlock(self.model.Vec3(sim_bbox_min), self.model.Vec3(sim_bbox_max))
        sim_bbox.Name = bbox_name
        self._log(
            f"  - Created far-field simulation BBox with {padding_mm}mm padding.",
            log_type="info",
        )
        return sim_bbox

    def _apply_common_settings(self, simulation: "emfdtd.Simulation"):
        """Applies common material, gridding, and solver settings."""
        self._log(f"Applying common settings to {simulation.Name}...", log_type="progress")

        material_setup = MaterialSetup(
            self.config,
            simulation,
            None,
            self.phantom_name,
            self.verbose_logger,
            self.progress_logger,
            free_space=False,
        )
        material_setup.assign_materials(phantom_only=True)

        gridding_setup = GriddingSetup(
            self.config,
            simulation,
            None,
            None,
            self.verbose_logger,
            self.progress_logger,
            frequency_mhz=self.frequency_mhz,
        )
        gridding_setup.setup_gridding()

        boundary_setup = BoundarySetup(self.config, simulation, self.verbose_logger, self.progress_logger)
        boundary_setup.setup_boundary_conditions()

        self._add_point_sensors(simulation, "far_field_simulation_bbox")

        self._setup_solver_settings(simulation)

        self._finalize_setup(self.project_manager, simulation, self.frequency_mhz)
        self._log("Common settings applied.", log_type="success")

    def _finalize_setup(
        self,
        project_manager: "ProjectManager",
        simulation: "emfdtd.Simulation",
        frequency_mhz: int,
    ):
        """Gathers entities and calls the finalization method from the base class."""
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

        super()._finalize_setup(project_manager, simulation, all_simulation_parts, frequency_mhz)
