"""Validate that config files in configs/ match those in goliat/config/defaults/."""

import json
import sys
from pathlib import Path


def normalize_json(file_path: Path) -> dict:
    """Load and normalize JSON (handles formatting differences)."""
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def compare_configs():
    """Compare config files: for each file in defaults/, check if it matches in configs/."""
    repo_root = Path(__file__).parent.parent
    defaults_dir = repo_root / "goliat" / "config" / "defaults"
    configs_dir = repo_root / "configs"

    if not defaults_dir.exists():
        print(f"❌ Defaults directory not found: {defaults_dir}")
        return False

    if not configs_dir.exists():
        print(f"❌ Configs directory not found: {configs_dir}")
        return False

    errors = []
    checked_count = 0

    # Iterate over all JSON files in defaults (same logic as setup_configs)
    for default_file in defaults_dir.glob("*.json"):
        # Skip material_name_mapping.json - it goes to data/, not configs/
        if default_file.name == "material_name_mapping.json":
            continue

        config_file = configs_dir / default_file.name

        # Check if the file exists in configs/
        if not config_file.exists():
            errors.append(f"[ERROR] Missing in configs/: {default_file.name}")
            continue

        checked_count += 1

        # Compare content
        try:
            default_data = normalize_json(default_file)
            config_data = normalize_json(config_file)

            if default_data != config_data:
                errors.append(f"[ERROR] Content mismatch: {default_file.name}")
                # Show a brief diff
                import difflib

                default_str = json.dumps(default_data, indent=2, sort_keys=True)
                config_str = json.dumps(config_data, indent=2, sort_keys=True)
                diff = list(
                    difflib.unified_diff(
                        default_str.splitlines(keepends=True),
                        config_str.splitlines(keepends=True),
                        fromfile=f"defaults/{default_file.name}",
                        tofile=f"configs/{default_file.name}",
                        lineterm="",
                        n=3,  # Show 3 lines of context
                    )
                )
                # Limit diff output to avoid overwhelming output
                errors.extend(diff[:30])
        except json.JSONDecodeError as e:
            errors.append(f"[ERROR] Invalid JSON in {config_file.name}: {e}")
        except Exception as e:
            errors.append(f"[ERROR] Error comparing {default_file.name}: {e}")

    if errors:
        print("=" * 80)
        print("Config sync validation failed!")
        print("=" * 80)
        print(f"Checked {checked_count} file(s) from defaults/")
        print()
        for error in errors:
            print(error)
        print("\n💡 Tip: Run 'python scripts/sync_configs.py' to sync configs")
        return False

    print(f"All {checked_count} config file(s) are in sync!")
    return True


if __name__ == "__main__":
    success = compare_configs()
    sys.exit(0 if success else 1)
