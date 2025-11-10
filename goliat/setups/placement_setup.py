import os
from typing import TYPE_CHECKING

import numpy as np

from .base_setup import BaseSetup

if TYPE_CHECKING:
    from logging import Logger

    from ..antenna import Antenna
    from ..config import Config


class PlacementSetup(BaseSetup):
    """Handles antenna placement and orientation relative to phantom.

    Imports antenna model, calculates target position based on placement scenario,
    and applies composed transformation (stand-up rotation, translation, orientation
    twists) to position antenna correctly.
    """

    def __init__(
        self,
        config: "Config",
        phantom_name: str,
        frequency_mhz: int,
        base_placement_name: str,
        position_name: str,
        orientation_name: str,
        antenna: "Antenna",
        verbose_logger: "Logger",
        progress_logger: "Logger",
        free_space: bool = False,
    ):
        """Initializes the PlacementSetup.

        Args:
            config: Configuration object.
            phantom_name: Name of the phantom model.
            frequency_mhz: Simulation frequency in MHz.
            base_placement_name: Base name of the placement scenario.
            position_name: Name of the position within the scenario.
            orientation_name: Name of the orientation within the scenario.
            antenna: Antenna object to place.
            verbose_logger: Logger for detailed output.
            progress_logger: Logger for progress updates.
            free_space: Whether this is a free-space simulation.
        """
        super().__init__(config, verbose_logger, progress_logger)
        self.phantom_name = phantom_name
        self.frequency_mhz = frequency_mhz
        self.base_placement_name = base_placement_name
        self.position_name = position_name
        self.orientation_name = orientation_name
        self.placement_name = f"{base_placement_name}_{position_name}_{orientation_name}"
        self.antenna = antenna
        self.free_space = free_space

        # Import XCoreMath for transformations
        import XCoreMath

        self.XCoreMath = XCoreMath

    def place_antenna(self):
        """Places and orients antenna using a single composed transformation.

        This method implements a key optimization: instead of applying multiple
        transforms sequentially (which causes precision loss and can accumulate errors),
        it composes all transformations into a single matrix and applies it once.

        The transformation sequence is:
        1. Stand-up rotation: Rotates antenna 90° around X-axis to make it upright
        2. Base translation: Moves antenna to a reference point (speaker location)
        3. Special rotation: For 'by_cheek', applies -90° Z-rotation to align with YZ plane
        4. Orientation twists: Applies any rotations specified in orientation config
        5. Final translation: Moves antenna to its target position relative to phantom

        The order matters because matrix multiplication is not commutative. Each step
        builds on the previous transform, so the antenna ends up correctly positioned
        and oriented relative to the phantom regardless of how many rotations are needed.

        Args:
            None (uses instance attributes: antenna, placement_name, etc.)

        Raises:
            RuntimeError: If antenna import fails or required entities aren't found.
        """
        self._log(
            f"--- Starting Placement: {self.base_placement_name} - {self.position_name} - {self.orientation_name} ---",
            log_type="header",
        )

        phantom_definition = (self.config["phantom_definitions"] or {}).get(self.phantom_name.lower(), {})
        if not self.free_space and not phantom_definition.get("placements", {}).get(f"do_{self.base_placement_name}"):
            self._log(
                f"Placement '{self.base_placement_name}' is disabled in the configuration.",
                log_type="info",
            )
            return

        base_target_point, position_offset = self._get_placement_details()

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
        ground_entities = [e for e in antenna_group.Entities if "Ground" in e.Name or "Substrate" in e.Name]  # type: ignore

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
        if self.orientation_rotations:
            for rot in self.orientation_rotations:
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

        self._log("--- Transformation Sequence Complete ---", log_type="success")

    def _get_placement_details(self) -> tuple:
        """Calculates target point, position offset, and orientation rotations.

        Determines where the antenna should be placed based on the placement scenario.
        Different scenarios use different anatomical landmarks:

        - 'front_of_eyes': Places antenna centered horizontally on eyes, positioned
          at a distance in front of them. Uses eye bounding box center.

        - 'by_cheek': Places antenna near the ear, aligned along the ear-to-mouth
          line. Calculates rotation angle dynamically based on ear and lip positions,
          then positions antenna at specified distance from ear.

        - 'by_belly': Places antenna centered on trunk bounding box, positioned
          at a distance above the belly.

        Also extracts orientation rotations from config. These can be either:
        - A dict (phantom rotation config) - phone doesn't rotate
        - A list of rotation dicts - phone rotates according to config

        Returns:
            Tuple of (base_target_point Vec3, position_offset list).
            base_target_point is the calculated anatomical reference point.
            position_offset is additional offset from config for fine-tuning.
        """
        if self.free_space:
            return self.model.Vec3(0, 0, 0), [0, 0, 0]

        scenario = (self.config["placement_scenarios"] or {}).get(self.base_placement_name)
        if not scenario:
            raise ValueError(f"Placement scenario '{self.base_placement_name}' not defined.")

        position_offset = scenario["positions"].get(self.position_name, [0, 0, 0])

        orientation_config = scenario["orientations"].get(self.orientation_name, [])
        if isinstance(orientation_config, dict):
            # New phantom rotation config, phone does not rotate
            self.orientation_rotations = []
        else:
            # It's a list, which could be a mix of phantom rotation dicts
            # and phone rotation dicts. Filter for actual rotation dicts.
            self.orientation_rotations = [
                rot for rot in orientation_config if isinstance(rot, dict) and "axis" in rot and "angle_deg" in rot
            ]

        all_entities = self.model.AllEntities()
        phantom_definition = (self.config["phantom_definitions"] or {}).get(self.phantom_name.lower(), {})
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
            self.orientation_rotations.insert(0, base_rotation)

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

        return base_target_point, position_offset

    def _get_speaker_reference(self, ground_entities, upright_transform):
        """Finds speaker reference point on phone for placement.

        The speaker reference point is a standardized location on the phone (typically
        near the top edge) that serves as the anchor for antenna placement. This ensures
        consistent positioning across different phone models.

        The method works by:
        1. Getting the bounding box of the Ground/Substrate entities (the PCB)
        2. Finding the horizontal center (X and Y)
        3. Calculating a point that's 'distance_from_top' millimeters below the top
           edge (negative Z direction because phone is upright)

        This reference point is used in the transformation chain as the initial
        translation target before applying orientation-specific rotations and final
        placement translation.

        Args:
            ground_entities: List of Ground/Substrate entities (the phone PCB).
            upright_transform: Transform that makes phone upright (needed for
                              bounding box calculation).

        Returns:
            Vec3 reference point for antenna placement. This point is in the phone's
            local coordinate system after the upright transform is applied.

        Raises:
            ValueError: If no Ground entities are found.
        """

        if not ground_entities:
            raise ValueError("No antenna 'Ground' entities found to calculate 'speaker' reference point.")

        # Get Ground/PCB bounding box
        ground_bbox_min, ground_bbox_max = self.model.GetBoundingBox(ground_entities, transform=upright_transform)

        # Find the speaker reference point
        scenario = (self.config["placement_scenarios"] or {}).get(self.base_placement_name) or {}
        distance_from_top = scenario.get("antenna_reference", {}).get("distance_from_top", 10)  # speaker at 10 mm from top by default
        reference_target_point = self.model.Vec3(
            (ground_bbox_min[0] + ground_bbox_max[0]) / 2.0,  # horizontal center of the phone
            (ground_bbox_min[1] + ground_bbox_max[1]) / 2.0,  # depth center of the phone
            -(
                ground_bbox_max[2] - distance_from_top
            ),  # distance_from_top below (vertical) top part of phone, negative for transform to that position
        )

        return reference_target_point
