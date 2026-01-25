import json
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from .extraction.cleaner import Cleaner
from .extraction.json_encoder import NumpyArrayEncoder
from .extraction.power_extractor import PowerExtractor
from .extraction.reporter import Reporter
from .extraction.resonance_extractor import ResonanceExtractor
from .extraction.sapd_extractor import SapdExtractor
from .extraction.sar_extractor import SarExtractor
from .extraction.sensor_extractor import SensorExtractor
from .logging_manager import LoggingMixin

if TYPE_CHECKING:
    from logging import Logger

    import s4l_v1.simulation.emfdtd

    from .config import Config
    from .gui_manager import QueueGUI
    from .studies.base_study import BaseStudy


@dataclass
class ExtractionContext:
    """Context object containing all parameters needed for result extraction.

    Groups related parameters together to reduce the parameter count of ResultsExtractor.__init__.
    """

    config: "Config"
    simulation: "s4l_v1.simulation.emfdtd.Simulation"
    phantom_name: str
    frequency_mhz: int | list[int]
    scenario_name: str
    position_name: str
    orientation_name: str
    study_type: str
    verbose_logger: "Logger"
    progress_logger: "Logger"
    free_space: bool = False
    gui: "Optional[QueueGUI]" = None
    study: "Optional[BaseStudy]" = None


