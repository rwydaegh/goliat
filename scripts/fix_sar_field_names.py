#!/usr/bin/env python3
"""Fix SAR field names in old result files based on bounding_box setting.

This script scans through result directories and updates sar_results.json files
to use the correct SAR field name (whole_body_sar, head_SAR, or trunk_SAR) based
on the bounding_box setting in config.json.

If bounding_box is "whole_body", converts head_SAR or trunk_SAR to whole_body_sar.
"""

import json
import sys
from pathlib import Path


def extract_scenario_name_from_placement(placement_name: str) -> str | None:
    """Extract base scenario name from placement directory name.

    Examples:
        "by_cheek_tragus_tilt_base" -> "by_cheek"
        "front_of_eyes_center_vertical" -> "front_of_eyes"
        "by_belly_up_vertical" -> "by_belly"
    """
    if placement_name.startswith("front_of_eyes"):
        return "front_of_eyes"
    elif placement_name.startswith("by_cheek"):
        return "by_cheek"
    elif placement_name.startswith("by_belly"):
        return "by_belly"
    return None


def get_bounding_box_setting(config_path: Path, placement_name: str) -> str | None:
    """Read bounding_box setting from config.json.

    Returns:
        "whole_body", "head", "trunk", "default", or None if not found
    """
    if not config_path.exists():
        return None

    try:
        with open(config_path, "r") as f:
            config = json.load(f)

        config_snapshot = config.get("config_snapshot", {})
        placement_scenarios = config_snapshot.get("placement_scenarios", {})

        # Extract scenario name
        scenario_name = extract_scenario_name_from_placement(placement_name)
        if not scenario_name:
            return None

        scenario_config = placement_scenarios.get(scenario_name, {})
        return scenario_config.get("bounding_box", "default")
    except Exception as e:
        print(f"  ERROR reading {config_path}: {e}", file=sys.stderr)
        return None


def fix_sar_results_file(sar_results_path: Path, pkl_path: Path, bounding_box_setting: str) -> bool:
    """Fix SAR field names in sar_results.json and sar_stats_all_tissues.pkl based on bounding_box setting.

    Args:
        sar_results_path: Path to sar_results.json file
        pkl_path: Path to sar_stats_all_tissues.pkl file
        bounding_box_setting: "whole_body", "head", "trunk", or "default"

    Returns:
        True if any file was modified, False otherwise
    """
    modified_json = False
    modified_pkl = False

    # Fix JSON file
    if sar_results_path.exists():
        try:
            with open(sar_results_path, "r") as f:
                sar_results = json.load(f)

            sar_value = None
            old_key = None

            # Check what SAR field exists
            if "whole_body_sar" in sar_results:
                # Already correct, nothing to do for JSON
                pass
            elif "head_SAR" in sar_results:
                sar_value = sar_results["head_SAR"]
                old_key = "head_SAR"
            elif "trunk_SAR" in sar_results:
                sar_value = sar_results["trunk_SAR"]
                old_key = "trunk_SAR"

            if old_key:
                # Determine what the field should be based on bounding_box setting
                if bounding_box_setting == "whole_body":
                    new_key = "whole_body_sar"
                elif bounding_box_setting == "head":
                    new_key = "head_SAR"
                elif bounding_box_setting == "trunk":
                    new_key = "trunk_SAR"
                else:  # "default" or None - keep existing behavior
                    # Default logic: by_cheek/front_of_eyes -> head_SAR, by_belly -> trunk_SAR
                    placement_name = sar_results_path.parent.name
                    if placement_name.startswith("front_of_eyes") or placement_name.startswith("by_cheek"):
                        new_key = "head_SAR"
                    elif placement_name.startswith("by_belly"):
                        new_key = "trunk_SAR"
                    else:
                        new_key = old_key  # Keep as is

                # Only modify if key needs to change
                if old_key != new_key:
                    # Remove old key and add new key
                    del sar_results[old_key]
                    sar_results[new_key] = sar_value
                    modified_json = True

                    # Write back to file
                    with open(sar_results_path, "w") as f:
                        json.dump(sar_results, f, indent=4)
        except Exception as e:
            print(f"  ERROR processing JSON {sar_results_path}: {e}", file=sys.stderr)

    # Fix PKL file
    if pkl_path.exists():
        try:
            import pickle

            with open(pkl_path, "rb") as f:
                pkl_data = pickle.load(f)

            summary_results = pkl_data.get("summary_results", {})
            if not summary_results:
                return modified_json

            sar_value = None
            old_key = None

            # Check what SAR field exists in summary_results
            if "whole_body_sar" in summary_results:
                # Already correct, nothing to do for PKL
                pass
            elif "head_SAR" in summary_results:
                sar_value = summary_results["head_SAR"]
                old_key = "head_SAR"
            elif "trunk_SAR" in summary_results:
                sar_value = summary_results["trunk_SAR"]
                old_key = "trunk_SAR"

            if old_key:
                # Determine what the field should be based on bounding_box setting
                if bounding_box_setting == "whole_body":
                    new_key = "whole_body_sar"
                elif bounding_box_setting == "head":
                    new_key = "head_SAR"
                elif bounding_box_setting == "trunk":
                    new_key = "trunk_SAR"
                else:  # "default" or None - keep existing behavior
                    # Default logic: by_cheek/front_of_eyes -> head_SAR, by_belly -> trunk_SAR
                    placement_name = pkl_path.parent.name
                    if placement_name.startswith("front_of_eyes") or placement_name.startswith("by_cheek"):
                        new_key = "head_SAR"
                    elif placement_name.startswith("by_belly"):
                        new_key = "trunk_SAR"
                    else:
                        new_key = old_key  # Keep as is

                # Only modify if key needs to change
                if old_key != new_key:
                    # Remove old key and add new key
                    del summary_results[old_key]
                    summary_results[new_key] = sar_value
                    pkl_data["summary_results"] = summary_results
                    modified_pkl = True

                    # Write back to file
                    with open(pkl_path, "wb") as f:
                        pickle.dump(pkl_data, f)
        except Exception as e:
            print(f"  ERROR processing PKL {pkl_path}: {e}", file=sys.stderr)

    return modified_json or modified_pkl


