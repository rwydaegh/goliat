# Near-Field Dosimetric Assessment for Child Phantoms

This project provides a robust and automated framework for conducting near-field Specific Absorption Rate (SAR) simulations for the GOLIAT project, focusing on the Thelonius and Eartha child voxel phantoms.

## 1. Project Goal

The primary objective is to replicate and extend the near-field dosimetric assessments detailed in the `GOLIAT_PartB_20210920_3rdSubmission_final.pdf` and `Near-field_GOLIAT.pdf` documents. The framework is designed to be automated, flexible, and reproducible, handling a large matrix of simulation parameters.

### Key Deliverables

As specified in `context/what we need.md`, the required outputs for each simulation are:
- Whole-body SAR
- Head SAR
- Trunk SAR
- psSAR10g in skin, eyes, and brain (in mW/kg)

These results are to be calculated for a normalized applied power that induces a peak spatial-average SAR (psSAR10g) of 1 W/kg.

## 2. Simulation Parameters

The simulation campaign covers the following parameters:

*   **Phantoms:** Thelonius, Eartha
*   **Frequencies:** 700, 835, 1450, 2140, 2450, 3500, 5200, 5800 (all in MHz)
*   **Antenna Models:**
    *   **PIFA:** 700 MHz, 835 MHz
    *   **IFA:** All other frequencies
*   **Antenna Placements:** 22 positions per phantom, including variations in front of the eyes, on the belly, and near the cheek/ear.

## 3. Project Structure

The project is organized into a modular and scalable structure:

```
near_field/
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
├── run_study.py                    # Main entry point to run a simulation campaign
├── prepare_antennas.py             # One-time script to center antenna models
├── simulation_config.json          # Main simulation configuration
├── phantoms_config.json            # Phantom-specific configuration
├── material_name_mapping.json      # Maps model entity names to material names
├── README.md                       # This file
└── requirements.txt                # Python dependencies
```

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
2.  Place the downloaded `.smash` files into the `near_field/data/antennas/downloaded_from_drive/` directory.
3.  Run the preparation script using the Sim4Life Python interpreter:

```bash
"C:\Program Files\Sim4Life_8.2.0.16876\Python\python.exe" prepare_antennas.py
```
This will process the antennas and save the centered `.sab` files to `near_field/data/antennas/centered/`.

### Step 4: Run a Simulation

To run a single test simulation, execute the main study script:

```bash
"C:\Program Files\Sim4Life_8.2.0.16876\Python\python.exe" run_study.py
```
The script is pre-configured to run a single test case for the Thelonius phantom at 700 MHz with the antenna placed in front of the eyes. The full simulation campaign can be enabled by modifying `run_study.py` to use the `NearFieldStudy` class.

## 5. Roadmap & Future Features

This project is under active development. The following features are planned:

-   [x] **Core Framework:** Establish a class-based, configuration-driven structure.
-   [x] **Single Simulation:** Implement and debug the workflow for a single test case.
-   [x] **Log Suppression:** Add targeted log suppression for cleaner output.
-   [ ] **Full Campaign Automation:** Implement the `NearFieldStudy` class to run all parameter combinations automatically.
-   [ ] **Advanced Result Extraction:** Extend result extraction to include all required SAR metrics for all specified organs.
-   [ ] **Eartha Phantom Support:** Integrate the Eartha phantom and its specific configurations.
-   [ ] **GitHub Integration:**
    -   [ ] Initialize a private Git repository.
    -   [ ] Push the `src` directory and other key files to a remote on `github.ugent.be`.
-   [ ] **CI/CD Pipeline:** Set up a continuous integration pipeline to automate testing and validation.