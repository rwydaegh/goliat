import os
import sys
import logging
import time
import zipfile
import tempfile
from pathlib import Path

# 1. Add project root to Python path
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

# 2. Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
from src.config import Config
import osparc

# 3. Load config to get credentials
print("\n--- Loading Configuration ---")
try:
    config = Config(base_dir, "configs/base_config.json")
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

# 5. Prepare Job Submission Data
print("\n--- Preparing Job Submission Data ---")
solver_key = "simcore/services/comp/s4l-python-runner-gpu"
solver_version = "1.2.212"
runner_script_path = Path("osparc_and_s4l_cloud_archive/inspect_environment.py")

print("Job data prepared:")
print(f"  - Runner Script: {runner_script_path}")
print(f"  - Solver: {solver_key} v{solver_version}")

# 6. Create and Start the Job
print("\n--- Submitting Job to oSPARC ---")
try:
    with osparc.ApiClient(cfg) as api_client:
        files_api = osparc.FilesApi(api_client)
        solvers_api = osparc.SolversApi(api_client)

        # Zip the runner script
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp_zip_file:
            with zipfile.ZipFile(tmp_zip_file.name, 'w') as zf:
                # The runner expects the script to be named main.py
                zf.write(runner_script_path, "main.py")
            tmp_zip_path = tmp_zip_file.name

        print(f"Uploading zipped input bundle: {tmp_zip_path}")
        input_bundle_osparc = files_api.upload_file(file=tmp_zip_path)
        os.remove(tmp_zip_path) # Clean up the temporary zip file

        print(f"Creating job for runner: {runner_script_path.name}")
        solver = solvers_api.get_solver_release(solver_key, solver_version)
        
        job = solvers_api.create_job(
            solver.id,
            solver.version,
            osparc.JobInputs({"input_1": input_bundle_osparc})
        )
        
        if not job.id:
            raise RuntimeError("oSPARC API did not return a job ID after creation.")
        
        print(f"Job created with ID: {job.id}. Starting job...")
        status = solvers_api.start_job(solver.id, solver.version, job.id)
        
        print("Job started successfully. Polling for status...")

        # 7. Poll for Job Completion
        while not status.stopped_at:
            time.sleep(3)
            status = solvers_api.inspect_job(solver.id, solver.version, job.id)
            print(f"  - Job '{job.id}' status: {status.state} ({status.progress}%)")

        print(f"Job {job.id} finished with status: {status.state}")
        print("Waiting for logs to become available...")
        time.sleep(10) # Wait 10 seconds for logs to be processed
        print("Downloading logs...")
        try:
            logfile_path = solvers_api.get_job_output_logfile(solver.id, solver.version, job.id)
            print(f"Log file downloaded to: {logfile_path}")
            with zipfile.ZipFile(logfile_path, 'r') as zip_ref:
                for member in zip_ref.infolist():
                    print(f"\n--- Log Content: {member.filename} ---")
                    # Use a try-except block to handle potential binary logs
                    try:
                        print(zip_ref.read(member).decode())
                    except UnicodeDecodeError:
                        print("Could not decode log file, it may be binary.")

        except Exception as log_e:
            print(f"Could not retrieve logs: {log_e}")

except Exception as e:
    print(f"An error occurred during job submission: {e}")
    import traceback
    traceback.print_exc()

print("\n--- Environment inspection script finished ---")