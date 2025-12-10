import argparse
import json
import logging
import os
import sys

# Check for no-gui flag before importing matplotlib to set backend
# GUI is now default ON unless --no-gui is specified
GUI_MODE = "--no-gui" not in sys.argv

import matplotlib  # noqa: E402

# Always use Agg backend for analysis plotting to avoid threading issues
# even when the GUI is running (the GUI is a separate PyQt window)
matplotlib.use("Agg")

from goliat.utils.setup import initial_setup  # noqa: E402
from goliat.analysis.analyzer import Analyzer  # noqa: E402
from goliat.analysis.far_field_strategy import FarFieldAnalysisStrategy  # noqa: E402
from goliat.analysis.near_field_strategy import NearFieldAnalysisStrategy  # noqa: E402
from goliat.config import Config  # noqa: E402
from goliat.logging_manager import setup_loggers  # noqa: E402

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
from cli.utils import get_base_dir  # noqa: E402

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

        # 1. Create strategies for each phantom
        strategies = []
        for phantom_name in phantoms:
            if study_type == "near_field":
                strategy = NearFieldAnalysisStrategy(config, phantom_name, analysis_config=analysis_config)
            else:
                strategy = FarFieldAnalysisStrategy(config, phantom_name, analysis_config=analysis_config)
            strategies.append((phantom_name, strategy))

        # Calculate estimated total items based on config structure
        # Items = (num_frequencies × num_placements) per phantom + estimated plots
        antenna_config = config["antenna_config"] or {}
        placement_scenarios = config["placement_scenarios"] or {}

        num_frequencies = len(antenna_config)
        num_placements = 0
        for scenario_def in placement_scenarios.values():
            if scenario_def:
                positions = scenario_def.get("positions", {})
                orientations = scenario_def.get("orientations", {})
                num_placements += len(positions) * max(len(orientations), 1)

        # Items per phantom: processing + plotting (roughly 2x for plots)
        items_per_phantom = num_frequencies * num_placements * 2  # *2 for plots
        # Add buffer for additional plots (heatmaps, summaries, etc.)
        items_per_phantom += 50

        total_items = len(phantoms) * items_per_phantom

        logging.getLogger("progress").debug(
            f"Progress bar estimate: {num_frequencies} freqs × {num_placements} placements × 2 + 50 = "
            f"{items_per_phantom}/phantom × {len(phantoms)} phantoms = {total_items} total items",
            extra={"log_type": "verbose"},
        )

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

            # Generate Excel file if enabled (default: True for near_field)
            if analysis_config.get("generate_excel", True) and study_type == "near_field":
                from goliat.analysis.create_excel_for_partners import main as excel_main

                logging.getLogger("progress").info("--- Generating Excel file for partners ---", extra={"log_type": "header"})
                try:
                    excel_main()
                    logging.getLogger("progress").info("--- Excel file generation complete ---", extra={"log_type": "success"})
                except Exception as e:
                    logging.getLogger("progress").warning(f"Failed to generate Excel file: {e}", extra={"log_type": "warning"})

            # Run stats if enabled (default: True)
            if analysis_config.get("run_stats", True):
                from goliat.analysis.analyze_simulation_stats import main as stats_main

                logging.getLogger("progress").info("--- Running simulation statistics ---", extra={"log_type": "header"})
                # Run stats with default arguments
                original_argv = sys.argv[:]
                sys.argv = ["goliat-stats", "results", "-o", "paper/simulation_stats", "--json"]
                try:
                    stats_main()
                    logging.getLogger("progress").info("--- Simulation statistics complete ---", extra={"log_type": "success"})
                finally:
                    sys.argv = original_argv

            # Run comparison if enabled in analysis config
            compare_config = analysis_config.get("compare", {})
            if compare_config.get("enabled", False):
                from goliat.analysis.compare import run_comparison

                logging.getLogger("progress").info("--- Running UGent vs CNR comparison ---", extra={"log_type": "header"})
                try:
                    run_comparison(
                        compare_config.get("ugent_file", "results/near_field/Final_Data_UGent.xlsx"),
                        compare_config.get("cnr_file", "results/near_field/Final_Data_CNR.xlsx"),
                        compare_config.get("output_dir", "plots/comparison"),
                        args.format,
                    )
                    logging.getLogger("progress").info("--- Comparison complete ---", extra={"log_type": "success"})
                except Exception as e:
                    logging.getLogger("progress").warning(f"Failed to run comparison: {e}", extra={"log_type": "warning"})

            logging.getLogger("progress").info("Done. You can now close the GUI.", extra={"log_type": "success"})

        # 4. Start Analysis in Background
        gui.start_analysis(run_analysis_task)

        # 5. Start Event Loop
        app.exec()
        # Force exit to avoid waiting for non-daemon threads (like matplotlib backends)
        os._exit(0)

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

        # Generate Excel file if enabled (default: True for near_field)
        if analysis_config.get("generate_excel", True) and study_type == "near_field":
            from goliat.analysis.create_excel_for_partners import main as excel_main

            logging.getLogger("progress").info("--- Generating Excel file for partners ---", extra={"log_type": "header"})
            try:
                excel_main()
                logging.getLogger("progress").info("--- Excel file generation complete ---", extra={"log_type": "success"})
            except Exception as e:
                logging.getLogger("progress").warning(f"Failed to generate Excel file: {e}", extra={"log_type": "warning"})

        # Run stats if enabled (default: True)
        if analysis_config.get("run_stats", True):
            from goliat.analysis.analyze_simulation_stats import main as stats_main

            logging.getLogger("progress").info("--- Running simulation statistics ---", extra={"log_type": "header"})
            # Run stats with default arguments
            original_argv = sys.argv[:]
            sys.argv = ["goliat-stats", "results", "-o", "paper/simulation_stats", "--json"]
            try:
                stats_main()
                logging.getLogger("progress").info("--- Simulation statistics complete ---", extra={"log_type": "success"})
            finally:
                sys.argv = original_argv

        # Run comparison if enabled in analysis config
        compare_config = analysis_config.get("compare", {})
        if compare_config.get("enabled", False):
            from goliat.analysis.compare import run_comparison

            logging.getLogger("progress").info("--- Running UGent vs CNR comparison ---", extra={"log_type": "header"})
            try:
                run_comparison(
                    compare_config.get("ugent_file", "results/near_field/Final_Data_UGent.xlsx"),
                    compare_config.get("cnr_file", "results/near_field/Final_Data_CNR.xlsx"),
                    compare_config.get("output_dir", "plots/comparison"),
                    args.format,
                )
                logging.getLogger("progress").info("--- Comparison complete ---", extra={"log_type": "success"})
            except Exception as e:
                logging.getLogger("progress").warning(f"Failed to run comparison: {e}", extra={"log_type": "warning"})


if __name__ == "__main__":
    main()
