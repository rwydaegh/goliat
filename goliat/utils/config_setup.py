"""Config file setup utilities."""

import logging
import os
import shutil
from pathlib import Path
from typing import Optional


def setup_configs(base_dir: Optional[str] = None, overwrite: bool = False) -> None:
    """Copy default config files from package to base_dir/configs/.

    Args:
        base_dir: Base directory where configs should be copied (defaults to current working directory).
        overwrite: If True, overwrite existing files without prompting.
    """
    if base_dir is None:
        base_dir = os.getcwd()

    # Get default configs from package
    try:
        from importlib.resources import files

        defaults_traversable = files("goliat") / "config" / "defaults"
        if not defaults_traversable.is_dir():
            raise FileNotFoundError("Package defaults directory not found")
        # Convert Traversable to Path for easier manipulation
        defaults_dir = Path(str(defaults_traversable))
    except (ImportError, ModuleNotFoundError, FileNotFoundError):
        # Fallback: try to find in repo structure (for editable installs)
        script_dir = Path(__file__).parent.parent.parent
        defaults_dir = script_dir / "config" / "defaults"
        if not defaults_dir.exists():
            logging.warning("Could not find default config files. Skipping config setup.")
            return

    # Target directory
    configs_dir = Path(base_dir) / "configs"
    configs_dir.mkdir(exist_ok=True)

    # Copy each config file (exclude material_name_mapping.json - it goes to data/)
    copied_count = 0
    skipped_count = 0

    for config_file in defaults_dir.glob("*.json"):
        # Skip material_name_mapping.json - it's copied separately to data/
        if config_file.name == "material_name_mapping.json":
            continue
        target_file = configs_dir / config_file.name

        # Check if file exists
        if target_file.exists() and not overwrite:
            # Silently skip existing files (don't prompt - this is called during normal operation)
            skipped_count += 1
            continue

        # Copy file
        try:
            shutil.copy2(str(config_file), str(target_file))
            logging.info(f"  ✓ Copied {config_file.name}")
            copied_count += 1
        except Exception as e:
            logging.error(f"  ✗ Failed to copy {config_file.name}: {e}")

    if copied_count > 0:
        logging.info(f"\n✓ Config files initialized in {configs_dir}")
        if skipped_count > 0:
            logging.info(f"  ({skipped_count} file(s) skipped - already exist)")

    # Copy material_name_mapping.json to data/ directory
    try:
        material_mapping_source = defaults_dir / "material_name_mapping.json"
        if material_mapping_source.exists():
            data_dir = Path(base_dir) / "data"
            data_dir.mkdir(exist_ok=True)
            material_mapping_target = data_dir / "material_name_mapping.json"

            if material_mapping_target.exists() and not overwrite:
                # Silently skip existing files (don't prompt)
                logging.info("  Skipping material_name_mapping.json (already exists)")
            else:
                shutil.copy2(str(material_mapping_source), str(material_mapping_target))
                logging.info("  ✓ Copied material_name_mapping.json to data/")
    except Exception as e:
        logging.warning(f"Could not copy material_name_mapping.json: {e}")
