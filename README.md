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

5.  **Simulation Execution**: The [`SimulationRunner`](src/simulation_runner.py:13) executes the simulation. It supports three modes:
    *   **Local Manual Run**: It generates the solver input file and waits for the user to manually launch `iSolve.exe`. This is the default for GUI-based runs.
    *   **Local Automated Run**: It directly invokes the standalone `iSolve.exe` solver and waits for it to complete.
    *   **Cloud Run**: It submits the simulation to a specified cloud-based oSPARC server using the oSPARC API. This is controlled by the `server` and `osparc_credentials` settings in the configuration.

6.  **Results Extraction**: After the simulation completes, the [`ResultsExtractor`](src/results_extractor.py:11) performs post-processing. The extracted data differs significantly by study type:
    *   **Near-Field**: Results are stored in a dedicated folder for each unique combination of `phantom/frequency/placement`. The extractor calculates whole-body, head, or trunk SAR, as well as psSAR10g for specific tissue groups like the eyes and brain.
    *   **Far-Field**: Results are stored per `phantom/frequency`, but contain data for multiple simulations (one for each incident direction and polarization). The extractor generates comprehensive reports that aggregate SAR data across all these scenarios.

### 2.2. Key Supporting Components

-   **GUI & Multiprocessing**: A [`GuiManager`](src/gui_manager.py:86) provides a real-time progress window using PySide6. To ensure the UI remains responsive and stable, the entire study is executed in a separate process using Python's `multiprocessing` module. Communication between the GUI and the study process is handled via queues and events.
-   **Logging**: The [`LoggingManager`](src/logging_manager.py:5) sets up detailed logs for debugging and high-level progress tracking. It now features colored output for improved readability in the console.
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
└── requirements.txt
```

*Note: The `data`, `results`, and `logs` directories are not included in the repository and will be created locally.*

## 4. How to Run

### Prerequisites

Ensure you have **Sim4Life v8.2.2** or later installed and licensed.

### Running a Study

To simplify running studies, you can source a local `.bashrc` file to add the Sim4Life Python executable to your shell's `PATH` for the current session.

**1. One-Time Setup**

If your Sim4Life installation path is different from the default, update the `.bashrc` file in the project's root directory with the correct path.

**2. Activate the Environment**

Before running a study, source the `.bashrc` file to update your `PATH`:

```bash
source .bashrc
```

**3. Run the Study**

The study is now launched through a graphical user interface (GUI).

```bash
python run_study.py
```

This will open the main application window. From there, you can:
1.  **Load a Configuration**: Use the "Load Config" button to select a study file (e.g., `configs/near_field_config.json`).
2.  **Start the Study**: Click "Run Study" to begin the simulation process.
3.  **Monitor Progress**: The GUI will display real-time progress, logs, and ETA estimates.

The script will automatically perform all necessary setup steps on the first run:
1.  **Install Dependencies**: From `requirements.txt`.
2.  **Download Data**: Phantoms and antennas.
3.  **Prepare Antennas**: Processes antenna models.

## 5. oSPARC Batch Run

For large-scale studies, this framework supports batch submissions to oSPARC, allowing for massively parallel simulations. This is ideal for scenarios where you need to run hundreds or thousands of simulations efficiently.

The process is designed in three stages to ensure a smooth workflow:

1.  **Input File Generation**: First, you generate all the necessary solver input files (`.h5`). This is done locally. In your configuration file (e.g., `configs/todays_far_field_config.json`), modify the `execution_control` section as follows:

    ```json
    "execution_control": {
        "do_setup": true,
        "only_write_input_file": true,
        "do_run": false,
        "do_extract": false,
        "batch_run": false
    }
    ```

    Then, run the study: `python run_study.py --config configs/your_config.json`. The framework will prepare all simulation input files without running the simulations.

2.  **Batch Submission to oSPARC**: Once the input files are generated, you can submit them to oSPARC in a batch. Update the `execution_control` to enable `batch_run`:

    ```json
    "execution_control": {
        "batch_run": true
    }
    ```

    Now, execute the study script again: `python run_study.py --config configs/your_config.json`. This will launch a GUI that monitors the progress of all your oSPARC jobs in real-time. It will handle job submission, status polling, and result downloads automatically.

3.  **Post-Processing and Analysis**: After all oSPARC jobs have completed and the results are downloaded, the final step is to analyze the outputs. Disable the `batch_run` and enable `do_extract` in your configuration:

    ```json
    "execution_control": {
        "do_setup": false,
        "do_run": false,
        "do_extract": true,
        "batch_run": false
    }
    ```

    Run the study one last time: `python run_study.py --config configs/your_config.json`. This will process all the downloaded results and generate the final SAR (Specific Absorption Rate) reports and any other required analyses.

## 5. Configuration

The framework is controlled by a hierarchical JSON configuration system. A study-specific config (e.g., [`near_field_config.json`](configs/near_field_config.json:1)) inherits settings from a [`base_config.json`](configs/base_config.json:1) and can override them. This allows for a high degree of flexibility and avoids repetition.

The most important parameters are:
- **`extends`**: Defines the parent configuration file.
- **`study_type`**: Determines the simulation type (`"near_field"` or `"far_field"`).
- **`execution_control`**: A set of booleans (`do_setup`, `do_run`, `do_extract`) that control which parts of the workflow are executed. This is useful for re-running only a specific part of a study.
- **`phantoms`** and **`frequencies_mhz`**: The lists that define the core matrix of the study.

For a complete and detailed list of all available configuration parameters, please see the **[Configuration Documentation](configs/documentation.md)**.