import os
from .base_study import BaseStudy
from ..antenna import Antenna
from ..utils import ensure_s4l_running
from ..project_manager import ProjectManager
from ..setups.near_field_setup import NearFieldSetup
from ..simulation_runner import SimulationRunner
from ..results_extractor import ResultsExtractor

class NearFieldStudy(BaseStudy):
    """
    Manages and runs a full near-field simulation campaign.
    """
    def __init__(self, config_filename="near_field_config.json", verbose=True):
        super().__init__(config_filename, verbose)
        self.project_manager = ProjectManager(self.config, self.verbose)

    def run(self, setup_only=False):
        """
        Runs the entire simulation campaign based on the configuration.
        """
        self._log(f"--- Starting Near-Field Study: {self.config.get_setting('study_name')} ---")
        ensure_s4l_running()

        phantoms = self.config.get_setting('phantoms', {}).keys()
        frequencies = self.config.get_setting('antenna_config', {}).keys()
        all_scenarios = self.config.get_setting('placement_scenarios', {})

        try:
            for phantom_name in phantoms:
                placements_config = self.config.get_phantom_placements(phantom_name)
                if not placements_config:
                    continue
                
                enabled_placements = []
                for scenario_name, scenario_details in all_scenarios.items():
                    if placements_config.get(f"do_{scenario_name}"):
                        positions = scenario_details.get('positions', {})
                        orientations = scenario_details.get('orientations', {})
                        for pos_name in positions.keys():
                            for orient_name in orientations.keys():
                                enabled_placements.append(f"{scenario_name}_{pos_name}_{orient_name}")

                for freq_str in frequencies:
                    freq = int(freq_str)
                    for placement_name in enabled_placements:
                        self._run_placement(phantom_name, freq, placement_name, setup_only)
        
        finally:
            self.project_manager.cleanup()
            self._log("\n--- Near-Field Study Finished ---")

    def _run_placement(self, phantom_name, freq, placement_name, setup_only=False):
        """
        Runs a full placement scenario, which may include multiple positions and orientations.
        """
        self._log(f"\n--- Running Placement: {phantom_name}, {freq}MHz, {placement_name} ---")
        
        try:
            # 1. Setup Simulation
            self._log("--- Setup Phase ---")
            antenna = Antenna(self.config, freq)
            setup = NearFieldSetup(self.config, phantom_name, freq, placement_name, antenna, self.verbose)
            simulation = setup.run_full_setup(self.project_manager)
            
            if not simulation:
                self._log("ERROR: Setup failed to produce a simulation object.")
                return

            if setup_only:
                self._log("--- Setup Only Mode: Skipping simulation run and extraction. ---")
                self.project_manager.save()
                return

            # 2. Run Simulation
            self._log("--- Run Phase ---")
            runner = SimulationRunner(self.config, self.project_manager.project_path, simulation, self.verbose)
            simulation = runner.run()

            # 3. Extract Results
            self._log("--- Extraction Phase ---")
            self.project_manager.reload_project()
            
            import s4l_v1.document
            sim_name = simulation.Name
            simulation = next((s for s in s4l_v1.document.AllSimulations if s.Name == sim_name), None)
            if not simulation:
                raise RuntimeError(f"Could not find simulation '{sim_name}' after reloading project.")

            extractor = ResultsExtractor(self.config, simulation, phantom_name, freq, placement_name, self.verbose)
            extractor.extract()

            # Save the project to store the results of this placement
            self.project_manager.save()

        except Exception as e:
            self._log(f"ERROR: An error occurred during placement '{placement_name}': {e}")