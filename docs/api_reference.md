
<a id="run_analysis"></a>

# Module run\_analysis

<a id="run_analysis.main"></a>

#### main

```python
def main()
```

Main entry point for the analysis script.

<a id="run_free_space_study"></a>

# Module run\_free\_space\_study

<a id="run_free_space_study.ConsoleLogger"></a>

## ConsoleLogger

```python
class ConsoleLogger()
```

A console-based logger for headless script execution.

<a id="run_free_space_study.create_temp_config"></a>

#### create\_temp\_config

```python
def create_temp_config(base_config, frequency_mhz)
```

Creates a temporary configuration for a single free-space run.

<a id="run_free_space_study.main"></a>

#### main

```python
def main()
```

Runs a free-space simulation for each available frequency to validate
the antenna models and the core simulation pipeline.

<a id="run_parallel_studies"></a>

# Module run\_parallel\_studies

<a id="run_parallel_studies.setup_console_logging"></a>

#### setup\_console\_logging

```python
def setup_console_logging()
```

Sets up a basic console logger with color.

<a id="run_parallel_studies.split_list_into_n"></a>

#### split\_list\_into\_n

```python
def split_list_into_n(items, n)
```

Split a list into n approximately equal parts.

<a id="run_parallel_studies.calculate_split_factors"></a>

#### calculate\_split\_factors

```python
def calculate_split_factors(num_phantoms, num_items, target_splits)
```

Calculate optimal splitting factors for phantoms and items (frequencies/antennas).
Prioritizes splitting phantoms first, then items.

Returns: (phantom_splits, item_splits) where phantom_splits * item_splits = target_splits

<a id="run_parallel_studies.split_config"></a>

#### split\_config

```python
def split_config(config_path, num_splits, logger)
```

Splits the configuration file into a number of parallel configs using smart algorithm.

<a id="run_parallel_studies.run_study_process"></a>

#### run\_study\_process

```python
def run_study_process(args)
```

Runs the study for a given config file.

<a id="run_parallel_studies.main"></a>

#### main

```python
def main()
```

Main function to split configs and run studies in parallel.

<a id="run_study"></a>

# Module run\_study

<a id="run_study.ConsoleLogger"></a>

## ConsoleLogger

```python
class ConsoleLogger()
```

A console-based logger to substitute for the GUI.

<a id="run_study.study_process_wrapper"></a>

#### study\_process\_wrapper

```python
def study_process_wrapper(queue, stop_event, config_filename, process_id)
```

This function runs in a separate process to execute the study.
It sets up its own loggers and communicates with the main GUI process via a queue
and a stop event.

<a id="run_study.main"></a>

#### main

```python
def main()
```

Main entry point for running a study.
It launches the GUI in the main process and the study in a separate process.

<a id="antenna"></a>

# Module antenna

<a id="antenna.Antenna"></a>

## Antenna

```python
class Antenna()
```

Manages antenna-specific properties and configurations.

<a id="antenna.Antenna.__init__"></a>

#### \_\_init\_\_

```python
def __init__(config: "Config", frequency_mhz: int)
```

Initializes the Antenna object.

**Arguments**:

- `config` - The configuration object containing antenna settings.
- `frequency_mhz` - The operating frequency in MHz.

<a id="antenna.Antenna.get_config_for_frequency"></a>

#### get\_config\_for\_frequency

```python
def get_config_for_frequency() -> dict
```

Gets the antenna configuration for the current frequency.

**Raises**:

- `ValueError` - If no configuration is defined for the frequency.
  

**Returns**:

  The antenna configuration dictionary.

<a id="antenna.Antenna.get_model_type"></a>

#### get\_model\_type

```python
def get_model_type() -> str
```

Gets the antenna model type (e.g., 'PIFA', 'IFA').

<a id="antenna.Antenna.get_source_entity_name"></a>

#### get\_source\_entity\_name

```python
def get_source_entity_name() -> str
```

Gets the name of the source entity in the CAD model.

<a id="antenna.Antenna.get_centered_antenna_path"></a>

#### get\_centered\_antenna\_path

```python
def get_centered_antenna_path(centered_antennas_dir: str) -> str
```

Constructs the path to the centered .sab antenna file.

**Arguments**:

- `centered_antennas_dir` - The directory for centered antenna files.
  

**Returns**:

  The absolute path to the centered antenna model file.

<a id="colors"></a>

# Module colors

<a id="colors.get_color"></a>

#### get\_color

```python
def get_color(log_type: str) -> str
```

Retrieves the colorama color code for a given log type.

**Arguments**:

- `log_type` - The type of log message (e.g., 'info', 'warning').
  

**Returns**:

  The colorama color code for the log type.

<a id="config"></a>

# Module config

<a id="config.deep_merge"></a>

#### deep\_merge

```python
def deep_merge(source: dict, destination: dict) -> dict
```

Recursively merges two dictionaries, overwriting destination with source values.

**Arguments**:

- `source` - The dictionary with values to merge.
- `destination` - The dictionary to be merged into.
  

**Returns**:

  The merged dictionary.

<a id="config.Config"></a>

## Config

```python
class Config()
```

Manages loading and access of hierarchical JSON configurations.

<a id="config.Config.__init__"></a>

#### \_\_init\_\_

```python
def __init__(base_dir: str, config_filename: str = "near_field_config.json")
```

Initializes the Config object by loading all relevant configuration files.

**Arguments**:

- `base_dir` - The base directory of the project.
- `config_filename` - The name of the main configuration file to load.

<a id="config.Config.get_setting"></a>

#### get\_setting

```python
def get_setting(path: str, default=None)
```

Retrieves a nested setting using a dot-separated path.

**Example**:

  `get_setting("simulation_parameters.number_of_point_sensors")`
  

**Arguments**:

- `path` - The dot-separated path to the setting.
- `default` - The default value to return if the setting is not found.
  

**Returns**:

  The value of the setting, or the default value.

<a id="config.Config.get_simulation_parameters"></a>

#### get\_simulation\_parameters

```python
def get_simulation_parameters() -> dict
```

Gets the 'simulation_parameters' dictionary.

<a id="config.Config.get_antenna_config"></a>

#### get\_antenna\_config

```python
def get_antenna_config() -> dict
```

Gets the 'antenna_config' dictionary.

<a id="config.Config.get_gridding_parameters"></a>

#### get\_gridding\_parameters

```python
def get_gridding_parameters() -> dict
```

Gets the 'gridding_parameters' dictionary.

<a id="config.Config.get_phantom_definition"></a>

#### get\_phantom\_definition

```python
def get_phantom_definition(phantom_name: str) -> dict
```

Gets the configuration for a specific phantom.

**Arguments**:

- `phantom_name` - The name of the phantom.
  

**Returns**:

  The configuration for the specified phantom.

<a id="config.Config.get_material_mapping"></a>

#### get\_material\_mapping

```python
def get_material_mapping(phantom_name: str) -> dict
```

Gets the material name mapping for a specific phantom.

**Arguments**:

- `phantom_name` - The name of the phantom.
  

**Returns**:

  The material mapping dictionary.

<a id="config.Config.get_solver_settings"></a>

#### get\_solver\_settings

```python
def get_solver_settings() -> dict
```

Gets the 'solver_settings' dictionary.

<a id="config.Config.get_antenna_component_names"></a>

#### get\_antenna\_component\_names

