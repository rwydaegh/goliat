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
        frequency_mhz: int,
        direction_name: str,
        polarization_name: str,
        project_manager: "ProjectManager",
        verbose_logger: "Logger",
        progress_logger: "Logger",
        profiler: "Profiler",
        gui=None,
    ):
        super().__init__(config, verbose_logger, progress_logger)
        self.phantom_name = phantom_name
        self.frequency_mhz = frequency_mhz
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
                frequency_mhz=self.frequency_mhz,
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

            super()._finalize_setup(self.project_manager, simulation, all_simulation_parts, self.frequency_mhz)
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

        Args:
            bbox_entity: Simulation bounding box entity.

        Returns:
            Configured simulation object.
        """
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
        """Creates simulation bbox from phantom geometry with padding."""
        bbox_name = "far_field_simulation_bbox"
        self._log("Creating simulation bounding box for far-field...", log_type="progress")
        import XCoreModeling

        phantom_entities = [e for e in self.model.AllEntities() if isinstance(e, XCoreModeling.TriangleMesh)]
        if not phantom_entities:
            raise RuntimeError("No phantom found to create bounding box.")

        bbox_min, bbox_max = self.model.GetBoundingBox(phantom_entities)

        padding_mm = self.config["simulation_parameters.bbox_padding_mm"]
        if padding_mm is None:
            padding_mm = 50

        sim_bbox_min = np.array(bbox_min) - padding_mm
        sim_bbox_max = np.array(bbox_max) + padding_mm

        sim_bbox = XCoreModeling.CreateWireBlock(self.model.Vec3(sim_bbox_min), self.model.Vec3(sim_bbox_max))
        sim_bbox.Name = bbox_name
        self._log(
            f"  - Created far-field simulation BBox with {padding_mm}mm padding.",
            log_type="info",
        )
        return sim_bbox
