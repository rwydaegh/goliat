# Dosimetric Assessment Framework

This project provides a robust and automated Python framework for conducting both **near-field** and **far-field** dosimetric assessments for the GOLIAT project, using the Sim4Life simulation platform.

The framework is designed to be modular, scalable, and reproducible, handling a large matrix of simulation parameters to replicate and extend the studies detailed in the GOLIAT project documents.

## 1. Project Goal

The primary objective is to perform a comprehensive dosimetric assessment for the **thelonious** and **Eartha** child voxel phantoms across a wide range of frequencies and exposure scenarios. This includes:
- **Near-Field:** SAR simulations with device antennas placed close to the phantom.
- **Far-Field:** Whole-body exposure simulations from incident plane waves, covering both environmental and auto-induced scenarios.

### Key Deliverables

As specified in [`context/what we need.md`](context/what%20we%20need.md:1), the required outputs include whole-body SAR, head SAR, trunk SAR, and psSAR10g in various tissues, calculated for normalized applied power.

## 2. Architecture

The framework is designed around a clear, modular workflow that proceeds from configuration to results. The core logic is orchestrated by **Study** classes, which manage the entire simulation lifecycle.

### 2.1. Workflow Overview

A typical run follows these steps:

1.  **Configuration Loading**: The [`Config`](src/config.py:18) class loads a study-specific JSON file (e.g., [`near_field_config.json`](configs/near_field_config.json:1)). It intelligently merges this with a [`base_config.json`](configs/base_config.json:1) using an `extends` keyword, allowing for shared settings and specific overrides.

2.  **Study Orchestration**: A high-level **Study** class ([`NearFieldStudy`](src/studies/near_field_study.py) or [`FarFieldStudy`](src/studies/far_field_study.py)) takes control. It iterates through the defined simulation matrix (e.g., phantoms, frequencies, placements). This class is the main driver, calling all other components in sequence.

3.  **Project Management**: For each individual simulation run, the [`ProjectManager`](src/project_manager.py:11) handles the Sim4Life project file (`.smash`). Based on the `execution_control` config, it either creates a fresh project (deleting the old one) or opens an existing one for re-running or post-processing. It also includes validation checks to prevent working with corrupted or locked files.

4.  **Scene Setup**: A **Setup** class ([`NearFieldSetup`](src/setups/near_field_setup.py) or [`FarFieldSetup`](src/setups/far_field_setup.py)) builds the simulation scene. This is where the primary differences between study types emerge:
    *   **Near-Field**: The setup involves importing a specific antenna CAD model, which acts as the source of the EMF, and placing it at a precise distance and orientation relative to the phantom (e.g., 8mm from the cheek). This can also be run as a "free-space" simulation without a phantom to characterize the antenna alone.
    *   **Far-Field**: The setup defines one or more **plane wave** sources with specific incident directions (e.g., `x_pos`) and polarizations (e.g., `theta`). It does not involve placing a device.

5.  **Simulation Execution**: The [`SimulationRunner`](src/simulation_runner.py:13) executes the simulation by invoking the standalone `iSolve.exe` solver.

6.  **Results Extraction**: After the simulation completes, the [`ResultsExtractor`](src/results_extractor.py:11) performs post-processing. The extracted data differs significantly by study type:
    *   **Near-Field**: Results are stored in a dedicated folder for each unique combination of `phantom/frequency/placement`. The extractor calculates whole-body, head, or trunk SAR, as well as psSAR10g for specific tissue groups like the eyes and brain.
    *   **Far-Field**: Results are stored per `phantom/frequency`, but contain data for multiple simulations (one for each incident direction and polarization). The extractor generates comprehensive reports that aggregate SAR data across all these scenarios.

### 2.2. Key Supporting Components

-   **GUI & Logging**: A [`GuiManager`](src/gui_manager.py:86) provides a real-time progress window using PySide6, running the study in a separate process to keep the UI responsive. The [`LoggingManager`](src/logging_manager.py:5) sets up detailed logs for debugging and high-level progress tracking.
-   **Utilities**: The [`utils.py`](src/utils.py:1) module contains a [`Profiler`](src/utils.py:18) that learns from past runs to provide increasingly accurate ETA estimates for studies.

This separation of concerns ensures that each part of the process is self-contained, making the framework easier to maintain and extend.

## 3. Project Structure

The project is organized into a modular and scalable structure:

```
.
├── configs/
│   ├── base_config.json
│   ├── far_field_config.json
│   └── near_field_config.json
├── docs/
├── scripts/
├── analysis/
├── src/
│   ├── analysis/
│   ├── setups/
│   ├── studies/
│   ├── antenna.py
│   ├── config.py
│   ├── gui_manager.py
│   ├── logging_manager.py
│   ├── project_manager.py
│   ├── results_extractor.py
│   ├── simulation_runner.py
│   ├── startup.py
│   └── utils.py
├── run_study.py
├── material_name_mapping.json
└── requirements.txt
```

*Note: The `data`, `results`, and `logs` directories are not included in the repository and will be created locally.*

## 4. How to Run

### Prerequisites

Ensure you have **Sim4Life v8.2.0.16876** installed and licensed.

### Running a Study

All commands **must** be executed with the Python interpreter included with Sim4Life.

**Path to Python:** `"C:/Program Files/Sim4Life_8.2.0.16876/Python/python.exe"`

---

#### Other Examples

**Run a study:**

The GUI automatically launches when running `run_study.py`. It requires a configuration file

**Run a far-field study:**
```bash
"C:/Program Files/Sim4Life_8.2.0.16876/Python/python.exe" run_study.py --config "configs/far_field_config.json"
```

**Run a near-field study:**
```bash
"C:/Program Files/Sim4Life_8.2.0.16876/Python/python.exe" run_study.py --config "configs/near_field_config.json"
```

The script will automatically perform all necessary setup steps on the first run:
1.  **Install Dependencies**: From `requirements.txt`.
2.  **Download Data**: Phantoms and antennas.
3.  **Prepare Antennas**: Processes antenna models.

## 5. Configuration

The framework is controlled by a hierarchical JSON configuration system. A study-specific config (e.g., [`near_field_config.json`](configs/near_field_config.json:1)) inherits settings from a [`base_config.json`](configs/base_config.json:1) and can override them. This allows for a high degree of flexibility and avoids repetition.

The most important parameters are:
- **`extends`**: Defines the parent configuration file.
- **`study_type`**: Determines the simulation type (`"near_field"` or `"far_field"`).
- **`execution_control`**: A set of booleans (`do_setup`, `do_run`, `do_extract`) that control which parts of the workflow are executed. This is useful for re-running only a specific part of a study.
- **`phantoms`** and **`frequencies_mhz`**: The lists that define the core matrix of the study.

For a complete and detailed list of all available configuration parameters, please see the **[Configuration Documentation](configs/documentation.md)**.