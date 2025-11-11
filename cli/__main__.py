"""Main CLI entry point for GOLIAT."""

import argparse
import os
import sys

# Only run initial_setup for commands that need it
# Commands like 'init', 'version', 'status' don't need full setup


def create_parser():
    """Create the main argument parser with subcommands."""
    parser = argparse.ArgumentParser(
        prog="goliat",
        description="GOLIAT - Automated EMF dosimetry simulations using Sim4Life",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    subparsers.required = True

    # study command
    study_parser = subparsers.add_parser("study", help="Run a dosimetric assessment study")
    study_parser.add_argument(
        "config",
        type=str,
        nargs="?",
        default="near_field_config",
        help="Path or name of the configuration file (e.g., todays_far_field or configs/near_field_config.json).",
    )
    study_parser.add_argument(
        "--title",
        type=str,
        default="",
        help="Set the title of the GUI window.",
    )
    study_parser.add_argument("--pid", type=str, default=None, help="The process ID for logging.")
    study_parser.add_argument(
        "--no-cache",
        action="store_true",
        help="If set, redo simulations even if the configuration matches a completed run.",
    )

    # analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Run analysis for near-field or far-field studies")
    analyze_parser.add_argument("--config", type=str, required=True, help="Path to the configuration file.")

    # parallel command
    parallel_parser = subparsers.add_parser("parallel", help="Split a config file and run studies in parallel")
    parallel_parser.add_argument(
        "config",
        type=str,
        nargs="?",
        default="configs/near_field_config.json",
        help="Path or name of the configuration file (e.g., todays_far_field or configs/near_field_config.json).",
    )
    parallel_parser.add_argument(
        "--num-splits",
        type=int,
        default=4,
        help="Number of configs to split into (any positive integer that can be factored "
        "given the phantoms and frequencies/antennas available).",
    )
    parallel_parser.add_argument(
        "--skip-split",
        action="store_true",
        help="Skip the splitting step and run studies from an existing parallel directory.",
    )
    parallel_parser.add_argument(
        "--no-cache",
        action="store_true",
        help="If set, redo simulations even if the configuration matches a completed run.",
    )

    # init command
    subparsers.add_parser("init", help="Initialize GOLIAT environment (install dependencies, check setup)")

    # status command
    subparsers.add_parser("status", help="Show GOLIAT setup status and environment information")

    # validate command
    validate_parser = subparsers.add_parser("validate", help="Validate a GOLIAT config file")
    validate_parser.add_argument("config", type=str, help="Path to the configuration file to validate")

    # version command
    subparsers.add_parser("version", help="Show GOLIAT version information")

    # free-space command
    subparsers.add_parser(
        "free-space",
        help="Run free-space simulations for antenna validation",
        aliases=["freespace"],
    )
    # No arguments needed for free-space

    # super_study command
    super_study_parser = subparsers.add_parser("super_study", help="Create a super study and upload it to the web dashboard")
    super_study_parser.add_argument(
        "config",
        type=str,
        help="Path to the configuration file (e.g., configs/near_field_config.json).",
    )
    super_study_parser.add_argument(
        "--name",
        type=str,
        required=True,
        help="Name for the super study (used by workers to join).",
    )
    super_study_parser.add_argument(
        "--description",
        type=str,
        default="",
        help="Optional description for the super study.",
    )
    super_study_parser.add_argument(
        "--num-splits",
        type=int,
        default=4,
        help="Number of assignments to split into (default: 4).",
    )
    super_study_parser.add_argument(
        "--server-url",
        type=str,
        default=None,
        help="URL of the monitoring server (default: https://goliat.waves-ugent.be).",
    )

    # worker command
    worker_parser = subparsers.add_parser("worker", help="Run as a worker on a super study assignment")
    worker_parser.add_argument(
        "assignment_index",
        type=int,
        help="Assignment index to run (0-based).",
    )
    worker_parser.add_argument(
        "super_study_name",
        type=str,
        help="Name of the super study to join.",
    )
    worker_parser.add_argument(
        "--title",
        type=str,
        default="",
        help="Set the title of the GUI window.",
    )
    worker_parser.add_argument(
        "--no-cache",
        action="store_true",
        help="If set, redo simulations even if the configuration matches a completed run.",
    )
    worker_parser.add_argument(
        "--server-url",
        type=str,
        default=None,
        help="URL of the monitoring server (default: https://goliat.waves-ugent.be).",
    )

    return parser


def _print_ascii_art():
    """Print GOLIAT ASCII art banner."""
    from cli.ascii_art import GOLIAT_BANNER

    print(GOLIAT_BANNER)


def main():
    """Main entry point for GOLIAT CLI."""
    _print_ascii_art()

    parser = create_parser()
    args = parser.parse_args()

    # Commands that don't need full setup
    if args.command == "init":
        # Run initial setup (install dependencies, check Python, prepare data)
        from goliat.utils.setup import initial_setup

        initial_setup()
        print("\n✓ GOLIAT initialization complete!")
        print("  You can now run 'goliat study <config>' to start a simulation.")
        return

    elif args.command == "version":
        from cli.commands import show_version

        show_version()
        return

    elif args.command == "status":
        from cli.commands import show_status
        from cli.utils import get_base_dir

        base_dir = get_base_dir()
        show_status(base_dir=base_dir)
        return

    elif args.command == "validate":
        from cli.commands import validate_config

        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        # Validate doesn't need full setup, but it needs the package
        try:
            validate_config(args.config, base_dir=base_dir)
        except ImportError:
            print("Error: GOLIAT package not installed. Run 'goliat study' to install.")
        return

    # Commands that need full setup
    from goliat.utils.setup import initial_setup

    initial_setup()

    if args.command == "study":
        from cli.run_study import main as study_main

        # Reconstruct sys.argv for the study module (it expects to parse its own args)
        # Remove 'goliat study' and keep just the config and flags
        original_argv = sys.argv[:]
        sys.argv = ["goliat-study"]  # Fake program name for compatibility
        if args.config:
            sys.argv.append(args.config)
        if args.title:
            sys.argv.extend(["--title", args.title])
        if args.pid:
            sys.argv.extend(["--pid", args.pid])
        if args.no_cache:
            sys.argv.append("--no-cache")
        try:
            study_main()
        finally:
            sys.argv = original_argv

    elif args.command == "analyze":
        from cli.run_analysis import main as analyze_main

        original_argv = sys.argv[:]
        sys.argv = ["goliat-analyze", "--config", args.config]
        try:
            analyze_main()
        finally:
            sys.argv = original_argv

    elif args.command == "parallel":
        from cli.run_parallel_studies import main as parallel_main

        original_argv = sys.argv[:]
        sys.argv = ["goliat-parallel"]
        if args.config:
            sys.argv.append(args.config)
        if args.num_splits != 4:  # Only add if not default
            sys.argv.extend(["--num-splits", str(args.num_splits)])
        if args.skip_split:
            sys.argv.append("--skip-split")
        if args.no_cache:
            sys.argv.append("--no-cache")
        try:
            parallel_main()
        finally:
            sys.argv = original_argv

    elif args.command in ("free-space", "freespace"):
        from cli.run_free_space_study import main as free_space_main

        original_argv = sys.argv[:]
        sys.argv = ["goliat-free-space"]
        try:
            free_space_main()
        finally:
            sys.argv = original_argv

    elif args.command == "super_study":
        from cli.run_super_study import main as super_study_main

        original_argv = sys.argv[:]
        sys.argv = ["goliat-super-study", args.config, "--name", args.name]
        if args.description:
            sys.argv.extend(["--description", args.description])
        if args.num_splits != 4:
            sys.argv.extend(["--num-splits", str(args.num_splits)])
        if args.server_url:
            sys.argv.extend(["--server-url", args.server_url])
        try:
            super_study_main()
        finally:
            sys.argv = original_argv

    elif args.command == "worker":
        from cli.run_worker import main as worker_main

        original_argv = sys.argv[:]
        sys.argv = ["goliat-worker", str(args.assignment_index), args.super_study_name]
        if args.title:
            sys.argv.extend(["--title", args.title])
        if args.no_cache:
            sys.argv.append("--no-cache")
        if args.server_url:
            sys.argv.extend(["--server-url", args.server_url])
        try:
            worker_main()
        finally:
            sys.argv = original_argv

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
