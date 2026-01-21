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


### Constants

::: goliat.constants
    options:
      show_root_heading: true
      show_source: true


### Data Extractor

::: goliat.data_extractor
    options:
      show_root_heading: true
      show_source: true


### Gui Manager

::: goliat.gui_manager
    options:
      show_root_heading: true
      show_source: true


### Logging Manager

::: goliat.logging_manager.ColorFormatter
    options:
      show_root_heading: true
      show_source: true


### Metadata Exporter

::: goliat.metadata_exporter.TimingBreakdown
    options:
      show_root_heading: true
      show_source: true


### Profiler

::: goliat.profiler.Profiler
    options:
      show_root_heading: true
      show_source: true


### Project Manager

::: goliat.project_manager.ProjectCorruptionError
    options:
      show_root_heading: true
      show_source: true


### Results Extractor

::: goliat.results_extractor.ExtractionContext
    options:
      show_root_heading: true
      show_source: true


### Simulation Runner

::: goliat.simulation_runner.SimulationRunner
    options:
      show_root_heading: true
      show_source: true


---

## Configuration

Configuration management and settings.

### Core

::: goliat.config.core.Config
    options:
      show_root_heading: true
      show_source: true


### Credentials

::: goliat.config.credentials
    options:
      show_root_heading: true
      show_source: true


### File Management

::: goliat.config.file_management
    options:
      show_root_heading: true
      show_source: true


### Merge

::: goliat.config.merge
    options:
      show_root_heading: true
      show_source: true


### Profiling

::: goliat.config.profiling
    options:
      show_root_heading: true
      show_source: true


### Simulation Config

::: goliat.config.simulation_config
    options:
      show_root_heading: true
      show_source: true


---

## Study Orchestration

Study classes that orchestrate simulation workflows.

### Base Study

::: goliat.studies.base_study.BaseStudy
    options:
      show_root_heading: true
      show_source: true


### Far Field Study

::: goliat.studies.far_field_study.FarFieldStudy
    options:
      show_root_heading: true
      show_source: true


### Near Field Study

::: goliat.studies.near_field_study.NearFieldStudy
    options:
      show_root_heading: true
      show_source: true


---

## Setup Modules

Classes responsible for building the Sim4Life simulation scene.

### Base Setup

::: goliat.setups.base_setup.BaseSetup
    options:
      show_root_heading: true
      show_source: true


### Boundary Setup

::: goliat.setups.boundary_setup.BoundarySetup
    options:
      show_root_heading: true
      show_source: true


### Far Field Setup

::: goliat.setups.far_field_setup.FarFieldSetup
    options:
      show_root_heading: true
      show_source: true


### Gridding Setup

::: goliat.setups.gridding_setup.GriddingSetup
    options:
      show_root_heading: true
      show_source: true


### Material Setup

::: goliat.setups.material_setup.MaterialSetup
    options:
      show_root_heading: true
      show_source: true


### Near Field Setup

::: goliat.setups.near_field_setup.NearFieldSetup
    options:
      show_root_heading: true
      show_source: true


### Phantom Setup

::: goliat.setups.phantom_setup.PhantomSetup
    options:
      show_root_heading: true
      show_source: true


### Placement Setup

::: goliat.setups.placement_setup.PlacementSetup
    options:
      show_root_heading: true
      show_source: true


### Source Setup

::: goliat.setups.source_setup.SourceSetup
    options:
      show_root_heading: true
      show_source: true


---

## Execution Strategies

Strategy pattern implementations for different simulation execution methods.

### Execution Strategy

::: goliat.runners.execution_strategy.ExecutionStrategy
    options:
      show_root_heading: true
      show_source: true


### Isolve Manual Strategy

::: goliat.runners.isolve_manual_strategy.ISolveManualStrategy
    options:
      show_root_heading: true
      show_source: true


### Isolve Output Parser

::: goliat.runners.isolve_output_parser.ProgressInfo
    options:
      show_root_heading: true
      show_source: true


### Isolve Process Manager

::: goliat.runners.isolve_process_manager.ISolveProcessManager
    options:
      show_root_heading: true
      show_source: true


### Keep Awake Handler

::: goliat.runners.keep_awake_handler.KeepAwakeHandler
    options:
      show_root_heading: true
      show_source: true


### Osparc Direct Strategy

::: goliat.runners.osparc_direct_strategy.OSPARCDirectStrategy
    options:
      show_root_heading: true
      show_source: true


### Post Simulation Handler

::: goliat.runners.post_simulation_handler.PostSimulationHandler
    options:
      show_root_heading: true
      show_source: true


