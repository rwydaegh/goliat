import os
import sys
import glob
import subprocess
import time
import logging
import traceback
import threading
from queue import Queue, Empty
from .utils import open_project, non_blocking_sleep
from .logging_manager import LoggingMixin

class SimulationRunner(LoggingMixin):
    """
    Manages the execution of the simulation, either through the Sim4Life API
    or by calling the iSolve.exe solver manually.
    """
    def __init__(self, config, project_path, simulations, verbose_logger, progress_logger, gui=None, study=None):
        self.config = config
        self.project_path = project_path
        self.simulations = simulations if isinstance(simulations, list) else [simulations]
        self.verbose_logger = verbose_logger
        self.progress_logger = progress_logger
        self.gui = gui
        self.study = study
        import s4l_v1.document
        self.document = s4l_v1.document


    def run_all(self):
        """
        Runs all simulations in the list, managing GUI animations.
        """
        total_sims = len(self.simulations)
        if self.gui:
            self.gui.update_stage_progress("Running Simulation", 0, total_sims)

        for i, sim in enumerate(self.simulations):
            self._log(f"\n--- Running simulation {i+1}/{total_sims}: {sim.Name} ---", level='progress')
            
            # Start animation before the run
            if self.gui:
                self.gui.start_stage_animation("run_simulation_total", i + 1)

            self.run(sim)

            # End animation and update progress after the run
            if self.gui and self.study:
                self.gui.end_stage_animation()
                progress = self.study.profiler.get_weighted_progress("run", (i + 1) / total_sims)
                self.gui.update_overall_progress(int(progress), 100)
                self.gui.update_stage_progress("Running Simulation", i + 1, total_sims)
                
        self._log("\n--- All simulations finished ---", level='progress')

    def run(self, simulation):
        """
        Runs a single simulation, wrapping the entire process in a single subtask
        for more accurate time estimation.
        """
        self._log(f"Running simulation: {simulation.Name}", level='verbose')
        if not simulation:
            self._log(f"ERROR: Simulation object not found.", level='progress')
            return

        with self.study.subtask("run_simulation_total"):
            try:
                if hasattr(simulation, "WriteInputFile"):
                    with self.study.subtask("run_write_input_file"):
                        self._log("Writing solver input file...", level='progress')
                        simulation.WriteInputFile()
                        self.document.SaveAs(self.project_path) # Force a save to flush files

                if self.config.get_manual_isolve():
                    self._run_isolve_manual(simulation)
                else:
                    simulation.RunSimulation(wait=True)
                    self._log("Simulation finished.", level='progress')
            except Exception as e:
                self._log(f"An error occurred during simulation run: {e}", level='progress')
                traceback.print_exc()

        return simulation

    def _run_isolve_manual(self, simulation):
        """
        Finds iSolve.exe, runs it in a non-blocking way, and logs its output in real-time.
        """
        # --- 1. Setup: Find paths and prepare command ---
        # The input file is now written in the run() method before this is called.

        python_path = sys.executable
        s4l_root = os.path.dirname(os.path.dirname(python_path))
        isolve_path = os.path.join(s4l_root, "Solvers", "iSolve.exe")
        if not os.path.exists(isolve_path):
            raise FileNotFoundError(f"iSolve.exe not found at the expected path: {isolve_path}")

        if not hasattr(simulation, 'GetInputFileName'):
            raise RuntimeError("Could not get input file name from simulation object.")

        relative_path = simulation.GetInputFileName()
        project_dir = os.path.dirname(self.project_path)
        input_file_path = os.path.join(project_dir, relative_path)
        if not os.path.exists(input_file_path):
            raise FileNotFoundError(f"Solver input file not found at: {input_file_path}")

        solver_kernel = self.config.get_solver_settings().get('kernel', 'Software')
        log_msg = f"Running iSolve with {solver_kernel} on {os.path.basename(input_file_path)}"
        self._log(log_msg, level='progress')

        command = [isolve_path, "-i", input_file_path]
        show_output = self.config.get_solver_settings().get('show_solver_output', True)

        # --- 2. Non-blocking reader thread setup ---
        def reader_thread(pipe, queue):
            """Reads lines from a pipe and puts them on a queue."""
            try:
                for line in iter(pipe.readline, ''):
                    queue.put(line)
            finally:
                pipe.close()

        try:
            with self.study.subtask("run_isolve_execution"):
                process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            
            output_queue = Queue()
            thread = threading.Thread(target=reader_thread, args=(process.stdout, output_queue))
            thread.daemon = True
            thread.start()

            # --- 3. Main loop: Monitor process and log output without blocking ---
            while process.poll() is None:
                try:
                    # Read all available lines from the queue
                    while True:
                        line = output_queue.get_nowait()
                        self.verbose_logger.info(line.strip())
                except Empty:
                    # No new output, sleep briefly to prevent a busy-wait
                    time.sleep(0.1)
            
            # Process has finished, get the return code
            return_code = process.returncode
            # Make sure the reader thread has finished and read all remaining output
            thread.join()
            while not output_queue.empty():
                line = output_queue.get_nowait()
                self.verbose_logger.info(line.strip())

            if return_code != 0:
                error_message = f"iSolve.exe failed with return code {return_code}."
                self._log(error_message, level='progress')
                raise RuntimeError(error_message)

            # --- 4. Post-simulation steps ---
            with self.study.subtask("run_wait_for_results"):
                self._log("Waiting for 5 seconds to ensure results are written to disk...", level='progress')
                non_blocking_sleep(5)
            
            with self.study.subtask("run_reload_project"):
                self._log("Re-opening project to load results...", level='progress')
                self.document.Close()
                open_project(self.project_path)
            
            sim_name = simulation.Name
            simulation = next((s for s in self.document.AllSimulations if s.Name == sim_name), None)
            if not simulation:
                raise RuntimeError(f"Could not find simulation '{sim_name}' after re-opening project.")
            self._log("Project reloaded and results are available.", level='progress')

        except Exception as e:
            self._log(f"An unexpected error occurred while running iSolve.exe: {e}", level='progress')
            traceback.print_exc()
            raise