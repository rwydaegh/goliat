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
        
        import s4l_v1.model
        import XCoreModeling

        self.model = s4l_v1.model
        self.XCoreModeling = XCoreModeling

    def _log(self, message):
        if self.verbose:
            print(message)

    def place_antenna(self):
        """
        Places and orients the antenna in the simulation environment.
        """
        self._log("Placing and orienting antenna...")
        
        placements_config = self.config.get_phantom_placements(self.phantom_name.lower())
        if not self.free_space and not placements_config.get(f"do_{self.placement_name.lower()}"):
            self._log(f"Placement '{self.placement_name}' is disabled in the configuration.")
            return

        target_point, rotations_deg = self._get_placement_details()

        antenna_path = self.antenna.get_centered_antenna_path(os.path.join(self.config.base_dir, 'data', 'antennas', 'centered'))
        if not os.path.exists(antenna_path):
            raise FileNotFoundError(f"Antenna file not found at: {antenna_path}")

        imported_entities = list(self.model.Import(antenna_path))
        
        antenna_group_orig_name = f"Antenna {self.frequency_mhz} MHz"
        new_antenna_group = next((e for e in imported_entities if hasattr(e, 'Name') and e.Name == antenna_group_orig_name), None)
        new_bbox_entity = next((e for e in imported_entities if hasattr(e, 'Name') and e.Name == "Antenna bounding box"), None)

        if not new_antenna_group:
            raise ValueError(f"Could not find antenna group '{antenna_group_orig_name}' in newly imported entities.")

        new_antenna_group.Name = f"{antenna_group_orig_name} ({self.placement_name})"
        if new_bbox_entity:
            new_bbox_entity.Name = f"Antenna bounding box ({self.placement_name})"

        entities_to_transform = [new_antenna_group]
        if new_bbox_entity:
            entities_to_transform.append(new_bbox_entity)

        scale = self.model.Vec3(1, 1, 1)
        null_translation = self.model.Vec3(0, 0, 0)

        for axis, angle_deg in rotations_deg:
            rotation_vec = self.model.Vec3(0, 0, 0)
            if axis.upper() == 'X':
                rotation_vec.X = np.deg2rad(angle_deg)
            elif axis.upper() == 'Y':
                rotation_vec.Y = np.deg2rad(angle_deg)
            elif axis.upper() == 'Z':
                rotation_vec.Z = np.deg2rad(angle_deg)
            
            transform = self.model.Transform(scale, rotation_vec, null_translation)
            for entity in entities_to_transform:
                entity.ApplyTransform(transform)

        rotation_vec_x = self.model.Vec3(np.deg2rad(90), 0, 0)
        transform_x = self.model.Transform(scale, rotation_vec_x, null_translation)
        for entity in entities_to_transform:
            entity.ApplyTransform(transform_x)

        if self.placement_name == "by_cheek":
            rotation_vec_z = self.model.Vec3(0, 0, np.deg2rad(-90))
            transform_z = self.model.Transform(scale, rotation_vec_z, null_translation)
            for entity in entities_to_transform:
                entity.ApplyTransform(transform_z)

        translation_transform = self.XCoreModeling.Transform()
        translation_transform.Translation = target_point
        for entity in entities_to_transform:
            entity.ApplyTransform(translation_transform)

    def _get_placement_details(self):
        """
        Returns the target point and rotations for a given placement.
        """
        if self.free_space:
            self._log("  - Free-space mode: Placing antenna at origin.")
            return self.model.Vec3(0, 0, 0), [('X', 90), ('Y', 180)]

        all_entities = self.model.AllEntities()
        placements_config = self.config.get_phantom_placements(self.phantom_name.lower())
        
        upright_rotations = [('X', 90), ('Y', 180)]
        cheek_rotations = [('X', 90), ('Y', 180), ('Z', 90)]

        if self.placement_name.lower() == 'front_of_eyes':
            eye_entities = [e for e in all_entities if 'Eye' in e.Name or 'Cornea' in e.Name]
            if not eye_entities:
                raise ValueError("No eye or cornea entities found for 'Eyes' placement.")
            eye_bbox_min, eye_bbox_max = self.model.GetBoundingBox(eye_entities)
            distance = placements_config.get('distance_from_eye', 100)
            center_x = (eye_bbox_min[0] + eye_bbox_max[0]) / 2.0
            center_z = (eye_bbox_min[2] + eye_bbox_max[2]) / 2.0
            target_y = eye_bbox_max[1] + distance
            return self.model.Vec3(center_x, target_y, center_z), upright_rotations
        
        elif self.placement_name.lower() == 'front_of_belly':
            trunk_bbox = self.model.AllEntities()[f"{self.phantom_name.lower()}_Trunk_BBox"]
            trunk_bbox_min, trunk_bbox_max = self.model.GetBoundingBox([trunk_bbox])
            distance = placements_config.get('distance_from_belly', 100)
            center_x = (trunk_bbox_min[0] + trunk_bbox_max[0]) / 2.0
            center_z = (trunk_bbox_min[2] + trunk_bbox_max[2]) / 2.0
            target_y = trunk_bbox_max[1] + distance
            return self.model.Vec3(center_x, target_y, center_z), upright_rotations

        elif self.placement_name.lower() == 'by_cheek':
            ear_skin_entity = next((e for e in all_entities if hasattr(e, 'Name') and e.Name == "Ear_skin"), None)
            if not ear_skin_entity:
                raise ValueError("Could not find 'Ear_skin' entity for 'Cheek' placement.")
            ear_bbox_min, ear_bbox_max = self.model.GetBoundingBox([ear_skin_entity])
            distance = placements_config.get('distance_from_cheek', 15)
            center_y = (ear_bbox_min[1] + ear_bbox_max[1]) / 2.0
            center_z = (ear_bbox_min[2] + ear_bbox_max[2]) / 2.0
            target_x = ear_bbox_max[0] + distance
            return self.model.Vec3(target_x, center_y, center_z), cheek_rotations
        
        else:
            raise ValueError(f"Invalid placement name: {self.placement_name}")