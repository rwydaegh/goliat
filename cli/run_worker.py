"""CLI module for running as a worker on a super study assignment."""

import argparse
import json
import logging
import os
import socket
import subprocess
import sys

import colorama

from goliat.colors import init_colorama

try:
    import requests

    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

# Base directory for config files
from cli.utils import get_base_dir

base_dir = get_base_dir()


def setup_console_logging():
    """Sets up a basic console logger with color."""
    init_colorama()
    logger = logging.getLogger("worker_logger")
    logger.setLevel(logging.INFO)
    logger.propagate = False  # Prevent propagation to root logger
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    if logger.hasHandlers():
        logger.handlers.clear()
    logger.addHandler(handler)
    return logger


def parse_assignment_indices(assignment_str: str) -> list[int]:
    """Parse assignment string into list of indices.

    Supports:
    - Single number: "5" -> [5]
    - Comma-separated: "1,2,3" -> [1, 2, 3]
    - Ranges: "1-5" -> [1, 2, 3, 4, 5]
    - Mixed: "0,1,3-5,8" -> [0, 1, 3, 4, 5, 8]

    Args:
        assignment_str: String representing assignment indices.

    Returns:
        Sorted list of unique assignment indices.

    Raises:
        ValueError: If the format is invalid.
    """
    indices = set()
    parts = assignment_str.split(",")

    for part in parts:
        part = part.strip()
        if not part:
            continue

        if "-" in part:
            # Range syntax: "1-5"
            range_parts = part.split("-")
            if len(range_parts) != 2:
                raise ValueError(f"Invalid range format: '{part}'. Use 'start-end' format.")
            try:
                start = int(range_parts[0].strip())
                end = int(range_parts[1].strip())
            except ValueError:
                raise ValueError(f"Invalid range values in '{part}'. Must be integers.")

            if start > end:
                raise ValueError(f"Invalid range '{part}': start ({start}) > end ({end}).")

            indices.update(range(start, end + 1))
        else:
            # Single number
            try:
                indices.add(int(part))
            except ValueError:
                raise ValueError(f"Invalid assignment index: '{part}'. Must be an integer.")

    return sorted(indices)


def get_machine_id():
    """Get a unique machine identifier (IP address).

    Tries public IP first (via api.ipify.org) with retries, then falls back to local IP.
    This matches the logic in progress_gui.py to ensure consistency.
    """
    if not REQUESTS_AVAILABLE:
        # If requests not available, skip public IP and go straight to local
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return socket.gethostname()

    # Try external service first with retries (matches progress_gui.py)
    import requests

    for attempt in range(3):  # Try up to 3 times
        try:
            response = requests.get("https://api.ipify.org", timeout=10)
            if response.status_code == 200:
                public_ip = response.text.strip()
                if public_ip:
                    return public_ip
        except Exception:
            if attempt == 2:  # Last attempt failed
                pass  # Will fall through to local IP
            continue

    # Fallback to local IP
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        # Final fallback to hostname
        return socket.gethostname()