```python
def get_antenna_component_names(antenna_model_type: str) -> list
```

Gets component names for a specific antenna model type.

**Arguments**:

- `antenna_model_type` - The type of the antenna model (e.g., 'PIFA').
  

**Returns**:

  A list of component names.

<a id="config.Config.get_manual_isolve"></a>

#### get\_manual\_isolve

```python
def get_manual_isolve() -> bool
```

Gets the 'manual_isolve' boolean flag.

<a id="config.Config.get_freespace_expansion"></a>

#### get\_freespace\_expansion

```python
def get_freespace_expansion() -> list
```

Gets the freespace antenna bounding box expansion in millimeters.

<a id="config.Config.get_excitation_type"></a>

#### get\_excitation\_type

```python
def get_excitation_type() -> str
```

Gets the simulation excitation type (e.g., 'Harmonic', 'Gaussian').

<a id="config.Config.get_bandwidth"></a>

#### get\_bandwidth

```python
def get_bandwidth() -> float
```

Gets the simulation bandwidth in MHz for Gaussian excitation.

<a id="config.Config.get_placement_scenario"></a>

#### get\_placement\_scenario

```python
def get_placement_scenario(scenario_name: str) -> dict
```

Gets the definition for a specific placement scenario.

**Arguments**:

- `scenario_name` - The name of the placement scenario.
  

**Returns**:

  The configuration for the placement scenario.

<a id="config.Config.get_profiling_config"></a>

#### get\_profiling\_config

```python
def get_profiling_config(study_type: str) -> dict
```

Gets the profiling configuration for a given study type.

**Arguments**:

- `study_type` - The type of the study (e.g., 'near_field').
  

**Returns**:

  The profiling configuration for the study type.

<a id="config.Config.get_line_profiling_config"></a>

#### get\_line\_profiling\_config

```python
def get_line_profiling_config() -> dict
```

Gets the 'line_profiling' settings.

<a id="config.Config.get_download_email"></a>

#### get\_download\_email

```python
def get_download_email() -> str
```

Gets the download email from environment variables.

<a id="config.Config.get_osparc_credentials"></a>

#### get\_osparc\_credentials

```python
def get_osparc_credentials() -> dict
```

Gets oSPARC credentials from environment variables.

**Raises**:

- `ValueError` - If required oSPARC credentials are not set.
  

**Returns**:

  A dictionary containing oSPARC API credentials.

<a id="config.Config.get_only_write_input_file"></a>

#### get\_only\_write\_input\_file

```python
def get_only_write_input_file() -> bool
```

Gets the 'only_write_input_file' flag from 'execution_control'.

<a id="config.Config.get_auto_cleanup_previous_results"></a>

#### get\_auto\_cleanup\_previous\_results

```python
def get_auto_cleanup_previous_results() -> list
```

Gets the 'auto_cleanup_previous_results' setting from 'execution_control'.

This setting determines which previous simulation files to automatically delete
to preserve disk space. It should only be used in serial workflows.

**Returns**:

  A list of file types to clean up (e.g., ["output", "input"]).

<a id="data_extractor"></a>

# Module data\_extractor

<a id="data_extractor.get_parameter_from_json"></a>

#### get\_parameter\_from\_json

```python
def get_parameter_from_json(file_path: str, json_path: str) -> Any
```

Extracts a nested parameter from a JSON file using a dot-separated path.

**Arguments**:

- `file_path` - The path to the JSON file.
- `json_path` - The dot-separated path to the nested key.
  

**Returns**:

  The value found at the specified path, or None if not found.

<a id="data_extractor.get_parameter"></a>

#### get\_parameter

```python
def get_parameter(source_config: Dict[str, Any], context: Dict[str,
                                                               Any]) -> Any
```

Retrieves a parameter from a data source based on a configuration.

This function uses a `source_config` to determine the data source type
(e.g., 'json') and access parameters. The `context` dictionary provides
dynamic values for formatting file paths.

**Arguments**:

- `source_config` - A dictionary defining the data source.
- `context` - A dictionary with contextual information for formatting.
  

**Returns**:

  The retrieved parameter value, or None on error.

<a id="gui_manager"></a>

# Module gui\_manager

<a id="gui_manager.QueueGUI"></a>

## QueueGUI

```python
class QueueGUI(LoggingMixin)
```

A proxy for the main GUI, designed to operate in a separate process.

This class mimics the `ProgressGUI` interface but directs all calls to a
`multiprocessing.Queue`, allowing a worker process to send thread-safe
updates to the main GUI process.

<a id="gui_manager.QueueGUI.__init__"></a>

#### \_\_init\_\_

```python
def __init__(queue: "Queue", stop_event: "Event", profiler: "Profiler",
             progress_logger: "Logger", verbose_logger: "Logger")
```

Initializes the QueueGUI proxy.

**Arguments**:

- `queue` - The queue for inter-process communication.
- `stop_event` - An event to signal termination.
- `profiler` - The profiler instance for ETA calculations.
- `progress_logger` - Logger for progress messages.
- `verbose_logger` - Logger for detailed messages.

<a id="gui_manager.QueueGUI.log"></a>

#### log

```python
def log(message: str, level: str = "verbose", log_type: str = "default")
```

Sends a log message to the main GUI process via the queue.

<a id="gui_manager.QueueGUI.update_overall_progress"></a>

#### update\_overall\_progress

```python
def update_overall_progress(current_step: int, total_steps: int)
```

Sends an overall progress update to the queue.

<a id="gui_manager.QueueGUI.update_stage_progress"></a>

#### update\_stage\_progress

```python
def update_stage_progress(stage_name: str, current_step: int,
                          total_steps: int)
```

Sends a stage-specific progress update to the queue.

<a id="gui_manager.QueueGUI.start_stage_animation"></a>

#### start\_stage\_animation

```python
def start_stage_animation(task_name: str, end_value: int)
```

Sends a command to start a progress bar animation.

<a id="gui_manager.QueueGUI.end_stage_animation"></a>

#### end\_stage\_animation

```python
def end_stage_animation()
```

Sends a command to stop the progress bar animation.

<a id="gui_manager.QueueGUI.update_profiler"></a>

#### update\_profiler

```python
def update_profiler()
```

Sends the updated profiler object to the GUI process.

<a id="gui_manager.QueueGUI.process_events"></a>

#### process\_events

```python
def process_events()
```

A no-op method for interface compatibility.

<a id="gui_manager.QueueGUI.is_stopped"></a>

#### is\_stopped

```python
def is_stopped() -> bool
```

Checks if the main process has signaled a stop request.

<a id="gui_manager.ProgressGUI"></a>

## ProgressGUI

```python
class ProgressGUI(QWidget)
```

The main GUI for monitoring simulation progress.

Provides a real-time view of the study's progress, including progress bars,
ETA, and a log of status messages. It runs in the main process and
communicates with the worker process via a multiprocessing queue.

<a id="gui_manager.ProgressGUI.__init__"></a>

#### \_\_init\_\_

```python
def __init__(queue: "Queue",
             stop_event: "Event",
             process,
             window_title: str = "Simulation Progress")
```

Initializes the ProgressGUI window.

**Arguments**:

- `queue` - The queue for receiving messages from the worker process.
- `stop_event` - An event to signal termination to the worker process.
- `process` - The worker process running the study.
- `window_title` - The title of the GUI window.

<a id="gui_manager.ProgressGUI.init_ui"></a>

