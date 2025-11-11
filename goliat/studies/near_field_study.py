import os
import traceback
from typing import TYPE_CHECKING

from ..antenna import Antenna
from ..logging_manager import add_simulation_log_handlers, remove_simulation_log_handlers
from ..results_extractor import ResultsExtractor
from ..setups.near_field_setup import NearFieldSetup
from ..utils import profile
from .base_study import BaseStudy

if TYPE_CHECKING:
    pass


class NearFieldStudy(BaseStudy):
    """Manages near-field simulation campaigns.

    Runs simulations across phantoms, frequencies, placements, positions, and
    orientations. Handles setup, run, and extraction phases with progress
    tracking and metadata verification.
    """

    def _run_study(self):
        """Executes the complete near-field study campaign.

        Iterates through all configured phantoms, frequencies, placement scenarios,
        positions, and orientations. For each combination, runs setup, simulation,
        and extraction. Tracks progress and validates cleanup config.
        """
        config_filename = os.path.basename(self.config.config_path)
        self._log(
            f"--- Starting Near-Field Study: {config_filename} ---",
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
                "All execution phases (setup, run, extract) are disabled. Nothing to do.",
                log_type="warning",
            )
            return

        # Sanity check for auto_cleanup_previous_results
        self._validate_auto_cleanup_config(do_setup, do_run, do_extract, auto_cleanup)  # type: ignore

        phantoms = self.config["phantoms"] or []
        if not isinstance(phantoms, list):
            phantoms = [phantoms]
        frequencies = (self.config["antenna_config"] or {}).keys()  # type: ignore
        all_scenarios = self.config["placement_scenarios"] or {}

        # Calculate total number of simulations for the profiler
        total_simulations = 0
        for phantom_name in phantoms:
            phantom_definition = (self.config["phantom_definitions"] or {}).get(phantom_name, {})  # type: ignore
            placements_config = phantom_definition.get("placements", {})
            if not placements_config:
                continue
            for scenario_name, scenario_details in all_scenarios.items():  # type: ignore
                if placements_config.get(f"do_{scenario_name}"):
                    positions = scenario_details.get("positions", {})
                    orientations = scenario_details.get("orientations", {})
                    total_simulations += len(list(frequencies)) * len(positions) * len(orientations)  # type: ignore

        self.profiler.set_total_simulations(total_simulations)
        if do_setup:
            self.profiler.current_phase = "setup"
        elif do_run:
            self.profiler.current_phase = "run"
        elif do_extract:
            self.profiler.current_phase = "extract"

        simulation_count = 0
        for phantom_name in phantoms:
            phantom_definition = (self.config["phantom_definitions"] or {}).get(phantom_name, {})  # type: ignore
            placements_config = phantom_definition.get("placements", {})
            if not placements_config:
                continue

            for freq_str in frequencies:
                freq = int(freq_str)
                for scenario_name, scenario_details in all_scenarios.items():  # type: ignore
                    if placements_config.get(f"do_{scenario_name}"):
                        positions = scenario_details.get("positions", {})
                        orientations = scenario_details.get("orientations", {})
                        for pos_name in positions.keys():  # type: ignore
                            for orient_name in orientations.keys():  # type: ignore
                                self._check_for_stop_signal()
                                simulation_count += 1
                                placement_name = f"{scenario_name}_{pos_name}_{orient_name}"
                                self._log(
                                    f"\n--- Processing Simulation {simulation_count}/{total_simulations}: "
                                    f"{phantom_name}, {freq}MHz, {placement_name} ---",
                                    level="progress",
                                    log_type="header",
                                )
                                if self.gui:
                                    self.gui.update_simulation_details(
                                        simulation_count,
                                        total_simulations,
                                        f"{phantom_name}, {freq}MHz, {placement_name}",
                                    )
                                self._run_placement(
                                    phantom_name,  # type: ignore
                                    freq,
                                    scenario_name,
                                    pos_name,
                                    orient_name,
                                    do_setup,  # type: ignore
                                    do_run,  # type: ignore
                                    do_extract,  # type: ignore
                                )
                                self.profiler.simulation_completed()
                                if self.gui:
                                    self.gui.update_overall_progress(simulation_count, total_simulations)

    def _validate_auto_cleanup_config(self, do_setup: bool, do_run: bool, do_extract: bool, auto_cleanup: list):
        """Validates the auto_cleanup_previous_results configuration.

        Args:
            do_setup: Whether setup phase is enabled.
            do_run: Whether run phase is enabled.
            do_extract: Whether extract phase is enabled.
            auto_cleanup: List of file types to clean up.
        """
        if not auto_cleanup:
            return

        # Check if this is a proper serial workflow (all phases enabled)
        if not (do_setup and do_run and do_extract):
            self._log(
                "WARNING: 'auto_cleanup_previous_results' is enabled, but not all phases "
                "(setup, run, extract) are active. This may cause data loss if you're running "
                "phases separately!",
                level="progress",
                log_type="warning",
            )
            self._log(
                "  Recommendation: Only use auto_cleanup when running complete serial workflows "
                "where do_setup=true, do_run=true, and do_extract=true.",
                level="progress",
                log_type="info",
            )

        # Check for batch/parallel run mode
        batch_run = self.config["execution_control.batch_run"] or False
        if batch_run:
            self._log(
                "ERROR: 'auto_cleanup_previous_results' is enabled alongside 'batch_run'. "
                "This combination can cause data corruption in parallel execution!",
                level="progress",
                log_type="error",
            )
            self._log(
                "  Auto-cleanup will be DISABLED for safety. Please set "
                "'auto_cleanup_previous_results' to [] in your config when using batch mode.",
                level="progress",
                log_type="warning",
            )
            # Force disable auto-cleanup to prevent data corruption
            self.config.config["execution_control"]["auto_cleanup_previous_results"] = []

        # Inform user that auto-cleanup is active
        cleanup_types = self.config.get_auto_cleanup_previous_results()
        if cleanup_types:
            file_type_names = {
                "output": "output files (*_Output.h5)",
                "input": "input files (*_Input.h5)",
                "smash": "project files (*.smash)",
            }
            cleanup_descriptions = [file_type_names.get(t, t) for t in cleanup_types]  # type: ignore
            self._log(
                f"Auto-cleanup enabled: {', '.join(filter(None, cleanup_descriptions))} will be "
                "deleted after each simulation's results are extracted to save disk space.",
                level="progress",
                log_type="info",
            )

    def _run_placement(
        self,
        phantom_name: str,
        freq: int,
        scenario_name: str,
        position_name: str,
        orientation_name: str,
        do_setup: bool,
        do_run: bool,
        do_extract: bool,
    ):
        """Runs a full placement scenario for a single position and orientation."""
        placement_name = f"{scenario_name}_{position_name}_{orientation_name}"
        try:
            simulation = None

            # 1. Setup Simulation
            sim_log_handlers = None
            if do_setup:
                with profile(self, "setup"):
                    verification_status = self.project_manager.create_or_open_project(
                        phantom_name, freq, scenario_name, position_name, orientation_name
                    )
                    # Add simulation-specific log handlers after project directory is created
                    if self.project_manager.project_path:
                        project_dir = os.path.dirname(self.project_manager.project_path)
                        sim_log_handlers = add_simulation_log_handlers(project_dir)
                    needs_setup = not verification_status["setup_done"]

                    if needs_setup:
                        self.project_manager.create_new()
                        antenna = Antenna(self.config, freq)
                        setup = NearFieldSetup(
                            self.config,
                            phantom_name,
                            freq,
                            scenario_name,
                            position_name,
                            orientation_name,
                            antenna,
                            self.verbose_logger,
                            self.progress_logger,
                            self.profiler,
                            self.gui,
                        )

                        with self.subtask("setup_simulation", instance_to_profile=setup):
                            simulation = setup.run_full_setup(self.project_manager)

                        if not simulation:
                            self._log(f"ERROR: Setup failed for {placement_name}.", level="progress", log_type="error")
                            return

                    # Always ensure metadata is written, even if setup is skipped
                    surgical_config = self.config.build_simulation_config(
                        phantom_name=phantom_name,
                        frequency_mhz=freq,
                        scenario_name=scenario_name,
                        position_name=position_name,
                        orientation_name=orientation_name,
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
                    phantom_name, freq, scenario_name, position_name, orientation_name
                )
                # Add simulation-specific log handlers after project directory is created
                if self.project_manager.project_path:
                    project_dir = os.path.dirname(self.project_manager.project_path)
                    sim_log_handlers = add_simulation_log_handlers(project_dir)

            # ALWAYS get a fresh simulation handle from the document before run/extract
            import s4l_v1.document

            if s4l_v1.document.AllSimulations:
                sim_name = f"EM_FDTD_{phantom_name}_{freq}MHz_{placement_name}"
                simulation = next(
                    (s for s in s4l_v1.document.AllSimulations if s.Name == sim_name),
                    None,
                )

            if not simulation:
                self._log(
                    f"ERROR: No simulation found or created for {placement_name}. Cannot proceed.",
                    level="progress",
                    log_type="error",
                )
                return

            # 2. Run Simulation
            if do_run:
                with profile(self, "run"):
                    self._execute_run_phase(simulation)  # type: ignore

            # 3. Extract Results
            if do_extract:
                with profile(self, "extract"):
                    # Verify run deliverables exist before starting extraction
                    if not self._verify_run_deliverables_before_extraction():
                        self._log(
                            f"Skipping extraction for {placement_name} - run deliverables not found.",
                            log_type="warning",
                        )
                        return

                    self.project_manager.reload_project()

                    import s4l_v1.document

                    sim_name = simulation.Name
                    reloaded_simulation = next(
                        (s for s in s4l_v1.document.AllSimulations if s.Name == sim_name),
                        None,
                    )

                    if not reloaded_simulation:
                        raise RuntimeError(f"Could not find simulation '{sim_name}' after reloading project.")

                    with self.subtask("extract_results_total"):
                        extractor = ResultsExtractor.from_params(
                            config=self.config,
                            simulation=reloaded_simulation,  # type: ignore
                            phantom_name=phantom_name,
                            frequency_mhz=freq,
                            scenario_name=scenario_name,
                            position_name=position_name,
                            orientation_name=orientation_name,
                            study_type="near_field",
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
            self._log(
                f"ERROR: An error occurred during placement '{placement_name}': {e}",
                level="progress",
                log_type="error",
            )
            self.verbose_logger.error(traceback.format_exc())
        finally:
            # Remove simulation-specific log handlers
            if sim_log_handlers:  # type: ignore[possibly-unbound]
                remove_simulation_log_handlers(sim_log_handlers)
            if self.project_manager and hasattr(self.project_manager.document, "IsOpen") and self.project_manager.document.IsOpen():  # type: ignore
                self.project_manager.close()
