# 📖 User Guide: Understanding GOLIAT Workflows

This guide provides a comprehensive, plain-language explanation of how GOLIAT operates, serving as your essential roadmap for running and analyzing EMF dosimetry simulations. We'll delve into the end-to-end workflows for both near-field (device close to the body, like a mobile phone) and far-field (whole-body exposure, such as environmental plane waves) scenarios.

GOLIAT automates the intricate and often tedious aspects of EMF simulations: from downloading necessary models and constructing complex scenes in Sim4Life, to executing calculations and extracting critical metrics like Specific Absorption Rate (SAR).

## 💡 Key Concepts in EMF Dosimetry

Before diving into the workflows, let's clarify some fundamental terms:

-   **Phantoms**: These are highly detailed digital human models (e.g., "thelonious" represents a 6-year-old boy, "eartha" an adult female). They serve as realistic 3D representations for safe and accurate simulation of EMF interaction with biological tissues.
-   **Near-Field Simulations**: Focus on scenarios where an EMF source (e.g., an antenna in a mobile device) is in close proximity to the body. These simulations are crucial for assessing localized absorption, particularly in sensitive areas like the head, eyes, or limbs.
-   **Far-Field Simulations**: Address scenarios involving plane waves impinging on the entire body from various directions (e.g., front, back, sides). These are typically used for evaluating environmental or broadcast exposure.
-   **Specific Absorption Rate (SAR)**: The primary output metric, representing the rate at which electromagnetic energy is absorbed per unit mass of biological tissue, typically expressed in milliwatts per kilogram (mW/kg) per 1W of input power. GOLIAT provides whole-body average SAR, localized SAR (e.g., head/trunk), and peak spatial-average SAR (psSAR) over 10g tissue cubes in specific organs (e.g., brain, eyes, skin).
-   **Configuration Files (Configs)**: JSON files that serve as the "recipe" for your simulations. They define all parameters, including phantom selection, frequencies, antenna properties, and execution controls. GOLIAT uses a hierarchical system where study-specific configs inherit from `base_config.json`, allowing for easy customization and overrides.

## 🚀 End-to-End Workflow: From Config to Analysis

GOLIAT's robust and modular design follows a clear, sequential flow: **Load Config → Orchestrate Study → Setup Scene → Run Simulation → Extract Results → Analyze & Plot**.

### 1. Load Configuration

Your journey begins by specifying a configuration file.
-   Execute your study using the command line:
    ```bash
    python run_study.py --config configs/your_study_config.json
    ```
-   GOLIAT intelligently merges your chosen configuration (e.g., `near_field_config.json`) with the `base_config.json`, applying overrides for specific parameters like solver settings or gridding refinements.
-   A graphical user interface (GUI) will launch. Here, you can load your configuration (if not provided via CLI) and initiate the study by clicking "Run Study".

**💡 Pro Tip**: Configuration files are human-readable JSON. We recommend editing them in a code editor like VS Code. Start by copying one of the provided templates (e.g., `near_field_config.json`) and modify only the parameters relevant to your study, such as phantoms or frequencies. Refer to the [Configuration Guide](configuration.md) for a detailed breakdown of all parameters.

### 2. Orchestrate Study

The core logic of your simulation is managed by specialized **Study** classes (`NearFieldStudy` or `FarFieldStudy`).

-   **Near-Field Example**: If you're running a near-field study, the `NearFieldStudy` class will systematically loop through all defined phantoms, frequencies, and antenna placements. For instance, it might process "thelonious" phantom at 700 MHz with an antenna placed "by_cheek" (e.g., 8mm from the cheek).
-   **Far-Field Example**: For far-field studies, the `FarFieldStudy` class iterates through phantoms, frequencies, incident directions (e.g., x_pos, y_neg), and polarizations (e.g., theta, phi) to ensure comprehensive coverage.
-   **Project Management**: For each unique simulation scenario, GOLIAT creates a dedicated Sim4Life project file (`.smash`) within a structured `results/` directory (e.g., `results/near_field/thelonious/700MHz/by_cheek/`).
-   **Progress Tracking**: The GUI provides real-time progress updates and an Estimated Time of Arrival (ETA), which becomes more accurate over time as GOLIAT learns from previous runs.

