# API Reference

Complete API documentation for GOLIAT, organized by module category.

## Core Modules

Core functionality for configuration, logging, and utilities.

### Antenna

::: goliat.antenna.Antenna
    options:
      show_root_heading: true
      show_source: true


### Colors

::: goliat.colors
    options:
      show_root_heading: true
      show_source: true


### Data Management

::: goliat.data_extractor
    options:
      show_root_heading: true
      show_source: true


### Logging

::: goliat.logging_manager
    options:
      show_root_heading: true
      show_source: true


### Profiling

::: goliat.profiler.Profiler
    options:
      show_root_heading: true
      show_source: true


### Project Management

::: goliat.project_manager
    options:
      show_root_heading: true
      show_source: true

---

## Study Orchestration

Study classes that orchestrate simulation workflows.

### Base Study

::: goliat.studies.base_study
    options:
      show_root_heading: true
      show_source: true


### Far-Field Study

::: goliat.studies.far_field_study
    options:
      show_root_heading: true
      show_source: true


### Near-Field Study

::: goliat.studies.near_field_study
    options:
      show_root_heading: true
      show_source: true

---

## Setup Modules

Classes responsible for building the Sim4Life simulation scene.

### Base Setup

::: goliat.setups.base_setup
    options:
      show_root_heading: true
      show_source: true


### Boundary Setup

::: goliat.setups.boundary_setup
    options:
      show_root_heading: true
      show_source: true


### Far-Field Setup

::: goliat.setups.far_field_setup
    options:
      show_root_heading: true
      show_source: true


### Gridding Setup

::: goliat.setups.gridding_setup
    options:
      show_root_heading: true
      show_source: true


### Material Setup

::: goliat.setups.material_setup
    options:
      show_root_heading: true
      show_source: true


### Near-Field Setup

::: goliat.setups.near_field_setup
    options:
      show_root_heading: true
      show_source: true


### Phantom Setup

::: goliat.setups.phantom_setup
    options:
      show_root_heading: true
      show_source: true


### Placement Setup

::: goliat.setups.placement_setup
    options:
      show_root_heading: true
      show_source: true


### Source Setup

::: goliat.setups.source_setup
    options:
      show_root_heading: true
      show_source: true

---

## Simulation Execution

::: goliat.simulation_runner.SimulationRunner
    options:
      show_root_heading: true
      show_source: true

---

## Execution Strategies

Strategy pattern implementations for different simulation execution methods.

### Base Strategy

::: goliat.runners.execution_strategy
    options:
      show_root_heading: true
      show_source: true


### iSolve Manual Strategy

::: goliat.runners.isolve_manual_strategy
    options:
      show_root_heading: true
      show_source: true


### oSPARC Direct Strategy

::: goliat.runners.osparc_direct_strategy
    options:
      show_root_heading: true
      show_source: true


### Sim4Life API Strategy

::: goliat.runners.sim4life_api_strategy
    options:
      show_root_heading: true
      show_source: true

---

## Results Extraction

Classes for extracting and processing simulation results.

### Cleanup

::: goliat.extraction.cleaner.Cleaner
    options:
      show_root_heading: true
      show_source: true


### JSON Encoding

::: goliat.extraction.json_encoder
    options:
      show_root_heading: true
      show_source: true


### Power Extraction

::: goliat.extraction.power_extractor
    options:
      show_root_heading: true
      show_source: true


### Reporting

::: goliat.extraction.reporter.Reporter
    options:
      show_root_heading: true
      show_source: true


### SAR Extraction

::: goliat.extraction.sar_extractor
    options:
      show_root_heading: true
      show_source: true


### Sensor Extraction

::: goliat.extraction.sensor_extractor
    options:
      show_root_heading: true
      show_source: true

---

## Analysis

Classes for analyzing and visualizing simulation results.

### Analyzer

::: goliat.analysis.analyzer.Analyzer
    options:
      show_root_heading: true
      show_source: true


### Analysis Strategies

::: goliat.analysis.base_strategy
    options:
      show_root_heading: true
      show_source: true


### Far-Field Strategy

::: goliat.analysis.far_field_strategy
    options:
      show_root_heading: true
      show_source: true


### Near-Field Strategy

::: goliat.analysis.near_field_strategy
    options:
      show_root_heading: true
      show_source: true


### Plotting

::: goliat.analysis.plotter.Plotter
    options:
      show_root_heading: true
      show_source: true

---

## GUI Components

Graphical user interface for monitoring simulation progress.

### Main GUI

::: goliat.gui.progress_gui
    options:
      show_root_heading: true
      show_source: true

### GUI Communication

::: goliat.gui.queue_gui
    options:
      show_root_heading: true
      show_source: true

### GUI Components

::: goliat.gui.components.clock_manager
    options:
      show_root_heading: true
      show_source: true

::: goliat.gui.components.data_manager
    options:
      show_root_heading: true
      show_source: true

::: goliat.gui.components.graph_manager
    options:
      show_root_heading: true
      show_source: true

::: goliat.gui.components.machine_id_detector
    options:
      show_root_heading: true
      show_source: true

### Plot Components

::: goliat.gui.components.plots.overall_progress_plot
    options:
      show_root_heading: true
      show_source: true

::: goliat.gui.components.plots.pie_charts_manager
    options:
      show_root_heading: true
      show_source: true

::: goliat.gui.components.plots.system_utilization_plot
    options:
      show_root_heading: true
      show_source: true

::: goliat.gui.components.plots.time_remaining_plot
    options:
      show_root_heading: true
      show_source: true

::: goliat.gui.components.progress_animation
    options:
      show_root_heading: true
      show_source: true

::: goliat.gui.components.progress_animation
    options:
      show_root_heading: true
      show_source: true

::: goliat.gui.components.progress_manager
    options:
      show_root_heading: true
      show_source: true

::: goliat.gui.components.queue_handler
    options:
      show_root_heading: true
      show_source: true

::: goliat.gui.components.screenshot_capture
    options:
      show_root_heading: true
      show_source: true

::: goliat.gui.components.status_manager
    options:
      show_root_heading: true
      show_source: true

::: goliat.gui.components.system_monitor
    options:
      show_root_heading: true
      show_source: true

::: goliat.gui.components.timings_table
    options:
      show_root_heading: true
      show_source: true

::: goliat.gui.components.tray_manager
    options:
      show_root_heading: true
      show_source: true

::: goliat.gui.components.ui_builder
    options:
      show_root_heading: true
      show_source: true

::: goliat.gui.components.utilization_manager
    options:
      show_root_heading: true
      show_source: true

::: goliat.gui.components.web_bridge_manager
    options:
      show_root_heading: true
      show_source: true

---

## Scripts

Entry point scripts for running studies and analysis.

!!! note "Scripts"
    These are top-level scripts for running studies. They are not part of the core API but are included for reference.

- `goliat study` - Main entry point for running studies
- `goliat analyze` - Entry point for post-processing analysis
- `goliat parallel` - Script for running parallel study batches
- `goliat free-space` - Script for free-space validation runs
- `goliat init` - Initialize GOLIAT environment (install dependencies, setup)
- `goliat status` - Show setup status and environment information
- `goliat validate` - Validate configuration files
- `goliat version` - Show GOLIAT version information