import os
import sys
import logging
import time
import zipfile
import argparse
import shutil
import traceback
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from collections import defaultdict
from PySide6.QtCore import QObject, Signal, QThread, Slot, QTimer
import colorama
from batch_gui import BatchGUI

# --- 1. Setup Logging & Colors ---
def setup_job_logging(base_dir: str, job_id: str):
    """Set up a unique log file for each job in a specific subdirectory."""
    log_dir = Path(base_dir) / "logs" / "osparc_submission_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file_path = log_dir / f"job_{job_id}.log"

    job_logger = logging.getLogger(f'job_{job_id}')
    job_logger.setLevel(logging.INFO)
    job_logger.propagate = False

    if job_logger.hasHandlers():
        job_logger.handlers.clear()

    file_handler = logging.FileHandler(log_file_path, mode='w')
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    job_logger.addHandler(file_handler)
    
    return job_logger

colorama.init(autoreset=True)
STATUS_COLORS = {
    "PENDING": colorama.Fore.YELLOW,
    "PUBLISHED": colorama.Fore.LIGHTYELLOW_EX,
    "WAITING_FOR_CLUSTER": colorama.Fore.MAGENTA,
    "WAITING_FOR_RESOURCES": colorama.Fore.LIGHTMAGENTA_EX,
    "STARTED": colorama.Fore.CYAN,
    "SUCCESS": colorama.Fore.GREEN,
    "FAILED": colorama.Fore.RED,
    "DOWNLOADING": colorama.Fore.BLUE,
    "FINALIZING": colorama.Fore.CYAN,
    "FINISHED": colorama.Fore.GREEN,
    "UNKNOWN": colorama.Fore.WHITE,
}

# --- 2. Core Functions ---
def find_input_files(config) -> list[Path]:
    """Finds all solver input files (.h5) based on the provided configuration."""
    print("--- Searching for input files based on configuration ---")
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
                project_dir = results_base_dir / study_type / phantom.lower() / f"{freq}MHz"
                project_filename_base = f"far_field_{phantom.lower()}_{freq}MHz"
                results_folder = project_dir / f"{project_filename_base}.smash_Results"

                if results_folder.exists():
                    found_files = list(results_folder.glob('*_Input.h5'))
                    if found_files:
                        input_files.extend(found_files)
                        print(f"Found {len(found_files)} input file(s) in: {results_folder}")
                    else:
                        print(f"WARNING: No input files found in expected directory: {results_folder}")
                else:
                    print(f"WARNING: Results directory does not exist: {results_folder}")

    if not input_files:
        print("ERROR: Could not find any input files. Make sure you have run the 'setup' phase first.")
        sys.exit(1)
    
    print(f"--- Found a total of {len(input_files)} input files to process. ---")
    return input_files


def get_osparc_client_config(config, osparc_module):
    """Initializes and returns the oSPARC client configuration."""
    creds = config.get_osparc_credentials()
    if not all(k in creds for k in ['api_key', 'api_secret', 'api_server']):
        raise ValueError("Missing oSPARC credentials in configuration.")
    
    return osparc_module.Configuration(
        host=creds['api_server'],
        username=creds['api_key'],
        password=creds['api_secret'],
    )


def submit_job(input_file_path: Path, client_cfg, solver_key: str, solver_version: str, osparc_module):
    """Submits a single job to oSPARC and returns the job and solver objects."""
    with osparc_module.ApiClient(client_cfg) as api_client:
        files_api = osparc_module.FilesApi(api_client)
        solvers_api = osparc_module.SolversApi(api_client)

        input_file_osparc = files_api.upload_file(file=str(input_file_path))
        solver = solvers_api.get_solver_release(solver_key, solver_version)
        
        job = solvers_api.create_job(
            solver.id,
            solver.version,
            job_inputs=osparc_module.JobInputs({"input_1": input_file_osparc})
        )
        
        if not job.id:
            raise RuntimeError("oSPARC API did not return a job ID after creation.")
        
        solvers_api.start_job(solver.id, solver.version, job.id)
        return job, solver

