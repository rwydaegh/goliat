import os
import sys
import argparse

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.config import Config
from src.project import NearFieldProject

def main():
    """
    Main entry point to run the near-field simulation study.
    """
    parser = argparse.ArgumentParser(description="Run a near-field simulation study.")
    parser.add_argument('--phantom', type=str, required=True, help="Name of the phantom to use.")
    parser.add_argument('--antenna', type=str, required=True, help="Name of the antenna model to use.")
    parser.add_argument('--frequency', type=int, required=True, help="Frequency in MHz.")
    parser.add_argument('--position', type=str, required=True, help="Placement of the antenna.")
    parser.add_argument('--force-setup', action='store_true', help="Force the project setup to run even if a .smash file exists.")
    parser.add_argument('--extract-only', action='store_true', help="Only run the result extraction step.")
    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    project_name = f"{args.phantom}_{args.frequency}MHz_{args.position}"
    
    project = None  # Ensure project is defined for the finally block
    try:
        print(f"--- Starting project: {project_name} ---")
        config = Config(base_dir)
        
        project = NearFieldProject(
            project_name=project_name,
            phantom_name=args.phantom,
            frequency_mhz=args.frequency,
            placement_name=args.position,
            config=config,
            verbose=config.get_verbose(),
            force_setup=args.force_setup
        )
        
        if args.extract_only:
            print("--- Opening project for result extraction only ---")
            project.open_for_extraction()
        else:
            project.setup()
            project.run()
        
        project.extract_results()
        
    except Exception as e:
        print(f"An error occurred during the study: {e}")
    finally:
        if project:
            project.cleanup()
        print(f"--- Finished project: {project_name} ---")

if __name__ == "__main__":
    main()