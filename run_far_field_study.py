import os
import sys

# Add the src directory to the Python path
# This is necessary to be able to import modules from the src directory
# when running this script from the root directory.
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from studies.far_field_study import FarFieldStudy

def main():
    """
    Main function to run the far-field simulation study.
    """
    print("--- Initializing Far-Field Study ---")
    
    # The FarFieldStudy class will load 'far_field_config.json' by default
    study = FarFieldStudy()
    study.run()

    print("--- Far-Field Study Script Finished ---")

if __name__ == "__main__":
    main()