import logging
import os
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import TYPE_CHECKING

import colorama

from goliat.osparc_batch.logging_utils import setup_job_logging
from goliat.osparc_batch.osparc_client import (
    _submit_job_in_process,
    get_osparc_client_config,
)

if TYPE_CHECKING:
    from goliat.osparc_batch.worker import Worker

main_logger = logging.getLogger("osparc_batch")


def main_process_logic(worker: "Worker"):
    """The main logic of the batch run, executed in a QThread."""
    import osparc as osparc_module

    try:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
        worker.client_cfg = get_osparc_client_config(worker.config, osparc_module)  # type: ignore

        solver_key = "simcore/services/comp/isolve-gpu"
        solver_version = "2.2.212"

        main_logger.info(f"{colorama.Fore.MAGENTA}--- Submitting Jobs to oSPARC in Parallel ---")
        worker.running_jobs = {}
        with ProcessPoolExecutor(max_workers=min(len(worker.input_files), 61) or 1) as executor:
            future_to_file = {
                executor.submit(
                    _submit_job_in_process,
                    fp,
                    worker.client_cfg,  # type: ignore
                    solver_key,
                    solver_version,
                ): fp
                for fp in worker.input_files
            }
            for future in as_completed(future_to_file):
                file_path = future_to_file[future]
                try:
                    result = future.result()
                    if result:
                        job, solver = result
                        worker.running_jobs[file_path] = (job, solver)
                        if job.id:
                            setup_job_logging(base_dir, job.id)
                            job_logger = logging.getLogger(f"job_{job.id}")
                            job_logger.info(f"Job {job.id} submitted for input file {file_path.name} at path {file_path}.")
                except Exception as exc:
                    main_logger.error(f"ERROR: Submitting job for {file_path.name} generated an exception: {exc}\n{traceback.format_exc()}")

        if not worker.running_jobs:
            main_logger.error("ERROR: No jobs were successfully submitted. Exiting.")
            worker.finished.emit()
            return

        main_logger.info(f"{colorama.Fore.MAGENTA}--- Polling for Job Completion and Downloading Results ---")
        worker.job_statuses = {job.id: ("PENDING", time.time()) for _, (job, _) in worker.running_jobs.items()}
        worker.file_to_job_id = {fp: j.id for fp, (j, s) in worker.running_jobs.items()}
        worker.downloaded_jobs = set()

        worker.timer.start(5000)

    except Exception as e:
        main_logger.error(f"\nCRITICAL ERROR in main process: {e}\n{traceback.format_exc()}")
        worker.finished.emit()