#### init\_ui

```python
def init_ui()
```

Initializes and arranges all UI widgets.

<a id="gui_manager.ProgressGUI.process_queue"></a>

#### process\_queue

```python
def process_queue()
```

Processes messages from the worker process queue to update the UI.

<a id="gui_manager.ProgressGUI.tray_icon_activated"></a>

#### tray\_icon\_activated

```python
def tray_icon_activated(reason)
```

Handles activation of the system tray icon.

<a id="gui_manager.ProgressGUI.hide_to_tray"></a>

#### hide\_to\_tray

```python
def hide_to_tray()
```

Hides the main window and shows the system tray icon.

<a id="gui_manager.ProgressGUI.show_from_tray"></a>

#### show\_from\_tray

```python
def show_from_tray()
```

Shows the main window from the system tray.

<a id="gui_manager.ProgressGUI.stop_study"></a>

#### stop\_study

```python
def stop_study()
```

Sends a stop signal to the worker process.

<a id="gui_manager.ProgressGUI.update_overall_progress"></a>

#### update\_overall\_progress

```python
def update_overall_progress(current_step: int, total_steps: int)
```

Updates the overall progress bar.

<a id="gui_manager.ProgressGUI.update_stage_progress"></a>

#### update\_stage\_progress

```python
def update_stage_progress(stage_name: str, current_step: int,
                          total_steps: int)
```

Updates the stage-specific progress bar.

<a id="gui_manager.ProgressGUI.start_stage_animation"></a>

#### start\_stage\_animation

```python
def start_stage_animation(estimated_duration: float, end_step: int)
```

Starts a smooth animation for the stage progress bar.

**Arguments**:

- `estimated_duration` - The estimated time in seconds for the task.
- `end_step` - The target step value for the animation.

<a id="gui_manager.ProgressGUI.end_stage_animation"></a>

#### end\_stage\_animation

```python
def end_stage_animation()
```

Stops the stage progress bar animation.

<a id="gui_manager.ProgressGUI.update_animation"></a>

#### update\_animation

```python
def update_animation()
```

Updates the progress bar animation frame by frame.

<a id="gui_manager.ProgressGUI.update_status"></a>

#### update\_status

```python
def update_status(message: str, log_type: str = "default")
```

Appends a message to the status log text box.

<a id="gui_manager.ProgressGUI.update_clock"></a>

#### update\_clock

```python
def update_clock()
```

Updates the elapsed time and ETA labels.

<a id="gui_manager.ProgressGUI.study_finished"></a>

#### study\_finished

```python
def study_finished(error: bool = False)
```

Handles study completion, stopping timers and updating the UI.

<a id="gui_manager.ProgressGUI.closeEvent"></a>

#### closeEvent

```python
def closeEvent(event)
```

Handles the window close event, ensuring worker process termination.

<a id="logging_manager"></a>

# Module logging\_manager

<a id="logging_manager.ColorFormatter"></a>

## ColorFormatter

```python
class ColorFormatter(logging.Formatter)
```

A custom log formatter that applies color to terminal output.

<a id="logging_manager.ColorFormatter.format"></a>

#### format

```python
def format(record: logging.LogRecord) -> str
```

Formats the log record by adding color codes.

**Arguments**:

- `record` - The log record to format.
  

**Returns**:

  The formatted and colorized log message.

<a id="logging_manager.setup_loggers"></a>

#### setup\_loggers

```python
def setup_loggers(
        process_id: str = None) -> tuple[logging.Logger, logging.Logger, str]
```

Initializes and configures the dual-logging system.

Sets up two loggers:
1. 'progress': For high-level, user-facing updates.
2. 'verbose': For detailed, internal debugging information.

Also handles log rotation to prevent excessive disk usage.

**Arguments**:

- `process_id` - An identifier for the process to ensure unique log
  filenames in parallel runs.
  

**Returns**:

  A tuple containing the progress logger, verbose logger, and the
  session timestamp.

<a id="logging_manager.shutdown_loggers"></a>

#### shutdown\_loggers

```python
def shutdown_loggers()
```

Safely shuts down all logging handlers to release file locks.

<a id="logging_manager.LoggingMixin"></a>

## LoggingMixin

```python
class LoggingMixin()
```

A mixin class that provides a standardized logging interface.

Provides a `_log` method that directs messages to the appropriate logger
('progress' or 'verbose') and, if available, to the GUI.

<a id="profiler"></a>

# Module profiler

<a id="profiler.Profiler"></a>

## Profiler

```python
class Profiler()
```

Manages execution time tracking, ETA estimation, and study phase management.

This class divides a study into phases (setup, run, extract), calculates
weighted progress, and estimates the time remaining. It also saves updated
time estimates to a configuration file after each run, making it
self-improving.

<a id="profiler.Profiler.__init__"></a>

#### \_\_init\_\_

```python
def __init__(execution_control: dict, profiling_config: dict, study_type: str,
             config_path: str)
```

Initializes the Profiler.

**Arguments**:

- `execution_control` - A dictionary indicating which study phases are active.
- `profiling_config` - A dictionary with historical timing data.
- `study_type` - The type of the study (e.g., 'near_field').
- `config_path` - The file path to the profiling configuration.

<a id="profiler.Profiler.set_total_simulations"></a>

#### set\_total\_simulations

```python
def set_total_simulations(total: int)
```

Sets the total number of simulations for the study.

<a id="profiler.Profiler.set_project_scope"></a>

#### set\_project\_scope

```python
def set_project_scope(total_projects: int)
```

Sets the total number of projects to be processed.

<a id="profiler.Profiler.set_current_project"></a>

#### set\_current\_project

```python
def set_current_project(project_index: int)
```

Sets the index of the currently processing project.

<a id="profiler.Profiler.start_stage"></a>

#### start\_stage

```python
def start_stage(phase_name: str, total_stages: int = 1)
```

Marks the beginning of a new study phase or stage.

**Arguments**:

- `phase_name` - The name of the phase being started.
- `total_stages` - The total number of stages within this phase.

<a id="profiler.Profiler.end_stage"></a>

#### end\_stage

```python
def end_stage()
```

Marks the end of a study phase and records its duration.

<a id="profiler.Profiler.complete_run_phase"></a>

#### complete\_run\_phase

```python
def complete_run_phase()
```

Stores the total duration of the 'run' phase from its subtasks.

<a id="profiler.Profiler.get_weighted_progress"></a>

#### get\_weighted\_progress

```python
def get_weighted_progress(phase_name: str,
                          phase_progress_ratio: float) -> float
```

Calculates the overall study progress based on phase weights.

**Arguments**:

- `phase_name` - The name of the current phase.
- `phase_progress_ratio` - The progress of the current phase (0.0 to 1.0).
  

**Returns**:

  The total weighted progress percentage.

<a id="profiler.Profiler.get_subtask_estimate"></a>

#### get\_subtask\_estimate

```python
def get_subtask_estimate(task_name: str) -> float
```

Retrieves the estimated time for a specific subtask.

**Arguments**:

- `task_name` - The name of the subtask.
  

**Returns**:

  The estimated duration in seconds.

<a id="profiler.Profiler.get_time_remaining"></a>

#### get\_time\_remaining

```python
def get_time_remaining(current_stage_progress: float = 0.0) -> float
```

Estimates the total time remaining for the study.

