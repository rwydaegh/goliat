import os
import numpy as np
import json

from .antenna import Antenna
from .utils import ensure_s4l_running, open_project

class NearFieldProject:
    """
    Manages the setup, execution, and result extraction for a single near-field simulation.
    """
    def __init__(self, project_name, phantom_name, frequency_mhz, placement_name, config, verbose=True):
        self.project_name = project_name
        self.phantom_name = phantom_name
        self.frequency_mhz = frequency_mhz
        self.placement_name = placement_name
        self.config = config
        self.verbose = verbose
        self.antenna = Antenna(config, frequency_mhz)
        self.simulation = None
        
        # Ensure the results directory exists and set the project path
        results_dir = os.path.join(self.config.base_dir, 'results')
        os.makedirs(results_dir, exist_ok=True)
        self.project_path = os.path.join(results_dir, f"{self.project_name}.smash")
        
        # Defer S4L imports until after the application is running
        self._import_s4l_modules()

    def _log(self, message):
        if self.verbose:
            print(message)

    def _import_s4l_modules(self):
        """Imports Sim4Life modules and attaches them to the instance."""
        ensure_s4l_running()
        import s4l_v1
        import s4l_v1.document
        import s4l_v1.model
        import s4l_v1.simulation.emfdtd
        import s4l_v1.units
        import s4l_v1.materials.database
        import s4l_v1.data
        import s4l_v1.analysis
        import s4l_v1.analysis.em_evaluators
        import XCoreModeling

        self.s4l_v1 = s4l_v1
        self.document = s4l_v1.document
        self.model = s4l_v1.model
        self.emfdtd = s4l_v1.simulation.emfdtd
        self.units = s4l_v1.units
        self.database = s4l_v1.materials.database
        self.data = s4l_v1.data
        self.analysis = s4l_v1.analysis
        self.em_evaluators = s4l_v1.analysis.em_evaluators
        self.XCoreModeling = XCoreModeling

    def setup(self):
        """
        Sets up the entire simulation environment in Sim4Life.
        """
        open_project(self.project_path)
        self._ensure_phantom_is_loaded()
        self._setup_bounding_boxes()
        self._place_antenna()
        self._setup_simulation()
        self.save()

    def run(self):
        """
        Runs the simulation.
        """
        self._log(f"Running simulation for {self.project_name}...")
        if self.simulation:
            self.simulation.UpdateGrid()
            self.simulation.CreateVoxels()
            self.simulation.RunSimulation(wait=True)
            self._log("Simulation finished.")
        else:
            self._log(f"ERROR: Simulation object not found.")

    def extract_results(self):
        """
        Extracts and saves the simulation results.
        """
        self._log("Extracting results...")
        if not self.simulation:
            self._log("  - ERROR: Simulation object not found. Skipping result extraction.")
            return
        
        # Get the 'Overall Field' sensor from the simulation results
        # S4L returns a list, so we take the first one.
        overall_field_sensor = self.simulation.Results()['Overall Field'][0]
        if not overall_field_sensor:
            self._log("  - ERROR: Could not find 'Overall Field' sensor in simulation results.")
            return

        # Create a new SAR statistics evaluator
        sar_evaluator = self.em_evaluators.SarStatisticsEvaluator(overall_field_sensor)
        
        # Update the evaluator to compute the results
        sar_evaluator.Update()

        # Get the SAR result object from the evaluator's outputs
        sar_results = sar_evaluator.Outputs()['SAR Statistics']
        if not sar_results:
            self._log("  - ERROR: Could not find 'SAR Statistics' in evaluator outputs.")
            return
            
        # Get all available SAR values
        peak_sar_1g = sar_results.Data.GetMaximum(self.units.W_kg, averaging_mass=1.0)
        peak_sar_10g = sar_results.Data.GetMaximum(self.units.W_kg, averaging_mass=10.0)
        
        self._log(f"  - Peak SAR (1g): {peak_sar_1g:.4f} W/kg")
        self._log(f"  - Peak SAR (10g): {peak_sar_10g:.4f} W/kg")

        # Save results to a file
        results_dir = os.path.join(self.config.base_dir, 'results', self.phantom_name, f"{self.frequency_mhz}MHz", self.placement_name)
        os.makedirs(results_dir, exist_ok=True)
        
        results_data = {
            'peak_sar_1g_W_kg': peak_sar_1g,
            'peak_sar_10g_W_kg': peak_sar_10g
        }
        
        results_filepath = os.path.join(results_dir, 'sar_results.json')
        with open(results_filepath, 'w') as f:
            json.dump(results_data, f, indent=4)
        self._log(f"  - SAR results saved to: {results_filepath}")

    def save(self):
        """
        Saves the project to its file path.
        """
        self._log(f"Saving project to {self.project_path}...")
        self.document.SaveAs(self.project_path)
        self._log("Project saved.")

    def cleanup(self):
        """
        Closes the Sim4Life document.
        """
        self._log("Cleaning up and closing project...")
        self.document.Close()

    def _ensure_phantom_is_loaded(self):
        """
        Ensures the phantom model is loaded into the current document.
        """
        all_entities = self.model.AllEntities()
        if any(self.phantom_name.lower() in entity.Name.lower() for entity in all_entities if hasattr(entity, 'Name')):
            self._log("Phantom model is already present in the document.")
            return True

        sab_path = os.path.join(self.config.base_dir, 'data', 'phantoms', f"{self.phantom_name.capitalize()}.sab")
        if os.path.exists(sab_path):
            self._log(f"Phantom not found in document. Importing from '{sab_path}'...")
            self.XCoreModeling.Import(sab_path)
            self._log("Phantom imported successfully.")
            return True

        self._log(f"Local .sab file not found. Attempting to download '{self.phantom_name}'...")
        available_downloads = self.data.GetAvailableDownloads()
        phantom_to_download = next((item for item in available_downloads if self.phantom_name in item.Name), None)
        
        if not phantom_to_download:
            raise FileNotFoundError(f"Phantom '{self.phantom_name}' not found for download or in local files.")
        
        self._log(f"Found '{phantom_to_download.Name}'. Downloading...")
        self.data.DownloadModel(phantom_to_download, email="example@example.com", directory=os.path.join(self.config.base_dir, 'data', 'phantoms'))
        self._log("Phantom downloaded successfully. Please re-run the script to import the new .sab file.")
        return False

    def _setup_bounding_boxes(self):
        """
        Creates the head and trunk bounding boxes.
        """
        self._log("Setting up bounding boxes...")
        all_entities = self.model.AllEntities()
        
        phantom_config = self.config.get_phantom_config(self.phantom_name.lower())
        if not phantom_config:
            raise ValueError(f"Configuration for '{self.phantom_name.lower()}' not found.")

        # Clean up pre-existing bounding boxes and antenna placements
        head_bbox_name = f"{self.phantom_name.lower()}_Head_BBox"
        trunk_bbox_name = f"{self.phantom_name.lower()}_Trunk_BBox"
        sim_bbox_name = f"{self.placement_name.lower()}_simulation_bbox"
        antenna_group_name = f"Antenna {self.frequency_mhz} MHz ({self.placement_name})"
        antenna_bbox_name = f"Antenna bounding box ({self.placement_name})"

        entities_to_delete = [
            e for e in all_entities if hasattr(e, 'Name') and e.Name in [
                head_bbox_name,
                trunk_bbox_name,
                sim_bbox_name,
                antenna_group_name,
                antenna_bbox_name
            ]
        ]
        for entity in entities_to_delete:
            self._log(f"  - Deleting existing entity: {entity.Name}")
            entity.Delete()
        
        # Re-fetch entities after deletion
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
        self._log("  - Head BBox created.")

        # Trunk BBox
        trunk_z_sep = phantom_config['trunk_z_separation']
        chest_y_ext = phantom_config['chest_extension']
        trunk_bbox_min_vec = self.model.Vec3(bbox_min[0], bbox_min[1], trunk_z_sep)
        trunk_bbox_max_vec = self.model.Vec3(bbox_max[0], chest_y_ext, head_y_sep)
        trunk_bbox = self.XCoreModeling.CreateWireBlock(trunk_bbox_min_vec, trunk_bbox_max_vec)
        trunk_bbox.Name = trunk_bbox_name
        self._log("  - Trunk BBox created.")

    def _place_antenna(self):
        """
        Places and orients the antenna in the simulation environment.
        """
        self._log("Placing and orienting antenna...")
        
        placements_config = self.config.get_phantom_placements(self.phantom_name.lower())
        if not placements_config.get(f"do_{self.placement_name.lower()}"):
            self._log(f"Placement '{self.placement_name}' is disabled in the configuration.")
            return

        # Get target point based on placement
        target_point, rotations_deg = self._get_placement_details()

        # Import and transform antenna
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

        new_antenna_group.IsVisible = True
        if new_bbox_entity:
            new_bbox_entity.IsVisible = True

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

        # Add a final +90 degree rotation on X-axis for all placements
        rotation_vec_x = self.model.Vec3(np.deg2rad(90), 0, 0)
        transform_x = self.model.Transform(scale, rotation_vec_x, null_translation)
        for entity in entities_to_transform:
            entity.ApplyTransform(transform_x)

        # For the cheek placement, add an additional -90 degree Z rotation
        if self.placement_name == "by_cheek":
            rotation_vec_z = self.model.Vec3(0, 0, np.deg2rad(-90))
            transform_z = self.model.Transform(scale, rotation_vec_z, null_translation)
            for entity in entities_to_transform:
                entity.ApplyTransform(transform_z)

        translation_transform = self.XCoreModeling.Transform()
        translation_transform.Translation = target_point
        for entity in entities_to_transform:
            entity.ApplyTransform(translation_transform)
            
        # Create combined simulation bounding box
        if self.placement_name.lower() == 'front_of_eyes' or self.placement_name.lower() == 'by_cheek':
            bbox_to_combine_name = f"{self.phantom_name.lower()}_Head_BBox"
        else:
            bbox_to_combine_name = f"{self.phantom_name.lower()}_Trunk_BBox"
        
        bbox_to_combine = self.model.AllEntities()[bbox_to_combine_name]
            
        combined_bbox_min, combined_bbox_max = self.model.GetBoundingBox([bbox_to_combine, new_bbox_entity])
        sim_bbox = self.XCoreModeling.CreateWireBlock(combined_bbox_min, combined_bbox_max)
        sim_bbox.Name = f"{self.placement_name.lower()}_simulation_bbox"
        self._log(f"  - Combined BBox created for {self.placement_name}.")

    def _get_placement_details(self):
        """
        Returns the target point and rotations for a given placement.
        """
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

    def _setup_simulation(self):
        """
        Creates and configures the EM-FDTD simulation.
        """
        self._log("Setting up simulation...")
        
        all_entities = self.model.AllEntities()
        sim_params = self.config.get_simulation_parameters()
        grid_params = self.config.get_gridding_parameters()

        # --- Simulation Cleanup ---
        # Delete all existing simulations to ensure a clean state
        if self.document.AllSimulations:
            self._log(f"  - Deleting {len(self.document.AllSimulations)} existing simulation(s)...")
            # Iterate over a copy of the list as we are modifying it
            for sim in list(self.document.AllSimulations):
                self._log(f"    - Deleting: {sim.Name}")
                self.document.AllSimulations.Remove(sim)
        
        sim_name = f"EM_FDTD_{self.phantom_name}_{self.antenna.get_model_name()}_{self.placement_name}"

        # --- Create and Configure Simulation ---
        simulation = self.emfdtd.Simulation()
        simulation.Name = sim_name
        self.document.AllSimulations.Add(simulation)

        # Set Frequency and General Parameters
        # IMPORTANT: Frequency must be set *before* assigning materials for dispersive properties to be calculated correctly.
        simulation.Frequency = self.frequency_mhz, self.units.MHz
        
        # --- Set Solver Settings ---
        solver_settings = self.config.get_solver_settings()
        if solver_settings:
            kernel_type = solver_settings.get("kernel", "CUDA")
            # location = solver_settings.get("location", "localhost") # TODO: Implement location setting
            
            solver = simulation.SolverSettings
            kernel_enum = solver.Kernel.enum
            
            if hasattr(kernel_enum, kernel_type):
                solver.Kernel = getattr(kernel_enum, kernel_type)
                self._log(f"  - Solver kernel set to: {kernel_type}")
            else:
                self._log(f"  - Warning: Invalid solver kernel '{kernel_type}' specified. Using default.")

        sim_time = sim_params.get("simulation_time_periods", 15)
        term_level = sim_params.get("global_auto_termination", "Medium")
        simulation.SetupSettings.SimulationTime = sim_time, self.units.Periods
        term_options = simulation.SetupSettings.GlobalAutoTermination.enum
        if hasattr(term_options, f"GlobalAutoTermination{term_level}"):
            simulation.SetupSettings.GlobalAutoTermination = getattr(term_options, f"GlobalAutoTermination{term_level}")

        # Set Background Material
        background_settings = simulation.raw.BackgroundMaterialSettings()
        try:
            air_material = self.database["Generic 1.1"]["Air"]
        except KeyError:
            raise RuntimeError("Could not find 'Air' in the 'Generic 1.1' material database.")
        simulation.raw.AssignMaterial(background_settings, air_material)

        # Set Phantom Materials
        # This logic assumes that the only TriangleMesh entities present are the phantom parts.
        # This is safe because the antenna model does not use TriangleMesh objects.
        phantom_parts = [e for e in all_entities if isinstance(e, self.XCoreModeling.TriangleMesh)]
        if not phantom_parts:
            raise RuntimeError("ERROR: No TriangleMesh parts could be found in the project.")
        
        material_groups = {}
        name_mapping = self.config.get_material_mapping()
        for part in phantom_parts:
            base_name = part.Name.split('(')[0].strip()
            material_name = name_mapping.get(base_name, base_name.replace('_', ' '))
            if material_name not in material_groups:
                material_groups[material_name] = []
            material_groups[material_name].append(part)

        successful_assignments = 0
        for material_name, entities in material_groups.items():
            material_settings = self.emfdtd.MaterialSettings()
            try:
                mat = self.database["IT'IS 4.2"][material_name]
                simulation.LinkMaterialWithDatabase(material_settings, mat)
                simulation.Add(material_settings, entities)
                successful_assignments += len(entities)
            except KeyError:
                self._log(f"    - Warning: Could not find material '{material_name}' in IT'IS 4.2 database.")
        self._log(f"  - Assigned materials for {successful_assignments}/{len(phantom_parts)} parts.")

        # Set Antenna Source & Materials
        self._log("  - Setting antenna source and materials...")
        antenna_group_name = f"Antenna {self.frequency_mhz} MHz ({self.placement_name})"
        antenna_group = next((e for e in all_entities if hasattr(e, 'Name') and e.Name == antenna_group_name), None)
        if not antenna_group:
            raise RuntimeError(f"Could not find antenna group: {antenna_group_name}")
        
        self._log(f"    - Found antenna group: '{antenna_group.Name}'")
        
        source_entity_name = self.antenna.get_source_entity_name()
        
        # Define and validate all required components
        antenna_model_name = self.antenna.get_model_name()
        component_names = self.config.get_antenna_component_names(antenna_model_name)
        if not component_names:
            raise ValueError(f"No component names defined for antenna model '{antenna_model_name}' in simulation_config.json")

        components = {}
        for key, name in component_names.items():
            entity = next((e for e in antenna_group.Entities if e.Name == name), None)
            if not entity:
                # Also search top-level entities for PIFA parts
                entity = next((e for e in all_entities if e.Name == name), None)

            if not entity:
                raise RuntimeError(f"Could not find required antenna component '{name}' for model '{antenna_model_name}'")
            
            components[key] = entity
            self._log(f"      - Found component: {key} ('{name}')")

        source_entity = components["source"]
        antenna_entity = components["antenna"]
        battery_entity = components["battery"]
        ground_entity = components["ground"]

        antenna_bodies = [e for e in [antenna_entity, battery_entity, ground_entity] if isinstance(e, self.model.Body)]
        if antenna_bodies:
            material_settings = self.emfdtd.MaterialSettings()
            try:
                mat = self.database["Generic 1.1"]["Copper"]
                simulation.LinkMaterialWithDatabase(material_settings, mat)
                simulation.Add(material_settings, antenna_bodies)
            except KeyError:
                self._log("    - Warning: Could not find 'Copper' in 'Generic 1.1' database.")

        edge_source_settings = self.emfdtd.EdgeSourceSettings()
        edge_source_settings.CenterFrequency = self.frequency_mhz, self.units.MHz
        edge_source_settings.Bandwidth = self.frequency_mhz, self.units.MHz
        simulation.Add(edge_source_settings, [source_entity])

        # Define Gridding
        ant_fine_grid = grid_params.get("antenna_fine_grid", 0.3)
        bat_fine_grid = grid_params.get("battery_ground_fine_grid", 0.3)
        bat_coarse_grid = grid_params.get("battery_ground_coarse_grid", 1.0)
        
        sim_bbox_entity = self.model.AllEntities()[f"{self.placement_name.lower()}_simulation_bbox"]
        simulation.GlobalGridSettings.BoundingBox = self.model.GetBoundingBox([sim_bbox_entity])
        manual_grid_sim_bbox = simulation.AddManualGridSettings([sim_bbox_entity])
        manual_grid_sim_bbox.MaxStep = np.array([1, 1, 1]), self.units.MilliMeters

        auto_grid_settings = simulation.AddAutomaticGridSettings([source_entity])
        manual_grid_antenna = simulation.AddManualGridSettings([antenna_entity])
        manual_grid_antenna.MaxStep = np.array([ant_fine_grid] * 3), self.units.MilliMeters

        if self.placement_name.lower() == 'cheek':
            battery_grid_res = np.array([bat_fine_grid, bat_coarse_grid, bat_coarse_grid])
        else:
            battery_grid_res = np.array([bat_coarse_grid, bat_fine_grid, bat_coarse_grid])
        
        manual_grid_battery = simulation.AddManualGridSettings([battery_entity, ground_entity])
        manual_grid_battery.MaxStep = battery_grid_res, self.units.MilliMeters

        # Define Sensors
        edge_sensor_settings = self.emfdtd.EdgeSensorSettings()
        simulation.Add(edge_sensor_settings, [source_entity])

        # Voxelization Settings
        voxeler_settings = self.emfdtd.AutomaticVoxelerSettings()
        core_antenna_parts = [antenna_entity, battery_entity, source_entity, ground_entity]
        all_simulation_parts = phantom_parts + core_antenna_parts
        simulation.Add(voxeler_settings, all_simulation_parts)

        # Update all material properties to reflect the new simulation frequency
        self._log("  - Updating all material properties for the new frequency...")
        
        # Temporarily suppress verbose log output during material update
        import XCore
        
        self._log("    - Suppressing engine log for material update...")
        old_log_level = XCore.SetLogLevel(XCore.eLogCategory.Nothing)
        
        simulation.UpdateAllMaterials()
        
        # Restore the original log level
        XCore.SetLogLevel(old_log_level)
        self._log("    - Restored engine log level.")

        self.simulation = simulation
        self._log("Simulation setup complete.")