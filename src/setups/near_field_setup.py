import os
import numpy as np

from .phantom_setup import PhantomSetup
from .placement_setup import PlacementSetup
from .gridding_setup import GriddingSetup
from .material_setup import MaterialSetup
from .source_setup import SourceSetup
from .base_setup import BaseSetup

class NearFieldSetup(BaseSetup):
    """
    Configures the entire simulation environment within Sim4Life by coordinating
    specialized setup modules.
    """
    def __init__(self, config, phantom_name, frequency_mhz, placement_name, antenna, verbose_logger, progress_logger, free_space=False):
        super().__init__(config, verbose_logger, progress_logger)
        self.phantom_name = phantom_name
        self.frequency_mhz = frequency_mhz
        self.placement_name = placement_name
        self.antenna = antenna
        self.free_space = free_space

        if placement_name.startswith('front_of_eyes'):
            self.base_placement_name = 'front_of_eyes'
        elif placement_name.startswith('by_cheek'):
            self.base_placement_name = 'by_cheek'
        elif placement_name.startswith('by_belly'):
            self.base_placement_name = 'by_belly'
        else:
            self.base_placement_name = placement_name
        
        # S4L modules
        import XCoreModeling
        self.document = self.s4l_v1.document
        self.XCoreModeling = XCoreModeling

    def run_full_setup(self, project_manager):
        """
        Executes the full sequence of setup steps.
        """
        self._log("Running full simulation setup...", 'progress')

        # Create or open the project file. This is the first step.
        project_manager.create_or_open_project(self.phantom_name, self.frequency_mhz, self.placement_name)
        
        if not self.free_space:
            phantom_setup = PhantomSetup(self.config, self.phantom_name, self.verbose_logger, self.progress_logger)
            phantom_setup.ensure_phantom_is_loaded()
            self._setup_bounding_boxes()

        placement_setup = PlacementSetup(self.config, self.phantom_name, self.frequency_mhz, self.placement_name, self.antenna, self.verbose_logger, self.progress_logger, self.free_space)
        placement_setup.place_antenna()

        self._create_simulation_bbox()

        simulation = self._setup_simulation_entity()
        
        antenna_components = self._get_antenna_components()

        material_setup = MaterialSetup(self.config, simulation, self.antenna, self.verbose_logger, self.progress_logger, self.free_space)
        material_setup.assign_materials(antenna_components)

        gridding_setup = GriddingSetup(self.config, simulation, self.placement_name, self.antenna, self.verbose_logger, self.progress_logger)
        gridding_setup.setup_gridding(antenna_components)

        source_setup = SourceSetup(self.config, simulation, self.frequency_mhz, self.antenna, self.verbose_logger, self.progress_logger, self.free_space)
        source_setup.setup_source_and_sensors(antenna_components)

        sim_bbox_name = f"{self.placement_name.lower()}_simulation_bbox"
        self._add_point_sensors(simulation, sim_bbox_name)

        self._finalize_setup(simulation, antenna_components)
        
        self._log("Full simulation setup complete.", 'progress')
        return simulation

    def _get_antenna_components(self):
        # The antenna group name changes during placement. We need to find it regardless of its state.
        # Initial name: "Antenna {freq} MHz"
        # Placed name:  "Antenna {freq} MHz (Placement)"
        
        placed_name = f"Antenna {self.frequency_mhz} MHz ({self.placement_name})"
        initial_name = f"Antenna {self.frequency_mhz} MHz"

        all_entities = self.model.AllEntities()
        
        antenna_group = next((e for e in all_entities if hasattr(e, 'Name') and e.Name == placed_name), None)
        if not antenna_group:
            antenna_group = next((e for e in all_entities if hasattr(e, 'Name') and e.Name == initial_name), None)

        if not antenna_group:
            raise RuntimeError(f"Could not find antenna group. Looked for '{placed_name}' and '{initial_name}'.")

        flat_component_list = []
        for entity in antenna_group.Entities:
            if hasattr(entity, 'History') and "Union" in entity.History:
                flat_component_list.extend(entity.GetChildren())
            else:
                flat_component_list.append(entity)
        
        return {e.Name: e for e in flat_component_list}

    def _setup_bounding_boxes(self):
        """
        Creates the head and trunk bounding boxes.
        """
        self._log("Setting up bounding boxes...", 'verbose')
        all_entities = self.model.AllEntities()
        
        phantom_config = self.config.get_phantom_config(self.phantom_name.lower())
        if not phantom_config:
            raise ValueError(f"Configuration for '{self.phantom_name.lower()}' not found.")

        head_bbox_name = f"{self.phantom_name.lower()}_Head_BBox"
        trunk_bbox_name = f"{self.phantom_name.lower()}_Trunk_BBox"
        
        entities_to_delete = [e for e in all_entities if hasattr(e, 'Name') and e.Name in [head_bbox_name, trunk_bbox_name]]
        for entity in entities_to_delete:
            self._log(f"  - Deleting existing entity: {entity.Name}", 'verbose')
            entity.Delete()
        
        all_entities = self.model.AllEntities()
        tissue_entities = [e for e in all_entities if isinstance(e, self.XCoreModeling.TriangleMesh)]
        bbox_min, bbox_max = self.model.GetBoundingBox(tissue_entities)

        # Head BBox
        ear_skin_entity = next((e for e in all_entities if hasattr(e, 'Name') and e.Name == "Ear_skin"), None)
        if not ear_skin_entity:
            head_x_min, head_x_max = bbox_min[0], bbox_max[0]
        else:
            ear_bbox_min, ear_bbox_max = self.model.GetBoundingBox([ear_skin_entity])
            head_x_min, head_x_max = ear_bbox_min[0], ear_bbox_max[0]
        
        head_y_sep = phantom_config['head_y_separation']
        back_of_head_y = phantom_config.get('back_of_head', bbox_min[1])
        head_bbox_min_vec = self.model.Vec3(head_x_min, back_of_head_y, head_y_sep)
        head_bbox_max_vec = self.model.Vec3(head_x_max, bbox_max[1], bbox_max[2])
        head_bbox = self.XCoreModeling.CreateWireBlock(head_bbox_min_vec, head_bbox_max_vec)
        head_bbox.Name = head_bbox_name
        self._log("  - Head BBox created.", 'verbose')

        # Trunk BBox
        trunk_z_sep = phantom_config['trunk_z_separation']
        chest_y_ext = phantom_config['chest_extension']
        trunk_bbox_min_vec = self.model.Vec3(bbox_min[0], bbox_min[1], trunk_z_sep)
        trunk_bbox_max_vec = self.model.Vec3(bbox_max[0], chest_y_ext, head_y_sep)
        trunk_bbox = self.XCoreModeling.CreateWireBlock(trunk_bbox_min_vec, trunk_bbox_max_vec)
        trunk_bbox.Name = trunk_bbox_name
        self._log("  - Trunk BBox created.", 'verbose')

    def _create_simulation_bbox(self):
        if self.free_space:
            antenna_bbox_entity = next((e for e in self.model.AllEntities() if hasattr(e, 'Name') and "Antenna bounding box" in e.Name), None)
            antenna_bbox_min, antenna_bbox_max = self.model.GetBoundingBox([antenna_bbox_entity])
            expansion = self.config.get_freespace_expansion()
            sim_bbox_min = np.array(antenna_bbox_min) - np.array(expansion)
            sim_bbox_max = np.array(antenna_bbox_max) + np.array(expansion)
            sim_bbox = self.XCoreModeling.CreateWireBlock(self.model.Vec3(sim_bbox_min), self.model.Vec3(sim_bbox_max))
            sim_bbox.Name = "freespace_simulation_bbox"
            self._log(f"  - Created free-space simulation BBox.", 'verbose')
        else:
            antenna_bbox_entity = next((e for e in self.model.AllEntities() if hasattr(e, 'Name') and "Antenna bounding box" in e.Name), None)
            if self.base_placement_name in ['front_of_eyes', 'by_cheek']:
                bbox_to_combine_name = f"{self.phantom_name.lower()}_Head_BBox"
            else:
                bbox_to_combine_name = f"{self.phantom_name.lower()}_Trunk_BBox"
            
            bbox_to_combine = self.model.AllEntities()[bbox_to_combine_name]
                
            combined_bbox_min, combined_bbox_max = self.model.GetBoundingBox([bbox_to_combine, antenna_bbox_entity])
            sim_bbox = self.XCoreModeling.CreateWireBlock(combined_bbox_min, combined_bbox_max)
            sim_bbox.Name = f"{self.placement_name.lower()}_simulation_bbox"
            self._log(f"  - Combined BBox created for {self.placement_name}.", 'verbose')

    def _setup_simulation_entity(self):
        """
        Creates and configures the base EM-FDTD simulation entity.
        """
        self._log("Setting up simulation entity...", 'verbose')
        
        if self.document.AllSimulations:
            for sim in list(self.document.AllSimulations):
                self.document.AllSimulations.Remove(sim)
        
        sim_name = f"EM_FDTD_{self.phantom_name}_{self.antenna.get_model_type()}_{self.placement_name}"
        if self.free_space:
            sim_name += "_freespace"
        simulation = self.emfdtd.Simulation()
        simulation.Name = sim_name
        
        import s4l_v1.units
        simulation.Frequency = self.frequency_mhz, s4l_v1.units.MHz

        self.document.AllSimulations.Add(simulation)
        
        self._setup_solver_settings(simulation)

        if self.free_space:
            sim_bbox_name = "freespace_simulation_bbox"
        else:
            sim_bbox_name = f"{self.placement_name.lower()}_simulation_bbox"
        
        sim_bbox_entity = next((e for e in self.model.AllEntities() if hasattr(e, 'Name') and e.Name == sim_bbox_name), None)
        if not sim_bbox_entity:
            raise RuntimeError(f"Could not find simulation bounding box: '{sim_bbox_name}'")

        self._apply_simulation_time_and_termination(simulation, sim_bbox_entity, self.frequency_mhz)
        
        return simulation

    def _finalize_setup(self, simulation, antenna_components):
        all_antenna_parts = list(antenna_components.values())
        point_sensor_entities = [e for e in self.model.AllEntities() if "Point Entity" in e.Name]

        if self.free_space:
            all_simulation_parts = all_antenna_parts + point_sensor_entities
        else:
            phantom_entities = [e for e in self.model.AllEntities() if isinstance(e, self.XCoreModeling.TriangleMesh)]
            all_simulation_parts = phantom_entities + all_antenna_parts + point_sensor_entities
        
        super()._finalize_setup(simulation, all_simulation_parts)