This considers completed phases, current phase progress, and estimated
time for all future phases.

**Arguments**:

- `current_stage_progress` - The progress of the current stage (0.0 to 1.0).
  

**Returns**:

  The estimated time remaining in seconds.

<a id="profiler.Profiler.update_and_save_estimates"></a>

#### update\_and\_save\_estimates

```python
def update_and_save_estimates()
```

Updates the profiling configuration with the latest average times and saves it.

This makes the profiler's estimates self-improving over time.

<a id="profiler.Profiler.save_estimates"></a>

#### save\_estimates

```python
def save_estimates()
```

Saves the final profiling estimates at the end of the study.

<a id="project_manager"></a>

# Module project\_manager

<a id="project_manager.ProjectCorruptionError"></a>

## ProjectCorruptionError

```python
class ProjectCorruptionError(Exception)
```

Custom exception raised for errors related to corrupted or locked project files.

<a id="project_manager.ProjectManager"></a>

## ProjectManager

```python
class ProjectManager(LoggingMixin)
```

Manages the lifecycle of Sim4Life (.smash) project files.

Handles creation, opening, saving, and validation of project files,
ensuring robustness against file corruption and locks.

<a id="project_manager.ProjectManager.__init__"></a>

#### \_\_init\_\_

```python
def __init__(config: "Config",
             verbose_logger: "Logger",
             progress_logger: "Logger",
             gui: "QueueGUI" = None)
```

Initializes the ProjectManager.

**Arguments**:

- `config` - The main configuration object.
- `verbose_logger` - Logger for detailed output.
- `progress_logger` - Logger for high-level progress updates.
- `gui` - The GUI proxy for inter-process communication.

<a id="project_manager.ProjectManager.create_or_open_project"></a>

#### create\_or\_open\_project

```python
def create_or_open_project(phantom_name: str,
                           frequency_mhz: int,
                           scenario_name: str = None,
                           position_name: str = None,
                           orientation_name: str = None)
```

Creates a new project or opens an existing one based on the 'do_setup' flag.

**Arguments**:

- `phantom_name` - The name of the phantom model.
- `frequency_mhz` - The simulation frequency in MHz.
- `scenario_name` - The base name of the placement scenario.
- `position_name` - The name of the position within the scenario.
- `orientation_name` - The name of the orientation within the scenario.
  

**Raises**:

- `ValueError` - If required parameters are missing or `study_type` is unknown.
- `FileNotFoundError` - If `do_setup` is false and the project file does not exist.
- `ProjectCorruptionError` - If the project file is corrupted.

<a id="project_manager.ProjectManager.create_new"></a>

#### create\_new

```python
def create_new()
```

Creates a new, empty project in memory.

Closes any open document, deletes the existing project file and its
cache, then creates a new unsaved project.

<a id="project_manager.ProjectManager.open"></a>

#### open

```python
def open()
```

Opens an existing project after performing validation checks.

**Raises**:

- `ProjectCorruptionError` - If the project file is invalid, locked, or
  cannot be opened by Sim4Life.

<a id="project_manager.ProjectManager.save"></a>

#### save

```python
def save()
```

Saves the currently active project to its designated file path.

**Raises**:

- `ValueError` - If the project path has not been set.

<a id="project_manager.ProjectManager.close"></a>

#### close

```python
def close()
```

Closes the currently active Sim4Life document.

<a id="project_manager.ProjectManager.cleanup"></a>

#### cleanup

```python
def cleanup()
```

Closes any open project.

<a id="project_manager.ProjectManager.reload_project"></a>

#### reload\_project

```python
def reload_project()
```

Saves, closes, and re-opens the project to load simulation results.

<a id="results_extractor"></a>

# Module results\_extractor

<a id="results_extractor.ResultsExtractor"></a>

## ResultsExtractor

```python
class ResultsExtractor(LoggingMixin)
```

Orchestrates post-processing and data extraction from simulation results.

Coordinates modules to extract power, SAR, and sensor data from a
Sim4Life simulation, then manages report generation and cleanup.

<a id="results_extractor.ResultsExtractor.__init__"></a>

#### \_\_init\_\_

```python
def __init__(config: "Config",
             simulation: "s4l_v1.simulation.emfdtd.Simulation",
             phantom_name: str,
             frequency_mhz: int,
             scenario_name: str,
             position_name: str,
             orientation_name: str,
             study_type: str,
             verbose_logger: "Logger",
             progress_logger: "Logger",
             free_space: bool = False,
             gui: "QueueGUI" = None,
             study: "BaseStudy" = None)
```

Initializes the ResultsExtractor.

**Arguments**:

- `config` - The configuration object for the study.
- `simulation` - The simulation object to extract results from.
- `phantom_name` - The name of the phantom model used.
- `frequency_mhz` - The simulation frequency in MHz.
- `scenario_name` - The base name of the placement scenario.
- `position_name` - The name of the position within the scenario.
- `orientation_name` - The name of the orientation within the scenario.
- `study_type` - The type of the study (e.g., 'near_field').
- `verbose_logger` - Logger for detailed output.
- `progress_logger` - Logger for progress updates.
- `free_space` - Flag indicating if the simulation was run in free space.
- `gui` - The GUI proxy for updates.
- `study` - The parent study object.

<a id="results_extractor.ResultsExtractor.extract"></a>

#### extract

```python
def extract()
```

Orchestrates the extraction of all relevant data from the simulation.

This is the main entry point for the class. It coordinates extraction
modules for power, SAR, and sensor data, then saves the results.

<a id="simulation_runner"></a>

# Module simulation\_runner

<a id="simulation_runner.SimulationRunner"></a>

## SimulationRunner

```python
class SimulationRunner(LoggingMixin)
```

Manages simulation execution via the Sim4Life API or iSolve.exe.

<a id="simulation_runner.SimulationRunner.__init__"></a>

#### \_\_init\_\_

```python
def __init__(config: "Config",
             project_path: str,
             simulations: Union["s4l_v1.simulation.emfdtd.Simulation",
                                List["s4l_v1.simulation.emfdtd.Simulation"]],
             verbose_logger: "Logger",
             progress_logger: "Logger",
             gui: "QueueGUI" = None,
             study: "BaseStudy" = None)
```

Initializes the SimulationRunner.

**Arguments**:

- `config` - The configuration object for the study.
- `project_path` - The file path to the Sim4Life project.
- `simulations` - A single simulation or a list of simulations to run.
- `verbose_logger` - Logger for detailed, verbose output.
- `progress_logger` - Logger for high-level progress updates.
- `gui` - The GUI proxy for sending updates to the main process.
- `study` - The parent study object for profiling and context.

<a id="simulation_runner.SimulationRunner.run_all"></a>

#### run\_all

```python
def run_all()
```

Runs all simulations in the list, managing GUI animations.

<a id="simulation_runner.SimulationRunner.run"></a>

#### run

```python
def run(simulation: "s4l_v1.simulation.emfdtd.Simulation")
```

Runs a single simulation, wrapped in a subtask for timing.

<a id="utils"></a>

# Module utils

<a id="utils.StudyCancelledError"></a>

## StudyCancelledError

```python
class StudyCancelledError(Exception)
```

Custom exception to indicate that the study was cancelled by the user.

<a id="utils.Profiler"></a>

## Profiler

```python
class Profiler()
```

A simple profiler to track and estimate execution time for a series of runs.

<a id="utils.Profiler.__init__"></a>

