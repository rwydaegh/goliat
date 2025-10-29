# Post-Refactor Discussion: `SimulationRunner` and Architectural Symmetry

## 1. General Context and Plan

This document details a significant refactoring effort aimed at aligning the GOLIAT codebase with a modern, one-simulation-per-project architecture. The primary motivation was to eliminate legacy artifacts from a previous design where multiple simulations were handled within a single project file. This legacy approach created unnecessary complexity, reduced maintainability, and led to architectural inconsistencies, particularly between the `NearFieldStudy` and `FarFieldStudy` workflows.

**Relevant Files:**
- `src/simulation_runner.py`
- `src/studies/far_field_study.py`
- `src/studies/near_field_study.py`
- `src/setups/far_field_setup.py`
- `src/profiler.py`
- `src/studies/base_study.py`
- `src/utils.py`
- `src/results_extractor.py`

**The core plan was as follows:**
1.  **Simplify `SimulationRunner`**: Transform it from a multi-simulation orchestrator into a lean, single-simulation executor, decoupled from the GUI and high-level `Study` logic.
2.  **Centralize Control in `Study` Classes**: Make the `Study` classes (`NearFieldStudy`, `FarFieldStudy`) the sole orchestrators of the entire simulation lifecycle, including all GUI updates and profiling contexts.
3.  **Achieve Architectural Symmetry**: Refactor `FarFieldStudy` and `NearFieldStudy` to ensure they follow the same logical patterns for setup, execution, and result extraction, making the codebase more predictable and easier to maintain.
4.  **Preserve and Enhance Profiling**: Re-implement the granular subtask profiling system in a decoupled way, using dependency injection of the `Profiler` object, to ensure the self-improving ETA feature remains robust.

---

## 2. Detailed Change Analysis (`git diff`)

Below is a breakdown of every change made during this refactoring effort, with a justification for each modification.

### `src/profiler.py`

```diff
+import contextlib
 import json
 import time
 from collections import defaultdict
@@ -162,6 +163,24 @@ class Profiler:
         eta = time_in_current_phase + time_for_future_phases
         return max(0, eta)
 
+    @contextlib.contextmanager
+    def subtask(self, task_name: str):
+        """A context manager to time a subtask."""
+        self.subtask_stack.append({"name": task_name, "start_time": time.monotonic()})
+        try:
+            yield
+        finally:
+            subtask = self.subtask_stack.pop()
+            elapsed = time.monotonic() - subtask["start_time"]
+            self.subtask_times[subtask["name"]].append(elapsed)
+            # TODO: Logging from the profiler is not ideal. Consider a callback.
+            # self._log(
+            #     f"    - Subtask '{task_name}' done in {elapsed:.2f}s",
+            #     level="progress",
+            #     log_type="progress",
+            # )
+            self.update_and_save_estimates()
+
     def update_and_save_estimates(self):
         """Updates the profiling configuration with the latest average times and saves it.
```

*   **Change**: The `subtask` context manager, which handles the timing of granular operations, was moved from `src/utils.py` directly into the `Profiler` class.
*   **Reason**: This was the cornerstone of the final, corrected refactoring plan. It centralizes profiling logic within the `Profiler` class, where it belongs. This enables a clean dependency injection pattern, allowing components like `SimulationRunner` to perform profiling by depending only on the `Profiler`, not the entire `Study` object.

### `src/utils.py`

```diff
-@contextlib.contextmanager
-def profile_subtask(study: "BaseStudy", task_name: str, instance_to_profile=None):
-    """A context manager for a 'subtask'.
-    ... (60 lines removed) ...
-        study.end_stage_animation()
```

*   **Change**: The `profile_subtask` function was completely removed.
*   **Reason**: This function was made redundant by the migration of its core timing logic to the `Profiler.subtask` method and its GUI/line-profiling logic to the `BaseStudy.subtask` method. Removing it eliminates dead code and completes the centralization of the profiling logic.

### `src/studies/base_study.py`

