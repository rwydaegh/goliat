import json
import os
import subprocess
import shutil
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import scienceplots
import pickle

import argparse
import sys

# Base directory for config files (package is installed, no sys.path needed)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))

from goliat.studies.near_field_study import NearFieldStudy
from goliat.studies.far_field_study import FarFieldStudy
from goliat.utils import ensure_s4l_running
from goliat.logging_manager import setup_loggers, shutdown_loggers
from goliat.utils import (
    Profiler as SimpleProfiler,
)  # Use the simple profiler for this analysis
import traceback
import multiprocessing
from PySide6.QtWidgets import QApplication
from analysis.sensitivity_analysis.gui import SensitivityAnalysisGUI
from goliat.config import Config
from goliat.data_extractor import get_parameter

# --- Configuration ---
SENSITIVITY_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "sensitivity_analysis_config.json")


def load_sensitivity_config():
    """Load the sensitivity analysis configuration."""
    with open(SENSITIVITY_CONFIG_PATH, "r") as f:
        return json.load(f)


def setup_directories(config):
    """Create necessary directories for the analysis."""
    os.makedirs(config["results_dir"], exist_ok=True)
    os.makedirs(config["analysis_fig_dir"], exist_ok=True)
    os.makedirs(config["config_dir"], exist_ok=True)


def analysis_process_wrapper(queue, frequency_mhz, sensitivity_config):
    """
    This function runs in a separate process and executes the sensitivity analysis.
    It communicates with the main GUI process via a queue.
    """
    # Add Sim4Life python libs to the path in the new process
    s4l_py_path = "C:/Program Files/Sim4Life_8.2.0.16876/Python/Lib/site-packages"
    if s4l_py_path not in sys.path:
        sys.path.insert(0, s4l_py_path)

    setup_loggers()
    try:
        ensure_s4l_running()
        import s4l_v1.document  # Import after the application is confirmed to be running

        results = []
        base_config_path = os.path.join(PROJECT_ROOT, sensitivity_config["base_config_path"])
        sensitivity_params = sensitivity_config["sensitivity_parameters"]
        output_variables = sensitivity_config["output_variables"]

        # For now, we handle one sensitivity parameter. The structure allows for more.
        param_info = sensitivity_params[0]
        param_name = param_info["name"]
        param_values = param_info["values"]

        class DummyGUI:
            def log(self, message, level="verbose"):
                pass

            def update_overall_progress(self, current_step, total_steps):
                pass

            def update_stage_progress(self, stage_name, current_step, total_steps):
                pass

            def start_stage_animation(self, task_name, end_value):
                pass

            def end_stage_animation(self):
                pass

            def update_profiler(self):
                pass

        with open(base_config_path, "r") as f:
            base_config = json.load(f)
        study_type = base_config.get("study_type")

        if study_type == "near_field":
            study = NearFieldStudy(study_type="near_field", config_filename=base_config_path, gui=DummyGUI())
        elif study_type == "far_field":
            study = FarFieldStudy(study_type="far_field", config_filename=base_config_path, gui=DummyGUI())
        else:
            raise ValueError(f"Unknown study type '{study_type}' in config.")

        profiling_config_path = os.path.join(PROJECT_ROOT, sensitivity_config["profiling_config_path"])
        profiler = SimpleProfiler(config_path=profiling_config_path, study_type="sensitivity_analysis")
        total_runs = len(param_values)
        profiler.start_study(total_runs)

        for i, value in enumerate(param_values):
            profiler.start_run()

            run_message = f"Run {i+1}/{total_runs}: {param_name} = {value} at {frequency_mhz} MHz"
            queue.put({"type": "status", "message": run_message})
            queue.put({"type": "progress", "current": i, "total": total_runs})

            elapsed = profiler.get_elapsed()
            eta = profiler.get_time_remaining()
            queue.put({"type": "timing", "elapsed": elapsed, "eta": eta})

            with profiler.subtask("config_creation"):
                with open(base_config_path, "r") as f:
                    config_data = json.load(f)

                if "simulation_parameters" not in config_data:
                    config_data["simulation_parameters"] = {}
                config_data["simulation_parameters"][param_name] = int(value)

                # Far-field configs don't have antenna_config, so we remove this logic.
                # The frequency is handled by the 'frequencies_mhz' list.
                config_data["frequencies_mhz"] = [frequency_mhz]

                run_name = f"sensitivity_{param_name}_{value}_freq_{frequency_mhz}"
                temp_config_path = os.path.join(
                    PROJECT_ROOT,
                    sensitivity_config["config_dir"],
                    f"{run_name}_config.json",
                )

                with open(temp_config_path, "w") as f:
                    json.dump(config_data, f, indent=2)

            study.config_filename = os.path.abspath(temp_config_path)
            study.run()

            with profiler.subtask("close_project"):
                import time

                if s4l_v1.document.AllSimulations:
                    s4l_v1.document.Close()
                    time.sleep(2)

            with profiler.subtask("extract_results"):
                run_results = {"param_value": value}

                # This context extraction needs to be more robust for both study types
                phantom_name = config_data.get("phantoms", ["default_phantom"])[0]

                if study_type == "near_field":
                    placement_scenario = list(config_data.get("placement_scenarios", {}).keys())[0]
                    position = list(config_data.get("placement_scenarios", {}).get(placement_scenario, {}).get("positions", {}).keys())[0]
                    orientation = list(
                        config_data.get("placement_scenarios", {}).get(placement_scenario, {}).get("orientations", {}).keys()
                    )[0]
                    placement_name = f"{placement_scenario}_{position}_{orientation}"
                else:  # far_field
                    setup_type = config_data.get("far_field_setup", {}).get("type", "environmental")
                    incident_direction = config_data.get("far_field_setup", {}).get(setup_type, {}).get("incident_directions", [""])[0]
                    polarization = config_data.get("far_field_setup", {}).get(setup_type, {}).get("polarizations", [""])[0]
                    placement_name = f"{setup_type}_{incident_direction}_{polarization}"

                context = {
                    "project_root": PROJECT_ROOT,
                    "phantom_name": phantom_name,
                    "frequency": frequency_mhz,
                    "placement_name": placement_name,
                }

                for var_name, var_config in output_variables.items():
                    val = get_parameter(var_config, context)
                    run_results[var_name] = val if val is not None else float("nan")
                    queue.put(
                        {
                            "type": "status",
                            "message": (
                                f"  -> Extracted {var_name}: {val:.4f}"
                                if val is not None
                                else f"  -> WARNING: Could not extract {var_name}"
                            ),
                        }
                    )

                results.append(run_results)

            profiler.end_run()
            profiler.save_estimates()

            df = pd.DataFrame(results)
            results_csv_path = os.path.join(
                PROJECT_ROOT,
                sensitivity_config["results_dir"],
                f"sensitivity_results_{frequency_mhz}MHz.csv",
            )
            df.to_csv(results_csv_path, index=False)

            # Pickle results
            results_pickle_path = os.path.join(
                PROJECT_ROOT,
                sensitivity_config["results_dir"],
                f"sensitivity_results_{frequency_mhz}MHz.pkl",
            )
            with open(results_pickle_path, "wb") as f:
                pickle.dump(df, f)

        queue.put({"type": "progress", "current": total_runs, "total": total_runs})
        df = pd.DataFrame(results)
        if not df.empty:
            queue.put(
                {
                    "type": "plot",
                    "df": df,
                    "freq": frequency_mhz,
                    "config": sensitivity_config,
                }
            )

        queue.put({"type": "finished"})

    except Exception as e:
        # Log the fatal error to the file-based loggers first
        error_message = f"FATAL ERROR in sensitivity analysis process: {e}\n{traceback.format_exc()}"
        # The loggers are already set up, so we can get them by name
        import logging

        logging.getLogger("progress").error(error_message)
        logging.getLogger("verbose").error(error_message)

        # Then, send the error to the GUI
        queue.put({"type": "status", "message": f"FATAL ERROR: Check logs for details."})
        queue.put({"type": "finished"})
    finally:
        # The application is managed by the process lifecycle.
        # We only need to ensure the loggers are shut down.
        shutdown_loggers()


