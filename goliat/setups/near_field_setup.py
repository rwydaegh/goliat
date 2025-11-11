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
    from ..antenna import Antenna
    from ..config import Config
    from ..profiler import Profiler
    from ..project_manager import ProjectManager
    import s4l_v1.simulation.emfdtd as emfdtd


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
        profiler: "Profiler",
        gui=None,
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
        self.profiler = profiler
        self.gui = gui
        self.free_space = free_space

        # S4L modules
        import XCoreModeling

        self.document = self.s4l_v1.document
        self.XCoreModeling = XCoreModeling

    def run_full_setup(self, project_manager: "ProjectManager", lock=None) -> "emfdtd.Simulation":
        """Executes complete setup sequence with detailed timing.

        Orchestrates the entire simulation setup process in 6 major subtasks:

        1. Load phantom: Imports phantom model from disk or downloads if missing.
           Creates head/trunk bounding boxes if needed.

        2. Configure scene: Imports antenna, places it relative to phantom, creates
           simulation bounding box, sets up simulation entity, adds point sensors.
           Handles special cases like phantom rotation and phone alignment.

        3. Assign materials: Maps tissue names to IT'IS database materials, assigns
           antenna component materials from config. Uses file locking for thread safety.

        4. Configure solver: Sets up gridding (automatic or manual with subgrids),
           configures boundary conditions (PML), and sets up excitation sources.

        5. Voxelize: Runs automatic voxelization on all simulation entities, updates
           materials and grid, optionally exports material properties.

        6. Save project: Saves the .smash file to disk.

        Each subtask is profiled individually for accurate timing estimates. The method
        returns a fully configured simulation object ready to run.

        Args:
            project_manager: Project manager for saving operations.
            lock: Optional lock (currently unused, reserved for future use).

        Returns:
            Fully configured simulation object ready for execution.
        """
        self._log("Running full simulation setup...", log_type="progress")

        # Subtask 1: Load phantom
        if not self.free_space:
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
        self._log("    - Configure scene (bboxes, placement, simulation, sensors)...", level="progress", log_type="progress")
        with self.profiler.subtask("setup_configure_scene"):
            if not self.free_space:
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

            antenna_components = self._get_antenna_components()
            self._create_simulation_bbox()
            simulation = self._setup_simulation_entity()

            sim_bbox_name = f"{self.placement_name.lower()}_simulation_bbox"
            self._add_point_sensors(simulation, sim_bbox_name)

            self._handle_phantom_rotation(placement_setup)
            self._align_simulation_with_phone()

        elapsed = self.profiler.subtask_times["setup_configure_scene"][-1]
        self._log(f"      - Subtask 'setup_configure_scene' done in {elapsed:.2f}s", log_type="verbose")
        self._log(f"      - Done in {elapsed:.2f}s", level="progress", log_type="success")

        # Subtask 3: Assign materials
        self._log("    - Assign materials...", level="progress", log_type="progress")
        with self.profiler.subtask("setup_materials"):
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

        elapsed = self.profiler.subtask_times["setup_materials"][-1]
        self._log(f"      - Subtask 'setup_materials' done in {elapsed:.2f}s", log_type="verbose")
        self._log(f"      - Done in {elapsed:.2f}s", level="progress", log_type="success")

        # Subtask 4: Configure solver
        self._log("    - Configure solver (gridding, boundaries, sources)...", level="progress", log_type="progress")
        with self.profiler.subtask("setup_solver"):
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

        elapsed = self.profiler.subtask_times["setup_solver"][-1]
        self._log(f"      - Subtask 'setup_solver' done in {elapsed:.2f}s", log_type="verbose")
        self._log(f"      - Done in {elapsed:.2f}s", level="progress", log_type="success")

        # Subtask 5: Voxelize
        self._log("    - Voxelize simulation...", level="progress", log_type="progress")
        with self.profiler.subtask("setup_voxelize"):
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

        self._log("Full simulation setup complete.", log_type="success")
        return simulation

    def _align_simulation_with_phone(self):
        """Aligns entire scene with phone orientation for 'by_cheek' scenarios.

        For 'by_cheek' placements, the phone needs to be upright (vertical) to match
        real-world usage. This method rotates the entire simulation scene (phantom,
        bounding boxes, sensors) to align with the phone's upright orientation.

        The alignment works by:
        1. Finding reference entities on the phone (Ground/Substrate for PIFA, Battery
           for IFA) that define the phone's orientation
        2. Calculating a transform that makes the phone upright
        3. Applying that transform to all scene entities (phantom, bboxes, sensors)

        This is done AFTER phantom rotation (if any) but BEFORE final placement, ensuring
        the entire scene maintains correct relative geometry. Only transforms parent
        groups and bounding boxes, not individual tissues, to avoid double transformation.

        This method only runs for 'by_cheek' placements where phone orientation matters.
        """
        if self.base_placement_name != "by_cheek":
            return

        self._log("Aligning simulation scene with phone...", log_type="progress")

        from XCoreMath import Transform
        from QTech import Vec3

        model_type = self.antenna.get_model_type()
        if model_type == "PIFA":
            reference_entity_name = "component1:Substrate"
            target_entity_name = "component1:Battery"
        elif model_type == "IFA":
            reference_entity_name = "Ground"
            target_entity_name = "Battery"
        else:
            self._log(f"Antenna model type '{model_type}' not supported for alignment. Skipping.", log_type="warning")
            return

        all_entities = self.model.AllEntities()

        reference_entity = next((e for e in all_entities if hasattr(e, "Name") and e.Name == reference_entity_name), None)
        target_entity = next((e for e in all_entities if hasattr(e, "Name") and e.Name == target_entity_name), None)

        if not reference_entity or not target_entity:
            self._log(
                f"Could not find reference ('{reference_entity_name}') or target ('{target_entity_name}') entities. Skipping alignment.",
                log_type="warning",
            )
            return

        # Calculate the transformation matrix to make the phone upright, mimicking the script
        reference_transform = reference_entity.Transform
        original_target_transform = target_entity.Transform

        # Decompose the original transform
        target_rotation = original_target_transform.DecomposeRotation
        target_translation = original_target_transform.Translation

        if model_type == "PIFA":
            target_rotation[1] = 0
            target_rotation[2] = np.deg2rad(-90)
            target_translation[1] = 0
        else:  # IFA
            target_rotation[0] = 0
            target_rotation[1] = 0
            target_rotation[2] = 0
            target_translation[2] = 150

        # Create the new transform for the target entity
        upright_target_transform = Transform(Vec3(1, 1, 1), target_rotation, target_translation)

        # The Diff transform is calculated based on the new target transform and the original reference
        diff_transform = upright_target_transform * reference_transform.Inverse()

        # Apply the transformation to the specific parent groups and bounding boxes.
        # This prevents the double-transformation of children (e.g., individual tissues).

        # Find the main phantom group (e.g., 'Thelonious_6y_V6')
        phantom_group_name_lower = self.phantom_name.lower()
        phantom_group = next((e for e in all_entities if phantom_group_name_lower in e.Name.lower() and hasattr(e, "Entities")), None)

        # Find the main antenna group
        antenna_group = next((e for e in all_entities if e.Name.startswith("Antenna ") and hasattr(e, "Entities")), None)

        # Find all relevant bounding boxes
        sim_bbox = next((e for e in all_entities if e.Name.endswith("_simulation_bbox")), None)
        ant_bbox = next((e for e in all_entities if "Antenna bounding box" in e.Name), None)
        head_bbox = next((e for e in all_entities if e.Name.endswith("_Head_BBox")), None)
        trunk_bbox = next((e for e in all_entities if e.Name.endswith("_Trunk_BBox")), None)

        # Find all point sensor entities
        point_sensors = [e for e in all_entities if "Point Sensor Entity" in e.Name]

        entities_to_transform = [e for e in [phantom_group, antenna_group, sim_bbox, ant_bbox, head_bbox, trunk_bbox] if e]
        entities_to_transform.extend(point_sensors)

        if not phantom_group:
            self._log(
                f"Could not find phantom group containing '{phantom_group_name_lower}'. Phantom will not be rotated.", log_type="warning"
            )

        self._log(f"--- Applying transform to {len(entities_to_transform)} specific entities.", log_type="verbose")
        for entity in entities_to_transform:
            self._log(f"  - Re-aligning '{entity.Name}'", log_type="verbose")
            entity.ApplyTransform(diff_transform)

        self._log("Successfully aligned simulation scene.", log_type="success")

    def _get_antenna_components(self) -> dict:
        """Gets all antenna component entities as a name-to-entity dict."""

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
        for entity in antenna_group.Entities:  # type: ignore
            if hasattr(entity, "History") and "Union" in entity.History:
                flat_component_list.extend(entity.GetChildren())
            else:
                flat_component_list.append(entity)

        return {e.Name: e for e in flat_component_list}

    def _setup_bounding_boxes(self):
        """Creates head and trunk bounding boxes from phantom geometry."""
        self._log("Setting up bounding boxes...", log_type="progress")
        all_entities = self.model.AllEntities()

        phantom_config = (self.config["phantom_definitions"] or {}).get(self.phantom_name.lower(), {})
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
        """Creates main simulation bounding box based on placement scenario.

        For free-space, expands antenna bbox. For phantom, combines antenna
        bbox with head/trunk/whole-body bbox based on config.
        """
        if self.free_space:
            antenna_bbox_entity = next(
                (e for e in self.model.AllEntities() if hasattr(e, "Name") and "Antenna bounding box" in e.Name),
                None,
            )
            antenna_bbox_min, antenna_bbox_max = self.model.GetBoundingBox([antenna_bbox_entity])
            expansion = self.config["simulation_parameters.freespace_antenna_bbox_expansion_mm"]
            if expansion is None:
                expansion = [10, 10, 10]
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
            placement_scenario_config = (self.config["placement_scenarios"] or {}).get(self.base_placement_name) or {}
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

            if bounding_box_setting == "whole_body":
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
        """Creates and configures the EM-FDTD simulation entity."""
        self._log("Setting up simulation entity...", log_type="progress")

        if self.document.AllSimulations:
            for sim in list(self.document.AllSimulations):
                self.document.AllSimulations.Remove(sim)

        sim_name = f"EM_FDTD_{self.phantom_name}_{self.frequency_mhz}MHz_{self.placement_name}"
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

        sim_bbox_entity = next(
            (e for e in self.model.AllEntities() if hasattr(e, "Name") and e.Name == sim_bbox_name),
            None,
        )
        if not sim_bbox_entity:
            raise RuntimeError(f"Could not find simulation bounding box: '{sim_bbox_name}'")

        self._apply_simulation_time_and_termination(simulation, sim_bbox_entity, self.frequency_mhz)

        return simulation

    def _handle_phantom_rotation(self, placement_setup: "PlacementSetup"):
        """Rotates phantom to phone for 'by_cheek' if configured.

        Some 'by_cheek' orientations require the phantom to rotate to match the phone's
        position, creating a more natural contact scenario. This method handles that
        rotation.

        The process:
        1. Finds the touching angle using binary search (maximum safe rotation)
        2. Applies an optional offset from config (for fine-tuning)
        3. Rotates phantom, bboxes, and sensors around Z-axis
        4. Removes the rotation instruction from placement_setup to prevent the phone
           from also rotating (would cause double rotation)

        This ensures the phantom and phone maintain their relative positions correctly
        after the rotation is applied.

        Args:
            placement_setup: Placement setup instance. Its orientation_rotations list
                           will be modified to remove phantom rotation config.
        """
        if self.base_placement_name != "by_cheek":
            return

        scenario = (self.config["placement_scenarios"] or {}).get(self.base_placement_name) or {}
        orientation_config = scenario.get("orientations", {}).get(self.orientation_name)

        # Find the phantom rotation dictionary in the list
        phantom_rot_config = next(
            (item for item in orientation_config if isinstance(item, dict) and "rotate_phantom_to_cheek" in item), None
        )

        if not phantom_rot_config:
            self._log("Phantom rotation not enabled for this orientation.", log_type="info")
            return

        self._log("--- Handling Phantom Rotation ---", log_type="header")

        # Find touching angle and add offset
        touching_angle_deg = self._find_touching_angle()
        angle_offset_deg = phantom_rot_config.get("angle_offset_deg", 0)
        final_rotation_deg = touching_angle_deg + angle_offset_deg

        self._log(f"Determined touching angle: {touching_angle_deg:.2f} deg.", log_type="info")
        self._log(f"Applying offset of {angle_offset_deg:.2f} deg. Final rotation: {final_rotation_deg:.2f} deg.", log_type="info")

        # Create the rotation transform around the Z-axis
        import XCoreMath

        rotation = XCoreMath.Rotation(XCoreMath.Vec3(0, 0, 1), np.deg2rad(final_rotation_deg))

        # Get all entities that need to be rotated
        all_entities = self.model.AllEntities()
        phantom_group_name_lower = self.phantom_name.lower()
        phantom_group = next((e for e in all_entities if phantom_group_name_lower in e.Name.lower() and hasattr(e, "Entities")), None)
        sim_bbox = next((e for e in all_entities if e.Name.endswith("_simulation_bbox")), None)
        head_bbox = next((e for e in all_entities if e.Name.endswith("_Head_BBox")), None)
        trunk_bbox = next((e for e in all_entities if e.Name.endswith("_Trunk_BBox")), None)
        point_sensors = [e for e in all_entities if "Point Sensor Entity" in e.Name]

        entities_to_transform = [e for e in [phantom_group, sim_bbox, head_bbox, trunk_bbox] if e]
        entities_to_transform.extend(point_sensors)

        if not phantom_group:
            self._log(
                f"Could not find phantom group containing '{phantom_group_name_lower}'. Phantom will not be rotated.", log_type="warning"
            )

        self._log(f"--- Applying rotation to {len(entities_to_transform)} specific entities.", log_type="verbose")
        for entity in entities_to_transform:
            self._log(f"  - Rotating '{entity.Name}'", log_type="verbose")
            entity.ApplyTransform(rotation)

        self._log("Entities rotated successfully.", log_type="success")

        # Since the phantom is rotated, we remove the phantom rotation instruction
        # from the list to prevent the phone from being rotated by it.
        if phantom_rot_config in placement_setup.orientation_rotations:
            placement_setup.orientation_rotations.remove(phantom_rot_config)

    def _find_touching_angle(self) -> float:
        """Finds angle where phantom touches phone using binary search.

        For 'by_cheek' placements, the phantom needs to be rotated to touch the phone
        naturally. This method finds the maximum safe rotation angle before contact
        occurs, ensuring the phantom is positioned realistically without interpenetration.

        The algorithm uses binary search over a 0-30 degree range:
        - Tests rotation angles by applying transforms and checking distance
        - If distance > 0, angle is safe (phantom not touching), search higher
        - If distance <= 0, phantom is touching/intersecting, search lower
        - Continues until precision threshold (0.5°) is reached

        The returned angle is negative because it's used in a rotation transform that
        rotates the phantom TO the phone (negative rotation in the transform space).
        The .Inverse() call in the implementation compensates for this sign convention.

        Returns:
            Rotation angle in degrees (negative value). This is the last safe angle
            before contact, suitable for use in a rotation transform.
        """
        self._log("Finding touching angle using binary search...", log_type="progress")
        import XCoreMath

        all_entities = self.model.AllEntities()
        skin_entity = next((e for e in all_entities if hasattr(e, "Name") and "Skin" in e.Name), None)

        antenna_group = next((e for e in all_entities if e.Name.startswith("Antenna ") and hasattr(e, "Entities")), None)

        if not antenna_group:
            self._log("Could not find antenna group for distance check. Returning 0.", log_type="warning")
            return 0.0

        ground_entities = [e for e in antenna_group.Entities if "Ground" in e.Name or "Substrate" in e.Name]  # type: ignore

        if not skin_entity or not ground_entities:
            self._log("Could not find all necessary entities for distance check. Returning 0.", log_type="warning")
            return 0.0

        low_angle, high_angle = 0, 30  # Search space in degrees
        precision = 0.5
        last_safe_angle = 0

        while high_angle - low_angle > precision:
            mid_angle = (low_angle + high_angle) / 2

            # Apply rotation
            rotation = XCoreMath.Rotation(XCoreMath.Vec3(0, 0, 1), np.deg2rad(mid_angle))
            skin_entity.ApplyTransform(rotation.Inverse())  # This .Inverse() makes up for the minus sign in the return value

            # Check distance
            distance, _ = self.XCoreModeling.GetEntityEntityDistance(skin_entity, ground_entities[0])

            # Rotate back
            skin_entity.ApplyTransform(rotation)

            self._log(f"  - Angle: {mid_angle:.2f} deg, Distance: {distance.Distance:.4f} mm", log_type="verbose")

            if distance.Distance > 0:  # Not touching
                last_safe_angle = mid_angle
                low_angle = mid_angle
            else:  # Touching or intersecting
                high_angle = mid_angle

        return -last_safe_angle
