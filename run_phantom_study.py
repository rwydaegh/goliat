import os
import sys
from src.startup import run_full_startup

def main():
    """
    Runs a single phantom simulation study.
    """
    base_dir = os.path.abspath(os.path.dirname(__file__))
    
    # Add the project root to the Python path
    sys.path.insert(0, base_dir)
    
    # Run all startup checks and preparations
    run_full_startup(base_dir)

    from src.config import Config
    from src.study import NearFieldStudy

    config = Config(base_dir)
    study = NearFieldStudy(config)

    phantom_name = "Thelonius"
    frequency_mhz = 700
    placement_name = "front_of_eyes"
    project_name = f"{phantom_name}_{frequency_mhz}MHz_{placement_name}_test"

    print(f"--- Starting Single Phantom Simulation Study: {project_name} ---")
    try:
        study.run_single(
            project_name=project_name,
            phantom_name=phantom_name,
            frequency_mhz=frequency_mhz,
            placement_name=placement_name,
            free_space=False,
            setup_only=False,
            extract_only=False
        )
    except Exception as e:
        print(f"  - ERROR: An error occurred during the {project_name} simulation: {e}")

    print(f"--- Single Phantom Simulation Study Finished: {project_name} ---")

if __name__ == "__main__":
    main()