#### \_\_init\_\_

```python
def __init__(config_path: str, study_type: str = "sensitivity_analysis")
```

Initializes the simple Profiler.

**Arguments**:

- `config_path` - The file path to the profiling configuration JSON.
- `study_type` - The key for the study-specific configuration.

<a id="utils.Profiler.start_study"></a>

#### start\_study

```python
def start_study(total_runs: int)
```

Starts a new study, resetting counters.

<a id="utils.Profiler.start_run"></a>

#### start\_run

```python
def start_run()
```

Marks the beginning of a single run.

<a id="utils.Profiler.end_run"></a>

#### end\_run

```python
def end_run()
```

Marks the end of a single run and records its duration.

<a id="utils.Profiler.get_average_run_time"></a>

#### get\_average\_run\_time

```python
def get_average_run_time() -> float
```

Gets the average run time, prioritizing measured times over historical estimates.

<a id="utils.Profiler.get_time_remaining"></a>

#### get\_time\_remaining

```python
def get_time_remaining() -> float
```

Estimates the time remaining for the entire study.

<a id="utils.Profiler.save_estimates"></a>

#### save\_estimates

```python
def save_estimates()
```

Saves the new average run time to the configuration file.

<a id="utils.Profiler.get_elapsed"></a>

#### get\_elapsed

```python
def get_elapsed() -> float
```

Gets the total elapsed time since the study started.

**Returns**:

  The elapsed time in seconds.

<a id="utils.Profiler.subtask"></a>

#### subtask

```python
@contextlib.contextmanager
def subtask(name: str)
```

A context manager to time a subtask.

<a id="utils.format_time"></a>

#### format\_time

```python
def format_time(seconds: float) -> str
```

Formats seconds into a human-readable string (e.g., 1m 23s).

<a id="utils.non_blocking_sleep"></a>

#### non\_blocking\_sleep

```python
def non_blocking_sleep(seconds: int)
```

A non-blocking sleep that processes GUI events.

<a id="utils.profile"></a>

#### profile

```python
@contextlib.contextmanager
def profile(study: "BaseStudy", phase_name: str)
```

A context manager to profile a block of code (a 'phase').

<a id="utils.profile_subtask"></a>

#### profile\_subtask

```python
@contextlib.contextmanager
def profile_subtask(study: "BaseStudy",
                    task_name: str,
                    instance_to_profile=None)
```

A context manager for a 'subtask'.

Handles:
- High-level timing via study.profiler.
- GUI stage animation.
- Optional, detailed line-by-line profiling if configured.

<a id="utils.ensure_s4l_running"></a>

#### ensure\_s4l\_running

```python
def ensure_s4l_running()
```

Ensures that the Sim4Life application is running.

<a id="utils.open_project"></a>

#### open\_project

```python
def open_project(project_path: str)
```

Opens a Sim4Life project or creates a new one in memory.

<a id="utils.delete_project_file"></a>

#### delete\_project\_file

```python
def delete_project_file(project_path: str)
```

Deletes the project file if it exists.

<a id="utils.suppress_stdout_stderr"></a>

#### suppress\_stdout\_stderr

```python
@contextlib.contextmanager
def suppress_stdout_stderr()
```

A context manager that redirects stdout and stderr to devnull.

<a id="src.analysis.analyzer"></a>

# Module src.analysis.analyzer

<a id="src.analysis.analyzer.Analyzer"></a>

## Analyzer

```python
class Analyzer()
```

Analyzes simulation results using a strategy pattern.

<a id="src.analysis.analyzer.Analyzer.__init__"></a>

#### \_\_init\_\_

```python
def __init__(config: "Config", phantom_name: str,
             strategy: "BaseAnalysisStrategy")
```

Initializes the Analyzer.

**Arguments**:

- `config` - The configuration object for the study.
- `phantom_name` - The name of the phantom model being analyzed.
- `strategy` - The analysis strategy to use.

<a id="src.analysis.analyzer.Analyzer.run_analysis"></a>

#### run\_analysis

```python
def run_analysis()
```

Runs the full analysis pipeline using the selected strategy.

<a id="src.analysis.base_strategy"></a>

# Module src.analysis.base\_strategy

<a id="src.analysis.base_strategy.BaseAnalysisStrategy"></a>

## BaseAnalysisStrategy

```python
class BaseAnalysisStrategy(ABC)
```

Abstract base class for analysis strategies.

<a id="src.analysis.base_strategy.BaseAnalysisStrategy.__init__"></a>

#### \_\_init\_\_

```python
def __init__(config: "Config", phantom_name: str)
```

Initializes the analysis strategy.

**Arguments**:

- `config` - The main configuration object.
- `phantom_name` - The name of the phantom being analyzed.

<a id="src.analysis.base_strategy.BaseAnalysisStrategy.get_results_base_dir"></a>

#### get\_results\_base\_dir

```python
@abstractmethod
def get_results_base_dir() -> str
```

Gets the base directory for results.

<a id="src.analysis.base_strategy.BaseAnalysisStrategy.get_plots_dir"></a>

#### get\_plots\_dir

```python
@abstractmethod
def get_plots_dir() -> str
```

Gets the directory for saving plots.

<a id="src.analysis.base_strategy.BaseAnalysisStrategy.load_and_process_results"></a>

#### load\_and\_process\_results

```python
@abstractmethod
def load_and_process_results(analyzer: "Analyzer")
```

Loads and processes all relevant simulation results.

**Arguments**:

- `analyzer` - The main analyzer instance calling the strategy.

<a id="src.analysis.base_strategy.BaseAnalysisStrategy.get_normalization_factor"></a>

#### get\_normalization\_factor

```python
@abstractmethod
def get_normalization_factor(frequency_mhz: int,
                             simulated_power_w: float) -> float
```

Calculates the normalization factor for SAR values.

**Arguments**:

- `frequency_mhz` - The simulation frequency in MHz.
- `simulated_power_w` - The input power from the simulation in Watts.
  

**Returns**:

  The calculated normalization factor.

<a id="src.analysis.base_strategy.BaseAnalysisStrategy.extract_data"></a>

#### extract\_data

```python
@abstractmethod
def extract_data(pickle_data: dict, frequency_mhz: int, detailed_name: str,
                 scenario_name: str, sim_power: float,
                 norm_factor: float) -> tuple[dict, list]
```

Extracts and structures data from a single simulation's result files.

**Arguments**:

- `pickle_data` - Data loaded from the .pkl result file.
- `frequency_mhz` - The simulation frequency.
- `detailed_name` - The detailed name of the placement or scenario.
- `scenario_name` - The general scenario name.
- `sim_power` - The simulated input power in Watts.
- `norm_factor` - The normalization factor to apply.
  

**Returns**:

  A tuple containing the main result entry and a list of organ-specific entries.

<a id="src.analysis.base_strategy.BaseAnalysisStrategy.apply_bug_fixes"></a>

#### apply\_bug\_fixes

```python
@abstractmethod
def apply_bug_fixes(result_entry: dict) -> dict
```

Applies workarounds for known data inconsistencies.

**Arguments**:

- `result_entry` - The data entry for a single simulation result.
  

**Returns**:

  The corrected result entry.

<a id="src.analysis.base_strategy.BaseAnalysisStrategy.calculate_summary_stats"></a>

#### calculate\_summary\_stats