### 3. Setup Scene in Sim4Life

This phase involves GOLIAT automatically constructing the 3D simulation environment within Sim4Life.

-   **Phantom Loading**: The specified digital phantom model is downloaded (if not already present) and imported into the scene, complete with its detailed tissue segmentation (e.g., skin, brain, muscle).
-   **Antenna/Source Placement**:
    -   **Near-Field**: The CAD model of the antenna (e.g., PIFA or IFA type) is imported and precisely positioned relative to the phantom, according to the defined placement scenario (e.g., 8mm gap from the cheek, with a specific tilt).
    -   **Far-Field**: Instead of an antenna, a plane wave source is configured, specifying its electric field strength (e.g., 1 V/m), incident direction, and polarization.
-   **Material Assignment**: Appropriate electromagnetic properties (e.g., conductivity, permittivity) are assigned to all entities in the scene (tissues, antenna components) based on the specified frequency.
-   **Gridding**: The simulation domain is discretized into a computational grid. GOLIAT intelligently applies gridding rules, using finer cells around critical areas like the antenna or phantom surface, and coarser cells elsewhere. This can be automatic or manually controlled via millimeter steps.
-   **Boundaries and Sensors**: Perfectly Matched Layer (PML) boundaries are configured to absorb outgoing electromagnetic waves, preventing reflections. Point sensors are strategically placed (e.g., at the corners of the simulation bounding box) to monitor field values.
-   **Solver Configuration**: The Finite-Difference Time-Domain (FDTD) solver is set up, typically leveraging GPU acceleration (e.g., Acceleware kernel) for faster computation.

**Visualizing the Scene**: Imagine a detailed 3D model of a human phantom, with an antenna precisely positioned nearby, all enclosed within a computational grid. GOLIAT handles the complex process of voxelization, where the continuous 3D geometry is converted into discrete cells filled with specific tissue properties.

### 4. Run Simulation

With the scene meticulously set up, GOLIAT proceeds to execute the electromagnetic simulation.

-   **Local Execution**: For local runs, GOLIAT directly invokes the Sim4Life iSolve.exe solver. The GUI remains responsive, displaying logs and progress updates as the solver runs.
-   **Cloud Execution (oSPARC)**: For large-scale or parallel studies, GOLIAT can generate the necessary input files (`.h5`) and submit them as jobs to the oSPARC cloud platform. It then monitors the status of these jobs (e.g., PENDING → RUNNING → SUCCESS).
-   **Duration**: A single simulation can take anywhere from 5 to 30 minutes, depending on factors like grid resolution, frequency, and computational resources. All results are normalized to a 1W input power for consistency.

**Batch Mode**: By setting `"batch_run": true` in your configuration, GOLIAT can manage multiple simulations concurrently, either locally (using `run_parallel_studies.py`) or on oSPARC. The GUI tracks the status of all jobs and automatically downloads results upon completion.

### 5. Extract & Analyze Results

After the simulation, GOLIAT's `ResultsExtractor` and `Analyzer` components take over to process and interpret the vast amount of raw data.

-   **SAR Extraction**: The extractor pulls various SAR metrics from the simulation output:
    -   **Whole-Body SAR**: The average SAR over the entire phantom.
    -   **Localized SAR**: Average SAR in specific regions, such as the head or trunk, relevant for localized exposures.
    -   **psSAR10g**: Peak spatial-average SAR over a 10-gram tissue cube, typically reported for sensitive organs like the eyes, brain, and skin.
    -   **Power Balance**: A crucial check to ensure energy conservation within the simulation, ideally close to 100%.
-   **Normalization**: All extracted SAR values are normalized to a 1W input power, providing a standardized basis for comparison.
-   **Output Files** (located in the `results/` folder):
    -   `sar_results.json`: A JSON file containing the primary normalized SAR values.
    -   `sar_stats_all_tissues.pkl`: A Python pickle file with detailed, tissue-specific SAR data.
    -   **Plots**: GOLIAT automatically generates a suite of visualizations, including SAR heatmaps (showing SAR distribution by tissue and frequency), bar charts (comparing SAR in different regions), and boxplots (illustrating SAR distributions).
