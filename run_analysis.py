import os
import sys
import argparse
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend before importing pyplot
import logging

# Ensure the src directory is in the Python path
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__)))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

# --- Centralized Startup ---
from scripts.utils import initial_setup
initial_setup()
# --- End Centralized Startup ---

from src.config import Config
from src.analysis.analyzer import Analyzer
from src.analysis.strategies import NearFieldAnalysisStrategy, FarFieldAnalysisStrategy
from src.logging_manager import setup_loggers

def main():
    """
    Main entry point for the analysis script.
    """
    parser = argparse.ArgumentParser(description="Run analysis for near-field or far-field studies.")
    parser.add_argument('--config', type=str, required=True, help="Path to the configuration file.")
    args = parser.parse_args()

    # Setup logging
    setup_loggers()

    config = Config(base_dir, config_filename=args.config)
    
    phantoms = config.get_setting('phantoms', [])
    if not phantoms:
        logging.getLogger('progress').error("No phantoms found in the configuration file.")
        return

    study_type = config.get_setting('study_type')
    if not study_type:
        logging.getLogger('progress').error("'study_type' not found in the configuration file.")
        return

    for phantom_name in phantoms:
        if study_type == 'near_field':
            strategy = NearFieldAnalysisStrategy(config, phantom_name)
        else:
            strategy = FarFieldAnalysisStrategy(config, phantom_name)
        
        analyzer = Analyzer(config, phantom_name, strategy)
        analyzer.run_analysis()

if __name__ == "__main__":
    main()