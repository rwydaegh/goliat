from typing import TYPE_CHECKING

import numpy as np

from .base_setup import BaseSetup
from .boundary_setup import BoundarySetup
from .gridding_setup import GriddingSetup
from .material_setup import MaterialSetup
from .phantom_setup import PhantomSetup
from .placement_setup import PlacementSetup
from .source_setup import SourceSetup

if TYPE_CHECKING:
    from logging import Logger

    import s4l_v1.simulation.emfdtd as emfdtd

    from ..antenna import Antenna
    from ..config import Config
    from ..project_manager import ProjectManager


class NearFieldSetup(BaseSetup):
    """Configures the simulation environment by coordinating setup modules."""

    def __init__(
        self,
        config: "Config",
        phantom_name: str,
        frequency_mhz: int,
        scenario_name: str,
        position_name: str,
        orientation_name: str,
        antenna: "Antenna",
        verbose_logger: "Logger",
        progress_logger: "Logger",
        free_space: bool = False,
    ):
        super().__init__(config, verbose_logger, progress_logger)
        self.phantom_name = phantom_name
        self.frequency_mhz = frequency_mhz
        self.base_placement_name = scenario_name
        self.position_name = position_name
        self.orientation_name = orientation_name
        self.placement_name = f"{scenario_name}_{position_name}_{orientation_name}"
        self.antenna = antenna
        self.free_space = free_space

        # S4L modules
        import XCoreModeling

        self.document = self.s4l_v1.document
        self.XCoreModeling = XCoreModeling

    def run_full_setup(self, project_manager: "ProjectManager", lock=None) -> "emfdtd.Simulation":
        """Executes the full sequence of setup steps."""
        self._log("Running full simulation setup...", log_type="progress")

        # The project is now created/opened by the study, not the setup.
        # This method assumes a valid project is already open.

        if not self.free_space:
            phantom_setup = PhantomSetup(
                self.config,
                self.phantom_name,
                self.verbose_logger,
                self.progress_logger,
            )
            phantom_setup.ensure_phantom_is_loaded()
            self._setup_bounding_boxes()

        placement_setup = PlacementSetup(
            self.config,
            self.phantom_name,
            self.frequency_mhz,
            self.base_placement_name,
            self.position_name,
            self.orientation_name,
            self.antenna,
            self.verbose_logger,
            self.progress_logger,
            self.free_space,
        )
        placement_setup.place_antenna()

        self._create_simulation_bbox()

        simulation = self._setup_simulation_entity()

        antenna_components = self._get_antenna_components()

        material_setup = MaterialSetup(
            self.config,
            simulation,
            self.antenna,
            self.phantom_name,
            self.verbose_logger,
            self.progress_logger,
            self.free_space,
        )
        material_setup.assign_materials(antenna_components)

        gridding_setup = GriddingSetup(
            self.config,
            simulation,
            self.placement_name,
            self.antenna,
            self.verbose_logger,
            self.progress_logger,
            frequency_mhz=self.frequency_mhz,
        )
        gridding_setup.setup_gridding(antenna_components)

        boundary_setup = BoundarySetup(self.config, simulation, self.verbose_logger, self.progress_logger)
        boundary_setup.setup_boundary_conditions()

        source_setup = SourceSetup(
            self.config,
            simulation,
            self.frequency_mhz,
            self.antenna,
            self.verbose_logger,
            self.progress_logger,
            self.free_space,
        )
        source_setup.setup_source_and_sensors(antenna_components)

        sim_bbox_name = f"{self.placement_name.lower()}_simulation_bbox"
        self._add_point_sensors(simulation, sim_bbox_name)

        all_antenna_parts = list(antenna_components.values())
        point_sensor_entities = [e for e in self.model.AllEntities() if "Point Sensor Entity" in e.Name]

        if self.free_space:
            sim_bbox_name = "freespace_simulation_bbox"
        else:
            sim_bbox_name = f"{self.placement_name.lower()}_simulation_bbox"

        sim_bbox_entity = next(
            (e for e in self.model.AllEntities() if hasattr(e, "Name") and e.Name == sim_bbox_name),
            None,
        )
        if not sim_bbox_entity:
            raise RuntimeError(f"Could not find simulation bounding box: '{sim_bbox_name}' for voxelization.")

        phantom_entities = [e for e in self.model.AllEntities() if isinstance(e, self.XCoreModeling.TriangleMesh)]
        all_simulation_parts = phantom_entities + all_antenna_parts + point_sensor_entities + [sim_bbox_entity]

        super()._finalize_setup(project_manager, simulation, all_simulation_parts, self.frequency_mhz)

        self._log("Full simulation setup complete.", log_type="success")
        return simulation

    def _get_antenna_components(self) -> dict:
        """Gets a dictionary of all antenna component entities."""

        placed_name = f"Antenna {self.frequency_mhz} MHz ({self.placement_name})"
        initial_name = f"Antenna {self.frequency_mhz} MHz"

        all_entities = self.model.AllEntities()

        antenna_group = next(
            (e for e in all_entities if hasattr(e, "Name") and e.Name == placed_name),
            None,
        )
        if not antenna_group:
            antenna_group = next(
                (e for e in all_entities if hasattr(e, "Name") and e.Name == initial_name),
                None,
            )

        if not antenna_group:
            raise RuntimeError(f"Could not find antenna group. Looked for '{placed_name}' and '{initial_name}'.")

        flat_component_list = []
        for entity in antenna_group.Entities:
            if hasattr(entity, "History") and "Union" in entity.History:
                flat_component_list.extend(entity.GetChildren())
            else:
                flat_component_list.append(entity)

        return {e.Name: e for e in flat_component_list}

    def _setup_bounding_boxes(self):
        """Creates the head and trunk bounding boxes."""
        self._log("Setting up bounding boxes...", log_type="progress")
        all_entities = self.model.AllEntities()

        phantom_config = self.config.get_phantom_definition(self.phantom_name.lower())
        if not phantom_config:
            raise ValueError(f"Configuration for '{self.phantom_name.lower()}' not found.")

        head_bbox_name = f"{self.phantom_name.lower()}_Head_BBox"
        trunk_bbox_name = f"{self.phantom_name.lower()}_Trunk_BBox"

        entities_to_delete = [e for e in all_entities if hasattr(e, "Name") and e.Name in [head_bbox_name, trunk_bbox_name]]
        for entity in entities_to_delete:
            self._log(f"  - Deleting existing entity: {entity.Name}", log_type="verbose")
            entity.Delete()

        all_entities = self.model.AllEntities()
        tissue_entities = [e for e in all_entities if isinstance(e, self.XCoreModeling.TriangleMesh)]
        bbox_min, bbox_max = self.model.GetBoundingBox(tissue_entities)

        # Head BBox
        ear_skin_entity = next(
            (e for e in all_entities if hasattr(e, "Name") and e.Name == "Ear_skin"),
            None,
        )
        if not ear_skin_entity:
            head_x_min, head_x_max = bbox_min[0], bbox_max[0]
        else:
            ear_bbox_min, ear_bbox_max = self.model.GetBoundingBox([ear_skin_entity])
            head_x_min, head_x_max = ear_bbox_min[0], ear_bbox_max[0]

        head_y_sep = phantom_config["head_y_separation"]
        back_of_head_y = phantom_config.get("back_of_head", bbox_min[1])
        head_bbox_min_vec = self.model.Vec3(head_x_min, back_of_head_y, head_y_sep)
        head_bbox_max_vec = self.model.Vec3(head_x_max, bbox_max[1], bbox_max[2])
        head_bbox = self.XCoreModeling.CreateWireBlock(head_bbox_min_vec, head_bbox_max_vec)
        head_bbox.Name = head_bbox_name
        self._log("  - Head BBox created.", log_type="info")

        # Trunk BBox
        trunk_z_sep = phantom_config["trunk_z_separation"]
        chest_y_ext = phantom_config["chest_extension"]
        trunk_bbox_min_vec = self.model.Vec3(bbox_min[0], bbox_min[1], trunk_z_sep)
        trunk_bbox_max_vec = self.model.Vec3(bbox_max[0], chest_y_ext, head_y_sep)
        trunk_bbox = self.XCoreModeling.CreateWireBlock(trunk_bbox_min_vec, trunk_bbox_max_vec)
        trunk_bbox.Name = trunk_bbox_name
        self._log("  - Trunk BBox created.", log_type="info")

    def _create_simulation_bbox(self):
        """Creates the main simulation bounding box."""
        if self.free_space:
            antenna_bbox_entity = next(
                (e for e in self.model.AllEntities() if hasattr(e, "Name") and "Antenna bounding box" in e.Name),
                None,
            )
            antenna_bbox_min, antenna_bbox_max = self.model.GetBoundingBox([antenna_bbox_entity])
            expansion = self.config.get_freespace_expansion()
            sim_bbox_min = np.array(antenna_bbox_min) - np.array(expansion)
            sim_bbox_max = np.array(antenna_bbox_max) + np.array(expansion)
            sim_bbox = self.XCoreModeling.CreateWireBlock(self.model.Vec3(sim_bbox_min), self.model.Vec3(sim_bbox_max))
            sim_bbox.Name = "freespace_simulation_bbox"
            self._log("  - Created free-space simulation BBox.", log_type="info")
        else:
            antenna_bbox_entity = next(
                (e for e in self.model.AllEntities() if hasattr(e, "Name") and "Antenna bounding box" in e.Name),
                None,
            )
            placement_scenario_config = self.config.get_placement_scenario(self.base_placement_name)
            bounding_box_setting = placement_scenario_config.get("bounding_box", "default")

            self._log(f"  - Bounding box setting: '{bounding_box_setting}'", log_type="info")

            # Warn user for unusual combinations
            if self.base_placement_name in ["front_of_eyes", "by_cheek"] and bounding_box_setting == "trunk":
                self._log(
                    (
                        f"WARNING: Using a 'trunk' bounding box for the '{self.base_placement_name}' "
                        "placement is unusual and may lead to unexpected results."
                    ),
                    log_type="warning",
                )
            if self.base_placement_name == "by_belly" and bounding_box_setting == "head":
                self._log(
                    (
                        f"WARNING: Using a 'head' bounding box for the '{self.base_placement_name}' "
                        "placement is unusual and may lead to unexpected results."
                    ),
                    log_type="warning",
                )

            entities_to_bound = [antenna_bbox_entity]

            if bounding_box_setting == "full_body":
                phantom_entities = [e for e in self.model.AllEntities() if isinstance(e, self.XCoreModeling.TriangleMesh)]
                entities_to_bound.extend(phantom_entities)
            else:
                bbox_map = {
                    "default_head": "Head_BBox",
                    "default_other": "Trunk_BBox",
                    "head": "Head_BBox",
                    "trunk": "Trunk_BBox",
                }

                key = bounding_box_setting
                if key == "default":
                    key = "default_head" if self.base_placement_name in ["front_of_eyes", "by_cheek"] else "default_other"

                if key in bbox_map:
                    bbox_name = f"{self.phantom_name.lower()}_{bbox_map[key]}"
                    entities_to_bound.append(self.model.AllEntities()[bbox_name])

            combined_bbox_min, combined_bbox_max = self.model.GetBoundingBox(entities_to_bound)
            sim_bbox = self.XCoreModeling.CreateWireBlock(combined_bbox_min, combined_bbox_max)
            sim_bbox.Name = f"{self.placement_name.lower()}_simulation_bbox"
            self._log(f"  - Combined BBox created for {self.placement_name}.", log_type="info")

    def _setup_simulation_entity(self) -> "emfdtd.Simulation":
        """Creates and configures the base EM-FDTD simulation entity."""
        self._log("Setting up simulation entity...", log_type="progress")

        if self.document.AllSimulations:  # type: ignore
            for sim in list(self.document.AllSimulations):  # type: ignore
                self.document.AllSimulations.Remove(sim)  # type: ignore

        sim_name = f"EM_FDTD_{self.phantom_name}_{self.frequency_mhz}MHz_{self.placement_name}"
        if self.free_space:
            sim_name += "_freespace"
        simulation = self.emfdtd.Simulation()
        simulation.Name = sim_name

        import s4l_v1.units

        simulation.Frequency = self.frequency_mhz, s4l_v1.units.MHz

        self.document.AllSimulations.Add(simulation)  # type: ignore

        self._setup_solver_settings(simulation)

        if self.free_space:
            sim_bbox_name = "freespace_simulation_bbox"
        else:
            sim_bbox_name = f"{self.placement_name.lower()}_simulation_bbox"

        sim_bbox_entity = next(
            (e for e in self.model.AllEntities() if hasattr(e, "Name") and e.Name == sim_bbox_name),
            None,
        )
        if not sim_bbox_entity:
            raise RuntimeError(f"Could not find simulation bounding box: '{sim_bbox_name}'")

        self._apply_simulation_time_and_termination(simulation, sim_bbox_entity, self.frequency_mhz)

        return simulation
