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

    print(f"✓ Created config file: {output_path}")
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
    print(f"Package installed: {'✓ Yes' if is_installed else '✗ No'}")

    # Python interpreter
    print(f"Python: {sys.executable}")
    if "Sim4Life" in sys.executable:
        print("  ✓ Sim4Life Python detected")
    else:
        print("  ⚠ Not using Sim4Life Python")

    # Data directories
    data_dir = os.path.join(base_dir, "data")
    phantoms_dir = os.path.join(data_dir, "phantoms")
    antennas_dir = os.path.join(data_dir, "antennas", "centered")

    print("\nData directories:")
    print(f"  Phantoms: {'✓ Present' if os.path.exists(phantoms_dir) and os.listdir(phantoms_dir) else '✗ Missing'}")
    print(f"  Antennas: {'✓ Present' if os.path.exists(antennas_dir) and os.listdir(antennas_dir) else '✗ Missing'}")

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
            print("  ✗ Missing 'study_type'")
            sys.exit(1)
        else:
            print(f"  ✓ Study type: {study_type}")

        phantoms = config["phantoms"] or []
        if not phantoms:
            print("  ✗ No phantoms specified")
            sys.exit(1)
        else:
            if isinstance(phantoms, dict):
                phantom_list = list(phantoms.keys())
            else:
                phantom_list = phantoms
            print(f"  ✓ Phantoms: {', '.join(phantom_list)}")

        if study_type == "near_field":
            antenna_config = config["antenna_config"] or {}
            if not antenna_config:
                print("  ✗ Missing 'antenna_config'")
                sys.exit(1)
            else:
                print(f"  ✓ Frequencies: {', '.join(antenna_config.keys())} MHz")
        elif study_type == "far_field":
            frequencies = config["frequencies_mhz"] or []
            if not frequencies:
                print("  ✗ Missing 'frequencies_mhz'")
                sys.exit(1)
            else:
                print(f"  ✓ Frequencies: {', '.join(map(str, frequencies))} MHz")

        print("  ✓ Config is valid!")

    except Exception as e:
        print(f"  ✗ Error: {e}")
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