def fetch_assignment(super_study_name, assignment_index, server_url, machine_id, logger):
    """Fetch an assignment from the super study."""
    if not REQUESTS_AVAILABLE:
        logger.error(f"{colorama.Fore.RED}Error: requests library is required. Install with: pip install requests")
        sys.exit(1)

    try:
        # Get super study by name
        logger.info(f"Fetching super study '{super_study_name}' from {server_url}...")
        response = requests.get(f"{server_url}/api/super-studies", params={"name": super_study_name}, timeout=10)

        if response.status_code != 200:
            logger.error(f"{colorama.Fore.RED}Error: Could not fetch super study. Status: {response.status_code}")
            logger.error(f"Response: {response.text[:500]}")
            sys.exit(1)

        studies = response.json()
        if not studies:
            logger.error(f"{colorama.Fore.RED}Error: Super study '{super_study_name}' not found")
            sys.exit(1)

        super_study = studies[0]  # Take first match
        super_study_id = super_study["id"]

        logger.info(f"{colorama.Fore.GREEN}Found super study: {super_study['name']}")
        logger.info(f"  Total assignments: {super_study['totalAssignments']}")
        logger.info(f"  Completed: {super_study['completedAssignments']}")

        # Get assignments
        response = requests.get(f"{server_url}/api/super-studies/{super_study_id}/assignments", timeout=10)

        if response.status_code != 200:
            logger.error(f"{colorama.Fore.RED}Error: Could not fetch assignments. Status: {response.status_code}")
            sys.exit(1)

        assignments = response.json()

        # Sort assignments by index to ensure correct order
        assignments.sort(key=lambda a: a.get("index", 0))

        # Find the requested assignment by index field
        assignment = None
        for a in assignments:
            if a.get("index") == assignment_index:
                assignment = a
                break

        if not assignment:
            logger.error(f"{colorama.Fore.RED}Error: Assignment with index {assignment_index} not found")
            logger.error(f"Available indices: {[a.get('index', '?') for a in assignments]}")
            sys.exit(1)

        assignment_id = assignment["id"]

        logger.info(f"\n{colorama.Fore.CYAN}Assignment {assignment_index}:")
        logger.info(f"  Status: {assignment['status']}")
        logger.info(f"  ID: {assignment_id}")

        # Claim the assignment
        logger.info(f"\nClaiming assignment for machine {machine_id}...")
        response = requests.post(f"{server_url}/api/assignments/{assignment_id}/claim", json={"machineId": machine_id}, timeout=10)

        if response.status_code != 200:
            logger.error(f"{colorama.Fore.RED}Error: Could not claim assignment. Status: {response.status_code}")
            logger.error(f"Response: {response.text[:500]}")
            sys.exit(1)

        logger.info(f"{colorama.Fore.GREEN}Assignment claimed successfully!")

        return assignment, super_study_id

    except requests.exceptions.ConnectionError:
        logger.error(f"{colorama.Fore.RED}Error: Could not connect to {server_url}")
        logger.error("Make sure the server is running and accessible.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"{colorama.Fore.RED}Error fetching assignment: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


def run_assignment(assignment, super_study_name, assignment_index, title, no_cache, reupload_results, auto_close, logger):
    """Run the study with the assignment config.

    Args:
        assignment: Assignment data from the server.
        super_study_name: Name of the super study.
        assignment_index: Assignment index.
        title: GUI window title.
        no_cache: Whether to disable caching.
        reupload_results: Whether to reupload cached results.
        auto_close: Whether to auto-close GUI on success.
        logger: Logger instance.

    Returns:
        True if successful, False otherwise.
    """
    # Create config file in configs directory (not temp)
    config_data = assignment.get("splitConfig", {})

    # Check use_web setting early - worker NEEDS web to function
    use_web = config_data.get("use_web")
    if use_web is None:
        use_web = True  # Default to True if not specified

    if not use_web:
        logger.error(f"{colorama.Fore.RED}Error: use_web must be True for goliat worker command.")
        logger.error("Worker mode requires web connectivity to fetch assignments and upload results.")
        logger.error("Set 'use_web': true in your config file.")
        sys.exit(1)

    # Use configs directory instead of temp
    configs_dir = os.path.join(base_dir, "configs")
    os.makedirs(configs_dir, exist_ok=True)
    config_path = os.path.join(configs_dir, f"{super_study_name}_assignment_{assignment_index}.json")

    # Check if config has "extends" and copy base config if needed
    base_config_name = config_data.get("extends")
    if base_config_name:
        # Try to find base config in configs directory
        base_config_path = os.path.join(configs_dir, base_config_name)
        if os.path.exists(base_config_path):
            # Already exists, no need to copy
            logger.info(f"  Using existing base config: {base_config_name}")
        else:
            logger.warning(f"  Base config not found: {base_config_name}")

    # Write the assignment config
    # Note: json.dump preserves key order by default (Python 3.7+), ensuring the original
    # JSON structure from the server is maintained when saved to file.
    with open(config_path, "w") as f:
        json.dump(config_data, f, indent=2)

    logger.info(f"\n{colorama.Fore.CYAN}Running assignment {assignment_index}...")
    logger.info(f"  Config saved to: {config_path}")
    logger.info("  Starting study...\n")

    # Set environment variables for web integration
    os.environ["GOLIAT_ASSIGNMENT_ID"] = assignment.get("id", "")
    if reupload_results:
        os.environ["GOLIAT_REUPLOAD_RESULTS"] = "1"

    # Run the study using goliat study command
    from cli.run_study import main as study_main

    # Reconstruct sys.argv for the study module
    original_argv = sys.argv[:]
    sys.argv = ["goliat-study", config_path]
    if title:
        sys.argv.extend(["--title", title])
    if no_cache:
        sys.argv.append("--no-cache")
    if auto_close:
        sys.argv.append("--auto-close")

    try:
        study_main()
        logger.info(f"\n{colorama.Fore.CYAN}Study process finished for assignment {assignment_index}.")
        logger.info(f"{colorama.Fore.YELLOW}Note: Check the web dashboard to verify completion status.")
        return True
    except Exception as e:
        logger.error(f"\n{colorama.Fore.RED}Assignment {assignment_index} FAILED: {e}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        sys.argv = original_argv


def run_single_worker(
    assignment_index: int,
    super_study_name: str,
    server_url: str,
    machine_id: str,
    title: str,
    no_cache: bool,
    reupload_results: bool,
    auto_close: bool,
    logger,
) -> bool:
    """Run a single worker assignment in-process.

    Args:
        assignment_index: Assignment index to run.
        super_study_name: Name of the super study.
        server_url: URL of the monitoring server.
        machine_id: Machine identifier.
        title: GUI window title.
        no_cache: Whether to disable caching.
        reupload_results: Whether to reupload cached results.
        auto_close: Whether to auto-close GUI on success.
        logger: Logger instance.

    Returns:
        True if successful, False otherwise.
    """
    logger.info(f"{colorama.Fore.CYAN}GOLIAT Worker")
    logger.info(f"  Machine ID: {machine_id}")
    logger.info(f"  Super Study: {super_study_name}")
    logger.info(f"  Assignment: {assignment_index}")
    logger.info(f"  Server: {server_url}\n")

    # Fetch and claim assignment
    assignment, super_study_id = fetch_assignment(super_study_name, assignment_index, server_url, machine_id, logger)

    # Run the assignment
    effective_title = title or f"[Worker {assignment_index}] {super_study_name}"
    success = run_assignment(
        assignment, super_study_name, assignment_index, effective_title, no_cache, reupload_results, auto_close, logger
    )

    return success


def run_worker_subprocess(
    assignment_index: int, super_study_name: str, server_url: str, title: str, no_cache: bool, reupload_results: bool, logger
) -> int:
    """Run a worker assignment as a subprocess.

    This allows memory to be fully reclaimed between assignments, which is crucial
    for handling memory errors (exit code 42) with retry logic.

    Args:
        assignment_index: Assignment index to run.
        super_study_name: Name of the super study.
        server_url: URL of the monitoring server.
        title: GUI window title.
        no_cache: Whether to disable caching.
        reupload_results: Whether to reupload cached results.
        logger: Logger instance.

    Returns:
        Exit code from the subprocess (0 = success, 42 = memory error, other = failure).
    """
    # Build command
    cmd = [
        sys.executable,
        "-m",
        "cli",
        "worker",
        str(assignment_index),
        super_study_name,
        "--server-url",
        server_url,
        "--auto-close",  # Always auto-close in batch mode
    ]
    if title:
        cmd.extend(["--title", title])
    if no_cache:
        cmd.append("--no-cache")
    if reupload_results:
        cmd.append("--reupload-results")

    logger.info(f"{colorama.Fore.CYAN}Starting subprocess for assignment {assignment_index}...")
    logger.info(f"  Command: {' '.join(cmd)}")

    # Run subprocess and wait for completion
    result = subprocess.run(cmd, cwd=base_dir)

    return result.returncode


def run_batch_workers(
    assignment_indices: list[int],
    super_study_name: str,
    server_url: str,
    title_prefix: str,
    no_cache: bool,
    reupload_results: bool,
    max_retries: int,
    logger,
) -> bool:
    """Run multiple worker assignments sequentially with retry logic.

    Each assignment runs as a subprocess to allow full memory reclamation.
    Memory errors (exit code 42) trigger a retry of the same assignment.

    Args:
        assignment_indices: List of assignment indices to run.
        super_study_name: Name of the super study.
        server_url: URL of the monitoring server.
        title_prefix: Prefix for GUI window titles.
        no_cache: Whether to disable caching.
        reupload_results: Whether to reupload cached results.
        max_retries: Maximum retries per assignment on memory error.
        logger: Logger instance.

    Returns:
        True if all assignments completed successfully, False otherwise.
    """
    total = len(assignment_indices)
    logger.info(f"{colorama.Fore.CYAN}{'=' * 60}")
    logger.info(f"{colorama.Fore.CYAN}GOLIAT Batch Worker Mode")
    logger.info(f"{colorama.Fore.CYAN}{'=' * 60}")
    logger.info(f"  Super Study: {super_study_name}")
    logger.info(f"  Assignments: {assignment_indices}")
    logger.info(f"  Total: {total}")
    logger.info(f"  Max retries per assignment: {max_retries}")
    logger.info(f"  Server: {server_url}")
    logger.info(f"{colorama.Fore.CYAN}{'=' * 60}\n")

    completed = []
    failed = []

    for i, assignment_index in enumerate(assignment_indices):
        logger.info(f"\n{colorama.Fore.CYAN}{'=' * 60}")
        logger.info(f"{colorama.Fore.CYAN}Assignment {assignment_index} ({i + 1}/{total})")
        logger.info(f"{colorama.Fore.CYAN}{'=' * 60}")

        title = (
            f"{title_prefix}[Worker {assignment_index}] ({i + 1}/{total})"
            if title_prefix
            else f"[Worker {assignment_index}] {super_study_name} ({i + 1}/{total})"
        )

        retry_count = 0
        success = False

        while retry_count <= max_retries:
            if retry_count > 0:
                logger.info(f"\n{colorama.Fore.YELLOW}Retry {retry_count}/{max_retries} for assignment {assignment_index}...")

            exit_code = run_worker_subprocess(assignment_index, super_study_name, server_url, title, no_cache, reupload_results, logger)

            if exit_code == 0:
                logger.info(f"{colorama.Fore.GREEN}✓ Assignment {assignment_index} completed successfully!")
                success = True
                break
            elif exit_code == 42:
                # Memory error - retry
                logger.warning(f"{colorama.Fore.YELLOW}Memory error (exit code 42) for assignment {assignment_index}.")
                retry_count += 1
                if retry_count <= max_retries:
                    logger.info(f"{colorama.Fore.YELLOW}Will retry (caching will resume from last checkpoint)...")
                else:
                    logger.error(f"{colorama.Fore.RED}Max retries ({max_retries}) exceeded for assignment {assignment_index}.")
            else:
                # Other error - don't retry
                logger.error(f"{colorama.Fore.RED}Assignment {assignment_index} failed with exit code {exit_code}.")
                break

        if success:
            completed.append(assignment_index)
        else:
            failed.append(assignment_index)

    # Summary
    logger.info(f"\n{colorama.Fore.CYAN}{'=' * 60}")
    logger.info(f"{colorama.Fore.CYAN}Batch Worker Summary")
    logger.info(f"{colorama.Fore.CYAN}{'=' * 60}")
    logger.info(f"  Completed: {len(completed)}/{total} - {completed}")
    if failed:
        logger.info(f"  {colorama.Fore.RED}Failed: {len(failed)}/{total} - {failed}")
    logger.info(f"{colorama.Fore.CYAN}{'=' * 60}\n")

    return len(failed) == 0


def main():
    """Main function to run as a worker.

    Supports both single assignment mode (backward compatible) and batch mode
    for running multiple assignments sequentially with retry logic.

    Examples:
        goliat worker 0 my_study          # Single assignment
        goliat worker 1,2,3 my_study      # Multiple comma-separated
        goliat worker 0-4 my_study        # Range
        goliat worker 0,2,4-7 my_study    # Mixed
    """
    logger = setup_console_logging()
    parser = argparse.ArgumentParser(
        description="Run as a worker on a super study assignment.",
        epilog="""
Examples:
  goliat worker 0 my_study          # Single assignment
  goliat worker 1,2,3 my_study      # Multiple comma-separated
  goliat worker 0-4 my_study        # Range (0,1,2,3,4)
  goliat worker 0,2,4-7 my_study    # Mixed (0,2,4,5,6,7)
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "assignment_indices",
        type=str,
        help="Assignment index(es) to run. Single: '5', Multiple: '1,2,3', Range: '1-5', Mixed: '0,2,4-7'.",
    )
    parser.add_argument(
        "super_study_name",
        type=str,
        help="Name of the super study to join.",
    )
    parser.add_argument(
        "--title",
        type=str,
        default="",
        help="Set the title of the GUI window.",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="If set, redo simulations even if the configuration matches a completed run.",
    )
    parser.add_argument(
        "--reupload-results",
        action="store_true",
        help="When caching skips simulations, upload extraction results that appear valid.",
    )
    parser.add_argument(
        "--server-url",
        type=str,
        default=None,
        help="URL of the monitoring server (default: https://monitor.goliat.waves-ugent.be).",
    )
    parser.add_argument(
        "--auto-close",
        action="store_true",
        help="Automatically close the GUI when assignment completes successfully.",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Maximum retries per assignment on memory error (default: 3).",
    )

    args = parser.parse_args()

    # Parse assignment indices
    try:
        assignment_indices = parse_assignment_indices(args.assignment_indices)
    except ValueError as e:
        logger.error(f"{colorama.Fore.RED}Error parsing assignment indices: {e}")
        sys.exit(1)

    if not assignment_indices:
        logger.error(f"{colorama.Fore.RED}No valid assignment indices provided.")
        sys.exit(1)

    # Get server URL: command arg > env var > hardcoded default
    server_url = args.server_url or os.getenv("GOLIAT_MONITORING_URL") or "https://monitor.goliat.waves-ugent.be"
    server_url = server_url.rstrip("/")
    machine_id = get_machine_id()

    # Decide mode: single (in-process) vs batch (subprocess)
    if len(assignment_indices) == 1:
        # Single assignment mode - run in-process for efficiency
        assignment_index = assignment_indices[0]
        success = run_single_worker(
            assignment_index,
            args.super_study_name,
            server_url,
            machine_id,
            args.title,
            args.no_cache,
            args.reupload_results,
            args.auto_close,
            logger,
        )
        if not success:
            sys.exit(1)
    else:
        # Batch mode - run each as subprocess with auto-close and retry logic
        success = run_batch_workers(
            assignment_indices,
            args.super_study_name,
            server_url,
            args.title,
            args.no_cache,
            args.reupload_results,
            args.max_retries,
            logger,
        )
        if not success:
            sys.exit(1)


if __name__ == "__main__":
    main()
