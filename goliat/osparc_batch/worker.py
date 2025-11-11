import logging
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QObject, QTimer, Signal, Slot


class Worker(QObject):
    """Worker thread for oSPARC batch logic, polling, and downloads."""

    finished = Signal()
    progress = Signal(str)
    status_update_requested = Signal(str, str)

    def __init__(
        self,
        config_path: str,
        logger: logging.Logger,
        get_osparc_client_config_func: Callable[..., Any],
        download_and_process_results_func: Callable[..., Any],
        get_progress_report_func: Callable[..., str],
        main_process_logic_func: Callable[..., Any],
    ):
        super().__init__()
        # Inputs / injected dependencies
        self.config_path = config_path
        self.logger = logger
        self.get_osparc_client_config = get_osparc_client_config_func
        self.download_and_process_results = download_and_process_results_func
        self.get_progress_report = get_progress_report_func
        self.main_process_logic = main_process_logic_func

        # Runtime state
        self.config = None
        self.stop_requested = False
        self.input_files = []
        self.job_statuses = {}
        self.file_to_job_id = {}
        self.running_jobs = {}
        self.downloaded_jobs = set()
        self.jobs_being_downloaded = set()
        self.file_retries = {}  # Correct: Associate retries with the file path
        self.client_cfg = None

        # Executors and timers
        self.download_executor = ThreadPoolExecutor(max_workers=4)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._check_jobs_status)
        self.status_update_requested.connect(self._update_job_status)

    def run(self):
        """Starts the long-running task."""
        self.main_process_logic(self)

    def _download_job_in_thread(self, job, solver, file_path: Path):
        """Runs a single download in a thread."""
        import osparc as osparc_module

        try:
            client_cfg = self.get_osparc_client_config(self.config, osparc_module)
            self.download_and_process_results(
                job,
                solver,
                client_cfg,
                file_path,
                osparc_module,
                self.status_update_requested,
            )
        except Exception as e:
            job_logger = logging.getLogger(f"job_{job.id}")
            job_logger.error(f"Error during download for job {job.id}: {e}\n{traceback.format_exc()}")
            self.status_update_requested.emit(job.id, "FAILED")
        finally:
            if job.id in self.jobs_being_downloaded:
                self.jobs_being_downloaded.remove(job.id)
            self.downloaded_jobs.add(job.id)

    def _check_jobs_status(self):
        """Periodically checks the status of running jobs."""
        if self.stop_requested or len(self.downloaded_jobs) >= len(self.running_jobs):
            if self.timer.isActive():
                self.timer.stop()
            self.download_executor.shutdown()
            self.logger.info("\n--- All Jobs Finished or Stopped ---")
            final_report = self.get_progress_report(self.input_files, self.job_statuses, self.file_to_job_id)
            self.logger.info(final_report)
            self.finished.emit()
            return

        import osparc as osparc_module

        with osparc_module.ApiClient(self.client_cfg) as api_client:
            solvers_api = osparc_module.SolversApi(api_client)
            # Iterate over a copy of the items, as the dictionary may be modified during the loop
            for file_path, (job, solver) in list(self.running_jobs.items()):
                if job.id in self.downloaded_jobs or job.id in self.jobs_being_downloaded:
                    continue

                try:
                    status = solvers_api.inspect_job(solver.id, solver.version, job.id)
                    job_logger = logging.getLogger(f"job_{job.id}")
                    new_status_str = f"{status.state} ({status.progress}%)"

                    current_status_str, _ = self.job_statuses.get(job.id, ("UNKNOWN", time.time()))

                    if status.state == current_status_str.split(" "):
                        self.job_statuses[job.id] = (
                            new_status_str,
                            self.job_statuses[job.id],
                        )
                    else:
                        self.job_statuses[job.id] = (new_status_str, time.time())
                        job_logger.info(f"Status update: {new_status_str}")

                    if status.state == "SUCCESS":
                        self.logger.info(f"\nJob {job.id} for {file_path.name} finished. Starting download...")
                        self.jobs_being_downloaded.add(job.id)
                        self.job_statuses[job.id] = ("DOWNLOADING", time.time())
                        self.download_executor.submit(self._download_job_in_thread, job, solver, file_path)

                    elif status.state == "FAILED":
                        job_logger.error(f"Job {job.id} for {file_path.name} has failed.")

                        retries = self.file_retries.get(file_path, 0)
                        if retries < 3:
                            new_retry_count = retries + 1
                            self.file_retries[file_path] = new_retry_count
                            job_logger.warning(f"Retrying job for {file_path.name} (attempt {new_retry_count}/3)...")
                            self.status_update_requested.emit(job.id, f"RETRYING ({new_retry_count}/3)")
                            self._resubmit_job(file_path)
                        else:
                            job_logger.error(f"Job for {file_path.name} has failed after {retries} retries. Giving up.")
                            self.downloaded_jobs.add(job.id)
                            if self.job_statuses.get(job.id, ("dummy", 0)) != "FAILED":
                                self.job_statuses[job.id] = ("FAILED", time.time())

                except Exception as exc:
                    job_logger = logging.getLogger(f"job_{job.id}")
                    job_logger.error(f"Error inspecting job {job.id}: {exc}\n{traceback.format_exc()}")
                    self.job_statuses[job.id] = ("FAILED", time.time())
                    self.downloaded_jobs.add(job.id)

    def _resubmit_job(self, file_path: Path):
        """Resubmits a failed job."""
        from goliat.osparc_batch.osparc_client import (
            _submit_job_in_process,
        )
        from goliat.osparc_batch.logging_utils import setup_job_logging

        try:
            base_dir = self.config.base_dir  # type: ignore
            solver_key = "simcore/services/comp/isolve-gpu"
            solver_version = "2.2.212"

            # --- State Cleanup for the Old Job ---
            old_job_id = self.file_to_job_id.pop(file_path, None)
            if old_job_id:
                self.running_jobs.pop(file_path, None)
                self.job_statuses.pop(old_job_id, None)
                self.downloaded_jobs.discard(old_job_id)

            # --- Submit New Job ---
            job, solver = _submit_job_in_process(file_path, self.client_cfg, solver_key, solver_version)  # type: ignore
            if job and job.id:
                setup_job_logging(base_dir, job.id)
                job_logger = logging.getLogger(f"job_{job.id}")
                job_logger.info(f"Resubmitted as new job {job.id} for input file {file_path.name}.")

                # --- State Update for the New Job ---
                self.running_jobs[file_path] = (job, solver)
                self.file_to_job_id[file_path] = job.id
                self.job_statuses[job.id] = ("PENDING", time.time())
                # The retry count is already updated in _check_jobs_status using self.file_retries
            else:
                self.logger.error(f"Failed to resubmit job for {file_path.name}. The job will be marked as FAILED.")
                if old_job_id:
                    self.file_to_job_id[file_path] = old_job_id
                    self.job_statuses[old_job_id] = ("FAILED", time.time())
                    self.downloaded_jobs.add(old_job_id)

        except Exception as e:
            self.logger.error(f"Critical error during job resubmission for {file_path.name}: {e}\n{traceback.format_exc()}")

    @Slot(str, str)
    def _update_job_status(self, job_id: str, status: str):
        """Thread-safe method to update job status."""
        self.job_statuses[job_id] = (status, time.time())

    @Slot()
    def request_progress_report(self):
        """Handles the request for a progress report."""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        self.logger.info(f"--- Progress report requested by user at {timestamp} ---")
        if not self.input_files:
            self.logger.info("No input files found yet. The process may still be initializing.")
            return
        report = self.get_progress_report(self.input_files, self.job_statuses, self.file_to_job_id)
        self.logger.info(report)

    @Slot()
    def stop(self):
        """Requests the worker to stop."""
        self.logger.info("--- Stop requested by user ---")
        self.stop_requested = True
        if self.timer.isActive():
            self.timer.stop()
        # The cancel_futures parameter is available in Python 3.9+
        # For older versions, this will gracefully shut down.
        self.download_executor.shutdown(wait=False, cancel_futures=True)
        self.finished.emit()
        if self.thread():
            self.thread().quit()
            self.thread().wait()

    @Slot()
    def cancel_jobs(self):
        """Cancels all running jobs and then stops the worker."""
        self.logger.info("--- Cancellation of all jobs requested by user ---")
        self.stop_requested = True
        if self.timer.isActive():
            self.timer.stop()

        # Run the cancel_all_jobs function
        try:
            import os
            from goliat.utils.scripts.cancel_all_jobs import cancel_all_jobs

            config_path = self.config_path
            max_jobs = len(self.running_jobs)

            # Determine base_dir from config_path
            if os.path.isabs(config_path):
                base_dir = os.path.dirname(os.path.dirname(config_path)) if "configs" in config_path else os.path.dirname(config_path)
            else:
                base_dir = os.getcwd()

            self.logger.info(f"Running cancellation for {max_jobs} jobs...")
            cancel_all_jobs(config_path, max_jobs, base_dir=base_dir)
            self.logger.info("--- Job cancellation finished ---")
        except Exception as e:
            self.logger.error(f"An unexpected error occurred during job cancellation: {e}")
        finally:
            self.download_executor.shutdown(wait=False, cancel_futures=True)
            self.finished.emit()
            if self.thread():
                self.thread().quit()
                self.thread().wait()
