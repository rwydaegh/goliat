import os
import sys
import argparse

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.config import Config
from src.study import NearFieldStudy

def main():
    """
    Runs a free-space simulation for each available frequency to validate
    the antenna models and the core simulation pipeline.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    config = Config(base_dir)
    study = NearFieldStudy(config)

    # Get all available frequency bands from the antenna configuration
    frequency_bands = config.get_antenna_config().keys()
    sorted_frequencies = sorted([int(f) for f in frequency_bands])

    print("--- Starting Full Free-Space Simulation Study ---")
    for freq_band in sorted_frequencies:
        print(f"\n--- Running Free-Space Simulation for {freq_band} MHz ---")

        antenna_config = config.get_antenna_config().get(str(freq_band))
        if not antenna_config:
            print(f"  - WARNING: No antenna configuration found for frequency: {freq_band} MHz. Skipping.")
            continue

        center_frequency = antenna_config.get("center_frequency")
        if not center_frequency:
            print(f"  - WARNING: 'center_frequency' not defined for {freq_band} MHz. Skipping.")
            continue

        project_name = f"freespace_{freq_band}MHz_validation"
        
        try:
            study.run_single(
                project_name=project_name,
                phantom_name="freespace",
                frequency_mhz=center_frequency,
                placement_name="origin",
                free_space=True,
                setup_only=False,
                extract_only=False
            )
        except Exception as e:
            print(f"  - ERROR: An error occurred during the {freq_band} MHz simulation: {e}")
            # Continue to the next simulation
            continue

    print("\n--- All Free-Space Simulations Finished ---")

if __name__ == "__main__":
    main()