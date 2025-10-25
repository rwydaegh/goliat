import hashlib
import json
import os
import json
import hashlib
from typing import TYPE_CHECKING

import h5py
import s4l_v1.model as s4l_model

from .logging_manager import LoggingMixin
from .utils import open_project

if TYPE_CHECKING:
    from logging import Logger

    from .config import Config
    from .gui_manager import QueueGUI


class ProjectCorruptionError(Exception):
    """Custom exception raised for errors related to corrupted or locked project files."""

    pass


class ProjectManager(LoggingMixin):
    """Manages the lifecycle of Sim4Life (.smash) project files.

    Handles creation, opening, saving, and validation of project files,
    ensuring robustness against file corruption and locks.
    """

    def __init__(
        self,
        config: "Config",
        verbose_logger: "Logger",
        progress_logger: "Logger",
        gui: "QueueGUI" = None,
    ):
        """Initializes the ProjectManager.

        Args:
            config: The main configuration object.
            verbose_logger: Logger for detailed output.
            progress_logger: Logger for high-level progress updates.
            gui: The GUI proxy for inter-process communication.
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

    def _generate_config_hash(self, config_dict: dict) -> str:
        """Generates a SHA256 hash for a configuration dictionary."""
        # Serialize the dictionary to a canonical JSON string (sorted keys)
        config_string = json.dumps(config_dict, sort_keys=True)
        return hashlib.sha256(config_string.encode("utf-8")).hexdigest()

    def write_simulation_metadata(self, meta_path: str, surgical_config: dict):
        """Writes a simulation's surgical config and hash to a specified path.

        Args:
            meta_path: The full path to save the metadata file (e.g., .../results/.../config.meta.json).
            surgical_config: The surgical configuration dictionary for the simulation.
        """
        config_hash = self._generate_config_hash(surgical_config)
        metadata = {"config_hash": config_hash, "config_snapshot": surgical_config}

        os.makedirs(os.path.dirname(meta_path), exist_ok=True)
        with open(meta_path, "w") as f:
            json.dump(metadata, f, indent=4)
        self._log(
            f"  - Saved configuration metadata to {os.path.basename(meta_path)}",
            log_type="info",
        )

    def get_far_field_meta_path(
        self,
        phantom_name: str,
        frequency_mhz: int,
        direction_name: str,
        polarization_name: str,
    ) -> str:
        """Constructs the standardized path for a far-field simulation's metadata file."""
        results_dir = os.path.join(
            self.config.base_dir,
            "results",
            "far_field",
            phantom_name.lower(),
            f"{frequency_mhz}MHz",
        )
        # The actual simulation-specific results are in a subdirectory
        sim_specific_dir_name = f"environmental_{direction_name}_{polarization_name}"
        meta_filename = "config.meta.json"
        return os.path.join(results_dir, sim_specific_dir_name, meta_filename)

    def verify_simulation_metadata(self, meta_path: str, surgical_config: dict) -> bool:
        """Verifies if a simulation's metadata file exists and matches the current config.

        Args:
            meta_path: The full path to the metadata file to check.
            surgical_config: The surgical configuration to compare against.

        Returns:
            True if the metadata is valid and matches, False otherwise.
        """
        if not os.path.exists(meta_path):
            self._log(
                f"  - No metadata file found for this simulation at {os.path.basename(meta_path)}. "
                "Verification failed.",
                log_type="info",
            )
            return False

        try:
            with open(meta_path, "r") as f:
                metadata = json.load(f)

            stored_hash = metadata.get("config_hash")
            current_hash = self._generate_config_hash(surgical_config)

            if stored_hash == current_hash:
                self._log(
                    f"  - Configuration hash matches for {os.path.basename(meta_path)}. Simulation is valid.",
                    log_type="success",
                )
                return True
            else:
                self._log(
                    f"  - Configuration hash mismatch for {os.path.basename(meta_path)}. Simulation is outdated.",
                    log_type="warning",
                )
                return False
        except (json.JSONDecodeError, KeyError):
            self._log(
                f"  - Metadata file {os.path.basename(meta_path)} is corrupted. Verification failed.",
                log_type="error",
            )
            return False

    def _is_valid_smash_file(self) -> bool:
        """Checks if the project file is a valid, unlocked HDF5 file.

        Performs two checks:
        1. Attempts to rename the file to itself to detect file locks.
        2. Uses `h5py` to verify the file's HDF5 structure.

        Returns:
            True if the file is valid and not locked, False otherwise.
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

    def create_or_open_project(
        self,
        phantom_name: str,
        frequency_mhz: int,
        scenario_name: str = None,
        position_name: str = None,
        orientation_name: str = None,
        **kwargs,
    ) -> bool:
        """Creates a new project or opens an existing one based on the 'do_setup' flag.

        Args:
            phantom_name: The name of the phantom model.
            frequency_mhz: The simulation frequency in MHz.
            scenario_name: The base name of the placement scenario.
            position_name: The name of the position within the scenario.
            orientation_name: The name of the orientation within the scenario.

        Raises:
            ValueError: If required parameters are missing or `study_type` is unknown.
            FileNotFoundError: If `do_setup` is false and the project file does not exist.
            ProjectCorruptionError: If the project file is corrupted.
        """
        study_type = self.config.get_setting("study_type")
        if not study_type:
            raise ValueError("'study_type' not found in the configuration file.")

        if study_type == "near_field":
            if not all(
                [
                    phantom_name,
                    frequency_mhz,
                    scenario_name,
                    position_name,
                    orientation_name,
                ]
            ):
                raise ValueError(
                    "For near-field studies, all placement parameters are required."
                )
            placement_name = f"{scenario_name}_{position_name}_{orientation_name}"
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

        # For far-field, direction and polarization are part of the unique signature,
        # but they are not used in the file path, so we retrieve them from the setup logic if needed.
        # This is a bit of a workaround but keeps the project manager's interface clean.
        direction_name = None
        polarization_name = None
        if study_type == "far_field":
            # This part is tricky as the project manager doesn't inherently know about direction/polarization.
            # However, for the hash to be unique per simulation, we need it.
            # We will assume for now that the calling context (the study) will handle this.
            # Let's pass None for now and see if we need to refactor the study to provide it.
            pass

        surgical_config = self.config.build_simulation_config(
            phantom_name=phantom_name,
            frequency_mhz=frequency_mhz,
            scenario_name=scenario_name,
            position_name=position_name,
            orientation_name=orientation_name,
            direction_name=direction_name,
            polarization_name=polarization_name,
        )

        if do_setup:
            # For near-field, the logic is simple: one project, one metadata file.
            if study_type == "near_field":
                project_is_valid = self.verify_simulation_metadata(
                    self.project_path + ".meta.json", surgical_config
                )
                if project_is_valid:
                    self._log(
                        "Verified existing project. Skipping setup.", log_type="info"
                    )
                    self.open()
                    return False  # Indicate setup is not needed
                else:
                    self._log(
                        "Existing project is invalid or out of date. Creating new project.",
                        log_type="info",
                    )
                    self.create_new()
                    # After a successful setup, write the metadata
                    self.write_simulation_metadata(
                        self.project_path + ".meta.json", surgical_config
                    )
                    return True  # Indicate setup was performed

            # For far-field, the study class handles per-simulation verification.
            # This method just ensures the main project file exists.
            elif study_type == "far_field":
                # The decision to create a new project is delegated to the study,
                # which checks if a rebuild is needed.
                needs_rebuild = kwargs.get("needs_project_rebuild", True)
                if needs_rebuild and os.path.exists(self.project_path):
                    self._log(
                        "One or more simulations are outdated. Rebuilding project file.",
                        log_type="info",
                    )
                    self.create_new()
                elif not os.path.exists(self.project_path):
                    self._log(
                        "Project file does not exist. Creating new project.",
                        log_type="info",
                    )
                    self.create_new()
                else:
                    self._log(
                        "Project file exists and no rebuild is required. Opening.",
                        log_type="info",
                    )
                    self.open()
                return True  # Always return True for setup phase, study will skip sims internally

        # Logic for do_setup = False remains the same
        self._log(
            "Execution control: 'do_setup' is false. Opening existing project without verification.",
            log_type="info",
        )
        if not os.path.exists(self.project_path):
            error_msg = (
                f"ERROR: 'do_setup' is false, but project file not found at {self.project_path}. "
                "Cannot proceed."
            )
            self._log(error_msg, log_type="fatal")
            raise FileNotFoundError(error_msg)

        self.open()
        return False

    def create_new(self):
        """Creates a new, empty project in memory.

        Closes any open document, deletes the existing project file and its
        cache, then creates a new unsaved project.
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
        """Opens an existing project after performing validation checks.

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
        """Saves the currently active project to its designated file path.

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
        """Closes any open project."""
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
