import os
import sys
from src.startup import run_full_startup

def main():
    """
    Runs a sweep of phantom simulation studies for all frequencies for a specific placement.
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
    placement_name = "front_of_eyes"
    
    # Get all frequencies from the antenna configuration
    frequencies = config.get_antenna_config().keys()

    print(f"--- Starting Simulation Sweep for Phantom: {phantom_name}, Placement: {placement_name} ---")

    for freq in frequencies:
        frequency_mhz = int(freq)
        base_project_name = f"{phantom_name}_{frequency_mhz}MHz_{placement_name}"

        print(f"--- Starting Phantom Simulation Scenario: {base_project_name} ---")
        try:
            study.run_placement_scenario(
                base_project_name=base_project_name,
                phantom_name=phantom_name,
                frequency_mhz=frequency_mhz,
                placement_name=placement_name,
                free_space=False,
                setup_only=False,
                extract_only=False
            )
        except Exception as e:
            print(f"  - ERROR: An error occurred during the {base_project_name} scenario: {e}")
            import traceback
            traceback.print_exc()
        
        print(f"--- Phantom Simulation Scenario Finished: {base_project_name} ---")

    print(f"--- Full Simulation Sweep Finished ---")

if __name__ == "__main__":
    main()