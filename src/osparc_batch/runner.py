import os
import sys
import logging
import time
import zipfile
import argparse
import shutil
import statistics
import traceback
import re
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from collections import defaultdict
from PySide6.QtCore import QThread
import colorama
from src.osparc_batch.gui import BatchGUI
from src.osparc_batch.worker import Worker

# --- 1. Set up Logging ---
def setup_console_logging():
    """Sets up a basic console logger with color."""
    colorama.init(autoreset=True)
    logger = logging.getLogger('osparc_batch')
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(message)s'))
    logger.addHandler(handler)
    return logger

main_logger = setup_console_logging()
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

STATUS_COLORS = {
    "PENDING": colorama.Fore.YELLOW,
    "PUBLISHED": colorama.Fore.LIGHTYELLOW_EX,
    "WAITING_FOR_CLUSTER": colorama.Fore.MAGENTA,
    "WAITING_FOR_RESOURCES": colorama.Fore.LIGHTMAGENTA_EX,
    "STARTED": colorama.Fore.CYAN,
    "SUCCESS": colorama.Fore.GREEN,
    "FAILED": colorama.Fore.RED,
    "RETRYING": colorama.Fore.LIGHTRED_EX,
    "DOWNLOADING": colorama.Fore.BLUE,
    "FINISHED": colorama.Fore.GREEN,
    "COMPLETED": colorama.Fore.GREEN,
    "UNKNOWN": colorama.Fore.WHITE,
}

# --- 2. Core Functions ---
def find_input_files(config) -> list[Path]:
    """
    Finds solver input files (.h5), identifies the latest group based on creation time and configuration,
    and cleans up older, unselected files.
    """
    main_logger.info(f"{colorama.Fore.MAGENTA}--- Searching for input files based on configuration ---")
    results_base_dir = Path(config.base_dir) / "results"
    study_type = config.get_setting('study_type')
    phantoms = config.get_setting('phantoms', [])
    frequencies = config.get_setting('frequencies_mhz', [])

    if not all([study_type, phantoms, frequencies]):
        raise ValueError("Config must specify 'study_type', 'phantoms', and 'frequencies_mhz'.")

    all_input_files = []
    for phantom in phantoms:
        for freq in frequencies:
            if study_type == 'far_field':
                project_dir = results_base_dir / study_type / phantom.lower() / f"{freq}MHz"
                project_filename_base = f"far_field_{phantom.lower()}_{freq}MHz"
                results_folder = project_dir / f"{project_filename_base}.smash_Results"

                if not results_folder.exists():
                    main_logger.warning(f"{colorama.Fore.YELLOW}WARNING: Results directory does not exist: {results_folder}")
                    continue

                found_files = list(results_folder.glob('*_Input.h5'))
                if not found_files:
                    main_logger.warning(f"{colorama.Fore.YELLOW}WARNING: No input files found in: {results_folder}")
                    continue
                
                main_logger.info(f"{colorama.Fore.CYAN}Found {len(found_files)} raw input file(s) in: {results_folder}")

                # --- Grouping Logic ---
                far_field_setup = config.get_setting('far_field_setup', {}).get('environmental', {})
                if not far_field_setup:
                    main_logger.warning(f"{colorama.Fore.YELLOW}WARNING: No 'environmental' far-field setup in config. Using all found files.")
                    all_input_files.extend(found_files)
                    continue

                inc_dirs = far_field_setup.get('incident_directions', [])
                pols = far_field_setup.get('polarizations', [])
                expected_count = len(inc_dirs) * len(pols)
                main_logger.info(f"Expected file count per batch: {expected_count} ({len(inc_dirs)} dirs x {len(pols)} pols)")

                if len(found_files) < expected_count:
                    main_logger.warning(f"{colorama.Fore.YELLOW}WARNING: Not enough files for a full batch ({len(found_files)}/{expected_count}). Using all available.")
                    all_input_files.extend(found_files)
                    continue
                
                files_with_mtime = sorted([(f, f.stat().st_mtime) for f in found_files], key=lambda x: x[1], reverse=True)
                
                main_logger.info("Analyzing file timestamps to find the latest batch...")
                latest_files = files_with_mtime[:expected_count]
                oldest_in_group_time = latest_files[-1]
                
                # Simple approach: take the N youngest files. A more complex periodicity analysis could be added here if needed.
                selected_files = [f for f, _ in latest_files]
                main_logger.info(f"{colorama.Fore.GREEN}Selected the latest {len(selected_files)} files based on modification time.")

                # --- Time Gap Analysis ---
                if len(latest_files) > 1:
                    time_diffs = [latest_files[i][1] - latest_files[i+1][1] for i in range(len(latest_files)-1)]
                    time_diffs_str = ", ".join([f"{diff:.2f}s" for diff in time_diffs])
                    main_logger.info(f"{colorama.Fore.YELLOW}Time gaps between files: [{time_diffs_str}].")

                    if len(time_diffs) > 3:
                        max_diff = max(time_diffs)
                        other_diffs = [d for d in time_diffs if d != max_diff]
                        
                        if len(other_diffs) > 1:
                            mean_diff = statistics.mean(other_diffs)
                            
                            if max_diff > 2 * mean_diff:
                                main_logger.warning(f"{colorama.Back.RED}{colorama.Fore.WHITE}CRITICAL WARNING: Potential old input file detected!{colorama.Style.RESET_ALL}")
                                main_logger.warning(f"The largest time gap ({max_diff:.2f}s) is significantly larger than expected (mean: {mean_diff:.2f}s, std: {std_dev:.2f}s).")
                                main_logger.warning("Please verify the input files are from the correct batch.")
                                
                                response = input("Do you want to continue anyway? (y/n): ").lower()
                                if response != 'y':
                                    main_logger.error("Aborting due to user request.")
                                    sys.exit(1)

                # --- Cleanup Logic ---
                unselected_files = [f for f, _ in files_with_mtime[expected_count:]]
                if unselected_files:
                    main_logger.info(f"{colorama.Fore.YELLOW}--- Deleting {len(unselected_files)} older input files ---")
                    for f in unselected_files:
                        try:
                            f.unlink()
                            main_logger.info(f"Deleted: {f.name}")
                        except OSError as e:
                            main_logger.error(f"Error deleting file {f}: {e}")
                
                all_input_files.extend(selected_files)

    if not all_input_files:
        main_logger.error(f"{colorama.Fore.RED}ERROR: Could not find any input files to process.")
        sys.exit(1)
    
    main_logger.info(f"{colorama.Fore.GREEN}--- Found a total of {len(all_input_files)} input files to process. ---")
    return all_input_files


