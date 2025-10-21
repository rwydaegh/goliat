"""Simulation file cleanup utilities."""

import glob
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..results_extractor import ResultsExtractor


class Cleaner:
    """Handles cleanup of simulation files to save disk space."""

    def __init__(self, parent: "ResultsExtractor"):
        """Initializes the Cleaner.

        Args:
            parent: The parent ResultsExtractor instance.
        """
        self.parent = parent

    def cleanup_simulation_files(self):
        """Deletes simulation files based on the 'auto_cleanup_previous_results' config.

        This is called after successful extraction to save disk space.
        """
        cleanup_types = self.parent.config.get_auto_cleanup_previous_results()
        if not cleanup_types:
            return

        project_path = self.parent.study.project_manager.project_path
        project_dir = os.path.dirname(project_path)
        project_filename = os.path.basename(project_path)
        results_dir = os.path.join(project_dir, project_filename + "_Results")

        # Map cleanup types to file patterns and directories
        file_patterns = {
            "output": (results_dir, "*_Output.h5", "output"),
            "input": (results_dir, "*_Input.h5", "input"),
            "smash": (project_dir, "*.smash", "project"),
        }

        self.parent._log(
            "--- Starting Auto-Cleanup ---",
            level="progress",
            log_type="header",
        )

        total_deleted = self._delete_files(cleanup_types, file_patterns)

        if total_deleted > 0:
            self.parent._log(
                f"--- Auto-Cleanup Complete: {total_deleted} file(s) deleted. ---",
                level="progress",
                log_type="success",
            )

    def _delete_files(self, cleanup_types: list, file_patterns: dict) -> int:
        """Deletes files based on cleanup types."""
        total_deleted = 0

        for cleanup_type in cleanup_types:
            if cleanup_type not in file_patterns:
                continue

            search_dir, pattern, description = file_patterns[cleanup_type]
            file_pattern = os.path.join(search_dir, pattern)
            files_to_delete = glob.glob(file_pattern)

            if files_to_delete:
                self.parent._log(
                    f"  - Cleaning up {len(files_to_delete)} {description} file(s) ({pattern})...",
                    level="progress",
                    log_type="info",
                )

                for file_path in files_to_delete:
                    if self._delete_single_file(file_path):
                        total_deleted += 1

        return total_deleted

    def _delete_single_file(self, file_path: str) -> bool:
        """Deletes a single file and logs the result."""
        try:
            os.remove(file_path)
            self.parent._log(
                f"    - Deleted: {os.path.basename(file_path)}",
                log_type="verbose",
            )
            return True
        except Exception as e:
            self.parent._log(
                f"    - Warning: Could not delete {os.path.basename(file_path)}: {e}",
                level="progress",
                log_type="warning",
            )
            return False
