import os
import logging
import importlib
from line_profiler import LineProfiler
from src.config import Config
from src.utils import Profiler, ensure_s4l_running, StudyCancelledError, profile_subtask
import traceback
from src.project_manager import ProjectManager
from src.logging_manager import LoggingMixin

class BaseStudy(LoggingMixin):
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
        self.line_profiler = None
        
        self.project_manager = ProjectManager(self.config, self.verbose_logger, self.progress_logger, self.gui)
        self.stop_requested = False


    def subtask(self, task_name, instance_to_profile=None):
        """
        Returns a context manager that profiles a subtask, handling timing,
        GUI animations, and optional line-profiling.
        """
        return profile_subtask(self, task_name, instance_to_profile)

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

    def _setup_line_profiler(self, subtask_name, instance):
        """
        Sets up the line profiler for a specific subtask if configured.
        """
        line_profiling_config = self.config.get_line_profiling_config()
        
        if not line_profiling_config.get("enabled", False) or subtask_name not in line_profiling_config.get("subtasks", {}):
            return None, lambda func: func

        self._log(f"  - Setting up line profiler for subtask: {subtask_name}", level='verbose')
        
        lp = LineProfiler()
        functions_to_profile = line_profiling_config["subtasks"][subtask_name]

        for func_path in functions_to_profile:
            try:
                module_path, class_name, func_name = func_path.rsplit('.', 2)
                
                # Dynamically import the module and get the class
                module = importlib.import_module(module_path)
                class_obj = getattr(module, class_name)
                
                # Get the function object from the class
                func_to_add = getattr(class_obj, func_name)
                
                self._log(f"    - Adding function to profiler: {class_name}.{func_name} from {module_path}")
                lp.add_function(func_to_add)

            except (ImportError, AttributeError, ValueError) as e:
                self._log(f"  - WARNING: Could not find or parse function '{func_path}' for line profiling. Error: {e}", level='progress')
        
        return lp, lp.wrap_function