import os
import sys
import logging
import time
import zipfile
import tempfile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

# 1. Add project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.config import Config
import osparc

# 2. Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 3. Load config to get credentials
print("\n--- Loading Configuration ---")
try:
    config = Config(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')), "configs/base_config.json")
    creds = config.get_osparc_credentials()
    if not all(k in creds for k in ['api_key', 'api_secret', 'api_server']):
        raise ValueError("Missing oSPARC credentials in configuration.")
    print("Configuration and credentials loaded successfully.")
except Exception as e:
    print(f"Error loading configuration: {e}")
    sys.exit(1)

# 4. Initialize oSPARC client
print("\n--- Initializing oSPARC Client ---")
try:
    cfg = osparc.Configuration(
        host=creds['api_server'],
        username=creds['api_key'],
        password=creds['api_secret'],
    )
    print("oSPARC client initialized successfully.")
except Exception as e:
    print(f"Error initializing oSParc client: {e}")
    sys.exit(1)

# 6. Prepare Job Submission Data
print("\n--- Preparing Job Submission Data ---")
input_files = [
    r"C:\Users\rwydaegh\Downloads\test.smash_Results\0cb530d3-858b-45ce-8e96-3c36297ec9c3_Input.h5",
    r"C:\Users\rwydaegh\Downloads\test.smash_Results\0cb530d3-858b-45ce-8e96-3c36297ec9c3_Input.h5",
]

solver_key = "simcore/services/comp/isolve-gpu"
solver_version = "2.2.212"

print("Job data prepared:")
print(f"  - Input Files: {len(input_files)}")
print(f"  - Solver: {solver_key} v{solver_version}")

def submit_job(input_file_path):
    """Submits a single job to oSPARC and returns the job object."""
    with osparc.ApiClient(cfg) as api_client:
        files_api = osparc.FilesApi(api_client)
        solvers_api = osparc.SolversApi(api_client)

        print(f"Uploading input file: {input_file_path}")
        input_file_osparc = files_api.upload_file(file=str(input_file_path))

        print(f"Creating job for solver: {solver_key}")
        solver = solvers_api.get_solver_release(solver_key, solver_version)
        
        job = solvers_api.create_job(
            solver.id,
            solver.version,
            osparc.JobInputs({"input_1": input_file_osparc})
        )
        
        if not job.id:
            raise RuntimeError("oSPARC API did not return a job ID after creation.")
        
        print(f"Job created with ID: {job.id}. Starting job...")
        solvers_api.start_job(solver.id, solver.version, job.id)
        print(f"Job {job.id} for {input_file_path} started successfully.")
        return job, solver

def download_and_process_results(job_id, job, solver, results_dir):
    """Downloads and processes the results for a single job."""
    with osparc.ApiClient(cfg) as api_client:
        files_api = osparc.FilesApi(api_client)
        solvers_api = osparc.SolversApi(api_client)
        try:
            print(f"\n--- Downloading results for job {job_id} ---")
            outputs = solvers_api.get_job_outputs(solver.id, solver.version, job.id)
            print(f"Job {outputs.job_id} got these results:")
            for output_name, result in outputs.results.items():
                print(output_name, "=", result)
                if hasattr(result, 'id'):
                    download_path = files_api.download_file(file_id=result.id)
                    print(f"Downloaded {output_name} to: {download_path}")
                    
                    if result.filename.endswith('.zip'):
                        print(f"Extracting {output_name} to {results_dir}")
                        with zipfile.ZipFile(download_path, 'r') as zip_ref:
                            zip_ref.extractall(results_dir)
                        os.remove(download_path)
                    elif result.filename.endswith('.h5'):
                        new_path = results_dir / f"{job_id}_{result.filename}"
                        os.rename(download_path, new_path)
                        print(f"Moved {output_name} to {new_path}")
                    else:
                        # Fallback for other file types
                        new_path = results_dir / f"{job_id}_{result.filename}"
                        os.rename(download_path, new_path)
                        print(f"Moved {output_name} to {new_path}")

        except Exception as res_e:
            print(f"Could not retrieve results for job {job_id}: {res_e}")

# 7. Create and Start the Jobs in Parallel
print("\n--- Submitting Jobs to oSPARC in Parallel ---")
jobs = {}
with ThreadPoolExecutor(max_workers=2) as executor:
    future_to_file = {executor.submit(submit_job, file_path): file_path for file_path in input_files}
    for future in future_to_file:
        file_path = future_to_file[future]
        try:
            job, solver = future.result()
            jobs[job.id] = (job, solver)
        except Exception as exc:
            print(f'{file_path} generated an exception: {exc}')

# 8. Poll for Job Completion
print("\n--- Polling for Job Completion ---")
all_jobs_done = False
while not all_jobs_done:
    all_jobs_done = True
    for job_id, (job, solver) in jobs.items():
        with osparc.ApiClient(cfg) as api_client:
            solvers_api = osparc.SolversApi(api_client)
            status = solvers_api.inspect_job(solver.id, solver.version, job.id)
            print(f"  - Job '{job.id}' status: {status.state} ({status.progress}%)")
            if not status.stopped_at:
                all_jobs_done = False
    if not all_jobs_done:
        time.sleep(5)

print("\n--- All Jobs Finished ---")

# 9. Download Results in Parallel
print("\n--- Downloading Results in Parallel ---")
results_dir = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / "results" / "isolve_outputs"
results_dir.mkdir(parents=True, exist_ok=True)
print(f"Results will be saved to: {results_dir}")

with ThreadPoolExecutor(max_workers=2) as executor:
    future_to_job = {executor.submit(download_and_process_results, job_id, job, solver, results_dir): job_id for job_id, (job, solver) in jobs.items()}
    for future in future_to_job:
        job_id = future_to_job[future]
        try:
            future.result()
        except Exception as exc:
            print(f'Job {job_id} generated an exception during result download: {exc}')

print("\n--- Debug script finished ---")