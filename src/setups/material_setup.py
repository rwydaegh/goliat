import os
import time
from .base_setup import BaseSetup

class MaterialSetup(BaseSetup):
    def __init__(self, config, simulation, antenna, verbose_logger, progress_logger, free_space=False):
        super().__init__(config, verbose_logger, progress_logger)
        self.simulation = simulation
        self.antenna = antenna
        self.free_space = free_space
        
        import s4l_v1.materials.database
        import XCoreModeling

        self.database = s4l_v1.materials.database
        self.XCoreModeling = XCoreModeling

    def assign_materials(self, antenna_components=None, phantom_only=False):
        """
        Assigns materials to the simulation entities.
        """
        self._log("Assigning materials...", log_type='progress')
        
        # Background material
        background_settings = self.simulation.raw.BackgroundMaterialSettings()
        air_material = self.database["Generic 1.1"]["Air"]
        self.simulation.raw.AssignMaterial(background_settings, air_material)

        # Phantom materials
        if not self.free_space:
            self._assign_phantom_materials()

        # Antenna materials
        if not phantom_only:
            if not antenna_components:
                raise ValueError("antenna_components must be provided when not in phantom_only mode.")
            self._assign_antenna_materials(antenna_components)

    def _assign_phantom_materials(self):
        lock_file_path = os.path.join(self.config.base_dir, 'material_db.lock')

        # Acquire lock
        while True:
            try:
                # Use exclusive creation mode to atomically create the file
                with open(lock_file_path, 'x'):
                    break  # Lock acquired
            except FileExistsError:
                time.sleep(0.5)  # Wait before retrying

        try:
            all_entities = self.model.AllEntities()
            phantom_parts = [e for e in all_entities if isinstance(e, self.XCoreModeling.TriangleMesh)]
            
            phantom_name = self.config.get_setting("phantoms")[0]
            name_mapping = self.config.get_material_mapping(phantom_name)

            material_groups = {}
            for part in phantom_parts:
                base_name = part.Name.split('(')[0].strip()
                material_name = name_mapping.get(base_name, base_name.replace('_', ' '))
                material_groups.setdefault(material_name, []).append(part)

            for material_name, entities in material_groups.items():
                try:
                    mat = self.database["IT'IS 4.2"][material_name]
                    material_settings = self.emfdtd.MaterialSettings()
                    self.simulation.LinkMaterialWithDatabase(material_settings, mat)
                    self.simulation.Add(material_settings, entities)
                except KeyError:
                    self._log(f"    - Warning: Could not find material '{material_name}' in IT'IS 4.2 database.", log_type='warning')

        finally:
            # Release lock
            if os.path.exists(lock_file_path):
                os.remove(lock_file_path)

    def _assign_antenna_materials(self, antenna_components):
        antenna_config = self.antenna.get_config_for_frequency()
        material_mappings = antenna_config.get("materials", {})

        for comp_name, mat_name in material_mappings.items():
            if comp_name in antenna_components:
                entity = antenna_components[comp_name]
                material_settings = self.emfdtd.MaterialSettings()

                excitation_type = self.config.get_excitation_type()
                if "Copper" in mat_name and self.free_space and excitation_type.lower() == 'gaussian':
                    material_settings.Type = "PEC"
                    self.simulation.Add(material_settings, [entity])
                    self._log("\n" + "="*80, log_type='warning')
                    self._log(f"  WARNING: Forcing material for '{comp_name}' to PEC.", log_type='warning')
                    self._log("           This is a required workaround because Sim4Life does not yet support", log_type='warning')
                    self._log("           Gaussian excitation with dispersive materials like Copper.", log_type='warning')
                    self._log("="*80 + "\n", log_type='warning')
                elif mat_name.lower() == 'pec':
                    material_settings.Type = "PEC"
                    self.simulation.Add(material_settings, [entity])
                    self._log(f"  - Assigned 'PEC' to '{comp_name}'.", log_type='info')
                else:
                    try:
                        db_name = "IT'IS 4.2" if "Rogers" in mat_name else "Generic 1.1"
                        mat = self.database[db_name][mat_name]
                        self.simulation.LinkMaterialWithDatabase(material_settings, mat)
                        self.simulation.Add(material_settings, [entity])
                        self._log(f"  - Assigned '{mat_name}' to '{comp_name}'.", log_type='info')
                    except KeyError:
                        self._log(f"    - Warning: Could not find material '{mat_name}' in database.", log_type='warning')
            else:
                self._log(f"    - Warning: Could not find component '{comp_name}' to assign material.", log_type='warning')