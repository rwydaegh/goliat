"""Simulation file cleanup utilities."""

import glob
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..results_extractor import ResultsExtractor


class Cleaner:
    """Manages deletion of simulation files to free disk space.

    Deletes output files, input files, and/or project files based on config.
    Useful for long-running studies where disk space is limited.
    """

    def __init__(self, parent: "ResultsExtractor"):
        """Sets up the cleaner.

        Args:
            parent: Parent ResultsExtractor instance.
        """
        self.parent = parent

    def cleanup_simulation_files(self):
        """Deletes simulation files based on auto_cleanup config.

        Removes files matching specified patterns (output/input H5 files,
        project files). Only runs if cleanup is enabled in config.
        """
        cleanup_types = self.parent.config.get_auto_cleanup_previous_results()
        if not cleanup_types:
            return

        if self.parent.study is None:
            self.parent._log("  - WARNING: Study object is not available. Skipping cleanup.", log_type="warning")
            return

        project_path = self.parent.study.project_manager.project_path
        if not project_path:
            self.parent._log("  - WARNING: Project path is not set. Skipping cleanup.", log_type="warning")
            return
        project_dir = os.path.dirname(project_path)
        project_filename = os.path.basename(project_path)
        results_dir = os.path.join(project_dir, project_filename + "_Results")

        # Map cleanup types to file patterns and directories
        file_patterns = {
            "output": (results_dir, "*_Output.h5", "output"),
            "input": (results_dir, "*_Input.h5", "input"),
            "smash": (project_dir, "*.smash", "project"),
        }

        total_deleted = self._delete_files(cleanup_types, file_patterns)

        if total_deleted > 0:
            self.parent._log(
                f"  - Cleaned up {total_deleted} file(s) to save disk space.",
                level="progress",
                log_type="info",
            )

    def _delete_files(self, cleanup_types: list, file_patterns: dict) -> int:
        """Deletes files matching specified cleanup patterns.

        Args:
            cleanup_types: List of cleanup types to perform (e.g., ['output', 'smash']).
            file_patterns: Dict mapping cleanup types to (dir, pattern, description).

        Returns:
            Total number of files successfully deleted.
        """
        total_deleted = 0

        for cleanup_type in cleanup_types:
            if cleanup_type not in file_patterns:
                continue

            search_dir, pattern, description = file_patterns[cleanup_type]
            file_pattern = os.path.join(search_dir, pattern)
            files_to_delete = glob.glob(file_pattern)

            if files_to_delete:
                for file_path in files_to_delete:
                    if self._delete_single_file(file_path):
                        total_deleted += 1

        return total_deleted

    def _delete_single_file(self, file_path: str) -> bool:
        """Deletes one file and logs success/failure."""
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
