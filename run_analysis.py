import os
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend before importing pyplot

from src.config import Config
from src.analysis.analyzer import Analyzer

def main():
    """
    Main entry point for the analysis script.
    """
    # The base directory is the project root
    base_dir = os.path.abspath(os.path.dirname(__file__))
    
    # Initialize the configuration
    config = Config(base_dir)
    
    # Initialize and run the analyzer
    analyzer = Analyzer(config)
    analyzer.run_analysis()

if __name__ == "__main__":
    main()