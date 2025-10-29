# Refactoring Plan: Aligning with a Single-Simulation Architecture

This plan follows the recommendations from the `refactoring_analysis.md` document, focusing on simplifying `SimulationRunner` and centralizing GUI control in the `Study` classes.

### Phase 1: Simplify `SimulationRunner`

The first step is to refactor `SimulationRunner` to be a lean, single-purpose class that only knows how to run one simulation and is completely unaware of the GUI.

1.  **Modify `SimulationRunner.__init__`**:
    *   Change the `simulations` parameter to accept only a single simulation object, not a `Union` or a `List`.
    *   Remove the `gui` and `study` parameters. The runner should no longer have direct access to the GUI proxy or the parent study.

2.  **Refactor `run` and Remove `run_all`**:
    *   Delete the `run_all` method.
    *   Move the core simulation logic from `run_all` into the `run` method.
    *   Remove all calls to `self.gui` (e.g., `self.gui.start_stage_animation`, `self.gui.update_stage_progress`) from the class.

### Phase 2: Consolidate GUI Logic in `Study` Classes

With `SimulationRunner` simplified, the `Study` classes will become the sole orchestrators of the GUI's stage progress bar for all phases (`setup`, `run`, and `extract`).

3.  **Update `FarFieldStudy._run_single_simulation`**:
    *   Before calling the refactored `SimulationRunner.run()`, add a call to `self.gui.update_stage_progress("Running Simulation", 0, 1)`.
    *   Start the GUI animation using `self.gui.start_stage_animation("run_simulation_total", 1)`.
    *   After `SimulationRunner.run()` completes, call `self.gui.end_stage_animation()`.
    *   Finally, update the stage progress to 100% with `self.gui.update_stage_progress("Running Simulation", 1, 1)`.

4.  **Update `NearFieldStudy._run_placement`**:
    *   Apply the same logic as in `FarFieldStudy`. Wrap the call to `SimulationRunner.run()` with the appropriate GUI start/end animation and progress update calls. This will make the GUI handling consistent across both study types.

### Phase 3: Update `ResultsExtractor` for Better Sub-Stage Reporting

To ensure the stage progress bar remains useful for multi-step phases like extraction, we will refine how `ResultsExtractor` reports its progress.

5.  **Refine `ResultsExtractor.extract`**:
    *   The `ResultsExtractor` already updates the stage progress for its sub-tasks (e.g., "Extracting Power", "Extracting SAR"). We will review this to ensure it provides a smooth and informative user experience. The total number of extraction steps will be calculated and passed to `update_stage_progress` to show granular progress (e.g., 1/3, 2/3, 3/3).

### Mermaid Diagram of Proposed Workflow

```mermaid
sequenceDiagram
    participant Study
    participant GUI
    participant SimulationRunner
    participant ResultsExtractor

    Note over Study: _run_single_simulation() starts
    Study->>GUI: update_stage_progress("Setup", 1, 1)

    Study->>GUI: update_stage_progress("Running Simulation", 0, 1)
    Study->>GUI: start_stage_animation("run_simulation_total", 1)
    Study->>SimulationRunner: run(simulation)
    SimulationRunner-->>Study: (blocks until complete)
    Study->>GUI: end_stage_animation()
    Study->>GUI: update_stage_progress("Running Simulation", 1, 1)

    Study->>ResultsExtractor: extract()
    ResultsExtractor->>GUI: update_stage_progress("Extracting Power", 1, 3)
    ResultsExtractor->>GUI: update_stage_progress("Extracting SAR", 2, 3)
    ResultsExtractor->>GUI: update_stage_progress("Saving Reports", 3, 3)
    ResultsExtractor-->>Study: (returns)
    Note over Study: _run_single_simulation() ends