def _submit_job_in_process(input_file_path: Path, client_cfg, solver_key: str, solver_version: str):
    """Helper function to run the oSPARC submission in a separate process."""
    import osparc as osparc_module
    return submit_job(input_file_path, client_cfg, solver_key, solver_version, osparc_module)


def download_and_process_results(job, solver, client_cfg, input_file_path, osparc_module, status_callback=None):
    """Downloads and processes the results for a single job."""
    job_logger = logging.getLogger(f'job_{job.id}')
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
                
                if status_callback:
                    status_callback.emit(job.id, "FINALIZING")
                
                if result_file.filename.endswith('.zip'):
                    job_logger.info(f"Extracting {result_file.filename} to {output_dir}")
                    with zipfile.ZipFile(download_path, 'r') as zip_ref:
                        zip_ref.extractall(output_dir)
                    os.remove(download_path)
                else:
                    if "output.h5" in result_file.filename:
                        output_filename = input_file_path.stem.replace('_Input', '_Output') + ".h5"
                    else:
                        output_filename = result_file.filename
                    
                    final_path = output_dir / output_filename
                    shutil.move(download_path, final_path)
                    job_logger.info(f"Saved {output_name} to {final_path}")
                
                if status_callback:
                    status_callback.emit(job.id, "FINISHED")

    except Exception as e:
        job_logger.error(f"Could not retrieve results for job {job.id}: {e}\n{traceback.format_exc()}")
        if status_callback:
            status_callback.emit(job.id, "FAILED")


def get_progress_report(input_files, job_statuses, file_to_job_id) -> str:
    """Generates a status summary and a colored file tree string."""
    report_lines = []
    
    status_counts = defaultdict(int)
    for status_str in job_statuses.values():
        state = status_str.split(" ")[0]
        status_counts[state] += 1
    summary = " | ".join(f"{state}: {count}" for state, count in sorted(status_counts.items()))
    report_lines.append(f"\n--- Progress Summary ---\n{summary}\n")

    tree = defaultdict(lambda: defaultdict(list))
    if not input_files:
        return ""
    common_path_str = os.path.commonpath([str(p.parent) for p in input_files])
    base_path = Path(common_path_str)

    for file_path in input_files:
        try:
            relative_path = file_path.relative_to(base_path)
            parts = list(relative_path.parts)
            if not parts:
                continue

            current_level = tree
            for part in parts[:-1]:
                current_level = current_level[part]
            
            filename = parts[-1]
            parent_key = parts[-2] if len(parts) > 1 else base_path.name
            
            if isinstance(current_level.get(parent_key), dict):
                current_level[parent_key][filename] = file_to_job_id.get(file_path)
            else:
                current_level[parent_key] = {filename: file_to_job_id.get(file_path)}

        except (IndexError, ValueError) as e:
            report_lines.append(f"Could not process path {file_path}: {e}")

    def build_tree_recursive(node, prefix=""):
        items = sorted(node.keys())
        for i, item in enumerate(items):
            is_last = i == len(items) - 1
            connector = "└── " if is_last else "├── "
            
            if isinstance(node[item], dict):
                report_lines.append(f"{prefix}{connector}{colorama.Fore.WHITE}{item}")
                new_prefix = prefix + ("    " if is_last else "│   ")
                build_tree_recursive(node[item], new_prefix)
            else:
                job_id = node[item]
                status_str = job_statuses.get(job_id, "UNKNOWN")
                status = status_str.split(" ")[0]
                color = STATUS_COLORS.get(status, colorama.Fore.WHITE)
                colored_text = f"{color}{item} (oSPARC Job: {job_id}, Status: {status_str}){colorama.Style.RESET_ALL}"
                report_lines.append(f"{prefix}{connector}{colored_text}")

    report_lines.append("--- File Status Tree ---")
    build_tree_recursive(tree)
    report_lines.append("------------------------\n")
    
    return "\n".join(report_lines)