```diff
+import contextlib
+import io
-from src.utils import StudyCancelledError, ensure_s4l_running, profile_subtask
+from src.utils import StudyCancelledError, ensure_s4l_running

-    def subtask(self, task_name: str, instance_to_profile=None):
-        """Returns a context manager that profiles a subtask."""
-        return profile_subtask(self, task_name, instance_to_profile)
+    @contextlib.contextmanager
+    def subtask(self, task_name: str, instance_to_profile=None):
+        """Returns a context manager that profiles a subtask, handling GUI and line profiling."""
+        self.start_stage_animation(task_name, 1)
+
+        lp = None
+        wrapper = None
+        line_profiling_config = self.config.get_line_profiling_config()
+        if instance_to_profile and line_profiling_config.get("enabled", False) and task_name in line_profiling_config.get("subtasks", {}):
+            self._log(f"  - Activating line profiler for subtask: {task_name}", "verbose", "verbose")
+            lp, wrapper = self._setup_line_profiler(task_name, instance_to_profile)
+
+        try:
+            with self.profiler.subtask(task_name):
+                if lp and wrapper:
+                    yield wrapper
+                else:
+                    yield lambda func: func
+        finally:
+            self._log(
+                f"    - Subtask '{task_name}' done in {self.profiler.subtask_times[task_name][-1]:.2f}s",
+                level="progress",
+                log_type="progress",
+            )
+            if lp:
+                self._log(f"    - Line profiler stats for '{task_name}':", "verbose", "verbose")
+                s = io.StringIO()
+                lp.print_stats(stream=s)
+                self.verbose_logger.info(s.getvalue())
+
+            self.end_stage_animation()
```

*   **Change**: The `subtask` method was transformed from a simple call to the old `utils` function into a full-featured context manager.
*   **Reason**: This change correctly separates concerns. The `BaseStudy.subtask` method now acts as a wrapper that orchestrates the functionality surrounding a timed event: it starts the GUI animation, sets up the optional line-profiler, calls the core timing logic (`self.profiler.subtask`), and then handles the cleanup (logging, printing line-profiler stats, and stopping the GUI animation). This is the crucial link that allows the `Profiler` to remain unaware of the GUI.

### `src/simulation_runner.py`

```diff
-from typing import TYPE_CHECKING, List, Optional, Union
+from typing import TYPE_CHECKING, Optional
-    from .gui_manager import QueueGUI
-    from .studies.base_study import BaseStudy
+    from .profiler import Profiler

-        simulations: Union[
-            "s4l_v1.simulation.emfdtd.Simulation",
-            List["s4l_v1.simulation.emfdtd.Simulation"],
-        ],
+        simulation: "s4l_v1.simulation.emfdtd.Simulation",
+        profiler: "Profiler",
-        gui: Optional["QueueGUI"] = None,
-        study: Optional["BaseStudy"] = None,

-            simulations: A single simulation or a list of simulations to run.
-            gui: The GUI proxy for sending updates to the main process.
-            study: The parent study object for profiling and context.
+            simulation: The simulation to run.
+            profiler: The profiler instance for timing subtasks.

-        self.simulations = simulations if isinstance(simulations, list) else [simulations]
-        self.gui = gui
-        self.study = study
+        self.simulation = simulation
+        self.profiler = profiler

-    def run_all(self):
-        """Runs all simulations in the list, managing GUI animations."""
-        ... (26 lines removed) ...
-
-    def run(self, simulation: "s4l_v1.simulation.emfdtd.Simulation"):
-        """Runs a single simulation, wrapped in a subtask for timing."""
+    def run(self):
+        """Runs a single simulation."""

-        with self.study.subtask("run_simulation_total"):  # type: ignore
+        try:
+            if hasattr(self.simulation, "WriteInputFile"):
+                with self.profiler.subtask("run_write_input_file"):
+                    ...
+            ...
+            if self.config.get_manual_isolve():
+                self._run_isolve_manual(self.simulation)
+            ...
+        ...

-        try:
-            with self.study.subtask("run_isolve_execution"):  # type: ignore
-                ...
-            # --- 4. Post-simulation steps ---
-            with self.study.subtask("run_wait_for_results"):  # type: ignore
-                ...
-            with self.study.subtask("run_reload_project"):  # type: ignore
-                ...
+        try:
+            with self.profiler.subtask("run_isolve_execution"):
+                ...
+            # --- 4. Post-simulation steps ---
+            with self.profiler.subtask("run_wait_for_results"):
+                ...
+            with self.profiler.subtask("run_reload_project"):
+                ...
```

