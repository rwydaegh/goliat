"""Bashrc configuration management.

This module handles creating and updating .bashrc files for Sim4Life Python PATH configuration.
"""

import logging
import os

from .preferences import get_user_preferences, save_user_preferences


def sync_bashrc_to_home(base_dir):
    """Sync project .bashrc to home directory if preference is enabled."""
    project_bashrc = os.path.join(base_dir, ".bashrc")
    home_bashrc = os.path.join(os.path.expanduser("~"), ".bashrc")

    if not os.path.exists(project_bashrc):
        return

    try:
        with open(project_bashrc, "r", encoding="utf-8") as f:
            bashrc_content = f.read()

        # Read existing home .bashrc
        existing_content = ""
        if os.path.exists(home_bashrc):
            with open(home_bashrc, "r", encoding="utf-8") as f:
                existing_content = f.read()

        # Remove old GOLIAT entries if they exist
        lines = existing_content.split("\n")
        new_lines = []
        in_goliat_section = False
        for line in lines:
            if "# GOLIAT: Sim4Life Python PATH" in line:
                in_goliat_section = True
                continue
            if in_goliat_section and (line.startswith("export PATH") and "Sim4Life" in line):
                continue
            if in_goliat_section and line.strip() == "" and new_lines and new_lines[-1].strip() == "":
                in_goliat_section = False
                continue
            if not in_goliat_section:
                new_lines.append(line)

        # Remove trailing empty lines
        while new_lines and new_lines[-1].strip() == "":
            new_lines.pop()

        # Append new content
        new_content = "\n".join(new_lines)
        if new_content and not new_content.endswith("\n"):
            new_content += "\n"
        new_content += "\n# GOLIAT: Sim4Life Python PATH (auto-synced)\n"
        new_content += bashrc_content

        with open(home_bashrc, "w", encoding="utf-8") as f:
            f.write(new_content)

        logging.info("Synced .bashrc to ~/.bashrc (preference enabled)")
    except Exception as e:
        logging.warning(f"Could not sync .bashrc to home directory: {e}")


def update_bashrc(selected_python_path, base_dir=None):
    """
    Creates/updates a project-local .bashrc file with PATH entries for Sim4Life Python.

    This creates a .bashrc file in the project directory (non-intrusive).
    If base_dir is provided and user preference is set, also syncs to ~/.bashrc.
    """
    bashrc_path = os.path.join(os.getcwd(), ".bashrc")

    # Strip any existing quotes from the input path
    selected_python_path = selected_python_path.strip().strip('"').strip("'")

    # Prepare the new path lines
    drive, path_rest = os.path.splitdrive(selected_python_path)
    # On Linux, os.path.splitdrive may not split Windows paths correctly
    # If drive is empty, extract it manually from the path
    if not drive and path_rest:
        # Check if path starts with a drive letter (e.g., "C:\...")
        if len(path_rest) >= 2 and path_rest[1] == ":":
            drive = path_rest[0:2]  # Get "C:"
            path_rest = path_rest[2:]  # Get rest after "C:"

    # Replace backslashes with forward slashes (works on both Windows and Linux)
    path_rest_normalized = path_rest.replace("\\", "/")
    # Remove colon from drive letter (C: -> C) for bash path conversion
    drive_letter = drive.replace(":", "").upper() if drive else ""
    bash_path = f"/{drive_letter}{path_rest_normalized}"

    # Write BOTH Python and Scripts directories to PATH
    # Python directory: for python.exe itself
    python_line = f'export PATH="{bash_path}:$PATH"\n'
    # Scripts directory: for pip-installed executables like goliat.exe
    scripts_line = f'export PATH="{bash_path}/Scripts:$PATH"\n'

    # Overwrite the file with both paths
    with open(bashrc_path, "w") as f:
        f.write(python_line)
        f.write(scripts_line)

    logging.info("'.bashrc' has been updated. Please restart your shell or run 'source .bashrc'.")

    # Check if user wants to sync to home directory
    if base_dir:
        prefs = get_user_preferences(base_dir)
        if prefs.get("sync_bashrc_to_home", False):
            sync_bashrc_to_home(base_dir)


