import os
import logging
from src.config import Config
from src.utils import Profiler

class BaseStudy:
    """
    Abstract base class for all studies (Near-Field, Far-Field).
    """
    def __init__(self, config_filename, verbose=True, gui=None):
        """
        Initializes the study by loading its configuration.
        
        Args:
            config_filename (str): The name of the configuration file in the 'configs' directory.
            verbose (bool): Flag to enable/disable detailed logging.
            gui (ProgressGUI, optional): The GUI object for progress updates. Defaults to None.
        """
        self.base_dir = self._find_base_dir()
        self.config = Config(self.base_dir, config_filename)
        self.verbose = verbose
        self.gui = gui
        self.progress_logger = logging.getLogger('progress')
        self.verbose_logger = logging.getLogger('verbose')
        self.profiler = Profiler(self.config)

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

    def _log(self, message, level='verbose'):
        """
        Logs a message to the appropriate stream (progress or verbose).
        If a GUI is present, it delegates the logging to the GUI's log method.
        """
        if self.gui:
            # The GUI's log method will handle both logging to file and updating the status window
            self.gui.log(message, level=level)
        elif self.verbose:
            # If no GUI, log directly to the appropriate logger
            if level == 'progress':
                self.progress_logger.info(message)
            else:
                self.verbose_logger.info(message)

    def start_subtask(self, task_name):
        """Starts a subtask on the profiler."""
        self.profiler.start_subtask(task_name)

    def end_subtask(self):
        """
        Ends the current subtask on the profiler. The task name is implicitly
        handled by the profiler's internal stack.
        """
        if not self.profiler.subtask_stack:
            return 0
        return self.profiler.end_subtask()

    def start_stage_animation(self, task_name, end_value):
        """Starts the GUI animation for a stage."""
        if self.gui:
            self.gui.start_stage_animation(task_name, end_value)

    def end_stage_animation(self):
        """Ends the GUI animation for a stage."""
        if self.gui:
            self.gui.end_stage_animation()

    def run(self):
        """
        This method must be implemented by subclasses to execute the specific study.
        """
        raise NotImplementedError("The 'run' method must be implemented by a subclass.")