class ResultsExtractor(LoggingMixin):
    """Orchestrates post-processing and data extraction from simulation results.

    Coordinates modules to extract power, SAR, and sensor data from a
    Sim4Life simulation, then manages report generation and cleanup.
    """

    def __init__(self, context: ExtractionContext):
        """Initializes the ResultsExtractor.

        Args:
            context: ExtractionContext containing all extraction parameters.
        """
        self.config = context.config
        self.simulation = context.simulation
        self.phantom_name = context.phantom_name
        self.frequency_mhz = context.frequency_mhz
        self.scenario_name = context.scenario_name
        self.position_name = context.position_name  # For far-field: direction. For near-field: position.
        self.placement_name = f"{context.scenario_name}_{context.position_name}_{context.orientation_name}"
        self.orientation_name = context.orientation_name  # For far-field: polarization. For near-field: orientation.
        self.study_type = context.study_type
        self.verbose_logger = context.verbose_logger
        self.progress_logger = context.progress_logger
        self.free_space = context.free_space
        self.gui = context.gui
        self.study = context.study

        import s4l_v1.analysis
        import s4l_v1.document
        import s4l_v1.units as units

        self.document = s4l_v1.document
        self.analysis = s4l_v1.analysis
        self.units = units

    @classmethod
    def from_params(
        cls,
        config: "Config",
        simulation: "s4l_v1.simulation.emfdtd.Simulation",
        phantom_name: str,
        frequency_mhz: int | list[int],
        scenario_name: str,
        position_name: str,
        orientation_name: str,
        study_type: str,
        verbose_logger: "Logger",
        progress_logger: "Logger",
        free_space: bool = False,
        gui: "Optional[QueueGUI]" = None,
        study: "Optional[BaseStudy]" = None,
    ) -> "ResultsExtractor":
        """Creates a ResultsExtractor from individual parameters.

        Factory method for backward compatibility. Creates an ExtractionContext
        and initializes the extractor with it.

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

        Returns:
            A new ResultsExtractor instance.
        """
        context = ExtractionContext(
            config=config,
            simulation=simulation,
            phantom_name=phantom_name,
            frequency_mhz=frequency_mhz,
            scenario_name=scenario_name,
            position_name=position_name,
            orientation_name=orientation_name,
            study_type=study_type,
            verbose_logger=verbose_logger,
            progress_logger=progress_logger,
            free_space=free_space,
            gui=gui,
            study=study,
        )
        return cls(context)

    def _get_extraction_flag(self, flag_name: str, default: bool = True) -> bool:
        """Gets an extraction flag value with backward compatibility.

        Checks both new 'extraction.{flag}' and legacy 'extract_{flag}' config keys.

        Args:
            flag_name: Name of the extraction flag (e.g., 'sar', 'power_balance', 'sapd').
            default: Default value if flag is not set in config.

        Returns:
            Boolean value of the extraction flag.
        """
        # Try new structure first: extraction.{flag_name}
        new_value = self.config[f"extraction.{flag_name}"]
        if new_value is not None:
            return bool(new_value)

        # Try legacy structure: extract_{flag_name}
        legacy_value = self.config[f"extract_{flag_name}"]
        if legacy_value is not None:
            return bool(legacy_value)

        # Return default
        return default

    @staticmethod
    def get_required_deliverable_filenames() -> dict:
        """Returns the required deliverable filenames that must exist for extract to be considered done.

        These are the core files that are always generated during extraction.
        """
        return {
            "json": "sar_results.json",
            "pkl": "sar_stats_all_tissues.pkl",
            "html": "sar_stats_all_tissues.html",
        }

    @staticmethod
    def get_optional_deliverable_filenames() -> dict:
        """Returns optional deliverable filenames that may or may not be generated.

        These files are only created when specific extraction features are enabled
        (e.g., SAPD extraction).
        """
        return {
            "sapd_json": "sapd_results.json",
        }

    @staticmethod
    def get_deliverable_filenames() -> dict:
        """Returns all deliverable filenames (required + optional).

        For backward compatibility and file uploads.
        """
        return {
            **ResultsExtractor.get_required_deliverable_filenames(),
            **ResultsExtractor.get_optional_deliverable_filenames(),
        }

    def extract(self):
        """Extracts all data from simulation results and saves outputs.

        Coordinates power extraction, SAR statistics, power balance, and optional
        point sensors. Generates reports (Pickle/HTML) and saves JSON results.
        Optionally cleans up simulation files if auto-cleanup is enabled.
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

        # --- Extraction Steps (orchestrated by extraction modules) ---
        power_extractor = PowerExtractor(self, results_data)
        power_extractor.extract_input_power(simulation_extractor)

        # Extract resonance frequency for Gaussian excitation
        excitation_type = self.config["simulation_parameters.excitation_type"] or "Harmonic"
        excitation_type_lower = excitation_type.lower() if isinstance(excitation_type, str) else "harmonic"
        if excitation_type_lower == "gaussian":
            resonance_extractor = ResonanceExtractor(self, results_data)
            resonance_data = resonance_extractor.extract_resonance_frequency(simulation_extractor)
            if resonance_data:
                results_data.update(resonance_data)

                # Update detuning file if calibration write is enabled
                if self.config.detuning_write_during_calibration and not self.free_space:
                    detuning_mhz = resonance_data.get("detuning_mhz", 0.0)
                    self.config.update_detuning_file(
                        self.phantom_name,
                        self.frequency_mhz,
                        self.placement_name,
                        detuning_mhz,
                    )

        if not self.free_space:
            # Check if SAR extraction is enabled (defaults to True for backward compatibility)
            extract_sar = self._get_extraction_flag("sar", default=True)
            if extract_sar:
                sar_extractor = SarExtractor(self, results_data)
                sar_extractor.extract_sar_statistics(simulation_extractor)
            else:
                self._log("    - SAR extraction disabled by config", level="progress", log_type="info")

            # Check if power balance extraction is enabled (defaults to True for backward compatibility)
            extract_power_balance = self._get_extraction_flag("power_balance", default=True)
            if extract_power_balance:
                power_extractor.extract_power_balance(simulation_extractor)
            else:
                self._log("    - Power balance extraction disabled by config", level="progress", log_type="info")

            # Check if SAPD extraction is enabled (defaults to False)
            extract_sapd = self._get_extraction_flag("sapd", default=False)
            if extract_sapd:
                sapd_extractor = SapdExtractor(self, results_data)
                sapd_extractor.extract_sapd(simulation_extractor)

        # Check if point sensors are configured AND extraction is enabled
        num_sensors_value = self.config["simulation_parameters.number_of_point_sensors"]
        num_sensors = int(num_sensors_value) if isinstance(num_sensors_value, (int, float)) else 0
        extract_point_sensors = self._get_extraction_flag("point_sensors", default=True)
        if num_sensors > 0 and extract_point_sensors:
            sensor_extractor = SensorExtractor(self, results_data)
            sensor_extractor.extract_point_sensor_data(simulation_extractor)
        elif num_sensors > 0 and not extract_point_sensors:
            self._log("    - Point sensor extraction disabled by config", level="progress", log_type="info")

        # Only generate reports if SAR data was extracted
        extract_sar = self._get_extraction_flag("sar", default=True)
        if not self.free_space and "_temp_sar_df" in results_data and extract_sar:
            reporter = Reporter(self)
            reporter.save_reports(
                results_data.pop("_temp_sar_df"),
                results_data.pop("_temp_tissue_groups"),
                results_data.pop("_temp_group_sar_stats"),
                results_data,
            )

        self._save_json_results(results_data)

        # Export simulation metadata before cleanup (to capture file sizes)
        if self.study and hasattr(self.study, "profiler") and hasattr(self.study, "project_manager"):
            if self.study.project_manager.project_path:
                from goliat.metadata_exporter import export_simulation_metadata

                # Build simulation name
                if self.study_type == "far_field":
                    # For far-field: EM_FDTD_{phantom}_{freq}MHz_{direction}_{polarization}
                    # position_name = direction, orientation_name = polarization
                    sim_name = f"EM_FDTD_{self.phantom_name}_{self.frequency_mhz}MHz_{self.position_name}_{self.orientation_name}"
                else:
                    # For near-field: EM_FDTD_{phantom}_{freq}MHz_{placement}
                    sim_name = f"EM_FDTD_{self.phantom_name}_{self.frequency_mhz}MHz_{self.placement_name}"

                export_simulation_metadata(
                    profiler=self.study.profiler,
                    project_path=self.study.project_manager.project_path,
                    simulation_name=sim_name,
                    study_type=self.study_type,
                    phantom_name=self.phantom_name,
                    frequency_mhz=self.frequency_mhz,
                    config_path=self.config.config_path,
                    extract_sar=self._get_extraction_flag("sar", default=True),
                    extract_sapd=self._get_extraction_flag("sapd", default=False),
                )

        # Cleanup if configured
        if self.config.get_auto_cleanup_previous_results():
            cleaner = Cleaner(self)
            cleaner.cleanup_simulation_files()

    def _save_json_results(self, results_data: dict):
        """Saves final results to JSON, excluding temporary helper data and point_sensor_data.

        When SAR extraction is disabled, creates minimal placeholder files so the
        caching system still recognizes the extraction as complete.
        """
        reporter = Reporter(self)
        results_dir = reporter._get_results_dir()
        os.makedirs(results_dir, exist_ok=True)
        deliverables = self.get_deliverable_filenames()

        # Save SAPD results separately if present
        if "sapd_results" in results_data:
            sapd_filepath = os.path.join(results_dir, deliverables["sapd_json"])
            with open(sapd_filepath, "w") as f:
                json.dump(results_data["sapd_results"], f, indent=4, cls=NumpyArrayEncoder)
            self._log(f"  - SAPD results saved to: {sapd_filepath}", log_type="info")

        results_filepath = os.path.join(results_dir, deliverables["json"])

        final_results_data = {
            k: v for k, v in results_data.items() if not k.startswith("_temp") and k != "point_sensor_data" and k != "sapd_results"
        }

        # Check if SAR extraction was disabled
        extract_sar = self._get_extraction_flag("sar", default=True)
        if not extract_sar:
            # Add a flag indicating SAR was disabled
            final_results_data["sar_extraction_disabled"] = True

            # Create placeholder files for caching to work
            import pickle

            pkl_filepath = os.path.join(results_dir, deliverables["pkl"])
            with open(pkl_filepath, "wb") as f:
                pickle.dump({"sar_extraction_disabled": True, "note": "SAR extraction was disabled by config"}, f)
            self._log(f"  - Created placeholder PKL file: {pkl_filepath}", log_type="info")

            html_filepath = os.path.join(results_dir, deliverables["html"])
            with open(html_filepath, "w") as f:
                f.write(
                    "<html><body><h1>SAR extraction disabled</h1><p>SAR extraction was disabled in the configuration (extract_sar: false).</p></body></html>"
                )
            self._log(f"  - Created placeholder HTML file: {html_filepath}", log_type="info")

        with open(results_filepath, "w") as f:
            json.dump(final_results_data, f, indent=4, cls=NumpyArrayEncoder)

        self._log(f"  - SAR results saved to: {results_filepath}", log_type="info")
