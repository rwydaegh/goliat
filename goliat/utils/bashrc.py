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
            # Preserve AX_USE_UNSUPPORTED_CARDS even if it's in GOLIAT section
            if in_goliat_section and "AX_USE_UNSUPPORTED_CARDS" in line:
                new_lines.append(line)
                continue
            # Preserve PYTHONIOENCODING even if it's in GOLIAT section
            if in_goliat_section and "PYTHONIOENCODING" in line:
                new_lines.append(line)
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

        # Ensure ~/.bash_profile sources ~/.bashrc (Git Bash/MINGW64 compatibility)
        _ensure_bash_profile_sources_bashrc()

        logging.info("Synced .bashrc to ~/.bashrc (preference enabled)")
    except Exception as e:
        logging.warning(f"Could not sync .bashrc to home directory: {e}")


def _ensure_bash_profile_sources_bashrc():
    """Ensure ~/.bash_profile sources ~/.bashrc.

    Git Bash/MINGW64 on Windows reads ~/.bash_profile but not ~/.bashrc by default.
    This adds the standard sourcing snippet if not already present.
    """
    bash_profile = os.path.join(os.path.expanduser("~"), ".bash_profile")
    source_snippet = """
# Source ~/.bashrc if it exists
if [ -f ~/.bashrc ]; then
    source ~/.bashrc
fi
"""

    try:
        existing_content = ""
        if os.path.exists(bash_profile):
            with open(bash_profile, "r", encoding="utf-8") as f:
                existing_content = f.read()

        # Check if already sourcing .bashrc
        if "source ~/.bashrc" in existing_content or ". ~/.bashrc" in existing_content:
            return  # Already configured

        # Append the sourcing snippet
        with open(bash_profile, "a", encoding="utf-8") as f:
            f.write(source_snippet)

        logging.info("Updated ~/.bash_profile to source ~/.bashrc")
    except Exception as e:
        logging.warning(f"Could not update ~/.bash_profile: {e}")


def update_bashrc(selected_python_path, base_dir=None):
    """
    Creates/updates a project-local .bashrc file with PATH entries for Sim4Life Python.

    This creates a .bashrc file in the project directory (non-intrusive).
    If base_dir is provided and user preference is set, also syncs to ~/.bashrc.

    Preserves existing content that is not Sim4Life PATH related, including
    AX_USE_UNSUPPORTED_CARDS and other custom environment variables.
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

    # Read existing content to preserve non-Sim4Life lines
    preserved_lines = []  # Lines to preserve (comments, non-Sim4Life exports, etc.)
    preserved_vars = {}  # Track preserved environment variables
    has_ax_unsupported = False
    has_pythonioencoding = False

    if os.path.exists(bashrc_path):
        try:
            with open(bashrc_path, "r", encoding="utf-8") as f:
                all_lines = f.readlines()

            # Parse existing content and preserve non-Sim4Life PATH lines
            for line in all_lines:
                stripped = line.strip()
                # Skip Sim4Life PATH lines (will be replaced)
                if stripped.startswith("export PATH") and "Sim4Life" in line:
                    continue
                # Preserve AX_USE_UNSUPPORTED_CARDS
                if "AX_USE_UNSUPPORTED_CARDS" in line:
                    has_ax_unsupported = True
                    preserved_vars["AX_USE_UNSUPPORTED_CARDS"] = line.rstrip("\n")
                    continue
                # Preserve PYTHONIOENCODING
                if "PYTHONIOENCODING" in line:
                    has_pythonioencoding = True
                    preserved_vars["PYTHONIOENCODING"] = line.rstrip("\n")
                    continue
                # Preserve other export statements that aren't Sim4Life PATH
                if stripped.startswith("export ") and "PATH" not in line:
                    var_name = stripped.split("=")[0].replace("export ", "").strip()
                    if var_name:
                        preserved_vars[var_name] = line.rstrip("\n")
                        continue
                # Preserve comments and other non-export lines
                preserved_lines.append(line.rstrip("\n"))
        except Exception as e:
            logging.warning(f"Could not read existing .bashrc: {e}")

    # Build new content
    new_lines = []

    # Add preserved non-export lines first
    new_lines.extend(preserved_lines)

    # Add Sim4Life PATH lines
    new_lines.append(python_line.rstrip("\n"))
    new_lines.append(scripts_line.rstrip("\n"))

    # Add AX_USE_UNSUPPORTED_CARDS if not already present
    if not has_ax_unsupported:
        new_lines.append("export AX_USE_UNSUPPORTED_CARDS=1")
    elif "AX_USE_UNSUPPORTED_CARDS" in preserved_vars:
        new_lines.append(preserved_vars["AX_USE_UNSUPPORTED_CARDS"])

    # Add PYTHONIOENCODING if not already present (fixes Unicode on older Windows)
    if not has_pythonioencoding:
        new_lines.append("export PYTHONIOENCODING=utf-8")
    elif "PYTHONIOENCODING" in preserved_vars:
        new_lines.append(preserved_vars["PYTHONIOENCODING"])

    # Add other preserved environment variables
    for var_name, var_line in preserved_vars.items():
        if var_name not in ("AX_USE_UNSUPPORTED_CARDS", "PYTHONIOENCODING"):
            new_lines.append(var_line)

    # Write the updated content
    with open(bashrc_path, "w", encoding="utf-8") as f:
        f.write("\n".join(new_lines))
        if new_lines:  # Add trailing newline if file has content
            f.write("\n")

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
    print("  PRO: Sim4Life Python will be available automatically in ALL new bash windows")
    print("  PRO: You won't need to remember to run 'source .bashrc' each time")
    print("  CON: This modifies your global bash configuration")
    print()
    print("OPTION 2 (Default):")
    print("  Keep using the project-local .bashrc file")
    print("  PRO: Non-intrusive - doesn't modify your global bash config")
    print("  CON: You must run 'source .bashrc' each time you open a new bash terminal")
    print("       (or navigate to the project directory and source it)")
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
            print("\nNote: Sim4Life Python paths already found in ~/.bashrc")
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

            print("\nDone! Copied .bashrc configuration to ~/.bashrc")
            print("  New bash windows will automatically have Sim4Life Python in PATH.")
            print("  You can remove these lines from ~/.bashrc anytime if needed.")
            print("  This preference will be remembered - future .bashrc updates will sync automatically.")

            # Save preference
            prefs = get_user_preferences(base_dir)
            prefs["sync_bashrc_to_home"] = True
            save_user_preferences(base_dir, prefs)
        except Exception as e:
            logging.error(f"Failed to write to ~/.bashrc: {e}")
            print(f"\nError: Could not write to ~/.bashrc: {e}")
            print("  You can manually copy the content from .bashrc to ~/.bashrc if desired.")
    else:
        print("\nOK, keeping project-local .bashrc")
        print("  Remember to run 'source .bashrc' when opening new bash terminals,")
        print("  or navigate to the project directory first.")
        print("  You can manually copy .bashrc to ~/.bashrc later if desired.")
        print("  You can edit data/.goliat_preferences.json to enable auto-sync later.")

        # Save preference as False
        prefs = get_user_preferences(base_dir)
        prefs["sync_bashrc_to_home"] = False
        save_user_preferences(base_dir, prefs)
