import os
from .utils import open_project

class ProjectManager:
    """
    Handles the lifecycle of the .smash project file.
    """
    def __init__(self, config, verbose=True):
        self.config = config
        self.verbose = verbose
        self.project_path = None
        import s4l_v1.document
        self.document = s4l_v1.document

    def _log(self, message):
        if self.verbose:
            print(message)

    def create_or_open_project(self, phantom_name, frequency_mhz, placement_name=None, simulation_name_suffix=None):
        """
        Creates or opens a project. Handles different naming conventions for
        near-field and far-field studies.
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
            # A project per phantom and frequency for far-field.
            project_dir = os.path.join(self.config.base_dir, 'results', study_dir, phantom_name.lower(), f"{frequency_mhz}MHz")
            project_filename = f"far_field_{phantom_name.lower()}_{frequency_mhz}MHz.smash"

        os.makedirs(project_dir, exist_ok=True)
        self.project_path = os.path.join(project_dir, project_filename)
        self._log(f"Project path set to: {self.project_path}")

        # Always create a new project to avoid issues with corrupted files from previous runs.
        self.create_new()
        self.save()

    def create_new(self):
        """
        Creates a new empty project in memory, deleting any existing file.
        The project is not saved to disk until save() is explicitly called.
        """
        if os.path.exists(self.project_path):
            self._log(f"Deleting existing project file at {self.project_path}")
            os.remove(self.project_path)
        
        self._log("Creating a new empty project in memory.")
        self.document.New()

    def open(self):
        """
        Opens an existing project.
        """
        self._log(f"Opening project: {self.project_path}")
        open_project(self.project_path)

    def save(self):
        """
        Saves the project to its file path.
        """
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
        # After re-opening, the document object is new, so we need to get a fresh reference
        import s4l_v1.document
        self.document = s4l_v1.document
        self._log("Project reloaded.")
