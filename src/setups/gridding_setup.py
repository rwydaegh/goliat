import numpy as np

class GriddingSetup:
    def __init__(self, config, simulation, placement_name, antenna, verbose=True):
        self.config = config
        self.simulation = simulation
        self.placement_name = placement_name
        self.antenna = antenna
        self.verbose = verbose
        
        import s4l_v1.model
        import s4l_v1.simulation.emfdtd
        import s4l_v1.units

        self.model = s4l_v1.model
        self.emfdtd = s4l_v1.simulation.emfdtd
        self.units = s4l_v1.units

    def _log(self, message):
        if self.verbose:
            print(message)

    def setup_gridding(self, antenna_components):
        """
        Sets up the gridding for the simulation.
        """
        self._log("Setting up gridding...")
        sim_params = self.config.get_simulation_parameters()
        
        # Global gridding on simulation bounding box
        if self.simulation.Name.endswith("_freespace"):
            sim_bbox_name = "freespace_simulation_bbox"
        else:
            sim_bbox_name = f"{self.placement_name.lower()}_simulation_bbox"
        
        sim_bbox_entity = next((e for e in self.model.AllEntities() if hasattr(e, 'Name') and e.Name == sim_bbox_name), None)
        if not sim_bbox_entity:
            raise RuntimeError(f"Could not find simulation bounding box: '{sim_bbox_name}'")

        self.simulation.GlobalGridSettings.BoundingBox = self.model.GetBoundingBox([sim_bbox_entity])
        manual_grid_sim_bbox = self.simulation.AddManualGridSettings([sim_bbox_entity])
        global_grid_res = sim_params.get("global_gridding", 3.0)
        manual_grid_sim_bbox.MaxStep = np.array([global_grid_res] * 3), self.units.MilliMeters

        # Antenna-specific gridding
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
                        oriented_res = [res[1], res[0], res[2]]
                        oriented_geom_res = [geom_res[1], geom_res[0], geom_res[2]]
                    else:
                        oriented_res = res
                        oriented_geom_res = geom_res
                    
                    manual_grid = self.simulation.AddManualGridSettings(components_to_grid)
                    manual_grid.MaxStep = np.array(oriented_res), self.units.MilliMeters
                    manual_grid.Resolution = np.array(oriented_geom_res), self.units.MilliMeters
        else:
            source_entity = antenna_components[self.antenna.get_source_entity_name()]
            self.simulation.AddAutomaticGridSettings([source_entity])