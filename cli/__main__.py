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
    analyze_parser.add_argument(
        "config",
        type=str,
        nargs="?",
        default="near_field_config",
        help="Path or name of the configuration file (e.g., near_field_config or configs/near_field_config.json).",
    )
    analyze_parser.add_argument(
        "--format",
        type=str,
        choices=["pdf", "png"],
        default="pdf",
        help="Output format for plots (default: pdf).",
    )
    analyze_parser.add_argument(
        "--analysis",
        type=str,
        default=None,
        help="Path to analysis configuration file (JSON) specifying which plots to generate.",
    )
    analyze_parser.add_argument(
        "--generate-paper",
        action="store_true",
        default=False,
        help="Generate LaTeX paper after analysis completes.",
    )
    analyze_parser.add_argument(
        "--no-gui",
        action="store_true",
        default=False,
        help="Disable the GUI window and run in terminal-only mode.",
    )

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

    # config command with subcommands
    config_parser = subparsers.add_parser(
        "config",
        help="Manage GOLIAT configuration and preferences",
        description="View or modify GOLIAT user preferences (Sim4Life version, bashrc sync, etc.)",
    )
    config_subparsers = config_parser.add_subparsers(dest="config_command", help="Config subcommands")

    # config show
    config_subparsers.add_parser("show", help="Show current configuration and preferences")

    # config set-version
    config_subparsers.add_parser(
        "set-version",
        help="Change the Sim4Life version",
        description="Interactively select which Sim4Life version to use.",
    )

    # AI assistant commands
    ask_parser = subparsers.add_parser("ask", help="Ask AI assistant about GOLIAT")
    ask_parser.add_argument("question", type=str, nargs="?", help="Question to ask")
    ask_parser.add_argument("--debug", type=str, metavar="ERROR", help="Debug an error message")
    ask_parser.add_argument("--logs", type=str, metavar="FILE", help="Log file for context")
    ask_parser.add_argument("--config", type=str, metavar="FILE", help="Config file for context")
    ask_parser.add_argument("--backend", type=str, choices=["openai", "local"], default="openai")
    ask_parser.add_argument("--reindex", action="store_true", help="Force reindex codebase")

    chat_parser = subparsers.add_parser("chat", help="Interactive chat with AI assistant")
    chat_parser.add_argument("--backend", type=str, choices=["openai", "local"], default="openai")

    debug_parser = subparsers.add_parser(
        "debug",
        help="Debug errors and analyze GOLIAT logs with AI assistance",
        description="Automatically gathers context from logs, shell history, and environment, "
        "then uses GPT-5 to diagnose issues and suggest fixes.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                                    # Auto-detect from recent logs
  %(prog)s "simulation failed"                # Debug specific error
  %(prog)s --question "Why did SAR extraction fail?"
  %(prog)s --logs logs/session.log --log-count 5
  %(prog)s --no-shell-context                 # Skip shell history gathering
        """,
    )
    debug_parser.add_argument(
        "error",
        type=str,
        nargs="?",
        metavar="ERROR_MESSAGE",
        help="The error message to debug. If not provided, will try to infer from context.",
    )
    debug_parser.add_argument(
        "--question",
        "--query",
        "-q",
        type=str,
        dest="question",
        help="Natural language question about the error or logs. "
        "Example: 'Why did the simulation fail?' or 'What caused the power balance issue?'",
    )
    debug_parser.add_argument(
        "--logs",
        type=str,
        metavar="LOG_FILE",
        help="Path to a specific log file to analyze. If not provided, will auto-detect recent log files from logs/ directory.",
    )
    debug_parser.add_argument(
        "--log-count",
        type=int,
        metavar="N",
        help="Number of recent log sessions to analyze (default: 3). "
        "Each session includes both .log (verbose) and .progress.log (summary) files. "
        "Only applies when --logs is not specified.",
    )
    debug_parser.add_argument(
        "--config",
        type=str,
        metavar="CONFIG_FILE",
        help="Path to a GOLIAT config file to include for context. Useful when debugging config-related issues.",
    )
    debug_parser.add_argument(
        "--no-shell-context",
        action="store_true",
        help="Don't gather shell history and environment variables. Useful if you want to focus only on log files.",
    )
    debug_parser.add_argument(
        "--no-browser", action="store_true", help="Don't open the HTML debug report in browser. Just print to console."
    )
    # Model selection group
    model_group = debug_parser.add_mutually_exclusive_group()
    model_group.add_argument("--simple", action="store_true", help="Force use of simple model (gpt-5-mini) - faster and cheaper.")
    model_group.add_argument("--complex", action="store_true", help="Force use of complex model (gpt-5) - more thorough analysis.")
    model_group.add_argument("--auto", action="store_true", help="Auto-select model based on query complexity (default).")

    recommend_parser = subparsers.add_parser("recommend", help="AI analysis of logs for issues")
    recommend_parser.add_argument("log_file", type=str, help="Log file to analyze (or '-' for stdin)")
    recommend_parser.add_argument("--quiet", action="store_true", help="Only output if issues found")
    recommend_parser.add_argument("--backend", type=str, choices=["openai", "local"], default="openai")

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
        default=None,
        help="Number of assignments to split into (default: 4 for auto mode).",
    )
    super_study_parser.add_argument(
        "--split-by",
        type=str,
        default="auto",
        choices=["auto", "phantom", "direction", "polarization", "frequency"],
        help="Dimension to split by: 'auto' (phantoms × frequencies), 'phantom', 'direction', 'polarization', or 'frequency'.",
    )
    super_study_parser.add_argument(
        "--server-url",
        type=str,
        default=None,
        help="URL of the monitoring server (default: https://monitor.goliat.waves-ugent.be).",
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
        "--reupload-results",
        action="store_true",
        help="When caching skips simulations, upload extraction results that appear valid.",
    )
    worker_parser.add_argument(
        "--server-url",
        type=str,
        default=None,
        help="URL of the monitoring server (default: https://monitor.goliat.waves-ugent.be).",
    )

    # stats command - unified for both directory scanning and single-file parsing
    stats_parser = subparsers.add_parser("stats", help="Analyze simulation statistics from verbose.log files")
    stats_parser.add_argument(
        "path",
        nargs="?",
        default="results",
        help="Results directory to scan OR path to a single verbose.log file (default: results).",
    )
    stats_parser.add_argument(
        "-o",
        "--output",
        default="paper/simulation_stats",
        help="Output directory for plots/data (directory mode) or JSON file path (single-file mode).",
    )
    stats_parser.add_argument(
        "--json",
        action="store_true",
        help="Also save raw stats as JSON (directory mode only).",
    )
    stats_parser.add_argument(
        "--pretty",
        action="store_true",
        help="Print metrics to console in pretty format (single-file mode only).",
    )

    return parser


def _print_ascii_art():
    """Print GOLIAT ASCII art banner if terminal is wide enough, otherwise print simple text."""
    import shutil

    from cli.ascii_art import GOLIAT_BANNER

    # Get terminal width
    try:
        terminal_width = shutil.get_terminal_size().columns
    except (OSError, AttributeError):
        # Fallback if terminal size can't be determined (e.g., piped output)
        terminal_width = 80

    # Find the widest line in the ASCII art
    lines = [line for line in GOLIAT_BANNER.split("\n") if line.strip()]
    if not lines:
        print("\nGOLIAT\n")
        return

    max_width = max(len(line) for line in lines)

    # Only print ASCII art if it uses less than 120% of terminal width
    if max_width < terminal_width * 1.2:
        print(GOLIAT_BANNER)
    else:
        # Print simple replacement when terminal is too narrow
        print("\n" + "=" * min(terminal_width - 2, 60))
        print("GOLIAT".center(min(terminal_width - 2, 60)))
        print("=" * min(terminal_width - 2, 60) + "\n")


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
        print("\nGOLIAT initialization complete!")
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

    elif args.command == "config":
        from cli.commands import config_show, config_set_version
        from cli.utils import get_base_dir

        base_dir = get_base_dir()

        if args.config_command == "show":
            config_show(base_dir=base_dir)
        elif args.config_command == "set-version":
            config_set_version(base_dir=base_dir)
        else:
            # No subcommand given, show help
            print("Usage: goliat config <command>")
            print("\nAvailable commands:")
            print("  show         Show current configuration and preferences")
            print("  set-version  Change the Sim4Life version")
        return

    elif args.command == "ask":
        from cli.run_ai import main_ask

        original_argv = sys.argv[:]
        sys.argv = ["goliat-ask"]
        if args.question:
            sys.argv.append(args.question)
        if hasattr(args, "debug") and args.debug:
            sys.argv.extend(["--debug", args.debug])
        if hasattr(args, "logs") and args.logs:
            sys.argv.extend(["--logs", args.logs])
        if hasattr(args, "config") and args.config:
            sys.argv.extend(["--config", args.config])
        if hasattr(args, "backend"):
            sys.argv.extend(["--backend", args.backend])
        if hasattr(args, "reindex") and args.reindex:
            sys.argv.append("--reindex")
        try:
            main_ask()
        finally:
            sys.argv = original_argv
        return

    elif args.command == "chat":
        from cli.run_ai import main_chat

        original_argv = sys.argv[:]
        sys.argv = ["goliat-chat"]
        if hasattr(args, "backend"):
            sys.argv.extend(["--backend", args.backend])
        try:
            main_chat()
        finally:
            sys.argv = original_argv
        return

    elif args.command == "debug":
        from cli.run_ai import main_debug

        original_argv = sys.argv[:]
        sys.argv = ["goliat-debug"]
        if hasattr(args, "error") and args.error:
            sys.argv.append(args.error)
        if hasattr(args, "question") and args.question:
            sys.argv.extend(["--question", args.question])
        if hasattr(args, "logs") and args.logs:
            sys.argv.extend(["--logs", args.logs])
        if hasattr(args, "log_count") and args.log_count:
            sys.argv.extend(["--log-count", str(args.log_count)])
        if hasattr(args, "config") and args.config:
            sys.argv.extend(["--config", args.config])
        if hasattr(args, "no_shell_context") and args.no_shell_context:
            sys.argv.append("--no-shell-context")
        if hasattr(args, "no_browser") and args.no_browser:
            sys.argv.append("--no-browser")
        if hasattr(args, "simple") and args.simple:
            sys.argv.append("--simple")
        if hasattr(args, "complex") and args.complex:
            sys.argv.append("--complex")
        if hasattr(args, "auto") and args.auto:
            sys.argv.append("--auto")
        try:
            main_debug()
        finally:
            sys.argv = original_argv
        return

    elif args.command == "recommend":
        from cli.run_ai import main_recommend

        original_argv = sys.argv[:]
        sys.argv = ["goliat-recommend", args.log_file]
        if hasattr(args, "quiet") and args.quiet:
            sys.argv.append("--quiet")
        if hasattr(args, "backend"):
            sys.argv.extend(["--backend", args.backend])
        try:
            main_recommend()
        finally:
            sys.argv = original_argv
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
        sys.argv = ["goliat-analyze"]
        if args.config:
            sys.argv.append(args.config)
        if hasattr(args, "format"):
            sys.argv.extend(["--format", args.format])
        if hasattr(args, "analysis") and args.analysis:
            sys.argv.extend(["--analysis", args.analysis])
        if hasattr(args, "generate_paper") and args.generate_paper:
            sys.argv.append("--generate-paper")
        if hasattr(args, "no_gui") and args.no_gui:
            sys.argv.append("--no-gui")
        try:
            analyze_main()
        finally:
            sys.argv = original_argv

    elif args.command == "stats":
        # Determine if path is a single file or directory
        if os.path.isfile(args.path) and args.path.endswith(".log"):
            # Single-file mode: parse a single verbose.log file
            from goliat.analysis.parse_verbose_log import main as parse_log_main

            original_argv = sys.argv[:]
            sys.argv = ["goliat-stats", args.path]
            if args.output:
                sys.argv.extend(["-o", args.output])
            if args.pretty:
                sys.argv.append("--pretty")
            try:
                parse_log_main()
            finally:
                sys.argv = original_argv
        else:
            # Directory mode: scan results directory and generate visualizations
            from goliat.analysis.analyze_simulation_stats import main as stats_main

            original_argv = sys.argv[:]
            sys.argv = ["goliat-stats", args.path]
            if args.output:
                sys.argv.extend(["-o", args.output])
            if args.json:
                sys.argv.append("--json")
            try:
                stats_main()
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
        if args.num_splits is not None:
            sys.argv.extend(["--num-splits", str(args.num_splits)])
        if hasattr(args, "split_by") and args.split_by:
            sys.argv.extend(["--split-by", args.split_by])
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
        if args.reupload_results:
            sys.argv.append("--reupload-results")
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
