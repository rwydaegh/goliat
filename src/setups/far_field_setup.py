import os
import numpy as np
from .base_setup import BaseSetup
from .phantom_setup import PhantomSetup
from .material_setup import MaterialSetup
from .gridding_setup import GriddingSetup

class FarFieldSetup(BaseSetup):
    """
    Configures a single far-field simulation for a specific direction and polarization.
    """
    def __init__(self, config, phantom_name, frequency_mhz, direction_name, polarization_name, project_manager, verbose=True):
        super().__init__(config, verbose)
        self.phantom_name = phantom_name
        self.frequency_mhz = frequency_mhz
        self.direction_name = direction_name
        self.polarization_name = polarization_name
        self.project_manager = project_manager
        self.simulation_type = self.config.get_setting('far_field_setup/type', 'environmental')
        self.document = self.s4l_v1.document

    def run_full_setup(self, phantom_setup):
        """
        Executes the full sequence of setup steps for a single far-field simulation.
        """
        self._log(f"--- Setting up single Far-Field sim ---")
        
        # The phantom is now loaded once per project in the study.
        # This setup will just add a simulation to the currently open project.
        bbox_entity = self._create_or_get_simulation_bbox()
        
        simulation = self._create_simulation_entity(bbox_entity)

        self._apply_common_settings(simulation)
        
        return simulation

    def _create_simulation_entity(self, bbox_entity):
        """
        Creates the EM FDTD simulation entity and its plane wave source.
        """
        sim_name = f"EM_FDTD_{self.phantom_name}_{self.frequency_mhz}MHz_{self.direction_name}_{self.polarization_name}"
        self._log(f"  - Creating simulation: {sim_name}")
        
        simulation = self.emfdtd.Simulation()
        simulation.Name = sim_name
        
        # Set frequency for the entire simulation FIRST. This influences material properties.
        simulation.Frequency = self.frequency_mhz, self.s4l_v1.units.MHz

        plane_wave_source = self.emfdtd.PlaneWaveSourceSettings()
        plane_wave_source.CenterFrequency = self.frequency_mhz, self.s4l_v1.units.MHz
        
        # Calculate direction vector (k) and angles
        direction_map = {
            "x_pos": (0, 90), "x_neg": (180, 90),
            "y_pos": (90, 90), "y_neg": (270, 90),
            "z_pos": (0, 0),   "z_neg": (0, 180)
        }
        phi_deg, theta_deg = direction_map[self.direction_name]
        
        plane_wave_source.Theta = theta_deg
        plane_wave_source.Phi = phi_deg

        # Set polarization (psi angle)
        if self.polarization_name == 'theta':
            plane_wave_source.Psi = 0
        elif self.polarization_name == 'phi':
            plane_wave_source.Psi = 90
        
        simulation.Add(plane_wave_source, [bbox_entity])
        self.document.AllSimulations.Add(simulation)

        self._apply_simulation_time_and_termination(simulation, bbox_entity, self.frequency_mhz)

        return simulation

    def _create_or_get_simulation_bbox(self):
        """
        Creates the simulation bounding box if it doesn't exist, otherwise returns the existing one.
        """
        bbox_name = "far_field_simulation_bbox"
        existing_bbox = next((e for e in self.model.AllEntities() if hasattr(e, 'Name') and e.Name == bbox_name), None)
        if existing_bbox:
            self._log("Found existing simulation bounding box.")
            return existing_bbox

        self._log("Creating simulation bounding box for far-field...")
        import XCoreModeling
        phantom_entities = [e for e in self.model.AllEntities() if isinstance(e, XCoreModeling.TriangleMesh)]
        if not phantom_entities:
            raise RuntimeError("No phantom found to create bounding box.")
        
        bbox_min, bbox_max = self.model.GetBoundingBox(phantom_entities)
        
        padding_m = self.config.get_setting("simulation_parameters/bbox_padding_m", 0.05)
        padding_mm = padding_m * 1000

        sim_bbox_min = np.array(bbox_min) - padding_mm
        sim_bbox_max = np.array(bbox_max) + padding_mm

        sim_bbox = XCoreModeling.CreateWireBlock(self.model.Vec3(sim_bbox_min), self.model.Vec3(sim_bbox_max))
        sim_bbox.Name = bbox_name
        self._log(f"  - Created far-field simulation BBox with {padding_m}m padding.")
        return sim_bbox

    def _apply_common_settings(self, simulation):
        """
        Applies common material, gridding, and solver settings to the simulation.
        """
        self._log(f"Applying common settings to {simulation.Name}...")
        
        material_setup = MaterialSetup(self.config, simulation, None, self.verbose, free_space=False)
        material_setup.assign_materials(phantom_only=True)

        gridding_setup = GriddingSetup(self.config, simulation, None, None, self.verbose)
        gridding_setup.setup_gridding()

        self._add_point_sensors(simulation)

        self._setup_solver_settings(simulation)

        self._finalize_setup(simulation)
        self._log("Common settings applied.")

    def _add_point_sensors(self, simulation):
        """Adds point sensors at the corners of the simulation bounding box."""
        num_points = self.config.get_setting("simulation_parameters/simulation_bbox_points", 8)
        if num_points == 0:
            self._log("  - Skipping point sensor creation (0 points requested).")
            return

        sim_bbox_entity = next((e for e in self.model.AllEntities() if "far_field_simulation_bbox" in e.Name), None)
        if not sim_bbox_entity:
            self._log("  - WARNING: Could not find simulation bounding box to add point sensors.")
            return
        
        bbox_min, bbox_max = self.model.GetBoundingBox([sim_bbox_entity])
        corners = [
            (bbox_min[0], bbox_min[1], bbox_min[2]), (bbox_max[0], bbox_min[1], bbox_min[2]),
            (bbox_min[0], bbox_max[1], bbox_min[2]), (bbox_max[0], bbox_max[1], bbox_min[2]),
            (bbox_min[0], bbox_min[1], bbox_max[2]), (bbox_max[0], bbox_min[1], bbox_max[2]),
            (bbox_min[0], bbox_max[1], bbox_max[2]), (bbox_max[0], bbox_max[1], bbox_max[2])
        ]

        for i in range(min(num_points, 8)):
            corner = corners[i]
            point_entity_name = f"Point Sensor Entity {i+1}"
            
            # Check if the point sensor entity already exists
            existing_entity = next((e for e in self.model.AllEntities() if hasattr(e, 'Name') and e.Name == point_entity_name), None)
            
            if existing_entity:
                self._log(f"  - Point sensor '{point_entity_name}' already exists. Skipping creation.")
                continue

            point_entity = self.model.CreatePoint(self.model.Vec3(corner))
            point_entity.Name = point_entity_name
            point_sensor = self.emfdtd.PointSensorSettings()
            point_sensor.Name = f"Point Sensor {i+1}"
            simulation.Add(point_sensor, [point_entity])
            self._log(f"  - Added point sensor at {corner}")

    def _finalize_setup(self, simulation):
        """
        Gathers all necessary entities for a far-field simulation and calls the shared
        finalization method from the base class.
        """
        bbox_entity = next((e for e in self.model.AllEntities() if hasattr(e, 'Name') and e.Name == "far_field_simulation_bbox"), None)
        if not bbox_entity:
            raise RuntimeError("Could not find 'far_field_simulation_bbox' for voxelization.")

        import XCoreModeling
        phantom_entities = [e for e in self.model.AllEntities() if isinstance(e, XCoreModeling.TriangleMesh)]
        point_sensor_entities = [e for e in self.model.AllEntities() if "Point Sensor Entity" in e.Name]
        
        all_simulation_parts = phantom_entities + [bbox_entity] + point_sensor_entities
        
        super()._finalize_setup(simulation, all_simulation_parts)