def plot_results(df, frequency_mhz, config):
    """Plot the sensitivity analysis results."""
    plt.style.use("science")
    plt.rcParams.update({"text.usetex": False})
    fig, ax = plt.subplots()
    ax.grid(True, which="major", axis="y", linestyle="--")

    param_name = config["sensitivity_parameters"][0]["name"]
    output_vars = config["output_variables"].keys()

    for var in output_vars:
        ax.plot(
            df["param_value"],
            df[var],
            "o-",
            label=f'{var.replace("_", " ").title()} @ {frequency_mhz} MHz',
        )

    ax.set_xlabel(param_name.replace("_", " ").title())
    ax.set_ylabel("Output Value")
    ax.set_title(f"Sensitivity Analysis for Frequency {frequency_mhz} MHz")
    ax.legend()

    analysis_fig_dir = os.path.join(PROJECT_ROOT, config["analysis_fig_dir"])
    fig_path_png = os.path.join(analysis_fig_dir, f"sensitivity_plot_{frequency_mhz}MHz.png")
    plt.savefig(fig_path_png, dpi=300)
    plt.close(fig)  # Close the figure to free memory without showing it


def main():
    """Main function to run from the command line."""
    parser = argparse.ArgumentParser(description="Run sensitivity analysis for a given frequency.")
    parser.add_argument(
        "--frequency",
        type=int,
        default=700,
        help="The frequency in MHz to run the analysis for.",
    )
    args = parser.parse_args()

    sensitivity_config = load_sensitivity_config()
    setup_directories(sensitivity_config)

    queue = multiprocessing.Queue()

    process = multiprocessing.Process(
        target=analysis_process_wrapper,
        args=(queue, args.frequency, sensitivity_config),
    )

    app = QApplication(sys.argv)
    gui = SensitivityAnalysisGUI(queue, process)

    process.start()

    gui.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
