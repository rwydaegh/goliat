import numpy as np
from .base_setup import BaseSetup

class GriddingSetup(BaseSetup):
    def __init__(self, config, simulation, placement_name, antenna, verbose_logger, progress_logger, frequency_mhz=None):
        super().__init__(config, verbose_logger, progress_logger)
        self.simulation = simulation
        self.placement_name = placement_name
        self.antenna = antenna
        self.frequency_mhz = frequency_mhz
        
        import s4l_v1.units
        self.units = s4l_v1.units

    def setup_gridding(self, antenna_components=None):
        """
        Sets up the gridding for the simulation. If antenna_components are provided,
        it will also set up the subgrids for the antenna.
        """
        self._log("Setting up gridding...", level='verbose')
        self._setup_main_grid()
        if antenna_components:
            self._setup_subgrids(antenna_components)
        else:
            self._log("  - No antenna components provided, skipping subgridding.")

    def _setup_main_grid(self):
        """
        Sets up the main grid based on the overall simulation bounding box.
        """
        gridding_params = self.config.get_gridding_parameters()
        gridding_mode = gridding_params.get("gridding_mode", "manual")

        # Determine the name of the simulation bounding box
        if self.simulation.Name.endswith("_freespace"):
            sim_bbox_name = "freespace_simulation_bbox"
        elif self.placement_name:
            sim_bbox_name = f"{self.placement_name.lower()}_simulation_bbox"
        else:  # Far-field case
            sim_bbox_name = "far_field_simulation_bbox"

        # Find the bounding box entity
        self._log(f"  - Looking for global grid bounding box: '{sim_bbox_name}'")
        sim_bbox_entity = next((e for e in self.model.AllEntities() if hasattr(e, 'Name') and e.Name == sim_bbox_name), None)
        if not sim_bbox_entity:
            raise RuntimeError(f"Could not find simulation bounding box: '{sim_bbox_name}'")

        if gridding_mode == "automatic":
            self._log("  - Using automatic gridding.")
            auto_grid_settings = self.simulation.AddAutomaticGridSettings([sim_bbox_entity])
            
            # Set refinement based on config, with a default value
            refinement_level = gridding_params.get("refinement", "AutoRefinementDefault")
            auto_grid_settings.AutoRefinement = refinement_level
            
            self._log(f"  - Automatic gridding set with refinement level: {refinement_level}", level='verbose')

        elif gridding_mode == "manual":
            self._log("  - Using manual gridding.")
            manual_grid_sim_bbox = self.simulation.AddManualGridSettings([sim_bbox_entity])
            
            global_grid_res_mm = None
            log_source = "default"

            # Try to get per-frequency gridding first
            if self.frequency_mhz:
                per_freq_gridding = self.config.get_setting("gridding_parameters.global_gridding_per_frequency")
                if per_freq_gridding and isinstance(per_freq_gridding, dict):
                    freq_key = str(int(self.frequency_mhz))
                    if freq_key in per_freq_gridding:
                        global_grid_res_mm = per_freq_gridding[freq_key]
                        log_source = f"frequency-specific ({self.frequency_mhz}MHz)"

            # Fallback to global gridding if per-frequency is not found
            if global_grid_res_mm is None:
                global_grid_res_mm = self.config.get_setting("simulation_parameters.global_gridding", 5.0)
                log_source = "global"

            manual_grid_sim_bbox.MaxStep = (np.array([global_grid_res_mm] * 3), self.units.MilliMeters)
            self._log(f"  - Global grid set with {log_source} resolution: {global_grid_res_mm} mm.", level='verbose')
        else:
            raise ValueError(f"Unsupported gridding_mode: {gridding_mode}")

    def _setup_subgrids(self, antenna_components):
        # Antenna-specific gridding
        if not self.antenna:
            self._log("  - No antenna provided, skipping subgridding.")
            return

        antenna_config = self.antenna.get_config_for_frequency()
        gridding_config = antenna_config.get("gridding")
        if gridding_config:
            # Automatic settings
            automatic_components = [antenna_components[name] for name in gridding_config.get("automatic", []) if name in antenna_components]
            if automatic_components:
                self.simulation.AddAutomaticGridSettings(automatic_components)

            # Manual settings
            manual_grid_step = gridding_config.get("manual_grid_step", {})
            resolution = gridding_config.get("resolution", {})

            for grid_type, comp_names in gridding_config.get("manual", {}).items():
                components_to_grid = [antenna_components[name] for name in comp_names if name in antenna_components]
                
                if components_to_grid:
                    if grid_type in manual_grid_step:
                        res = manual_grid_step[grid_type]
                    else:
                        continue

                    geom_res = resolution.get(grid_type, [1.0, 1.0, 1.0])
                    
                    if self.placement_name == "by_cheek":
                        oriented_res = [res, res, res]
                        oriented_geom_res = [geom_res, geom_res, geom_res]
                    else:
                        oriented_res = res
                        oriented_geom_res = geom_res
                    
                    manual_grid = self.simulation.AddManualGridSettings(components_to_grid)
                    manual_grid.MaxStep = np.array(oriented_res), self.units.MilliMeters
                    manual_grid.Resolution = np.array(oriented_geom_res), self.units.MilliMeters
        else:
            source_entity = antenna_components[self.antenna.get_source_entity_name()]
            self.simulation.AddAutomaticGridSettings([source_entity])