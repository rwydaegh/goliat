import os
import argparse
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend before importing pyplot

from src.config import Config
from src.analysis.analyzer import Analyzer
from src.analysis.strategies import NearFieldAnalysisStrategy, FarFieldAnalysisStrategy

def main():
    """
    Main entry point for the analysis script.
    """
    parser = argparse.ArgumentParser(description="Run analysis for near-field or far-field studies.")
    parser.add_argument('study_type', type=str, choices=['near_field', 'far_field'], help="Type of study to analyze.")
    parser.add_argument('--config', type=str, required=True, help="Path to the configuration file.")
    args = parser.parse_args()

    base_dir = os.path.abspath(os.path.dirname(__file__))
    config = Config(base_dir, config_filename=args.config)
    
    phantoms = config.get_setting('phantoms', [])
    if not phantoms:
        print("No phantoms found in the configuration file.")
        return

    for phantom_name in phantoms:
        if args.study_type == 'near_field':
            strategy = NearFieldAnalysisStrategy(config, phantom_name)
        else:
            strategy = FarFieldAnalysisStrategy(config, phantom_name)
        
        analyzer = Analyzer(config, phantom_name, strategy)
        analyzer.run_analysis()

if __name__ == "__main__":
    main()