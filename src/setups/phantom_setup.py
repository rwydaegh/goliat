import os
from .base_setup import BaseSetup

class PhantomSetup(BaseSetup):
    def __init__(self, config, phantom_name, verbose_logger, progress_logger):
        super().__init__(config, verbose_logger, progress_logger)
        self.phantom_name = phantom_name
        
        import s4l_v1.model
        import s4l_v1.data
        import XCoreModeling

        self.model = s4l_v1.model
        self.data = s4l_v1.data
        self.XCoreModeling = XCoreModeling

    def _log(self, message):
        self.verbose_logger.info(message)

    def ensure_phantom_is_loaded(self):
        """
        Ensures the phantom model is loaded into the current document.
        """
        self._log("--- Running Phantom Check ---")
        all_entities = self.model.AllEntities()
        self._log(f"Found {len(all_entities)} total entities in the project.")
        
        is_loaded = False
        for i, entity in enumerate(all_entities):
            if hasattr(entity, 'Name'):
                entity_name_lower = entity.Name.lower()
                phantom_name_lower = self.phantom_name.lower()
                if phantom_name_lower in entity_name_lower:
                    is_loaded = True
                    break
            else:
                self._log(f"  - Entity {i}: (No 'Name' attribute)")

        if is_loaded:
            self._log("--- Phantom Check Result: Phantom model is already present. ---")
            return True
        else:
            self._log("--- Phantom Check Result: Phantom not found in project. ---")

        study_type = self.config.get_setting('study_type')
        if study_type == 'near_field' or study_type == 'far_field':
            sab_path = os.path.join(self.config.base_dir, 'data', 'phantoms', f"{self.phantom_name}.sab")
            if os.path.exists(sab_path):
                self._log(f"Phantom not found in document. Importing from '{sab_path}'...")
                self.XCoreModeling.Import(sab_path)
                self._log("Phantom imported successfully.")
                return True

            self._log(f"Local .sab file not found. Attempting to download '{self.phantom_name}'...")
            available_downloads = self.data.GetAvailableDownloads()
            phantom_to_download = next((item for item in available_downloads if self.phantom_name in item.Name), None)
            
            if not phantom_to_download:
                raise FileNotFoundError(f"Phantom '{self.phantom_name}' not found for download or in local files.")
            
            self._log(f"Found '{phantom_to_download.Name}'. Downloading...")
            download_email = self.config.get_setting('download_email', 'example@example.com')
            self.data.DownloadModel(phantom_to_download, email=download_email, directory=os.path.join(self.config.base_dir, 'data', 'phantoms'))
            self._log("Phantom downloaded successfully. Please re-run the script to import the new .sab file.")
            return False
        else:
            raise ValueError(f"Unknown study type: {study_type}")