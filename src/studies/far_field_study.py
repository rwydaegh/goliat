import os
from .base_study import BaseStudy
from ..config import Config
from ..project_manager import ProjectManager
from ..setups.far_field_setup import FarFieldSetup
from ..setups.phantom_setup import PhantomSetup
from ..simulation_runner import SimulationRunner
from ..results_extractor import ResultsExtractor
from ..utils import ensure_s4l_running

class FarFieldStudy(BaseStudy):
    """
    Manages a far-field simulation study, including setup, execution, and results extraction.
    """
    def __init__(self, config_filename="far_field_config.json", verbose=True):
        super().__init__(config_filename, verbose)
        self.project_manager = ProjectManager(self.config, self.verbose)

    def run(self):
        """
        Executes the entire far-field study by iterating through each simulation case,
        creating a separate project for each.
        """
        self._log(f"--- Starting Far-Field Study: {self.config.get_setting('study_name')} ---")
        ensure_s4l_running()

        phantoms = self.config.get_setting('phantoms', [])
        frequencies = self.config.get_setting('frequencies_mhz', [])
        far_field_params = self.config.get_setting('far_field_setup/environmental', {})
        incident_directions = far_field_params.get('incident_directions', [])
        polarizations = far_field_params.get('polarizations', [])

        project_manager = ProjectManager(self.config, self.verbose)
        try:
            for phantom_name in phantoms:
                for freq in frequencies:
                    self._log(f"\n--- Processing: {phantom_name}, {freq}MHz ---")
                    
                    try:
                        project_manager.create_or_open_project(phantom_name, freq)
                        
                        all_simulations = []
                        # 1. Setup All Simulations for this frequency
                        self._log("  --- Setup Phase ---")
                        phantom_setup = PhantomSetup(self.config, phantom_name, self.verbose)
                        phantom_setup.ensure_phantom_is_loaded()

                        for direction_name in incident_directions:
                            for polarization_name in polarizations:
                                self._log(f"    - Setting up: {direction_name}_{polarization_name}")
                                setup = FarFieldSetup(self.config, phantom_name, freq, direction_name, polarization_name, project_manager, self.verbose)
                                simulation = setup.run_full_setup(phantom_setup)
                                if simulation:
                                    all_simulations.append(simulation)
                                else:
                                    self._log(f"  ERROR: Setup failed for {direction_name}_{polarization_name}")
                        
                        if not all_simulations:
                            self._log("  ERROR: No simulations were created for this frequency. Skipping.")
                            continue

                        # 2. Run All Simulations in the project
                        self._log("  --- Run Phase ---")
                        runner = SimulationRunner(self.config, project_manager.project_path, all_simulations, self.verbose)
                        runner.run_all()

                        # 3. Extract Results
                        self._log("  --- Extraction Phase ---")
                        # project_manager.reload_project() # Temporarily disabled to avoid disk space errors.
                        
                        # In the future, extract results from all_simulations
                        self._log("  --- Result extraction is a future step. ---")

                    except Exception as e:
                        self._log(f"  ERROR: An error occurred while processing {freq}MHz: {e}")
                    finally:
                        # Close the project for this phantom/frequency combination
                        if project_manager and hasattr(project_manager.document, 'IsOpen') and project_manager.document.IsOpen():
                            project_manager.close()
        finally:
            # Ensure the main document is closed at the very end of the study
            if project_manager and hasattr(project_manager.document, 'IsOpen') and project_manager.document.IsOpen():
                project_manager.close()

        self._log("\n--- Far-Field Study Finished ---")