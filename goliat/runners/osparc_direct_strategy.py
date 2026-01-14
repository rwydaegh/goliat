"""Execution strategy for oSPARC cloud platform execution."""

import os
import time
import traceback
from typing import TYPE_CHECKING

from ..logging_manager import LoggingMixin
from .execution_strategy import ExecutionStrategy
from .post_simulation_handler import PostSimulationHandler

if TYPE_CHECKING:
    pass


class OSPARCDirectStrategy(ExecutionStrategy, LoggingMixin):
    """Execution strategy for submitting simulations to oSPARC cloud platform."""

    def __init__(self, server_name: str, *args, **kwargs):
        """Initialize oSPARC direct strategy.

        Args:
            server_name: oSPARC resource name to use (e.g., 'local', 'osparc-1').
            *args: Passed to parent class.
            **kwargs: Passed to parent class.
        """
        super().__init__(*args, **kwargs)
        self.server_name = server_name

    def run(self) -> None:
        """Submits simulation directly to oSPARC cloud platform.

        This method handles cloud-based simulation execution through the oSPARC
        platform. Instead of running locally, it uploads the solver input file
        to oSPARC, submits a job, and polls for completion.

        The process:
        1. Initializes oSPARC API client using credentials from config
        2. Creates a job submission with input file path and resource name
        3. Submits job and waits for completion (polls status periodically)
        4. Downloads results when job completes successfully
        5. Reloads project to load results into Sim4Life

        This requires Sim4Life 8.2.0 for the XOsparcApiClient module. The method
        handles authentication, job lifecycle, and error reporting.

        Raises:
            RuntimeError: If API client unavailable, job creation fails, job
                          completes with non-success status, or simulation can't
                          be found after reload.
            FileNotFoundError: If solver input file not found.
            ValueError: If oSPARC credentials are missing from config.
        """
        try:
            import XOsparcApiClient  # type: ignore # Only available in Sim4Life v8.2.0 and later.
        except ImportError as e:
            self._log(
                "Failed to import XOsparcApiClient. This module is required for direct oSPARC integration.",
                level="progress",
                log_type="error",
            )
            self._log(
                "Please ensure you are using Sim4Life version 8.2 or 9.2.",
                level="progress",
                log_type="info",
            )
            self._log(f"Original error: {e}", log_type="verbose")
            self.verbose_logger.error(traceback.format_exc())
            raise RuntimeError("Could not import XOsparcApiClient module, which is necessary for oSPARC runs.")

        self._log(
            f"--- Running simulation on oSPARC server: {self.server_name} ---",
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
        input_file_path = os.path.join(os.path.dirname(self.project_path), self.simulation.GetInputFileName())
        if not os.path.exists(input_file_path):
            raise FileNotFoundError(f"Solver input file not found at: {input_file_path}")

        job_data = XOsparcApiClient.JobSubmissionData()
        job_data.InputFilePath = input_file_path
        job_data.ResourceName = self.server_name
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
            raise RuntimeError(f"Failed to create oSPARC job: {create_response.Content}")

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
            raise RuntimeError(f"Failed to start oSPARC job {job_id}: {start_response.Content}")

        # 4. Poll for Job Completion
        self._log("Job started. Polling for status...", level="progress", log_type="progress")
        while True:
            self._check_for_stop_signal()

            status_response = client.GetJobStatus(job_data.SolverKey, job_data.SolverVersion, job_id)
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
                    raise RuntimeError(f"oSPARC job {job_id} failed with status: {status}")
                break

            time.sleep(30)

        # 5. Post-simulation steps
        post_handler = PostSimulationHandler(self.project_path, self.profiler, self.verbose_logger, self.progress_logger)
        post_handler.wait_and_reload()
