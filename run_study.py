import os
import sys

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.config import Config
from src.project import NearFieldProject

def main():
    """
    Main entry point to run the near-field simulation study.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # --- Single Test Case Configuration ---
    test_phantom = "thelonius"
    test_frequency = 700
    test_placement = "front_of_eyes"
    project_name = f"{test_phantom}_{test_frequency}MHz_{test_placement}"
    
    project = None  # Ensure project is defined for the finally block
    try:
        print(f"--- Starting single test project: {project_name} ---")
        config = Config(base_dir)
        
        project = NearFieldProject(
            project_name=project_name,
            phantom_name=test_phantom,
            frequency_mhz=test_frequency,
            placement_name=test_placement,
            config=config,
            verbose=config.get_verbose()
        )
        
        project.setup()
        project.run()
        project.extract_results()
        
    except Exception as e:
        print(f"An error occurred during the study: {e}")
    finally:
        if project:
            project.cleanup()
        print(f"--- Finished single test project: {project_name} ---")

if __name__ == "__main__":
    main()