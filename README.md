# Near-Field Dosimetric Assessment for Child Phantoms

This project provides a robust and automated framework for conducting near-field Specific Absorption Rate (SAR) simulations for the GOLIAT project, focusing on the Thelonius and Eartha child voxel phantoms.

The framework is designed to be automated, flexible, and reproducible, handling a large matrix of simulation parameters to replicate and extend the near-field dosimetric assessments detailed in the `GOLIAT_PartB_20210920_3rdSubmission_final.pdf` and `Near-field_GOLIAT.pdf` documents.

## 1. Project Goal

The primary objective is to perform a comprehensive near-field SAR assessment for the **Thelonius** and **Eartha** child voxel phantoms.

### Key Deliverables

As specified in `context/what we need.md`, the required outputs for each simulation are:
- Whole-body SAR
- Head SAR
- Trunk SAR
- psSAR10g in skin, eyes, and brain (in mW/kg)

These results are to be calculated for a normalized applied power that induces a peak spatial-average SAR (psSAR10g) of 1 W/kg.

## 2. Simulation Scope

The simulation campaign covers the following parameters:

*   **Phantoms:** Thelonius, Eartha
*   **Frequencies:** 700, 835, 1450, 2140, 2450, 3500, 5200, 5800 (all in MHz)
*   **Antenna Models:**
    *   **PIFA:** 700 MHz, 835 MHz
    *   **IFA:** All other frequencies
*   **Antenna Placements:** 22 distinct positions and orientations per phantom, covering the eyes, belly, and ear regions.

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
│   ├── __init__.py
│   ├── config.py                 # Handles loading and validation of config files
│   ├── antenna.py                # Helper class for antenna properties
│   ├── project.py                # Defines the NearFieldProject class
│   ├── study.py                  # Defines the NearFieldStudy class for campaign management
│   └── utils.py                  # Utility functions (e.g., s4l interaction)
├── docs/
│   ├── ROADMAP.md                # Development roadmap
│   └── README.md                 # This file (deprecated, points to root README)
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

## 4. Setup and Execution

### Step 1: Prerequisites

Ensure you have Sim4Life v8.2 or later installed and licensed. The project requires Python and the dependencies listed in `requirements.txt`.

### Step 2: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 3: Prepare Antenna Models

The original antenna models (`.smash` files) must be centered and converted to `.sab` format for use in the simulations.

1.  Download the antenna models from the [GOLIAT Google Drive](https://drive.google.com/drive/folders/1xymuIkKBqX-oDJ3VA3UCEaPuOGe2aDj5?usp=sharing).
2.  Create the directory `data/antennas/downloaded_from_drive/`.
3.  Place the downloaded `.smash` files into it.
4.  Run the preparation script using the Sim4Life Python interpreter:

```bash
"C:\Program Files\Sim4Life_8.2.0.16876\Python\python.exe" prepare_antennas.py
```
This will process the antennas and save the centered `.sab` files to `data/antennas/centered/`.

### Step 4: Run a Simulation

To run a single test simulation, execute the main study script:

```bash
"C:\Program Files\Sim4Life_8.2.0.16876\Python\python.exe" run_study.py
```
The script is pre-configured to run a single test case for the Thelonius phantom at 700 MHz with the antenna placed in front of the eyes. The full simulation campaign can be enabled by modifying `run_study.py` to use the `NearFieldStudy` class.

### Manual Solver Execution (iSolve)

For more control over the simulation, you can run the solver manually. This is useful for debugging or running on a machine without a full Sim4Life UI license.

1.  Open `simulation_config.json`.
2.  Set the `"manual_isolve"` flag to `true`.
3.  Run the `run_study.py` script as usual.

This will configure the project and generate the necessary solver input files without starting the simulation. It will then execute `iSolve.exe` in a separate process. The output of the solver will be piped to the console. When using this mode, result extraction is skipped.

## 5. How it Works: Framework Architecture

The project is built on a modular, class-based Python framework that interfaces with the Sim4Life API.

*   **`src/config.py`**: Manages all simulation and phantom configurations through JSON files, ensuring a clean separation of parameters from code.
*   **`src/antenna.py`**: A helper class that abstracts antenna-specific details, such as model selection and source configuration based on frequency.
*   **`src/project.py`**: The core `NearFieldProject` class, which encapsulates the entire workflow for a single simulation—from setup and antenna placement to execution and result extraction.
*   **`src/study.py`**: The `NearFieldStudy` class, designed to orchestrate the full simulation campaign by iterating through all defined parameters.
*   **`run_study.py`**: The main entry point for launching simulations.

This structure is designed to be scalable, maintainable, and easily adaptable for future research needs.

## 6. Roadmap & Future Features

The development roadmap is outlined in [`docs/ROADMAP.md`](docs/ROADMAP.md). Key upcoming features include:

-   Full campaign automation to run all parameter combinations.
-   Integration and support for the Eartha phantom.
-   Advanced result extraction for all required SAR metrics.
-   GitHub integration and setup of a CI/CD pipeline.

## 7. Context and Reference Materials

The `context/` directory contains key reference documents for the project, including the original near-field study (`Near-field_GOLIAT.pdf`) and a summary of the required deliverables (`what we need.md`). See [`context/README.md`](context/README.md) for more details.