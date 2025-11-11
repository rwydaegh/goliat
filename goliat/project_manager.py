import hashlib
import json
import os
from datetime import datetime
from typing import TYPE_CHECKING, Optional

import h5py

from .logging_manager import LoggingMixin
from .results_extractor import ResultsExtractor
from .utils import open_project

if TYPE_CHECKING:
    from logging import Logger

    from .config import Config
    from .gui_manager import QueueGUI


class ProjectCorruptionError(Exception):
    """Raised when a project file is corrupted, locked, or inaccessible."""


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
        gui: Optional["QueueGUI"] = None,
        no_cache: bool = False,
    ):
        """Initializes the ProjectManager.

        Args:
            config: The main configuration object.
            verbose_logger: Logger for detailed output.
            progress_logger: Logger for high-level progress updates.
            gui: The GUI proxy for inter-process communication.
            no_cache: If True, bypasses metadata verification.
        """
        self.config = config
        self.verbose_logger = verbose_logger
        self.progress_logger = progress_logger
        self.gui = gui
        self.no_cache = no_cache
        import s4l_v1.document

        self.document = s4l_v1.document
        self.project_path: Optional[str] = None
        self.execution_control = self.config["execution_control"] or {"do_setup": True, "do_run": True, "do_extract": True}

    def _generate_config_hash(self, config_dict: dict) -> str:
        """Creates a SHA256 hash from a config dict for verification."""
        config_string = json.dumps(config_dict, sort_keys=True)
        return hashlib.sha256(config_string.encode("utf-8")).hexdigest()

    def write_simulation_metadata(self, meta_path: str, surgical_config: dict):
        """Writes config metadata and hash to disk for verification/resume.

        Creates a metadata file that tracks the config hash and completion status
        of each phase (setup/run/extract). Used by the verify-and-resume feature.

        Args:
            meta_path: Full path where metadata should be saved.
            surgical_config: The minimal config snapshot for this simulation.
        """
        config_hash = self._generate_config_hash(surgical_config)
        metadata = {
            "config_hash": config_hash,
            "config_snapshot": surgical_config,
            "setup_timestamp": datetime.now().isoformat(),
            "run_done": False,
            "extract_done": False,
        }

        os.makedirs(os.path.dirname(meta_path), exist_ok=True)
        with open(meta_path, "w") as f:
            json.dump(metadata, f, indent=4)
        self._log(
            f"  - Saved configuration metadata to {os.path.basename(meta_path)}",
            log_type="info",
        )

    def update_simulation_metadata(self, meta_path: str, run_done: Optional[bool] = None, extract_done: Optional[bool] = None):
        """Updates phase completion flags in the metadata file.

        Args:
            meta_path: Path to the metadata file.
            run_done: New run phase status.
            extract_done: New extract phase status.
        """
        if not os.path.exists(meta_path):
            self._log(f"Cannot update metadata, file not found: {meta_path}", log_type="warning")
            return

        with open(meta_path, "r+") as f:
            metadata = json.load(f)
            if run_done is not None:
                metadata["run_done"] = run_done
            if extract_done is not None:
                metadata["extract_done"] = extract_done
            f.seek(0)
            json.dump(metadata, f, indent=4)
            f.truncate()
        self._log(f"Updated metadata in {os.path.basename(meta_path)}", log_type="info")

    def _get_deliverables_status(self, project_dir: str, project_filename: str, setup_timestamp: float) -> dict:
        """Checks if simulation deliverables exist and are newer than setup time.

        Validates that both run and extract phases have produced their expected outputs.
        For run phase, looks for _Output.h5 files in the Results directory. For extract
        phase, checks for JSON, PKL, and HTML report files.

        Important safeguards:
        - Only considers H5 files larger than 8MB (iSolve sometimes creates incomplete
          files that are smaller)
        - Files must be newer than setup_timestamp to ensure they're from this run,
          not an old run
        - All extract deliverables must exist (not just some) to mark extract as done

        Args:
            project_dir: Directory containing the project file.
            project_filename: Base name of the project file (without extension).
            setup_timestamp: Timestamp to compare against (setup time in seconds).

        Returns:
            Dict with 'run_done' and 'extract_done' boolean flags.
        """
        status = {"run_done": False, "extract_done": False}

        # Check for run deliverables
        results_dir = os.path.join(project_dir, project_filename + "_Results")
        h5_file_path = None
        if os.path.exists(results_dir):
            output_files = [os.path.join(results_dir, f) for f in os.listdir(results_dir) if f.endswith("_Output.h5")]
            if output_files:
                # Find the latest file based on modification time
                h5_file_path = max(output_files, key=os.path.getmtime)

        # TODO: iSolve somehow still produces small _Output.h5 files. 8 MB limit is arbitrary...
        if h5_file_path and os.path.getsize(h5_file_path) > 8 * 1024 * 1024 and os.path.getmtime(h5_file_path) > setup_timestamp:
            status["run_done"] = True

        # Check for extract deliverables
        deliverable_filenames = ResultsExtractor.get_deliverable_filenames()
        extract_files = [os.path.join(project_dir, filename) for filename in deliverable_filenames.values()]

        # All deliverables must exist and be fresher than the setup timestamp.
        are_all_deliverables_fresh = all(
            os.path.exists(file_path) and os.path.getmtime(file_path) > setup_timestamp for file_path in extract_files
        )

        if are_all_deliverables_fresh:
            status["extract_done"] = True

        return status

    def verify_simulation_metadata(self, meta_path: str, surgical_config: dict, smash_path: Optional[str] = None) -> dict:
        """Verifies if an existing simulation can be reused to skip completed phases.

        This method implements a three-step verification process to determine if a
        previously run simulation can be reused:

        1. Config hash check: Compares the stored config hash with the current config.
           If they don't match, the simulation is outdated and must be rerun.

        2. Project file validation: Checks if the .smash file exists, is not locked,
           and has valid HDF5 structure. If invalid, setup must be rerun.

        3. Deliverable freshness check: Verifies that output files (H5 results) and
           extracted files (JSON/PKL/HTML) exist and are newer than the setup timestamp.
           This ensures we don't skip phases if files are missing or outdated.

        The method returns a dict indicating which phases are complete, allowing the
        study to skip setup/run/extract as appropriate. Note that extract completion
        always requires run completion - if extract is done but run isn't, both are
        marked incomplete to prevent inconsistent states.

        Args:
            meta_path: Path to the metadata file containing config hash and timestamps.
            surgical_config: Current config snapshot to compare against stored hash.
            smash_path: Optional override for project file path (used for verification).

        Returns:
            Dict with boolean flags: 'setup_done', 'run_done', 'extract_done'.
            All False if verification fails at any step.
        """
        status = {"setup_done": False, "run_done": False, "extract_done": False}
        if not os.path.exists(meta_path):
            self._log(f"No metadata file found at {os.path.basename(meta_path)}.", log_type="info")
            return status

        try:
            with open(meta_path, "r") as f:
                metadata = json.load(f)

            stored_hash = metadata.get("config_hash")
            current_hash = self._generate_config_hash(surgical_config)

            if stored_hash != current_hash:
                self._log(f"Config hash mismatch for {os.path.basename(meta_path)}. Simulation is outdated.", log_type="warning")
                return status

            path_to_check = smash_path or self.project_path
            if not path_to_check:
                self._log("Project path not set, cannot verify .smash file.", log_type="error")
                return status

            original_path = self.project_path
            self.project_path = path_to_check
            is_valid = self._is_valid_smash_file()
            self.project_path = original_path

            if not is_valid:
                self._log(f"Project file '{os.path.basename(path_to_check)}' is missing or corrupted.", log_type="warning")
                return status

            status["setup_done"] = True

            setup_timestamp_str = metadata.get("setup_timestamp")
            if not setup_timestamp_str:
                self._log("No setup_timestamp in metadata, cannot verify deliverables.", log_type="warning")
                return status  # Returns all False

            # Convert ISO 8601 string to timestamp
            if isinstance(setup_timestamp_str, str):
                setup_timestamp = datetime.fromisoformat(setup_timestamp_str).timestamp()
            else:
                setup_timestamp = float(setup_timestamp_str)  # Backward compatibility

            project_dir = os.path.dirname(path_to_check)
            project_filename = os.path.basename(path_to_check)
            deliverables_status = self._get_deliverables_status(project_dir, project_filename, setup_timestamp)

            # The final status is determined *only* by the presence of deliverables on the file system.
            # This prevents a situation where metadata claims completion but files are missing.
            status["run_done"] = deliverables_status["run_done"]
            status["extract_done"] = deliverables_status["extract_done"]

            # Extract cannot possible be done if the corresponding run is not done or invalid
            if status["extract_done"] and not status["run_done"]:
                self._log("Extraction was done, but run not. Rerunning both.", log_type="warning")
                status["extract_done"] = False

            status_parts = []
            for key, value in status.items():
                name = key.replace("_done", "").replace("_", " ").title()
                status_text = "done" if value else "NOT done"
                status_parts.append(f"{name} {status_text}")
            status_msg = ", ".join(status_parts)
            self._log(f"Verified existing project. Status: {status_msg}", log_type="success")
            if status["run_done"] and status["extract_done"]:
                self._log("Project already done, skipping.", level="progress", log_type="success")
            return status

        except (json.JSONDecodeError, KeyError):
            self._log(f"Metadata file {os.path.basename(meta_path)} is corrupted.", log_type="error")
            return status

    def get_setup_timestamp_from_metadata(self, meta_path: str) -> Optional[float]:
        """Retrieves the setup timestamp from the metadata file.

        Args:
            meta_path: Path to the metadata file.

        Returns:
            Setup timestamp as a float (seconds since epoch), or None if not found or file doesn't exist.
        """
        if not os.path.exists(meta_path):
            return None

        try:
            with open(meta_path, "r") as f:
                metadata = json.load(f)

            setup_timestamp_str = metadata.get("setup_timestamp")
            if not setup_timestamp_str:
                return None

            # Convert ISO 8601 string to timestamp
            if isinstance(setup_timestamp_str, str):
                return datetime.fromisoformat(setup_timestamp_str).timestamp()
            else:
                return float(setup_timestamp_str)  # Backward compatibility
        except (json.JSONDecodeError, KeyError, ValueError):
            return None

    def _is_valid_smash_file(self) -> bool:
        """Checks if a project file is valid and not locked.

        Performs two checks: file lock detection (via rename test) and HDF5
        structure validation. Returns False if locked or corrupted.

        Returns:
            True if file is valid and accessible, False otherwise.
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
            self._log(f"  - HDF5 format error in {self.project_path}: {e}", log_type="error")
            return False

    def _validate_placement_params(
        self,
        study_type: str,
        phantom_name: str,
        frequency_mhz: int,
        scenario_name: Optional[str],
        position_name: Optional[str],
        orientation_name: Optional[str],
    ) -> None:
        """Validates placement parameters for the given study type.

        Args:
            study_type: The type of study ('near_field' or 'far_field').
            phantom_name: The name of the phantom model.
            frequency_mhz: The simulation frequency in MHz.
            scenario_name: The base name of the placement scenario.
            position_name: The name of the position within the scenario.
            orientation_name: The name of the orientation within the scenario.

        Raises:
            ValueError: If required parameters are missing.
        """
        if not all([phantom_name, frequency_mhz, scenario_name, position_name, orientation_name]):
            raise ValueError(f"For {study_type} studies, all placement parameters are required.")

    def _build_project_path(
        self,
        study_type: str,
        phantom_name: str,
        frequency_mhz: int,
        placement_name: str,
    ) -> tuple[str, str]:
        """Builds project directory and filename paths for the given study type.

        Args:
            study_type: The type of study ('near_field' or 'far_field').
            phantom_name: The name of the phantom model.
            frequency_mhz: The simulation frequency in MHz.
            placement_name: The placement name (scenario_position_orientation).

        Returns:
            Tuple of (project_dir, project_filename).

        Raises:
            ValueError: If study_type is unknown.
        """
        if study_type == "near_field":
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
                placement_name,
            )
            project_filename = f"far_field_{phantom_name.lower()}_{frequency_mhz}MHz_{placement_name}.smash"
        else:
            raise ValueError(f"Unknown study_type '{study_type}' in config.")

        return project_dir, project_filename

    def create_or_open_project(
        self,
        phantom_name: str,
        frequency_mhz: int,
        scenario_name: Optional[str] = None,
        position_name: Optional[str] = None,
        orientation_name: Optional[str] = None,
        **kwargs,
    ) -> dict:
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
        study_type = self.config["study_type"]
        if not study_type or not isinstance(study_type, str):
            raise ValueError("'study_type' not found in the configuration file.")

        # Validate placement parameters
        self._validate_placement_params(study_type, phantom_name, frequency_mhz, scenario_name, position_name, orientation_name)

        # Build placement name and project paths
        placement_name = f"{scenario_name}_{position_name}_{orientation_name}"
        project_dir, project_filename = self._build_project_path(study_type, phantom_name, frequency_mhz, placement_name)

        os.makedirs(project_dir, exist_ok=True)
        self.project_path = os.path.join(project_dir, project_filename).replace("\\", "/")
        self._log(f"Project path set to: {self.project_path}", log_type="info")

        if self.execution_control is None:
            self.execution_control = {}
        do_setup = self.execution_control.get("do_setup", True)

        # For far-field, direction and polarization are part of the unique signature,
        # but they are not used in the file path, so we retrieve them from the setup logic if needed.
        # This is a bit of a workaround but keeps the project manager's interface clean.
        direction_name = None
        polarization_name = None
        if study_type == "far_field":
            # For far-field, the orientation and position names map to direction and polarization
            direction_name = orientation_name
            polarization_name = position_name

        surgical_config = self.config.build_simulation_config(
            phantom_name=phantom_name,
            frequency_mhz=frequency_mhz,
            scenario_name=scenario_name,
            position_name=position_name,
            orientation_name=orientation_name,
            direction_name=direction_name,
            polarization_name=polarization_name,
        )

        if not do_setup:
            self._log(
                "Execution control: 'do_setup' is false. Opening existing project without verification.",
                log_type="info",
            )
            if not self.project_path or not os.path.exists(self.project_path):
                error_msg = f"ERROR: 'do_setup' is false, but project file not found at {self.project_path}. Cannot proceed."
                self._log(error_msg, log_type="fatal")
                raise FileNotFoundError(error_msg)
            self.open()
            # Return a status dict indicating setup is done, but we don't know about the other phases.
            return {"setup_done": True, "run_done": False, "extract_done": False}

        # If do_setup is true, we verify the project unless --no-cache is used.
        if self.no_cache:
            self._log("`--no-cache` flag is active. Forcing a new setup by skipping verification.", log_type="warning")
            return {"setup_done": False, "run_done": False, "extract_done": False}

        verification_status = self.verify_simulation_metadata(os.path.join(project_dir, "config.json"), surgical_config)

        if verification_status["setup_done"]:
            self._log("Verified existing project. Opening.", log_type="info")
            self.open()
            return verification_status

        if os.path.exists(project_dir):
            self._log("Existing project is invalid or out of date. A new setup is required.", log_type="info")
        return {"setup_done": False, "run_done": False, "extract_done": False}

    def create_new(self):
        """Creates a new empty project in memory.

        Closes any open document, deletes existing project file and cache files,
        then creates a fresh unsaved project. Also initializes the model by
        creating/deleting a dummy block to ensure Sim4Life is ready.
        """
        if self.document and hasattr(self.document, "IsOpen") and self.document.IsOpen():  # type: ignore
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
                    item.startswith(project_filename_base) and item != project_filename_base
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
        import s4l_v1.model as s4l_model

        dummy_block = s4l_model.CreateSolidBlock(s4l_model.Vec3(0, 0, 0), s4l_model.Vec3(1, 1, 1))
        dummy_block.Delete()
        self._log("Model initialized, ready for population.", log_type="verbose")

    def open(self):
        """Opens an existing project after validation checks.

        Raises:
            ProjectCorruptionError: If project file is invalid, locked, or
                                    Sim4Life can't open it.
        """
        self._log(f"Validating project file: {self.project_path}", log_type="info")
        if not self._is_valid_smash_file():
            self._log(
                f"ERROR: Project file {self.project_path} is corrupted or locked.",
                log_type="fatal",
            )
            raise ProjectCorruptionError(f"File is not a valid or accessible HDF5 file: {self.project_path}")

        self._log(f"Opening project with Sim4Life: {self.project_path}", log_type="info")
        try:
            if self.project_path:
                open_project(self.project_path)
        except Exception as e:
            self._log(
                f"ERROR: Sim4Life failed to open project file, it is likely corrupted: {e}",
                log_type="fatal",
            )
            if self.document and hasattr(self.document, "IsOpen") and self.document.IsOpen():  # type: ignore
                self.document.Close()
            raise ProjectCorruptionError(f"Sim4Life could not open corrupted file: {self.project_path}")

    def save(self):
        """Saves the current project to its file path.

        Retries the save operation up to N times (configurable via save_retry_count)
        if Sim4Life randomly errors out. Logs warnings for each retry attempt.

        Raises:
            ValueError: If project_path hasn't been set.
            Exception: If all retry attempts fail, the last exception is raised.
        """
        if not self.project_path:
            raise ValueError("Project path is not set. Cannot save.")

        retry_count = self.config["save_retry_count"]
        if retry_count is None:
            retry_count = 4
        if not isinstance(retry_count, int):
            retry_count = 4
        last_exception = None

        self._log(f"Saving project to {self.project_path}...", log_type="info")

        for attempt in range(1, retry_count + 1):
            try:
                self.document.SaveAs(self.project_path)
                if attempt > 1:
                    self._log(f"Project saved successfully on attempt {attempt}.", log_type="success")
                else:
                    self._log("Project saved.", log_type="success")
                return
            except Exception as e:
                last_exception = e
                if attempt < retry_count:
                    self._log(
                        f"WARNING: Save attempt {attempt} failed: {e}. Retrying ({attempt + 1}/{retry_count})...",
                        log_type="warning",
                    )
                else:
                    self._log(
                        f"ERROR: All {retry_count} save attempts failed. Last error: {e}",
                        log_type="error",
                    )

        # If we get here, all attempts failed
        if last_exception is not None:
            raise last_exception
        raise RuntimeError("Save failed but no exception was captured")

    def close(self):
        """Closes the active Sim4Life document."""
        self._log("Closing project document...", log_type="info")
        self.document.Close()

    def cleanup(self):
        """Closes any open project."""
        if self.document and hasattr(self.document, "IsOpen") and self.document.IsOpen():  # type: ignore
            self.close()

    def reload_project(self):
        """Saves, closes, and reopens the project to load simulation results.

        Needed because Sim4Life sometimes requires a reload to see new results
        files. This ensures results are available for extraction.
        """
        if self.document and hasattr(self.document, "IsOpen") and self.document.IsOpen():  # type: ignore
            self._log("Saving and reloading project to load results...", log_type="info")
            self.save()
            self.close()

        self.open()
        self._log("Project reloaded.", log_type="success")
