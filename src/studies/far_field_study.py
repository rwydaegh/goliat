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

    def run(self, setup_only=False, extract_only=False):
        """
        Executes the entire far-field study by iterating through each simulation case,
        creating a separate project for each.
        """
        self._log(f"--- Starting Far-Field Study: {self.config.get_setting('study_name')} ---")
        ensure_s4l_running()

        if extract_only:
            self._run_extraction_only()
            return

        phantoms = self.config.get_setting('phantoms', [])
        frequencies = self.config.get_setting('frequencies_mhz', [])
        far_field_params = self.config.get_setting('far_field_setup/environmental', {})
        incident_directions = far_field_params.get('incident_directions', [])
        polarizations = far_field_params.get('polarizations', [])

        try:
            for phantom_name in phantoms:
                for freq in frequencies:
                    self._log(f"\n--- Processing: {phantom_name}, {freq}MHz ---")
                    
                    try:
                        self.project_manager.create_or_open_project(phantom_name, freq)
                        
                        all_simulations = []
                        # 1. Setup All Simulations for this frequency
                        self._log("  --- Setup Phase ---")
                        phantom_setup = PhantomSetup(self.config, phantom_name, self.verbose)
                        phantom_setup.ensure_phantom_is_loaded()

                        for direction_name in incident_directions:
                            for polarization_name in polarizations:
                                self._log(f"    - Setting up: {direction_name}_{polarization_name}")
                                setup = FarFieldSetup(self.config, phantom_name, freq, direction_name, polarization_name, self.project_manager, self.verbose)
                                simulation = setup.run_full_setup(phantom_setup)
                                if simulation:
                                    all_simulations.append((simulation, direction_name, polarization_name))
                                else:
                                    self._log(f"  ERROR: Setup failed for {direction_name}_{polarization_name}")
                        
                        if not all_simulations:
                            self._log("  ERROR: No simulations were created for this frequency. Skipping.")
                            continue

                        if setup_only:
                            self._log("  --- Setup Only Mode: Skipping simulation run and extraction. ---")
                            self.project_manager.save()
                            continue

                        # 2. Run All Simulations in the project
                        self._log("  --- Run Phase ---")
                        sim_objects_only = [s[0] for s in all_simulations]
                        runner = SimulationRunner(self.config, self.project_manager.project_path, sim_objects_only, self.verbose)
                        runner.run_all()

                        # 3. Extract Results
                        self._log("  --- Extraction Phase ---")
                        self.project_manager.reload_project()
                        self._extract_results_for_project(phantom_name, freq)

                    except Exception as e:
                        self._log(f"  ERROR: An error occurred while processing {freq}MHz: {e}")
                    finally:
                        if self.project_manager and hasattr(self.project_manager.document, 'IsOpen') and self.project_manager.document.IsOpen():
                            self.project_manager.close()
        finally:
            if self.project_manager and hasattr(self.project_manager.document, 'IsOpen') and self.project_manager.document.IsOpen():
                self.project_manager.close()

        self._log("\n--- Far-Field Study Finished ---")

    def _run_extraction_only(self):
        self._log("--- Running in Extract-Only Mode ---")
        phantoms = self.config.get_setting('phantoms', [])
        frequencies = self.config.get_setting('frequencies_mhz', [])
        
        for phantom_name in phantoms:
            for freq in frequencies:
                try:
                    # This will now open the project if it exists
                    self.project_manager.create_or_open_project(phantom_name, freq, skip_load=True)
                    
                    # Check if the project was successfully opened
                    if not (self.project_manager.document and hasattr(self.project_manager.document, 'IsOpen') and self.project_manager.document.IsOpen()):
                        self._log(f"  - Project file not found or could not be opened for {phantom_name} at {freq}MHz. Skipping.")
                        continue
                    
                    self._log(f"\n--- Extracting from: {phantom_name}, {freq}MHz ---")
                    self._extract_results_for_project(phantom_name, freq)
                except Exception as e:
                    self._log(f"  ERROR: An error occurred during extraction for {freq}MHz: {e}")
                finally:
                    if self.project_manager and hasattr(self.project_manager.document, 'IsOpen') and self.project_manager.document.IsOpen():
                        self.project_manager.close()

    def _extract_results_for_project(self, phantom_name, freq):
        import s4l_v1.document
        
        all_sims_in_doc = list(s4l_v1.document.AllSimulations)
        if not all_sims_in_doc:
            self._log("  - No simulations found in the project document.")
            return

        self._log(f"  - Found {len(all_sims_in_doc)} simulations in the project.")
        for sim in all_sims_in_doc:
            try:
                sim_name = sim.Name
                # Expected name format: EM_FDTD_thelonius_450MHz_x_pos_theta
                parts = sim_name.split('_')
                if len(parts) < 7:
                    self._log(f"    - WARNING: Could not parse simulation name '{sim_name}'. Skipping.")
                    continue
                
                direction_name = "_".join(parts[4:-1])
                polarization_name = parts[-1]
                placement_name = f"environmental_{direction_name}_{polarization_name}"
                
                self._log(f"    - Extracting from simulation: {sim_name}")
                extractor = ResultsExtractor(self.config, sim, phantom_name, freq, placement_name, 'far_field', self.verbose)
                extractor.extract()
            except Exception as e:
                self._log(f"    - ERROR: Failed to extract results for simulation '{sim.Name}': {e}")