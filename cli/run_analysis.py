import argparse
import json
import logging
import os
import sys

# Check for no-gui flag before importing matplotlib to set backend
# GUI is now default ON unless --no-gui is specified
GUI_MODE = "--no-gui" not in sys.argv

import matplotlib

# Always use Agg backend for analysis plotting to avoid threading issues
# even when the GUI is running (the GUI is a separate PyQt window)
matplotlib.use("Agg")

from goliat.utils.setup import initial_setup
from goliat.analysis.analyzer import Analyzer
from goliat.analysis.far_field_strategy import FarFieldAnalysisStrategy
from goliat.analysis.near_field_strategy import NearFieldAnalysisStrategy
from goliat.config import Config
from goliat.logging_manager import setup_loggers

# Imports for GUI
if GUI_MODE:
    try:
        from PySide6.QtWidgets import QApplication
        from goliat.gui.analysis_gui import AnalysisGUI
    except ImportError:
        print("Error: PySide6 not installed or AnalysisGUI not found. Running in headless mode.")
        GUI_MODE = False
        matplotlib.use("Agg")

# Base directory for config files
from cli.utils import get_base_dir

base_dir = get_base_dir()

# --- Centralized Startup ---
# Only run initial_setup if not in test/CI environment
if not os.environ.get("PYTEST_CURRENT_TEST") and not os.environ.get("CI"):
    initial_setup()
# --- End Centralized Startup ---


def load_analysis_config(config_path: str | None) -> dict:
    """Loads the analysis configuration file.

    Args:
        config_path: Path to the analysis config JSON file, or None.

    Returns:
        Dictionary with plot names as keys and boolean values, or empty dict if not provided.
    """
    if not config_path:
        return {}

    if not os.path.exists(config_path):
        logging.getLogger("progress").warning(
            f"Analysis config file not found: {config_path}. Generating all plots.",
            extra={"log_type": "warning"},
        )
        return {}

    try:
        with open(config_path, "r") as f:
            config = json.load(f)
        return config
    except json.JSONDecodeError as e:
        logging.getLogger("progress").error(
            f"Invalid JSON in analysis config file: {e}. Generating all plots.",
            extra={"log_type": "error"},
        )
        return {}


def main():
    """
    Main entry point for the analysis script.
    """
    parser = argparse.ArgumentParser(description="Run analysis for near-field or far-field studies.")
    parser.add_argument(
        "config",
        type=str,
        nargs="?",
        default="near_field_config",
        help="Path or name of the configuration file (e.g., near_field_config or configs/near_field_config.json).",
    )
    parser.add_argument(
        "--format",
        type=str,
        choices=["pdf", "png"],
        default="pdf",
        help="Output format for plots (default: pdf).",
    )
    parser.add_argument(
        "--analysis",
        type=str,
        default="configs/analysis.json",
        help="Path to analysis configuration file (JSON) specifying which plots to generate.",
    )
    parser.add_argument(
        "--generate-paper",
        action="store_true",
        default=False,
        help="Generate LaTeX paper after analysis completes.",
    )
    parser.add_argument(
        "--no-gui",
        action="store_true",
        default=False,
        help="Disable the GUI window and run in terminal-only mode.",
    )
    args = parser.parse_args()

    # Setup logging
    setup_loggers()

    # GUI is enabled by default unless --no-gui is specified or import failed
    gui_enabled = not args.no_gui and GUI_MODE

    config = Config(base_dir, config_filename=args.config)
    analysis_config = load_analysis_config(args.analysis)

    phantoms = config["phantoms"] or []
    if not phantoms:
        logging.getLogger("progress").error("No phantoms found in the configuration file.")
        return

    study_type = config["study_type"]
    if not study_type:
        logging.getLogger("progress").error("'study_type' not found in the configuration file.")
        return

    if gui_enabled:
        # GUI Mode Execution
        app = QApplication(sys.argv)
        
        # 1. Calculate Total Items
        total_items = 0
        strategies = []
        
        # Pre-create strategies to calculate totals
        for phantom_name in phantoms:
            if study_type == "near_field":
                strategy = NearFieldAnalysisStrategy(config, phantom_name, analysis_config=analysis_config)
            else:
                strategy = FarFieldAnalysisStrategy(config, phantom_name, analysis_config=analysis_config)
            
            strategies.append((phantom_name, strategy))
            total_items += strategy.get_total_items()

        # 2. Create GUI
        window_title = f"{phantoms[0]} ({len(phantoms)} phantoms)" if len(phantoms) > 1 else phantoms[0]
        gui = AnalysisGUI(window_title, total_items)
        gui.show()
        
        # 3. Define Worker Function
        def run_analysis_task():
            for phantom_name, strategy in strategies:
                # Update GUI header if possible (not strictly thread-safe to update UI directly, 
                # but we can rely on logging "Starting Results Analysis" which GUI handles)
                analyzer = Analyzer(config, phantom_name, strategy, plot_format=args.format)
                analyzer.run_analysis()
            
            if args.generate_paper:
                from cli.generate_paper import main as generate_paper_main
                logging.getLogger("progress").info("Generating LaTeX paper...", extra={"log_type": "info"})
                generate_paper_main()

        # 4. Start Analysis in Background
        gui.start_analysis(run_analysis_task)
        
        # 5. Start Event Loop
        sys.exit(app.exec())

    else:
        # Headless Mode Execution (Original)
        for phantom_name in phantoms:
            if study_type == "near_field":
                strategy = NearFieldAnalysisStrategy(config, phantom_name, analysis_config=analysis_config)
            else:
                strategy = FarFieldAnalysisStrategy(config, phantom_name, analysis_config=analysis_config)

            analyzer = Analyzer(config, phantom_name, strategy, plot_format=args.format)
            analyzer.run_analysis()

        # Generate paper if requested
        if args.generate_paper:
            from cli.generate_paper import main as generate_paper_main

            logging.getLogger("progress").info("Generating LaTeX paper...", extra={"log_type": "info"})
            generate_paper_main()


if __name__ == "__main__":
    main()
