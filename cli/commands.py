"""CLI commands for initialization and utilities."""

import json
import os
import sys


def init_config(study_type: str = "near_field", output_path: str = None, base_dir: str = None):
    """Initialize a new GOLIAT config file from a template.

    Args:
        study_type: Type of study ('near_field' or 'far_field')
        output_path: Where to save the config (defaults to configs/my_{study_type}_config.json)
        base_dir: Base directory of the project (for finding templates)
    """
    if base_dir is None:
        from cli.utils import get_base_dir

        base_dir = get_base_dir()

    # Template file
    template_file = os.path.join(base_dir, "configs", f"{study_type}_config.json")

    if not os.path.exists(template_file):
        print(f"Error: Template file not found: {template_file}")
        print("Available study types: near_field, far_field")
        sys.exit(1)

    # Output path
    if output_path is None:
        output_name = f"my_{study_type}_config.json"
        output_path = os.path.join(base_dir, "configs", output_name)

    # Make sure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Check if file already exists
    if os.path.exists(output_path):
        response = input(f"File {output_path} already exists. Overwrite? [y/N]: ").strip().lower()
        if response not in ("y", "yes"):
            print("Cancelled.")
            return

    # Copy template
    with open(template_file, "r") as f:
        config = json.load(f)

    # Write to output
    with open(output_path, "w") as f:
        json.dump(config, f, indent=2)

    print(f"Created config file: {output_path}")
    print("  Edit this file to customize your study settings.")


def show_status(base_dir: str = None):
    """Show GOLIAT setup status and environment information."""
    if base_dir is None:
        from cli.utils import get_base_dir

        base_dir = get_base_dir()

    print("=" * 60)
    print("GOLIAT Status")
    print("=" * 60)

    # Package version
    try:
        import goliat

        if hasattr(goliat, "__version__"):
            print(f"Version: {goliat.__version__}")
        else:
            # Read from pyproject.toml
            import tomllib

            pyproject_path = os.path.join(base_dir, "pyproject.toml")
            if os.path.exists(pyproject_path):
                with open(pyproject_path, "rb") as f:
                    pyproject = tomllib.load(f)
                    version = pyproject.get("project", {}).get("version", "unknown")
                    print(f"Version: {version}")
    except Exception:
        print("Version: unknown")

    # Package installation status
    from goliat.utils.setup import check_package_installed

    is_installed = check_package_installed()
    print(f"Package installed: {'Yes' if is_installed else 'No'}")

    # Python interpreter
    print(f"Python: {sys.executable}")
    if "Sim4Life" in sys.executable:
        print("  Sim4Life Python detected")
    else:
        print("  Warning: Not using Sim4Life Python")

    # Data directories
    data_dir = os.path.join(base_dir, "data")
    phantoms_dir = os.path.join(data_dir, "phantoms")
    antennas_dir = os.path.join(data_dir, "antennas", "centered")

    print("\nData directories:")
    print(f"  Phantoms: {'Present' if os.path.exists(phantoms_dir) and os.listdir(phantoms_dir) else 'Missing'}")
    print(f"  Antennas: {'Present' if os.path.exists(antennas_dir) and os.listdir(antennas_dir) else 'Missing'}")

    # Config files
    configs_dir = os.path.join(base_dir, "configs")
    if os.path.exists(configs_dir):
        config_files = [f for f in os.listdir(configs_dir) if f.endswith(".json")]
        print(f"\nConfig files: {len(config_files)} found")

    print("=" * 60)


def validate_config(config_path: str, base_dir: str = None):
    """Validate a GOLIAT config file."""
    if base_dir is None:
        from cli.utils import get_base_dir

        base_dir = get_base_dir()

    try:
        from goliat.config import Config

        print(f"Validating config: {config_path}")
        config = Config(base_dir, config_path)

        # Basic checks
        study_type = config["study_type"]
        if not study_type:
            print("  ERROR: Missing 'study_type'")
            sys.exit(1)
        else:
            print(f"  Study type: {study_type}")

        phantoms = config["phantoms"] or []
        if not phantoms:
            print("  ERROR: No phantoms specified")
            sys.exit(1)
        else:
            if isinstance(phantoms, dict):
                phantom_list = list(phantoms.keys())
            else:
                phantom_list = phantoms
            print(f"  Phantoms: {', '.join(phantom_list)}")

        if study_type == "near_field":
            antenna_config = config["antenna_config"] or {}
            if not antenna_config:
                print("  ERROR: Missing 'antenna_config'")
                sys.exit(1)
            else:
                print(f"  Frequencies: {', '.join(antenna_config.keys())} MHz")
        elif study_type == "far_field":
            frequencies = config["frequencies_mhz"] or []
            if not frequencies:
                print("  ERROR: Missing 'frequencies_mhz'")
                sys.exit(1)
            else:
                print(f"  Frequencies: {', '.join(map(str, frequencies))} MHz")

        print("  Config is valid!")

    except Exception as e:
        print(f"  ERROR: {e}")
        sys.exit(1)


