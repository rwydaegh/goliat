import os
from src.config import Config

class BaseStudy:
    """
    Abstract base class for all studies (Near-Field, Far-Field).
    """
    def __init__(self, config_filename, verbose=True):
        """
        Initializes the study by loading its configuration.
        
        Args:
            config_filename (str): The name of the configuration file in the 'configs' directory.
            verbose (bool): Flag to enable/disable detailed logging.
        """
        self.base_dir = self._find_base_dir()
        self.config = Config(self.base_dir, config_filename)
        self.verbose = verbose

    def _find_base_dir(self):
        """
        Finds the project's base directory by searching upwards from the current file.
        This makes the script runnable from different locations.
        """
        start_path = os.path.abspath(__file__)
        current_path = start_path
        while True:
            # Assumes base directory is the one containing 'src' and 'configs'
            if os.path.basename(os.path.dirname(current_path)) == 'src' and 'configs' in os.listdir(os.path.dirname(os.path.dirname(current_path))):
                return os.path.dirname(os.path.dirname(current_path))
            parent_path = os.path.dirname(current_path)
            if parent_path == current_path:
                # Fallback for safety, though the above should work
                return os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
            current_path = parent_path

    def _log(self, message):
        """
        Prints a message to the console if verbose mode is enabled.
        """
        if self.verbose:
            print(message, flush=True)

    def run(self, setup_only=False):
        """
        This method must be implemented by subclasses to execute the specific study.
        
        Args:
            setup_only (bool): If True, only the setup phase will be run.
        """
        raise NotImplementedError("The 'run' method must be implemented by a subclass.")