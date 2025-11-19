# UML Diagrams

These diagrams are generated from the Python sources under `goliat/` using Pyreverse (from Pylint). The generator script is [`scripts/generate_uml.py`](https://github.com/rwydaegh/goliat/blob/master/scripts/generate_uml.py).

<details>
<summary>Class Diagram</summary>

```kroki-plantuml
@startuml classes_GOLIAT
set namespaceSeparator none
class "Analyzer" as goliat.analysis.analyzer.Analyzer {
  all_organ_results : list
  all_results : list
  base_dir
  config : str
  phantom_name : str
  plotter
  results_base_dir
  strategy : str
  tissue_group_definitions : dict
  __init__(config: 'Config', phantom_name: str, strategy: 'BaseAnalysisStrategy')
  _convert_units_and_cache(results_df: pd.DataFrame, organ_results_df: pd.DataFrame) -> pd.DataFrame
  _export_reports(results_df: pd.DataFrame, all_organ_results_df: pd.DataFrame)
  _generate_plots(results_df: pd.DataFrame, all_organ_results_df: pd.DataFrame)
  _process_single_result(frequency_mhz: int, scenario_name: str, pos_name: str, orient_name: str)
  run_analysis()
}
class "Antenna" as goliat.antenna.Antenna {
  antenna_config
  config : str
  frequency_mhz : int
  __init__(config: 'Config', frequency_mhz: int)
  get_centered_antenna_path(centered_antennas_dir: str) -> str
  get_config_for_frequency() -> dict
  get_model_type() -> str
  get_source_entity_name() -> str
}
class "BaseAnalysisStrategy" as goliat.analysis.base_strategy.BaseAnalysisStrategy {
  base_dir
  config : str
  phantom_name : str
  __init__(config: 'Config', phantom_name: str)
  {abstract}apply_bug_fixes(result_entry: dict) -> dict
  {abstract}calculate_summary_stats(results_df: pd.DataFrame) -> pd.DataFrame
  {abstract}extract_data(pickle_data: dict, frequency_mhz: int, placement_name: str, scenario_name: str, sim_power: float, norm_factor: float) -> tuple[dict, list]
  {abstract}generate_plots(analyzer: 'Analyzer', plotter: 'Plotter', results_df: pd.DataFrame, all_organ_results_df: pd.DataFrame)
  {abstract}get_normalization_factor(frequency_mhz: int, simulated_power_w: float) -> float
  {abstract}get_plots_dir() -> str
  {abstract}get_results_base_dir() -> str
  {abstract}load_and_process_results(analyzer: 'Analyzer')
}
class "BaseSetup" as goliat.setups.base_setup.BaseSetup {
  config : str
  emfdtd
  model
  progress_logger : str
  s4l_v1
  verbose_logger : str
  __init__(config: 'Config', verbose_logger: 'Logger', progress_logger: 'Logger')
  _add_point_sensors(simulation: 'emfdtd.Simulation', sim_bbox_entity_name: str)
  _apply_simulation_time_and_termination(simulation: 'emfdtd.Simulation', sim_bbox_entity: 'model.Entity', frequency_mhz: int)
  _finalize_setup(project_manager: 'ProjectManager', simulation: 'emfdtd.Simulation', all_simulation_parts: list, frequency_mhz: int)
  _setup_solver_settings(simulation: 'emfdtd.Simulation')
  {abstract}run_full_setup(project_manager: 'ProjectManager')
}
class "BaseStudy" as goliat.studies.base_study.BaseStudy {
  base_dir
  config
  gui : Optional['QueueGUI']
  line_profiler : NoneType
  no_cache : bool
  profiler
  progress_logger : NoneType, RootLogger
  project_manager
  study_type : str
  verbose_logger : NoneType, RootLogger
  __init__(study_type: str, config_filename: Optional[str], gui: Optional['QueueGUI'], profiler, no_cache: bool)
  _check_for_stop_signal()
  _collect_result_files(project_dir: str) -> dict
  _execute_run_phase(simulation)
  _get_execution_control_flags() -> tuple[bool, bool, bool]
  _log_line_profiler_stats(task_name: str, lp: LineProfiler)
  _normalize_relative_path(project_dir: str) -> str
  {abstract}_run_study()
  _set_initial_profiler_phase(do_setup: bool, do_run: bool, do_extract: bool)
  _setup_line_profiler_if_needed(subtask_name: str, instance) -> tuple
  _should_reupload_results() -> bool
  _upload_files_to_server(files: dict, relative_path: str, assignment_id: str, server_url: str)
  _upload_results_if_assignment(project_dir: str)
  _validate_auto_cleanup_config(do_setup: bool, do_run: bool, do_extract: bool, auto_cleanup: list)
  _validate_execution_control(do_setup: bool, do_run: bool, do_extract: bool) -> bool
  _verify_and_update_metadata(stage: str)
  _verify_run_deliverables_before_extraction() -> bool
  end_stage_animation()
  run()
  start_stage_animation(task_name: str, end_value: int)
  subtask(task_name: str, instance_to_profile)
}
class "BatchGUI" as goliat.osparc_batch.gui.BatchGUI {
  button_layout
  cancel_jobs_requested
  force_stop_button
  print_progress_requested
  progress_button
  stop_and_cancel_button
  stop_run_requested
  tray_button
  tray_icon
  __init__()
  closeEvent(event)
  force_stop_run()
  hide_to_tray()
  init_ui()
  show_from_tray()
  stop_and_cancel_jobs()
  tray_icon_activated(reason)
}
class "BoundarySetup" as goliat.setups.boundary_setup.BoundarySetup {
  simulation : str
  __init__(config: 'Config', simulation: 'emfdtd.Simulation', verbose_logger: 'Logger', progress_logger: 'Logger')
  setup_boundary_conditions()
}
class "Cleaner" as goliat.extraction.cleaner.Cleaner {
  parent : str
  __init__(parent: 'ResultsExtractor')
  _delete_files(cleanup_types: list, file_patterns: dict) -> int
  _delete_single_file(file_path: str) -> bool
  cleanup_simulation_files()
}
class "ClockManager" as goliat.gui.components.clock_manager.ClockManager {
  gui : str
  __init__(gui: 'ProgressGUI') -> None
  update() -> None
}
class "ColorFormatter" as goliat.logging_manager.ColorFormatter {
  format(record: logging.LogRecord) -> str
}
class "Config" as goliat.config.core.Config {
  base_dir : str
  config
  config_path
  material_mapping
  material_mapping_path
  profiling_config
  profiling_config_path
  __getitem__(path: str)
  __init__(base_dir: str, config_filename: str, no_cache: bool)
  _load_config_with_inheritance(path: str) -> dict
  _load_json(path: str) -> dict
  _resolve_config_path(config_filename: str, base_path: str) -> str
  build_simulation_config(phantom_name: str, frequency_mhz: int, scenario_name: Optional[str], position_name: Optional[str], orientation_name: Optional[str], direction_name: Optional[str], polarization_name: Optional[str]) -> dict
  get_auto_cleanup_previous_results() -> list
  get_download_email() -> str
  get_material_mapping(phantom_name: str) -> dict
  get_only_write_input_file() -> bool
  get_osparc_credentials() -> dict
  get_profiling_config(study_type: str) -> dict
}
class "CustomFormatter" as goliat.logging_manager.CustomFormatter {
  format(record: logging.LogRecord) -> str
}
class "DataManager" as goliat.gui.components.data_manager.DataManager {
  data_dir : str
  overall_progress_file : str
  session_hash : str
  system_utilization_file : str
  time_remaining_file : str
  verbose_logger : Logger
  __init__(data_dir: str, verbose_logger: Logger) -> None
  _cleanup_old_data_files() -> None
  _initialize_files() -> None
  _write_csv_row(file_path: str, value: float, value_name: str) -> None
  write_overall_progress(progress_percent: float) -> None
  write_system_utilization(cpu_percent: float, ram_percent: float, gpu_percent: Optional[float], gpu_vram_percent: Optional[float]) -> None
  write_time_remaining(hours_remaining: float) -> None
}
class "ExecutionStrategy" as goliat.runners.execution_strategy.ExecutionStrategy {
  config : str
  gui : str
  profiler : str
  progress_logger : str
  project_manager : str
  project_path : str
  simulation : str
  verbose_logger : str
  __init__(config: 'Config', project_path: str, simulation: 's4l_v1.simulation.emfdtd.Simulation', profiler: 'Profiler', verbose_logger: 'LoggingMixin', progress_logger: 'LoggingMixin', project_manager: 'ProjectManager', gui: 'QueueGUI | None')
  _check_for_stop_signal() -> None
  {abstract}run() -> None
}
class "ExtractionContext" as goliat.results_extractor.ExtractionContext {
  config : str
  free_space : bool
  frequency_mhz : int
  gui : str
  orientation_name : str
  phantom_name : str
  position_name : str
  progress_logger : str
  scenario_name : str
  simulation : str
  study : str
  study_type : str
  verbose_logger : str
  __init__(self, config: 'Config', simulation: 's4l_v1.simulation.emfdtd.Simulation', phantom_name: str, frequency_mhz: int, scenario_name: str, position_name: str, orientation_name: str, study_type: str, verbose_logger: 'Logger', progress_logger: 'Logger', free_space: bool, gui: 'Optional[QueueGUI]', study: 'Optional[BaseStudy]') -> None
}
class "FarFieldAnalysisStrategy" as goliat.analysis.far_field_strategy.FarFieldAnalysisStrategy {
  apply_bug_fixes(result_entry: dict) -> dict
  calculate_summary_stats(results_df: pd.DataFrame) -> pd.DataFrame
  extract_data(pickle_data: dict, frequency_mhz: int, placement_name: str, scenario_name: str, sim_power: float, norm_factor: float) -> tuple[dict, list]
  generate_plots(analyzer: 'Analyzer', plotter: 'Plotter', results_df: pd.DataFrame, all_organ_results_df: pd.DataFrame)
  get_normalization_factor(frequency_mhz: int, simulated_power_w: float) -> float
  get_plots_dir() -> str
  get_results_base_dir() -> str
  load_and_process_results(analyzer: 'Analyzer')
}
class "FarFieldSetup" as goliat.setups.far_field_setup.FarFieldSetup {
  direction_name : str
  document
  frequency_mhz : int
  gui : NoneType
  phantom_name : str
  polarization_name : str
  profiler : str
  project_manager : str
  simulation_type : str
  __init__(config: 'Config', phantom_name: str, frequency_mhz: int, direction_name: str, polarization_name: str, project_manager: 'ProjectManager', verbose_logger: 'Logger', progress_logger: 'Logger', profiler: 'Profiler', gui)
  _create_or_get_simulation_bbox() -> 'model.Entity'
  _create_simulation_entity(bbox_entity: 'model.Entity') -> 'emfdtd.Simulation'
  run_full_setup(project_manager: 'ProjectManager') -> 'emfdtd.Simulation'
}
class "FarFieldStudy" as goliat.studies.far_field_study.FarFieldStudy {
  _iterate_far_field_simulations(phantoms: list, frequencies: list, incident_directions: list, polarizations: list, total_simulations: int, do_setup: bool, do_run: bool, do_extract: bool)
  _process_single_far_field_simulation(phantom_name: str, freq: int, direction_name: str, polarization_name: str, simulation_count: int, total_simulations: int, do_setup: bool, do_run: bool, do_extract: bool)
  _run_single_simulation(phantom_name: str, freq: int, direction_name: str, polarization_name: str, do_setup: bool, do_run: bool, do_extract: bool)
  _run_study()
}
class "GraphManager" as goliat.gui.components.graph_manager.GraphManager {
  gui : str
  __init__(gui: 'ProgressGUI') -> None
  update() -> None
}
class "GriddingSetup" as goliat.setups.gridding_setup.GriddingSetup {
  antenna : str
  frequency_mhz : int | None
  placement_name : str
  simulation : str
  units
  __init__(config: 'Config', simulation: 'emfdtd.Simulation', placement_name: str, antenna: 'Antenna', verbose_logger: 'Logger', progress_logger: 'Logger', frequency_mhz: int | None)
  _apply_subgridding(subgridding_config: dict, antenna_components: dict, subgridded_components: list)
  _find_simulation_bbox_entity(sim_bbox_name: str)
  _get_manual_grid_resolution(gridding_params: dict, global_gridding_params: dict) -> tuple[float, str]
  _get_simulation_bbox_name() -> str
  _setup_automatic_component_grids(gridding_config: dict, antenna_components: dict)
  _setup_automatic_grid(sim_bbox_entity, global_gridding_params: dict)
  _setup_main_grid()
  _setup_manual_component_grids(gridding_config: dict, antenna_components: dict, subgridded_components: list)
  _setup_manual_grid(sim_bbox_entity, gridding_params: dict, global_gridding_params: dict)
  _setup_padding(padding_params: dict)
  _setup_subgrids(antenna_components: dict)
  _validate_all_per_frequency_grids(per_freq_gridding: dict | None)
  _validate_grid_size(grid_size_mm: float, source: str)
  setup_gridding(antenna_components: dict | None)
}
class "HTTPClient" as goliat.utils.http_client.HTTPClient {
  gui : NoneType
  machine_id : str
  progress_logger : Logger
  server_url
  verbose_logger : Logger
  __init__(server_url: str, machine_id: str, logger: logging.Logger) -> None
  _handle_exception(e: Exception, message_type: str) -> None
  post_gui_screenshots(screenshots: Dict[str, bytes]) -> bool
  post_gui_update(message: Dict[str, Any]) -> bool
  post_heartbeat(system_info: Optional[Dict[str, Any]]) -> bool
}
class "ISolveManualStrategy" as goliat.runners.isolve_manual_strategy.ISolveManualStrategy {
  current_isolve_process : NoneType, Popen
  current_process_manager : NoneType
  __init__()
  _check_for_memory_error_and_exit(detected_errors: list, stderr_output: str) -> None
  _cleanup() -> None
  _handle_execution_exception(e: Exception, process_manager: ISolveProcessManager | None, detected_errors: list, retry_handler: RetryHandler, output_parser: ISolveOutputParser, keep_awake_handler: KeepAwakeHandler) -> bool
  _handle_process_failure(process_manager: ISolveProcessManager, return_code: int, detected_errors: list, stderr_output: str, retry_handler: RetryHandler, output_parser: ISolveOutputParser, keep_awake_handler: KeepAwakeHandler) -> bool
  _monitor_running_process(process_manager: ISolveProcessManager, output_parser: ISolveOutputParser, keep_awake_handler: KeepAwakeHandler, detected_errors: list) -> None
  _prepare_for_retry(retry_handler: RetryHandler, output_parser: ISolveOutputParser, keep_awake_handler: KeepAwakeHandler) -> None
  _prepare_isolve_command() -> list[str]
  _process_output_line(line: str, output_parser: ISolveOutputParser, keep_awake_handler: KeepAwakeHandler, detected_errors: list) -> None
  _process_remaining_output(process_manager: ISolveProcessManager, output_parser: ISolveOutputParser, detected_errors: list) -> None
  run() -> None
}
class "ISolveOutputParser" as goliat.runners.isolve_output_parser.ISolveOutputParser {
  logged_milestones : Set[int]
  progress_logger : str
  progress_pattern
  verbose_logger : str
  __init__(verbose_logger: 'Logger', progress_logger: 'Logger')
  _extract_progress(line: str) -> Optional[ProgressInfo]
  _format_time_remaining(time_str: str) -> str
  _is_error_line(line: str) -> bool
  log_milestone(progress_info: ProgressInfo) -> None
  parse_line(line: str) -> ParsedLine
  reset_milestones() -> None
  should_log_milestone(percentage: int) -> bool
}
class "ISolveProcessManager" as goliat.runners.isolve_process_manager.ISolveProcessManager {
  _is_running : bool
  command : List[str]
  gui : Optional['QueueGUI']
  output_queue : Optional[Queue]
  process : NoneType, Optional[subprocess.Popen]
  progress_logger : str
  reader_thread : Optional[threading.Thread]
  verbose_logger : str
  __init__(command: List[str], gui: Optional['QueueGUI'], verbose_logger: 'Logger', progress_logger: 'Logger')
  check_stop_signal() -> None
  cleanup() -> None
  get_return_code() -> Optional[int]
  is_running() -> bool
  read_all_remaining_lines() -> List[str]
  read_available_lines() -> List[str]
  read_stderr() -> str
  start() -> None
  terminate(timeout: float) -> None
}
class "KeepAwakeHandler" as goliat.runners.keep_awake_handler.KeepAwakeHandler {
  config : str
  triggered : bool
  __init__(config: 'Config')
  reset() -> None
  trigger_before_retry() -> None
  trigger_on_progress() -> None
}
class "LoggingMixin" as goliat.logging_manager.LoggingMixin {
  gui : Optional['QueueGUI']
  progress_logger : Logger
  verbose_logger : Logger
  _log(message: str, level: str, log_type: str)
}
class "MachineIdDetector" as goliat.gui.components.machine_id_detector.MachineIdDetector {
  detect(verbose_logger: Logger) -> Optional[str]
}
class "MaterialSetup" as goliat.setups.material_setup.MaterialSetup {
  XCoreModeling
  antenna : str
  database
  free_space : bool
  phantom_name : str
  simulation : str
  __init__(config: 'Config', simulation: 'emfdtd.Simulation', antenna: 'Antenna', phantom_name: str, verbose_logger: 'Logger', progress_logger: 'Logger', free_space: bool)
  _assign_antenna_materials(antenna_components: dict)
  _assign_phantom_materials()
  assign_materials(antenna_components: dict | None, phantom_only: bool)
}
class "MessageSanitizer" as goliat.utils.message_sanitizer.MessageSanitizer {
  sanitize(message: Dict[str, Any]) -> Dict[str, Any]
}
class "NearFieldAnalysisStrategy" as goliat.analysis.near_field_strategy.NearFieldAnalysisStrategy {
  calculate_summary_stats(results_df: pd.DataFrame) -> pd.DataFrame
  extract_data(pickle_data: dict, frequency_mhz: int, placement_name: str, scenario_name: str, sim_power: float, norm_factor: float) -> tuple[dict, list]
  generate_plots(analyzer: 'Analyzer', plotter: 'Plotter', results_df: pd.DataFrame, all_organ_results_df: pd.DataFrame)
  get_normalization_factor(frequency_mhz: int, simulated_power_w: float) -> float
  get_plots_dir() -> str
  get_results_base_dir() -> str
  load_and_process_results(analyzer: 'Analyzer')
}
class "NearFieldSetup" as goliat.setups.near_field_setup.NearFieldSetup {
  XCoreModeling
  antenna : str
  base_placement_name : str
  document
  free_space : bool
  frequency_mhz : int
  gui : NoneType
  orientation_name : str
  phantom_name : str
  placement_name : str
  position_name : str
  profiler : str
  __init__(config: 'Config', phantom_name: str, frequency_mhz: int, scenario_name: str, position_name: str, orientation_name: str, antenna: 'Antenna', verbose_logger: 'Logger', progress_logger: 'Logger', profiler: 'Profiler', gui, free_space: bool)
  _align_simulation_with_phone()
  _create_simulation_bbox()
  _find_touching_angle() -> float
  _get_antenna_components() -> dict
  _handle_phantom_rotation(placement_setup: 'PlacementSetup')
  _setup_bounding_boxes()
  _setup_simulation_entity() -> 'emfdtd.Simulation'
  run_full_setup(project_manager: 'ProjectManager', lock) -> 'emfdtd.Simulation'
}
class "NearFieldStudy" as goliat.studies.near_field_study.NearFieldStudy {
  _calculate_total_simulations(phantoms: list, frequencies, all_scenarios: dict) -> int
  _iterate_near_field_simulations(phantoms: list, frequencies, all_scenarios: dict, total_simulations: int, do_setup: bool, do_run: bool, do_extract: bool)
  _iterate_scenarios_for_frequency(phantom_name: str, freq: int, placements_config: dict, all_scenarios: dict, simulation_count: int, total_simulations: int, do_setup: bool, do_run: bool, do_extract: bool) -> int
  _process_single_near_field_simulation(phantom_name: str, freq: int, scenario_name: str, pos_name: str, orient_name: str, simulation_count: int, total_simulations: int, do_setup: bool, do_run: bool, do_extract: bool)
  _run_placement(phantom_name: str, freq: int, scenario_name: str, position_name: str, orientation_name: str, do_setup: bool, do_run: bool, do_extract: bool)
  _run_study()
  _set_initial_profiler_phase(do_setup: bool, do_run: bool, do_extract: bool)
}
class "NumpyArrayEncoder" as goliat.extraction.json_encoder.NumpyArrayEncoder {
  default(o: Any) -> Any
}
class "OSPARCDirectStrategy" as goliat.runners.osparc_direct_strategy.OSPARCDirectStrategy {
  server_name : str
  __init__(server_name: str)
  run() -> None
}
class "OverallProgressPlot" as goliat.gui.components.plots.overall_progress_plot.OverallProgressPlot {
  ax : Axes
  canvas : FigureCanvasQTAgg
  data : List[Tuple[datetime, float]]
  figure : Figure
  max_progress_seen : float
  __init__() -> None
  _refresh() -> None
  _setup() -> None
  add_data_point(timestamp: datetime, progress_percent: float) -> None
}
class "ParsedLine" as goliat.runners.isolve_output_parser.ParsedLine {
  error_message : Optional[str]
  has_progress : bool
  is_error : bool
  progress_info : Optional[ProgressInfo]
  raw_line : str
  __init__(self, raw_line: str, is_error: bool, error_message: Optional[str], has_progress: bool, progress_info: Optional[ProgressInfo]) -> None
}
class "PhantomSetup" as goliat.setups.phantom_setup.PhantomSetup {
  XCoreModeling
  data
  model
  phantom_name : str
  __init__(config: 'Config', phantom_name: str, verbose_logger: 'Logger', progress_logger: 'Logger')
  _log(message: str, level: str, log_type: str)
  ensure_phantom_is_loaded() -> bool
}
class "PieChartsManager" as goliat.gui.components.plots.pie_charts_manager.PieChartsManager {
  axes : List[_Axes]
  canvas : FigureCanvasQTAgg
  figure : Figure
  __init__() -> None
  _format_task_label(subtask_key: str) -> str
  _group_small_slices(labels: List[str], sizes: List[float], threshold_percent: float) -> Tuple[List[str], List[float]]
  _setup() -> None
  update(profiler: 'Profiler') -> None
}
class "PlacementSetup" as goliat.setups.placement_setup.PlacementSetup {
  XCoreMath
  antenna : str
  base_placement_name : str
  free_space : bool
  frequency_mhz : int
  orientation_name : str
  orientation_rotations : list
  phantom_name : str
  placement_name : str
  position_name : str
  __init__(config: 'Config', phantom_name: str, frequency_mhz: int, base_placement_name: str, position_name: str, orientation_name: str, antenna: 'Antenna', verbose_logger: 'Logger', progress_logger: 'Logger', free_space: bool)
  _get_placement_details() -> tuple
  _get_speaker_reference(ground_entities, upright_transform)
  place_antenna()
}
class "Plotter" as goliat.analysis.plotter.Plotter {
  plots_dir : str
  __init__(plots_dir: str)
  _normalize_axes_array(axes_array, n_freqs: int) -> list
  _plot_balance_distribution(power_df: pd.DataFrame)
  _plot_balance_heatmap(power_df: pd.DataFrame)
  _plot_heatmap(fig, ax, data: pd.DataFrame, title: str, cbar: bool, cbar_ax)
  _plot_power_components(power_df: pd.DataFrame)
  _plot_single_frequency_components(ax, freq_data: pd.DataFrame, available_cols: list, freq: int)
  _prepare_power_data(results_df: pd.DataFrame) -> pd.DataFrame | None
  plot_average_sar_bar(scenario_name: str, avg_results: pd.DataFrame, progress_info: pd.Series)
  plot_far_field_distribution_boxplot(results_df: pd.DataFrame, metric: str)
  plot_peak_sar_heatmap(organ_df: pd.DataFrame, group_df: pd.DataFrame, tissue_groups: dict, value_col: str, title: str)
  plot_peak_sar_line(summary_stats: pd.DataFrame)
  plot_power_balance_overview(results_df: pd.DataFrame)
  plot_pssar_line(scenario_name: str, avg_results: pd.DataFrame)
  plot_sar_distribution_boxplots(scenario_name: str, scenario_results_df: pd.DataFrame)
  plot_sar_heatmap(organ_df: pd.DataFrame, group_df: pd.DataFrame, tissue_groups: dict)
  plot_whole_body_sar_bar(avg_results: pd.DataFrame)
}
class "PostSimulationHandler" as goliat.runners.post_simulation_handler.PostSimulationHandler {
  document
  profiler : str
  progress_logger : str
  project_path : str
  verbose_logger : str
  __init__(project_path: str, profiler: 'Profiler', verbose_logger: 'Logger', progress_logger: 'Logger')
  wait_and_reload() -> None
}
class "PowerExtractor" as goliat.extraction.power_extractor.PowerExtractor {
  config
  document
  frequency_mhz
  gui
  parent : str
  placement_name
  progress_logger
  results_data : dict
  simulation
  study_type
  verbose_logger
  __init__(parent: 'ResultsExtractor', results_data: dict)
  _extract_far_field_power(simulation_extractor: 'analysis.Extractor')
  _extract_near_field_power(simulation_extractor: 'analysis.Extractor')
  extract_input_power(simulation_extractor: 'analysis.Extractor')
  extract_power_balance(simulation_extractor: 'analysis.Extractor')
}
class "Profiler" as goliat.profiler.Profiler {
  completed_phases : set
  completed_simulations : int
  completed_stages_in_phase : int
  config_path : str
  current_phase : NoneType, str
  current_project : int
  execution_control : dict
  phase_skipped : bool
  phase_start_time : NoneType
  phase_weights : dict
  profiling_config : dict
  run_phase_total_duration : int
  start_time
  study_type : str
  subtask_stack : list
  subtask_times : defaultdict
  total_projects : int
  total_simulations : int
  total_stages_in_phase : int
  __init__(execution_control: dict, profiling_config: dict, study_type: str, config_path: str)
  _calculate_phase_weights() -> dict
  _get_smart_phase_estimate(phase: str) -> float
  complete_run_phase()
  end_stage()
  get_phase_subtasks(phase_name: str) -> list
  get_subtask_estimate(task_name: str) -> float
  get_time_remaining(current_stage_progress: float) -> float
  get_weighted_progress(phase_name: str, phase_progress_ratio: float) -> float
  save_estimates()
  set_current_project(project_index: int)
  set_project_scope(total_projects: int)
  set_total_simulations(total: int)
  simulation_completed()
  start_stage(phase_name: str, total_stages: int)
  subtask(task_name: str)
  update_and_save_estimates()
}
class "Profiler" as goliat.utils.core.Profiler {
  completed_runs : int
  config_path : str
  current_run_start_time : NoneType
  profiling_config
  run_times : list
  start_time
  study_type : str
  total_runs : int
  __init__(config_path: str, study_type: str)
  _load_config() -> dict
  end_run()
  get_average_run_time() -> float
  get_elapsed() -> float
  get_time_remaining() -> float
  save_estimates()
  start_run()
  start_study(total_runs: int)
  subtask(name: str)
}
class "ProgressAnimation" as goliat.gui.components.progress_animation.ProgressAnimation {
  active : bool
  debug : bool
  duration : float
  end_value : int
  progress_bar
  start_time : float
  start_value : int
  timer
  __init__(progress_bar: 'QProgressBar', timer: 'QTimer', debug: bool) -> None
  {abstract}_log(message: str) -> None
  start(estimated_duration: float, end_step: int) -> None
  stop() -> None
  update() -> None
}
class "ProgressGUI" as goliat.gui.progress_gui.ProgressGUI {
  DEBUG : bool
  animation_timer
  clock_manager
  clock_timer
  current_simulation_count : int
  data_manager
  gpu_available : bool
  graph_manager
  graph_timer
  init_window_title : str
  machine_id
  process : Process
  profiler : Optional['Profiler']
  profiler_phase : Optional[str]
  progress_animation
  progress_logger : Logger
  progress_manager
  progress_sync_timer
  queue
  queue_handler
  queue_timer
  server_url : str
  start_time : float
  status_manager
  stop_event : Event
  study_had_errors : bool
  study_is_finished : bool
  total_simulations : int
  total_steps_for_stage : int
  tray_manager
  utilization_manager
  utilization_timer
  verbose_logger : Logger
  web_bridge_manager
  __init__(queue: Queue, stop_event: Event, process: Process, init_window_title: str) -> None
  _initialize_animation() -> None
  _initialize_components() -> None
  _initialize_managers() -> None
  _initialize_system_monitoring() -> None
  _setup_timers() -> None
  _update_web_status(connected: bool, message: str) -> None
  closeEvent(event: Any) -> None
  end_stage_animation() -> None
  hide_to_tray() -> None
  show_from_tray() -> None
  start_stage_animation(estimated_duration: float, end_step: int) -> None
  stop_study() -> None
  study_finished(error: bool) -> None
  update_animation() -> None
  update_clock() -> None
  update_graphs() -> None
  update_overall_progress(current_step: float, total_steps: int) -> None
  update_simulation_details(sim_count: int, total_sims: int, details: str) -> None
  update_stage_progress(stage_name: str, current_step: int, total_steps: int, sub_stage: str) -> None
  update_status(message: str, log_type: str) -> None
  update_utilization() -> None
}
class "ProgressInfo" as goliat.runners.isolve_output_parser.ProgressInfo {
  mcells_per_sec : str
  percentage : int
  time_remaining : str
  __init__(self, percentage: int, time_remaining: str, mcells_per_sec: str) -> None
}
class "ProgressManager" as goliat.gui.components.progress_manager.ProgressManager {
  gui : str
  __init__(gui: 'ProgressGUI') -> None
  update_overall(current_step: float, total_steps: int) -> None
  update_simulation_details(sim_count: int, total_sims: int, details: str) -> None
  update_stage(stage_name: str, current_step: int, total_steps: int, sub_stage: str) -> None
}
class "<color:red>ProjectCorruptionError</color>" as goliat.project_manager.ProjectCorruptionError {
}
class "ProjectManager" as goliat.project_manager.ProjectManager {
  config : str
  document
  execution_control : dict
  gui : Optional['QueueGUI']
  no_cache : bool
  progress_logger : str
  project_path : NoneType, Optional[str]
  verbose_logger : str
  __init__(config: 'Config', verbose_logger: 'Logger', progress_logger: 'Logger', gui: Optional['QueueGUI'], no_cache: bool)
  _build_project_path(study_type: str, phantom_name: str, frequency_mhz: int, placement_name: str) -> tuple[str, str]
  _check_auto_cleanup_scenario(extract_done: bool) -> bool
  _check_extract_deliverables(project_dir: str, setup_timestamp: float) -> bool
  _check_run_deliverables(project_dir: str, project_filename: str, setup_timestamp: float, extract_done: bool) -> bool
  _generate_config_hash(config_dict: dict) -> str
  _get_deliverables_status(project_dir: str, project_filename: str, setup_timestamp: float) -> dict
  _is_valid_smash_file() -> bool
  _log_status_summary(status: dict)
  _normalize_status(status: dict) -> dict
  _parse_setup_timestamp(metadata: dict) -> Optional[float]
  _validate_h5_file(h5_file_path: str, results_dir: str, setup_timestamp: float) -> bool
  _validate_placement_params(study_type: str, phantom_name: str, frequency_mhz: int, scenario_name: Optional[str], position_name: Optional[str], orientation_name: Optional[str]) -> None
  _verify_config_hash(metadata: dict, surgical_config: dict, meta_path: str) -> bool
  _verify_deliverables(path_to_check: str, setup_timestamp: float) -> dict
  _verify_project_file(smash_path: Optional[str]) -> Tuple[bool, Optional[str]]
  cleanup()
  close()
  create_new()
  create_or_open_project(phantom_name: str, frequency_mhz: int, scenario_name: Optional[str], position_name: Optional[str], orientation_name: Optional[str]) -> dict
  get_setup_timestamp_from_metadata(meta_path: str) -> Optional[float]
  open()
  reload_project()
  save()
  update_simulation_metadata(meta_path: str, run_done: Optional[bool], extract_done: Optional[bool])
  verify_simulation_metadata(meta_path: str, surgical_config: dict, smash_path: Optional[str]) -> dict
  write_simulation_metadata(meta_path: str, surgical_config: dict, update_setup_timestamp: bool)
}
class "QueueGUI" as goliat.gui.queue_gui.QueueGUI {
  profiler : str
  progress_logger : Logger
  queue
  stop_event : Event
  verbose_logger : Logger
  __init__(queue: Queue, stop_event: Event, profiler: 'Profiler', progress_logger: Logger, verbose_logger: Logger) -> None
  end_stage_animation() -> None
  is_stopped() -> bool
  log(message: str, level: str, log_type: str) -> None
  {abstract}process_events() -> None
  start_stage_animation(task_name: str, end_value: int) -> None
  update_overall_progress(current_step: float, total_steps: int) -> None
  update_profiler() -> None
  update_simulation_details(sim_count: int, total_sims: int, details: str) -> None
  update_stage_progress(stage_name: str, current_step: int, total_steps: int, sub_stage: str) -> None
}
class "QueueHandler" as goliat.gui.components.queue_handler.QueueHandler {
  _MESSAGE_HANDLERS : dict
  gui : str
  __init__(gui_instance: 'ProgressGUI') -> None
  _handle_end_animation(msg: Dict[str, Any]) -> None
  _handle_fatal_error(msg: Dict[str, Any]) -> None
  _handle_finished(msg: Dict[str, Any]) -> None
  _handle_overall_progress(msg: Dict[str, Any]) -> None
  _handle_profiler_update(msg: Dict[str, Any]) -> None
  _handle_sim_details(msg: Dict[str, Any]) -> None
  _handle_stage_progress(msg: Dict[str, Any]) -> None
  _handle_start_animation(msg: Dict[str, Any]) -> None
  _handle_status(msg: Dict[str, Any]) -> None
  process_queue() -> None
}
class "Reporter" as goliat.extraction.reporter.Reporter {
  parent : str
  __init__(parent: 'ResultsExtractor')
  _build_html_content(df: pd.DataFrame, tissue_groups: dict, group_sar_stats: dict, results_data: dict) -> str
  _get_results_dir() -> str
  _save_html_report(results_dir: str, df: pd.DataFrame, tissue_groups: dict, group_sar_stats: dict, results_data: dict)
  _save_pickle_report(results_dir: str, df: pd.DataFrame, tissue_groups: dict, group_sar_stats: dict, results_data: dict)
  save_reports(df: pd.DataFrame, tissue_groups: dict, group_sar_stats: dict, results_data: dict)
}
class "ResonanceExtractor" as goliat.extraction.resonance_extractor.ResonanceExtractor {
  config
  document
  frequency_mhz
  parent : str
  progress_logger
  results_data : dict
  verbose_logger
  __init__(parent: 'ResultsExtractor', results_data: dict)
  extract_resonance_frequency(simulation_extractor: 'analysis.Extractor')
}
class "ResultsExtractor" as goliat.results_extractor.ResultsExtractor {
  analysis
  config
  document
  free_space
  frequency_mhz
  gui
  orientation_name
  phantom_name
  placement_name : str
  progress_logger
  simulation
  study
  study_type
  units
  verbose_logger
  __init__(context: ExtractionContext)
  _save_json_results(results_data: dict)
  extract()
  from_params(config: 'Config', simulation: 's4l_v1.simulation.emfdtd.Simulation', phantom_name: str, frequency_mhz: int, scenario_name: str, position_name: str, orientation_name: str, study_type: str, verbose_logger: 'Logger', progress_logger: 'Logger', free_space: bool, gui: 'Optional[QueueGUI]', study: 'Optional[BaseStudy]') -> 'ResultsExtractor'
  get_deliverable_filenames() -> dict
}
class "RetryHandler" as goliat.runners.retry_handler.RetryHandler {
  attempt_number : int
  progress_logger : str
  __init__(progress_logger: 'Logger')
  get_attempt_number() -> int
  record_attempt() -> None
  reset() -> None
  should_retry(return_code: Optional[int], detected_errors: list) -> bool
}
class "SarExtractor" as goliat.extraction.sar_extractor.SarExtractor {
  analysis
  config
  document
  gui
  parent : str
  phantom_name
  placement_name
  progress_logger
  results_data : dict
  simulation
  tissue_grouper
  units
  verbose_logger
  __init__(parent: 'ResultsExtractor', results_data: dict)
  _calculate_group_sar(df: pd.DataFrame, tissue_groups: dict) -> dict
  _create_sar_dataframe(results: object) -> pd.DataFrame
  _evaluate_sar_statistics(em_sensor_extractor: 'analysis.Extractor') -> object | None
  _setup_em_sensor_extractor(simulation_extractor: 'analysis.Extractor') -> 'analysis.Extractor'
  _store_all_regions_sar(df: pd.DataFrame) -> None
  _store_group_sar_results(group_sar_stats: dict) -> None
  _store_temporary_data(df: pd.DataFrame, tissue_groups: dict, group_sar_stats: dict) -> None
  extract_peak_sar_details(em_sensor_extractor: 'analysis.Extractor')
  extract_sar_statistics(simulation_extractor: 'analysis.Extractor')
}
class "ScreenshotCapture" as goliat.gui.components.screenshot_capture.ScreenshotCapture {
  gui : str
  verbose_logger : NoneType, RootLogger
  __init__(gui: 'ProgressGUI') -> None
  _compress_to_jpeg(pixmap: Any, quality: int) -> Optional[bytes]
  capture_all_tabs() -> Dict[str, bytes]
}
class "SensorExtractor" as goliat.extraction.sensor_extractor.SensorExtractor {
  parent : str
  progress_logger
  results_data : dict
  verbose_logger
  __init__(parent: 'ResultsExtractor', results_data: dict)
  _save_plot(fig, ax)
  extract_point_sensor_data(simulation_extractor: 'analysis.Extractor')
}
class "Sim4LifeAPIStrategy" as goliat.runners.sim4life_api_strategy.Sim4LifeAPIStrategy {
  server_id : str | None
  __init__(server_id: str | None)
  run() -> None
}
class "SimulationRunner" as goliat.simulation_runner.SimulationRunner {
  config : str
  current_strategy : NoneType, Optional['ExecutionStrategy']
  document
  gui : str
  profiler : str
  progress_logger : str
  project_manager : str
  project_path : str
  simulation : str
  verbose_logger : str
  __init__(config: 'Config', project_path: str, simulation: 's4l_v1.simulation.emfdtd.Simulation', profiler: 'Profiler', verbose_logger: 'Logger', progress_logger: 'Logger', project_manager: 'ProjectManager', gui: 'Optional[QueueGUI]')
  _cleanup_isolve_process()
  _create_execution_strategy(server_name: Optional[str]) -> ExecutionStrategy
  _get_server_id(server_name: str) -> Optional[str]
  run()
}
class "SourceSetup" as goliat.setups.source_setup.SourceSetup {
  antenna : str
  free_space : bool
  frequency_mhz : int
  simulation : str
  units
  __init__(config: 'Config', simulation: 'emfdtd.Simulation', frequency_mhz: int, antenna: 'Antenna', verbose_logger: 'Logger', progress_logger: 'Logger', free_space: bool)
  setup_source_and_sensors(antenna_components: dict)
}
class "StatusManager" as goliat.gui.components.status_manager.StatusManager {
  color_map : dict[str, str]
  error_count : int
  warning_count : int
  __init__() -> None
  format_message(message: str, log_type: str) -> str
  get_color(log_type: str) -> str
  get_error_summary(web_connected: bool) -> str
  record_log(log_type: str) -> None
}
class "<color:red>StudyCancelledError</color>" as goliat.utils.core.StudyCancelledError {
}
class "SystemMonitor" as goliat.gui.components.system_monitor.SystemMonitor {
  get_cpu_cores() -> int
  get_cpu_utilization() -> float
  get_gpu_name() -> Optional[str]
  get_gpu_utilization() -> Optional[float]
  get_gpu_vram_utilization() -> Optional[Tuple[float, float]]
  get_ram_utilization() -> Tuple[float, float]
  get_ram_utilization_detailed() -> Tuple[float, float, float]
  get_total_ram_gb() -> float
  is_gpu_available() -> bool
}
class "SystemUtilizationPlot" as goliat.gui.components.plots.system_utilization_plot.SystemUtilizationPlot {
  ax : Axes
  canvas : FigureCanvasQTAgg
  cpu_cores : int
  cpu_data : List[Tuple[datetime, float]]
  figure : Figure
  gpu_available : bool
  gpu_data : List[Tuple[datetime, Optional[float]]]
  gpu_name : NoneType, Optional[str]
  gpu_vram_data : List[Tuple[datetime, Optional[float]]]
  ram_data : List[Tuple[datetime, float]]
  total_gpu_vram_gb : float
  total_ram_gb : float
  __init__() -> None
  _refresh() -> None
  _setup() -> None
  add_data_point(timestamp: datetime, cpu_percent: float, ram_percent: float, gpu_percent: Optional[float], gpu_vram_percent: Optional[float], cpu_cores: int, total_ram_gb: float, gpu_name: Optional[str], total_gpu_vram_gb: float) -> None
}
class "TimeRemainingPlot" as goliat.gui.components.plots.time_remaining_plot.TimeRemainingPlot {
  ax : Axes
  canvas : FigureCanvasQTAgg
  data : List[Tuple[datetime, float]]
  figure : Figure
  max_time_remaining_seen : float
  __init__() -> None
  _refresh() -> None
  _setup() -> None
  add_data_point(timestamp: datetime, hours_remaining: float) -> None
}
class "TimingsTable" as goliat.gui.components.timings_table.TimingsTable {
  table
  __init__(table_widget: QTableWidget) -> None
  _setup_table() -> None
  update(profiler: 'Profiler') -> None
}
class "TissueGrouper" as goliat.extraction.tissue_grouping.TissueGrouper {
  config : str
  logger : str
  phantom_name : str
  __init__(config: 'Config', phantom_name: str, logger: 'LoggingMixin')
  _group_from_config(material_mapping: dict, available_tissues: list[str]) -> dict[str, list[str]]
  group_tissues(available_tissues: list[str]) -> dict[str, list[str]]
}
class "TrayManager" as goliat.gui.components.tray_manager.TrayManager {
  parent
  tray_icon
  __init__(parent_widget: QWidget, show_callback: Callable[[], None], close_callback: Callable[[], None]) -> None
  _tray_icon_activated(reason: QSystemTrayIcon.ActivationReason, show_callback: Callable[[], None]) -> None
  hide() -> None
  is_visible() -> bool
  show() -> None
}
class "UIBuilder" as goliat.gui.components.ui_builder.UIBuilder {
  STYLESHEET : str
  _build_buttons(gui_instance: 'ProgressGUI', main_layout: QVBoxLayout) -> None
  _build_overall_progress_tab(gui_instance: 'ProgressGUI') -> None
  _build_piecharts_tab(gui_instance: 'ProgressGUI') -> None
  _build_progress_tab(gui_instance: 'ProgressGUI', status_manager: 'StatusManager') -> None
  _build_system_utilization_tab(gui_instance: 'ProgressGUI') -> None
  _build_time_remaining_tab(gui_instance: 'ProgressGUI') -> None
  _build_timings_tab(gui_instance: 'ProgressGUI') -> None
  build(gui_instance: 'ProgressGUI', status_manager: 'StatusManager') -> None
  get_icon_path() -> str
}
class "UtilizationManager" as goliat.gui.components.utilization_manager.UtilizationManager {
  _last_cpu_percent : float
  _last_gpu_percent : NoneType, Optional[float]
  _last_gpu_vram_percent : NoneType, Optional[float]
  _last_ram_percent : float
  gui : str
  __init__(gui: 'ProgressGUI') -> None
  update() -> None
  update_plot() -> None
}
class "WebBridgeManager" as goliat.gui.components.web_bridge_manager.WebBridgeManager {
  gui : str
  machine_id : Optional[str]
  screenshot_capture : Optional[Any]
  screenshot_timer : Optional[Any]
  server_url : str
  web_bridge : Optional[Any]
  __init__(gui: 'ProgressGUI', server_url: str, machine_id: Optional[str]) -> None
  _capture_and_send_screenshots() -> None
  _initialize_screenshot_capture() -> None
  initialize() -> None
  send_finished(error: bool) -> None
  stop() -> None
  sync_progress() -> None
}
class "WebGUIBridge" as goliat.utils.gui_bridge.WebGUIBridge {
  _system_info : Optional[Dict[str, Any]]
  connection_callback : Optional[Callable[[bool], None]]
  executor : Optional[ThreadPoolExecutor]
  gui : NoneType
  http_client
  internal_queue : Queue
  is_connected : bool
  last_heartbeat_success : bool
  machine_id : str
  progress_logger : NoneType, RootLogger
  running : bool
  server_url
  thread : Optional[threading.Thread]
  throttle_interval : float
  verbose_logger : NoneType, RootLogger
  __init__(server_url: str, machine_id: str, throttle_hz: float)
  _forward_loop() -> None
  _send_heartbeat(system_info: Optional[Dict[str, Any]]) -> None
  _send_log_batch(log_messages: list[Dict[str, Any]]) -> None
  _send_log_batch_sync(log_messages: list[Dict[str, Any]]) -> None
  _send_message(message: Dict[str, Any]) -> None
  _send_message_sync(message: Dict[str, Any]) -> None
  _send_screenshots(message: Dict[str, Any]) -> None
  _send_screenshots_sync(screenshots: Dict[str, bytes]) -> None
  enqueue(message: Dict[str, Any]) -> None
  send_heartbeat_with_system_info(system_info: Dict[str, Any]) -> None
  set_connection_callback(callback: Callable[[bool], None]) -> None
  set_system_info(system_info: Dict[str, Any]) -> None
  start() -> None
  stop() -> None
}
class "Worker" as goliat.osparc_batch.worker.Worker {
  client_cfg : NoneType
  config : NoneType
  config_path : str
  download_and_process_results : Callable[..., Any]
  download_executor : ThreadPoolExecutor
  downloaded_jobs : set
  file_retries : dict
  file_to_job_id : dict
  finished
  get_osparc_client_config : Callable[..., Any]
  get_progress_report : Callable[..., str]
  input_files : list
  job_statuses : dict
  jobs_being_downloaded : set
  logger : Logger
  main_process_logic : Callable[..., Any]
  progress
  running_jobs : dict
  status_update_requested
  stop_requested : bool
  timer
  __init__(config_path: str, logger: logging.Logger, get_osparc_client_config_func: Callable[..., Any], download_and_process_results_func: Callable[..., Any], get_progress_report_func: Callable[..., str], main_process_logic_func: Callable[..., Any])
  _check_jobs_status()
  _download_job_in_thread(job, solver, file_path: Path)
  _resubmit_job(file_path: Path)
  _update_job_status(job_id: str, status: str)
  cancel_jobs()
  request_progress_report()
  run()
  stop()
}
goliat.analysis.far_field_strategy.FarFieldAnalysisStrategy --|> goliat.analysis.base_strategy.BaseAnalysisStrategy
goliat.analysis.near_field_strategy.NearFieldAnalysisStrategy --|> goliat.analysis.base_strategy.BaseAnalysisStrategy
goliat.extraction.power_extractor.PowerExtractor --|> goliat.logging_manager.LoggingMixin
goliat.extraction.resonance_extractor.ResonanceExtractor --|> goliat.logging_manager.LoggingMixin
goliat.extraction.sar_extractor.SarExtractor --|> goliat.logging_manager.LoggingMixin
goliat.gui.queue_gui.QueueGUI --|> goliat.logging_manager.LoggingMixin
goliat.project_manager.ProjectManager --|> goliat.logging_manager.LoggingMixin
goliat.results_extractor.ResultsExtractor --|> goliat.logging_manager.LoggingMixin
goliat.runners.isolve_manual_strategy.ISolveManualStrategy --|> goliat.logging_manager.LoggingMixin
goliat.runners.isolve_manual_strategy.ISolveManualStrategy --|> goliat.runners.execution_strategy.ExecutionStrategy
goliat.runners.isolve_output_parser.ISolveOutputParser --|> goliat.logging_manager.LoggingMixin
goliat.runners.isolve_process_manager.ISolveProcessManager --|> goliat.logging_manager.LoggingMixin
goliat.runners.osparc_direct_strategy.OSPARCDirectStrategy --|> goliat.logging_manager.LoggingMixin
goliat.runners.osparc_direct_strategy.OSPARCDirectStrategy --|> goliat.runners.execution_strategy.ExecutionStrategy
goliat.runners.post_simulation_handler.PostSimulationHandler --|> goliat.logging_manager.LoggingMixin
goliat.runners.retry_handler.RetryHandler --|> goliat.logging_manager.LoggingMixin
goliat.runners.sim4life_api_strategy.Sim4LifeAPIStrategy --|> goliat.logging_manager.LoggingMixin
goliat.runners.sim4life_api_strategy.Sim4LifeAPIStrategy --|> goliat.runners.execution_strategy.ExecutionStrategy
goliat.setups.base_setup.BaseSetup --|> goliat.logging_manager.LoggingMixin
goliat.setups.boundary_setup.BoundarySetup --|> goliat.setups.base_setup.BaseSetup
goliat.setups.far_field_setup.FarFieldSetup --|> goliat.setups.base_setup.BaseSetup
goliat.setups.gridding_setup.GriddingSetup --|> goliat.setups.base_setup.BaseSetup
goliat.setups.material_setup.MaterialSetup --|> goliat.setups.base_setup.BaseSetup
goliat.setups.near_field_setup.NearFieldSetup --|> goliat.setups.base_setup.BaseSetup
goliat.setups.phantom_setup.PhantomSetup --|> goliat.setups.base_setup.BaseSetup
goliat.setups.placement_setup.PlacementSetup --|> goliat.setups.base_setup.BaseSetup
goliat.setups.source_setup.SourceSetup --|> goliat.setups.base_setup.BaseSetup
goliat.simulation_runner.SimulationRunner --|> goliat.logging_manager.LoggingMixin
goliat.studies.base_study.BaseStudy --|> goliat.logging_manager.LoggingMixin
goliat.studies.far_field_study.FarFieldStudy --|> goliat.studies.base_study.BaseStudy
goliat.studies.near_field_study.NearFieldStudy --|> goliat.studies.base_study.BaseStudy
goliat.utils.gui_bridge.WebGUIBridge --|> goliat.logging_manager.LoggingMixin
goliat.utils.http_client.HTTPClient --|> goliat.logging_manager.LoggingMixin
goliat.analysis.plotter.Plotter --* goliat.analysis.analyzer.Analyzer : plotter
goliat.config.core.Config --* goliat.studies.base_study.BaseStudy : config
goliat.extraction.tissue_grouping.TissueGrouper --* goliat.extraction.sar_extractor.SarExtractor : tissue_grouper
goliat.gui.components.clock_manager.ClockManager --* goliat.gui.progress_gui.ProgressGUI : clock_manager
goliat.gui.components.data_manager.DataManager --* goliat.gui.progress_gui.ProgressGUI : data_manager
goliat.gui.components.graph_manager.GraphManager --* goliat.gui.progress_gui.ProgressGUI : graph_manager
goliat.gui.components.progress_animation.ProgressAnimation --* goliat.gui.progress_gui.ProgressGUI : progress_animation
goliat.gui.components.progress_manager.ProgressManager --* goliat.gui.progress_gui.ProgressGUI : progress_manager
goliat.gui.components.queue_handler.QueueHandler --* goliat.gui.progress_gui.ProgressGUI : queue_handler
goliat.gui.components.screenshot_capture.ScreenshotCapture --* goliat.gui.components.web_bridge_manager.WebBridgeManager : screenshot_capture
goliat.gui.components.status_manager.StatusManager --* goliat.gui.progress_gui.ProgressGUI : status_manager
goliat.gui.components.tray_manager.TrayManager --* goliat.gui.progress_gui.ProgressGUI : tray_manager
goliat.gui.components.utilization_manager.UtilizationManager --* goliat.gui.progress_gui.ProgressGUI : utilization_manager
goliat.gui.components.web_bridge_manager.WebBridgeManager --* goliat.gui.progress_gui.ProgressGUI : web_bridge_manager
goliat.profiler.Profiler --* goliat.studies.base_study.BaseStudy : profiler
goliat.project_manager.ProjectManager --* goliat.studies.base_study.BaseStudy : project_manager
goliat.utils.gui_bridge.WebGUIBridge --* goliat.gui.components.web_bridge_manager.WebBridgeManager : web_bridge
goliat.utils.http_client.HTTPClient --* goliat.utils.gui_bridge.WebGUIBridge : http_client
goliat.config.core.Config --o goliat.osparc_batch.worker.Worker : config
goliat.runners.isolve_manual_strategy.ISolveManualStrategy --o goliat.simulation_runner.SimulationRunner : current_strategy
goliat.runners.isolve_process_manager.ISolveProcessManager --o goliat.runners.isolve_manual_strategy.ISolveManualStrategy : current_process_manager
goliat.runners.osparc_direct_strategy.OSPARCDirectStrategy --o goliat.simulation_runner.SimulationRunner : current_strategy
goliat.runners.sim4life_api_strategy.Sim4LifeAPIStrategy --o goliat.simulation_runner.SimulationRunner : current_strategy
@enduml
```

</details>

<details>
<summary>Packages Diagram</summary>

```kroki-plantuml
@startuml packages_GOLIAT
set namespaceSeparator none
package "goliat" as goliat {
}
package "goliat.analysis" as goliat.analysis {
}
package "goliat.analysis.analyzer" as goliat.analysis.analyzer {
}
package "goliat.analysis.base_strategy" as goliat.analysis.base_strategy {
}
package "goliat.analysis.far_field_strategy" as goliat.analysis.far_field_strategy {
}
package "goliat.analysis.near_field_strategy" as goliat.analysis.near_field_strategy {
}
package "goliat.analysis.plotter" as goliat.analysis.plotter {
}
package "goliat.antenna" as goliat.antenna {
}
package "goliat.colors" as goliat.colors {
}
package "goliat.config" as goliat.config {
}
package "goliat.config.core" as goliat.config.core {
}
package "goliat.config.credentials" as goliat.config.credentials {
}
package "goliat.config.file_management" as goliat.config.file_management {
}
package "goliat.config.merge" as goliat.config.merge {
}
package "goliat.config.profiling" as goliat.config.profiling {
}
package "goliat.config.simulation_config" as goliat.config.simulation_config {
}
package "goliat.constants" as goliat.constants {
}
package "goliat.data_extractor" as goliat.data_extractor {
}
package "goliat.extraction" as goliat.extraction {
}
package "goliat.extraction.cleaner" as goliat.extraction.cleaner {
}
package "goliat.extraction.json_encoder" as goliat.extraction.json_encoder {
}
package "goliat.extraction.power_extractor" as goliat.extraction.power_extractor {
}
package "goliat.extraction.reporter" as goliat.extraction.reporter {
}
package "goliat.extraction.resonance_extractor" as goliat.extraction.resonance_extractor {
}
package "goliat.extraction.sar_extractor" as goliat.extraction.sar_extractor {
}
package "goliat.extraction.sensor_extractor" as goliat.extraction.sensor_extractor {
}
package "goliat.extraction.tissue_grouping" as goliat.extraction.tissue_grouping {
}
package "goliat.gui" as goliat.gui {
}
package "goliat.gui.components" as goliat.gui.components {
}
package "goliat.gui.components.clock_manager" as goliat.gui.components.clock_manager {
}
package "goliat.gui.components.data_manager" as goliat.gui.components.data_manager {
}
package "goliat.gui.components.graph_manager" as goliat.gui.components.graph_manager {
}
package "goliat.gui.components.machine_id_detector" as goliat.gui.components.machine_id_detector {
}
package "goliat.gui.components.plots" as goliat.gui.components.plots {
}
package "goliat.gui.components.plots._matplotlib_imports" as goliat.gui.components.plots._matplotlib_imports {
}
package "goliat.gui.components.plots.overall_progress_plot" as goliat.gui.components.plots.overall_progress_plot {
}
package "goliat.gui.components.plots.pie_charts_manager" as goliat.gui.components.plots.pie_charts_manager {
}
package "goliat.gui.components.plots.system_utilization_plot" as goliat.gui.components.plots.system_utilization_plot {
}
package "goliat.gui.components.plots.time_remaining_plot" as goliat.gui.components.plots.time_remaining_plot {
}
package "goliat.gui.components.plots.utils" as goliat.gui.components.plots.utils {
}
package "goliat.gui.components.progress_animation" as goliat.gui.components.progress_animation {
}
package "goliat.gui.components.progress_manager" as goliat.gui.components.progress_manager {
}
package "goliat.gui.components.queue_handler" as goliat.gui.components.queue_handler {
}
package "goliat.gui.components.screenshot_capture" as goliat.gui.components.screenshot_capture {
}
package "goliat.gui.components.status_manager" as goliat.gui.components.status_manager {
}
package "goliat.gui.components.system_monitor" as goliat.gui.components.system_monitor {
}
package "goliat.gui.components.timings_table" as goliat.gui.components.timings_table {
}
package "goliat.gui.components.tray_manager" as goliat.gui.components.tray_manager {
}
package "goliat.gui.components.ui_builder" as goliat.gui.components.ui_builder {
}
package "goliat.gui.components.utilization_manager" as goliat.gui.components.utilization_manager {
}
package "goliat.gui.components.web_bridge_manager" as goliat.gui.components.web_bridge_manager {
}
package "goliat.gui.progress_gui" as goliat.gui.progress_gui {
}
package "goliat.gui.queue_gui" as goliat.gui.queue_gui {
}
package "goliat.gui_manager" as goliat.gui_manager {
}
package "goliat.logging_manager" as goliat.logging_manager {
}
package "goliat.osparc_batch" as goliat.osparc_batch {
}
package "goliat.osparc_batch.cleanup" as goliat.osparc_batch.cleanup {
}
package "goliat.osparc_batch.file_finder" as goliat.osparc_batch.file_finder {
}
package "goliat.osparc_batch.gui" as goliat.osparc_batch.gui {
}
package "goliat.osparc_batch.logging_utils" as goliat.osparc_batch.logging_utils {
}
package "goliat.osparc_batch.main_logic" as goliat.osparc_batch.main_logic {
}
package "goliat.osparc_batch.osparc_client" as goliat.osparc_batch.osparc_client {
}
package "goliat.osparc_batch.progress" as goliat.osparc_batch.progress {
}
package "goliat.osparc_batch.runner" as goliat.osparc_batch.runner {
}
package "goliat.osparc_batch.worker" as goliat.osparc_batch.worker {
}
package "goliat.profiler" as goliat.profiler {
}
package "goliat.project_manager" as goliat.project_manager {
}
package "goliat.results_extractor" as goliat.results_extractor {
}
package "goliat.runners" as goliat.runners {
}
package "goliat.runners.execution_strategy" as goliat.runners.execution_strategy {
}
package "goliat.runners.isolve_manual_strategy" as goliat.runners.isolve_manual_strategy {
}
package "goliat.runners.isolve_output_parser" as goliat.runners.isolve_output_parser {
}
package "goliat.runners.isolve_process_manager" as goliat.runners.isolve_process_manager {
}
package "goliat.runners.keep_awake_handler" as goliat.runners.keep_awake_handler {
}
package "goliat.runners.osparc_direct_strategy" as goliat.runners.osparc_direct_strategy {
}
package "goliat.runners.post_simulation_handler" as goliat.runners.post_simulation_handler {
}
package "goliat.runners.retry_handler" as goliat.runners.retry_handler {
}
package "goliat.runners.sim4life_api_strategy" as goliat.runners.sim4life_api_strategy {
}
package "goliat.setups" as goliat.setups {
}
package "goliat.setups.base_setup" as goliat.setups.base_setup {
}
package "goliat.setups.boundary_setup" as goliat.setups.boundary_setup {
}
package "goliat.setups.far_field_setup" as goliat.setups.far_field_setup {
}
package "goliat.setups.gridding_setup" as goliat.setups.gridding_setup {
}
package "goliat.setups.material_setup" as goliat.setups.material_setup {
}
package "goliat.setups.near_field_setup" as goliat.setups.near_field_setup {
}
package "goliat.setups.phantom_setup" as goliat.setups.phantom_setup {
}
package "goliat.setups.placement_setup" as goliat.setups.placement_setup {
}
package "goliat.setups.source_setup" as goliat.setups.source_setup {
}
package "goliat.simulation_runner" as goliat.simulation_runner {
}
package "goliat.studies" as goliat.studies {
}
package "goliat.studies.base_study" as goliat.studies.base_study {
}
package "goliat.studies.far_field_study" as goliat.studies.far_field_study {
}
package "goliat.studies.near_field_study" as goliat.studies.near_field_study {
}
package "goliat.utils" as goliat.utils {
}
package "goliat.utils.bashrc" as goliat.utils.bashrc {
}
package "goliat.utils.config_setup" as goliat.utils.config_setup {
}
package "goliat.utils.core" as goliat.utils.core {
}
package "goliat.utils.data" as goliat.utils.data {
}
package "goliat.utils.data_prep" as goliat.utils.data_prep {
}
package "goliat.utils.gui_bridge" as goliat.utils.gui_bridge {
}
package "goliat.utils.http_client" as goliat.utils.http_client {
}
package "goliat.utils.message_sanitizer" as goliat.utils.message_sanitizer {
}
package "goliat.utils.package" as goliat.utils.package {
}
package "goliat.utils.preferences" as goliat.utils.preferences {
}
package "goliat.utils.python_interpreter" as goliat.utils.python_interpreter {
}
package "goliat.utils.scripts" as goliat.utils.scripts {
}
package "goliat.utils.scripts.cancel_all_jobs" as goliat.utils.scripts.cancel_all_jobs {
}
package "goliat.utils.scripts.prepare_antennas" as goliat.utils.scripts.prepare_antennas {
}
package "goliat.utils.setup" as goliat.utils.setup {
}
goliat.analysis.analyzer --> goliat.analysis.plotter
goliat.analysis.far_field_strategy --> goliat.analysis.base_strategy
goliat.analysis.near_field_strategy --> goliat.analysis.base_strategy
goliat.config --> goliat.config.core
goliat.config.core --> goliat.config.credentials
goliat.config.core --> goliat.config.file_management
goliat.config.core --> goliat.config.merge
goliat.config.core --> goliat.config.profiling
goliat.config.core --> goliat.config.simulation_config
goliat.extraction --> goliat.extraction.cleaner
goliat.extraction --> goliat.extraction.power_extractor
goliat.extraction --> goliat.extraction.reporter
goliat.extraction --> goliat.extraction.sar_extractor
goliat.extraction --> goliat.extraction.sensor_extractor
goliat.extraction.sar_extractor --> goliat.extraction.tissue_grouping
goliat.gui --> goliat.gui.components.data_manager
goliat.gui --> goliat.gui.components.plots
goliat.gui --> goliat.gui.components.progress_animation
goliat.gui --> goliat.gui.components.status_manager
goliat.gui.components.clock_manager --> goliat.utils
goliat.gui.components.plots --> goliat.gui.components.plots.overall_progress_plot
goliat.gui.components.plots --> goliat.gui.components.plots.pie_charts_manager
goliat.gui.components.plots --> goliat.gui.components.plots.system_utilization_plot
goliat.gui.components.plots --> goliat.gui.components.plots.time_remaining_plot
goliat.gui.components.plots.overall_progress_plot --> goliat.gui.components.plots._matplotlib_imports
goliat.gui.components.plots.overall_progress_plot --> goliat.gui.components.plots.utils
goliat.gui.components.plots.pie_charts_manager --> goliat.gui.components.plots._matplotlib_imports
goliat.gui.components.plots.system_utilization_plot --> goliat.gui.components.plots._matplotlib_imports
goliat.gui.components.plots.system_utilization_plot --> goliat.gui.components.plots.utils
goliat.gui.components.plots.time_remaining_plot --> goliat.gui.components.plots._matplotlib_imports
goliat.gui.components.plots.time_remaining_plot --> goliat.gui.components.plots.utils
goliat.gui.components.ui_builder --> goliat.gui.components.plots
goliat.gui.components.ui_builder --> goliat.gui.components.timings_table
goliat.gui.components.utilization_manager --> goliat.gui.components.system_monitor
goliat.gui.components.web_bridge_manager --> goliat.gui.components.screenshot_capture
goliat.gui.components.web_bridge_manager --> goliat.gui.components.system_monitor
goliat.gui.components.web_bridge_manager --> goliat.utils.gui_bridge
goliat.gui.progress_gui --> goliat.gui.components.clock_manager
goliat.gui.progress_gui --> goliat.gui.components.data_manager
goliat.gui.progress_gui --> goliat.gui.components.graph_manager
goliat.gui.progress_gui --> goliat.gui.components.machine_id_detector
goliat.gui.progress_gui --> goliat.gui.components.progress_animation
goliat.gui.progress_gui --> goliat.gui.components.progress_manager
goliat.gui.progress_gui --> goliat.gui.components.queue_handler
goliat.gui.progress_gui --> goliat.gui.components.status_manager
goliat.gui.progress_gui --> goliat.gui.components.system_monitor
goliat.gui.progress_gui --> goliat.gui.components.tray_manager
goliat.gui.progress_gui --> goliat.gui.components.ui_builder
goliat.gui.progress_gui --> goliat.gui.components.utilization_manager
goliat.gui.progress_gui --> goliat.gui.components.web_bridge_manager
goliat.gui.progress_gui --> goliat.logging_manager
goliat.gui.queue_gui --> goliat.logging_manager
goliat.gui_manager --> goliat.gui.progress_gui
goliat.gui_manager --> goliat.gui.queue_gui
goliat.logging_manager --> goliat.colors
goliat.osparc_batch.cleanup --> goliat.osparc_batch.logging_utils
goliat.osparc_batch.file_finder --> goliat.osparc_batch.logging_utils
goliat.osparc_batch.logging_utils --> goliat.colors
goliat.osparc_batch.main_logic --> goliat.osparc_batch.logging_utils
goliat.osparc_batch.main_logic --> goliat.osparc_batch.osparc_client
goliat.osparc_batch.osparc_client --> goliat.osparc_batch.logging_utils
goliat.osparc_batch.progress --> goliat.osparc_batch.logging_utils
goliat.osparc_batch.runner --> goliat.config
goliat.osparc_batch.runner --> goliat.osparc_batch.cleanup
goliat.osparc_batch.runner --> goliat.osparc_batch.file_finder
goliat.osparc_batch.runner --> goliat.osparc_batch.gui
goliat.osparc_batch.runner --> goliat.osparc_batch.logging_utils
goliat.osparc_batch.runner --> goliat.osparc_batch.main_logic
goliat.osparc_batch.runner --> goliat.osparc_batch.osparc_client
goliat.osparc_batch.runner --> goliat.osparc_batch.progress
goliat.osparc_batch.runner --> goliat.osparc_batch.worker
goliat.osparc_batch.worker --> goliat.osparc_batch.logging_utils
goliat.osparc_batch.worker --> goliat.osparc_batch.osparc_client
goliat.osparc_batch.worker --> goliat.utils.scripts.cancel_all_jobs
goliat.project_manager --> goliat.constants
goliat.project_manager --> goliat.logging_manager
goliat.project_manager --> goliat.results_extractor
goliat.project_manager --> goliat.utils
goliat.results_extractor --> goliat.extraction.cleaner
goliat.results_extractor --> goliat.extraction.json_encoder
goliat.results_extractor --> goliat.extraction.power_extractor
goliat.results_extractor --> goliat.extraction.reporter
goliat.results_extractor --> goliat.extraction.resonance_extractor
goliat.results_extractor --> goliat.extraction.sar_extractor
goliat.results_extractor --> goliat.extraction.sensor_extractor
goliat.results_extractor --> goliat.logging_manager
goliat.runners.isolve_manual_strategy --> goliat.runners.execution_strategy
goliat.runners.isolve_manual_strategy --> goliat.runners.isolve_output_parser
goliat.runners.isolve_manual_strategy --> goliat.runners.isolve_process_manager
goliat.runners.isolve_manual_strategy --> goliat.runners.keep_awake_handler
goliat.runners.isolve_manual_strategy --> goliat.runners.post_simulation_handler
goliat.runners.isolve_manual_strategy --> goliat.runners.retry_handler
goliat.runners.osparc_direct_strategy --> goliat.runners.execution_strategy
goliat.runners.osparc_direct_strategy --> goliat.runners.post_simulation_handler
goliat.runners.sim4life_api_strategy --> goliat.runners.execution_strategy
goliat.setups.base_setup --> goliat.logging_manager
goliat.setups.boundary_setup --> goliat.setups.base_setup
goliat.setups.far_field_setup --> goliat.setups.base_setup
goliat.setups.far_field_setup --> goliat.setups.boundary_setup
goliat.setups.far_field_setup --> goliat.setups.gridding_setup
goliat.setups.far_field_setup --> goliat.setups.material_setup
goliat.setups.far_field_setup --> goliat.setups.phantom_setup
goliat.setups.gridding_setup --> goliat.setups.base_setup
goliat.setups.material_setup --> goliat.setups.base_setup
goliat.setups.near_field_setup --> goliat.setups.base_setup
goliat.setups.near_field_setup --> goliat.setups.boundary_setup
goliat.setups.near_field_setup --> goliat.setups.gridding_setup
goliat.setups.near_field_setup --> goliat.setups.material_setup
goliat.setups.near_field_setup --> goliat.setups.phantom_setup
goliat.setups.near_field_setup --> goliat.setups.placement_setup
goliat.setups.near_field_setup --> goliat.setups.source_setup
goliat.setups.phantom_setup --> goliat.setups.base_setup
goliat.setups.placement_setup --> goliat.setups.base_setup
goliat.setups.source_setup --> goliat.setups.base_setup
goliat.simulation_runner --> goliat.logging_manager
goliat.simulation_runner --> goliat.runners.execution_strategy
goliat.simulation_runner --> goliat.runners.isolve_manual_strategy
goliat.simulation_runner --> goliat.runners.osparc_direct_strategy
goliat.simulation_runner --> goliat.runners.sim4life_api_strategy
goliat.studies.base_study --> goliat.config
goliat.studies.base_study --> goliat.logging_manager
goliat.studies.base_study --> goliat.profiler
goliat.studies.base_study --> goliat.project_manager
goliat.studies.base_study --> goliat.simulation_runner
goliat.studies.base_study --> goliat.utils
goliat.studies.far_field_study --> goliat.studies.base_study
goliat.studies.near_field_study --> goliat.studies.base_study
goliat.utils --> goliat.utils.core
goliat.utils --> goliat.utils.setup
goliat.utils.bashrc --> goliat.utils.preferences
goliat.utils.data --> goliat.colors
goliat.utils.data_prep --> goliat.utils.data
goliat.utils.data_prep --> goliat.utils.scripts.prepare_antennas
goliat.utils.gui_bridge --> goliat.logging_manager
goliat.utils.gui_bridge --> goliat.utils.http_client
goliat.utils.gui_bridge --> goliat.utils.message_sanitizer
goliat.utils.http_client --> goliat.logging_manager
goliat.utils.python_interpreter --> goliat.utils.bashrc
goliat.utils.scripts.cancel_all_jobs --> goliat.colors
goliat.utils.scripts.cancel_all_jobs --> goliat.config
goliat.utils.setup --> goliat.utils.bashrc
goliat.utils.setup --> goliat.utils.config_setup
goliat.utils.setup --> goliat.utils.data_prep
goliat.utils.setup --> goliat.utils.package
goliat.utils.setup --> goliat.utils.python_interpreter
goliat.analysis.analyzer ..> goliat.analysis.base_strategy
goliat.analysis.base_strategy ..> goliat.analysis.analyzer
goliat.analysis.base_strategy ..> goliat.analysis.plotter
goliat.analysis.far_field_strategy ..> goliat.analysis.analyzer
goliat.analysis.far_field_strategy ..> goliat.analysis.plotter
goliat.analysis.near_field_strategy ..> goliat.analysis.analyzer
goliat.analysis.near_field_strategy ..> goliat.analysis.plotter
goliat.antenna ..> goliat.config
goliat.gui.components.clock_manager ..> goliat.gui.progress_gui
goliat.gui.components.graph_manager ..> goliat.gui.progress_gui
goliat.gui.components.plots._matplotlib_imports ..> goliat.profiler
goliat.gui.components.plots.pie_charts_manager ..> goliat.profiler
goliat.gui.components.progress_manager ..> goliat.gui.progress_gui
goliat.gui.components.queue_handler ..> goliat.gui.progress_gui
goliat.gui.components.screenshot_capture ..> goliat.gui.progress_gui
goliat.gui.components.timings_table ..> goliat.profiler
goliat.gui.components.ui_builder ..> goliat.gui.components.status_manager
goliat.gui.components.ui_builder ..> goliat.gui.progress_gui
goliat.gui.components.utilization_manager ..> goliat.gui.progress_gui
goliat.gui.components.web_bridge_manager ..> goliat.gui.progress_gui
goliat.gui.progress_gui ..> goliat.profiler
goliat.gui.queue_gui ..> goliat.profiler
goliat.logging_manager ..> goliat.gui_manager
goliat.osparc_batch.file_finder ..> goliat.config
goliat.osparc_batch.main_logic ..> goliat.osparc_batch.worker
goliat.osparc_batch.osparc_client ..> goliat.config
goliat.project_manager ..> goliat.config
goliat.project_manager ..> goliat.gui_manager
goliat.results_extractor ..> goliat.config
goliat.results_extractor ..> goliat.gui_manager
goliat.results_extractor ..> goliat.studies.base_study
goliat.simulation_runner ..> goliat.config
goliat.simulation_runner ..> goliat.gui_manager
goliat.simulation_runner ..> goliat.profiler
goliat.simulation_runner ..> goliat.project_manager
@enduml
```

</details>

How to view
- Right click the above image and open in a new tab. Zoom in and pan around.
- Alternatively, use any PlantUML viewer (e.g., VS Code PlantUML extension, IntelliJ PlantUML plugin, or https://www.plantuml.com/plantuml).