import json
import os
from typing import TYPE_CHECKING, Optional

from .extraction.cleaner import Cleaner
from .extraction.json_encoder import NumpyArrayEncoder
from .extraction.power_extractor import PowerExtractor
from .extraction.reporter import Reporter
from .extraction.sar_extractor import SarExtractor
from .extraction.sensor_extractor import SensorExtractor
from .logging_manager import LoggingMixin

if TYPE_CHECKING:
    from logging import Logger

    import s4l_v1.simulation.emfdtd

    from .config import Config
    from .gui_manager import QueueGUI
    from .studies.base_study import BaseStudy


class ResultsExtractor(LoggingMixin):
    """Orchestrates post-processing and data extraction from simulation results.

    Coordinates modules to extract power, SAR, and sensor data from a
    Sim4Life simulation, then manages report generation and cleanup.
    """

    def __init__(
        self,
        config: "Config",
        simulation: "s4l_v1.simulation.emfdtd.Simulation",
        phantom_name: str,
        frequency_mhz: int,
        scenario_name: str,
        position_name: str,
        orientation_name: str,
        study_type: str,
        verbose_logger: "Logger",
        progress_logger: "Logger",
        free_space: bool = False,
        gui: "Optional[QueueGUI]" = None,
        study: "Optional[BaseStudy]" = None,
    ):
        """Initializes the ResultsExtractor.

        Args:
            config: The configuration object for the study.
            simulation: The simulation object to extract results from.
            phantom_name: The name of the phantom model used.
            frequency_mhz: The simulation frequency in MHz.
            scenario_name: The base name of the placement scenario.
            position_name: The name of the position within the scenario.
            orientation_name: The name of the orientation within the scenario.
            study_type: The type of the study (e.g., 'near_field').
            verbose_logger: Logger for detailed output.
            progress_logger: Logger for progress updates.
            free_space: Flag indicating if the simulation was run in free space.
            gui: The GUI proxy for updates.
            study: The parent study object.
        """
        self.config = config
        self.simulation = simulation
        self.phantom_name = phantom_name
        self.frequency_mhz = frequency_mhz
        self.placement_name = f"{scenario_name}_{position_name}_{orientation_name}"
        self.orientation_name = orientation_name
        self.study_type = study_type
        self.verbose_logger = verbose_logger
        self.progress_logger = progress_logger
        self.free_space = free_space
        self.gui = gui
        self.study = study

        import s4l_v1.analysis
        import s4l_v1.document
        import s4l_v1.units as units

        self.document = s4l_v1.document
        self.analysis = s4l_v1.analysis
        self.units = units

    @staticmethod
    def get_deliverable_filenames() -> dict:
        """Returns a dictionary of deliverable filenames."""
        return {
            "json": "sar_results.json",
            "pkl": "sar_stats_all_tissues.pkl",
            "html": "sar_stats_all_tissues.html",
        }

    def extract(self):
        """Orchestrates the extraction of all relevant data from the simulation.

        This is the main entry point for the class. It coordinates extraction
        modules for power, SAR, and sensor data, then saves the results.
        """
        if not self.simulation:
            self._log(
                "ERROR: Simulation object not found. Skipping result extraction.",
                level="progress",
                log_type="error",
            )
            return

        results_data = {}
        simulation_extractor = self.simulation.Results()

        # --- Extraction Steps with detailed logging ---
        self._log("    - Extract input power...", level="progress", log_type="progress")
        if self.study:
            with self.study.profiler.subtask("extract_input_power"):
                power_extractor = PowerExtractor(self, results_data)
                power_extractor.extract_input_power(simulation_extractor)
            self._log(
                f"      - Subtask 'extract_input_power' done in {self.study.profiler.subtask_times['extract_input_power'][-1]:.2f}s",
                level="progress",
                log_type="success",
            )
        else:
            power_extractor = PowerExtractor(self, results_data)
            power_extractor.extract_input_power(simulation_extractor)

        if not self.free_space:
            self._log("    - Extract SAR statistics...", level="progress", log_type="progress")
            if self.study:
                with self.study.profiler.subtask("extract_sar_statistics"):
                    sar_extractor = SarExtractor(self, results_data)
                    sar_extractor.extract_sar_statistics(simulation_extractor)
                self._log(
                    f"      - Subtask 'extract_sar_statistics' done in {self.study.profiler.subtask_times['extract_sar_statistics'][-1]:.2f}s",
                    level="progress",
                    log_type="success",
                )
            else:
                sar_extractor = SarExtractor(self, results_data)
                sar_extractor.extract_sar_statistics(simulation_extractor)

            self._log("    - Extract power balance...", level="progress", log_type="progress")
            if self.study:
                with self.study.profiler.subtask("extract_power_balance"):
                    power_extractor.extract_power_balance(simulation_extractor)
                self._log(
                    f"      - Subtask 'extract_power_balance' done in {self.study.profiler.subtask_times['extract_power_balance'][-1]:.2f}s",
                    level="progress",
                    log_type="success",
                )
            else:
                power_extractor.extract_power_balance(simulation_extractor)

        if self.config.get_setting("simulation_parameters.number_of_point_sensors", 0) > 0:
            self._log("    - Extract point sensors...", level="progress", log_type="progress")
            if self.study:
                with self.study.profiler.subtask("extract_point_sensor_data"):
                    sensor_extractor = SensorExtractor(self, results_data)
                    sensor_extractor.extract_point_sensor_data(simulation_extractor)
                self._log(
                    f"      - Subtask 'extract_point_sensor_data' done in {self.study.profiler.subtask_times['extract_point_sensor_data'][-1]:.2f}s",
                    level="progress",
                    log_type="success",
                )
            else:
                sensor_extractor = SensorExtractor(self, results_data)
                sensor_extractor.extract_point_sensor_data(simulation_extractor)

        if not self.free_space and "_temp_sar_df" in results_data:
            self._log("    - Generate reports...", level="progress", log_type="progress")
            if self.study:
                with self.study.profiler.subtask("generate_reports"):
                    reporter = Reporter(self)
                    reporter.save_reports(
                        results_data.pop("_temp_sar_df"),
                        results_data.pop("_temp_tissue_groups"),
                        results_data.pop("_temp_group_sar_stats"),
                        results_data,
                    )
                self._log(
                    f"      - Subtask 'generate_reports' done in {self.study.profiler.subtask_times['generate_reports'][-1]:.2f}s",
                    level="progress",
                    log_type="success",
                )
            else:
                reporter = Reporter(self)
                reporter.save_reports(
                    results_data.pop("_temp_sar_df"),
                    results_data.pop("_temp_tissue_groups"),
                    results_data.pop("_temp_group_sar_stats"),
                    results_data,
                )

        self._log("    - Save JSON results...", level="progress", log_type="progress")
        if self.study:
            with self.study.profiler.subtask("save_json_results"):
                self._save_json_results(results_data)
            self._log(
                f"      - Subtask 'save_json_results' done in {self.study.profiler.subtask_times['save_json_results'][-1]:.2f}s",
                level="progress",
                log_type="success",
            )
        else:
            self._save_json_results(results_data)

        # Cleanup if configured
        if self.config.get_auto_cleanup_previous_results():
            cleaner = Cleaner(self)
            cleaner.cleanup_simulation_files()

    def _save_json_results(self, results_data: dict):
        """Saves the final results to a JSON file."""
        reporter = Reporter(self)
        results_dir = reporter._get_results_dir()
        os.makedirs(results_dir, exist_ok=True)
        deliverables = self.get_deliverable_filenames()
        results_filepath = os.path.join(results_dir, deliverables["json"])

        final_results_data = {k: v for k, v in results_data.items() if not k.startswith("_temp")}

        with open(results_filepath, "w") as f:
            json.dump(final_results_data, f, indent=4, cls=NumpyArrayEncoder)

        self._log(f"  - SAR results saved to: {results_filepath}", log_type="info")
