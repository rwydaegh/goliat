import os
import sys
import logging
import time
import zipfile
import argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add project root to Python path to allow importing from 'src'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.config import Config
import osparc

# --- 1. Setup Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def find_input_files(config: Config) -> list[Path]:
    """
    Finds all solver input files (.h5) based on the provided configuration.
    """
    logging.info("--- Searching for input files based on configuration ---")
    results_base_dir = Path(config.base_dir) / "results"
    study_type = config.get_setting('study_type')
    phantoms = config.get_setting('phantoms', [])
    frequencies = config.get_setting('frequencies_mhz', [])
    
    input_files = []

    if not study_type or not phantoms or not frequencies:
        raise ValueError("Configuration must specify 'study_type', 'phantoms', and 'frequencies_mhz'.")

    for phantom in phantoms:
        for freq in frequencies:
            if study_type == 'far_field':
                # For far-field, all simulations for a frequency are in one project.
                project_dir = results_base_dir / study_type / phantom.lower() / f"{freq}MHz"
                project_filename_base = f"far_field_{phantom.lower()}_{freq}MHz"
                results_folder = project_dir / f"{project_filename_base}.smash_Results"

                if results_folder.exists():
                    # Find all input files in the results directory.
                    found_files = list(results_folder.glob('*_Input.h5'))
                    if found_files:
                        # Filter based on the directions and polarizations specified in the config
                        incident_directions = config.get_setting('far_field_setup.environmental.incident_directions', [])
                        polarizations = config.get_setting('far_field_setup.environmental.polarizations', [])
                        
                        # Since we can't directly map file UUIDs to sim names without reading the project,
                        # we'll assume for now that all generated input files for that project should be run.
                        # A more robust solution might involve parsing the .smash file if needed.
                        input_files.extend(found_files)
                        logging.info(f"Found {len(found_files)} input file(s) in: {results_folder}")
                    else:
                        logging.warning(f"No input files found in expected directory: {results_folder}")
                else:
                    logging.warning(f"Results directory does not exist: {results_folder}")
            # Add logic for near_field if needed in the future
            # elif study_type == 'near_field':
            #     ...
    
    if not input_files:
        logging.error("Could not find any input files. Make sure you have run the 'setup' phase first.")
        sys.exit(1)
        
    logging.info(f"--- Found a total of {len(input_files)} input files to process. ---")
    return input_files


def get_osparc_client_config(config: Config) -> osparc.Configuration:
    """Initializes and returns the oSPARC client configuration."""
    logging.info("--- Initializing oSPARC Client ---")
    creds = config.get_osparc_credentials()
    if not all(k in creds for k in ['api_key', 'api_secret', 'api_server']):
        raise ValueError("Missing oSPARC credentials in configuration.")
    
    cfg = osparc.Configuration(
        host=creds['api_server'],
        username=creds['api_key'],
        password=creds['api_secret'],
    )
    logging.info("oSPARC client configured successfully.")
    return cfg


def submit_job(input_file_path: Path, client_cfg: osparc.Configuration, solver_key: str, solver_version: str):
    """Submits a single job to oSPARC and returns the job and solver objects."""
    with osparc.ApiClient(client_cfg) as api_client:
        files_api = osparc.FilesApi(api_client)
        solvers_api = osparc.SolversApi(api_client)

        logging.info(f"Uploading input file: {input_file_path.name}")
        input_file_osparc = files_api.upload_file(file=str(input_file_path))

        logging.info(f"Creating job for solver: {solver_key} v{solver_version}")
        solver = solvers_api.get_solver_release(solver_key, solver_version)
        
        job = solvers_api.create_job(
            solver.id,
            solver.version,
            job_inputs=osparc.JobInputs({"input_1": input_file_osparc})
        )
        
        if not job.id:
            raise RuntimeError("oSPARC API did not return a job ID after creation.")
        
        logging.info(f"Job created with ID: {job.id}. Starting job...")
        solvers_api.start_job(solver.id, solver.version, job.id)
        logging.info(f"Job {job.id} for {input_file_path.name} started successfully.")
        return job, solver