```python
@abstractmethod
def calculate_summary_stats(results_df: pd.DataFrame) -> pd.DataFrame
```

Calculates summary statistics from the aggregated results.

**Arguments**:

- `results_df` - DataFrame with all aggregated simulation results.
  

**Returns**:

  A DataFrame with summary statistics.

<a id="src.analysis.base_strategy.BaseAnalysisStrategy.generate_plots"></a>

#### generate\_plots

```python
@abstractmethod
def generate_plots(analyzer: "Analyzer", plotter: "Plotter",
                   results_df: pd.DataFrame,
                   all_organ_results_df: pd.DataFrame)
```

Generates all plots relevant to this analysis strategy.

**Arguments**:

- `analyzer` - The main analyzer instance.
- `plotter` - The plotter instance to use for generating plots.
- `results_df` - DataFrame with main aggregated results.
- `all_organ_results_df` - DataFrame with detailed organ-level results.

<a id="src.analysis.far_field_strategy"></a>

# Module src.analysis.far\_field\_strategy

<a id="src.analysis.far_field_strategy.FarFieldAnalysisStrategy"></a>

## FarFieldAnalysisStrategy

```python
class FarFieldAnalysisStrategy(BaseAnalysisStrategy)
```

Analysis strategy for far-field simulations.

<a id="src.analysis.far_field_strategy.FarFieldAnalysisStrategy.get_results_base_dir"></a>

#### get\_results\_base\_dir

```python
def get_results_base_dir() -> str
```

Gets the base directory for far-field results.

<a id="src.analysis.far_field_strategy.FarFieldAnalysisStrategy.get_plots_dir"></a>

#### get\_plots\_dir

```python
def get_plots_dir() -> str
```

Gets the directory for saving far-field plots.

<a id="src.analysis.far_field_strategy.FarFieldAnalysisStrategy.get_normalization_factor"></a>

#### get\_normalization\_factor

```python
def get_normalization_factor(frequency_mhz: int,
                             simulated_power_w: float) -> float
```

Returns the normalization factor for far-field analysis (always 1.0).

<a id="src.analysis.far_field_strategy.FarFieldAnalysisStrategy.apply_bug_fixes"></a>

#### apply\_bug\_fixes

```python
def apply_bug_fixes(result_entry: dict) -> dict
```

No bug fixes needed for far-field data.

<a id="src.analysis.far_field_strategy.FarFieldAnalysisStrategy.calculate_summary_stats"></a>

#### calculate\_summary\_stats

```python
def calculate_summary_stats(results_df: pd.DataFrame) -> pd.DataFrame
```

Calculates summary statistics for far-field results.

<a id="src.analysis.near_field_strategy"></a>

# Module src.analysis.near\_field\_strategy

<a id="src.analysis.near_field_strategy.NearFieldAnalysisStrategy"></a>

## NearFieldAnalysisStrategy

```python
class NearFieldAnalysisStrategy(BaseAnalysisStrategy)
```

Analysis strategy for near-field simulations.

<a id="src.analysis.near_field_strategy.NearFieldAnalysisStrategy.get_results_base_dir"></a>

#### get\_results\_base\_dir

```python
def get_results_base_dir() -> str
```

Gets the base directory for near-field results.

<a id="src.analysis.near_field_strategy.NearFieldAnalysisStrategy.get_plots_dir"></a>

#### get\_plots\_dir

```python
def get_plots_dir() -> str
```

Gets the directory for saving near-field plots.

<a id="src.analysis.near_field_strategy.NearFieldAnalysisStrategy.load_and_process_results"></a>

#### load\_and\_process\_results

```python
def load_and_process_results(analyzer: "Analyzer")
```

Iterates through near-field simulation results and processes each one.

<a id="src.analysis.near_field_strategy.NearFieldAnalysisStrategy.get_normalization_factor"></a>

#### get\_normalization\_factor

```python
def get_normalization_factor(frequency_mhz: int,
                             simulated_power_w: float) -> float
```

Calculates the normalization factor based on the target power.

**Arguments**:

- `frequency_mhz` - The simulation frequency in MHz.
- `simulated_power_w` - The input power from the simulation in Watts.
  

**Returns**:

  The calculated normalization factor, or 1.0 if not possible.

<a id="src.analysis.near_field_strategy.NearFieldAnalysisStrategy.extract_data"></a>

#### extract\_data

```python
def extract_data(pickle_data: dict, frequency_mhz: int, placement_name: str,
                 scenario_name: str, sim_power: float,
                 norm_factor: float) -> tuple[dict, list]
```

Extracts and normalizes SAR data from a single near-field result.

**Arguments**:

- `pickle_data` - Data loaded from the .pkl result file.
- `frequency_mhz` - The simulation frequency.
- `placement_name` - The detailed name of the placement.
- `scenario_name` - The general scenario name (e.g., 'by_cheek').
- `sim_power` - The simulated input power in Watts.
- `norm_factor` - The normalization factor to apply to SAR values.
  

**Returns**:

  A tuple containing the main result entry and a list of organ-specific entries.

<a id="src.analysis.near_field_strategy.NearFieldAnalysisStrategy.apply_bug_fixes"></a>

#### apply\_bug\_fixes

```python
def apply_bug_fixes(result_entry: dict) -> dict
```

Applies a workaround for Head SAR being miscategorized as Trunk SAR.

**Arguments**:

- `result_entry` - The data entry for a single simulation result.
  

**Returns**:

  The corrected result entry.

<a id="src.analysis.near_field_strategy.NearFieldAnalysisStrategy.calculate_summary_stats"></a>

#### calculate\_summary\_stats

```python
def calculate_summary_stats(results_df: pd.DataFrame) -> pd.DataFrame
```

Calculates summary statistics, including completion progress.

**Arguments**:

- `results_df` - DataFrame with all aggregated simulation results.
  

**Returns**:

  A DataFrame with mean SAR values and a 'progress' column.

<a id="src.analysis.near_field_strategy.NearFieldAnalysisStrategy.generate_plots"></a>

#### generate\_plots

```python
def generate_plots(analyzer: "Analyzer", plotter: "Plotter",
                   results_df: pd.DataFrame,
                   all_organ_results_df: pd.DataFrame)
```

Generates all plots for the near-field analysis.

Includes bar charts for average SAR, line plots for psSAR, and boxplots
for SAR distribution.

**Arguments**:

- `analyzer` - The main analyzer instance.
- `plotter` - The plotter instance for generating plots.
- `results_df` - DataFrame with main aggregated results.
- `all_organ_results_df` - DataFrame with detailed organ-level results.

<a id="src.analysis.plotter"></a>

# Module src.analysis.plotter

<a id="src.analysis.plotter.Plotter"></a>

## Plotter

```python
class Plotter()
```

Generates various plots from simulation results.

<a id="src.analysis.plotter.Plotter.__init__"></a>

#### \_\_init\_\_

```python
def __init__(plots_dir: str)
```

Initializes the Plotter and creates the output directory.

**Arguments**:

- `plots_dir` - The directory where all generated plots will be saved.

<a id="src.analysis.plotter.Plotter.plot_average_sar_bar"></a>

#### plot\_average\_sar\_bar

```python
def plot_average_sar_bar(scenario_name: str, avg_results: pd.DataFrame,
                         progress_info: pd.Series)
```

Plots a bar chart of average Head and Trunk SAR per frequency.

**Arguments**:

