# Dosimetric Assessment Framework

This project provides a robust and automated Python framework for conducting both **near-field** and **far-field** dosimetric assessments for the GOLIAT project, using the Sim4Life simulation platform.

The framework is designed to be modular, scalable, and reproducible, handling a large matrix of simulation parameters to replicate and extend the studies detailed in the GOLIAT project documents.

## 1. Project Goal

The primary objective is to perform a comprehensive dosimetric assessment for the **Thelonius** and **Eartha** child voxel phantoms across a wide range of frequencies and exposure scenarios. This includes:
- **Near-Field:** SAR simulations with device antennas placed close to the phantom.
- **Far-Field:** Whole-body exposure simulations from incident plane waves, covering both environmental and auto-induced scenarios.

### Key Deliverables

As specified in [`context/what we need.md`](context/what%20we%20need.md:1), the required outputs include whole-body SAR, head SAR, trunk SAR, and psSAR10g in various tissues, calculated for normalized applied power.

## 2. Architecture

The framework is built on a modular, class-based architecture designed for flexibility and maintainability. A `BaseStudy` class defines a common interface, which is then extended by specialized study classes that orchestrate the simulation process.

-   **`studies/`**: Contains the high-level logic for managing simulation campaigns.
    -   `base_study.py`: Abstract base class defining the common study interface.
    -   `near_field_study.py`: Manages near-field SAR simulation campaigns.
    -   `far_field_study.py`: Manages far-field exposure simulation campaigns.
-   **`setups/`**: Contains the logic for building the simulation scene in Sim4Life.
    -   `base_setup.py`: Abstract base class for scene setup.
    -   `near_field_setup.py`: Configures the scene for near-field simulations (e.g., antenna placement).
    -   `far_field_setup.py`: Configures the scene for far-field simulations (e.g., plane wave sources).
-   **`Config`**: Manages all configurations from the JSON files in the `configs/` directory.
-   **`ProjectManager`**: Handles the lifecycle of the Sim4Life (`.smash`) project file.
-   **`SimulationRunner`**: Manages the execution of the simulation, with support for the Sim4Life API or the standalone `iSolve.exe` solver.
-   **`ResultsExtractor`**: Handles post-processing, extracting raw data, calculating statistics, and saving reports. It is designed to handle the different outputs from near-field and far-field simulations.

This separation of concerns allows for easy extension and maintenance of the codebase.

## 3. Project Structure

The project is organized into a modular and scalable structure:

```
.
├── configs/
│   ├── near_field_config.json      # Configuration for near-field studies
│   └── far_field_config.json       # Configuration for far-field studies
├── data/
│   ├── antennas/
│   └── phantoms/
├── results/
│   ├── near_field/                 # Directory for near-field results
│   └── far_field/                  # Directory for far-field results
├── scripts/
│   ├── download_data.py
│   └── prepare_antennas.py
├── src/
│   ├── analysis/
│   ├── setups/
│   │   ├── base_setup.py
│   │   ├── near_field_setup.py
│   │   └── far_field_setup.py
│   ├── studies/
│   │   ├── base_study.py
│   │   ├── near_field_study.py
│   │   └── far_field_study.py
│   ├── antenna.py
│   ├── config.py
│   ├── project_manager.py
│   ├── results_extractor.py
│   ├── simulation_runner.py
│   ├── startup.py
│   └── utils.py
├── docs/
│   └── Far_Field_Expansion_Plan.md # Strategic plan for the framework architecture
├── run_study.py                    # Main entry point to run a simulation campaign
├── material_name_mapping.json
├── README.md
└── requirements.txt
```

*Note: The `data` and `results` directories are not included in the repository and should be created locally.*

## 4. Automated Workflow

The framework is designed for a fully automated, "one-click" execution.

### Prerequisites

Ensure you have **Sim4Life v8.2 or later** installed and licensed.

### Running a Study

To run a simulation campaign, execute the main script with the desired study type.

*Note: These commands require the Sim4Life Python interpreter. If the `python` command on your system does not point to it, you must use the full path to the interpreter.*

**Run a near-field study:**
```bash
python run_study.py near_field
```

**Run a far-field study:**
```bash
python run_study.py far_field
```

If needed, use the full path to the interpreter:
```bash
"C:\Program Files\Sim4Life_8.2.0.16876\Python\python.exe" run_study.py far_field
```

The script will automatically perform all necessary setup steps:
1.  **Install Dependencies**: Checks and installs missing Python packages from `requirements.txt`.
2.  **Download Data**: Downloads and extracts required data (phantoms, antennas) into the `data/` directory.
3.  **Prepare Antennas**: Processes raw antenna models for simulation.
4.  **Run Simulations**: Proceeds with the full simulation campaign as defined in the specified configuration file.

## 5. Configuration

The simulation is controlled by JSON files located in the `configs/` directory.

-   **`configs/near_field_config.json`**: Defines parameters for near-field studies (e.g., antenna models, placements).
-   **`configs/far_field_config.json`**: Defines parameters for far-field studies (e.g., plane wave definitions).
-   **`material_name_mapping.json`**: Maps entity names from CAD models to Sim4Life material names.

### Key Configuration Parameters

-   `"manual_isolve"`: (boolean) Set to `true` to run the simulation using the standalone `iSolve.exe` solver instead of the integrated Sim4Life solver. This is useful for running on machines without a full Sim4Life UI license.
-   `"excitation_type"`: (string) The type of signal used to excite the antenna (e.g., `"Gaussian"`, `"Harmonic"`).
-   See the respective `_config.json` files for domain-specific parameters.

## 6. Roadmap & Future Features

The strategic development plan, which led to the current architecture, is detailed in [`docs/Far_Field_Expansion_Plan.md`](docs/Far_Field_Expansion_Plan.md). Future work includes:
-   Implementation of the auto-induced far-field scenario with MRT beamforming.
-   Comprehensive data aggregation and visualization tools for both study types.
-   Final power normalization calculations for all scenarios.
-   Version control and CI/CD pipeline setup.

## 7. Context and Reference Materials

The `context/` directory contains key reference documents for the project, including the original study definitions and a summary of the required deliverables. See [`context/README.md`](context/README.md) for more details.
## 8. Known Issues

### SIBC Performance with CUDA

**NOTE/TODO:** There is a known performance issue with the SIBC (Surface Impedance Boundary Condition) implementation when using the CUDA backend for GPU acceleration. This can lead to significantly longer simulation times or convergence problems.

A potential solution is to switch the solver to use the **Acceleware** backend instead of CUDA, as it has been observed to handle SIBC more efficiently. This can typically be configured within the Sim4Life solver settings.