# API Reference

This page provides comprehensive API documentation for all modules in the GOLIAT simulation framework.

!!! info "Documentation Note"
    Full API documentation with automatic code introspection requires Sim4Life dependencies.
    For now, please refer to the source code directly in the [`src/`](https://github.com/rwydaegh/goliat/tree/master/src) directory.

## Core Modules

### Studies
- [`NearFieldStudy`](https://github.com/rwydaegh/goliat/blob/master/src/studies/near_field_study.py) - Manages near-field simulation workflow
- [`FarFieldStudy`](https://github.com/rwydaegh/goliat/blob/master/src/studies/far_field_study.py) - Manages far-field simulation workflow
- [`BaseStudy`](https://github.com/rwydaegh/goliat/blob/master/src/studies/base_study.py) - Common study functionality

### Setup Components
- [`NearFieldSetup`](https://github.com/rwydaegh/goliat/blob/master/src/setups/near_field_setup.py) - Configures near-field simulations
- [`FarFieldSetup`](https://github.com/rwydaegh/goliat/blob/master/src/setups/far_field_setup.py) - Configures far-field simulations
- [`PhantomSetup`](https://github.com/rwydaegh/goliat/blob/master/src/setups/phantom_setup.py) - Handles phantom models
- [`PlacementSetup`](https://github.com/rwydaegh/goliat/blob/master/src/setups/placement_setup.py) - Manages antenna positioning
- [`GriddingSetup`](https://github.com/rwydaegh/goliat/blob/master/src/setups/gridding_setup.py) - Configures simulation grids
- [`MaterialSetup`](https://github.com/rwydaegh/goliat/blob/master/src/setups/material_setup.py) - Assigns material properties
- [`SourceSetup`](https://github.com/rwydaegh/goliat/blob/master/src/setups/source_setup.py) - Configures EMF sources
- [`BoundarySetup`](https://github.com/rwydaegh/goliat/blob/master/src/setups/boundary_setup.py) - Sets boundary conditions

### Core Components
- [`Config`](https://github.com/rwydaegh/goliat/blob/master/src/config.py) - Configuration management
- [`ProjectManager`](https://github.com/rwydaegh/goliat/blob/master/src/project_manager.py) - Sim4Life project handling
- [`SimulationRunner`](https://github.com/rwydaegh/goliat/blob/master/src/simulation_runner.py) - Simulation execution
- [`ResultsExtractor`](https://github.com/rwydaegh/goliat/blob/master/src/results_extractor.py) - Post-processing and data extraction
- [`Antenna`](https://github.com/rwydaegh/goliat/blob/master/src/antenna.py) - Antenna model management

### Analysis
- [`Analyzer`](https://github.com/rwydaegh/goliat/blob/master/src/analysis/analyzer.py) - Results analysis orchestration
- [`Plotter`](https://github.com/rwydaegh/goliat/blob/master/src/analysis/plotter.py) - Visualization generation
- [`NearFieldAnalysisStrategy`](https://github.com/rwydaegh/goliat/blob/master/src/analysis/strategies.py) - Near-field analysis
- [`FarFieldAnalysisStrategy`](https://github.com/rwydaegh/goliat/blob/master/src/analysis/strategies.py) - Far-field analysis

### Utilities
- [`Profiler`](https://github.com/rwydaegh/goliat/blob/master/src/profiler.py) - Performance profiling and ETA estimation
- [`GuiManager`](https://github.com/rwydaegh/goliat/blob/master/src/gui_manager.py) - GUI and progress tracking
- [`LoggingManager`](https://github.com/rwydaegh/goliat/blob/master/src/logging_manager.py) - Logging configuration

### oSPARC Batch Processing
- [`Worker`](https://github.com/rwydaegh/goliat/blob/master/src/osparc_batch/worker.py) - Cloud job management
- [`BatchGUI`](https://github.com/rwydaegh/goliat/blob/master/src/osparc_batch/gui.py) - Batch processing interface

## See Also

- [Architecture Overview](architecture_overview.md) - High-level system design
- [UML Diagrams](uml.md) - Class and package diagrams
- [Source Code](https://github.com/rwydaegh/goliat/tree/master/src) - Browse the code directly