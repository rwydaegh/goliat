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
├── src/
│   ├── setups/                   # Specialized setup modules (materials, grid, etc.)
│   ├── __init__.py
│   ├── antenna.py                # Helper class for antenna properties
│   ├── config.py                 # Handles loading and validation of config files
│   ├── project_manager.py        # Manages the .smash project file
│   ├── results_extractor.py      # Extracts and processes simulation results
│   ├── simulation_runner.py      # Runs the simulation (API or iSolve)
│   ├── simulation_setup.py       # Configures the S4L scene
│   ├── study.py                  # Defines the NearFieldStudy class for campaign management
│   └── utils.py                  # Utility functions (e.g., s4l interaction)
├── docs/
│   └── IMPROVED_ROADMAP.md       # Current development roadmap
├── context/
│   ├── what we need.md           # Summary of deliverables
│   └── README.md                 # Explains reference materials
├── run_study.py                    # Main entry point to run a simulation campaign
├── prepare_antennas.py             # One-time script to center antenna models
├── simulation_config.json          # Main simulation configuration
├── phantoms_config.json            # Phantom-specific configuration
├── material_name_mapping.json      # Maps model entity names to material names
├── README.md                       # This file
└── requirements.txt                # Python dependencies
```

*Note: The `data` and `results` directories are not included in the repository and should be created locally.*

## 4. Setup and Usage

### Step 1: Prerequisites

Ensure you have Sim4Life v8.2 or later installed and licensed. The project requires Python and the dependencies listed in `requirements.txt`.

### Step 2: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 3: Prepare Antenna Models

The original antenna models (`.smash` files) must be centered and converted to `.sab` format.

1.  Download the antenna models from the [GOLIAT Google Drive](https://drive.google.com/drive/folders/1xymuIkKBqX-oDJ3VA3UCEaPuOGe2aDj5?usp=sharing).
2.  Create the directory `data/antennas/downloaded_from_drive/`.
3.  Place the downloaded `.smash` files into it.
4.  Run the preparation script using the Sim4Life Python interpreter:

```bash
"C:\Program Files\Sim4Life_8.2.0.16876\Python\python.exe" prepare_antennas.py
```
This will process the antennas and save the centered `.sab` files to `data/antennas/centered/`.

### Step 4: Run Simulations

The `run_study.py` script is the main entry point. You can easily configure it to run a single simulation or a full campaign.

#### Example 1: Running a Single Test Case

To run a single, specific simulation, modify `run_study.py` as follows:

```python
# run_study.py

from src.config import Config
from src.study import NearFieldStudy

if __name__ == '__main__':
    # Load configuration from JSON files in the 'data' directory
    config = Config(base_dir='.')

    # Instantiate the main study controller
    study = NearFieldStudy(config)

    # Define and run a single simulation
    study.run_single(
        project_name="Thelonius_700MHz_FrontOfEyes_Test",
        phantom_name="thelonius",
        frequency_mhz=700,
        placement_name="front_of_eyes_pos1_h"
    )
```

Then execute the script:
```bash
"C:\Program Files\Sim4Life_8.2.0.16876\Python\python.exe" run_study.py
```

#### Example 2: Running a Full Campaign

To run the entire campaign iterating through all phantoms, frequencies, and placements defined in your configuration files, simply call the `run_campaign` method:

```python
# run_study.py

from src.config import Config
from src.study import NearFieldStudy

if __name__ == '__main__':
    config = Config(base_dir='.')
    study = NearFieldStudy(config)

    # Run the full campaign
    study.run_campaign()
```

### Manual Solver Execution (iSolve)

For more control, you can run the solver manually (e.g., on a machine without a full Sim4Life UI license).

1.  Open `simulation_config.json`.
2.  Set the `"manual_isolve"` flag to `true`.
3.  Run the `run_study.py` script as usual.

The framework will set up the project, generate solver input files, and then execute `iSolve.exe` in a separate process. The solver output will be piped to the console.

## 5. Configuration

The simulation is controlled by three main JSON files:
-   **`simulation_config.json`**: Defines global parameters like frequencies, solver settings, and termination criteria.
-   **`phantoms_config.json`**: Contains phantom-specific data, including placements, bounding box definitions, and tissue lists.
-   **`material_name_mapping.json`**: Maps entity names from the CAD models to the material names used in Sim4Life's database.

## 6. Roadmap & Future Features

The strategic development roadmap is outlined in [`docs/IMPROVED_ROADMAP.md`](docs/IMPROVED_ROADMAP.md). Key upcoming features include:
-   Full support for the **Eartha** phantom.
-   Comprehensive results extraction for all required SAR metrics.
-   Final power normalization calculations.
-   Data aggregation and visualization tools.
-   Version control and CI/CD pipeline setup.

## 7. Context and Reference Materials

The `context/` directory contains key reference documents for the project, including the original near-field study (`Near-field_GOLIAT.pdf`) and a summary of the required deliverables (`what we need.md`). See [`context/README.md`](context/README.md) for more details.