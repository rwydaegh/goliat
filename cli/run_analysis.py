import argparse
import logging
import os

import matplotlib

from goliat.utils.setup import initial_setup
from goliat.analysis.analyzer import Analyzer
from goliat.analysis.far_field_strategy import FarFieldAnalysisStrategy
from goliat.analysis.near_field_strategy import NearFieldAnalysisStrategy
from goliat.config import Config
from goliat.logging_manager import setup_loggers

matplotlib.use("Agg")  # Use non-interactive backend before importing pyplot

# Base directory for config files (package is installed, no sys.path needed)
# Get project root (go up from cli to repo root)
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# --- Centralized Startup ---
# Only run initial_setup if not in test/CI environment
if not os.environ.get("PYTEST_CURRENT_TEST") and not os.environ.get("CI"):
    initial_setup()
# --- End Centralized Startup ---


def main():
    """
    Main entry point for the analysis script.
    """
    parser = argparse.ArgumentParser(description="Run analysis for near-field or far-field studies.")
    parser.add_argument("--config", type=str, required=True, help="Path to the configuration file.")
    args = parser.parse_args()

    # Setup logging
    setup_loggers()

    config = Config(base_dir, config_filename=args.config)

    phantoms = config.get_setting("phantoms", [])
    if not phantoms:
        logging.getLogger("progress").error("No phantoms found in the configuration file.")
        return

    study_type = config.get_setting("study_type")
    if not study_type:
        logging.getLogger("progress").error("'study_type' not found in the configuration file.")
        return

    for phantom_name in phantoms:
        if study_type == "near_field":
            strategy = NearFieldAnalysisStrategy(config, phantom_name)
        else:
            strategy = FarFieldAnalysisStrategy(config, phantom_name)

        analyzer = Analyzer(config, phantom_name, strategy)
        analyzer.run_analysis()


if __name__ == "__main__":
    main()
