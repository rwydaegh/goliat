import numpy as np
import logging
import os
import pickle

class BaseSetup:
    """
    Abstract base class for all simulation setups (Near-Field, Far-Field).
    """
    def __init__(self, config, verbose_logger, progress_logger):
        """
        Initializes the base setup.
        
        Args:
            config (Config): The configuration object for the study.
            verbose_logger (logging.Logger): Logger for verbose output.
            progress_logger (logging.Logger): Logger for progress updates.
        """
        self.config = config
        self.verbose_logger = verbose_logger
        self.progress_logger = progress_logger
        import s4l_v1
        self.s4l_v1 = s4l_v1
        self.emfdtd = self.s4l_v1.simulation.emfdtd
        self.model = self.s4l_v1.model

    def _log(self, message, level='verbose'):
        """
        Logs a message to the appropriate logger.
        """
        if level == 'progress':
            self.progress_logger.info(message)
        else:
            self.verbose_logger.info(message)

    def _apply_simulation_time_and_termination(self, simulation, sim_bbox_entity, frequency_mhz):
        """
        Calculates and applies simulation time and termination settings.
        This is a shared method for both Near-Field and Far-Field setups.
        """
        sim_params = self.config.get_simulation_parameters()
        
        # Time Calculation
        time_multiplier = sim_params.get("simulation_time_multiplier", 5)
        self._log(f"  - Using simulation time multiplier: {time_multiplier}")
        
        bbox_min, bbox_max = self.model.GetBoundingBox([sim_bbox_entity])
        diagonal_length_m = np.linalg.norm(np.array(bbox_max) - np.array(bbox_min)) / 1000.0
        
        time_to_travel_s = (time_multiplier * diagonal_length_m) / 299792458
        sim_time_periods = time_to_travel_s / (1 / (frequency_mhz * 1e6))
        simulation.SetupSettings.SimulationTime = sim_time_periods, self.s4l_v1.units.Periods
        self._log(f"  - Simulation time set to {sim_time_periods:.2f} periods.")

        # Termination Criteria
        term_level = sim_params.get("global_auto_termination", "GlobalAutoTerminationWeak")
        self._log(f"  - Setting termination criteria to: {term_level}")
        term_options = simulation.SetupSettings.GlobalAutoTermination.enum
        if hasattr(term_options, term_level):
            simulation.SetupSettings.GlobalAutoTermination = getattr(term_options, term_level)
        
        if term_level == "GlobalAutoTerminationUserDefined":
            convergence_db = sim_params.get("convergence_level_dB", -30)
            simulation.SetupSettings.ConvergenceLevel = convergence_db
            self._log(f"    - Convergence level set to: {convergence_db} dB")

    def _setup_solver_settings(self, simulation):
        """ Configures solver settings, including kernel and boundary conditions. """
        self._log("  - Configuring solver settings...")
        solver_settings = self.config.get_solver_settings()
        if not solver_settings:
            return

        solver = simulation.SolverSettings

        # Setup Kernel
        kernel_type = solver_settings.get("kernel", "CUDA").lower()
        
        if kernel_type == "acceleware":
            solver.Kernel = solver.Kernel.enum.AXware
            self._log(f"    - Solver kernel set to: AXware")
        elif kernel_type == "cuda":
            solver.Kernel = solver.Kernel.enum.Cuda
            self._log(f"    - Solver kernel set to: Cuda")
        else:
            self._log(f"    - Warning: Unknown solver kernel '{kernel_type}'. Using default (Software).", level='progress')

        # Setup Boundary Conditions
        excitation_type = self.config.get_excitation_type()
        
        if excitation_type.lower() == 'gaussian':
            bc_type = "UpmlCpml"
            self._log("  - Gaussian source detected, forcing boundary condition to UpmlCpml.")
        else:
            boundary_config = solver_settings.get("boundary_conditions", {})
            bc_type = boundary_config.get("type", "UpmlCpml")

        self._log(f"    - Setting global boundary conditions to: {bc_type}")
        
        global_boundaries = simulation.GlobalBoundarySettings
        if global_boundaries:
            bc_enum = global_boundaries.GlobalBoundaryType.enum
            if hasattr(bc_enum, bc_type):
                global_boundaries.GlobalBoundaryType = getattr(bc_enum, bc_type)
                self._log(f"      - Successfully set GlobalBoundaryType to {bc_type}")
            else:
                self._log(f"      - Warning: Invalid boundary condition type '{bc_type}'. Using default.")
        else:
            self._log("      - Warning: 'GlobalBoundarySettings' not found on simulation object.")

    def run_full_setup(self, project_manager):
        """
        This method must be implemented by subclasses to prepare the simulation scene.
        
        Args:
            project_manager (ProjectManager): The project manager to handle file operations.
        
        Returns:
            The main simulation object.
        """
        raise NotImplementedError("The 'run_full_setup' method must be implemented by a subclass.")

    def _add_point_sensors(self, simulation, sim_bbox_entity_name):
        """Adds point sensors at the corners of the simulation bounding box."""
        num_points = self.config.get_setting("simulation_parameters/number_of_point_sources", 0)
        if num_points == 0:
            self._log("  - Skipping point sensor creation (0 points requested).")
            return

        sim_bbox_entity = next((e for e in self.model.AllEntities() if sim_bbox_entity_name in e.Name), None)
        if not sim_bbox_entity:
            self._log(f"  - WARNING: Could not find simulation bounding box '{sim_bbox_entity_name}' to add point sensors.")
            return
        
        bbox_min, bbox_max = self.model.GetBoundingBox([sim_bbox_entity])
        
        corner_map = {
            "lower_left_bottom": (bbox_min, bbox_min, bbox_min),
            "lower_right_bottom": (bbox_max, bbox_min, bbox_min),
            "lower_left_up": (bbox_min, bbox_max, bbox_min),
            "lower_right_up": (bbox_max, bbox_max, bbox_min),
            "top_left_bottom": (bbox_min, bbox_min, bbox_max),
            "top_right_bottom": (bbox_max, bbox_min, bbox_max),
            "top_left_up": (bbox_min, bbox_max, bbox_max),
            "top_right_up": (bbox_max, bbox_max, bbox_max)
        }

        point_source_order = self.config.get_setting("simulation_parameters/point_source_order", list(corner_map.keys()))
        
        for i in range(num_points):
            corner_name = point_source_order[i]
            corner_coords = corner_map.get(corner_name)
            if corner_coords is None:
                self._log(f"  - WARNING: Invalid corner name '{corner_name}' in point_source_order. Skipping.")
                continue

            point_entity_name = f"Point Sensor Entity {i+1} ({corner_name})"
            
            existing_entity = next((e for e in self.model.AllEntities() if hasattr(e, 'Name') and e.Name == point_entity_name), None)
            
            if existing_entity:
                self._log(f"  - Point sensor '{point_entity_name}' already exists. Skipping creation.")
                continue

            point_entity = self.model.CreatePoint(self.model.Vec3(corner_coords))
            point_entity.Name = point_entity_name
            point_sensor = self.emfdtd.PointSensorSettings()
            point_sensor.Name = f"Point Sensor {i+1}"
            simulation.Add(point_sensor, [point_entity])
            self._log(f"  - Added point sensor at {corner_coords} ({corner_name})")

    def _finalize_setup(self, simulation, all_simulation_parts, frequency_mhz):
        """
        Performs the final voxelization and grid update for a simulation.
        This is a shared method for both Near-Field and Far-Field setups.
        """
        self._log("    - Finalizing setup...")
        
        voxeler_settings = self.emfdtd.AutomaticVoxelerSettings()
        simulation.Add(voxeler_settings, all_simulation_parts)

        import XCore
        old_log_level = XCore.SetLogLevel(XCore.eLogCategory.Nothing)
        simulation.UpdateAllMaterials()
        XCore.SetLogLevel(old_log_level)

        if self.config.get_setting('export_material_properties'):
            self._log("--- Extracting Material Properties ---", level='progress')
            material_properties = []
            for settings in simulation.AllSettings:
                if isinstance(settings, self.emfdtd.MaterialSettings):
                    try:
                        self._log(f"  - Material: '{settings.Name}'")
                        self._log(f"    - Relative Permittivity: {settings.ElectricProps.RelativePermittivity:.4f}")
                        self._log(f"    - Electric Conductivity (S/m): {settings.ElectricProps.Conductivity:.4f}")
                        self._log(f"    - Mass Density (kg/m^3): {settings.MassDensity:.2f}")
                        material_properties.append({
                            'Name': settings.Name,
                            'RelativePermittivity': settings.ElectricProps.RelativePermittivity,
                            'Conductivity': settings.ElectricProps.Conductivity,
                            'MassDensity': settings.MassDensity
                        })
                    except Exception as e:
                        self._log(f"    - Could not extract properties for '{settings.Name}': {e}")
            self._log("--- Finished Extracting Material Properties ---", level='progress')

            output_dir = "analysis/cpw/data"
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
            output_path = os.path.join(output_dir, f"material_properties_{frequency_mhz}.pkl")
            with open(output_path, 'wb') as f:
                pickle.dump(material_properties, f)
            self._log(f"--- Exported Material Properties to {output_path} ---", level='progress')

        simulation.UpdateGrid()
        simulation.CreateVoxels()
        self._log("    - Finalizing setup complete.")
