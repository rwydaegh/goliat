import os
import traceback
from typing import TYPE_CHECKING, Optional

from ..antenna import Antenna
from ..results_extractor import ResultsExtractor
from ..setups.near_field_setup import NearFieldSetup
from ..simulation_runner import SimulationRunner
from ..utils import profile
from .base_study import BaseStudy

if TYPE_CHECKING:
    from ..gui_manager import QueueGUI


class NearFieldStudy(BaseStudy):
    """Manages and runs a full near-field simulation campaign."""

    def __init__(
        self,
        config_filename: str = "near_field_config.json",
        gui: Optional["QueueGUI"] = None,
        no_cache: bool = False,
    ):
        super().__init__("near_field", config_filename, gui, no_cache=no_cache)

    def _run_study(self):
        """Runs the entire simulation campaign based on the configuration."""
        self._log(
            f"--- Starting Near-Field Study: {self.config.get_setting('study_name')} ---",
            level="progress",
            log_type="header",
        )

        do_setup = self.config.get_setting("execution_control.do_setup", True)
        do_run = self.config.get_setting("execution_control.do_run", True)
        do_extract = self.config.get_setting("execution_control.do_extract", True)
        auto_cleanup = self.config.get_auto_cleanup_previous_results()

        if not do_setup and not do_run and not do_extract:
            self._log(
                "All execution phases (setup, run, extract) are disabled. Nothing to do.",
                log_type="warning",
            )
            return

        # Sanity check for auto_cleanup_previous_results
        self._validate_auto_cleanup_config(do_setup, do_run, do_extract, auto_cleanup)  # type: ignore

        phantoms = self.config.get_setting("phantoms", [])
        if not isinstance(phantoms, list):
            phantoms = [phantoms]
        frequencies = self.config.get_setting("antenna_config", {}).keys()  # type: ignore
        all_scenarios = self.config.get_setting("placement_scenarios", {})

        # Calculate total number of simulations for the profiler
        total_simulations = 0
        for phantom_name in phantoms:
            phantom_definition = self.config.get_phantom_definition(phantom_name)  # type: ignore
            placements_config = phantom_definition.get("placements", {})
            if not placements_config:
                continue
            for scenario_name, scenario_details in all_scenarios.items():  # type: ignore
                if placements_config.get(f"do_{scenario_name}"):
                    positions = scenario_details.get("positions", {})
                    orientations = scenario_details.get("orientations", {})
                    total_simulations += len(list(frequencies)) * len(positions) * len(orientations)  # type: ignore

        self.profiler.set_total_simulations(total_simulations)
        if self.gui:
            self.gui.update_overall_progress(0, 100)

        simulation_count = 0
        for phantom_name in phantoms:
            phantom_definition = self.config.get_phantom_definition(phantom_name)  # type: ignore
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
        batch_run = self.config.get_setting("execution_control.batch_run", False)
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
            if do_setup:
                verification_status = self.project_manager.create_or_open_project(
                    phantom_name, freq, scenario_name, position_name, orientation_name
                )
                needs_setup = not verification_status["setup_done"]

                if needs_setup:
                    with profile(self, "setup"):
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
                        )
                        with self.subtask("setup_simulation", instance_to_profile=setup) as wrapper:
                            simulation = wrapper(setup.run_full_setup)(self.project_manager)

                        if not simulation:
                            self._log(f"ERROR: Setup failed for {placement_name}.", level="progress", log_type="error")
                            return

                        self.project_manager.save()
                        surgical_config = self.config.build_simulation_config(
                            phantom_name=phantom_name,
                            frequency_mhz=freq,
                            scenario_name=scenario_name,
                            position_name=position_name,
                            orientation_name=orientation_name,
                        )
                        if self.project_manager.project_path:
                            self.project_manager.write_simulation_metadata(
                                os.path.join(os.path.dirname(self.project_manager.project_path), "config.json"), surgical_config
                            )

                        if self.gui:
                            progress = self.profiler.get_weighted_progress("setup", 1.0)
                            self.gui.update_overall_progress(int(progress), 100)
                            self.gui.update_stage_progress("Setup", 1, 1)

                # Update do_run and do_extract based on verification
                if verification_status["run_done"]:
                    do_run = False
                    self._log("Skipping run phase, deliverables found.", log_type="info")
                if verification_status["extract_done"]:
                    do_extract = False
                    self._log("Skipping extract phase, deliverables found.", log_type="info")

            else:
                self.project_manager.create_or_open_project(phantom_name, freq, scenario_name, position_name, orientation_name)

            # ALWAYS get a fresh simulation handle from the document before run/extract
            import s4l_v1.document

            if s4l_v1.document.AllSimulations:
                sim_name = f"EM_FDTD_{phantom_name}_{freq}MHz_{placement_name}"
                simulation = next(
                    (s for s in s4l_v1.document.AllSimulations if s.Name == sim_name),  # type: ignore
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
                    self.profiler.start_stage("run", total_stages=1)
                    runner = SimulationRunner(
                        self.config,
                        self.project_manager.project_path,  # type: ignore
                        [simulation],  # type: ignore
                        self.verbose_logger,
                        self.progress_logger,
                        self.gui,
                        self,
                    )
                    runner.run_all()
                    self.profiler.complete_run_phase()
                    self._verify_and_update_metadata("run")
                    if self.gui:
                        progress = self.profiler.get_weighted_progress("run", 1.0)
                        self.gui.update_overall_progress(int(progress), 100)
                        self.gui.update_stage_progress("Run", 1, 1)

            # 3. Extract Results
            if do_extract:
                with profile(self, "extract"):
                    if self.gui:
                        self.gui.update_stage_progress("Extracting Results", 0, 1)
                    self.project_manager.reload_project()

                    import s4l_v1.document

                    sim_name = simulation.Name
                    reloaded_simulation = next(
                        (s for s in s4l_v1.document.AllSimulations if s.Name == sim_name),  # type: ignore
                        None,
                    )

                    if not reloaded_simulation:
                        raise RuntimeError(f"Could not find simulation '{sim_name}' after reloading project.")

                    extractor = ResultsExtractor(
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
                    self.project_manager.save()  # TODO: can be skipped?
                    if self.gui:
                        progress = self.profiler.get_weighted_progress("extract", 1.0)
                        self.gui.update_overall_progress(int(progress), 100)
                        self.gui.update_stage_progress("Extracting Results", 1, 1)

        except Exception as e:
            self._log(
                f"ERROR: An error occurred during placement '{placement_name}': {e}",
                level="progress",
                log_type="error",
            )
            self.verbose_logger.error(traceback.format_exc())
        finally:
            if self.project_manager and hasattr(self.project_manager.document, "IsOpen") and self.project_manager.document.IsOpen():  # type: ignore
                self.project_manager.close()
