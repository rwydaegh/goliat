import os
import numpy as np

class PlacementSetup:
    def __init__(self, config, phantom_name, frequency_mhz, placement_name, antenna, verbose=True, free_space=False):
        self.config = config
        self.phantom_name = phantom_name
        self.frequency_mhz = frequency_mhz
        self.placement_name = placement_name
        self.antenna = antenna
        self.verbose = verbose
        self.free_space = free_space

        # Parse the detailed placement name, e.g., "front_of_eyes_center_vertical"
        try:
            parts = placement_name.split('_')
            if placement_name.startswith('front_of_eyes'):
                self.base_placement_name = 'front_of_eyes'
                self.position_name = parts[3]
                self.orientation_name = parts[4]
            elif placement_name.startswith('by_cheek_tilt'):
                self.base_placement_name = 'by_cheek_tilt'
                self.position_name = parts[3]
                self.orientation_name = parts[4]
            elif placement_name.startswith('by_cheek'):
                self.base_placement_name = 'by_cheek'
                self.position_name = parts[2]
                self.orientation_name = parts[3]
            elif placement_name.startswith('by_belly'):
                self.base_placement_name = 'by_belly'
                self.position_name = parts[2]
                self.orientation_name = parts[3]
            else:
                # Fallback for old single placement names or unknown format
                self.base_placement_name = placement_name
                self.position_name = "default"
                self.orientation_name = "default"

        except IndexError:
            # Fallback for old single placement names
            self.base_placement_name = placement_name
            self.position_name = "default"
            self.orientation_name = "default"
        
        import s4l_v1.model
        import XCoreModeling
        import XCoreMath

        self.model = s4l_v1.model
        self.XCoreModeling = XCoreModeling
        self.XCoreMath = XCoreMath

    def _log(self, message):
        if self.verbose:
            print(message)

    def place_antenna(self):
        """
        Places and orients the antenna by composing a single transformation matrix
        and applying it once.
        """
        self._log(f"--- Starting Placement: {self.base_placement_name} - {self.position_name} - {self.orientation_name} ---")

        placements_config = self.config.get_phantom_placements(self.phantom_name.lower())
        if not self.free_space and not placements_config.get(f"do_{self.base_placement_name}"):
            self._log(f"Placement '{self.base_placement_name}' is disabled in the configuration.")
            return

        base_target_point, orientation_rotations, position_offset = self._get_placement_details()

        # Import antenna model
        antenna_path = self.antenna.get_centered_antenna_path(os.path.join(self.config.base_dir, 'data', 'antennas', 'centered'))
        imported_entities = list(self.model.Import(antenna_path))
        
        antenna_group = next((e for e in imported_entities if "Antenna" in e.Name and "bounding box" not in e.Name), None)
        bbox_entity = next((e for e in imported_entities if "bounding box" in e.Name), None)
        
        if not antenna_group:
            raise RuntimeError("Could not find imported antenna group.")
        
        # Rename the entities to include the placement name for uniqueness
        antenna_group.Name = f"{antenna_group.Name} ({self.placement_name})"
        if bbox_entity:
            bbox_entity.Name = f"{bbox_entity.Name} ({self.placement_name})"

        entities_to_transform = [antenna_group, bbox_entity] if bbox_entity else [antenna_group]

        # --- Transformation Composition ---
        self._log("Composing final transformation...")
        
        # Start with an identity transform
        final_transform = self.XCoreMath.Transform()

        # 1. Stand-up Rotation
        rot_stand_up = self.XCoreMath.Rotation(self.XCoreMath.Vec3(1, 0, 0), np.deg2rad(90))
        final_transform = rot_stand_up * final_transform

        # Special rotation for 'by_cheek' to align with YZ plane
        if self.base_placement_name.startswith('by_cheek'):
            self._log("Applying 'by_cheek' specific Z-rotation.")
            rot_z_cheek = self.XCoreMath.Rotation(self.XCoreMath.Vec3(0, 0, 1), np.deg2rad(-90))
            final_transform = rot_z_cheek * final_transform

        # 2. Orientation Twist
        if orientation_rotations:
            for rot in orientation_rotations:
                axis_map = {'X': self.XCoreMath.Vec3(1,0,0), 'Y': self.XCoreMath.Vec3(0,1,0), 'Z': self.XCoreMath.Vec3(0,0,1)}
                rot_twist = self.XCoreMath.Rotation(axis_map[rot['axis'].upper()], np.deg2rad(rot['angle_deg']))
                final_transform = rot_twist * final_transform

        # 3. Final Translation
        final_target_point = self.model.Vec3(
            base_target_point[0] + position_offset[0],
            base_target_point[1] + position_offset[1],
            base_target_point[2] + position_offset[2]
        )
        translation_transform = self.XCoreMath.Translation(final_target_point)
        final_transform = translation_transform * final_transform

        # --- Apply the single, composed transform ---
        self._log("Applying final composed transform.")
        for entity in entities_to_transform:
            entity.ApplyTransform(final_transform)
        
        self._log("--- Transformation Sequence Complete ---")

    def _get_placement_details(self):
        """
        Calculates the base target point, position offset, and orientation rotations.
        """
        if self.free_space:
            return self.model.Vec3(0, 0, 0), [], [0, 0, 0]

        scenario = self.config.get_placement_scenario(self.base_placement_name)
        if not scenario:
            raise ValueError(f"Placement scenario '{self.base_placement_name}' not defined.")

        if self.base_placement_name.startswith('by_cheek'):
            position_offset = [0, 0, 0]
        else:
            position_offset = scenario['positions'].get(self.position_name, [0, 0, 0])
        orientation_rotations = scenario['orientations'].get(self.orientation_name, [])
        
        all_entities = self.model.AllEntities()
        placements_config = self.config.get_phantom_placements(self.phantom_name.lower())
        base_target_point = self.model.Vec3(0, 0, 0)

        if self.base_placement_name == 'front_of_eyes':
            eye_entities = [e for e in all_entities if 'Eye' in e.Name or 'Cornea' in e.Name]
            if not eye_entities:
                raise ValueError("No eye or cornea entities found for 'Eyes' placement.")
            eye_bbox_min, eye_bbox_max = self.model.GetBoundingBox(eye_entities)
            distance = placements_config.get('distance_from_eye', 200)
            base_target_point[0] = (eye_bbox_min[0] + eye_bbox_max[0]) / 2.0
            base_target_point[1] = eye_bbox_max[1] + distance
            base_target_point[2] = (eye_bbox_min[2] + eye_bbox_max[2]) / 2.0

        elif self.base_placement_name.startswith('by_cheek'):
            # Find ear and mouth entities
            ear_skin = next((e for e in all_entities if hasattr(e, 'Name') and e.Name == "Ear_skin"), None)
            mouth_entity = next((e for e in all_entities if hasattr(e, 'Name') and e.Name == "Tongue"), None)
            if not ear_skin or not mouth_entity:
                raise ValueError("Could not find 'Ear_skin' or 'Tongue' entities for 'Cheek' placement.")

            # Get center points
            ear_bbox_min, ear_bbox_max = self.model.GetBoundingBox([ear_skin])
            mouth_bbox_min, mouth_bbox_max = self.model.GetBoundingBox([mouth_entity])
            
            ear_center = self.XCoreMath.Vec3(
                (ear_bbox_min[0] + ear_bbox_max[0]) / 2.0,
                (ear_bbox_min[1] + ear_bbox_max[1]) / 2.0,
                (ear_bbox_min[2] + ear_bbox_max[2]) / 2.0
            )
            mouth_center = self.XCoreMath.Vec3(
                (mouth_bbox_min[0] + mouth_bbox_max[0]) / 2.0,
                (mouth_bbox_min[1] + mouth_bbox_max[1]) / 2.0,
                (mouth_bbox_min[2] + mouth_bbox_max[2]) / 2.0
            )

            # Calculate angle for base alignment
            direction_vector = mouth_center - ear_center
            # Angle in YZ plane is rotation around X-axis
            angle_rad = np.arctan2(direction_vector[2], direction_vector[1])
            angle_deg = np.rad2deg(angle_rad)

            # The phone should be perpendicular to this line, so add 90 degrees
            base_rotation_deg = angle_deg + 90
            self._log(f"Calculated base rotation for cheek alignment: {base_rotation_deg:.2f} degrees around X-axis.")

            # Add this as a new base rotation
            base_rotation = {"axis": "X", "angle_deg": base_rotation_deg}
            orientation_rotations.insert(0, base_rotation)

            # Set the target point based on the ear
            distance = placements_config.get('distance_from_cheek', 8)
            base_target_point[0] = ear_bbox_max[0] + distance
            base_target_point[1] = ear_center[1]
            base_target_point[2] = ear_center[2]
        
        elif self.base_placement_name == 'by_belly':
            trunk_bbox_name = f"{self.phantom_name.lower()}_Trunk_BBox"
            trunk_bbox = next((e for e in all_entities if hasattr(e, 'Name') and e.Name == trunk_bbox_name), None)
            if not trunk_bbox:
                raise ValueError(f"Could not find '{trunk_bbox_name}' entity for 'Belly' placement.")
            
            belly_bbox_min, belly_bbox_max = self.model.GetBoundingBox([trunk_bbox])
            distance = placements_config.get('distance_from_belly', 50)
            
            base_target_point[0] = (belly_bbox_min[0] + belly_bbox_max[0]) / 2.0
            base_target_point[1] = belly_bbox_max[1] + distance
            base_target_point[2] = (belly_bbox_min[2] + belly_bbox_max[2]) / 2.0
        
        else:
            raise ValueError(f"Invalid base placement name: {self.base_placement_name}")

        return base_target_point, orientation_rotations, position_offset