# --- 3. Main Process Logic ---
def main_process_logic(worker: 'Worker'):
    """The main logic of the batch run, now running in a QThread."""
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from src.config import Config
    import osparc as osparc_module

    try:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        
        config = Config(base_dir, worker.config_path)
        worker.config = config
        worker.input_files = find_input_files(config)
        worker.client_cfg = get_osparc_client_config(config, osparc_module)
        
        solver_key = "simcore/services/comp/isolve-gpu"
        solver_version = "2.2.212"

        worker.progress.emit("--- Submitting Jobs to oSPARC in Parallel ---")
        worker.running_jobs = {}
        with ProcessPoolExecutor(max_workers=len(worker.input_files) or 1) as executor:
            future_to_file = {
                executor.submit(_submit_job_in_process, fp, worker.client_cfg, solver_key, solver_version): fp
                for fp in worker.input_files
            }
            for future in as_completed(future_to_file):
                file_path = future_to_file[future]
                try:
                    job, solver = future.result()
                    worker.running_jobs[file_path] = (job, solver)
                    setup_job_logging(base_dir, job.id)
                    job_logger = logging.getLogger(f'job_{job.id}')
                    job_logger.info(f"Job {job.id} submitted for input file {file_path.name} at path {file_path}.")
                except Exception as exc:
                    worker.progress.emit(f'ERROR: Submitting job for {file_path.name} generated an exception: {exc}\n{traceback.format_exc()}')

        if not worker.running_jobs:
            worker.progress.emit("ERROR: No jobs were successfully submitted. Exiting.")
            worker.finished.emit()
            return

        worker.progress.emit("--- Polling for Job Completion and Downloading Results ---")
        worker.job_statuses = {job.id: "PENDING" for _, (job, _) in worker.running_jobs.items()}
        worker.file_to_job_id = {fp: j.id for fp, (j, s) in worker.running_jobs.items()}
        worker.downloaded_jobs = set()
        
        worker.timer.start(5000)

    except Exception as e:
        worker.progress.emit(f"\nCRITICAL ERROR in main process: {e}\n{traceback.format_exc()}")
        worker.finished.emit()

