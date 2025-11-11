import argparse
import logging
import os
import sys
import time
from typing import Optional

import colorama

from goliat.colors import init_colorama


# --- 1. Set up Logging ---
def setup_console_logging():
    """Sets up a basic console logger with color."""
    init_colorama()
    logger = logging.getLogger("osparc_batch")
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    return logger


main_logger = setup_console_logging()


def get_osparc_client_config(config, osparc_module):
    """Initializes and returns the oSPARC client configuration."""
    creds = config.get_osparc_credentials()
    if not all(k in creds for k in ["api_key", "api_secret", "api_server"]):
        raise ValueError("Missing oSPARC credentials in configuration.")

    return osparc_module.Configuration(
        host=creds["api_server"],
        username=creds["api_key"],
        password=creds["api_secret"],
    )


def cancel_all_jobs(config_path: str, max_jobs: int, base_dir: Optional[str] = None):
    """Cancels all running jobs on the oSPARC platform.

    Args:
        config_path: Path to the configuration file.
        max_jobs: Maximum number of jobs to check.
        base_dir: Base directory (defaults to current working directory).
    """
    import osparc as osparc_module

    from goliat.config import Config

    if base_dir is None:
        base_dir = os.getcwd()

    config = Config(base_dir, config_path)

    client_cfg = get_osparc_client_config(config, osparc_module)

    solver_key = "simcore/services/comp/isolve-gpu"
    solver_version = "2.2.212"

    with osparc_module.ApiClient(client_cfg) as api_client:
        solvers_api = osparc_module.SolversApi(api_client)

        main_logger.info(f"{colorama.Fore.MAGENTA}--- Fetching recent jobs (up to {max_jobs}) ---")
        all_jobs = []
        try:
            limit = 50
            offset = 0
            page_num = 0
            while True:
                main_logger.info(f"Fetching page {page_num} (offset: {offset}, limit: {limit})...")
                page = solvers_api.get_jobs_page(solver_key, solver_version, limit=limit, offset=offset)
                if page.items:
                    main_logger.info(f"Found {len(page.items)} jobs on this page.")
                    all_jobs.extend(page.items)
                    if len(all_jobs) >= max_jobs:
                        main_logger.warning(f"Reached job limit of {max_jobs}. Not fetching any more jobs.")
                        break
                    offset += limit
                    page_num += 1
                    time.sleep(0.5)
                else:
                    main_logger.info("No more jobs found on subsequent pages.")
                    break
        except Exception as e:
            main_logger.error(f"{colorama.Fore.RED}An error occurred while fetching jobs: {e}{colorama.Style.RESET_ALL}")

        if not all_jobs:
            main_logger.info("No jobs found to cancel.")
            return

        main_logger.info(f"\n--- Found a total of {len(all_jobs)} jobs. Now checking status and cancelling active ones ---")

        cancelled_jobs_count = 0
        for job in all_jobs:
            try:
                status = solvers_api.inspect_job(solver_key, solver_version, job.id)
                if status.state in [
                    "PENDING",
                    "PUBLISHED",
                    "WAITING_FOR_CLUSTER",
                    "WAITING_FOR_RESOURCES",
                    "STARTED",
                    "RETRYING",
                ]:
                    main_logger.info(f"Cancelling job {job.id} with status {status.state}...")
                    solvers_api.stop_job(solver_key, solver_version, job.id)
                    main_logger.info(f"{colorama.Fore.GREEN}Successfully sent cancel signal to job {job.id}.{colorama.Style.RESET_ALL}")
                    cancelled_jobs_count += 1
                else:
                    pass
            except Exception as e:
                main_logger.error(f"{colorama.Fore.RED}Failed to inspect or cancel job {job.id}: {e}{colorama.Style.RESET_ALL}")

        main_logger.info("\n--- Summary ---")
        main_logger.info(f"Successfully sent cancellation signals to {cancelled_jobs_count} jobs.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cancel all running oSPARC jobs.")
    parser.add_argument(
        "--config",
        type=str,
        required=False,
        default="configs/base_config.json",
        help="Path to the configuration file (defaults to 'configs/base_config.json').",
    )
    parser.add_argument(
        "--max-jobs",
        type=int,
        default=500,
        help="The maximum number of recent jobs to check (default: 500).",
    )
    args = parser.parse_args()

    # Base directory defaults to current working directory
    base_dir = os.getcwd()
    # Check if we're in a repo structure
    if not os.path.isdir(os.path.join(base_dir, "configs")):
        # Try going up one level (if run from scripts/ directory)
        parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        if os.path.isdir(os.path.join(parent_dir, "configs")):
            base_dir = parent_dir

    cancel_all_jobs(args.config, args.max_jobs, base_dir=base_dir)
    sys.exit(0)
