import os
import traceback
from typing import TYPE_CHECKING, Optional

from ..results_extractor import ResultsExtractor
from ..setups.far_field_setup import FarFieldSetup
from ..utils import profile
from .base_study import BaseStudy

if TYPE_CHECKING:
    from ..gui_manager import QueueGUI


class FarFieldStudy(BaseStudy):
    """Manages a far-field simulation study."""

    def __init__(
        self,
        config_filename: str = "far_field_config.json",
        gui: Optional["QueueGUI"] = None,
        no_cache: bool = False,
    ):
        super().__init__("far_field", config_filename, gui, no_cache=no_cache)

    def _run_study(self):
        """Executes the far-field study by iterating through each simulation case."""
        config_filename = os.path.basename(self.config.config_path)
        self._log(
            f"--- Starting Far-Field Study: {config_filename} ---",
            level="progress",
            log_type="header",
        )

        do_setup = self.config.get_setting("execution_control.do_setup", True)
        do_run = self.config.get_setting("execution_control.do_run", True)
        do_extract = self.config.get_setting("execution_control.do_extract", True)
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

        phantoms = self.config.get_setting("phantoms", []) or []
        frequencies = self.config.get_setting("frequencies_mhz", []) or []
        far_field_params = self.config.get_setting("far_field_setup.environmental", {})
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

        if self.gui:
            self.gui.update_overall_progress(0, 100)  # Initialize GUI progress

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
                        self._run_single_simulation(
                            phantom_name,
                            freq,
                            direction_name,
                            polarization_name,
                            do_setup,  # type: ignore
                            do_run,  # type: ignore
                            do_extract,  # type: ignore
                        )

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
                            simulation = wrapper(setup.run_full_setup)(self.project_manager)

                        if not simulation:
                            self._log(
                                f"ERROR: Setup failed for {direction_name}_{polarization_name}. Cannot proceed.",
                                level="progress",
                                log_type="error",
                            )
                            return

                        # Subtask 6: Save project
                        self._log("    - Save project...", level="progress", log_type="progress")
                        with self.profiler.subtask("setup_save_project"):
                            self.project_manager.save()
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
                        elapsed = self.profiler.subtask_times["setup_save_project"][-1]
                        self._log(f"      - Subtask 'setup_save_project' done in {elapsed:.2f}s", log_type="verbose")
                        self._log(f"      - Done in {elapsed:.2f}s", level="progress", log_type="success")

                    # Update do_run and do_extract based on verification
                    if verification_status["run_done"]:
                        do_run = False
                        self._log("Skipping run phase, deliverables found.", log_type="info")
                    if verification_status["extract_done"]:
                        do_extract = False
                        self._log("Skipping extract phase, deliverables found.", log_type="info")

                    if self.gui:
                        progress = self.profiler.get_weighted_progress("setup", 1.0)
                        self.gui.update_overall_progress(int(progress), 100)
                        self.gui.update_stage_progress("Setup", 1, 1)
            else:
                self.project_manager.create_or_open_project(
                    phantom_name,
                    freq,
                    "environmental",
                    polarization_name,
                    direction_name,
                )

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
                    self.project_manager.reload_project()
                    sim_name = simulation.Name
                    reloaded_simulation = next(
                        (s for s in s4l_v1.document.AllSimulations if s.Name == sim_name),
                        None,
                    )
                    if not reloaded_simulation:
                        raise RuntimeError(f"Could not find simulation '{sim_name}' after reloading.")

                    with self.subtask("extract_results_total"):
                        extractor = ResultsExtractor(
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
                        progress = self.profiler.get_weighted_progress("extract", 1.0)
                        self.gui.update_overall_progress(int(progress), 100)
                        self.gui.update_stage_progress("Extracting Results", 1, 1)

        except Exception as e:
            self._log(f"ERROR during simulation: {e}", log_type="error")
            self.verbose_logger.error(traceback.format_exc())
        finally:
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

        batch_run = self.config.get_setting("execution_control.batch_run", False)
        if batch_run:
            self._log(
                "ERROR: 'auto_cleanup_previous_results' is not compatible with 'batch_run'. Disabling.",
                log_type="error",
            )
            self.config.config["execution_control"]["auto_cleanup_previous_results"] = []

        cleanup_types = self.config.get_auto_cleanup_previous_results()
        if cleanup_types:
            self._log(f"Auto-cleanup enabled for: {', '.join(cleanup_types)}", log_type="info")
