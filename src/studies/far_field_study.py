import os
import traceback
from queue import Empty
from .base_study import BaseStudy
from ..utils import StudyCancelledError
from ..config import Config
from ..project_manager import ProjectManager
from ..setups.far_field_setup import FarFieldSetup
from ..setups.phantom_setup import PhantomSetup
from ..simulation_runner import SimulationRunner
from ..results_extractor import ResultsExtractor
from ..utils import ensure_s4l_running, profile

class FarFieldStudy(BaseStudy):
    """
    Manages a far-field simulation study, including setup, execution, and results extraction.
    """
    def __init__(self, config_filename="far_field_config.json", verbose=True, gui=None):
        super().__init__(config_filename, verbose, gui)
        self.project_manager = ProjectManager(self.config, self.verbose_logger, self.progress_logger, gui=self.gui)

    def run(self):
        """
        Executes the entire far-field study by iterating through each simulation case,
        creating a separate project for each.
        """
        self._log(f"--- Starting Far-Field Study: {self.config.get_setting('study_name')} ---", level='progress')
        ensure_s4l_running()

        do_setup = self.config.get_setting('execution_control.do_setup', True)
        do_run = self.config.get_setting('execution_control.do_run', True)
        do_extract = self.config.get_setting('execution_control.do_extract', True)

        if not do_setup and not do_run and not do_extract:
            self._log("All execution phases (setup, run, extract) are disabled in the config. Nothing to do.")
            return

        if not do_setup and do_run:
            self._log("WARNING: Running simulations without setup is not a standard workflow and might lead to issues.")

        phantoms = self.config.get_setting('phantoms', [])
        frequencies = self.config.get_setting('frequencies_mhz', [])
        far_field_params = self.config.get_setting('far_field_setup.environmental', {})
        incident_directions = far_field_params.get('incident_directions', [])
        polarizations = far_field_params.get('polarizations', [])

        total_projects = len(phantoms) * len(frequencies)
        sims_per_project = len(incident_directions) * len(polarizations)
        total_simulations = total_projects * sims_per_project
        
        # Inform the profiler about the total number of simulations for accurate ETA
        self.profiler.set_total_simulations(total_simulations)
        
        if self.gui:
            self.gui.update_overall_progress(0, 100) # Initialize GUI progress

        current_sim_count = 0
        
        try:
            for i, phantom_name in enumerate(phantoms):
                for j, freq in enumerate(frequencies):
                    # Check for a stop signal from the GUI at the start of each major iteration.
                    if self._check_for_stop_signal():
                        raise StudyCancelledError()

                    project_index = i * len(frequencies) + j + 1
                    self._log(f"\n--- Processing Project {project_index}/{total_projects}: {phantom_name}, {freq}MHz ---", level='progress')
                    current_sim_count_in_project = 0
                    
                    try:
                        self.project_manager.create_or_open_project(phantom_name, freq)
                        
                        all_simulations = []
                        # 1. Setup Phase
                        if do_setup:
                            with profile(self, "setup"):
                                phantom_setup = PhantomSetup(self.config, phantom_name, self.verbose_logger, self.progress_logger)
                                phantom_setup.ensure_phantom_is_loaded()
                                
                                total_setups = len(incident_directions) * len(polarizations)
                                if self.gui:
                                    self.gui.update_stage_progress("Setup", 0, total_setups)

                                for k, direction_name in enumerate(incident_directions):
                                    for l, polarization_name in enumerate(polarizations):
                                        if self._check_for_stop_signal():
                                            raise StudyCancelledError()
                                        setup_index = k * len(polarizations) + l + 1
                                        self._log(f"    - Setting up simulation {setup_index}/{total_setups}: {direction_name}_{polarization_name}", level='progress')
                                        
                                        self.start_stage_animation("setup_simulation", setup_index)
                                        
                                        self.start_subtask("setup_simulation")
                                        setup = FarFieldSetup(self.config, phantom_name, freq, direction_name, polarization_name, self.project_manager, self.verbose_logger, self.progress_logger)
                                        simulation = setup.run_full_setup(phantom_setup)
                                        elapsed = self.end_subtask()
                                        
                                        if simulation:
                                            all_simulations.append((simulation, direction_name, polarization_name))
                                            self._log(f"    - Done in {elapsed:.2f}s", level='progress')
                                        else:
                                            self._log(f"    - Setup failed after {elapsed:.2f}s", level='progress')

                                        self.end_stage_animation()

                                        if self.gui:
                                            progress = self.profiler.get_weighted_progress("setup", setup_index / total_setups)
                                            self.gui.update_overall_progress(int(progress), 100)
                                            self.gui.update_stage_progress("Setup", setup_index, total_setups)
                        else:
                            # If not setting up, load simulations from the existing project
                            import s4l_v1.document
                            all_simulations = [(sim, "_".join(sim.Name.split('_')[4:-1]), sim.Name.split('_')[-1]) for sim in s4l_v1.document.AllSimulations]

                        if not all_simulations:
                            self._log("  ERROR: No simulations found or created for this frequency. Skipping.", level='progress')
                            continue

                        # 2. Run Phase
                        if do_run:
                            with profile(self, "run"):
                                self.profiler.start_stage('run', total_stages=len(all_simulations))
                                sim_objects_only = [s[0] for s in all_simulations]
                                runner = SimulationRunner(self.config, self.project_manager.project_path, sim_objects_only, self.verbose_logger, self.progress_logger, self.gui, study=self)
                                runner.run_all()
                                # Manually complete the run phase after all its stages are done
                                self.profiler.complete_run_phase()

                        # 3. Extraction Phase
                        if do_extract:
                            with profile(self, "extract"):
                                if self.gui:
                                    self.gui.update_stage_progress("Extracting Results", 0, len(all_simulations))
                                self.project_manager.reload_project()
                                self._extract_results_for_project(phantom_name, freq)
                                if self.gui:
                                    progress = self.profiler.get_weighted_progress("extract", 1.0)
                                    self.gui.update_overall_progress(int(progress), 100)
                                    self.gui.update_stage_progress("Extracting Results", len(all_simulations), len(all_simulations))

                    except StudyCancelledError:
                        # This is not an error, but a signal to stop. Re-raise it to be caught by the outer loop.
                        raise
                    except Exception as e:
                        self._log(f"  ERROR: An error occurred while processing {freq}MHz: {e}", level='progress')
                        traceback.print_exc()
                    finally:
                        if self.project_manager and hasattr(self.project_manager.document, 'IsOpen') and self.project_manager.document.IsOpen():
                            self.project_manager.close()
        except StudyCancelledError:
            self._log("--- Study execution cancelled by user. ---", level='progress')
            # The 'finally' block will handle cleanup.
        finally:
            if self.project_manager and hasattr(self.project_manager.document, 'IsOpen') and self.project_manager.document.IsOpen():
                self.project_manager.close()
            # Save the learned estimates at the very end
            self.profiler.save_estimates()

        self._log("\n--- Far-Field Study Finished ---", level='progress')

    def _extract_results_for_project(self, phantom_name, freq):
        import s4l_v1.document
        
        all_sims_in_doc = list(s4l_v1.document.AllSimulations)
        if not all_sims_in_doc:
            self._log("  - No simulations found in the project document.")
            return

        self._log(f"  - Found {len(all_sims_in_doc)} simulations in the project.")
        for sim in all_sims_in_doc:
            if self._check_for_stop_signal():
                raise StudyCancelledError()
            try:
                sim_name = sim.Name
                # Expected name format: EM_FDTD_thelonius_450MHz_x_pos_theta
                parts = sim_name.split('_')
                if len(parts) < 7:
                    self._log(f"    - WARNING: Could not parse simulation name '{sim_name}'. Skipping.")
                    continue
                
                direction_name = "_".join(parts[4:-1])
                polarization_name = parts[-1]
                placement_name = f"environmental_{direction_name}_{polarization_name}"
                
                self._log(f"    - Extracting from simulation: {sim_name}", level='progress')
                extractor = ResultsExtractor(self.config, sim, phantom_name, freq, placement_name, 'far_field', self.verbose_logger, self.progress_logger, gui=self.gui, study=self)
                extractor.extract()
            except Exception as e:
                self._log(f"    - ERROR: Failed to extract results for simulation '{sim.Name}': {e}", level='progress')
                traceback.print_exc()

    def _check_for_stop_signal(self):
        """Checks the queue for a stop signal from the GUI without blocking."""
        if not self.gui or not hasattr(self.gui, 'queue'):
            return False
        try:
            msg = self.gui.queue.get_nowait()
            if msg.get('type') == 'stop':
                self._log("--- Study manually stopped by user ---", level='progress')
                return True
        except Empty:
            return False
        return False