def show_version():
    """Show GOLIAT version."""
    try:
        # Single source of truth: read from installed package metadata
        from goliat import __version__

        print(f"GOLIAT {__version__}")
    except Exception:
        # Fallback: try reading from pyproject.toml
        try:
            import tomllib
            from cli.utils import get_base_dir

            base_dir = get_base_dir()
            pyproject_path = os.path.join(base_dir, "pyproject.toml")
            if os.path.exists(pyproject_path):
                with open(pyproject_path, "rb") as f:
                    pyproject = tomllib.load(f)
                    version = pyproject.get("project", {}).get("version", "unknown")
                    print(f"GOLIAT {version}")
            else:
                print("GOLIAT version unknown")
        except Exception:
            print("GOLIAT version unknown")


def config_show(base_dir: str = None):
    """Show current GOLIAT configuration and preferences."""
    if base_dir is None:
        from cli.utils import get_base_dir

        base_dir = get_base_dir()

    from goliat.utils.preferences import get_user_preferences

    prefs = get_user_preferences(base_dir)

    print("\n" + "=" * 60)
    print("GOLIAT Configuration")
    print("=" * 60)

    # Sim4Life version
    s4l_path = prefs.get("sim4life_python_path")
    if s4l_path:
        import re

        match = re.search(r"Sim4Life[_-](\d+\.\d+\.\d+)", s4l_path)
        version_str = match.group(1) if match else "unknown"
        print(f"\nSim4Life version: {version_str}")
        print(f"  Path: {s4l_path}")
    else:
        print("\nSim4Life version: Not configured")
        print("  Run 'goliat config set-version' to select a version.")

    # Bashrc sync
    sync_bashrc = prefs.get("sync_bashrc_to_home", False)
    print(f"\nAuto-sync .bashrc to home: {'Yes' if sync_bashrc else 'No'}")

    # Preferences file location
    prefs_file = os.path.join(base_dir, "data", ".goliat_preferences.json")
    print(f"\nPreferences file: {prefs_file}")

    print("=" * 60 + "\n")


def config_set_version(base_dir: str = None):
    """Interactively change the Sim4Life version."""
    if base_dir is None:
        from cli.utils import get_base_dir

        base_dir = get_base_dir()

    from goliat.utils.bashrc import update_bashrc
    from goliat.utils.preferences import get_sim4life_python_path, set_sim4life_python_path
    from goliat.utils.python_interpreter import find_sim4life_python_executables

    viable_pythons = find_sim4life_python_executables()

    if not viable_pythons:
        print("\nNo supported Sim4Life installations found (8.2 or 9.2).")
        print("Please install Sim4Life first.")
        return

    current_path = get_sim4life_python_path(base_dir)

    print("\n" + "=" * 60)
    print("GOLIAT - Change Sim4Life Version")
    print("=" * 60)

    if current_path:
        import re

        match = re.search(r"Sim4Life[_-](\d+\.\d+\.\d+)", current_path)
        current_version = match.group(1) if match else "unknown"
        print(f"\nCurrent version: Sim4Life {current_version}")
    else:
        print("\nNo version currently configured.")

    print("\nAvailable versions:\n")

    import re

    for i, p in enumerate(viable_pythons):
        match = re.search(r"Sim4Life[_-](\d+\.\d+\.\d+)", p)
        version_str = match.group(1) if match else "unknown"
        current_marker = " (current)" if p == current_path else ""
        recommended = " (recommended)" if i == 0 and not current_marker else ""
        print(f"  [{i + 1}] Sim4Life {version_str}{current_marker}{recommended}")

    print("\n" + "-" * 60)
    print("TIP: Your choice is saved and can be changed anytime with")
    print("     'goliat config set-version'")
    print("-" * 60)

    try:
        choice = input("\nSelect a version, or press Enter to cancel: ")

        if not choice:
            print("\nNo changes made.")
            return

        selected_index = int(choice) - 1
        if not 0 <= selected_index < len(viable_pythons):
            raise ValueError

        selected_python = viable_pythons[selected_index]

        if selected_python == current_path:
            print("\nThat's already your current version. No changes needed.")
            return

        # Save to preferences
        set_sim4life_python_path(base_dir, selected_python)

        # Update bashrc
        update_bashrc(selected_python, base_dir=base_dir)

        print("\n" + "=" * 60)
        print("SUCCESS! Sim4Life version updated.")
        print("=" * 60)
        print(f"\nNew version: {selected_python}")
        print("\nTo apply changes, run:")
        print("  source .bashrc")
        print("\nThen, if you haven't already, reinstall GOLIAT:")
        print("  pip install -e .            # for editable install, or")
        print("  pip install goliat          # from PyPI")
        print("=" * 60 + "\n")

    except (ValueError, IndexError):
        print("\nInvalid selection. No changes made.")