-   **Aggregated Analysis**: You can run the dedicated analysis script (`python run_analysis.py --config your_config.json`) to aggregate results across multiple simulations and generate comprehensive CSV reports and additional plots.

**Example Output Interpretation**: For a near-field 700MHz simulation with an antenna by the cheek, you might observe:
-   Head SAR: 0.5 mW/kg (per 1W input).
-   Brain psSAR10g: 2.1 mW/kg peak.
For far-field studies, the analysis often involves aggregating results over different incident directions to determine worst-case exposure scenarios.

## 🔄 Near-Field vs. Far-Field Workflows: A Comparison

While the core GOLIAT workflow remains consistent, the specifics of scene setup and analysis differ between near-field and far-field studies.

### Near-Field Workflow (Device Exposure)

-   **Primary Use Case**: Assessing localized EMF exposure from devices held close to the body, such as mobile phones, wearables, or medical implants. The focus is on SAR in specific tissues and organs.
-   **Key Steps**:
    1.  **Configuration**: Set `"study_type": "near_field"` and define specific `placement_scenarios` (e.g., "by_cheek", "on_wrist").
    2.  **Scene Setup**: Involves importing a detailed CAD model of the device antenna and precisely positioning it relative to the phantom, often with a small air gap (e.g., 8mm).
    3.  **Simulation Run**: Typically uses a harmonic excitation (single frequency) to simulate continuous wave exposure.
    4.  **Results Analysis**: Concentrates on localized SAR values (e.g., head SAR, trunk SAR) and peak spatial-average SAR (psSAR10g) in sensitive tissues like the eyes, brain, and skin.
-   **Free-Space Mode**: GOLIAT supports a "freespace" phantom option, allowing you to run simulations of the antenna in isolation (without a body). This is useful for antenna characterization and validation.

### Far-Field Workflow (Environmental Exposure)

-   **Primary Use Case**: Evaluating whole-body EMF exposure from distant sources, such as broadcast antennas, cellular base stations, or industrial equipment. The focus is on whole-body average SAR and overall field distribution.
-   **Key Steps**:
    1.  **Configuration**: Set `"study_type": "far_field"` and define `incident_directions` (e.g., `["x_pos", "y_neg"]`) and `polarizations` (e.g., `["theta", "phi"]`).
    2.  **Scene Setup**: Instead of a device, plane wave sources are configured to illuminate the phantom from multiple directions, covering a full range of exposure angles.
    3.  **Simulation Run**: Multiple simulations are typically run for each frequency, covering all specified directions and polarizations (e.g., 12 simulations per frequency: 6 directions × 2 polarizations).
    4.  **Results Analysis**: Focuses on whole-body average SAR and how SAR is distributed across the entire phantom, often aggregated over various exposure scenarios.
-   **Auto-Induced Mode**: While currently a placeholder, this mode is envisioned for future implementations to simulate EMF exposure induced by body motion or other dynamic scenarios.

## ✅ Tips for Success

-   **Scale Up Your Studies**: For multi-core local execution, leverage `run_parallel_studies.py --num-splits 4` to distribute simulations across multiple CPU cores.
-   **Cloud Computing with oSPARC**: For hundreds or thousands of simulations, oSPARC offers a cost-effective and fast cloud solution. Remember to set up your API keys in a `.env` file.
-   **Customize with Confidence**: Feel free to modify frequencies and placements in your configuration files. However, for consistency with GOLIAT's protocols, it's generally recommended to keep the core antenna models fixed.
-   **Effective Debugging**: Always consult the `logs/` directory for detailed error messages. You can also rerun specific phases of a study (e.g., `"do_setup": false, "do_run": false, "do_extract": true`) to isolate and debug issues more efficiently.

You are now equipped to navigate GOLIAT and perform sophisticated EMF dosimetry simulations! For hands-on examples, proceed to the [Tutorials](tutorials/basic.md). If you have any further questions or encounter issues, please open a [GitHub Issue](https://github.com/rwydaegh/goliat/issues).

---
*Last updated: {date}*