from .config import Config
from .project import NearFieldProject

class NearFieldStudy:
    """
    Manages and runs a full near-field simulation campaign.
    """
    def __init__(self, config):
        self.config = config

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
                    
                    print(f"--- Starting project: {project_name} ---")
                    
                    project = NearFieldProject(
                        project_name=project_name,
                        phantom_name=phantom_name,
                        frequency_mhz=freq,
                        placement_name=placement,
                        config=self.config
                    )
                    
                    try:
                        project.setup()
                        project.run()
                        project.extract_results()
                    except Exception as e:
                        print(f"ERROR: An error occurred during project {project_name}: {e}")
                    finally:
                        project.cleanup()
                        
                    print(f"--- Finished project: {project_name} ---\n")