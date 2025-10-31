import logging
import os
import shutil
import traceback
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from goliat.osparc_batch.logging_utils import setup_console_logging

if TYPE_CHECKING:
    import osparc

    from goliat.config import Config

main_logger = setup_console_logging()


def get_osparc_client_config(config: "Config", osparc_module) -> "osparc.Configuration":
    """Initializes and returns the oSPARC client configuration."""
    creds = config.get_osparc_credentials()
    if not all(k in creds for k in ["api_key", "api_secret", "api_server"]):
        raise ValueError("Missing oSPARC credentials in configuration.")

    temp_dir = Path(config.base_dir) / "tmp_download"
    temp_dir.mkdir(exist_ok=True)

    client_config = osparc_module.Configuration(
        host=creds["api_server"],
        username=creds["api_key"],
        password=creds["api_secret"],
    )
    client_config.temp_folder_path = str(temp_dir)
    return client_config


def submit_job(
    input_file_path: Path,
    client_cfg: "osparc.Configuration",
    solver_key: str,
    solver_version: str,
    osparc_module,
) -> tuple["osparc.Job", "osparc.Solver"]:
    """Submits a single job to oSPARC and returns the job and solver objects."""
    with osparc_module.ApiClient(client_cfg) as api_client:
        files_api = osparc_module.FilesApi(api_client)
        solvers_api = osparc_module.SolversApi(api_client)

        input_file_osparc = files_api.upload_file(file=str(input_file_path))
        solver = solvers_api.get_solver_release(solver_key, solver_version)

        job = solvers_api.create_job(
            solver.id,
            solver.version,
            job_inputs=osparc_module.JobInputs({"input_1": input_file_osparc}),
        )

        if not job.id:
            raise RuntimeError("oSPARC API did not return a job ID after creation.")

        solvers_api.start_job(solver.id, solver.version, job.id)
        return job, solver


def _submit_job_in_process(
    input_file_path: Path,
    client_cfg: "osparc.Configuration",
    solver_key: str,
    solver_version: str,
) -> Optional[tuple["osparc.Job", "osparc.Solver"]]:
    """Helper function to run the oSPARC submission in a separate process."""
    import osparc as osparc_module

    try:
        return submit_job(input_file_path, client_cfg, solver_key, solver_version, osparc_module)
    except ValueError as e:
        if "Invalid value for `items`, must not be `None`" in str(e):
            main_logger.error(f"Error submitting job for {input_file_path.name}: oSPARC API returned invalid data. Skipping.")
            return None
        raise e


def download_and_process_results(
    job: "osparc.Job",
    solver: "osparc.Solver",
    client_cfg: "osparc.Configuration",
    input_file_path: Path,
    osparc_module,
    status_callback=None,
):
    """Downloads and processes the results for a single job."""
    job_logger = logging.getLogger(f"job_{job.id}")
    try:
        with osparc_module.ApiClient(client_cfg) as api_client:
            files_api = osparc_module.FilesApi(api_client)
            solvers_api = osparc_module.SolversApi(api_client)

            job_logger.info(f"--- Downloading results for job {job.id} ---")
            if status_callback:
                status_callback.emit(job.id, "DOWNLOADING")
            outputs = solvers_api.get_job_outputs(solver.id, solver.version, job.id)

            output_dir = input_file_path.parent

            for output_name, result_file in outputs.results.items():
                job_logger.info(f"Downloading {output_name} for job {job.id}...")

                download_path = files_api.download_file(file_id=result_file.id)

                if result_file.filename.endswith(".zip"):
                    job_logger.info(f"Extracting {result_file.filename} to {output_dir}")
                    with zipfile.ZipFile(download_path, "r") as zip_ref:
                        zip_ref.extractall(output_dir)

                        # --- Enhanced Log File Handling ---
                        uuid = input_file_path.stem.replace("_Input", "")
                        extracted_files = zip_ref.namelist()

                        for filename in extracted_files:
                            if filename.endswith(".log"):
                                extracted_path = output_dir / filename
                                if "input.log" in filename:
                                    new_name = f"iSolve-output-{uuid}.log"
                                else:
                                    new_name = f"{uuid}_AxLog.log"

                                final_log_path = output_dir / new_name
                                shutil.move(extracted_path, final_log_path)
                                job_logger.info(f"Renamed and moved log file to {final_log_path}")

                    os.remove(download_path)
                else:
                    if "output.h5" in result_file.filename:
                        output_filename = input_file_path.stem.replace("_Input", "_Output") + ".h5"
                    else:
                        output_filename = result_file.filename

                    final_path = output_dir / output_filename
                    shutil.move(download_path, final_path)
                    job_logger.info(f"Saved {output_name} to {final_path}")

                if status_callback:
                    status_callback.emit(job.id, "COMPLETED")

    except Exception as e:
        job_logger.error(f"Could not retrieve results for job {job.id}: {e}\n{traceback.format_exc()}")
        if status_callback:
            status_callback.emit(job.id, "FAILED")
