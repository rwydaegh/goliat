import os
import sys
import argparse

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.config import Config
from src.logging_manager import setup_loggers, shutdown_loggers
import logging
import atexit

def main():
    """
    Inspects the component names of a given antenna model after setup.
    """
    parser = argparse.ArgumentParser(description="Inspect antenna component names.")
    parser.add_argument('--frequency', type=int, required=True, help="Frequency in MHz of the antenna to inspect.")
    parser.add_argument('--config', type=str, default="near_field_config.json", help="Configuration file to use.")
    args = parser.parse_args()

    # Setup logging
    setup_loggers()
    atexit.register(shutdown_loggers)
    progress_logger = logging.getLogger('progress')
    verbose_logger = logging.getLogger('verbose')

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    config = Config(project_root, args.config)

    freq_band = str(args.frequency)
    antenna_config = config.get_antenna_config().get(freq_band)
    if not antenna_config:
        raise ValueError(f"No antenna configuration found for frequency: {freq_band} MHz")

    center_frequency = antenna_config.get("center_frequency")
    if not center_frequency:
        raise ValueError(f"'center_frequency' not defined for frequency: {freq_band} MHz")

    project_name = f"inspect_{freq_band}MHz_antenna"
    
    progress_logger.info(f"--- Setting up project to inspect antenna for {freq_band} MHz ---")
    
    from src.project_manager import ProjectManager
    from src.setups.near_field_setup import NearFieldSetup
    from src.antenna import Antenna
    from src.utils import ensure_s4l_running

    ensure_s4l_running()
    
    project_manager = ProjectManager(config, verbose_logger, progress_logger)
    antenna = Antenna(config, center_frequency)

    # Use the NearFieldSetup for freespace inspection
    setup = NearFieldSetup(config, "freespace", center_frequency, "origin", antenna, verbose_logger, progress_logger, free_space=True)
    setup.run_full_setup(project_manager)

    verbose_logger.info(f"\n--- Antenna Components for {freq_band} MHz (Live Inspection) ---")
    
    import s4l_v1.model
    all_entities = s4l_v1.model.AllEntities()
    
    # Recursively find and print all entities
    verbose_logger.info("--- All Entities in Scene ---")
    def print_entities_recursive(entity, indent=0):
        if hasattr(entity, 'Name'):
            verbose_logger.info(f"{'  ' * indent}- Name: '{entity.Name}', Type: {type(entity).__name__}")
        
        if hasattr(entity, 'Entities') and entity.Entities is not None:
            for child in entity.Entities:
                print_entities_recursive(child, indent + 1)
    
    for entity in all_entities:
        print_entities_recursive(entity)

    progress_logger.info("\n--- Inspection Finished ---")
    project_manager.save()
    project_manager.close()


if __name__ == "__main__":
    main()