### Retry Handler

::: goliat.runners.retry_handler.RetryHandler
    options:
      show_root_heading: true
      show_source: true


### Sim4Life Api Strategy

::: goliat.runners.sim4life_api_strategy.Sim4LifeAPIStrategy
    options:
      show_root_heading: true
      show_source: true


---

## Results Extraction

Classes for extracting and processing simulation results.

### Auto Induced Processor

::: goliat.extraction.auto_induced_processor.AutoInducedProcessor
    options:
      show_root_heading: true
      show_source: true


### Cleaner

::: goliat.extraction.cleaner.Cleaner
    options:
      show_root_heading: true
      show_source: true


### Field Combiner

::: goliat.extraction.field_combiner.FieldCombineConfig
    options:
      show_root_heading: true
      show_source: true


### Field Reader

::: goliat.extraction.field_reader
    options:
      show_root_heading: true
      show_source: true


### Focus Optimizer

::: goliat.extraction.focus_optimizer.FieldCache
    options:
      show_root_heading: true
      show_source: true


### Json Encoder

::: goliat.extraction.json_encoder.NumpyArrayEncoder
    options:
      show_root_heading: true
      show_source: true


### Power Extractor

::: goliat.extraction.power_extractor.PowerExtractor
    options:
      show_root_heading: true
      show_source: true


### Reporter

::: goliat.extraction.reporter.Reporter
    options:
      show_root_heading: true
      show_source: true


### Resonance Extractor

::: goliat.extraction.resonance_extractor.ResonanceExtractor
    options:
      show_root_heading: true
      show_source: true


### Sapd Extractor

::: goliat.extraction.sapd_extractor.SapdExtractionContext
    options:
      show_root_heading: true
      show_source: true


### Sar Extractor

::: goliat.extraction.sar_extractor.SarExtractor
    options:
      show_root_heading: true
      show_source: true


### Sensor Extractor

::: goliat.extraction.sensor_extractor.SensorExtractor
    options:
      show_root_heading: true
      show_source: true


### Tissue Grouping

::: goliat.extraction.tissue_grouping.TissueGrouper
    options:
      show_root_heading: true
      show_source: true


---

## Analysis

Classes for analyzing and visualizing simulation results.

### Analyze Simulation Stats

::: goliat.analysis.analyze_simulation_stats
    options:
      show_root_heading: true
      show_source: true


### Analyzer

::: goliat.analysis.analyzer.Analyzer
    options:
      show_root_heading: true
      show_source: true


### Base Strategy

::: goliat.analysis.base_strategy.BaseAnalysisStrategy
    options:
      show_root_heading: true
      show_source: true


### Compare

::: goliat.analysis.compare
    options:
      show_root_heading: true
      show_source: true


### Create Excel For Partners

::: goliat.analysis.create_excel_for_partners
    options:
      show_root_heading: true
      show_source: true


### Far Field Strategy

::: goliat.analysis.far_field_strategy.FarFieldAnalysisStrategy
    options:
      show_root_heading: true
      show_source: true


### Near Field Strategy

::: goliat.analysis.near_field_strategy.NearFieldAnalysisStrategy
    options:
      show_root_heading: true
      show_source: true


### Parallel Plot Executor

::: goliat.analysis.parallel_plot_executor.ParallelPlotExecutor
    options:
      show_root_heading: true
      show_source: true


### Parse Verbose Log

::: goliat.analysis.parse_verbose_log
    options:
      show_root_heading: true
      show_source: true


### Plotter

::: goliat.analysis.plotter.Plotter
    options:
      show_root_heading: true
      show_source: true


### Plots

::: goliat.analysis.plots.bar.BarPlotter
    options:
      show_root_heading: true
      show_source: true


::: goliat.analysis.plots.base.BasePlotter
    options:
      show_root_heading: true
      show_source: true


::: goliat.analysis.plots.boxplot.BoxplotPlotter
    options:
      show_root_heading: true
      show_source: true


::: goliat.analysis.plots.bubble.BubblePlotter
    options:
      show_root_heading: true
      show_source: true


::: goliat.analysis.plots.cdf.CdfPlotter
    options:
      show_root_heading: true
      show_source: true


::: goliat.analysis.plots.correlation.CorrelationPlotter
    options:
      show_root_heading: true
      show_source: true


::: goliat.analysis.plots.heatmap.HeatmapPlotter
    options:
      show_root_heading: true
      show_source: true


