# Near-Field Dosimetric Assessment Framework for Child Phantoms

This project provides a robust and automated Python framework for conducting near-field Specific Absorption Rate (SAR) simulations for the GOLIAT project, focusing on the Thelonius and Eartha child voxel phantoms using the Sim4Life simulation platform.

The framework is designed to be modular, scalable, and reproducible, handling a large matrix of simulation parameters to replicate and extend the near-field dosimetric assessments detailed in the `GOLIAT_PartB_20210920_3rdSubmission_final.pdf` and `Near-field_GOLIAT.pdf` documents.

## 1. Project Goal

The primary objective is to perform a comprehensive near-field SAR assessment for the **Thelonius** and **Eartha** child voxel phantoms across a wide range of frequencies and antenna placements.

### Key Deliverables

As specified in [`context/what we need.md`](context/what%20we%20need.md:1), the required outputs for each simulation are:
- Whole-body SAR
- Head SAR
- Trunk SAR
- psSAR10g in skin, eyes, and brain (in mW/kg)

These results are to be calculated for a normalized applied power that induces a peak spatial-average SAR (psSAR10g) of 1 W/kg.

## 2. Architecture

The framework is built on a modular, class-based architecture designed for clarity and maintainability. A high-level `NearFieldStudy` class orchestrates the simulation process, delegating specific tasks to specialized components:

-   **`Config`**: Manages all simulation and phantom configurations from the JSON files, separating parameters from the code.
-   **`ProjectManager`**: Handles the lifecycle of the Sim4Life (`.smash`) project file, including creation, opening, and saving.
-   **`SimulationSetup`**: Contains all the logic for building the simulation scene within Sim4Life, such as loading the phantom, placing the antenna, assigning materials, and defining the grid.
-   **`SimulationRunner`**: Manages the execution of the simulation, with support for running via the Sim4Life API or the standalone `iSolve.exe` solver.
-   **`ResultsExtractor`**: Handles all post-processing tasks, including extracting raw data, calculating SAR statistics, and saving the final reports.

This separation of concerns makes the codebase easier to debug, maintain, and extend with new functionality.

## 3. Project Structure

The project is organized into a modular and scalable structure:

```
.
├── data/
│   ├── antennas/
│   │   ├── downloaded_from_drive/  # Original .smash files
│   │   └── centered/               # Processed, centered .sab files
│   └── phantoms/
│       └── Thelonius.sab           # Phantom models
├── results/                        # Simulation outputs, logs, etc.
├── scripts/
│   ├── download_data.py          # Handles downloading data from Google Drive
│   ├── inspect_antennas.py       # Utility to inspect antenna model components
│   └── prepare_antennas.py       # Centers and prepares raw antenna models
├── src/
│   ├── setups/                   # Specialized setup modules (materials, grid, etc.)
│   ├── __init__.py
│   ├── antenna.py                # Helper class for antenna properties
│   ├── config.py                 # Handles loading and validation of config files
│   ├── project_manager.py        # Manages the .smash project file
│   ├── results_extractor.py      # Extracts and processes simulation results
│   ├── simulation_runner.py      # Runs the simulation (API or iSolve)
│   ├── simulation_setup.py       # Configures the S4L scene
│   ├── startup.py                # Handles all automated prerequisite checks
│   ├── study.py                  # Defines the NearFieldStudy class for campaign management
│   └── utils.py                  # Utility functions (e.g., s4l interaction)
├── docs/
│   └── IMPROVED_ROADMAP.md       # Current development roadmap
├── context/
│   ├── what we need.md           # Summary of deliverables
│   └── README.md                 # Explains reference materials
├── run_study.py                    # Main entry point to run a simulation campaign
├── simulation_config.json          # Main simulation configuration
├── phantoms_config.json            # Phantom-specific configuration
├── material_name_mapping.json      # Maps model entity names to material names
├── README.md                       # This file
└── requirements.txt                # Python dependencies
```

*Note: The `data` and `results` directories are not included in the repository and should be created locally.*

## 4. Automated Workflow

The framework is designed for a fully automated, "one-click" execution.

### Prerequisites

Ensure you have **Sim4Life v8.2 or later** installed and licensed.

### Running the Study

To run the entire simulation campaign, simply execute the main script using the Sim4Life Python interpreter:

```bash
"C:\Program Files\Sim4Life_8.2.0.16876\Python\python.exe" run_study.py
```

The script will automatically perform all necessary setup steps:
1.  **Install Dependencies**: Checks for and installs any missing Python packages from `requirements.txt`.
2.  **Download Data**: Downloads and extracts the required simulation data (phantoms and raw antenna models) from Google Drive into the `data/` directory. This step is skipped if the data is already present.
3.  **Prepare Antennas**: Centers the raw antenna models and saves them as processed `.sab` files in `data/antennas/centered/`. This step is also skipped if the centered files already exist.
4.  **Run Simulations**: Proceeds with the full simulation campaign as defined in the configuration files.

## 5. Configuration

The simulation is controlled by three main JSON files. For most use cases, you will only need to modify `simulation_config.json`.

-   **`simulation_config.json`**: Defines global simulation parameters.
-   **`phantoms_config.json`**: Contains phantom-specific data, including placements, bounding box definitions, and tissue lists.
-   **`material_name_mapping.json`**: Maps entity names from the CAD models to the material names used in Sim4Life's database.

### Key Configuration Parameters

The following parameters in `simulation_config.json` are the most important for customizing the simulation:

-   `"global_auto_termination"`: Defines how the simulation decides when to end.
    -   `"GlobalAutoTerminationUserDefined"`: The simulation stops when the energy in the field decays by a specific amount. This is the most common setting.
    -   `"GlobalAutoTerminationWeak"` / `"GlobalAutoTerminationStrong"`: Pre-defined termination criteria.
-   `"convergence_level_dB"`: If using `"UserDefined"` termination, this sets the energy decay threshold in decibels (dB). A value of `-15` means the simulation runs until the energy has dropped by 15 dB.
-   `"excitation_type"`: The type of signal used to excite the antenna.
    -   `"Gaussian"`: A pulse that covers a range of frequencies. Good for broadband analysis.
    -   `"Harmonic"`: A continuous sine wave at a single frequency.
-   `"simulation_time_multiplier"`: A factor that controls the total simulation time. The duration is calculated based on the time it takes for a wave to travel across the diagonal of the simulation bounding box, multiplied by this value. A larger value allows more time for reflections to settle, increasing accuracy but also runtime.
-   `"manual_isolve"`: Set to `true` to run the simulation using the standalone `iSolve.exe` solver instead of the integrated Sim4Life solver. This is useful for running on machines without a full Sim4Life UI license.

## 6. Roadmap & Future Features

The strategic development roadmap is outlined in [`docs/IMPROVED_ROADMAP.md`](docs/IMPROVED_ROADMAP.md). Key upcoming features include:
-   Full support for the **Eartha** phantom.
-   Comprehensive results extraction for all required SAR metrics.
-   Final power normalization calculations.
-   Data aggregation and visualization tools.
-   Version control and CI/CD pipeline setup.

## 7. Context and Reference Materials

The `context/` directory contains key reference documents for the project, including the original near-field study (`Near-field_GOLIAT.pdf`) and a summary of the required deliverables (`what we need.md`). See [`context/README.md`](context/README.md) for more details.