import os
from .config import Config
from .antenna import Antenna
from .utils import ensure_s4l_running
from .project_manager import ProjectManager
from .simulation_setup import SimulationSetup
from .simulation_runner import SimulationRunner
from .results_extractor import ResultsExtractor

class NearFieldStudy:
    """
    Manages and runs a full near-field simulation campaign.
    """
    def __init__(self, config):
        self.config = config

    def run_single(self, project_name, phantom_name, frequency_mhz, placement_name, free_space=False, setup_only=False, extract_only=False):
        """
        Runs a single simulation project.
        """
        project = None
        try:
            print(f"--- Starting project: {project_name} ---")
            
            project = self._create_project_components(project_name, phantom_name, frequency_mhz, placement_name, free_space)

            if extract_only:
                self._run_extraction_only(project)
            elif setup_only:
                self._run_setup_only(project)
            else:
                self._run_full_project(project)

        except Exception as e:
            print(f"An error occurred during the study: {e}")
        finally:
            if project and project.get('project_manager'):
                project['project_manager'].cleanup()
            print(f"--- Finished project: {project_name} ---")

    def _create_project_components(self, project_name, phantom_name, frequency_mhz, placement_name, free_space):
        ensure_s4l_running()
        
        # Create a directory for the specific simulation results
        results_dir = os.path.join(self.config.base_dir, 'results', phantom_name, f"{frequency_mhz}MHz", placement_name)
        os.makedirs(results_dir, exist_ok=True)
        project_path = os.path.join(results_dir, f"{project_name}.smash")

        project_manager = ProjectManager(project_path, verbose=self.config.get_verbose())
        antenna = Antenna(self.config, frequency_mhz)

        return {
            "project_name": project_name,
            "phantom_name": phantom_name,
            "frequency_mhz": frequency_mhz,
            "placement_name": placement_name,
            "free_space": free_space,
            "project_path": project_path,
            "project_manager": project_manager,
            "antenna": antenna,
            "simulation": None
        }

    def _run_setup_only(self, project):
        print("--- Running project setup only ---")
        project['project_manager'].create_new()
        setup = SimulationSetup(self.config, project['phantom_name'], project['frequency_mhz'], project['placement_name'], project['antenna'], self.config.get_verbose(), project['free_space'])
        project['simulation'] = setup.run_full_setup()
        project['project_manager'].save()

    def _run_extraction_only(self, project):
        print("--- Opening project for result extraction only ---")
        project['project_manager'].open()
        sim_name = f"EM_FDTD_{project['phantom_name']}_{project['antenna'].get_model_type()}_{project['placement_name']}"
        import s4l_v1.document
        project['simulation'] = next((s for s in s4l_v1.document.AllSimulations if s.Name == sim_name), None)
        if not project['simulation']:
            raise RuntimeError(f"Could not find simulation '{sim_name}' in existing project.")
        
        extractor = ResultsExtractor(self.config, project['simulation'], project['phantom_name'], project['frequency_mhz'], project['placement_name'], self.config.get_verbose(), project['free_space'])
        extractor.extract()

    def _run_full_project(self, project):
        self._run_setup_only(project)
        
        print("--- Project Run Phase ---")
        runner = SimulationRunner(self.config, project['project_path'], project['simulation'], self.config.get_verbose())
        project['simulation'] = runner.run()

        # Reload the project to ensure results are available
        project['project_manager'].reload_project()
        
        # Update the simulation object reference after reload
        sim_name = f"EM_FDTD_{project['phantom_name']}_{project['antenna'].get_model_type()}_{project['placement_name']}"
        import s4l_v1.document
        project['simulation'] = next((s for s in s4l_v1.document.AllSimulations if s.Name == sim_name), None)

        print("--- Result Extraction Phase ---")
        extractor = ResultsExtractor(self.config, project['simulation'], project['phantom_name'], project['frequency_mhz'], project['placement_name'], self.config.get_verbose(), project['free_space'])
        extractor.extract()

    def run_campaign(self):
        """
        Runs the entire simulation campaign based on the configuration.
        """
        phantoms = self.config.phantoms_config.keys()
        frequencies = self.config.get_frequencies()

        for phantom_name in phantoms:
            placements_config = self.config.get_phantom_placements(phantom_name)
            placements = [p.replace('do_', '') for p, enabled in placements_config.items() if enabled and p.startswith('do_')]
            
            for freq in frequencies:
                for placement in placements:
                    project_name = f"{phantom_name}_{freq}MHz_{placement}"
                    self.run_single(project_name, phantom_name, freq, placement)

    def run_campaign(self):
        """
        Runs the entire simulation campaign based on the configuration.
        """
        phantoms = self.config.phantoms_config.keys()
        frequencies = self.config.get_frequencies()

        for phantom_name in phantoms:
            placements_config = self.config.get_phantom_placements(phantom_name)
            placements = [p.replace('do_', '') for p, enabled in placements_config.items() if enabled and p.startswith('do_')]
            
            for freq in frequencies:
                for placement in placements:
                    project_name = f"{phantom_name}_{freq}MHz_{placement}"
                    self.run_single(project_name, phantom_name, freq, placement)