::: goliat.analysis.plots.line.LinePlotter
    options:
      show_root_heading: true
      show_source: true


::: goliat.analysis.plots.outliers.OutliersPlotter
    options:
      show_root_heading: true
      show_source: true


::: goliat.analysis.plots.penetration.PenetrationPlotter
    options:
      show_root_heading: true
      show_source: true


::: goliat.analysis.plots.power.PowerPlotter
    options:
      show_root_heading: true
      show_source: true


::: goliat.analysis.plots.ranking.RankingPlotter
    options:
      show_root_heading: true
      show_source: true


::: goliat.analysis.plots.spatial.SpatialPlotter
    options:
      show_root_heading: true
      show_source: true


::: goliat.analysis.plots.tissue_analysis.TissueAnalysisPlotter
    options:
      show_root_heading: true
      show_source: true


---

## GUI Components

Graphical user interface for monitoring simulation progress.

### Analysis Gui

::: goliat.gui.analysis_gui.SignalingLogHandler
    options:
      show_root_heading: true
      show_source: true


### Progress Gui

::: goliat.gui.progress_gui.ProgressGUI
    options:
      show_root_heading: true
      show_source: true


### Queue Gui

::: goliat.gui.queue_gui.QueueGUI
    options:
      show_root_heading: true
      show_source: true


### Components

::: goliat.gui.components.clock_manager.ClockManager
    options:
      show_root_heading: true
      show_source: true


::: goliat.gui.components.data_manager.DataManager
    options:
      show_root_heading: true
      show_source: true


::: goliat.gui.components.graph_manager.GraphManager
    options:
      show_root_heading: true
      show_source: true


::: goliat.gui.components.machine_id_detector.MachineIdDetector
    options:
      show_root_heading: true
      show_source: true


::: goliat.gui.components.progress_animation.ProgressAnimation
    options:
      show_root_heading: true
      show_source: true


::: goliat.gui.components.progress_manager.ProgressManager
    options:
      show_root_heading: true
      show_source: true


::: goliat.gui.components.queue_handler.QueueHandler
    options:
      show_root_heading: true
      show_source: true


::: goliat.gui.components.screenshot_capture.ScreenshotCapture
    options:
      show_root_heading: true
      show_source: true


::: goliat.gui.components.status_manager.StatusManager
    options:
      show_root_heading: true
      show_source: true


::: goliat.gui.components.system_monitor.SystemMonitor
    options:
      show_root_heading: true
      show_source: true


::: goliat.gui.components.timings_table.TimingsTable
    options:
      show_root_heading: true
      show_source: true


::: goliat.gui.components.tray_manager.TrayManager
    options:
      show_root_heading: true
      show_source: true


::: goliat.gui.components.ui_builder.UIBuilder
    options:
      show_root_heading: true
      show_source: true


::: goliat.gui.components.utilization_manager.UtilizationManager
    options:
      show_root_heading: true
      show_source: true


::: goliat.gui.components.web_bridge_manager.WebBridgeManager
    options:
      show_root_heading: true
      show_source: true


### Components / Plots

::: goliat.gui.components.plots._matplotlib_imports
    options:
      show_root_heading: true
      show_source: true


::: goliat.gui.components.plots.overall_progress_plot.OverallProgressPlot
    options:
      show_root_heading: true
      show_source: true


::: goliat.gui.components.plots.pie_charts_manager.PieChartsManager
    options:
      show_root_heading: true
      show_source: true


::: goliat.gui.components.plots.system_utilization_plot.SystemUtilizationPlot
    options:
      show_root_heading: true
      show_source: true


::: goliat.gui.components.plots.time_remaining_plot.TimeRemainingPlot
    options:
      show_root_heading: true
      show_source: true


::: goliat.gui.components.plots.utils
    options:
      show_root_heading: true
      show_source: true


---

## AI Assistant

AI-powered assistant for error diagnosis and code assistance.

### Assistant

::: goliat.ai.assistant.GOLIATAssistant
    options:
      show_root_heading: true
      show_source: true


### Chat Handler

::: goliat.ai.chat_handler.ChatHandler
    options:
      show_root_heading: true
      show_source: true


### Config

::: goliat.ai.config.ModelConfig
    options:
      show_root_heading: true
      show_source: true


### Cost Tracker

::: goliat.ai.cost_tracker.CostTracker
    options:
      show_root_heading: true
      show_source: true


### Embedding Indexer

::: goliat.ai.embedding_indexer.EmbeddingIndexer
    options:
      show_root_heading: true
      show_source: true


### Error Advisor

