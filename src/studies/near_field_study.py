import traceback

from ..antenna import Antenna
from ..results_extractor import ResultsExtractor
from ..setups.near_field_setup import NearFieldSetup
from ..simulation_runner import SimulationRunner
from ..utils import profile
from .base_study import BaseStudy


class NearFieldStudy(BaseStudy):
    """
    Manages and runs a full near-field simulation campaign.
    """

    def __init__(self, config_filename="near_field_config.json", gui=None):
        super().__init__("near_field", config_filename, gui)

    def _run_study(self):
        """
        Runs the entire simulation campaign based on the configuration.
        """
        self._log(
            f"--- Starting Near-Field Study: {self.config.get_setting('study_name')} ---",
            level="progress",
            log_type="header",
        )

        do_setup = self.config.get_setting("execution_control.do_setup", True)
        do_run = self.config.get_setting("execution_control.do_run", True)
        do_extract = self.config.get_setting("execution_control.do_extract", True)

        if not do_setup and not do_run and not do_extract:
            self._log(
                "All execution phases (setup, run, extract) are disabled. Nothing to do.",
                log_type="warning",
            )
            return

        phantoms = self.config.get_setting("phantoms", [])
        if not isinstance(phantoms, list):
            phantoms = [phantoms]
        frequencies = self.config.get_setting("antenna_config", {}).keys()
        all_scenarios = self.config.get_setting("placement_scenarios", {})

        # Calculate total number of simulations for the profiler
        total_simulations = 0
        for phantom_name in phantoms:
            placements_config = self.config.get_phantom_placements(phantom_name)
            if not placements_config:
                continue
            for scenario_name, scenario_details in all_scenarios.items():
                if placements_config.get(f"do_{scenario_name}"):
                    positions = scenario_details.get("positions", {})
                    orientations = scenario_details.get("orientations", {})
                    total_simulations += (
                        len(frequencies) * len(positions) * len(orientations)
                    )

        self.profiler.set_total_simulations(total_simulations)
        if self.gui:
            self.gui.update_overall_progress(0, 100)

        simulation_count = 0
        for phantom_name in phantoms:
            placements_config = self.config.get_phantom_placements(phantom_name)
            if not placements_config:
                continue

            enabled_placements = []
            for scenario_name, scenario_details in all_scenarios.items():
                if placements_config.get(f"do_{scenario_name}"):
                    positions = scenario_details.get("positions", {})
                    orientations = scenario_details.get("orientations", {})
                    for pos_name in positions.keys():
                        for orient_name in orientations.keys():
                            enabled_placements.append(
                                f"{scenario_name}_{pos_name}_{orient_name}"
                            )

            for freq_str in frequencies:
                self._check_for_stop_signal()
                freq = int(freq_str)
                for placement_name in enabled_placements:
                    self._check_for_stop_signal()
                    simulation_count += 1
                    self._log(
                        f"\n--- Processing Simulation {simulation_count}/{total_simulations}: "
                        f"{phantom_name}, {freq}MHz, {placement_name} ---",
                        level="progress",
                        log_type="header",
                    )
                    self._run_placement(
                        phantom_name, freq, placement_name, do_setup, do_run, do_extract
                    )

    def _run_placement(
        self, phantom_name, freq, placement_name, do_setup, do_run, do_extract
    ):
        """
        Runs a full placement scenario, which may include multiple positions and orientations.
        """
        try:
            simulation = None

            # 1. Setup Simulation
            if do_setup:
                with profile(self, "setup"):
                    if self.gui:
                        self.gui.update_stage_progress("Setup", 0, 1)

                    antenna = Antenna(self.config, freq)
                    setup = NearFieldSetup(
                        self.config,
                        phantom_name,
                        freq,
                        placement_name,
                        antenna,
                        self.verbose_logger,
                        self.progress_logger,
                    )

                    with self.subtask(
                        "setup_simulation", instance_to_profile=setup
                    ) as wrapper:
                        simulation = wrapper(setup.run_full_setup)(self.project_manager)

                    if not simulation:
                        self._log(
                            f"ERROR: Setup failed for {placement_name}. Cannot proceed.",
                            level="progress",
                            log_type="error",
                        )
                        return

                    # The first save is now critical after setup is complete.
                    self.project_manager.save()
                    if self.gui:
                        progress = self.profiler.get_weighted_progress("setup", 1.0)
                        self.gui.update_overall_progress(int(progress), 100)
                        self.gui.update_stage_progress("Setup", 1, 1)
            else:
                self.project_manager.create_or_open_project(
                    phantom_name, freq, placement_name
                )

            # ALWAYS get a fresh simulation handle from the document before run/extract
            import s4l_v1.document

            if s4l_v1.document.AllSimulations:
                # First, try to find the simulation with the correct "thelonious" name.
                sim_name_correct = f"EM_FDTD_{phantom_name}_{freq}MHz_{placement_name}"
                simulation = next(
                    (
                        s
                        for s in s4l_v1.document.AllSimulations
                        if s.Name == sim_name_correct
                    ),
                    None,
                )

                # If not found, check for the old "thelonius" name.
                if not simulation:
                    foo = phantom_name.replace("thelonious", "thelonius")
                    sim_name_old = f"EM_FDTD_{foo}_{freq}MHz_{placement_name}"
                    simulation = next(
                        (
                            s
                            for s in s4l_v1.document.AllSimulations
                            if s.Name == sim_name_old
                        ),
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
                        self.project_manager.project_path,
                        [simulation],
                        self.verbose_logger,
                        self.progress_logger,
                        self.gui,
                        self,
                    )
                    runner.run_all()
                    self.profiler.complete_run_phase()

            # 3. Extract Results
            if do_extract:
                with profile(self, "extract"):
                    if self.gui:
                        self.gui.update_stage_progress("Extracting Results", 0, 1)
                    self.project_manager.reload_project()

                    import s4l_v1.document

                    sim_name = simulation.Name
                    reloaded_simulation = next(
                        (
                            s
                            for s in s4l_v1.document.AllSimulations
                            if s.Name == sim_name
                        ),
                        None,
                    )

                    # If not found, check for the old "thelonius" name.
                    if not reloaded_simulation:
                        sim_name_old = sim_name.replace("thelonious", "thelonius")
                        reloaded_simulation = next(
                            (
                                s
                                for s in s4l_v1.document.AllSimulations
                                if s.Name == sim_name_old
                            ),
                            None,
                        )

                    if not reloaded_simulation:
                        raise RuntimeError(
                            f"Could not find simulation '{sim_name}' (or '{sim_name_old}') after reloading project."
                        )

                    extractor = ResultsExtractor(
                        self.config,
                        reloaded_simulation,
                        phantom_name,
                        freq,
                        placement_name,
                        "near_field",
                        self.verbose_logger,
                        self.progress_logger,
                        gui=self.gui,
                        study=self,
                    )
                    extractor.extract()
                    self.project_manager.save()
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
            traceback.print_exc()
        finally:
            if (
                self.project_manager
                and hasattr(self.project_manager.document, "IsOpen")
                and self.project_manager.document.IsOpen()
            ):
                self.project_manager.close()
