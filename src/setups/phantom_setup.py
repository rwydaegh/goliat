import os

class PhantomSetup:
    def __init__(self, config, phantom_name, verbose=True):
        self.config = config
        self.phantom_name = phantom_name
        self.verbose = verbose
        
        import s4l_v1.model
        import s4l_v1.data
        import XCoreModeling

        self.model = s4l_v1.model
        self.data = s4l_v1.data
        self.XCoreModeling = XCoreModeling

    def _log(self, message):
        if self.verbose:
            print(message)

    def ensure_phantom_is_loaded(self):
        """
        Ensures the phantom model is loaded into the current document.
        """
        all_entities = self.model.AllEntities()
        if any(self.phantom_name.lower() in entity.Name.lower() for entity in all_entities if hasattr(entity, 'Name')):
            self._log("Phantom model is already present in the document.")
            return True

        sab_path = os.path.join(self.config.base_dir, 'data', 'phantoms', f"{self.phantom_name.capitalize()}.sab")
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
        self.data.DownloadModel(phantom_to_download, email="example@example.com", directory=os.path.join(self.config.base_dir, 'data', 'phantoms'))
        self._log("Phantom downloaded successfully. Please re-run the script to import the new .sab file.")
        return False