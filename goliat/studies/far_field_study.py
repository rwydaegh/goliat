import json
import os
import traceback
from pathlib import Path
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

        do_setup, do_run, do_extract = self._get_execution_control_flags()
        auto_cleanup = self.config.get_auto_cleanup_previous_results()

        if not self._validate_execution_control(do_setup, do_run, do_extract):
            return

        if not do_setup and do_run:
            self._log(
                "WARNING: Running simulations without setup is not a standard workflow and might lead to issues.",
                log_type="warning",
            )

        # Sanity check for auto_cleanup_previous_results
        self._validate_auto_cleanup_config(do_setup, do_run, do_extract, auto_cleanup)

        phantoms = self.config["phantoms"] or []
        if not isinstance(phantoms, list):
            phantoms = [phantoms]
        frequencies = self.config["frequencies_mhz"] or []
        if not isinstance(frequencies, list):
            frequencies = [frequencies]

        # Parse multi-sine frequency groups (e.g., "700+2450" -> [700, 2450])
        parsed_frequencies = []
        for freq in frequencies:
            if isinstance(freq, str) and "+" in freq:
                # Multi-sine group: "700+2450" -> [700, 2450]
                freq_list = [int(f.strip()) for f in freq.split("+")]
                parsed_frequencies.append(freq_list)
                self._log(f"Multi-sine frequency group detected: {freq_list} MHz", log_type="info")
            else:
                parsed_frequencies.append(int(freq) if isinstance(freq, str) else freq)
        frequencies = parsed_frequencies

        far_field_params = self.config["far_field_setup.environmental"] or {}
        polarizations = far_field_params.get("polarizations", []) if far_field_params else []

        # Check for spherical tessellation mode
        spherical_tessellation = far_field_params.get("spherical_tessellation", None) if far_field_params else None

        if spherical_tessellation:
            # Generate directions from theta/phi divisions
            incident_directions = self._generate_spherical_directions(spherical_tessellation)
            self._log(
                f"Spherical tessellation: generated {len(incident_directions)} directions",
                log_type="info",
            )
        else:
            # Standard orthogonal directions from config
            incident_directions = far_field_params.get("incident_directions", []) if far_field_params else []

        total_simulations = len(phantoms) * len(frequencies) * len(incident_directions) * len(polarizations)
        self.profiler.set_total_simulations(total_simulations)
        self._set_initial_profiler_phase(do_setup, do_run, do_extract)

        self._iterate_far_field_simulations(
            phantoms, frequencies, incident_directions, polarizations, total_simulations, do_setup, do_run, do_extract
        )

    def _iterate_far_field_simulations(
        self,
        phantoms: list,
        frequencies: list,
        incident_directions: list,
        polarizations: list,
        total_simulations: int,
        do_setup: bool,
        do_run: bool,
        do_extract: bool,
    ):
        """Iterates through all far-field simulation combinations.

        Args:
            phantoms: List of phantom names.
            frequencies: List of frequencies in MHz.
            incident_directions: List of incident direction names.
            polarizations: List of polarization names.
            total_simulations: Total number of simulations.
            do_setup: Whether setup phase is enabled.
            do_run: Whether run phase is enabled.
            do_extract: Whether extract phase is enabled.
        """
        simulation_count = 0
        auto_induced_enabled = self.config["auto_induced.enabled"] or False

        for phantom_name in phantoms:  # type: ignore
            for freq in frequencies:  # type: ignore
                for direction_name in incident_directions:
                    for polarization_name in polarizations:
                        simulation_count += 1
                        self._process_single_far_field_simulation(
                            phantom_name,
                            freq,
                            direction_name,
                            polarization_name,
                            simulation_count,
                            total_simulations,
                            do_setup,
                            do_run,
                            do_extract,
                        )

                # After all directions/polarizations complete for this (phantom, freq),
                # run auto-induced analysis if enabled.
                # Auto-induced requires all _Output.h5 files to exist (from run phase).
                if auto_induced_enabled and do_run:
                    try:
                        self._run_auto_induced_for_phantom_freq(
                            phantom_name=phantom_name,
                            freq=freq,
                            incident_directions=incident_directions,
                            polarizations=polarizations,
                        )
                    except Exception as e:
                        self._log(
                            f"ERROR in auto-induced processing for {phantom_name}@{freq}MHz: {e}",
                            log_type="error",
                        )
                        self.verbose_logger.error(traceback.format_exc())

    def _generate_spherical_directions(self, tessellation_config: dict) -> list[str]:
        """Generates direction names from spherical tessellation config.

        Creates a grid of incident wave directions by dividing the sphere
        along theta (polar angle from +z) and phi (azimuthal angle from +x).

        Args:
            tessellation_config: Dict with 'theta_divisions' and 'phi_divisions'.
                - theta_divisions: Number of divisions for theta (0° to 180°).
                - phi_divisions: Number of divisions for phi (0° to 360°, exclusive of 360°).

        Returns:
            List of direction names in format "theta_phi" (e.g., "45_90").
        """
        theta_divisions = tessellation_config.get("theta_divisions", 3)
        phi_divisions = tessellation_config.get("phi_divisions", 4)

        directions = []

        # Generate theta values: 0° (z+) to 180° (z-)
        # Using theta_divisions + 1 points to include both endpoints
        theta_values = [i * 180 / theta_divisions for i in range(theta_divisions + 1)]

        # Generate phi values: 0° to 360° (exclusive of 360° since 0° = 360°)
        phi_values = [i * 360 / phi_divisions for i in range(phi_divisions)]

        for theta in theta_values:
            # At poles (theta=0 or 180), all phi values give the same direction
            # Only use phi=0 at poles to avoid redundant simulations
            if theta == 0 or theta == 180:
                direction_name = f"{int(theta)}_{int(0)}"
                directions.append(direction_name)
            else:
                for phi in phi_values:
                    direction_name = f"{int(theta)}_{int(phi)}"
                    directions.append(direction_name)

        self._log(f"  - Theta divisions: {theta_divisions} ({theta_values})", log_type="verbose")
        self._log(f"  - Phi divisions: {phi_divisions} ({phi_values})", log_type="verbose")
        self._log(f"  - Generated {len(directions)} unique directions", log_type="verbose")

        return directions

    def _process_single_far_field_simulation(
        self,
        phantom_name: str,
        freq: int | list[int],
        direction_name: str,
        polarization_name: str,
        simulation_count: int,
        total_simulations: int,
        do_setup: bool,
        do_run: bool,
        do_extract: bool,
    ):
        """Processes a single far-field simulation.

        Args:
            phantom_name: Name of the phantom.
            freq: Frequency in MHz.
            direction_name: Name of the incident direction.
            polarization_name: Name of the polarization.
            simulation_count: Current simulation count.
            total_simulations: Total number of simulations.
            do_setup: Whether setup phase is enabled.
            do_run: Whether run phase is enabled.
            do_extract: Whether extract phase is enabled.
        """
        self._check_for_stop_signal()
        # Format frequency for display
        freq_display = f"{'+'.join(str(f) for f in freq)}" if isinstance(freq, list) else str(freq)
        self._log(
            f"\n--- Processing Simulation {simulation_count}/{total_simulations}: "
            f"{phantom_name}, {freq_display}MHz, {direction_name}, {polarization_name} ---",
            level="progress",
            log_type="header",
        )
        if self.gui:
            self.gui.update_simulation_details(
                simulation_count,
                total_simulations,
                f"{phantom_name}, {freq_display}MHz, {direction_name}, {polarization_name}",
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
        freq: int | list[int],
        direction_name: str,
        polarization_name: str,
        do_setup: bool,
        do_run: bool,
        do_extract: bool,
    ):
        """Runs a full simulation for a single far-field case."""
        sim_log_handlers = None
        # Format frequency for naming/paths
        freq_str = f"{'+'.join(str(f) for f in freq)}" if isinstance(freq, list) else str(freq)
        try:
            simulation = None

            # 1. Setup Phase
            if do_setup:
                with profile(self, "setup"):
                    verification_status = self.project_manager.create_or_open_project(
                        phantom_name,
                        freq,
                        "environmental",
                        direction_name,
                        polarization_name,
                    )
                    # Add simulation-specific log handlers after project directory is created
                    if self.project_manager.project_path:
                        project_dir = os.path.dirname(self.project_manager.project_path)
                        sim_log_handlers = add_simulation_log_handlers(project_dir)
                    needs_setup = not verification_status["setup_done"]

                    # Mark profiler if setup was cached/skipped
                    if not needs_setup:
                        self.profiler.phase_skipped = True

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
                    # But preserve setup_timestamp if setup wasn't done
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
                            update_setup_timestamp=needs_setup,  # Update timestamp only if setup was done
                        )

                    # Update do_run and do_extract based on verification
                    if verification_status["run_done"]:
                        do_run = False
                        self._log("Skipping run phase, deliverables found.", log_type="info")
                    if verification_status["extract_done"]:
                        do_extract = False
                        self._log("Skipping extract phase, deliverables found.", log_type="info")
                        # Upload results if reupload flag is set and running as assignment
                        if self._should_reupload_results() and self.project_manager.project_path:
                            project_dir = os.path.dirname(self.project_manager.project_path)
                            self._upload_results_if_assignment(project_dir)

                    if self.gui:
                        self.gui.update_stage_progress("Setup", 1, 1)
            else:
                verification_status = self.project_manager.create_or_open_project(
                    phantom_name,
                    freq,
                    "environmental",
                    direction_name,
                    polarization_name,
                )
                # Add simulation-specific log handlers after project directory is created
                if self.project_manager.project_path:
                    project_dir = os.path.dirname(self.project_manager.project_path)
                    sim_log_handlers = add_simulation_log_handlers(project_dir)

            # Get a fresh simulation handle from the document if we need to run or extract
            # If everything is done, we don't need the simulation handle
            if do_run or do_extract:
                import s4l_v1.document

                if s4l_v1.document.AllSimulations:
                    sim_name = f"EM_FDTD_{phantom_name}_{freq_str}MHz_{direction_name}_{polarization_name}"
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
                    sim_name = simulation.Name  # type: ignore[attr-defined]
                    reloaded_simulation = next(
                        (s for s in s4l_v1.document.AllSimulations if s.Name == sim_name),  # type: ignore[possibly-unbound]
                        None,
                    )
                    if not reloaded_simulation:
                        raise RuntimeError(f"Could not find simulation '{sim_name}' after reloading.")

                    # For multi-sine, extract at each frequency separately
                    if isinstance(freq, list):
                        self._log(f"  - Multi-sine extraction: extracting at each frequency {freq} MHz", log_type="info")
                        for single_freq in freq:
                            self._log(f"    - Extracting at {single_freq} MHz...", log_type="progress")
                            try:
                                with self.subtask(f"extract_results_{single_freq}MHz"):
                                    extractor = ResultsExtractor.from_params(
                                        config=self.config,
                                        simulation=reloaded_simulation,  # type: ignore
                                        phantom_name=phantom_name,
                                        frequency_mhz=single_freq,  # Extract at single frequency
                                        scenario_name="environmental",
                                        position_name=direction_name,
                                        orientation_name=polarization_name,
                                        study_type="far_field",
                                        verbose_logger=self.verbose_logger,
                                        progress_logger=self.progress_logger,
                                        gui=self.gui,  # type: ignore
                                        study=self,
                                    )
                                    extractor.extract()
                            except Exception as freq_error:
                                self._log(
                                    f"    - ERROR extracting at {single_freq} MHz: {freq_error}. Continuing to next frequency.",
                                    log_type="error",
                                )
                                self.verbose_logger.error(traceback.format_exc())
                    else:
                        with self.subtask("extract_results_total"):
                            extractor = ResultsExtractor.from_params(
                                config=self.config,
                                simulation=reloaded_simulation,  # type: ignore
                                phantom_name=phantom_name,
                                frequency_mhz=freq,
                                scenario_name="environmental",
                                position_name=direction_name,
                                orientation_name=polarization_name,
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

    # ==================== Auto-Induced Exposure Methods ====================

    def _run_auto_induced_for_phantom_freq(
        self,
        phantom_name: str,
        freq: int | list[int],
        incident_directions: list[str],
        polarizations: list[str],
    ) -> None:
        """Runs auto-induced exposure analysis for a completed (phantom, freq) set.

        Prerequisites:
        - All environmental simulations for this (phantom, freq) must be complete.
        - All _Output.h5 files must exist.

        Args:
            phantom_name: Name of the phantom (e.g., "thelonious").
            freq: Frequency in MHz.
            incident_directions: List of direction names that were simulated.
            polarizations: List of polarization names that were simulated.
        """
        freq_str = f"{'+'.join(str(f) for f in freq)}" if isinstance(freq, list) else str(freq)

        # Get output directory for auto-induced results
        output_dir = self._get_auto_induced_output_dir(phantom_name, freq)
        summary_path = output_dir / "auto_induced_summary.json"

        # Check if already done (caching)
        if self._is_auto_induced_done(summary_path, phantom_name, freq, incident_directions, polarizations):
            self._log(
                f"  Auto-induced for {phantom_name}@{freq_str}MHz already complete, skipping.",
                level="progress",
                log_type="success",
            )
            return

        # Gather all _Output.h5 files
        h5_paths = self._gather_output_h5_files(phantom_name, freq, incident_directions, polarizations)
        expected_count = len(incident_directions) * len(polarizations)

        if len(h5_paths) < expected_count:
            self._log(
                f"  ERROR: Auto-induced requires all {expected_count} sims complete, found {len(h5_paths)} _Output.h5 files. Skipping.",
                log_type="error",
            )
            return

        # Find an _Input.h5 file (any one will do, grids are identical)
        input_h5 = self._find_input_h5(phantom_name, freq, incident_directions, polarizations)
        if not input_h5:
            self._log("  ERROR: No _Input.h5 file found for auto-induced processing.", log_type="error")
            return

        # Need to open a project with the phantom to access geometry
        # Reopen the last simulation's project
        last_dir = incident_directions[-1]
        last_pol = polarizations[-1]
        self.project_manager.create_or_open_project(
            phantom_name=phantom_name,
            frequency_mhz=freq,
            scenario_name="environmental",
            position_name=last_dir,
            orientation_name=last_pol,
        )
        self.project_manager.open()

        try:
            # Import and run processor
            from ..extraction.auto_induced_processor import AutoInducedProcessor

            processor = AutoInducedProcessor(self, phantom_name, int(freq) if not isinstance(freq, list) else freq[0])

            results = processor.process(
                h5_paths=h5_paths,
                input_h5=input_h5,
                output_dir=output_dir,
            )

            # Save summary
            self._save_auto_induced_summary(summary_path, results)

            self._log(
                f"  Auto-induced complete for {phantom_name}@{freq_str}MHz",
                level="progress",
                log_type="success",
            )

        finally:
            if self.project_manager and hasattr(self.project_manager.document, "IsOpen") and self.project_manager.document.IsOpen():  # type: ignore
                self.project_manager.close()

    def _get_auto_induced_output_dir(self, phantom_name: str, freq: int | list[int]) -> Path:
        """Get the output directory for auto-induced results.

        Args:
            phantom_name: Phantom name.
            freq: Frequency in MHz.

        Returns:
            Path to auto_induced output directory.
        """
        freq_str = f"{'+'.join(str(f) for f in freq)}" if isinstance(freq, list) else str(freq)
        return Path(self.config.base_dir) / "results" / "far_field" / phantom_name.lower() / f"{freq_str}MHz" / "auto_induced"

    def _is_auto_induced_done(
        self,
        summary_path: Path,
        phantom_name: str,
        freq: int | list[int],
        incident_directions: list[str],
        polarizations: list[str],
    ) -> bool:
        """Check if auto-induced processing is already complete.

        Auto-induced is considered done if:
        1. auto_induced_summary.json exists
        2. It's newer than all corresponding _Output.h5 files

        Args:
            summary_path: Path to the summary JSON file.
            phantom_name: Phantom name.
            freq: Frequency in MHz.
            incident_directions: List of direction names.
            polarizations: List of polarization names.

        Returns:
            True if auto-induced is already complete.
        """
        if not summary_path.exists():
            return False

        summary_mtime = summary_path.stat().st_mtime

        # Get all _Output.h5 files and check their modification times
        h5_paths = self._gather_output_h5_files(phantom_name, freq, incident_directions, polarizations)
        for h5_path in h5_paths:
            if h5_path.stat().st_mtime > summary_mtime:
                return False  # An H5 file is newer than summary

        return True

    def _gather_output_h5_files(
        self,
        phantom_name: str,
        freq: int | list[int],
        incident_directions: list[str],
        polarizations: list[str],
    ) -> list[Path]:
        """Gather all _Output.h5 files for a (phantom, freq) combination.

        Args:
            phantom_name: Phantom name.
            freq: Frequency in MHz.
            incident_directions: List of direction names.
            polarizations: List of polarization names.

        Returns:
            List of Path objects to _Output.h5 files.
        """
        freq_str = f"{'+'.join(str(f) for f in freq)}" if isinstance(freq, list) else str(freq)
        base_path = Path(self.config.base_dir) / "results" / "far_field" / phantom_name.lower() / f"{freq_str}MHz"

        h5_paths = []
        for direction in incident_directions:
            for polarization in polarizations:
                placement_name = f"environmental_{direction}_{polarization}"
                project_filename = f"far_field_{phantom_name.lower()}_{freq_str}MHz_{placement_name}"
                results_dir = base_path / placement_name / f"{project_filename}.smash_Results"

                if results_dir.exists():
                    for f in results_dir.iterdir():
                        if f.name.endswith("_Output.h5"):
                            h5_paths.append(f)
                            break  # Only one _Output.h5 per simulation

        return h5_paths

    def _find_input_h5(
        self,
        phantom_name: str,
        freq: int | list[int],
        incident_directions: list[str],
        polarizations: list[str],
    ) -> Path | None:
        """Find any _Input.h5 file for the (phantom, freq) set.

        All simulations for a (phantom, freq) have identical grids, so any _Input.h5 will work.

        Args:
            phantom_name: Phantom name.
            freq: Frequency in MHz.
            incident_directions: List of direction names.
            polarizations: List of polarization names.

        Returns:
            Path to an _Input.h5 file, or None if not found.
        """
        freq_str = f"{'+'.join(str(f) for f in freq)}" if isinstance(freq, list) else str(freq)
        base_path = Path(self.config.base_dir) / "results" / "far_field" / phantom_name.lower() / f"{freq_str}MHz"

        for direction in incident_directions:
            for polarization in polarizations:
                placement_name = f"environmental_{direction}_{polarization}"
                project_filename = f"far_field_{phantom_name.lower()}_{freq_str}MHz_{placement_name}"
                results_dir = base_path / placement_name / f"{project_filename}.smash_Results"

                if results_dir.exists():
                    for f in results_dir.iterdir():
                        if f.name.endswith("_Input.h5"):
                            return f

        return None

    def _save_auto_induced_summary(self, summary_path: Path, results: dict) -> None:
        """Save auto-induced results to a summary JSON file.

        Args:
            summary_path: Path to save the summary.
            results: Results dict from AutoInducedProcessor.
        """
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        with open(summary_path, "w") as f:
            json.dump(results, f, indent=4, default=str)
        self._log(f"  Summary saved: {summary_path}", log_type="info")
