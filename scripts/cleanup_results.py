"""
Script to recursively clean up results/far_field directory.

Deletes:
  - All .h5 files ending in '_Output'
  - All .smash files

Usage:
  python scripts/cleanup_results.py --dry-run          # Preview changes (default)
  python scripts/cleanup_results.py --actual-delete    # Delete files
"""

import argparse
from pathlib import Path


def cleanup_far_field(root_dir: Path, dry_run: bool = True):
    """
    Recursively find and delete specified files in the results/far_field directory.
    """
    if not root_dir.exists():
        print(f"Directory not found: {root_dir}")
        return

    print(f"{'DRY RUN: ' if dry_run else ''}Cleaning up results in {root_dir}...")

    deleted_count = 0
    total_size = 0

    for file_path in root_dir.rglob("*"):
        if not file_path.is_file():
            continue

        should_delete = False
        reason = ""

        # Requirement 1: .h5 files ending in _Output
        if file_path.suffix.lower() == ".h5" and file_path.stem.endswith("_Output"):
            should_delete = True
            reason = "_Output.h5 file"

        # Requirement 2: .smash files
        elif file_path.suffix.lower() == ".smash":
            should_delete = True
            reason = ".smash file"

        if should_delete:
            try:
                size = file_path.stat().st_size
                if dry_run:
                    print(f"[DRY RUN] Would delete {file_path} ({reason}) [{size / 1024 / 1024:.2f} MB]")
                else:
                    file_path.unlink()
                    print(f"[DELETED] {file_path} ({reason})")

                deleted_count += 1
                total_size += size
            except Exception as e:
                print(f"[ERROR] Failed to process {file_path}: {e}")

    print("-" * 40)
    if dry_run:
        print(f"Dry run complete. Found {deleted_count} files ({total_size / 1024 / 1024:.2f} MB) to delete.")
        print("Run with --actual-delete to perform the deletion.")
    else:
        print(f"Cleanup complete. Deleted {deleted_count} files ({total_size / 1024 / 1024:.2f} MB).")


def main():
    parser = argparse.ArgumentParser(description="Clean up far-field results artifacts.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true", default=True, help="Preview files to be deleted without removing them (default)")
    group.add_argument("--actual-delete", action="store_false", dest="dry_run", help="Actually delete the files")

    args = parser.parse_args()

    # Base directory relative to this script
    script_dir = Path(__file__).parent.resolve()
    root_dir = script_dir.parent / "results" / "far_field"

    cleanup_far_field(root_dir, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