def get_osparc_client_config(config, osparc_module):
    """Initializes and returns the oSPARC client configuration."""
    creds = config.get_osparc_credentials()
    if not all(k in creds for k in ['api_key', 'api_secret', 'api_server']):
        raise ValueError("Missing oSPARC credentials in configuration.")
    
    temp_dir = Path(config.base_dir) / "tmp_download"
    temp_dir.mkdir(exist_ok=True)

    client_config = osparc_module.Configuration(
        host=creds['api_server'],
        username=creds['api_key'],
        password=creds['api_secret'],
    )
    client_config.temp_folder_path = str(temp_dir)
    return client_config


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
    try:
        return submit_job(input_file_path, client_cfg, solver_key, solver_version, osparc_module)
    except ValueError as e:
        if "Invalid value for `items`, must not be `None`" in str(e):
            main_logger.error(f"Error submitting job for {input_file_path.name}: oSPARC API returned invalid data. Skipping.")
            return None
        raise e


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
                
                if result_file.filename.endswith('.zip'):
                    job_logger.info(f"Extracting {result_file.filename} to {output_dir}")
                    with zipfile.ZipFile(download_path, 'r') as zip_ref:
                        zip_ref.extractall(output_dir)
                        
                        # --- Enhanced Log File Handling ---
                        uuid = input_file_path.stem.replace('_Input', '')
                        extracted_files = zip_ref.namelist()
                        
                        for filename in extracted_files:
                            if filename.endswith('.log'):
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
                        output_filename = input_file_path.stem.replace('_Input', '_Output') + ".h5"
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


def get_progress_report(input_files, job_statuses, file_to_job_id) -> str:
    """Generates a status summary and a colored file tree string."""
    report_lines = []
    
    status_counts = defaultdict(int)
    for status_tuple in job_statuses.values():
        status_str = status_tuple[0] if isinstance(status_tuple, tuple) else status_tuple
        state = status_str.split(" ")[0]
        status_counts[state] += 1
    summary = " | ".join(f"{state}: {count}" for state, count in sorted(status_counts.items()))
    report_lines.append(f"\n{colorama.Fore.BLUE}--- Progress Summary ---\n{summary}\n{colorama.Style.RESET_ALL}")

    tree = {}
    if not input_files:
        return "\n".join(report_lines)

    # --- Optimized Path Handling ---
    try:
        first_path_parts = input_files[0].parts
        results_index = first_path_parts.index('results')
        base_path = Path(*first_path_parts[:results_index+1])
    except (ValueError, IndexError):
        # Fallback for safety, though not expected with the current structure
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
                current_level = current_level.setdefault(part, {})
            
            filename = parts[-1]
            current_level[filename] = file_to_job_id.get(file_path)

        except (IndexError, ValueError) as e:
            report_lines.append(f"{colorama.Fore.RED}Could not process path {file_path}: {e}{colorama.Style.RESET_ALL}")

    def build_tree_recursive(node, prefix=""):
        def sort_key(item):
            match = re.match(r'(\d+)', item)
            if match:
                return (1, int(match.group(1)))
            return (0, item)

        items = sorted(node.keys(), key=sort_key)
        for i, item in enumerate(items):
            is_last = i == len(items) - 1
            connector = "└── " if is_last else "├── "
            
            if isinstance(node[item], dict):
                report_lines.append(f"{prefix}{connector}{colorama.Fore.WHITE}{item}")
                new_prefix = prefix + ("    " if is_last else "│   ")
                build_tree_recursive(node[item], new_prefix)
            else:
                job_id = node[item]
                status_tuple = job_statuses.get(job_id, ("UNKNOWN", time.time()))
                status_str, start_time = status_tuple if isinstance(status_tuple, tuple) else (status_tuple, time.time())
                
                elapsed_time = time.time() - start_time
                timer_str = f" ({elapsed_time:.0f}s)"
                
                status = status_str.split(" ")[0]
                color = STATUS_COLORS.get(status, colorama.Fore.WHITE)
                colored_text = f"{color}{item} (oSPARC Job: {job_id}, Status: {status_str}{timer_str}){colorama.Style.RESET_ALL}"
                report_lines.append(f"{prefix}{connector}{colored_text}")

    report_lines.append(f"{colorama.Fore.BLUE}--- File Status Tree ---{colorama.Style.RESET_ALL}")
    build_tree_recursive(tree)
    report_lines.append(f"{colorama.Fore.BLUE}------------------------{colorama.Style.RESET_ALL}\n")
    
    return "\n".join(report_lines)


