# Near-Field Simulation Project

This project provides a structured framework for running near-field SAR (Specific Absorption Rate) simulations using Sim4Life.

## 1. Project Structure

- **`data/`**: Contains all input data, such as antenna models and phantom files.
- **`docs/`**: Project documentation.
- **`results/`**: Default directory for all simulation outputs.
- **`src/`**: The core Python source code for the simulation framework.
- **`prepare_antennas.py`**: A one-time script to process and center raw antenna models.
- **`run_study.py`**: The main entry point to run a simulation campaign or a single test.
- **`simulation_config.json`**: Defines global simulation parameters, frequencies, and antenna properties.
- **`phantoms_config.json`**: Defines phantom-specific parameters for bounding boxes and placements.

## 2. Setup and Execution

### Prerequisites

- Sim4Life V8.2 or later must be installed.
- The required Python packages can be installed via pip:
  ```bash
  pip install -r requirements.txt
  ```

### Step 1: Prepare Antenna Models

Before running a simulation, the raw antenna models must be centered. Run the `prepare_antennas.py` script using the Sim4Life Python interpreter.

**Command:**
```bash
"C:\Program Files\Sim4Life_8.2.0.16876\Python\python.exe" prepare_antennas.py
```
This will process the `.smash` files from `data/antennas/downloaded_from_drive/` and save the centered `.sab` files into `data/antennas/centered/`.

### Step 2: Run a Simulation Study

To run the simulation campaign, execute the `run_study.py` script, again using the Sim4Life Python interpreter.

**Command:**
```bash
"C:\Program Files\Sim4Life_8.2.0.16876\Python\python.exe" run_study.py
```

The script is currently configured to run a single test case. You can modify it to run the full campaign by commenting out the single-test logic and re-enabling the `NearFieldStudy` campaign loop.