# --- 4. Main Entry Point ---
class Worker(QObject):
    """Worker thread to run the main logic."""
    finished = Signal()
    progress = Signal(str)
    status_update_requested = Signal(str, str)

    def __init__(self, config_path):
        super().__init__()
        self.config_path = config_path
        self.config = None
        self.stop_requested = False
        self.input_files = []
        self.job_statuses = {}
        self.file_to_job_id = {}
        self.running_jobs = {}
        self.downloaded_jobs = set()
        self.jobs_being_downloaded = set()
        self.client_cfg = None
        self.download_executor = ThreadPoolExecutor(max_workers=4)
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._check_jobs_status)
        self.status_update_requested.connect(self._update_job_status)

    def run(self):
        """Starts the long-running task."""
        main_process_logic(self)

    def _download_job_in_thread(self, job, solver, file_path):
        """Helper to run a single download in a thread."""
        import osparc as osparc_module
        try:
            client_cfg = get_osparc_client_config(self.config, osparc_module)
            download_and_process_results(job, solver, client_cfg, file_path, osparc_module, self.status_update_requested)
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
            self.timer.stop()
            self.download_executor.shutdown()
            self.progress.emit("\n--- All Jobs Finished or Stopped ---")
            final_report = get_progress_report(self.input_files, self.job_statuses, self.file_to_job_id)
            self.progress.emit(final_report)
            self.finished.emit()
            return

        import osparc as osparc_module
        with osparc_module.ApiClient(self.client_cfg) as api_client:
            solvers_api = osparc_module.SolversApi(api_client)
            for file_path, (job, solver) in self.running_jobs.items():
                if job.id in self.downloaded_jobs:
                    continue

                try:
                    status = solvers_api.inspect_job(solver.id, solver.version, job.id)
                    job_logger = logging.getLogger(f'job_{job.id}')
                    new_status_str = f"{status.state} ({status.progress}%)"

                    if self.job_statuses.get(job.id) != new_status_str:
                        self.job_statuses[job.id] = new_status_str
                        job_logger.info(f"Status update: {new_status_str}")

                    if status.state == "SUCCESS" and job.id not in self.jobs_being_downloaded:
                        self.progress.emit(f"\nJob {job.id} for {file_path.name} finished. Starting download...")
                        self.jobs_being_downloaded.add(job.id)
                        self.download_executor.submit(self._download_job_in_thread, job, solver, file_path)
                    
                    elif status.state == "FAILED":
                        job_logger.error("Job failed.")
                        self.downloaded_jobs.add(job.id)

                except Exception as exc:
                    job_logger = logging.getLogger(f'job_{job.id}')
                    job_logger.error(f"Error inspecting job {job.id}: {exc}\n{traceback.format_exc()}")
                    self.job_statuses[job.id] = "FAILED"
                    self.downloaded_jobs.add(job.id)

    @Slot(str, str)
    def _update_job_status(self, job_id, status):
        """Thread-safe method to update job status."""
        self.job_statuses[job_id] = status

    @Slot()
    def request_progress_report(self):
        """Handles the request for a progress report."""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        self.progress.emit(f"--- Progress report requested by user at {timestamp} ---")
        if not self.input_files:
            self.progress.emit("No input files found yet. The process may still be initializing.")
            return
        report = get_progress_report(self.input_files, self.job_statuses, self.file_to_job_id)
        self.progress.emit(report)

    @Slot()
    def stop(self):
        """Requests the worker to stop."""
        self.progress.emit("--- Stop requested by user ---")
        self.stop_requested = True
        if self.timer.isActive():
            self.timer.stop()
        self.download_executor.shutdown(wait=False)
        self.finished.emit()


def clear_log_directory(base_dir: str):
    """Deletes all files in the osparc_submission_logs directory."""
    log_dir = Path(base_dir) / "logs" / "osparc_submission_logs"
    if log_dir.exists():
        print(f"--- Clearing log directory: {log_dir} ---")
        for item in log_dir.iterdir():
            if item.is_file():
                try:
                    item.unlink()
                except OSError as e:
                    print(f"Error deleting file {item}: {e}")
            elif item.is_dir():
                try:
                    shutil.rmtree(item)
                except OSError as e:
                    print(f"Error deleting directory {item}: {e}")

def main(config_path: str):
    """Main entry point: sets up and starts the GUI and the main logic process."""
    import sys
    from PySide6.QtWidgets import QApplication

    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    clear_log_directory(base_dir)

    app = QApplication.instance() or QApplication(sys.argv)
    
    thread = QThread()
    worker = Worker(config_path)
    worker.moveToThread(thread)
    
    gui = BatchGUI()
    
    # Connect signals and slots
    thread.started.connect(worker.run)
    worker.finished.connect(thread.quit)
    worker.finished.connect(worker.deleteLater)
    thread.finished.connect(thread.deleteLater)
    
    worker.progress.connect(print)
    gui.print_progress_requested.connect(worker.request_progress_report)
    gui.stop_run_requested.connect(worker.stop)
    
    worker.finished.connect(app.quit)
    
    thread.start()
    gui.show()
    app.exec()

    if thread.isRunning():
        thread.quit()
        thread.wait()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run a batch of simulations on oSPARC with a progress GUI.")
    parser.add_argument(
        '--config',
        type=str,
        required=False,
        default="configs/todays_far_field_config.json",
        help="Path to the configuration file (defaults to 'configs/todays_far_field_config.json')."
    )
    args = parser.parse_args()
    main(args.config)