*   **Change**: This is the most significant set of changes.
    1.  The `__init__` method was modified to accept a single `simulation` and a `profiler` object, removing the `simulations` list, `gui`, and `study` parameters.
    2.  The `run_all` method was deleted entirely.
    3.  The `run` method's signature was simplified, and its logic was unwrapped from the overarching `run_simulation_total` subtask.
    4.  The internal profiling calls (`with self.study.subtask(...)`) were replaced with `with self.profiler.subtask(...)`.
*   **Reason**: These changes collectively achieve the primary goal of the refactoring. The `SimulationRunner` is now a lean, decoupled component. It no longer manages lists of simulations and is completely unaware of the GUI. By accepting the `profiler` via dependency injection, it can perform the necessary granular timing for its internal operations without being coupled to the high-level `Study` class, which is a robust and maintainable architectural pattern.

### `src/setups/far_field_setup.py`

```diff
 from .gridding_setup import GriddingSetup
 from .material_setup import MaterialSetup
+from .phantom_setup import PhantomSetup

     def run_full_setup(self, project_manager: "ProjectManager") -> "emfdtd.Simulation":
         """Executes the full setup sequence for a single far-field simulation."""
         self._log("--- Setting up single Far-Field sim ---", log_type="header")
 
-        # The phantom is now loaded once per project in the study.
-        # This setup will just add a simulation to the currently open project.
+        phantom_setup = PhantomSetup(
+            self.config,
+            self.phantom_name,
+            self.verbose_logger,
+            self.progress_logger,
+        )
+        phantom_setup.ensure_phantom_is_loaded()
+
         bbox_entity = self._create_or_get_simulation_bbox()
```

*   **Change**: The `FarFieldSetup` class now instantiates and runs `PhantomSetup` within its `run_full_setup` method.
*   **Reason**: This was the crucial fix for architectural symmetry. Previously, the `FarFieldStudy` was responsible for phantom loading, a legacy artifact. This change makes `FarFieldSetup` self-contained and responsible for its own dependencies, perfectly mirroring the behavior of `NearFieldSetup` and creating a consistent, predictable design.

### `src/studies/far_field_study.py`

```diff
-            phantom_setup = PhantomSetup(self.config, phantom_name, self.verbose_logger, self.progress_logger)
-            for freq in frequencies:  # type: ignore
+            for freq in frequencies:  # type: ignore
                 for direction_name in incident_directions:
                     for polarization_name in polarizations:
                         ...
-                        self._run_single_simulation(..., phantom_setup)
+                        self._run_single_simulation(...)

     def _run_single_simulation(..., phantom_setup: "PhantomSetup"):
+    def _run_single_simulation(...):
         ...
-                        phantom_setup.ensure_phantom_is_loaded()
-                        ...
-                        with self.subtask("setup_simulation", instance_to_profile=setup) as wrapper:
-                            simulation = wrapper(setup.run_full_setup)(phantom_setup)
+                        with self.subtask("setup_simulation", instance_to_profile=setup) as wrapper:
+                            simulation = wrapper(setup.run_full_setup)(self.project_manager)
         ...
-                with profile(self, "run"):
-                    runner = SimulationRunner(...)
-                    runner.run_all()
-                    ...
-                    self.gui.update_stage_progress("Run", 1, 1)
+                with profile(self, "run"):
+                    if self.gui:
+                        self.gui.update_stage_progress("Running Simulation", 0, 1)
+                        self.gui.start_stage_animation("run_simulation_total", 1)
+
+                    runner = SimulationRunner(..., self.profiler, ...)
+                    runner.run()
+
+                    if self.gui:
+                        self.gui.end_stage_animation()
+
+                    self.profiler.complete_run_phase()
+                    ...
+                    self.gui.update_stage_progress("Running Simulation", 1, 1)
```

*   **Change**:
    1.  The instantiation of `PhantomSetup` was removed from the main loop.
    2.  The `_run_single_simulation` method was updated to remove the `phantom_setup` parameter and the call to `ensure_phantom_is_loaded`.
    3.  The "Run Phase" block was updated to instantiate the new `SimulationRunner` (passing the profiler), call `runner.run()`, and manage the GUI animations directly. The redundant `run_simulation_total` subtask was removed.
