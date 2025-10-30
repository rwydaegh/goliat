# GUI Feature Implementation Plan

This document outlines the technical plan for a set of approved feature enhancements for the `ProgressGUI`.

---

### 1. Simulation Counter

-   **Description:** A persistent label showing the current simulation number out of the total.
-   **Display:** `Simulation: 5 / 352`

### 2. Current Simulation Details

-   **Description:** A label showing the specific parameters of the simulation currently being processed.
-   **Display:** `Current Case: thelonious, 700MHz, front_of_eyes_center_vertical`

### 3. Dynamic Window Title

-   **Description:** Update the main window title to reflect the most critical information, allowing for at-a-glance monitoring when the application is minimized.
-   **Display:** `[8%] GOLIAT | Sim 29/352 | Running...`

### 4. Error/Warning Counter

-   **Description:** A non-intrusive counter that tracks the number of warnings and errors logged during the study.
-   **Display:** `⚠️ Warnings: 2 | ❌ Errors: 0`

### 5. Sub-Stage Label

-   **Description:** A secondary label, noted after a comma after the phase name which shows the the name of the granular sub-task currently being executed.
-   **Display:** `Setup, Voxelizing simulation...`

### 6. "Profiler" / "Timings" Tab

-   **Description:** A separate tab or collapsible section in the GUI that displays a table of all timed subtasks and their historical average durations from the `Profiler` object.
-   **Display:** A table with columns for `Phase`, `Subtask`, and `Average Time`.
