# Analysis of Far-Field Simulation Refactoring Artefacts

This document outlines the findings of a codebase analysis to identify remnants of a legacy feature where far-field simulations were bundled into a single `.smash` file. The goal is to identify areas for future refactoring to align the code with the current one-simulation-per-file paradigm.

## Table of Contents
1.  [Executive Summary](#executive-summary)
2.  [Key Findings](#key-findings)
3.  [Detailed Analysis](#detailed-analysis)
    - [The Stage Progress and Animation System](#the-stage-progress-and-animation-system)
    - [GUI, Logging, and Profiler](#gui-logging-and-profiler)
    - [Project Manager and Setups](#project-manager-and-setups)
    - [`SimulationRunner`](#simulationrunner)
    - [`FarFieldStudy` and `NearFieldStudy`](#farfieldstudy-and-nearfieldstudy)
    - [`ResultsExtractor`](#resultsextractor)
    - [Configuration Files](#configuration-files)
4.  [Recommendations for Refactoring](#recommendations-for-refactoring)

## Executive Summary

The codebase has been largely refactored to support the one-simulation-per-`.smash`-file paradigm. The `FarFieldStudy` and `NearFieldStudy` classes now correctly orchestrate the creation of individual projects for each simulation case. However, a significant artifact of the old multi-simulation architecture remains in the `SimulationRunner` class, which is still designed to handle lists of simulations. This creates unnecessary complexity and architectural dissonance.

Other high-level modules like the GUI, profiler, and loggers are sufficiently abstract and function correctly, though the GUI's "stage progress" bar and its interaction with the `SimulationRunner` is a clear sign of the old design. The `ResultsExtractor`, `ProjectManager`, and `Setup` modules are clean.

The primary recommendation is to refactor the `SimulationRunner` to handle only a single simulation, and to consolidate the GUI logic for each simulation phase (`setup`, `run`, `extract`) within the `Study` classes.

## Key Findings

- **`SimulationRunner` is a Legacy Component**: The `SimulationRunner` class is the most prominent artifact. It is designed to accept and iterate over a list of simulations, a feature that is no longer used as intended.
- **`FarFieldStudy` and `NearFieldStudy` are Partially Refactored**: Both study classes correctly create a separate project for each simulation but use the `SimulationRunner` inefficiently by passing it a list containing only one simulation.
- **GUI Logic is Split**: The logic for updating the GUI's "stage progress" bar is split between the `Study` classes (for `setup` and `extract`) and the `SimulationRunner` (for `run`), which is a direct consequence of the `SimulationRunner`'s legacy design.
- **Core Components are Clean**: The `ResultsExtractor`, `ProjectManager`, `Setup` modules, `Profiler`, and `LoggingManager` are all clean and aligned with the new single-simulation architecture.
- **Configuration Files Provide Context**: The structure of `far_field_config.json` (with its arrays of directions and polarizations) explains the original design of the `SimulationRunner`, but the file itself is not an issue as it is now interpreted correctly.

## Detailed Analysis

### The Stage Progress and Animation System

A deeper analysis of the GUI and its interaction with the `Profiler` and `SimulationRunner` reveals a subtle but important artifact of the old architecture. The system is composed of two progress bars: "Overall Progress" and "Stage Progress".

-   **Overall Progress**: This bar is driven by the `Profiler`'s phase-based weighting (`setup`, `run`, `extract`). It shows the progress of the entire study (e.g., "we are 50% through the total work"). This high-level view is agnostic to the simulation structure and works correctly in the new architecture.
-   **Stage Progress**: This bar is intended to show progress *within* a single phase. Its behavior is the source of the confusion.

#### How it Works (and Where the Artifact Lies)

1.  **Communication**: The `Study` process (running the simulation) communicates with the `GUI` process via a `multiprocessing.Queue`. The `QueueGUI` class in `gui_manager.py` is a proxy that sends messages to this queue.
2.  **Phase Updates**: For the `setup` and `extract` phases, the `Study` classes directly call `gui.update_stage_progress(...)`, treating the entire phase as a single stage (0% to 100%).
3.  **The "Run" Phase Anomaly**: The `run` phase is different. The `Study` class hands off control to the `SimulationRunner`. The `SimulationRunner`'s `run_all` method then takes over the stage progress updates.
    -   **Legacy Behavior**: In the old system, `run_all` would receive a list of simulations (e.g., 12 polarizations/directions). It would call `update_stage_progress("Running Simulation", 0, 12)` and then loop, calling `update_stage_progress("Running Simulation", i + 1, 12)` after each simulation. The stage bar would correctly show "1/12", "2/12", etc.
    -   **Current Behavior**: Now, `run_all` receives a list with only one simulation. The stage bar shows "0/1" and then "1/1".
4.  **The Animation System**: The animation system is layered on top of the stage progress bar. When `gui.start_stage_animation(task_name, end_value)` is called, it does the following:
    -   It asks the `Profiler` for the historical average time of `task_name` (e.g., `run_simulation_total`).
    -   It tells the `ProgressGUI` to start a smooth animation of the stage progress bar, moving it from its current value to a new target value (`end_value`) over the estimated duration.
    -   In the legacy system, `end_value` would be `i + 1`, so the bar would animate from 0% to 8.3% (1/12), then from 8.3% to 16.7% (2/12), and so on.
    -   In the current system, it animates from 0% to 100% (1/1) for the single simulation.

#### Conclusion

The stage progress bar and its associated animation system were designed for a `run` phase composed of multiple sub-stages (simulations). While the system still *functions*, the logic is now unnecessarily complex and spread across multiple classes. The `SimulationRunner`'s involvement in GUI updates is a direct artifact of this old design.

### GUI, Logging, and Profiler

These high-level managers are largely agnostic to the underlying simulation architecture.

-   **`logging_manager.py`**: Provides a generic logging service and is completely decoupled from the simulation structure. It is clean.
-   **`profiler.py`**: Tracks progress based on abstract "phases" (`setup`, `run`, `extract`). Its logic works correctly whether the "run" phase consists of one or many simulations.
-   **`gui_manager.py`**: As detailed above, the stage progress bar's logic is a clear artifact of the old system.

### Project Manager and Setups

A final review of these modules confirms they are aligned with the new architecture.

-   **`far_field_setup.py`**: This class is responsible for creating only a *single* simulation entity per execution.
-   **`project_manager.py`**: This class is designed to manage a single project at a time, with its "Verify and Resume" feature operating on a one-to-one basis between a simulation's metadata and its output files.

**Conclusion**: These core components are clean and do not contain any multi-simulation artifacts.

### `SimulationRunner`

The `SimulationRunner` class is a significant artifact of the old architecture.

- **`__init__` Method**: The `simulations` parameter is explicitly typed to accept a `Union` of a single simulation object or a `List` of simulation objects. The code immediately converts any single simulation into a list of one.
- **`run_all` Method**: This method is designed to iterate over `self.simulations` and run each one. Its name and logic clearly indicate its original purpose was to handle multiple simulations within the same project context.

**Conclusion**: This class is the most direct piece of evidence of the old multi-simulation paradigm.

### `FarFieldStudy` and `NearFieldStudy`

Both study classes have been adapted to the new one-simulation-per-project model, but their interaction with `SimulationRunner` reveals the architectural mismatch.

- **Single Simulation Logic**: The main loop in both studies calls a method for each individual simulation case, instantiating a new `SimulationRunner` for *each simulation*.
- **Inefficient Usage**: Crucially, both studies pass a *single* simulation object to the `SimulationRunner`, and then call `runner.run_all()`, which forces the `SimulationRunner` to iterate through its list of one.

**Conclusion**: The study orchestration logic is correct, but it uses a legacy component (`SimulationRunner`) in a way that is inefficient and confusing.

#### Near-Field Study: A Closer Look at Stage Progress

A focused analysis of the `NearFieldStudy` reveals how the stage progress bar is used outside of the `run` phase, confirming that the bar itself is a useful component that should be refactored, not removed.

-   **Phase-Level Progress**: The `_run_placement` method in `near_field_study.py` explicitly updates the stage progress for each major phase:
    -   `gui.update_stage_progress("Setup", 1, 1)` is called after the setup is complete.
    -   `gui.update_stage_progress("Run", 1, 1)` is called after the `SimulationRunner` finishes.
    -   `gui.update_stage_progress("Extracting Results", 0, 1)` and `...("Extracting Results", 1, 1)` are called at the beginning and end of the extraction phase.
-   **Sub-Phase Progress**: Furthermore, the `ResultsExtractor` itself uses the stage progress bar to show finer-grained steps within the extraction phase, such as "Extracting Power" and "Extracting SAR".

This demonstrates that the stage progress bar is a flexible UI element used to show progress for any given "stage," whether that stage is a whole phase (like `setup`) or a sub-task within a phase (like `Extracting Power`). The core issue is that the `SimulationRunner` incorrectly takes control of this UI element, a responsibility that should lie with the orchestrating `Study` class.

### `ResultsExtractor`

The `ResultsExtractor` class appears to have been fully refactored.

- **Single Simulation Focus**: The `__init__` method accepts only a single `simulation` object.
- **No Iteration Logic**: The `extract` method contains no loops or logic for handling multiple simulations from a single `.smash` file.

**Conclusion**: This module is clean and does not contain artifacts of the old system.

### Configuration Files

The configuration files, particularly `configs/far_field_config.json`, provide the context for the old architecture.

- **`incident_directions` and `polarizations`**: The presence of these arrays explains *why* `SimulationRunner` was designed to handle lists.
- **Current Interpretation**: The modern `Study` classes now iterate over these arrays to create a separate project for each individual simulation, which is the correct behavior.

**Conclusion**: The configuration files are not artifacts themselves, but they are a reflection of the original design.

## Recommendations for Refactoring

Based on the analysis, the following refactoring actions are recommended to fully align the codebase with the single-simulation-per-project architecture and improve code clarity and efficiency.

1.  **Simplify `SimulationRunner` to Handle a Single Simulation:**
    -   **Modify `__init__`**: Change the `simulations` parameter to accept only a single simulation object, not a `Union` or a `List`. Remove all GUI-related parameters (`gui`, `study`).
    -   **Remove `run_all` Method**: The `run_all` method is now redundant. Its logic should be merged into the `run` method.
    -   **Simplify `run` Method**: The `run` method should now only contain the logic to execute a single simulation. It should not be responsible for any GUI updates.

2.  **Consolidate GUI Logic into the Study Classes:**
    -   The responsibility for updating the GUI's stage progress bar should be moved entirely into the `Study` classes (`NearFieldStudy` and `FarFieldStudy`).
    -   Each `_run_single_simulation` or `_run_placement` method should explicitly manage the GUI state for the `setup`, `run`, and `extract` phases of a single simulation.
    -   This involves calling `update_stage_progress`, `start_stage_animation`, and `end_stage_animation` directly from the study class, providing a clear, linear workflow for the GUI.

3.  **Update `FarFieldStudy` and `NearFieldStudy` to Use the Simplified Components:**
    -   The instantiation of `SimulationRunner` in both studies should be updated to use the new, simplified interface.
      ```python
      # Before (in both studies)
      runner = SimulationRunner(..., simulation, ..., gui=self.gui, study=self)
      runner.run_all()
      
      # After (in both studies)
      if self.gui: self.gui.start_stage_animation(...)
      runner = SimulationRunner(..., simulation, ...)
      runner.run()
      if self.gui: self.gui.end_stage_animation(...)
      ```

By implementing these changes, the `SimulationRunner` will be transformed from a confusing legacy component into a clean, single-purpose class. The GUI logic will be centralized in the `Study` classes, making the overall workflow more explicit and easier to maintain.