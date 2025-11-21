import argparse
import json
import logging
import os

import matplotlib

# Set non-interactive backend BEFORE importing any modules that use matplotlib
matplotlib.use("Agg")

from goliat.utils.setup import initial_setup
from goliat.analysis.analyzer import Analyzer
from goliat.analysis.far_field_strategy import FarFieldAnalysisStrategy
from goliat.analysis.near_field_strategy import NearFieldAnalysisStrategy
from goliat.config import Config
from goliat.logging_manager import setup_loggers

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
    args = parser.parse_args()

    # Setup logging
    setup_loggers()

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