def scan_and_fix_results(base_dir: Path, dry_run: bool = False):
    """Scan result directories and fix SAR field names.

    Args:
        base_dir: Base directory containing results (e.g., "results/near_field")
        dry_run: If True, only report what would be changed without modifying files
    """
    base_dir = Path(base_dir)
    if not base_dir.exists():
        print(f"ERROR: Directory not found: {base_dir}", file=sys.stderr)
        return

    fixed_count = 0
    skipped_count = 0
    error_count = 0

    # Scan structure: base_dir/phantom/frequency/placement/
    for phantom_dir in sorted(base_dir.iterdir()):
        if not phantom_dir.is_dir():
            continue

        for freq_dir in sorted(phantom_dir.iterdir()):
            if not freq_dir.is_dir():
                continue

            for placement_dir in sorted(freq_dir.iterdir()):
                if not placement_dir.is_dir():
                    continue

                config_path = placement_dir / "config.json"
                sar_results_path = placement_dir / "sar_results.json"
                pkl_path = placement_dir / "sar_stats_all_tissues.pkl"

                if not sar_results_path.exists():
                    continue

                # Get bounding box setting from config
                bounding_box_setting = get_bounding_box_setting(config_path, placement_dir.name)

                if bounding_box_setting is None:
                    skipped_count += 1
                    if not dry_run:
                        print(f"  SKIP: {placement_dir} - no config.json or bounding_box setting")
                    continue

                # Fix the SAR results files (JSON and PKL)
                if dry_run:
                    # Check what would change in JSON
                    with open(sar_results_path, "r") as f:
                        sar_results = json.load(f)

                    has_head_json = "head_SAR" in sar_results
                    has_trunk_json = "trunk_SAR" in sar_results
                    has_whole_body_json = "whole_body_sar" in sar_results

                    # Check PKL if it exists
                    has_head_pkl = False
                    has_trunk_pkl = False
                    if pkl_path.exists():
                        try:
                            import pickle

                            with open(pkl_path, "rb") as f:
                                pkl_data = pickle.load(f)
                            summary_results = pkl_data.get("summary_results", {})
                            has_head_pkl = "head_SAR" in summary_results
                            has_trunk_pkl = "trunk_SAR" in summary_results
                            # Check for whole_body_sar but don't store (not used)
                            _ = "whole_body_sar" in summary_results
                        except Exception:
                            pass

                    needs_fix_json = bounding_box_setting == "whole_body" and (has_head_json or has_trunk_json)
                    needs_fix_pkl = bounding_box_setting == "whole_body" and (has_head_pkl or has_trunk_pkl)

                    if needs_fix_json or needs_fix_pkl:
                        print(f"  WOULD FIX: {placement_dir}")
                        print(f"    bounding_box: {bounding_box_setting}")
                        if needs_fix_json:
                            print(f"    JSON: {'head_SAR' if has_head_json else 'trunk_SAR'} -> whole_body_sar")
                        if needs_fix_pkl:
                            print(f"    PKL: {'head_SAR' if has_head_pkl else 'trunk_SAR'} -> whole_body_sar")
                        fixed_count += 1
                    elif not has_whole_body_json and not has_head_json and not has_trunk_json:
                        print(f"  SKIP: {placement_dir} - no SAR field found")
                        skipped_count += 1
                    else:
                        skipped_count += 1
                else:
                    modified = fix_sar_results_file(sar_results_path, pkl_path, bounding_box_setting)
                    if modified:
                        print(f"  FIXED: {placement_dir} (bounding_box: {bounding_box_setting})")
                        fixed_count += 1
                    else:
                        skipped_count += 1

    print("\n--- Summary ---")
    print(f"Fixed: {fixed_count}")
    print(f"Skipped: {skipped_count}")
    if error_count > 0:
        print(f"Errors: {error_count}")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Fix SAR field names in old result files based on bounding_box setting")
    parser.add_argument(
        "--results-dir",
        type=str,
        default="results/near_field",
        help="Base directory containing results (default: results/near_field)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be changed without modifying files",
    )
    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    if not results_dir.is_absolute():
        # Assume relative to script location or current working directory
        script_dir = Path(__file__).parent.parent
        results_dir = script_dir / args.results_dir

    print(f"Scanning: {results_dir}")
    if args.dry_run:
        print("DRY RUN MODE - no files will be modified\n")

    scan_and_fix_results(results_dir, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