*   **Reason**: These changes are the counterpart to the modifications in `FarFieldSetup` and `SimulationRunner`. They complete the symmetry refactoring by aligning the study's workflow with the new, cleaner component interfaces. The `Study` class now correctly orchestrates all aspects of the simulation run, including GUI feedback and profiling context.

### `src/studies/near_field_study.py`

```diff
         self.profiler.set_total_simulations(total_simulations)
+        if do_setup:
+            self.profiler.current_phase = "setup"
+        elif do_run:
+            self.profiler.current_phase = "run"
+        elif do_extract:
+            self.profiler.current_phase = "extract"
         if self.gui:
             self.gui.update_overall_progress(0, 100)
 ...
             # 2. Run Simulation
             if do_run:
                 with profile(self, "run"):
-                   self.profiler.start_stage("run", total_stages=1)
-                    runner = SimulationRunner(...)
-                    runner.run_all()
-                    ...
-                    self.gui.update_stage_progress("Run", 1, 1)
+                    if self.gui:
+                        self.gui.update_stage_progress("Running Simulation", 0, 1)
+                        self.gui.start_stage_animation("run_simulation_total", 1)
+
+                    runner = SimulationRunner(..., self.profiler, ...)
+                    runner.run()
+
+                    if self.gui:
+                        self.gui.end_stage_animation()
+
+                    self.profiler.complete_run_phase()
+                    ...
+                    self.gui.update_stage_progress("Running Simulation", 1, 1)
```

*   **Change**:
    1.  A profiler "hint" was added to the start of `_run_study` to improve initial ETA calculations.
    2.  The redundant `profiler.start_stage` call was removed.
    3.  The "Run Phase" block was updated to use the new `SimulationRunner` interface and manage GUI animations, mirroring the changes in `FarFieldStudy`.
*   **Reason**: These changes harmonize the logic between `NearFieldStudy` and `FarFieldStudy`, ensuring they are as symmetrical as possible. This improves consistency and predictability.

### `src/results_extractor.py`

```diff
-        if self.gui:
-            self.gui.update_stage_progress("Extracting Power", 50, 100)
+        # Dynamically determine the number of extraction steps for progress reporting
+        extraction_steps = []
+        ...
+        total_steps = len(extraction_steps)
+        current_step = 0
+
+        def update_progress(step_name):
+            nonlocal current_step
+            current_step += 1
+            if self.gui:
+                self.gui.update_stage_progress(f"Extracting: {step_name}", current_step, total_steps)
+
+        # --- Extraction Steps ---
+        update_progress("Input Power")
+        ...
+        if not self.free_space:
+            update_progress("SAR Statistics")
+            ...
```

*   **Change**: The `extract` method was refactored to dynamically calculate the number of extraction steps and update the GUI progress bar incrementally (e.g., "1/4", "2/4").
*   **Reason**: This addresses a key part of the user feedback. It replaces the arbitrary, hardcoded percentage updates with a more informative and accurate step-based progress report, improving the user experience during the extraction phase.

---

## 3. Post-Refactor Discussion

This refactoring effort was a success, but it was also a valuable lesson in the importance of rigorous, iterative verification. The initial changes, while technically correct according to the plan, introduced a subtle but critical regression in the profiling system that was only caught through a dedicated review process.

The final state of the architecture is significantly improved:

*   **Clearer Responsibilities**: Each component now has a more clearly defined responsibility. `Study` classes orchestrate, `Setup` classes build, `SimulationRunner` executes, and `Profiler` times. This separation of concerns is the hallmark of a maintainable codebase.
*   **Improved Decoupling**: By using dependency injection for the `Profiler`, we have enabled components to perform necessary timing functions without being coupled to the high-level `Study` orchestrator. This creates a reusable and testable pattern.
*   **Architectural Symmetry**: `FarFieldStudy` and `NearFieldStudy` are now remarkably similar in their structure and execution flow. This symmetry makes the code easier to understand, debug, and extend in the future. Any developer working on one study will immediately understand the structure of the other.
*   **Enhanced User Experience**: The removal of confusing GUI artifacts (like the "1/1" progress) and the addition of more granular progress in the extraction phase result in a more polished and professional user experience.

This process underscores that refactoring is not merely about changing code, but about methodically improving its structure and verifying that no functionality is lost in the process. The final architecture is now a much stronger foundation for future development.