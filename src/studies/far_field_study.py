import traceback

from ..results_extractor import ResultsExtractor
from ..setups.far_field_setup import FarFieldSetup
from ..setups.phantom_setup import PhantomSetup
from ..simulation_runner import SimulationRunner
from ..utils import StudyCancelledError, profile
from .base_study import BaseStudy


class FarFieldStudy(BaseStudy):
    """
    Manages a far-field simulation study, including setup, execution, and results extraction.
    """

    def __init__(self, config_filename="far_field_config.json", gui=None):
        super().__init__("far_field", config_filename, gui)

    def _run_study(self):
        """
        Executes the entire far-field study by iterating through each simulation case,
        creating a separate project for each.
        """
        self._log(
            f"--- Starting Far-Field Study: {self.config.get_setting('study_name')} ---",
            level="progress",
            log_type="header",
        )

        do_setup = self.config.get_setting("execution_control.do_setup", True)
        do_run = self.config.get_setting("execution_control.do_run", True)
        do_extract = self.config.get_setting("execution_control.do_extract", True)
        auto_cleanup = self.config.get_auto_cleanup_previous_results()

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
        self._validate_auto_cleanup_config(do_setup, do_run, do_extract, auto_cleanup)

        phantoms = self.config.get_setting("phantoms", [])
        frequencies = self.config.get_setting("frequencies_mhz", [])
        far_field_params = self.config.get_setting("far_field_setup.environmental", {})
        incident_directions = far_field_params.get("incident_directions", [])
        polarizations = far_field_params.get("polarizations", [])

        total_projects = len(phantoms) * len(frequencies)
        sims_per_project = len(incident_directions) * len(polarizations)
        total_simulations = total_projects * sims_per_project

        # Inform the profiler about the total number of simulations and projects for accurate ETA
        self.profiler.set_total_simulations(total_simulations)
        self.profiler.set_project_scope(total_projects)

        # Give the profiler a hint about the first phase to avoid an initial "N/A" for ETA
        if do_setup:
            self.profiler.current_phase = "setup"
        elif do_run:
            self.profiler.current_phase = "run"
        elif do_extract:
            self.profiler.current_phase = "extract"

        if self.gui:
            self.gui.update_overall_progress(0, 100)  # Initialize GUI progress

        for i, phantom_name in enumerate(phantoms):
            try:
                # One phantom setup object can be reused for all frequencies
                phantom_setup = PhantomSetup(
                    self.config, phantom_name, self.verbose_logger, self.progress_logger
                )

                for j, freq in enumerate(frequencies):
                    try:
                        # Check for a stop signal from the GUI at the start of each major iteration.
                        self._check_for_stop_signal()

                        # Create a new, clean project for each frequency to avoid performance degradation.
                        self.project_manager.create_or_open_project(phantom_name, freq)

                        # The phantom must be loaded into each new project.
                        phantom_setup.ensure_phantom_is_loaded()

                        project_index = i * len(frequencies) + j + 1
                        self.profiler.set_current_project(project_index)
                        self.profiler.completed_phases.clear()  # Reset for the new project

                        self._log(
                            f"\n--- Processing Frequency {j+1}/{len(frequencies)}: {freq}MHz "
                            f"for Phantom '{phantom_name}' ---",
                            level="progress",
                            log_type="header",
                        )

                        all_simulations = []
                        # 1. Setup Phase
                        if do_setup:
                            with profile(self, "setup"):
                                total_setups = len(incident_directions) * len(
                                    polarizations
                                )
                                if self.gui:
                                    self.gui.update_stage_progress(
                                        "Setup", 0, total_setups
                                    )

                                for k, direction_name in enumerate(incident_directions):
                                    for (
                                        polarization_index,
                                        polarization_name,
                                    ) in enumerate(polarizations):
                                        self._check_for_stop_signal()
                                        setup_index = (
                                            k * len(polarizations)
                                            + polarization_index
                                            + 1
                                        )
                                        self._log(
                                            f"    - Setting up simulation {setup_index}/{total_setups}: "
                                            f"{direction_name}_{polarization_name}",
                                            level="progress",
                                            log_type="progress",
                                        )

                                        setup = FarFieldSetup(
                                            self.config,
                                            phantom_name,
                                            freq,
                                            direction_name,
                                            polarization_name,
                                            self.project_manager,
                                            self.verbose_logger,
                                            self.progress_logger,
                                        )

                                        # The context manager handles timing,
                                        # GUI animations, and optional line profiling.
                                        with self.subtask(
                                            "setup_simulation",
                                            instance_to_profile=setup,
                                        ) as wrapper:
                                            simulation = wrapper(setup.run_full_setup)(
                                                phantom_setup
                                            )

                                        if simulation:
                                            all_simulations.append(
                                                (
                                                    simulation,
                                                    direction_name,
                                                    polarization_name,
                                                )
                                            )
                                        else:
                                            self._log(
                                                f"    - Setup failed for {direction_name}_{polarization_name}",
                                                level="progress",
                                                log_type="error",
                                            )

                                        if self.gui:
                                            progress = (
                                                self.profiler.get_weighted_progress(
                                                    "setup", setup_index / total_setups
                                                )
                                            )
                                            self.gui.update_overall_progress(
                                                int(progress), 100
                                            )
                                            self.gui.update_stage_progress(
                                                "Setup", setup_index, total_setups
                                            )

                                # Save the project after the entire setup phase for this project is complete.
                                self._log(
                                    "  - Saving project after setup phase...",
                                    level="progress",
                                    log_type="progress",
                                )
                                self.project_manager.save()
                        else:
                            # If not setting up, filter simulations from the existing project based on the config
                            import s4l_v1.document

                            all_sims_in_doc = list(s4l_v1.document.AllSimulations)

                            # Get the desired simulation names from the config
                            config_directions = self.config.get_setting(
                                "far_field_setup.environmental.incident_directions", []
                            )
                            config_polarizations = self.config.get_setting(
                                "far_field_setup.environmental.polarizations", []
                            )

                            # Reconstruct the expected simulation names from the config
                            expected_sim_names_thelonious = [
                                f"EM_FDTD_{phantom_name}_{freq}MHz_{d}_{p}"
                                for d in config_directions
                                for p in config_polarizations
                            ]
                            expected_sim_names_thelonius = [
                                f"EM_FDTD_{phantom_name.replace('thelonious', 'thelonius')}_{freq}MHz_{d}_{p}"
                                for d in config_directions
                                for p in config_polarizations
                            ]
                            expected_sim_names = (
                                expected_sim_names_thelonious
                                + expected_sim_names_thelonius
                            )

                            # Filter the simulations from the document
                            sims_to_process = [
                                sim
                                for sim in all_sims_in_doc
                                if sim.Name in expected_sim_names
                            ]

                            # Recreate the all_simulations tuple structure
                            all_simulations = []
                            for sim in sims_to_process:
                                parts = sim.Name.split("_")
                                direction_name = "_".join(parts[4:-1])
                                polarization_name = parts[-1]
                                all_simulations.append(
                                    (sim, direction_name, polarization_name)
                                )

                        if not all_simulations:
                            self._log(
                                "  ERROR: No matching simulations found in the project for the current configuration. "
                                "Skipping.",
                                level="progress",
                                log_type="error",
                            )
                            continue

                        # 2. Run Phase
                        if do_run:
                            with profile(self, "run"):
                                self.profiler.start_stage(
                                    "run", total_stages=len(all_simulations)
                                )
                                sim_objects_only = [s[0] for s in all_simulations]
                                runner = SimulationRunner(
                                    self.config,
                                    self.project_manager.project_path,
                                    sim_objects_only,
                                    self.verbose_logger,
                                    self.progress_logger,
                                    self.gui,
                                    study=self,
                                )
                                runner.run_all()
                                # Manually complete the run phase after all its stages are done
                                self.profiler.complete_run_phase()

                        # 3. Extraction Phase
                        if do_extract:
                            with profile(self, "extract"):
                                if self.gui:
                                    self.gui.update_stage_progress(
                                        "Extracting Results", 0, len(all_simulations)
                                    )
                                self.project_manager.reload_project()
                                self._extract_results_for_project(
                                    phantom_name, freq, all_simulations
                                )
                                if self.gui:
                                    progress = self.profiler.get_weighted_progress(
                                        "extract", 1.0
                                    )
                                    self.gui.update_overall_progress(int(progress), 100)
                                    self.gui.update_stage_progress(
                                        "Extracting Results",
                                        len(all_simulations),
                                        len(all_simulations),
                                    )
                    except Exception as e:
                        error_msg = (
                            f"  ERROR: An error occurred while processing frequency {freq}MHz "
                            f"for phantom '{phantom_name}': {e}"
                        )
                        self._log(error_msg, log_type="error")
                        self.verbose_logger.error(traceback.format_exc())
                        # Ensure the project is closed even if an error occurs within the frequency loop
                        if (
                            self.project_manager
                            and hasattr(self.project_manager.document, "IsOpen")
                            and self.project_manager.document.IsOpen()
                        ):
                            self.project_manager.close()
                        continue  # Continue to the next frequency
                    finally:
                        # Ensure the project is closed after each frequency to release resources.
                        if (
                            self.project_manager
                            and hasattr(self.project_manager.document, "IsOpen")
                            and self.project_manager.document.IsOpen()
                        ):
                            self.project_manager.close()

            except StudyCancelledError:
                # This is not an error, but a signal to stop. Re-raise it to be caught by the outer loop.
                raise
            except Exception as e:
                self._log(
                    f"  ERROR: An error occurred while processing phantom '{phantom_name}': {e}",
                    level="progress",
                    log_type="error",
                )
                traceback.print_exc()

    def _validate_auto_cleanup_config(self, do_setup, do_run, do_extract, auto_cleanup):
        """
        Validates the auto_cleanup_previous_results configuration and warns about potential issues.

        Args:
            do_setup (bool): Whether setup phase is enabled
            do_run (bool): Whether run phase is enabled
            do_extract (bool): Whether extract phase is enabled
            auto_cleanup (list): List of file types to clean up
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
            self.config.config["execution_control"][
                "auto_cleanup_previous_results"
            ] = []

        # Inform user that auto-cleanup is active
        cleanup_types = self.config.get_auto_cleanup_previous_results()
        if cleanup_types:
            file_type_names = {
                "output": "output files (*_Output.h5)",
                "input": "input files (*_Input.h5)",
                "smash": "project files (*.smash)",
            }
            cleanup_descriptions = [file_type_names.get(t, t) for t in cleanup_types]
            self._log(
                f"Auto-cleanup enabled: {', '.join(cleanup_descriptions)} will be "
                "deleted after each simulation's results are extracted to save disk space.",
                level="progress",
                log_type="info",
            )

    def _extract_results_for_project(self, phantom_name, freq, simulations_to_extract):
        """
        Extracts results for a given list of simulations.
        """
        if not simulations_to_extract:
            self._log(
                "  - No matching simulations to extract based on the current configuration.",
                log_type="warning",
            )
            return

        self._log(
            f"  - Extracting results for {len(simulations_to_extract)} simulation(s) matching the configuration.",
            log_type="info",
        )
        for sim, direction_name, polarization_name in simulations_to_extract:
            self._check_for_stop_signal()
            try:
                self._log(
                    f"    - Extracting from simulation: {sim.Name}",
                    level="progress",
                    log_type="progress",
                )
                extractor = ResultsExtractor(
                    config=self.config,
                    simulation=sim,
                    phantom_name=phantom_name,
                    frequency_mhz=freq,
                    scenario_name="environmental",
                    position_name=polarization_name,
                    orientation_name=direction_name,
                    study_type="far_field",
                    verbose_logger=self.verbose_logger,
                    progress_logger=self.progress_logger,
                    gui=self.gui,
                    study=self,
                )
                extractor.extract()
            except Exception as e:
                self._log(
                    f"    - ERROR: Failed to extract results for simulation '{sim.Name}': {e}",
                    level="progress",
                    log_type="error",
                )
                traceback.print_exc()