# --- 3. Main Process Logic ---
def main_process_logic(worker: 'Worker'):
    """The main logic of the batch run, now running in a QThread."""
    import osparc as osparc_module

    try:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
        worker.client_cfg = get_osparc_client_config(worker.config, osparc_module)
        
        solver_key = "simcore/services/comp/isolve-gpu"
        solver_version = "2.2.212"

        main_logger.info(f"{colorama.Fore.MAGENTA}--- Submitting Jobs to oSPARC in Parallel ---")
        worker.running_jobs = {}
        with ProcessPoolExecutor(max_workers=min(len(worker.input_files), 61) or 1) as executor:
            future_to_file = {
                executor.submit(_submit_job_in_process, fp, worker.client_cfg, solver_key, solver_version): fp
                for fp in worker.input_files
            }
            for future in as_completed(future_to_file):
                file_path = future_to_file[future]
                try:
                    result = future.result()
                    if result:
                        job, solver = result
                        worker.running_jobs[file_path] = (job, solver)
                        setup_job_logging(base_dir, job.id)
                        job_logger = logging.getLogger(f'job_{job.id}')
                        job_logger.info(f"Job {job.id} submitted for input file {file_path.name} at path {file_path}.")
                except Exception as exc:
                    main_logger.error(f'ERROR: Submitting job for {file_path.name} generated an exception: {exc}\n{traceback.format_exc()}')

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

# --- 4. Main Entry Point ---


def clear_log_directory(base_dir: str):
    """Deletes all files in the osparc_submission_logs directory."""
    log_dir = Path(base_dir) / "logs" / "osparc_submission_logs"
    if log_dir.exists():
        main_logger.info(f"--- Clearing log directory: {log_dir} ---")
        for item in log_dir.iterdir():
            if item.is_file():
                try:
                    item.unlink()
                except OSError as e:
                    main_logger.error(f"Error deleting file {item}: {e}")
            elif item.is_dir():
                try:
                    shutil.rmtree(item)
                except OSError as e:
                    main_logger.error(f"Error deleting directory {item}: {e}")

def clear_temp_download_directory(base_dir: str):
    """Deletes the temporary download directory."""
    temp_dir = Path(base_dir) / "tmp_download"
    if temp_dir.exists():
        main_logger.info(f"--- Clearing temporary download directory: {temp_dir} ---")
        try:
            shutil.rmtree(temp_dir)
        except OSError as e:
            main_logger.error(f"Error deleting directory {temp_dir}: {e}")

def main(config_path: str):
    """Main entry point: sets up and starts the GUI and the main logic process."""
    import sys
    from PySide6.QtWidgets import QApplication
    from src.config import Config

    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
    clear_log_directory(base_dir)

    config = Config(base_dir, config_path)
    input_files = find_input_files(config)

    app = QApplication.instance() or QApplication(sys.argv)
    
    thread = QThread()
    worker = Worker(
        config_path=config_path,
        logger=main_logger,
        get_osparc_client_config_func=get_osparc_client_config,
        download_and_process_results_func=download_and_process_results,
        get_progress_report_func=get_progress_report,
        main_process_logic_func=main_process_logic,
    )
    worker.config = config
    worker.input_files = input_files
    worker.moveToThread(thread)
    
    gui = BatchGUI()
    
    # Connect signals and slots
    thread.started.connect(worker.run)
    worker.finished.connect(thread.quit)
    worker.finished.connect(worker.deleteLater)
    thread.finished.connect(thread.deleteLater)
    
    worker.progress.connect(main_logger.info)
    gui.print_progress_requested.connect(worker.request_progress_report)
    gui.stop_run_requested.connect(worker.stop)
    gui.cancel_jobs_requested.connect(worker.cancel_jobs)
    
    worker.finished.connect(app.quit)
    
    thread.start()
    gui.show()
    app.exec()

    if thread.isRunning():
        thread.quit()
        thread.wait()

    clear_temp_download_directory(base_dir)

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