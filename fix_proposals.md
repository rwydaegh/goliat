# Proposed Fixes for "Time Remaining" ETA Calculation

Here are two potential approaches to fix the "Time Remaining" (ETA) calculation, ranging from a simple, immediate fix to a more robust, long-term solution.

## Approach 1: Quick Fix (Re-implementing the Pull Model)

This approach restores the old logic where the GUI "pulls" the ETA from the profiler on a timer, which is the simplest way to get the feature working again.

**Concept**: Modify the `ProgressGUI.update_clock` method to calculate the ETA on every tick, just as it did in the historical version.

**Implementation Steps**:

1.  **Update `ProgressGUI.update_clock`**:
    *   Check if `self.profiler` and `self.profiler.current_phase` exist.
    *   Get the current stage's progress from `self.stage_progress_bar.value()`.
    *   Call `self.profiler.get_time_remaining(current_stage_progress=...)`.
    *   Update the `eta_label` with the formatted result.

2.  **Enhance `Profiler.get_time_remaining`**:
    *   The current profiler's ETA calculation is too simplistic. It should be updated to factor in the progress of the *current* phase, not just the total elapsed time.
    *   The logic should be: `Time Remaining = (Time for current phase * (1 - progress_in_current_phase)) + (Sum of times for all remaining phases)`.

**Pros**:
*   **Fast to implement**: Requires changing only two methods.
*   **Low risk**: Re-introduces a previously working pattern.

**Cons**:
*   **Tightly couples the GUI and Profiler**: The GUI needs detailed knowledge of the profiler's internal state.
*   **Less efficient**: The calculation runs on a timer, even if no new information is available.

## Approach 2: Robust Fix (Implementing the Push Model with Signals)

This approach properly completes the intended refactoring by having the study "push" ETA updates to the GUI via signals. This is the more "correct" solution in a Qt environment.

**Concept**: Create a new signal in the `Study` worker that emits the updated ETA whenever significant progress is made. The GUI will have a slot to receive this signal and update the display.

**Implementation Steps**:

1.  **Create a New Signal**:
    *   In the `BaseStudy` class (or a worker class if one exists), define a new Qt signal, e.g., `eta_updated = Signal(float)`.

2.  **Emit the Signal**:
    *   Identify key points in the study's lifecycle where the ETA would change significantly (e.g., after a simulation completes, at the end of a major phase).
    *   At these points, call a method like `_calculate_and_emit_eta()`. This method would perform the calculation and then `self.eta_updated.emit(eta_in_seconds)`.

3.  **Create a Slot in the GUI**:
    *   In `ProgressGUI`, create a new slot, e.g., `def update_eta_label(self, eta_sec):`. This slot will format the time and update `self.eta_label`.

4.  **Connect Signal to Slot**:
    *   When the study/worker thread is created, connect the `eta_updated` signal to the `update_eta_label` slot.

**Pros**:
*   **Decoupled architecture**: The GUI becomes a passive receiver of information, which is a better design.
*   **More efficient**: ETA is only calculated and sent when needed, not on a polling timer.
*   **Aligns with Qt best practices**: Properly uses the signal/slot mechanism.

**Cons**:
*   **More complex to implement**: Requires changes across multiple files (study, worker, GUI) and a deeper understanding of Qt's threading model.

### Recommendation

For an immediate and reliable fix, **Approach 1** is recommended. It directly addresses the regression by restoring a known-good pattern.

For the long-term health and maintainability of the codebase, **Approach 2** is the superior solution. It would be the ideal choice if there is sufficient time to implement it correctly.

Given the context, I will proceed with writing the code for **Approach 1** as it provides the most direct path to resolving the immediate issue.