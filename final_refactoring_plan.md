# Final Refactoring Plan

This document outlines the comprehensive plan to address all issues confirmed in `counter_analysis.md`. The goal is to fix the critical profiling regression and resolve all medium-priority architectural inconsistencies.

### 1. Optimize Profiler I/O (Issue #4)

*   **File**: `src/profiler.py`
*   **Action**: Remove the call to `self.update_and_save_estimates()` from the `finally` block of the `subtask` method to prevent excessive disk I/O. The final save is already handled at the end of the study.

### 2. Standardize Profiling Architecture (Issues #1, #2, #5)

*   **Files**: `src/studies/far_field_study.py`, `src/studies/near_field_study.py`
*   **Action**:
    1.  In both study files, wrap the entire "Run Phase" logic (from `with profile(...)` onwards) in a `with self.subtask("run_simulation_total"):` block. This is the **critical fix** that restores the self-improving ETA for the run phase and provides user feedback.
    2.  In both study files, wrap the entire "Extraction Phase" logic (from `with profile(...)` onwards) in a `with self.subtask("extract_results_total"):` block. This makes the profiling pattern consistent across all three major phases (`setup`, `run`, `extract`).

### 3. Eliminate Code Duplication (Issue #3)

*   **File**: `src/studies/base_study.py`
    *   **Action**: Create a new private helper method, `_execute_run_phase(self, simulation)`. This method will encapsulate the entire, now-standardized "Run Phase" block.
*   **Files**: `src/studies/far_field_study.py`, `src/studies/near_field_study.py`
    *   **Action**: Replace the large, duplicated "Run Phase" code block in both files with a single, clean call to `self._execute_run_phase(simulation)`.

### 4. Clean Up Minor Issues (Issue #6)

*   **File**: `src/profiler.py`
*   **Action**: Remove the `TODO` comment and the commented-out logging code within the `subtask` method.

This plan will be executed sequentially to ensure a stable and verifiable refactoring process.