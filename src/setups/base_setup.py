import numpy as np

class BaseSetup:
    """
    Abstract base class for all simulation setups (Near-Field, Far-Field).
    """
    def __init__(self, config, verbose=True):
        """
        Initializes the base setup.
        
        Args:
            config (Config): The configuration object for the study.
            verbose (bool): Flag to enable/disable detailed logging.
        """
        self.config = config
        self.verbose = verbose
        import s4l_v1
        self.s4l_v1 = s4l_v1
        self.emfdtd = self.s4l_v1.simulation.emfdtd
        self.model = self.s4l_v1.model

    def _log(self, message):
        """
        Prints a message to the console if verbose mode is enabled.
        """
        if self.verbose:
            print(message)

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
        kernel_type = solver_settings.get("kernel", "CUDA")
        kernel_enum = solver.Kernel.enum
        kernel_to_set = next((k.name for k in kernel_enum if k.name.lower() == kernel_type.lower()), None)
        if kernel_to_set:
            solver.Kernel = getattr(kernel_enum, kernel_to_set)
            self._log(f"    - Solver kernel set to: {kernel_to_set}")
        else:
            self._log(f"    - Warning: Invalid solver kernel '{kernel_type}'. Using default.")

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

    def _finalize_setup(self, simulation, all_simulation_parts):
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

        simulation.UpdateGrid()
        simulation.CreateVoxels()
        self._log("    - Finalizing setup complete.")
