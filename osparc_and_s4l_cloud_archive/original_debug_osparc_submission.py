import os
import sys
import logging
import time

# 1. Add project root to Python path
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

# 2. Set up logging and initialize Sim4Life
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
from src.utils import ensure_s4l_running
from src.config import Config
import s4l_v1
import XOsparcApiClient

print("--- Initializing Sim4Life ---")
ensure_s4l_running()
print("--- Sim4Life Initialized ---")

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
    client = XOsparcApiClient.OsparcApiClient(
        api_key=creds['api_key'],
        api_secret=creds['api_secret'],
        api_server=creds['api_server'],
        api_version=creds.get('api_version', 'v0')
    )
    print("oSPARC client initialized successfully.")
except Exception as e:
    print(f"Error initializing oSParc client: {e}")
    sys.exit(1)

# 5. Prepare Job Submission Data
print("\n--- Preparing Job Submission Data ---")
# Using the provided path for the input file
input_file_path = r"C:\Users\rwydaegh\Downloads\test.smash_Results"
if not os.path.exists(input_file_path):
    print(f"ERROR: Input file not found at {input_file_path}")
    sys.exit(1)

job_data = XOsparcApiClient.JobSubmissionData()
job_data.InputFilePath = input_file_path
job_data.ResourceName = "small"
job_data.SolverKey = "sim4life-isolve"
job_data.SolverVersion = ""
print("Job data prepared:")
print(f"  - Input File: {job_data.InputFilePath}")
print(f"  - Resource: {job_data.ResourceName}")
print(f"  - Solver: {job_data.SolverKey} v{job_data.SolverVersion}")


# 6. Create and Start the Job
print("\n--- Submitting Job to oSPARC ---")
try:
    print(f"Creating job for input file: {os.path.basename(input_file_path)}")
    create_response = client.CreateJob(job_data)
    if not create_response.Success:
        raise RuntimeError(f"Failed to create oSPARC job: {create_response.Content}")
    
    job_id = create_response.Content.get("id")
    if not job_id:
        raise RuntimeError("oSPARC API did not return a job ID after creation.")
    
    print(f"Job created with ID: {job_id}. Starting job...")
    start_response = client.StartJob(job_data, job_id)
    if not start_response.Success:
        raise RuntimeError(f"Failed to start oSPARC job {job_id}: {start_response.Content}")
    
    print("Job started successfully. Polling for status...")

    # 7. Poll for Job Completion
    while True:
        status_response = client.GetJobStatus(job_data.SolverKey, job_data.SolverVersion, job_id)
        if not status_response.Success:
            print(f"Warning: Could not get job status for {job_id}.")
            time.sleep(10)
            continue

        status = status_response.Content.get("state")
        print(f"  - Job '{job_id}' status: {status}")

        if status in ["SUCCESS", "FAILED", "ABORTED"]:
            print(f"Job {job_id} finished with status: {status}")
            if status != "SUCCESS":
                print(f"oSPARC job {job_id} failed with status: {status}")
            break
        
        time.sleep(20)

except Exception as e:
    print(f"An error occurred during job submission: {e}")
    import traceback
    traceback.print_exc()

print("\n--- Debug script finished ---")