def prompt_copy_bashrc_to_home(base_dir):
    """
    Prompts user if they want to copy project .bashrc to their home directory.
    This makes Sim4Life Python available automatically in all new bash sessions.
    """
    project_bashrc = os.path.join(base_dir, ".bashrc")
    home_bashrc = os.path.join(os.path.expanduser("~"), ".bashrc")

    # Only prompt if project .bashrc exists
    if not os.path.exists(project_bashrc):
        return

    print("\n" + "=" * 80)
    print("Optional: Make Sim4Life Python available automatically")
    print("=" * 80)
    print("GOLIAT has created a .bashrc file in the project directory.")
    print("This file adds Sim4Life Python to your PATH.")
    print()
    print("OPTION 1 (Recommended for beginners):")
    print("  Copy this configuration to your home directory (~/.bashrc)")
    print("  ✓ Sim4Life Python will be available automatically in ALL new bash windows")
    print("  ✓ You won't need to remember to run 'source .bashrc' each time")
    print("  ⚠ This modifies your global bash configuration")
    print()
    print("OPTION 2 (Default):")
    print("  Keep using the project-local .bashrc file")
    print("  ✓ Non-intrusive - doesn't modify your global bash config")
    print("  ⚠ You must run 'source .bashrc' each time you open a new bash terminal")
    print("     (or navigate to the project directory and source it)")
    print()

    response = input("Copy .bashrc to your home directory? [y/N]: ").strip().lower()

    if response in ["y", "yes"]:
        # Read project .bashrc content
        try:
            with open(project_bashrc, "r", encoding="utf-8") as f:
                bashrc_content = f.read()
        except Exception as e:
            logging.warning(f"Could not read project .bashrc: {e}")
            return

        # Check if content already exists in home .bashrc
        existing_content = ""
        if os.path.exists(home_bashrc):
            try:
                with open(home_bashrc, "r", encoding="utf-8") as f:
                    existing_content = f.read()
            except Exception as e:
                logging.warning(f"Could not read existing ~/.bashrc: {e}")

        # Check if Sim4Life paths are already present
        if "Sim4Life" in existing_content or any(
            line.strip() in existing_content for line in bashrc_content.split("\n") if line.strip() and not line.strip().startswith("#")
        ):
            print("\n⚠ Sim4Life Python paths already found in ~/.bashrc")
            overwrite = input("  Do you want to update them? [y/N]: ").strip().lower()
            if overwrite not in ["y", "yes"]:
                print("  Skipped. Using existing ~/.bashrc configuration.")
                return

        # Append to home .bashrc (or create if doesn't exist)
        try:
            with open(home_bashrc, "a", encoding="utf-8") as f:
                f.write("\n# GOLIAT: Sim4Life Python PATH (added automatically)\n")
                f.write(bashrc_content)
                f.write("\n")

            print("\n✓ Copied .bashrc configuration to ~/.bashrc")
            print("  New bash windows will automatically have Sim4Life Python in PATH.")
            print("  You can remove these lines from ~/.bashrc anytime if needed.")
            print("  This preference will be remembered - future .bashrc updates will sync automatically.")

            # Save preference
            prefs = get_user_preferences(base_dir)
            prefs["sync_bashrc_to_home"] = True
            save_user_preferences(base_dir, prefs)
        except Exception as e:
            logging.error(f"Failed to write to ~/.bashrc: {e}")
            print(f"\n⚠ Could not write to ~/.bashrc: {e}")
            print("  You can manually copy the content from .bashrc to ~/.bashrc if desired.")
    else:
        print("\n✓ Keeping project-local .bashrc")
        print("  Remember to run 'source .bashrc' when opening new bash terminals,")
        print("  or navigate to the project directory first.")
        print("  You can manually copy .bashrc to ~/.bashrc later if desired.")
        print("  You can edit data/.goliat_preferences.json to enable auto-sync later.")

        # Save preference as False
        prefs = get_user_preferences(base_dir)
        prefs["sync_bashrc_to_home"] = False
        save_user_preferences(base_dir, prefs)
