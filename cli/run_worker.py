"""CLI module for running as a worker on a super study assignment."""

import argparse
import json
import logging
import os
import socket
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

        logger.info(f"{colorama.Fore.GREEN}✓ Found super study: {super_study['name']}")
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

        logger.info(f"{colorama.Fore.GREEN}✓ Assignment claimed successfully!")

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


def run_assignment(assignment, super_study_name, assignment_index, title, no_cache, logger):
    """Run the study with the assignment config."""
    # Create config file in configs directory (not temp)
    config_data = assignment.get("splitConfig", {})

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
    with open(config_path, "w") as f:
        json.dump(config_data, f, indent=2)

    logger.info(f"\n{colorama.Fore.CYAN}Running assignment {assignment_index}...")
    logger.info(f"  Config saved to: {config_path}")
    logger.info("  Starting study...\n")

    # Set environment variables for web integration
    os.environ["GOLIAT_ASSIGNMENT_ID"] = assignment.get("id", "")

    # Run the study using goliat study command
    from cli.run_study import main as study_main

    # Reconstruct sys.argv for the study module
    original_argv = sys.argv[:]
    sys.argv = ["goliat-study", config_path]
    if title:
        sys.argv.extend(["--title", title])
    if no_cache:
        sys.argv.append("--no-cache")

    try:
        study_main()
        logger.info(f"\n{colorama.Fore.CYAN}Study process finished for assignment {assignment_index}.")
        logger.info(f"{colorama.Fore.YELLOW}Note: Check the web dashboard to verify completion status.")
        return True
    except Exception as e:
        logger.error(f"\n{colorama.Fore.RED}✗ Assignment {assignment_index} failed: {e}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        sys.argv = original_argv


def main():
    """Main function to run as a worker."""
    logger = setup_console_logging()
    parser = argparse.ArgumentParser(description="Run as a worker on a super study assignment.")
    parser.add_argument(
        "assignment_index",
        type=int,
        help="Assignment index to run (0-based).",
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
        "--server-url",
        type=str,
        default=None,
        help="URL of the monitoring server (default: https://goliat.waves-ugent.be).",
    )

    args = parser.parse_args()

    # Get server URL: command arg > env var > hardcoded default
    server_url = args.server_url or os.getenv("GOLIAT_MONITORING_URL") or "https://goliat.waves-ugent.be"
    server_url = server_url.rstrip("/")
    machine_id = get_machine_id()

    logger.info(f"{colorama.Fore.CYAN}GOLIAT Worker")
    logger.info(f"  Machine ID: {machine_id}")
    logger.info(f"  Super Study: {args.super_study_name}")
    logger.info(f"  Assignment: {args.assignment_index}")
    logger.info(f"  Server: {server_url}\n")

    # Fetch and claim assignment
    assignment, super_study_id = fetch_assignment(args.super_study_name, args.assignment_index, server_url, machine_id, logger)

    # Run the assignment
    title = args.title or f"[Worker {args.assignment_index}] {args.super_study_name}"
    success = run_assignment(assignment, args.super_study_name, args.assignment_index, title, args.no_cache, logger)

    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