::: goliat.ai.error_advisor.Recommendation
    options:
      show_root_heading: true
      show_source: true


### Query Processor

::: goliat.ai.query_processor.QueryProcessor
    options:
      show_root_heading: true
      show_source: true


### Types

::: goliat.ai.types
    options:
      show_root_heading: true
      show_source: true


---

## oSPARC Batch Processing

Batch processing and worker management for oSPARC cloud execution.

### Cleanup

::: goliat.osparc_batch.cleanup
    options:
      show_root_heading: true
      show_source: true


### File Finder

::: goliat.osparc_batch.file_finder
    options:
      show_root_heading: true
      show_source: true


### Gui

::: goliat.osparc_batch.gui.BatchGUI
    options:
      show_root_heading: true
      show_source: true


### Logging Utils

::: goliat.osparc_batch.logging_utils
    options:
      show_root_heading: true
      show_source: true


### Main Logic

::: goliat.osparc_batch.main_logic
    options:
      show_root_heading: true
      show_source: true


### Osparc Client

::: goliat.osparc_batch.osparc_client
    options:
      show_root_heading: true
      show_source: true


### Progress

::: goliat.osparc_batch.progress
    options:
      show_root_heading: true
      show_source: true


### Runner

::: goliat.osparc_batch.runner
    options:
      show_root_heading: true
      show_source: true


### Worker

::: goliat.osparc_batch.worker.Worker
    options:
      show_root_heading: true
      show_source: true


---

## Dispersion

Material dispersion fitting and caching.

### Fitter

::: goliat.dispersion.fitter.PoleFit
    options:
      show_root_heading: true
      show_source: true


### Material Cache

::: goliat.dispersion.material_cache
    options:
      show_root_heading: true
      show_source: true


---

## Utilities

Utility functions and helper modules.

### Bashrc

::: goliat.utils.bashrc
    options:
      show_root_heading: true
      show_source: true


### Config Setup

::: goliat.utils.config_setup
    options:
      show_root_heading: true
      show_source: true


### Core

::: goliat.utils.core.StudyCancelledError
    options:
      show_root_heading: true
      show_source: true


### Data

::: goliat.utils.data
    options:
      show_root_heading: true
      show_source: true


### Data Prep

::: goliat.utils.data_prep
    options:
      show_root_heading: true
      show_source: true


### Gui Bridge

::: goliat.utils.gui_bridge.WebGUIBridge
    options:
      show_root_heading: true
      show_source: true


### H5 Slicer

::: goliat.utils.h5_slicer.H5Slicer
    options:
      show_root_heading: true
      show_source: true


### Http Client

::: goliat.utils.http_client.HTTPClient
    options:
      show_root_heading: true
      show_source: true


### Mesh Slicer

::: goliat.utils.mesh_slicer
    options:
      show_root_heading: true
      show_source: true


### Message Sanitizer

::: goliat.utils.message_sanitizer.MessageSanitizer
    options:
      show_root_heading: true
      show_source: true


### Package

::: goliat.utils.package
    options:
      show_root_heading: true
      show_source: true


### Preferences

::: goliat.utils.preferences
    options:
      show_root_heading: true
      show_source: true


### Python Interpreter

::: goliat.utils.python_interpreter
    options:
      show_root_heading: true
      show_source: true


### Setup

::: goliat.utils.setup
    options:
      show_root_heading: true
      show_source: true


### Skin Voxel Utils

::: goliat.utils.skin_voxel_utils
    options:
      show_root_heading: true
      show_source: true


### Version

::: goliat.utils.version
    options:
      show_root_heading: true
      show_source: true


### Scripts

::: goliat.utils.scripts.cancel_all_jobs
    options:
      show_root_heading: true
      show_source: true


::: goliat.utils.scripts.keep_awake
    options:
      show_root_heading: true
      show_source: true


::: goliat.utils.scripts.prepare_antennas
    options:
      show_root_heading: true
      show_source: true


---

## CLI Commands

Entry point commands for running studies and analysis.

!!! note "CLI Commands"
    These are top-level CLI commands. Run `goliat --help` for full usage information.

| Command | Description |
|---------|-------------|
| `goliat study` | Run a simulation study |
| `goliat analyze` | Run post-processing analysis |
| `goliat parallel` | Run parallel study batches |
| `goliat worker` | Run as a cloud worker |
| `goliat free-space` | Run free-space validation |
| `goliat init` | Initialize GOLIAT environment |
| `goliat status` | Show setup status |
| `goliat validate` | Validate configuration files |
| `goliat version` | Show version information |