import os
import traceback
from typing import TYPE_CHECKING

from ..logging_manager import add_simulation_log_handlers, remove_simulation_log_handlers
from ..results_extractor import ResultsExtractor
from ..setups.far_field_setup import FarFieldSetup
from ..utils import profile
from .base_study import BaseStudy

if TYPE_CHECKING:
    pass


class FarFieldStudy(BaseStudy):
    """Manages far-field simulation campaigns.

    Runs plane wave simulations across phantoms, frequencies, directions, and
    polarizations. Handles setup, run, and extraction phases with progress tracking.
    """

    def _run_study(self):
        """Executes the complete far-field study campaign.

        Iterates through all configured phantoms, frequencies, incident directions,
        and polarizations. For each combination, runs setup, simulation, and
        extraction. Tracks progress and validates execution control settings.
        """
        config_filename = os.path.basename(self.config.config_path)
        self._log(
            f"--- Starting Far-Field Study: {config_filename} ---",
            level="progress",
            log_type="header",
        )

        do_setup = self.config["execution_control.do_setup"]
        if do_setup is None:
            do_setup = True
        do_run = self.config["execution_control.do_run"]
        if do_run is None:
            do_run = True
        do_extract = self.config["execution_control.do_extract"]
        if do_extract is None:
            do_extract = True
        auto_cleanup = self.config.get_auto_cleanup_previous_results()

        # Warn about common misconfiguration
        if self.config.get_only_write_input_file() and not do_run:
            self._log(
                "WARNING: 'only_write_input_file' is set to true, but 'do_run' is false. "
                "The input file will NOT be written because the run phase is disabled. "
                "Set 'do_run: true' to write the input file.",
                level="progress",
                log_type="warning",
            )

        if not do_setup and not do_run and not do_extract:
            self._log(
                "All execution phases (setup, run, extract) are disabled in the config. Nothing to do.",
                log_type="warning",
            )
            return

        if not do_setup and do_run:
            self._log(
                "WARNING: Running simulations without setup is not a standard workflow and might lead to issues.",
                log_type="warning",
            )

        # Sanity check for auto_cleanup_previous_results
        self._validate_auto_cleanup_config(do_setup, do_run, do_extract, auto_cleanup)  # type: ignore

        phantoms = self.config["phantoms"] or []
        frequencies = self.config["frequencies_mhz"] or []
        far_field_params = self.config["far_field_setup.environmental"] or {}
        incident_directions = far_field_params.get("incident_directions", []) if far_field_params else []
        polarizations = far_field_params.get("polarizations", []) if far_field_params else []

        total_simulations = len(phantoms) * len(frequencies) * len(incident_directions) * len(polarizations)

        # Inform the profiler about the total number of simulations for accurate ETA
        self.profiler.set_total_simulations(total_simulations)

        # Give the profiler a hint about the first phase to avoid an initial "N/A" for ETA
        if do_setup:
            self.profiler.current_phase = "setup"
        elif do_run:
            self.profiler.current_phase = "run"
        elif do_extract:
            self.profiler.current_phase = "extract"

        simulation_count = 0
        for phantom_name in phantoms:  # type: ignore
            for freq in frequencies:  # type: ignore
                for direction_name in incident_directions:
                    for polarization_name in polarizations:
                        self._check_for_stop_signal()
                        simulation_count += 1
                        self._log(
                            f"\n--- Processing Simulation {simulation_count}/{total_simulations}: "
                            f"{phantom_name}, {freq}MHz, {direction_name}, {polarization_name} ---",
                            level="progress",
                            log_type="header",
                        )
                        if self.gui:
                            self.gui.update_simulation_details(
                                simulation_count,
                                total_simulations,
                                f"{phantom_name}, {freq}MHz, {direction_name}, {polarization_name}",
                            )
                        self._run_single_simulation(
                            phantom_name,
                            freq,
                            direction_name,
                            polarization_name,
                            do_setup,  # type: ignore
                            do_run,  # type: ignore
                            do_extract,  # type: ignore
                        )
                        self.profiler.simulation_completed()
                        if self.gui:
                            self.gui.update_overall_progress(simulation_count, total_simulations)

    def _run_single_simulation(
        self,
        phantom_name: str,
        freq: int,
        direction_name: str,
        polarization_name: str,
        do_setup: bool,
        do_run: bool,
        do_extract: bool,
    ):
        """Runs a full simulation for a single far-field case."""
        sim_log_handlers = None
        try:
            simulation = None

            # 1. Setup Phase
            if do_setup:
                with profile(self, "setup"):
                    verification_status = self.project_manager.create_or_open_project(
                        phantom_name,
                        freq,
                        "environmental",
                        polarization_name,
                        direction_name,
                    )
                    # Add simulation-specific log handlers after project directory is created
                    if self.project_manager.project_path:
                        project_dir = os.path.dirname(self.project_manager.project_path)
                        sim_log_handlers = add_simulation_log_handlers(project_dir)
                    needs_setup = not verification_status["setup_done"]

                    if needs_setup:
                        self.project_manager.create_new()

                        setup = FarFieldSetup(
                            self.config,
                            phantom_name,
                            freq,
                            direction_name,
                            polarization_name,
                            self.project_manager,
                            self.verbose_logger,
                            self.progress_logger,
                            self.profiler,
                            self.gui,
                        )

                        with self.subtask("setup_simulation", instance_to_profile=setup) as wrapper:
                            if wrapper:
                                simulation = wrapper(setup.run_full_setup)(self.project_manager)
                            else:
                                simulation = setup.run_full_setup(self.project_manager)

                        if not simulation:
                            self._log(
                                f"ERROR: Setup failed for {direction_name}_{polarization_name}. Cannot proceed.",
                                level="progress",
                                log_type="error",
                            )
                            return

                    # Always ensure metadata is written, even if setup is skipped
                    surgical_config = self.config.build_simulation_config(
                        phantom_name=phantom_name,
                        frequency_mhz=freq,
                        direction_name=direction_name,
                        polarization_name=polarization_name,
                    )
                    if self.project_manager.project_path:
                        self.project_manager.write_simulation_metadata(
                            os.path.join(os.path.dirname(self.project_manager.project_path), "config.json"),
                            surgical_config,
                        )

                    # Update do_run and do_extract based on verification
                    if verification_status["run_done"]:
                        do_run = False
                        self._log("Skipping run phase, deliverables found.", log_type="info")
                    if verification_status["extract_done"]:
                        do_extract = False
                        self._log("Skipping extract phase, deliverables found.", log_type="info")

                    if self.gui:
                        self.gui.update_stage_progress("Setup", 1, 1)
            else:
                verification_status = self.project_manager.create_or_open_project(
                    phantom_name,
                    freq,
                    "environmental",
                    polarization_name,
                    direction_name,
                )
                # Add simulation-specific log handlers after project directory is created
                if self.project_manager.project_path:
                    project_dir = os.path.dirname(self.project_manager.project_path)
                    sim_log_handlers = add_simulation_log_handlers(project_dir)

            import s4l_v1.document

            if s4l_v1.document.AllSimulations:
                sim_name = f"EM_FDTD_{phantom_name}_{freq}MHz_{direction_name}_{polarization_name}"
                simulation = next(
                    (s for s in s4l_v1.document.AllSimulations if s.Name == sim_name),
                    None,
                )

            if not simulation:
                self._log(
                    f"ERROR: No simulation found for {direction_name}_{polarization_name}.",
                    log_type="error",
                )
                return

            # 2. Run Phase
            if do_run:
                with profile(self, "run"):
                    self._execute_run_phase(simulation)  # type: ignore

            # 3. Extraction Phase
            if do_extract:
                with profile(self, "extract"):
                    # Verify run deliverables exist before starting extraction
                    if not self._verify_run_deliverables_before_extraction():
                        self._log(
                            f"Skipping extraction for {direction_name}_{polarization_name} - run deliverables not found.",
                            log_type="warning",
                        )
                        return

                    self.project_manager.reload_project()
                    sim_name = simulation.Name
                    reloaded_simulation = next(
                        (s for s in s4l_v1.document.AllSimulations if s.Name == sim_name),
                        None,
                    )
                    if not reloaded_simulation:
                        raise RuntimeError(f"Could not find simulation '{sim_name}' after reloading.")

                    with self.subtask("extract_results_total"):
                        extractor = ResultsExtractor.from_params(
                            config=self.config,
                            simulation=reloaded_simulation,  # type: ignore
                            phantom_name=phantom_name,
                            frequency_mhz=freq,
                            scenario_name="environmental",
                            position_name=polarization_name,
                            orientation_name=direction_name,
                            study_type="far_field",
                            verbose_logger=self.verbose_logger,
                            progress_logger=self.progress_logger,
                            gui=self.gui,  # type: ignore
                            study=self,
                        )
                        extractor.extract()
                    self._verify_and_update_metadata("extract")
                    self.project_manager.save()
                    if self.gui:
                        self.gui.update_stage_progress("Extracting Results", 1, 1)

        except Exception as e:
            self._log(f"ERROR during simulation: {e}", log_type="error")
            self.verbose_logger.error(traceback.format_exc())
        finally:
            # Remove simulation-specific log handlers
            if sim_log_handlers:
                remove_simulation_log_handlers(sim_log_handlers)
            if self.project_manager and hasattr(self.project_manager.document, "IsOpen") and self.project_manager.document.IsOpen():  # type: ignore
                self.project_manager.close()

    def _validate_auto_cleanup_config(self, do_setup: bool, do_run: bool, do_extract: bool, auto_cleanup: list):
        """Validates the auto_cleanup_previous_results configuration."""
        if not auto_cleanup:
            return

        if not (do_setup and do_run and do_extract):
            self._log(
                "WARNING: 'auto_cleanup_previous_results' is enabled, but not all phases are active.",
                log_type="warning",
            )

        batch_run = self.config["execution_control.batch_run"] or False
        if batch_run:
            self._log(
                "ERROR: 'auto_cleanup_previous_results' is not compatible with 'batch_run'. Disabling.",
                log_type="error",
            )
            self.config.config["execution_control"]["auto_cleanup_previous_results"] = []

        cleanup_types = self.config.get_auto_cleanup_previous_results()
        if cleanup_types:
            self._log(f"Auto-cleanup enabled for: {', '.join(cleanup_types)}", log_type="info")