- `scenario_name` - The name of the placement scenario (e.g., 'by_cheek').
- `avg_results` - DataFrame with average SAR values, indexed by frequency.
- `progress_info` - Series with completion progress for each frequency.

<a id="src.analysis.plotter.Plotter.plot_whole_body_sar_bar"></a>

#### plot\_whole\_body\_sar\_bar

```python
def plot_whole_body_sar_bar(avg_results: pd.DataFrame)
```

Plots a bar chart of the average Whole-Body SAR per frequency.

**Arguments**:

- `avg_results` - DataFrame with average SAR values, indexed by frequency.

<a id="src.analysis.plotter.Plotter.plot_peak_sar_line"></a>

#### plot\_peak\_sar\_line

```python
def plot_peak_sar_line(summary_stats: pd.DataFrame)
```

Plots the peak SAR across frequencies for far-field.

<a id="src.analysis.plotter.Plotter.plot_pssar_line"></a>

#### plot\_pssar\_line

```python
def plot_pssar_line(scenario_name: str, avg_results: pd.DataFrame)
```

Plots a line chart of the average psSAR10g for different tissue groups.

**Arguments**:

- `scenario_name` - The name of the placement scenario.
- `avg_results` - DataFrame with average psSAR10g values for various tissues.

<a id="src.analysis.plotter.Plotter.plot_sar_distribution_boxplots"></a>

#### plot\_sar\_distribution\_boxplots

```python
def plot_sar_distribution_boxplots(scenario_name: str,
                                   scenario_results_df: pd.DataFrame)
```

Creates boxplots to show the distribution of SAR values for each metric.

**Arguments**:

- `scenario_name` - The name of the placement scenario.
- `scenario_results_df` - DataFrame with detailed results for the scenario.

<a id="src.analysis.plotter.Plotter.plot_far_field_distribution_boxplot"></a>

#### plot\_far\_field\_distribution\_boxplot

```python
def plot_far_field_distribution_boxplot(results_df: pd.DataFrame,
                                        metric: str = "SAR_whole_body")
```

Generates a boxplot for the distribution of a given metric in far-field results.

<a id="src.analysis.plotter.Plotter.plot_sar_heatmap"></a>

#### plot\_sar\_heatmap

```python
def plot_sar_heatmap(organ_df: pd.DataFrame, group_df: pd.DataFrame,
                     tissue_groups: dict)
```

Generates the combined heatmap for Min, Avg, and Max SAR.

<a id="src.analysis.plotter.Plotter.plot_peak_sar_heatmap"></a>

#### plot\_peak\_sar\_heatmap

```python
def plot_peak_sar_heatmap(organ_df: pd.DataFrame,
                          group_df: pd.DataFrame,
                          tissue_groups: dict,
                          value_col: str = "peak_sar_10g_mw_kg",
                          title: str = "Peak SAR")
```

Generates a combined heatmap for a given peak SAR metric.

<a id="src.analysis.strategies"></a>

# Module src.analysis.strategies

<a id="src.analysis.strategies.BaseAnalysisStrategy"></a>

## BaseAnalysisStrategy

```python
class BaseAnalysisStrategy(ABC)
```

Abstract base class for analysis strategies.

<a id="src.analysis.strategies.BaseAnalysisStrategy.__init__"></a>

#### \_\_init\_\_

```python
def __init__(config, phantom_name)
```

Initializes the analysis strategy.

**Arguments**:

- `config` _Config_ - The main configuration object.
- `phantom_name` _str_ - The name of the phantom being analyzed.

<a id="src.analysis.strategies.BaseAnalysisStrategy.get_results_base_dir"></a>

#### get\_results\_base\_dir

```python
@abstractmethod
def get_results_base_dir()
```

Returns the base directory where results for this strategy are stored.

<a id="src.analysis.strategies.BaseAnalysisStrategy.get_plots_dir"></a>

#### get\_plots\_dir

```python
@abstractmethod
def get_plots_dir()
```

Returns the directory where plots for this strategy should be saved.

<a id="src.analysis.strategies.BaseAnalysisStrategy.load_and_process_results"></a>

#### load\_and\_process\_results

```python
@abstractmethod
def load_and_process_results(analyzer)
```

Loads and processes all relevant simulation results for the analysis.

**Arguments**:

- `analyzer` _Analyzer_ - The main analyzer instance calling the strategy.

<a id="src.analysis.strategies.BaseAnalysisStrategy.get_normalization_factor"></a>

#### get\_normalization\_factor

```python
@abstractmethod
def get_normalization_factor(frequency_mhz, simulated_power_w)
```

Calculates the normalization factor to apply to SAR values.

**Arguments**:

- `frequency_mhz` _int_ - The simulation frequency in MHz.
- `simulated_power_w` _float_ - The input power from the simulation in Watts.
  

**Returns**:

- `float` - The calculated normalization factor.

<a id="src.analysis.strategies.BaseAnalysisStrategy.extract_data"></a>

#### extract\_data

```python
@abstractmethod
def extract_data(pickle_data, frequency_mhz, detailed_name, scenario_name,
                 sim_power, norm_factor)
```

Extracts and structures data from a single simulation's result files.

**Arguments**:

- `pickle_data` _dict_ - Data loaded from the .pkl result file.
- `frequency_mhz` _int_ - The simulation frequency.
- `detailed_name` _str_ - The detailed name of the placement or scenario.
- `scenario_name` _str_ - The general scenario name.
- `sim_power` _float_ - The simulated input power in Watts.
- `norm_factor` _float_ - The normalization factor to apply.
  

**Returns**:

- `tuple` - A tuple containing the main result entry (dict) and a list of organ-specific entries (list of dicts).

<a id="src.analysis.strategies.BaseAnalysisStrategy.apply_bug_fixes"></a>

#### apply\_bug\_fixes

```python
@abstractmethod
def apply_bug_fixes(result_entry)
```

Applies any necessary workarounds or fixes for known data inconsistencies.

**Arguments**:

- `result_entry` _dict_ - The data entry for a single simulation result.
  

**Returns**:

- `dict` - The corrected result entry.

<a id="src.analysis.strategies.BaseAnalysisStrategy.calculate_summary_stats"></a>

#### calculate\_summary\_stats

```python
@abstractmethod
def calculate_summary_stats(results_df)
```

Calculates summary statistics from the aggregated results DataFrame.

**Arguments**:

- `results_df` _pd.DataFrame_ - The DataFrame containing all aggregated simulation results.
  

**Returns**:

- `pd.DataFrame` - A DataFrame with summary statistics.

<a id="src.analysis.strategies.BaseAnalysisStrategy.generate_plots"></a>

#### generate\_plots

```python
@abstractmethod
def generate_plots(analyzer, plotter, results_df, all_organ_results_df)
```

Generates all plots relevant to this analysis strategy.

**Arguments**:

- `analyzer` _Analyzer_ - The main analyzer instance.
- `plotter` _Plotter_ - The plotter instance to use for generating plots.
- `results_df` _pd.DataFrame_ - The DataFrame with main aggregated results.
- `all_organ_results_df` _pd.DataFrame_ - The DataFrame with detailed organ-level results.

<a id="src.analysis.strategies.NearFieldAnalysisStrategy"></a>

## NearFieldAnalysisStrategy

```python
class NearFieldAnalysisStrategy(BaseAnalysisStrategy)
```

Analysis strategy for near-field simulations.

