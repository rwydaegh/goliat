import os

import h5py
import s4l_v1.model as s4l_model

from .logging_manager import LoggingMixin
from .utils import open_project


class ProjectCorruptionError(Exception):
    """Custom exception raised for errors related to corrupted or locked project files."""

    pass


class ProjectManager(LoggingMixin):
    """
    Manages the lifecycle of Sim4Life (.smash) project files.

    This class handles the creation, opening, saving, and validation of
    project files, ensuring robustness against file corruption and locks.
    """

    def __init__(self, config, verbose_logger, progress_logger, gui=None):
        """
        Initializes the ProjectManager.

        Args:
            config (Config): The main configuration object.
            verbose_logger (logging.Logger): Logger for detailed output.
            progress_logger (logging.Logger): Logger for high-level progress updates.
            gui (QueueGUI, optional): The GUI proxy for inter-process communication.
        """
        self.config = config
        self.verbose_logger = verbose_logger
        self.progress_logger = progress_logger
        self.gui = gui
        import s4l_v1.document

        self.document = s4l_v1.document
        self.project_path = None
        self.execution_control = self.config.get_setting(
            "execution_control", {"do_setup": True, "do_run": True, "do_extract": True}
        )

    def _is_valid_smash_file(self):
        """
        Checks if the project file is a valid, unlocked HDF5 file.

        This method performs two checks:
        1.  It attempts to rename the file to itself as a proxy for detecting file locks.
        2.  It uses `h5py` to verify the file's basic HDF5 structure.

        Returns:
            bool: True if the file is valid and not locked, False otherwise.
        """
        if not self.project_path:
            return False
        lock_file_path = os.path.join(
            os.path.dirname(self.project_path),
            f".{os.path.basename(self.project_path)}.s4l_lock",
        )
        if os.path.exists(lock_file_path):
            self._log(
                f"  - Lock file detected: {lock_file_path}. Assuming project is in use.",
                log_type="warning",
            )
            return False

        try:
            os.rename(self.project_path, self.project_path)
        except OSError as e:
            self._log(
                f"  - File lock detected on {self.project_path}: {e}",
                log_type="warning",
            )
            self._log(
                "  - The file is likely being used by another process. Skipping.",
                log_type="warning",
            )
            return False

        try:
            with h5py.File(self.project_path, "r"):
                pass
            return True
        except OSError as e:
            self._log(
                f"  - HDF5 format error in {self.project_path}: {e}", log_type="error"
            )
            return False

    def create_or_open_project(self, phantom_name, frequency_mhz, placement_name=None):
        """
        Creates a new project or opens an existing one based on the 'do_setup' flag.

        Args:
            phantom_name (str): The name of the phantom model.
            frequency_mhz (int): The simulation frequency in MHz.
            placement_name (str, optional): The name of the placement scenario.

        Raises:
            ValueError: If required parameters are missing or `study_type` is unknown.
            FileNotFoundError: If `do_setup` is false and the project file does not exist.
            ProjectCorruptionError: If the project file is found to be corrupted.
        """
        study_type = self.config.get_setting("study_type")
        if not study_type:
            raise ValueError("'study_type' not found in the configuration file.")

        if study_type == "near_field":
            if not all([phantom_name, frequency_mhz, placement_name]):
                raise ValueError(
                    "For near-field studies, phantom_name, frequency_mhz, and placement_name are required."
                )

            project_dir = os.path.join(
                self.config.base_dir,
                "results",
                "near_field",
                phantom_name.lower(),
                f"{frequency_mhz}MHz",
                placement_name,
            )
            project_filename = f"near_field_{phantom_name.lower()}_{frequency_mhz}MHz_{placement_name}.smash"

        elif study_type == "far_field":
            project_dir = os.path.join(
                self.config.base_dir,
                "results",
                "far_field",
                phantom_name.lower(),
                f"{frequency_mhz}MHz",
            )
            project_filename = (
                f"far_field_{phantom_name.lower()}_{frequency_mhz}MHz.smash"
            )

        else:
            raise ValueError(f"Unknown study_type '{study_type}' in config.")

        os.makedirs(project_dir, exist_ok=True)
        self.project_path = os.path.join(project_dir, project_filename).replace(
            "\\", "/"
        )
        self._log(f"Project path set to: {self.project_path}", log_type="info")

        do_setup = self.execution_control.get("do_setup", True)

        if do_setup:
            self._log(
                "Execution control: 'do_setup' is true. Creating a new project.",
                log_type="info",
            )
            self.create_new()
        else:
            self._log(
                "Execution control: 'do_setup' is false. Attempting to open existing project.",
                log_type="info",
            )
            if not os.path.exists(self.project_path):
                old_project_path = self.project_path.replace("thelonious", "thelonius")
                if os.path.exists(old_project_path):
                    self._log(
                        f"Project not found at primary path, but found with old 'thelonius' naming: {old_project_path}",
                        log_type="warning",
                    )
                    self.project_path = old_project_path
                else:
                    error_msg = (
                        f"ERROR: 'do_setup' is false, but project file not found at {self.project_path} "
                        f"or with old naming. Cannot proceed."
                    )
                    self._log(error_msg, log_type="fatal")
                    raise FileNotFoundError(error_msg)

            try:
                self.open()
            except ProjectCorruptionError:
                if (
                    self.document
                    and hasattr(self.document, "IsOpen")
                    and self.document.IsOpen()
                ):
                    self.document.Close()
                raise

    def create_new(self):
        """
        Creates a new, empty project in memory.

        This method first closes any open document to release file locks, then
        deletes the existing project file and its associated cache files.
        Finally, it creates a new, unsaved project in memory.
        """
        if (
            self.document
            and hasattr(self.document, "IsOpen")
            and self.document.IsOpen()
        ):
            self._log(
                "Closing existing document before creating a new one to release file lock.",
                log_type="info",
            )
            self.document.Close()

        if self.project_path and os.path.exists(self.project_path):
            self._log(
                f"Deleting existing project file at {self.project_path}",
                log_type="warning",
            )
            os.remove(self.project_path)

            project_dir = os.path.dirname(self.project_path)
            project_filename_base = os.path.basename(self.project_path)
            for item in os.listdir(project_dir):
                is_cache_file = item.startswith(f".{project_filename_base}") or (
                    item.startswith(project_filename_base)
                    and item != project_filename_base
                )

                if is_cache_file:
                    item_path = os.path.join(project_dir, item)
                    if os.path.isfile(item_path):
                        self._log(f"Deleting cache file: {item_path}", log_type="info")
                        try:
                            os.remove(item_path)
                        except OSError as e:
                            self._log(
                                f"Error deleting cache file {item_path}: {e}",
                                log_type="error",
                            )

        self._log("Creating a new empty project in memory.", log_type="info")
        self.document.New()

        self._log(
            "Initializing model by creating and deleting a dummy block...",
            log_type="verbose",
        )
        dummy_block = s4l_model.CreateSolidBlock(
            s4l_model.Vec3(0, 0, 0), s4l_model.Vec3(1, 1, 1)
        )
        dummy_block.Delete()
        self._log("Model initialized, ready for population.", log_type="verbose")

    def open(self):
        """
        Opens an existing project after performing validation checks.

        Raises:
            ProjectCorruptionError: If the project file is invalid, locked, or
                                    cannot be opened by Sim4Life.
        """
        self._log(f"Validating project file: {self.project_path}", log_type="info")
        if not self._is_valid_smash_file():
            self._log(
                f"ERROR: Project file {self.project_path} is corrupted or locked.",
                log_type="fatal",
            )
            raise ProjectCorruptionError(
                f"File is not a valid or accessible HDF5 file: {self.project_path}"
            )

        self._log(
            f"Opening project with Sim4Life: {self.project_path}", log_type="info"
        )
        try:
            open_project(self.project_path)
        except Exception as e:
            self._log(
                f"ERROR: Sim4Life failed to open project file, it is likely corrupted: {e}",
                log_type="fatal",
            )
            if (
                self.document
                and hasattr(self.document, "IsOpen")
                and self.document.IsOpen()
            ):
                self.document.Close()
            raise ProjectCorruptionError(
                f"Sim4Life could not open corrupted file: {self.project_path}"
            )

    def save(self):
        """
        Saves the currently active project to its designated file path.

        Raises:
            ValueError: If the project path has not been set.
        """
        if not self.project_path:
            raise ValueError("Project path is not set. Cannot save.")

        self._log(f"Saving project to {self.project_path}...", log_type="info")
        self.document.SaveAs(self.project_path)
        self._log("Project saved.", log_type="success")

    def close(self):
        """Closes the currently active Sim4Life document."""
        self._log("Closing project document...", log_type="info")
        self.document.Close()

    def cleanup(self):
        """Performs cleanup operations, such as closing any open project."""
        if (
            self.document
            and hasattr(self.document, "IsOpen")
            and self.document.IsOpen()
        ):
            self.close()

    def reload_project(self):
        """Saves, closes, and re-opens the project to load simulation results."""
        if (
            self.document
            and hasattr(self.document, "IsOpen")
            and self.document.IsOpen()
        ):
            self._log(
                "Saving and reloading project to load results...", log_type="info"
            )
            self.save()
            self.close()

        self.open()
        self._log("Project reloaded.", log_type="success")
