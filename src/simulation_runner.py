import glob
import os
import subprocess
import sys
import threading
import time
import traceback
from queue import Empty, Queue

from .logging_manager import LoggingMixin
from .utils import non_blocking_sleep, open_project


class SimulationRunner(LoggingMixin):
    """
    Manages the execution of the simulation, either through the Sim4Life API
    or by calling the iSolve.exe solver manually.
    """

    def __init__(
        self,
        config,
        project_path,
        simulations,
        verbose_logger,
        progress_logger,
        gui=None,
        study=None,
    ):
        """Initializes the SimulationRunner.

        Args:
            config (Config): The configuration object for the study.
            project_path (str): The file path to the Sim4Life project.
            simulations (list or Simulation): A single simulation or a list of simulations to be run.
            verbose_logger (logging.Logger): Logger for detailed, verbose output.
            progress_logger (logging.Logger): Logger for high-level progress updates.
            gui (QueueGUI, optional): The GUI proxy for sending updates to the main process. Defaults to None.
            study (BaseStudy, optional): The parent study object, used for profiling and context. Defaults to None.
        """
        self.config = config
        self.project_path = project_path
        self.simulations = (
            simulations if isinstance(simulations, list) else [simulations]
        )
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
            self._log(
                f"\n--- Running simulation {i+1}/{total_sims}: {sim.Name} ---",
                level="progress",
                log_type="header",
            )

            # Start animation before the run
            if self.gui:
                self.gui.start_stage_animation("run_simulation_total", i + 1)

            self.run(sim)

            # End animation and update progress after the run
            if self.gui and self.study:
                self.gui.end_stage_animation()
                progress = self.study.profiler.get_weighted_progress(
                    "run", (i + 1) / total_sims
                )
                self.gui.update_overall_progress(int(progress), 100)
                self.gui.update_stage_progress("Running Simulation", i + 1, total_sims)

        self._log(
            "\n--- All simulations finished ---", level="progress", log_type="success"
        )

    def run(self, simulation):
        """
        Runs a single simulation, wrapping the entire process in a single subtask
        for more accurate time estimation.
        """
        if not simulation:
            self._log(
                "ERROR: Simulation object not found. Cannot run simulation.",
                level="progress",
                log_type="error",
            )
            return
        self._log(f"Running simulation: {simulation.Name}", log_type="verbose")

        with self.study.subtask("run_simulation_total"):
            server_name = self.config.get_server()

            try:
                if hasattr(simulation, "WriteInputFile"):
                    with self.study.subtask("run_write_input_file"):
                        self._log(
                            "Writing solver input file...",
                            level="progress",
                            log_type="progress",
                        )
                        simulation.WriteInputFile()
                        self.document.SaveAs(
                            self.project_path
                        )  # Force a save to flush files

                # Stop here if we only want to write the input file
                if self.config.get_only_write_input_file():
                    self._log(
                        "'only_write_input_file' is true, skipping simulation run.",
                        level="progress",
                        log_type="info",
                    )
                    return

                if self.config.get_manual_isolve():
                    self._run_isolve_manual(simulation)
                elif server_name and server_name != "localhost":
                    self._run_osparc_direct(simulation, server_name)
                else:
                    # Fallback to localhost if no server or localhost is specified
                    simulation.RunSimulation(wait=True, server_id=None)
                    self._log(
                        "Simulation finished on localhost.",
                        level="progress",
                        log_type="success",
                    )

            except Exception as e:
                self._log(
                    f"An error occurred during simulation run: {e}",
                    level="progress",
                    log_type="error",
                )
                # Check if a cloud server was intended for the run
                if self.config.get_server() and self.config.get_server() != "localhost":
                    self._log(
                        "If you are running on the cloud, please ensure you are logged into Sim4Life "
                        "via the GUI and your API credentials are correct.",
                        level="progress",
                        log_type="warning",
                    )
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
            raise FileNotFoundError(
                f"iSolve.exe not found at the expected path: {isolve_path}"
            )

        if not hasattr(simulation, "GetInputFileName"):
            raise RuntimeError("Could not get input file name from simulation object.")

        relative_path = simulation.GetInputFileName()
        project_dir = os.path.dirname(self.project_path)
        input_file_path = os.path.join(project_dir, relative_path)
        if not os.path.exists(input_file_path):
            raise FileNotFoundError(
                f"Solver input file not found at: {input_file_path}"
            )

        solver_kernel = self.config.get_solver_settings().get("kernel", "Software")
        log_msg = f"Running iSolve with {solver_kernel} on {os.path.basename(input_file_path)}"
        self._log(log_msg, level="progress", log_type="info")

        command = [isolve_path, "-i", input_file_path]

        # --- 2. Non-blocking reader thread setup ---
        def reader_thread(pipe, queue):
            """Reads lines from a subprocess pipe and puts them onto a queue.

            This function is designed to be run in a separate thread to allow for
            non-blocking reading of a subprocess's stdout or stderr.

            Args:
                pipe: The pipe to read from (e.g., process.stdout).
                queue (Queue): The queue to put the read lines onto.
            """
            try:
                for line in iter(pipe.readline, ""):
                    queue.put(line)
            finally:
                pipe.close()

        try:
            with self.study.subtask("run_isolve_execution"):
                process = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )

                output_queue = Queue()
                thread = threading.Thread(
                    target=reader_thread, args=(process.stdout, output_queue)
                )
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
                    self._log(error_message, level="progress", log_type="error")
                    raise RuntimeError(error_message)

            # --- 4. Post-simulation steps ---
            with self.study.subtask("run_wait_for_results"):
                self._log(
                    "Waiting for 5 seconds to ensure results are written to disk...",
                    level="progress",
                    log_type="info",
                )
                non_blocking_sleep(5)

            with self.study.subtask("run_reload_project"):
                self._log(
                    "Re-opening project to load results...",
                    level="progress",
                    log_type="progress",
                )
                self.document.Close()
                open_project(self.project_path)

            sim_name = simulation.Name
            simulation = next(
                (s for s in self.document.AllSimulations if s.Name == sim_name), None
            )
            if not simulation:
                raise RuntimeError(
                    f"Could not find simulation '{sim_name}' after re-opening project."
                )
            self._log(
                "Project reloaded and results are available.",
                level="progress",
                log_type="success",
            )

        except Exception as e:
            self._log(
                f"An unexpected error occurred while running iSolve.exe: {e}",
                level="progress",
                log_type="error",
            )
            traceback.print_exc()
            raise

    def _run_osparc_direct(self, simulation, server_name):
        """
        Submits a job directly to the oSPARC platform, bypassing server discovery.
        """
        try:
            import XOsparcApiClient  # Only available in Sim4Life v8.2.2 and later.
        except ImportError as e:
            self._log(
                "Failed to import XOsparcApiClient. This module is required for direct oSPARC integration.",
                level="progress",
                log_type="error",
            )
            self._log(
                "Please ensure you are using Sim4Life version 8.2.2 or higher.",
                level="progress",
                log_type="info",
            )
            self._log(f"Original error: {e}", log_type="verbose")
            traceback.print_exc()
            raise RuntimeError(
                "Could not import XOsparcApiClient module, which is necessary for oSPARC runs."
            )

        self._log(
            "--- Running simulation directly on oSPARC ---",
            level="progress",
            log_type="header",
        )

        # 1. Get Credentials and Initialize Client
        creds = self.config.get_osparc_credentials()
        if not all(k in creds for k in ["api_key", "api_secret", "api_server"]):
            raise ValueError("Missing oSPARC credentials in configuration.")

        client = XOsparcApiClient.OsparcApiClient(
            api_key=creds["api_key"],
            api_secret=creds["api_secret"],
            api_server=creds["api_server"],
            api_version=creds.get("api_version", "v0"),
        )
        self._log("oSPARC client initialized.", log_type="verbose")

        # 2. Prepare Job Submission Data
        input_file_path = os.path.join(
            os.path.dirname(self.project_path), simulation.GetInputFileName()
        )
        if not os.path.exists(input_file_path):
            raise FileNotFoundError(
                f"Solver input file not found at: {input_file_path}"
            )

        job_data = XOsparcApiClient.JobSubmissionData()
        job_data.InputFilePath = input_file_path
        job_data.ResourceName = server_name
        job_data.SolverKey = "sim4life-isolve"
        job_data.SolverVersion = ""  # Let the API choose the default version

        # 3. Create and Start the Job
        self._log(
            f"Creating job for input file: {os.path.basename(input_file_path)}",
            level="progress",
            log_type="info",
        )
        create_response = client.CreateJob(job_data)
        if not create_response.Success:
            raise RuntimeError(
                f"Failed to create oSPARC job: {create_response.Content}"
            )

        job_id = create_response.Content.get("id")
        if not job_id:
            raise RuntimeError("oSPARC API did not return a job ID after creation.")

        self._log(
            f"Job created with ID: {job_id}. Starting job...",
            level="progress",
            log_type="info",
        )
        start_response = client.StartJob(job_data, job_id)
        if not start_response.Success:
            raise RuntimeError(
                f"Failed to start oSPARC job {job_id}: {start_response.Content}"
            )

        # 4. Poll for Job Completion
        self._log(
            "Job started. Polling for status...", level="progress", log_type="progress"
        )
        while True:
            status_response = client.GetJobStatus(
                job_data.SolverKey, job_data.SolverVersion, job_id
            )
            if not status_response.Success:
                self._log(
                    f"Warning: Could not get job status for {job_id}.",
                    level="progress",
                    log_type="warning",
                )
                time.sleep(10)
                continue

            status = status_response.Content.get("state")
            self._log(f"  - Job '{job_id}' status: {status}", log_type="verbose")

            if status in ["SUCCESS", "FAILED", "ABORTED"]:
                log_type = "success" if status == "SUCCESS" else "error"
                self._log(
                    f"Job {job_id} finished with status: {status}",
                    level="progress",
                    log_type=log_type,
                )
                if status != "SUCCESS":
                    raise RuntimeError(
                        f"oSPARC job {job_id} failed with status: {status}"
                    )
                break

            time.sleep(30)

        # 5. Post-simulation steps (similar to _run_isolve_manual)
        with self.study.subtask("run_wait_for_results"):
            self._log(
                "Waiting for 5 seconds to ensure results are written to disk...",
                level="progress",
                log_type="info",
            )
            non_blocking_sleep(5)

        with self.study.subtask("run_reload_project"):
            self._log(
                "Re-opening project to load results...",
                level="progress",
                log_type="progress",
            )
            self.document.Close()
            open_project(self.project_path)

        sim_name = simulation.Name
        simulation = next(
            (s for s in self.document.AllSimulations if s.Name == sim_name), None
        )
        if not simulation:
            raise RuntimeError(
                f"Could not find simulation '{sim_name}' after re-opening project."
            )
        self._log(
            "Project reloaded and results are available.",
            level="progress",
            log_type="success",
        )
