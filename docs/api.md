# API Reference

This reference details GOLIAT's core classes and functions. It is generated from source code and includes descriptions, parameters, and usage examples. For full source, see [src/](https://github.com/rwydaegh/goliat/tree/master/src).

## Core Modules

### Configuration

#### Config
Loads and manages JSON configs with inheritance.

**Constructor**:
- `Config(base_dir, config_filename="near_field_config.json")`

**Key Methods**:
- `get_setting(path, default=None)`: Retrieves nested settings (e.g., "study_type").
  - Example:
    ```python
    config = Config(".")
    study_type = config.get_setting("study_type")  # Returns "near_field"
    ```

- `get_antenna_config()`: Returns antenna settings dict.
  - Example:
    ```python
    antennas = config.get_antenna_config()
    pifa_700 = antennas["700"]  # Dict with model_type, materials
    ```

- `get_profiling_config(study_type)`: Loads timing estimates.
  - Example:
    ```python
    profiling = config.get_profiling_config("near_field")
    avg_setup = profiling["avg_setup_time"]  # e.g., 135.19 s
    ```

### Studies

#### BaseStudy
Base class for study orchestration.

**Constructor**:
- `BaseStudy(study_type, config_filename, gui, profiler)`

**Key Methods**:
- `run()`: Executes the study workflow (setup, run, extract).
  - Example:
    ```python
    from src.studies.near_field_study import NearFieldStudy
    study = NearFieldStudy("near_field", "config.json", gui=None, profiler=None)
    study.run()  # Runs full study
    ```

#### NearFieldStudy
Manages near-field simulations.

**Constructor**:
- `NearFieldStudy(config_filename, gui)`

**Key Methods**:
- `_run_study()`: Loops over phantoms/frequencies/placements, calls setup/run/extract.
  - Inherits from BaseStudy; uses PlacementSetup for antenna positioning.

#### FarFieldStudy
Manages far-field simulations.

**Constructor**:
- `FarFieldStudy(config_filename, gui)`

**Key Methods**:
- `_run_study()`: Loops over phantoms/frequencies, creates plane wave sims for directions/polarizations.

### Setup Components

#### PhantomSetup
Loads and validates phantom models.

**Constructor**:
- `PhantomSetup(config, phantom_name, verbose_logger, progress_logger)`

**Key Methods**:
- `ensure_phantom_is_loaded()`: Downloads/imports phantom if missing.
  - Example:
    ```python
    phantom_setup = PhantomSetup(config, "thelonious", logger, logger)
    phantom_setup.ensure_phantom_is_loaded()  # Loads voxel model
    ```

#### PlacementSetup
Positions antenna relative to phantom.

**Constructor**:
- `PlacementSetup(config, phantom_name, frequency_mhz, placement_name, antenna, verbose_logger, progress_logger, free_space)`

**Key Methods**:
- `place_antenna()`: Applies position/orientation from config.
  - Example:
    ```python
    placement = PlacementSetup(config, "thelonious", 700, "by_cheek", antenna, logger, logger, False)
    placement.place_antenna()  # Positions at 8mm from cheek
    ```

#### MaterialSetup
Assigns materials to entities.

**Constructor**:
- `MaterialSetup(config, simulation, antenna, phantom_name, verbose_logger, progress_logger, free_space)`

**Key Methods**:
- `assign_materials(antenna_components, phantom_only=False)`: Maps config materials to CAD/tissues.
  - Example:
    ```python
    material_setup = MaterialSetup(config, sim, antenna, "thelonious", logger, logger, False)
    material_setup.assign_materials(components)  # Copper to antenna parts
    ```

#### GriddingSetup
Configures spatial grid.

**Constructor**:
- `GriddingSetup(config, simulation, placement_name, antenna, verbose_logger, progress_logger, frequency_mhz)`

**Key Methods**:
- `setup_gridding(antenna_components)`: Sets main grid and subgrids.
  - Example:
    ```python
    gridding = GriddingSetup(config, sim, "by_cheek", antenna, logger, logger, 700)
    gridding.setup_gridding(components)  # Applies 3mm step
    ```

#### SourceSetup
Configures EMF sources and sensors.

**Constructor**:
- `SourceSetup(config, simulation, frequency_mhz, antenna, verbose_logger, progress_logger, free_space)`

**Key Methods**:
- `setup_source_and_sensors(antenna_components)`: Adds excitation (harmonic/Gaussian).
  - Example:
    ```python
    source = SourceSetup(config, sim, 700, antenna, logger, logger, False)
    source.setup_source_and_sensors(components)  # Sets port excitation
    ```

### Core Components

#### ProjectManager
Handles .smash project files.

**Constructor**:
- `ProjectManager(config, verbose_logger, progress_logger, gui=None)`

**Key Methods**:
- `create_or_open_project(phantom_name, frequency_mhz, placement_name)`: Creates/opens .smash.
  - Example:
    ```python
    pm = ProjectManager(config, logger, logger)
    pm.create_or_open_project("thelonious", 700, "by_cheek")  # Sets path, opens
    ```

#### SimulationRunner
Executes simulations.

**Constructor**:
- `SimulationRunner(config, project_path, simulations, verbose_logger, progress_logger, gui, study)`

**Key Methods**:
- `run_all()`: Runs list of simulations.
  - Example:
    ```python
    runner = SimulationRunner(config, path, sims, logger, logger, gui, study)
    runner.run_all()  # Executes iSolve or oSPARC
    ```

#### ResultsExtractor
Post-processes simulation outputs.

**Constructor**:
- `ResultsExtractor(config, simulation, phantom_name, frequency_mhz, placement_name, study_type, verbose_logger, progress_logger, free_space, gui, study)`

**Key Methods**:
- `extract()`: Pulls SAR/power balance.
  - Example:
    ```python
    extractor = ResultsExtractor(config, sim, "thelonious", 700, "by_cheek", "near_field", logger, logger, False, gui, study)
    extractor.extract()  # Saves JSON/PKL with SAR values
    ```

### Analysis

#### Analyzer
Orchestrates analysis with strategy.

**Constructor**:
- `Analyzer(config, phantom_name, strategy)`

**Key Methods**:
- `run_analysis()`: Loads results, applies strategy, generates reports/plots.
  - Example:
    ```python
    from src.analysis.strategies import NearFieldAnalysisStrategy
    strategy = NearFieldAnalysisStrategy(config, "thelonious")
    analyzer = Analyzer(config, "thelonious", strategy)
    analyzer.run_analysis()  # Aggregates CSVs, plots
    ```

#### Plotter
Generates visualizations.

**Constructor**:
- `Plotter(plots_dir)`

**Key Methods**:
- `plot_sar_heatmap(organ_df, group_df, tissue_groups)`: Heatmap of SAR by tissue/freq.
  - Example:
    ```python
    plotter = Plotter("plots/")
    plotter.plot_sar_heatmap(df, group_df, groups)  # Saves PNG
    ```

For full API, browse [src/](https://github.com/rwydaegh/goliat/tree/master/src).

---
*Last updated: {date}*