<a id="src.analysis.strategies.NearFieldAnalysisStrategy.get_results_base_dir"></a>

#### get\_results\_base\_dir

```python
def get_results_base_dir()
```

Returns the base directory for near-field results.

<a id="src.analysis.strategies.NearFieldAnalysisStrategy.get_plots_dir"></a>

#### get\_plots\_dir

```python
def get_plots_dir()
```

Returns the directory for saving near-field plots.

<a id="src.analysis.strategies.NearFieldAnalysisStrategy.load_and_process_results"></a>

#### load\_and\_process\_results

```python
def load_and_process_results(analyzer)
```

Iterates through near-field simulation results and processes each one.

<a id="src.analysis.strategies.NearFieldAnalysisStrategy.get_normalization_factor"></a>

#### get\_normalization\_factor

```python
def get_normalization_factor(frequency_mhz, simulated_power_w)
```

Calculates the normalization factor based on the target power defined in the antenna configuration.

**Arguments**:

- `frequency_mhz` _int_ - The simulation frequency in MHz.
- `simulated_power_w` _float_ - The input power from the simulation in Watts.
  

**Returns**:

- `float` - The calculated normalization factor. Returns 1.0 if normalization is not possible.

<a id="src.analysis.strategies.NearFieldAnalysisStrategy.extract_data"></a>

#### extract\_data

```python
def extract_data(pickle_data, frequency_mhz, placement_name, scenario_name,
                 sim_power, norm_factor)
```

Extracts and normalizes SAR data from a single near-field simulation result.

**Arguments**:

- `pickle_data` _dict_ - Data loaded from the .pkl result file.
- `frequency_mhz` _int_ - The simulation frequency.
- `placement_name` _str_ - The detailed name of the placement.
- `scenario_name` _str_ - The general scenario name (e.g., 'by_cheek').
- `sim_power` _float_ - The simulated input power in Watts.
- `norm_factor` _float_ - The normalization factor to apply to SAR values.
  

**Returns**:

- `tuple` - A tuple containing the main result entry (dict) and a list of organ-specific entries.

<a id="src.analysis.strategies.NearFieldAnalysisStrategy.apply_bug_fixes"></a>

#### apply\_bug\_fixes

```python
def apply_bug_fixes(result_entry)
```

Applies a workaround for a known issue where Head SAR is miscategorized as Trunk SAR.

**Arguments**:

- `result_entry` _dict_ - The data entry for a single simulation result.
  

**Returns**:

- `dict` - The corrected result entry.

<a id="src.analysis.strategies.NearFieldAnalysisStrategy.calculate_summary_stats"></a>

#### calculate\_summary\_stats

```python
def calculate_summary_stats(results_df)
```

Calculates summary statistics, including completion progress for each scenario.

**Arguments**:

- `results_df` _pd.DataFrame_ - The DataFrame containing all aggregated simulation results.
  

**Returns**:

- `pd.DataFrame` - A DataFrame with mean SAR values and a 'progress' column.

<a id="src.analysis.strategies.NearFieldAnalysisStrategy.generate_plots"></a>

#### generate\_plots

```python
def generate_plots(analyzer, plotter, results_df, all_organ_results_df)
```

Generates all plots for the near-field analysis.

This includes bar charts for average SAR, line plots for psSAR, and boxplots
for SAR distribution.

**Arguments**:

- `analyzer` _Analyzer_ - The main analyzer instance.
- `plotter` _Plotter_ - The plotter instance to use for generating plots.
- `results_df` _pd.DataFrame_ - The DataFrame with main aggregated results.
- `all_organ_results_df` _pd.DataFrame_ - The DataFrame with detailed organ-level results.

<a id="src.analysis.strategies.FarFieldAnalysisStrategy"></a>

## FarFieldAnalysisStrategy

```python
class FarFieldAnalysisStrategy(BaseAnalysisStrategy)
```

Analysis strategy for far-field simulations.

<a id="src.antenna"></a>

# Module src.antenna

<a id="src.antenna.Antenna"></a>

## Antenna

```python
class Antenna()
```

Manages antenna-specific properties and configurations.

<a id="src.antenna.Antenna.__init__"></a>

#### \_\_init\_\_

```python
def __init__(config: "Config", frequency_mhz: int)
```

Initializes the Antenna object.

**Arguments**:

- `config` - The configuration object containing antenna settings.
- `frequency_mhz` - The operating frequency in MHz.

<a id="src.antenna.Antenna.get_config_for_frequency"></a>

#### get\_config\_for\_frequency

```python
def get_config_for_frequency() -> dict
```

Gets the antenna configuration for the current frequency.

**Raises**:

- `ValueError` - If no configuration is defined for the frequency.
  

**Returns**:

  The antenna configuration dictionary.

<a id="src.antenna.Antenna.get_model_type"></a>

#### get\_model\_type

```python
def get_model_type() -> str
```

Gets the antenna model type (e.g., 'PIFA', 'IFA').

<a id="src.antenna.Antenna.get_source_entity_name"></a>

#### get\_source\_entity\_name

```python
def get_source_entity_name() -> str
```

Gets the name of the source entity in the CAD model.

<a id="src.antenna.Antenna.get_centered_antenna_path"></a>

#### get\_centered\_antenna\_path

```python
def get_centered_antenna_path(centered_antennas_dir: str) -> str
```

Constructs the path to the centered .sab antenna file.

**Arguments**:

- `centered_antennas_dir` - The directory for centered antenna files.
  

**Returns**:

  The absolute path to the centered antenna model file.

<a id="src.colors"></a>

# Module src.colors

<a id="src.colors.get_color"></a>

#### get\_color

```python
def get_color(log_type: str) -> str
```

Retrieves the colorama color code for a given log type.

**Arguments**:

- `log_type` - The type of log message (e.g., 'info', 'warning').
  

**Returns**:

  The colorama color code for the log type.

<a id="src.config"></a>

# Module src.config

<a id="src.config.deep_merge"></a>

#### deep\_merge

```python
def deep_merge(source: dict, destination: dict) -> dict
```

Recursively merges two dictionaries, overwriting destination with source values.

**Arguments**:

- `source` - The dictionary with values to merge.
- `destination` - The dictionary to be merged into.
  

**Returns**:

  The merged dictionary.

<a id="src.config.Config"></a>

## Config

```python
class Config()
```

Manages loading and access of hierarchical JSON configurations.

<a id="src.config.Config.__init__"></a>

#### \_\_init\_\_

```python
def __init__(base_dir: str, config_filename: str = "near_field_config.json")
```

Initializes the Config object by loading all relevant configuration files.

**Arguments**:

- `base_dir` - The base directory of the project.
- `config_filename` - The name of the main configuration file to load.

<a id="src.config.Config.get_setting"></a>

#### get\_setting

```python
def get_setting(path: str, default=None)
```

Retrieves a nested setting using a dot-separated path.

**Example**:

  `get_setting("simulation_parameters.number_of_point_sensors")`
  

**Arguments**:

- `path` - The dot-separated path to the setting.
- `default` - The default value to return if the setting is not found.
  

**Returns**:

  The value of the setting, or the default value.

<a id="src.config.Config.get_simulation_parameters"></a>

#### get\_simulation\_parameters

```python
def get_simulation_parameters() -> dict
```

Gets the 'simulation_parameters' dictionary.

<a id="src.config.Config.get