import os
import h5py
import logging
from .utils import open_project
from .logging_manager import LoggingMixin

class ProjectCorruptionError(Exception):
    """Custom exception for corrupted project files."""
    pass

class ProjectManager(LoggingMixin):
    """
    Handles the lifecycle of the .smash project file.
    """
    def __init__(self, config, verbose_logger, progress_logger, gui=None):
        self.config = config
        self.verbose_logger = verbose_logger
        self.progress_logger = progress_logger
        self.gui = gui
        import s4l_v1.document
        self.document = s4l_v1.document
        self.project_path = None
        self.execution_control = self.config.get_setting('execution_control', {'do_setup': True, 'do_run': True, 'do_extract': True})


    def _is_valid_smash_file(self):
        """
        Checks if the project file is valid and not locked.
        It first tries to rename the file to itself to check for a lock,
        then uses h5py to check for basic HDF5 format corruption.
        """
        if not self.project_path:
            return False
        # Lock files can exist, preventing a check. If a lock file for the project exists,
        # we can reasonably assume the file is locked and avoid the check.
        lock_file_path = os.path.join(os.path.dirname(self.project_path), f".{os.path.basename(self.project_path)}.s4l_lock")
        if os.path.exists(lock_file_path):
            self._log(f"  - Lock file detected: {lock_file_path}. Assuming project is in use.")
            return False

        try:
            # 1. Check for file lock by trying to rename. This is a common Windows trick.
            os.rename(self.project_path, self.project_path)
        except OSError as e:
            self._log(f"  - File lock detected on {self.project_path}: {e}")
            self._log(f"  - The file is likely being used by another process. Skipping.")
            return False

        try:
            # 2. Check for HDF5 format corruption.
            with h5py.File(self.project_path, 'r') as f:
                pass
            return True
        except OSError as e:
            self._log(f"  - HDF5 format error in {self.project_path}: {e}")
            return False

    def create_or_open_project(self, phantom_name, frequency_mhz, placement_name=None):
        """
        Creates or opens a project based on the 'do_setup' execution control flag.
        """
        # Determine study type from the config filename
        if "near_field" in os.path.basename(self.config.config_path):
            study_dir = 'near_field'
            if not all([phantom_name, frequency_mhz, placement_name]):
                raise ValueError("For near-field studies, phantom_name, frequency_mhz, and placement_name are required.")
            
            project_dir = os.path.join(self.config.base_dir, 'results', study_dir, phantom_name.lower(), f"{frequency_mhz}MHz", placement_name)
            project_filename = f"near_field_{phantom_name.lower()}_{frequency_mhz}MHz_{placement_name}.smash"

        else:  # far_field
            study_dir = 'far_field'
            project_dir = os.path.join(self.config.base_dir, 'results', study_dir, phantom_name.lower(), f"{frequency_mhz}MHz")
            project_filename = f"far_field_{phantom_name.lower()}_{frequency_mhz}MHz.smash"

        os.makedirs(project_dir, exist_ok=True)
        # Ensure path uses forward slashes for Sim4Life compatibility
        self.project_path = os.path.join(project_dir, project_filename).replace('\\', '/')
        self._log(f"Project path set to: {self.project_path}")

        do_setup = self.execution_control.get('do_setup', True)

        if do_setup:
            self._log("Execution control: 'do_setup' is true. Creating a new project.")
            self.create_new()
            self.save()
        else:
            self._log("Execution control: 'do_setup' is false. Attempting to open existing project.")
            if not os.path.exists(self.project_path):
                # If the primary path doesn't exist, check for the old "thelonius" naming convention.
                old_project_path = self.project_path.replace("thelonious", "thelonius")
                if os.path.exists(old_project_path):
                    self._log(f"Project not found at primary path, but found with old 'thelonius' naming: {old_project_path}")
                    self.project_path = old_project_path
                else:
                    error_msg = f"ERROR: 'do_setup' is false, but project file not found at {self.project_path} or with old naming. Cannot proceed."
                    self._log(error_msg)
                    raise FileNotFoundError(error_msg)
            
            try:
                self.open()
            except ProjectCorruptionError:
                if self.document and hasattr(self.document, 'IsOpen') and self.document.IsOpen():
                    self.document.Close()
                raise  # Re-raise the exception to halt the study

    def create_new(self):
        """
        Creates a new empty project in memory, deleting any existing file.
        The project is not saved to disk until save() is explicitly called.
        """
        # Close any currently open document to release file locks before deleting
        if self.document and hasattr(self.document, 'IsOpen') and self.document.IsOpen():
            self._log("Closing existing document before creating a new one to release file lock.")
            self.document.Close()

        if self.project_path and os.path.exists(self.project_path):
            self._log(f"Deleting existing project file at {self.project_path}")
            os.remove(self.project_path)

            # Also delete associated cache files
            project_dir = os.path.dirname(self.project_path)
            project_filename_base = os.path.basename(self.project_path)
            for item in os.listdir(project_dir):
                # Cache files start with the project name (or a dot) and are not the project itself.
                # e.g. <project>.smash.s4l_cache or .<project>.smash.s4l_lock
                is_cache_file = item.startswith(f".{project_filename_base}") or \
                                (item.startswith(project_filename_base) and item != project_filename_base)
                
                if is_cache_file:
                    item_path = os.path.join(project_dir, item)
                    if os.path.isfile(item_path):
                        self._log(f"Deleting cache file: {item_path}")
                        try:
                            os.remove(item_path)
                        except OSError as e:
                            self._log(f"Error deleting cache file {item_path}: {e}", level='error')
        
        self._log("Creating a new empty project in memory.")
        self.document.New()

    def open(self):
        """
        Opens an existing project after validating it.
        """
        self._log(f"Validating project file: {self.project_path}")
        if not self._is_valid_smash_file():
            self._log(f"ERROR: Project file {self.project_path} is corrupted or locked.")
            raise ProjectCorruptionError(f"File is not a valid or accessible HDF5 file: {self.project_path}")

        self._log(f"Opening project with Sim4Life: {self.project_path}")
        try:
            # The open_project utility calls s4l_v1.document.Open()
            open_project(self.project_path)
        except Exception as e:
            # Catching a broad exception because the underlying Sim4Life error is not specific
            self._log(f"ERROR: Sim4Life failed to open project file, it is likely corrupted: {e}")
            # Close the document if it was partially opened, to release locks
            if self.document and hasattr(self.document, 'IsOpen') and self.document.IsOpen():
                self.document.Close()
            raise ProjectCorruptionError(f"Sim4Life could not open corrupted file: {self.project_path}")

    def save(self):
        """
        Saves the project to its file path using SaveAs.
        """
        if not self.project_path:
            raise ValueError("Project path is not set. Cannot save.")
        
        self._log(f"Saving project to {self.project_path}...")
        self.document.SaveAs(self.project_path)
        self._log("Project saved.")

    def close(self):
        """
        Closes the Sim4Life document.
        """
        self._log("Closing project document...")
        self.document.Close()

    def cleanup(self):
        """
        Placeholder for any additional cleanup tasks.
        Currently just closes the project.
        """
        if self.document and hasattr(self.document, 'IsOpen') and self.document.IsOpen():
            self.close()

    def reload_project(self):
        """Saves, closes, and re-opens the project to ensure results are loaded."""
        if self.document and hasattr(self.document, 'IsOpen') and self.document.IsOpen():
            self._log("Saving and reloading project to load results...")
            self.save()
            self.close()
        
        self.open()
        self._log("Project reloaded.")