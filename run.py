import argparse
import sys
from pathlib import Path

# Ensure the project root is in the Python path
# This allows the script to be run from anywhere and still find the 'src' and 'scripts' modules
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from scripts.run_osparc_batch import main

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run a batch of simulations on oSPARC with a progress GUI.")
    parser.add_argument(
        '--config',
        type=str,
        required=False,
        default="configs/todays_far_field_config.json",
        help="Path to the configuration file (defaults to 'configs/todays_far_field_config.json')."
    )
    args = parser.parse_args()
    main(args.config)