import os
from .utils import open_project

class ProjectManager:
    """
    Handles the lifecycle of the .smash project file.
    """
    def __init__(self, project_path, verbose=True):
        self.project_path = project_path
        self.verbose = verbose
        import s4l_v1.document
        self.document = s4l_v1.document

    def _log(self, message):
        if self.verbose:
            print(message)

    def create_new(self):
        """
        Creates and saves a new empty project, deleting any existing one.
        """
        if os.path.exists(self.project_path):
            self._log(f"Deleting existing project file at {self.project_path}")
            os.remove(self.project_path)
        
        self._log("Creating and saving a new empty project.")
        self.document.New()
        self.save()

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
        self.close()