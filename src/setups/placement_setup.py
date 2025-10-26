import os
from typing import TYPE_CHECKING

import numpy as np

from .base_setup import BaseSetup

if TYPE_CHECKING:
    from logging import Logger

    from ..antenna import Antenna
    from ..config import Config


class PlacementSetup(BaseSetup):
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

        import XCoreMath

        self.XCoreMath = XCoreMath

    def place_antenna(self):
        """Places and orients the antenna using a single composed transformation."""
        self._log(
            f"--- Starting Placement: {self.base_placement_name} - {self.position_name} - {self.orientation_name} ---",
            log_type="header",
        )

        phantom_definition = self.config.get_phantom_definition(self.phantom_name.lower())
        if not self.free_space and not phantom_definition.get("placements", {}).get(f"do_{self.base_placement_name}"):
            self._log(
                f"Placement '{self.base_placement_name}' is disabled in the configuration.",
                log_type="info",
            )
            return

        base_target_point, orientation_rotations, position_offset = self._get_placement_details()

        # Import antenna model
        antenna_path = self.antenna.get_centered_antenna_path(os.path.join(self.config.base_dir, "data", "antennas", "centered"))
        imported_entities = list(self.model.Import(antenna_path))

        antenna_group = next(
            (e for e in imported_entities if "Antenna" in e.Name and "bounding box" not in e.Name),
            None,
        )
        bbox_entity = next((e for e in imported_entities if "bounding box" in e.Name), None)

        if not antenna_group:
            raise RuntimeError("Could not find imported antenna group.")

        # Find the "Ground" entity/entities ("PCB" of the phone excl. IFA antenna)
        ground_entities = [e for e in antenna_group.Entities if "Ground" in e.Name or "Substrate" in e.Name]

        # Rename the entities to include the placement name for uniqueness
        antenna_group.Name = f"{antenna_group.Name} ({self.placement_name})"
        if bbox_entity:
            bbox_entity.Name = f"{bbox_entity.Name} ({self.placement_name})"

        entities_to_transform = [antenna_group, bbox_entity] if bbox_entity else [antenna_group]

        # --- Transformation Composition ---
        self._log("Composing final transformation...", log_type="progress")

        # Start with an identity transform
        final_transform = self.XCoreMath.Transform()

        # 1. Stand-up Rotation
        rot_stand_up = self.XCoreMath.Rotation(self.XCoreMath.Vec3(1, 0, 0), np.deg2rad(90))
        final_transform = rot_stand_up * final_transform

        # 2. Base translation to antenna reference point (speaker output of the mock-up phone)
        reference_target_point = self._get_speaker_reference(ground_entities, upright_transform=final_transform)
        base_translation = self.XCoreMath.Translation(reference_target_point)
        final_transform = base_translation * final_transform

        # Special rotation for 'by_cheek' to align with YZ plane
        if self.base_placement_name.startswith("by_cheek"):
            self._log("Applying 'by_cheek' specific Z-rotation.", log_type="info")
            rot_z_cheek = self.XCoreMath.Rotation(self.XCoreMath.Vec3(0, 0, 1), np.deg2rad(-90))
            final_transform = rot_z_cheek * final_transform

        # 3. Orientation Twist
        if orientation_rotations:
            for rot in orientation_rotations:
                axis_map = {
                    "X": self.XCoreMath.Vec3(1, 0, 0),
                    "Y": self.XCoreMath.Vec3(0, 1, 0),
                    "Z": self.XCoreMath.Vec3(0, 0, 1),
                }
                rot_twist = self.XCoreMath.Rotation(axis_map[rot["axis"].upper()], np.deg2rad(rot["angle_deg"]))
                final_transform = rot_twist * final_transform

        # 4. Final Translation
        final_target_point = self.model.Vec3(
            base_target_point[0] + position_offset[0],
            base_target_point[1] + position_offset[1],
            base_target_point[2] + position_offset[2],
        )
        translation_transform = self.XCoreMath.Translation(final_target_point)
        final_transform = translation_transform * final_transform

        # --- Apply the single, composed transform ---
        self._log("Applying final composed transform.", log_type="progress")
        for entity in entities_to_transform:
            entity.ApplyTransform(final_transform)

        # --- Target Rotation Feature ---
        scenario = self.config.get_placement_scenario(self.base_placement_name)
        target_rotation_config = scenario.get("target_rotation", {})
        
        if target_rotation_config.get("enabled", False) and not self.free_space:
            self._log("Applying target rotation feature...", log_type="header")
            self._apply_target_rotation(entities_to_transform, final_transform, target_rotation_config)

        self._log("--- Transformation Sequence Complete ---", log_type="success")

    def _get_placement_details(self) -> tuple:
        """Calculates the target point, offset, and orientation rotations."""
        if self.free_space:
            return self.model.Vec3(0, 0, 0), [], [0, 0, 0]

        scenario = self.config.get_placement_scenario(self.base_placement_name)
        if not scenario:
            raise ValueError(f"Placement scenario '{self.base_placement_name}' not defined.")

        position_offset = scenario["positions"].get(self.position_name, [0, 0, 0])
        orientation_rotations = scenario["orientations"].get(self.orientation_name, []).copy()

        all_entities = self.model.AllEntities()
        phantom_definition = self.config.get_phantom_definition(self.phantom_name.lower())
        placements_config = phantom_definition.get("placements", {})
        base_target_point = self.model.Vec3(0, 0, 0)

        if self.base_placement_name == "front_of_eyes":
            eye_entities = [e for e in all_entities if "Eye" in e.Name or "Cornea" in e.Name]
            if not eye_entities:
                raise ValueError("No eye or cornea entities found for 'Eyes' placement.")
            eye_bbox_min, eye_bbox_max = self.model.GetBoundingBox(eye_entities)
            distance = placements_config.get("distance_from_eye", 200)
            phantom_reference = scenario.get("phantom_reference", None)  # get name of phantom reference point from config
            vector_from_2D_eyes_center = placements_config.get(phantom_reference, [0, 0, 0])  # center of the belly by default
            base_target_point[0] = (eye_bbox_min[0] + eye_bbox_max[0]) / 2.0 + vector_from_2D_eyes_center[0]
            base_target_point[1] = eye_bbox_max[1] + vector_from_2D_eyes_center[1] + distance
            base_target_point[2] = (eye_bbox_min[2] + eye_bbox_max[2]) / 2.0 + vector_from_2D_eyes_center[2]

        elif self.base_placement_name.startswith("by_cheek"):
            # Find ear and mouth entities
            ear_skin = next(
                (e for e in all_entities if hasattr(e, "Name") and e.Name == "Ear_skin"),
                None,
            )

            lips_point = phantom_definition.get("lips")

            if not ear_skin or not lips_point:
                raise ValueError("Could not find 'Ear_skin' entity or 'lips' definition for 'Cheek' placement.")

            # Get center points
            ear_bbox_min, ear_bbox_max = self.model.GetBoundingBox([ear_skin])

            ear_center = self.XCoreMath.Vec3(
                (ear_bbox_min[0] + ear_bbox_max[0]) / 2.0,
                (ear_bbox_min[1] + ear_bbox_max[1]) / 2.0,
                (ear_bbox_min[2] + ear_bbox_max[2]) / 2.0,
            )
            mouth_center = self.XCoreMath.Vec3(lips_point[0], lips_point[1], lips_point[2])

            # Calculate angle for base alignment
            direction_vector = mouth_center - ear_center
            # Angle in YZ plane is rotation around X-axis
            angle_rad = np.arctan2(direction_vector[2], direction_vector[1])
            angle_deg = np.rad2deg(angle_rad)

            # The phone should be perpendicular to this line, so add 90 degrees
            base_rotation_deg = angle_deg + 90
            self._log(
                f"Calculated base rotation for cheek alignment: {base_rotation_deg:.2f} degrees around X-axis.",
                log_type="info",
            )

            # Add this as a new base rotation
            base_rotation = {"axis": "X", "angle_deg": base_rotation_deg}
            orientation_rotations.insert(0, base_rotation)

            # Set the target point based on the ear
            distance = placements_config.get("distance_from_cheek", 8)
            phantom_reference = scenario.get("phantom_reference", None)  # get name of phantom reference point from config
            vector_from_2D_ear_center = phantom_definition.get(phantom_reference, [0, 0, 0])  # center of the ear by default
            base_target_point[0] = ear_bbox_max[0] + vector_from_2D_ear_center[0] + distance
            base_target_point[1] = ear_center[1] + vector_from_2D_ear_center[1]
            base_target_point[2] = ear_center[2] + vector_from_2D_ear_center[2]

        elif self.base_placement_name == "by_belly":
            trunk_bbox_name = f"{self.phantom_name.lower()}_Trunk_BBox"
            trunk_bbox = next(
                (e for e in all_entities if hasattr(e, "Name") and e.Name == trunk_bbox_name),
                None,
            )
            if not trunk_bbox:
                raise ValueError(f"Could not find '{trunk_bbox_name}' entity for 'Belly' placement.")

            belly_bbox_min, belly_bbox_max = self.model.GetBoundingBox([trunk_bbox])
            distance = placements_config.get("distance_from_belly", 50)
            phantom_reference = scenario.get("phantom_reference", None)  # get name of phantom reference point from config
            vector_from_2D_belly_center = phantom_definition.get(phantom_reference, [0, 0, 0])  # center of the belly by default
            base_target_point[0] = (belly_bbox_min[0] + belly_bbox_max[0]) / 2.0 + vector_from_2D_belly_center[0]
            base_target_point[1] = belly_bbox_max[1] + vector_from_2D_belly_center[1] + distance
            base_target_point[2] = (belly_bbox_min[2] + belly_bbox_max[2]) / 2.0 + +vector_from_2D_belly_center[2]

        else:
            raise ValueError(f"Invalid base placement name: {self.base_placement_name}")

        return base_target_point, orientation_rotations, position_offset

    def _get_speaker_reference(self, ground_entities, upright_transform):
        """Function to find the speaker output reference location on the phone.
        CAUTION: only works when the mock-up phone is in upright position in XZ-plane ("Stand-up")
        after applying transform!
        """

        if not ground_entities:
            raise ValueError("No antenna 'Ground' entities found to calculate 'speaker' reference point.")

        # Get Ground/PCB bounding box
        ground_bbox_min, ground_bbox_max = self.model.GetBoundingBox(ground_entities, transform=upright_transform)

        # Find the speaker reference point
        scenario = self.config.get_placement_scenario(self.base_placement_name)
        distance_from_top = scenario["antenna_reference"].get("distance_from_top", 10)  # speaker at 10 mm from top by default
        reference_target_point = self.model.Vec3(
            (ground_bbox_min[0] + ground_bbox_max[0]) / 2.0,  # horizontal center of the phone
            (ground_bbox_min[1] + ground_bbox_max[1]) / 2.0,  # depth center of the phone
            -(
                ground_bbox_max[2] - distance_from_top
            ),  # distance_from_top below (vertical) top part of phone, negative for transform to that position
        )

        return reference_target_point

    def _apply_target_rotation(self, phone_entities, final_transform, target_rotation_config):
        """Rotate the Grid entity to align computational grid with the phone's orientation."""
        
        self._log("--- Target Rotation Feature ---", log_type="header")
        self._log("Rotating Grid entity to align with phone's orientation...", log_type="info")
    
        # Get the Grid entity that controls FDTD gridding
        grid_entity = self._get_grid_entity()
        
        if grid_entity:
            # Apply the phone's final transform directly to the Grid
            # Since Grid starts at origin (0,0,0), translation components shouldn't affect it
            # Only the rotation will take effect
            self._log(f"Applying transform to Grid:\n{final_transform.Matrix4}", log_type="verbose")
            
            grid_entity.ApplyTransform(final_transform)
            self._log(f"Successfully rotated Grid entity to align with phone orientation.", log_type="success")
            self._log("Phone remains in its original rotated position.", log_type="info")
            self._log("Computational grid is now aligned with phone's plane for efficient gridding.", log_type="success")
        else:
            self._log(f"Warning: Grid entity not found. Computational grid will not be rotated.", log_type="warning")
        
        self._log(f"Target rotation complete.", log_type="success")
    
    def _get_phantom_entities(self):
        """Get all phantom-related entities."""
        all_entities = self.model.AllEntities()
        phantom_entities = []
        phantom_name_lower = self.phantom_name.lower()
        
        for e in all_entities:
            if hasattr(e, "Name"):
                # Check if entity name contains the phantom name
                if phantom_name_lower in e.Name.lower():
                    phantom_entities.append(e)
        
        return phantom_entities

    def _get_bbox_entities(self):
        """Get all bounding box entities (excluding antenna bbox)."""
        all_entities = self.model.AllEntities()
        bbox_entities = []
        
        for e in all_entities:
            if hasattr(e, "Name"):
                # Include bbox entities but exclude antenna-specific bboxes
                if ("BBox" in e.Name or "bbox" in e.Name or "bounding box" in e.Name):
                    # Exclude antenna bounding boxes (already handled in phone_entities)
                    if self.placement_name not in e.Name:
                        bbox_entities.append(e)
        
        return bbox_entities

    def _get_sensor_entities(self):
        """Get all sensor entities."""
        all_entities = self.model.AllEntities()
        sensor_entities = []
        
        for e in all_entities:
            if hasattr(e, "Name"):
                if "Sensor" in e.Name or "sensor" in e.Name:
                    sensor_entities.append(e)
        
        return sensor_entities
    
    def _get_grid_entity(self):
        """Get the Grid entity that controls FDTD gridding in Sim4Life."""
        all_entities = self.model.AllEntities()
        
        for e in all_entities:
            if hasattr(e, "Name"):
                # In Sim4Life, the computational grid entity is typically named "Grid"
                if e.Name == "Grid":
                    return e
        
        return None
