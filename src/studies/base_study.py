import os
import logging
from src.config import Config
from src.utils import Profiler, ensure_s4l_running, StudyCancelledError
import traceback
from src.project_manager import ProjectManager

class BaseStudy:
    """
    Abstract base class for all studies (Near-Field, Far-Field).
    """
    def __init__(self, study_type, config_filename=None, gui=None):
        self.study_type = study_type
        self.gui = gui
        self.verbose_logger = logging.getLogger('verbose')
        self.progress_logger = logging.getLogger('progress')
        
        self.base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        self.config = Config(self.base_dir, config_filename if config_filename else f"{self.study_type}_config.json")
        
        # Get study-specific profiling config
        profiling_config = self.config.get_profiling_config(self.study_type)
        execution_control = self.config.get_setting('execution_control', {'do_setup': True, 'do_run': True, 'do_extract': True})
        
        self.profiler = Profiler(execution_control, profiling_config, self.study_type, self.config.profiling_config_path)
        
        self.project_manager = ProjectManager(self.config, self.verbose_logger, self.progress_logger, self.gui)
        self.stop_requested = False

    def _log(self, message, level='verbose'):
        """
        Logs a message to the appropriate stream (progress or verbose).
        If a GUI is present, it delegates the logging to the GUI's log method.
        """
        if self.gui:
            # The GUI's log method will handle both logging to file and updating the status window
            self.gui.log(message, level=level)
        else:
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
        """Main method to run the study."""
        ensure_s4l_running()
        try:
            self._run_study()
        except StudyCancelledError:
            self._log("--- Study execution cancelled by user. ---", level='progress')
        except Exception as e:
            self._log(f"--- FATAL ERROR in study: {e} ---", level='progress')
            self.verbose_logger.error(traceback.format_exc())
        finally:
            self._log(f"\n--- {self.__class__.__name__} Finished ---", level='progress')
            self.profiler.save_estimates()
            self.project_manager.cleanup()
            if self.gui:
                self.gui.update_profiler() # Send final profiler state

    def _run_study(self):
        """
        This method must be implemented by subclasses to execute the specific study.
        """
        raise NotImplementedError("The '_run_study' method must be implemented by a subclass.")