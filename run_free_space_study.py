import json
import os
import sys
import tempfile
import traceback

from scripts.utils import initial_setup
from src.config import Config
from src.logging_manager import setup_loggers, shutdown_loggers
from src.studies.near_field_study import NearFieldStudy

# Ensure the src directory is in the Python path
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__)))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

# --- Centralized Startup ---
initial_setup()
# --- End Centralized Startup ---


class ConsoleLogger:
    """A console-based logger for headless script execution."""

    def __init__(self, progress_logger, verbose_logger):
        self.progress_logger = progress_logger
        self.verbose_logger = verbose_logger

    def log(self, message, level="verbose", log_type="default"):
        if level == "progress":
            self.progress_logger.info(message)
        else:
            self.verbose_logger.info(message)

    def update_overall_progress(self, current, total):
        pass

    def update_stage_progress(self, name, current, total):
        pass

    def start_stage_animation(self, task_name, end_value):
        pass

    def end_stage_animation(self):
        pass

    def update_profiler(self):
        pass

    def is_stopped(self):
        return False


def create_temp_config(base_config, frequency_mhz):
    """Creates a temporary configuration for a single free-space run."""

    # Deep copy the base configuration
    config_data = json.loads(json.dumps(base_config.config))

    # Override for a single free-space simulation
    config_data["phantoms"] = {"freespace": {"do_front_of_eyes_center_vertical": True}}
    config_data["antenna_config"] = {str(frequency_mhz): base_config.get_antenna_config().get(str(frequency_mhz))}
    config_data["placement_scenarios"] = {
        "front_of_eyes_center_vertical": {
            "positions": {"center": [0, 0, 0]},
            "orientations": {"vertical": [0, 0, 0]},
        }
    }
    # Ensure we do a full run
    config_data["execution_control"] = {
        "do_setup": True,
        "do_run": True,
        "do_extract": True,
    }

    # Write to a temporary file
    temp_file = tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".json", dir=os.path.join(base_dir, "configs"))
    json.dump(config_data, temp_file, indent=4)
    temp_file.close()
    return temp_file.name


def main():
    """
    Runs a free-space simulation for each available frequency to validate
    the antenna models and the core simulation pipeline.
    """
    progress_logger, verbose_logger, _ = setup_loggers()

    try:
        # Load the base near-field config to get all frequencies
        base_config = Config(base_dir, "configs/near_field_config.json")
        frequency_bands = base_config.get_antenna_config().keys()
        sorted_frequencies = sorted([int(f) for f in frequency_bands])

        console_logger = ConsoleLogger(progress_logger, verbose_logger)

        progress_logger.info(
            "--- Starting Full Free-Space Simulation Study ---",
            extra={"log_type": "header"},
        )

        for freq in sorted_frequencies:
            progress_logger.info(
                f"\n--- Running Free-Space Simulation for {freq} MHz ---",
                extra={"log_type": "header"},
            )
            temp_config_path = None
            try:
                temp_config_path = create_temp_config(base_config, freq)

                # Instantiate and run the study with the temporary config
                study = NearFieldStudy(config_filename=temp_config_path, gui=console_logger)
                study.run()

            except Exception as e:
                progress_logger.error(f"  - ERROR: An error occurred during the {freq} MHz simulation: {e}")
                verbose_logger.error(traceback.format_exc())
                continue  # Continue to the next simulation
            finally:
                # Clean up the temporary config file
                if temp_config_path and os.path.exists(temp_config_path):
                    os.remove(temp_config_path)

        progress_logger.info(
            "\n--- All Free-Space Simulations Finished ---",
            extra={"log_type": "success"},
        )

    finally:
        shutdown_loggers()


if __name__ == "__main__":
    main()
