import argparse
import os
import sys

# Ensure the project root directory is in the Python path
base_dir = os.path.dirname(os.path.abspath(__file__))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

from src.studies.near_field_study import NearFieldStudy
from src.studies.far_field_study import FarFieldStudy
from src.startup import run_full_startup

def main():
    """
    Main entry point for running simulation studies.
    """
    parser = argparse.ArgumentParser(description="Run near-field or far-field simulation studies.")
    parser.add_argument(
        'study_type',
        type=str,
        choices=['near_field', 'far_field'],
        help="The type of study to run."
    )
    parser.add_argument(
        '--skip-startup',
        action='store_true',
        help="Skip the startup checks for dependencies and data."
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help="Enable detailed logging output."
    )
    parser.add_argument(
        '--setup-only',
        action='store_true',
        help="Only run the setup phase, do not run the simulation."
    )
    parser.add_argument(
        '--extract-only',
        action='store_true',
        help="Only run the extraction phase, skipping setup and simulation."
    )

    args = parser.parse_args()

    if not args.skip_startup:
        run_full_startup(base_dir)

    if args.study_type == 'near_field':
        config_file = "near_field_config.json"
        study = NearFieldStudy(config_filename=config_file, verbose=args.verbose)
    elif args.study_type == 'far_field':
        config_file = "far_field_config.json"
        study = FarFieldStudy(config_filename=config_file, verbose=args.verbose)
    else:
        # This case should not be reachable due to 'choices' in argparse
        print(f"Error: Unknown study type '{args.study_type}'")
        sys.exit(1)
        
    study.run(setup_only=args.setup_only, extract_only=args.extract_only)

if __name__ == "__main__":
    main()