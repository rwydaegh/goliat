import os
from typing import TYPE_CHECKING

from .base_setup import BaseSetup

if TYPE_CHECKING:
    from logging import Logger

    from ..config import Config


class PhantomSetup(BaseSetup):
    """Handles loading and importing phantom models into Sim4Life."""

    def __init__(
        self,
        config: "Config",
        phantom_name: str,
        verbose_logger: "Logger",
        progress_logger: "Logger",
    ):
        super().__init__(config, verbose_logger, progress_logger)
        self.phantom_name = phantom_name

        import s4l_v1.data
        import s4l_v1.model
        import XCoreModeling

        self.model = s4l_v1.model
        self.data = s4l_v1.data
        self.XCoreModeling = XCoreModeling

    def _log(self, message: str, level: str = "verbose", log_type: str = "default"):
        super()._log(message, level, log_type)

    def ensure_phantom_is_loaded(self) -> bool:
        """Checks if phantom is loaded, imports from disk if available, or downloads if missing.

        Returns:
            True if phantom is now loaded, False if download was initiated (requires re-run).
        """
        self._log("--- Running Phantom Check ---", log_type="header")
        all_entities = self.model.AllEntities()
        self._log(f"Found {len(all_entities)} total entities in the project.", log_type="info")

        is_loaded = False
        for i, entity in enumerate(all_entities):
            if hasattr(entity, "Name"):
                entity_name_lower = entity.Name.lower()
                phantom_name_lower = self.phantom_name.lower()
                if phantom_name_lower in entity_name_lower:
                    is_loaded = True
                    break
            else:
                self._log(f"  - Entity {i}: (No 'Name' attribute)", log_type="verbose")

        if is_loaded:
            self._log(
                "--- Phantom Check Result: Phantom model is already present. ---",
                log_type="success",
            )
            return True
        else:
            self._log(
                "--- Phantom Check Result: Phantom not found in project. ---",
                log_type="warning",
            )

        study_type = self.config["study_type"]
        if study_type == "near_field" or study_type == "far_field":
            sab_path = os.path.join(self.config.base_dir, "data", "phantoms", f"{self.phantom_name}.sab")
            if os.path.exists(sab_path):
                self._log(
                    f"Phantom not found in document. Importing from '{sab_path}'...",
                    log_type="info",
                )
                self.XCoreModeling.Import(sab_path)
                self._log("Phantom imported successfully.", log_type="success")
                return True

            self._log(
                f"Local .sab file not found. Attempting to download '{self.phantom_name}'...",
                log_type="info",
            )
            available_downloads = self.data.GetAvailableDownloads()
            phantom_to_download = next(
                (item for item in available_downloads if self.phantom_name.lower() in item.Name.lower()),
                None,
            )

            if not phantom_to_download:
                raise FileNotFoundError(f"Phantom '{self.phantom_name}' not found for download or in local files.")

            self._log(f"Found '{phantom_to_download.Name}'. Downloading...", log_type="info")
            download_email = self.config["download_email"]
            if download_email is None:
                download_email = "example@example.com"
            self.data.DownloadModel(
                phantom_to_download,
                email=download_email,  # type: ignore
                directory=os.path.join(self.config.base_dir, "data", "phantoms"),
            )
            self._log(
                "Phantom downloaded successfully. Please re-run the script to import the new .sab file.",
                log_type="success",
            )
            return False
        else:
            raise ValueError(f"Unknown study type: {study_type}")
