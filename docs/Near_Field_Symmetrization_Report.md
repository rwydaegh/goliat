# Near-Field Study Symmetrization Report

## 1. Executive Summary

This document details the comprehensive refactoring effort undertaken to align the **Near-Field Study** with the new architectural features recently introduced for the Far-Field Study. The primary goal was to address critical divergences that would have caused significant operational issues, including a non-functional GUI, inaccurate progress estimation, and inconsistent logging when running near-field simulations.

The project is now in a robust, maintainable state where both `NearFieldStudy` and `FarFieldStudy` are first-class citizens, sharing a common, feature-rich execution framework.

## 2. The Core Problem: Architectural Divergence

The introduction of a sophisticated new framework—including a `ProgressGUI`, a `Profiler` for time estimation, and a dual-stream `logging_manager`—was successfully integrated into the `FarFieldStudy`. However, the `NearFieldStudy` and its associated setup modules were not updated, leading to several critical points of failure:

*   **Project Granularity Mismatch:** The `FarFieldStudy` manages a **one-to-many** relationship (one project file with many simulations), while the `NearFieldStudy` operates on a **one-to-one** basis (one project file per simulation). The new GUI and profiler were designed for the former, making them incompatible with the latter.
*   **Broken GUI and Profiling:** The `NearFieldStudy` lacked the necessary instrumentation to communicate with the `ProgressGUI`. This would result in a frozen UI, no progress updates, and highly inaccurate (or non-existent) time estimations.
*   **Inconsistent Logging:** The near-field workflow was not using the new `progress` and `verbose` loggers, meaning crucial, user-facing status updates would be missing from both the GUI and the dedicated `*.progress.log` files.
*   **Flawed Cancellation Logic:** A bug in the `SimulationRunner` prevented the `StudyCancelledError` from being handled correctly, affecting both study types and preventing graceful shutdowns.

## 3. The Refactoring Solution: A Multi-faceted Approach

To resolve these issues, a meticulous, multi-step refactoring process was executed.

### 3.1. Harmonizing the `NearFieldStudy`

The [`src/studies/near_field_study.py`](src/studies/near_field_study.py) module was completely overhauled to mirror the structure and logic of its far-field counterpart. Key changes include:

*   **Full Profiler and GUI Instrumentation:** The study now makes extensive use of the `profile()` context manager and directly calls `start_stage_animation()`, `update_stage_progress()`, and other methods to provide rich, real-time feedback to the user.
*   **Correct `execution_control` Handling:** The study now correctly interprets the `do_setup`, `do_run`, and `do_extract` flags, allowing for flexible and partial execution runs (e.g., re-running an extraction on an existing project).
*   **Graceful Cancellation:** The main simulation loop now includes a call to `_check_for_stop_signal()`, ensuring that a user-initiated stop request from the GUI is handled cleanly.

### 3.2. Unifying the Setup Modules

A significant issue was that several setup modules (`PlacementSetup`, `MaterialSetup`, `GriddingSetup`, `SourceSetup`) did not inherit from the common `BaseSetup` class. This was rectified to ensure a consistent architecture.

*   **Standardized Inheritance:** All setup modules were refactored to inherit from `BaseSetup`.
*   **Centralized Logging:** The `__init__` methods were updated to accept the `verbose_logger` and `progress_logger` objects, and all internal `_log()` calls were updated to use this centralized system. This ensures that all output is correctly routed to the console, the GUI, and the appropriate log files.

### 3.3. Fixing Critical Cancellation Logic

The most critical bug was the improper handling of the `StudyCancelledError`. This was addressed in three key files:

1.  **[`src/simulation_runner.py`](src/simulation_runner.py):**
    *   The `run_all()` method was wrapped in a `try...except StudyCancelledError` block to ensure that if any simulation is cancelled, the entire loop is gracefully terminated.
    *   The `_run_isolve_manual()` method was updated to check for the stop signal during the solver's execution, allowing for near-instantaneous cancellation of the external `iSolve.exe` process.

2.  **[`src/utils.py`](src/utils.py):**
    *   The `StudyCancelledError` custom exception was formally defined to ensure it was available across the project without causing import errors.

3.  **[`src/gui_manager.py`](src/gui_manager.py):**
    *   The `stop_study()` method was refactored to send a `'stop'` message to the worker process's queue, enabling a "soft" shutdown request.
    *   The `closeEvent()` method was improved to attempt a graceful shutdown by joining the process with a timeout before resorting to termination.

## 4. Outcome: A Robust and Symmetrical Framework

As a result of this comprehensive refactoring, the following has been achieved:

*   **Full Functional Parity:** The near-field study now behaves identically to the far-field study from the user's perspective, with a fully functional and responsive GUI.
*   **Improved Maintainability:** By enforcing a consistent architecture and inheritance model, the codebase is now significantly easier to understand, maintain, and extend.
*   **Enhanced Robustness:** The corrected cancellation logic and standardized logging make the entire framework more stable and predictable.

The project is now in an excellent state to proceed with running near-field simulations, with the confidence that the underlying framework is sound.