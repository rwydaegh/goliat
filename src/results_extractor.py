import json
import os

from .extraction.cleaner import Cleaner
from .extraction.json_encoder import NumpyArrayEncoder
from .extraction.power_extractor import PowerExtractor
from .extraction.reporter import Reporter
from .extraction.sar_extractor import SarExtractor
from .extraction.sensor_extractor import SensorExtractor
from .logging_manager import LoggingMixin


class ResultsExtractor(LoggingMixin):
    """
    Orchestrates post-processing and data extraction from simulation results.

    This class coordinates specialized extraction modules to extract input power,
    SAR statistics, power balance, and point sensor data from a completed
    Sim4Life simulation. It also manages report generation and file cleanup.
    """

    def __init__(
        self,
        config,
        simulation,
        phantom_name,
        frequency_mhz,
        scenario_name,
        position_name,
        orientation_name,
        study_type,
        verbose_logger,
        progress_logger,
        free_space=False,
        gui=None,
        study=None,
    ):
        """
        Initializes the ResultsExtractor.

        Args:
            config (Config): The configuration object for the study.
            simulation (s4l_v1.simulation.emfdtd.Simulation): The simulation object to extract results from.
            phantom_name (str): The name of the phantom model used.
            frequency_mhz (int): The simulation frequency in MHz.
            scenario_name (str): The base name of the placement scenario.
            position_name (str): The name of the position within the scenario.
            orientation_name (str): The name of the orientation within the scenario.
            study_type (str): The type of the study (e.g., 'near_field').
            verbose_logger (logging.Logger): Logger for detailed output.
            progress_logger (logging.Logger): Logger for progress updates.
            free_space (bool): Flag indicating if the simulation was run in free space.
            gui (QueueGUI, optional): The GUI proxy for updates.
            study (BaseStudy, optional): The parent study object.
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

    def extract(self):
        """
        Orchestrates the extraction of all relevant data from the simulation.

        This is the main entry point for the class, which coordinates specialized
        extraction modules to extract input power, SAR statistics, power balance,
        and point sensor data, then saves the compiled results.
        """
        self._log("Extracting results...", log_type="progress")
        if not self.simulation:
            self._log(
                "  - ERROR: Simulation object not found. Skipping result extraction.",
                log_type="error",
            )
            return

        results_data = {}
        simulation_extractor = self.simulation.Results()

        # Extract power data
        if self.gui:
            self.gui.update_stage_progress("Extracting Power", 50, 100)

        power_extractor = PowerExtractor(self, results_data)
        power_extractor.extract_input_power(simulation_extractor)

        # Extract SAR data (non-free-space only)
        if not self.free_space:
            if self.gui:
                self.gui.update_stage_progress("Extracting SAR", 100, 100)

            sar_extractor = SarExtractor(self, results_data)
            sar_extractor.extract_sar_statistics(simulation_extractor)
            power_extractor.extract_power_balance(simulation_extractor)
        else:
            self._log(
                "  - Skipping SAR statistics for free-space simulation.",
                log_type="info",
            )

        # Extract point sensor data
        if (
            self.config.get_setting("simulation_parameters.number_of_point_sensors", 0)
            > 0
        ):
            if self.gui:
                self.gui.update_stage_progress("Extracting Point Sensors", 75, 100)

            sensor_extractor = SensorExtractor(self, results_data)
            sensor_extractor.extract_point_sensor_data(simulation_extractor)

        # Save reports
        if not self.free_space and "_temp_sar_df" in results_data:
            reporter = Reporter(self)
            reporter.save_reports(
                results_data.pop("_temp_sar_df"),
                results_data.pop("_temp_tissue_groups"),
                results_data.pop("_temp_group_sar_stats"),
                results_data,
            )

        # Save JSON results
        self._save_json_results(results_data)

        # Cleanup if configured
        if self.config.get_auto_cleanup_previous_results():
            cleaner = Cleaner(self)
            cleaner.cleanup_simulation_files()

    def _save_json_results(self, results_data):
        """Save the final results to JSON format."""
        results_dir = os.path.join(
            self.config.base_dir,
            "results",
            self.study_type,
            self.phantom_name,
            f"{self.frequency_mhz}MHz",
            self.placement_name,
        )
        os.makedirs(results_dir, exist_ok=True)
        results_filepath = os.path.join(results_dir, "sar_results.json")

        final_results_data = {
            k: v for k, v in results_data.items() if not k.startswith("_temp")
        }

        with open(results_filepath, "w") as f:
            json.dump(final_results_data, f, indent=4, cls=NumpyArrayEncoder)

        self._log(f"  - SAR results saved to: {results_filepath}", log_type="info")
