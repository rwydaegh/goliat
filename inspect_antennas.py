import os
import sys
import argparse

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.config import Config
from src.study import NearFieldStudy

def main():
    """
    Inspects the component names of a given antenna model after setup.
    """
    parser = argparse.ArgumentParser(description="Inspect antenna component names.")
    parser.add_argument('--frequency', type=int, required=True, help="Frequency in MHz of the antenna to inspect.")
    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.abspath(__file__))
    config = Config(base_dir)
    study = NearFieldStudy(config)

    freq_band = str(args.frequency)
    antenna_config = config.get_antenna_config().get(freq_band)
    if not antenna_config:
        raise ValueError(f"No antenna configuration found for frequency: {freq_band} MHz")

    center_frequency = antenna_config.get("center_frequency")
    if not center_frequency:
        raise ValueError(f"'center_frequency' not defined for frequency: {freq_band} MHz")

    project_name = f"inspect_{freq_band}MHz_antenna"
    
    print(f"--- Setting up project to inspect antenna for {freq_band} MHz ---")
    
    # We only need to run the setup part to load the model, but we need to inspect
    # the scene before the project is closed. We will replicate the key parts of
    # the study.run_single() method here.
    
    from src.project_manager import ProjectManager
    from src.simulation_setup import SimulationSetup
    from src.antenna import Antenna
    from src.utils import ensure_s4l_running

    ensure_s4l_running()
    
    results_dir = os.path.join(base_dir, 'results')
    os.makedirs(results_dir, exist_ok=True)
    project_path = os.path.join(results_dir, f"{project_name}.smash")

    project_manager = ProjectManager(project_path, verbose=config.get_verbose())
    antenna = Antenna(config, center_frequency)

    project_manager.create_new()
    setup = SimulationSetup(config, "freespace", center_frequency, "origin", antenna, config.get_verbose(), True)
    setup.run_full_setup()

    print(f"\n--- Antenna Components for {freq_band} MHz (Live Inspection) ---")
    
    import s4l_v1.model
    all_entities = s4l_v1.model.AllEntities()
    
    # Recursively find and print all entities
    print("--- All Entities in Scene ---")
    def print_entities_recursive(entity, indent=0):
        if hasattr(entity, 'Name'):
            print(f"{'  ' * indent}- Name: '{entity.Name}', Type: {type(entity).__name__}")
        
        if hasattr(entity, 'Entities') and entity.Entities is not None:
            for child in entity.Entities:
                print_entities_recursive(child, indent + 1)
    
    for entity in all_entities:
        print_entities_recursive(entity)

    print("\n--- Inspection Finished ---")
    project_manager.save()
    project_manager.close()


if __name__ == "__main__":
    main()