def download_and_process_results(job: osparc.Job, solver: osparc.Solver, client_cfg: osparc.Configuration, output_dir: Path):
    """Downloads and processes the results for a single job."""
    with osparc.ApiClient(client_cfg) as api_client:
        files_api = osparc.FilesApi(api_client)
        solvers_api = osparc.SolversApi(api_client)
        try:
            logging.info(f"--- Downloading results for job {job.id} ---")
            outputs = solvers_api.get_job_outputs(solver.id, solver.version, job.id)
            
            for output_name, result_file in outputs.results.items():
                logging.info(f"Downloading {output_name} for job {job.id}...")
                download_path = files_api.download_file(file_id=result_file.id)
                
                # Create a unique sub-directory for each job's results
                job_output_dir = output_dir / job.id
                job_output_dir.mkdir(parents=True, exist_ok=True)

                if result_file.filename.endswith('.zip'):
                    logging.info(f"Extracting {result_file.filename} to {job_output_dir}")
                    with zipfile.ZipFile(download_path, 'r') as zip_ref:
                        zip_ref.extractall(job_output_dir)
                    os.remove(download_path)
                else:
                    new_path = job_output_dir / result_file.filename
                    os.rename(download_path, new_path)
                    logging.info(f"Moved {output_name} to {new_path}")

        except Exception as e:
            logging.error(f"Could not retrieve results for job {job.id}: {e}")


def main(config_path: str):
    """
    Main function to find input files, run oSPARC jobs, and download results.
    """
    # --- Load Config ---
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    config = Config(base_dir, config_path)
    
    # --- Find Input Files ---
    input_files = find_input_files(config)

    # --- Initialize oSPARC Client ---
    client_cfg = get_osparc_client_config(config)

    # --- Define Solver ---
    solver_key = "simcore/services/comp/isolve-gpu"
    solver_version = "2.2.212" # Use a specific, tested version

    # --- Submit Jobs in Parallel ---
    logging.info("\n--- Submitting Jobs to oSPARC in Parallel ---")
    running_jobs = {}
    with ThreadPoolExecutor(max_workers=len(input_files) or 1) as executor:
        future_to_file = {
            executor.submit(submit_job, file_path, client_cfg, solver_key, solver_version): file_path
            for file_path in input_files
        }
        for future in as_completed(future_to_file):
            file_path = future_to_file[future]
            try:
                job, solver = future.result()
                running_jobs[job.id] = (job, solver)
            except Exception as exc:
                logging.error(f'Submitting job for {file_path.name} generated an exception: {exc}')

    if not running_jobs:
        logging.error("No jobs were successfully submitted. Exiting.")
        sys.exit(1)

    # --- Poll for Job Completion ---
    logging.info("\n--- Polling for Job Completion ---")
    all_jobs_done = False
    while not all_jobs_done:
        all_jobs_done = True
        for job_id, (job, solver) in running_jobs.items():
            with osparc.ApiClient(client_cfg) as api_client:
                solvers_api = osparc.SolversApi(api_client)
                status = solvers_api.inspect_job(solver.id, solver.version, job.id)
                logging.info(f"  - Job '{job_id}' status: {status.state} ({status.progress}%)")
                if not status.stopped_at:
                    all_jobs_done = False
        if not all_jobs_done:
            time.sleep(10)

    logging.info("\n--- All Jobs Finished ---")

    # --- Download Results in Parallel ---
    logging.info("\n--- Downloading Results in Parallel ---")
    output_dir = Path(base_dir) / "results" / "osparc_outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    logging.info(f"Results will be saved to: {output_dir}")

    with ThreadPoolExecutor(max_workers=len(running_jobs)) as executor:
        future_to_job = {
            executor.submit(download_and_process_results, job, solver, client_cfg, output_dir): job.id
            for job, solver in running_jobs.values()
        }
        for future in as_completed(future_to_job):
            job_id = future_to_job[future]
            try:
                future.result()
            except Exception as exc:
                logging.error(f'Job {job_id} generated an exception during result download: {exc}')

    logging.info("\n--- Batch oSPARC run finished ---")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run a batch of simulations on oSPARC.")
    parser.add_argument(
        '--config',
        type=str,
        required=True,
        help="Path to the configuration file (e.g., 'configs/todays_far_field_config.json')."
    )
    args = parser.parse_args()
    main(args.config)