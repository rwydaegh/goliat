import logging
import time
import traceback
from typing import Callable, Any
from concurrent.futures import ThreadPoolExecutor
from PySide6.QtCore import QObject, Signal, Slot, QTimer


class Worker(QObject):
    """Worker thread to run the oSPARC batch main logic and manage polling/downloads."""

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
        self.client_cfg = None

        # Executors and timers
        self.download_executor = ThreadPoolExecutor(max_workers=4)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._check_jobs_status)
        self.status_update_requested.connect(self._update_job_status)

    def run(self):
        """Starts the long-running task."""
        self.main_process_logic(self)

    def _download_job_in_thread(self, job, solver, file_path):
        """Helper to run a single download in a thread."""
        import osparc as osparc_module
        try:
            client_cfg = self.get_osparc_client_config(self.config, osparc_module)
            self.download_and_process_results(
                job, solver, client_cfg, file_path, osparc_module, self.status_update_requested
            )
        except Exception as e:
            job_logger = logging.getLogger(f'job_{job.id}')
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
            for file_path, (job, solver) in self.running_jobs.items():
                if job.id in self.downloaded_jobs or job.id in self.jobs_being_downloaded:
                    continue

                try:
                    status = solvers_api.inspect_job(solver.id, solver.version, job.id)
                    job_logger = logging.getLogger(f'job_{job.id}')
                    new_status_str = f"{status.state} ({status.progress}%)"

                    current_status, _ = self.job_statuses.get(job.id, ("UNKNOWN", time.time()))
                    if current_status != new_status_str:
                        self.job_statuses[job.id] = (new_status_str, time.time())
                        job_logger.info(f"Status update: {new_status_str}")

                    if status.state == "SUCCESS":
                        self.logger.info(f"\nJob {job.id} for {file_path.name} finished. Starting download...")
                        self.jobs_being_downloaded.add(job.id)
                        self.job_statuses[job.id] = ("DOWNLOADING", time.time())
                        self.download_executor.submit(self._download_job_in_thread, job, solver, file_path)

                    elif status.state == "FAILED":
                        job_logger.error("Job failed.")
                        self.downloaded_jobs.add(job.id)
                        if self.job_statuses.get(job.id, ("dummy", 0))[0] != "FAILED":
                            self.job_statuses[job.id] = ("FAILED", time.time())

                except Exception as exc:
                    job_logger = logging.getLogger(f'job_{job.id}')
                    job_logger.error(f"Error inspecting job {job.id}: {exc}\n{traceback.format_exc()}")
                    self.job_statuses[job.id] = ("FAILED", time.time())
                    self.downloaded_jobs.add(job.id)

    @Slot(str, str)
    def _update_job_status(self, job_id, status):
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