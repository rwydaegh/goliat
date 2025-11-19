# 📖 User Guide: Understanding GOLIAT Workflows

This guide explains how GOLIAT operates, covering workflows for both near-field (device close to the body, like a mobile phone) and far-field (whole-body exposure, such as environmental plane waves) scenarios.

GOLIAT automates the complex and often tedious aspects of EMF simulations: downloading necessary models, constructing complex scenes in Sim4Life, executing calculations, and extracting metrics like Specific Absorption Rate (SAR).

## 💡 Key concepts in EMF dosimetry

Before diving into the workflows, let's clarify some fundamental terms:

-   **Phantoms**: These are highly detailed digital human models (e.g., "thelonious" represents a 6-year-old boy, "ella" an adult female). They serve as realistic 3D representations for safe and accurate simulation of EMF interaction with biological tissues.
-   **Near-Field Simulations**: Focus on scenarios where an EMF source (e.g., an antenna in a mobile device) is in close proximity to the body. These simulations assess localized absorption, particularly in sensitive areas like the head, eyes, or limbs.
-   **Far-Field Simulations**: Address scenarios involving plane waves impinging on the entire body from various directions (e.g., front, back, sides). These are typically used for evaluating environmental or broadcast exposure.
-   **Specific Absorption Rate (SAR)**: The primary output metric, representing the rate at which electromagnetic energy is absorbed per unit mass of biological tissue, typically expressed in milliwatts per kilogram (mW/kg) per 1W of input power. GOLIAT provides whole-body average SAR, localized SAR (e.g., head/trunk), and peak spatial-average SAR (psSAR) over 10g tissue cubes in specific organs (e.g., brain, eyes, skin).
-   **Configuration Files (Configs)**: JSON files that serve as the "recipe" for your simulations. They define all parameters, including phantom selection, frequencies, antenna properties, and execution controls. GOLIAT uses a hierarchical system where study-specific configs inherit from `base_config.json`, allowing for easy customization and overrides.

## 🚀 End-to-end workflow: from config to analysis

GOLIAT's robust and modular design follows a clear, sequential flow: **Load Config → Orchestrate Study → Setup Scene → Run Simulation → Extract Results → Analyze & Plot**.

### 1. Load configuration

Your journey begins by specifying a configuration file.
-   Execute your study using the command line:
```bash
goliat study your_study_config.json
```

To bypass the caching system and force a fresh run, use the `--no-cache` flag:

```bash
goliat study your_study_config.json --no-cache
```
-   GOLIAT intelligently merges your chosen configuration (e.g., `near_field_config.json`) with the `base_config.json`, applying overrides for specific parameters like solver settings or gridding refinements.
-   A graphical user interface (GUI) will launch. Your configuration will be loaded and the study will initiate.

**💡 Pro Tip**: Configuration files are human-readable JSON. We recommend editing them in a code editor like VS Code. Start by copying one of the provided templates (e.g., `near_field_config.json`) and modify only the parameters relevant to your study, such as phantoms or frequencies. Refer to the [Configuration Guide](../developer_guide/configuration.md) for a detailed breakdown of all parameters.

### 2. Orchestrate study

The core logic of your simulation is managed by specialized **Study** classes (`NearFieldStudy` or `FarFieldStudy`).

-   **Near-Field Example**: If you're running a near-field study, the `NearFieldStudy` class will systematically loop through all defined phantoms, frequencies, and antenna placements. For instance, it might process "thelonious" phantom at 700 MHz with an antenna placed "by_cheek" (e.g., 8mm from the cheek).
-   **Far-Field Example**: For far-field studies, the `FarFieldStudy` class iterates through phantoms, frequencies, incident directions (e.g., x_pos, y_neg), and polarizations (e.g., theta, phi).
-   **Project Management**: For each unique simulation scenario, GOLIAT creates a dedicated Sim4Life project file (`.smash`) within a structured `results/` directory. The directory structure follows the pattern `results/{study_type}/{phantom}/{frequency}MHz/{scenario}/`, where `scenario` identifies the specific simulation configuration. For a near-field study, this might be `results/near_field/thelonious/700MHz/by_cheek_tragus_cheek_base/`. For a far-field study, it would be `results/far_field/thelonious/700MHz/environmental_x_pos_theta/`. Each simulation gets its own directory and project file, providing isolation and reliability.
-   **Progress Tracking**: The GUI provides real-time progress updates and an estimate for the Time Remaining, which becomes more accurate as the current session progresses. The GUI also tracks system resource utilization (CPU, RAM, GPU, VRAM) and displays time-series plots of these metrics. 

### 3. Setup scene in Sim4Life

This phase involves GOLIAT automatically constructing the 3D simulation environment within Sim4Life.

-   **Phantom Loading**: The specified digital phantom model is downloaded (if not already present) and imported into the scene, complete with its detailed tissue segmentation (e.g., skin, brain, muscle).
-   **Antenna/Source Placement**:
  -   **Near-Field**: The CAD model of the antenna (e.g., PIFA or IFA type) is imported and precisely positioned relative to the phantom, according to the defined placement scenario (e.g., 8mm gap from the cheek, with a specific tilt).
  -   **Far-Field**: Instead of an antenna, a plane wave source is configured, specifying its electric field strength (e.g., 1 V/m), incident direction, and polarization.
-   **Material Assignment**: Appropriate electromagnetic properties (e.g., conductivity, permittivity) are assigned to all entities in the scene (tissues, antenna components) based on the specified frequency.
-   **Gridding**: The simulation domain is discretized into a computational grid. GOLIAT intelligently applies gridding rules, using finer cells around critical areas like the antenna or phantom surface, and coarser cells elsewhere. This can be automatic or manually controlled via millimeter steps.
-   **Scene Optimization**: For `by_cheek` placements, GOLIAT automatically aligns the entire simulation scene (phantom, bounding boxes, sensors) with the phone's upright orientation. This alignment optimizes the computational grid orientation and can reduce simulation time. The alignment occurs after antenna placement and phantom rotation (if enabled), keeping the relative geometry correct throughout the scene.
-   **Boundaries and Sensors**: Perfectly Matched Layer (PML) boundaries are configured to absorb outgoing electromagnetic waves, preventing reflections. Point sensors are strategically placed at the corners of the simulation bounding box to monitor field values for convergence.
-   **Solver Configuration**: The Finite-Difference Time-Domain (FDTD) solver from `iSolve.exe` is set up, typically leveraging GPU acceleration (e.g., Acceleware or CUDA kernel) for faster computation.

### 4. Run simulation

With the scene meticulously set up, GOLIAT proceeds to execute the electromagnetic simulation.

-   **Local Execution**: For local runs, GOLIAT directly invokes the Sim4Life `iSolve.exe` solver. The GUI remains responsive, displaying logs and progress updates as the solver runs.
-   **Cloud Execution (oSPARC)**: For large-scale or parallel studies, GOLIAT can generate the necessary input files (`.h5`) and submit them as jobs to the oSPARC cloud platform. It then monitors the status of these jobs (e.g., PENDING → RUNNING → SUCCESS).
-   **Duration**: A single simulation can take anywhere from 5 seconds to 5 hours, depending on factors like grid resolution, frequency, and computational resources. All results are normalized to a 1W input power for consistency.

**Batch mode**: By setting `"batch_run": true` in your configuration, GOLIAT can manage multiple simulations concurrently, either locally (using `goliat parallel`) or on oSPARC. The GUI tracks the status of all jobs and automatically downloads results upon completion.

**Important limitation**: When running parallel simulations locally on a single machine with one GPU, **iSolve will only execute one simulation at a time**. This means:
- Setup and extract phases can run in parallel (CPU-based, benefits from parallelization)
- Run phase (iSolve) cannot run in parallel on a single GPU machine (processes queue sequentially)
- For true parallel iSolve execution, use oSPARC batch or multiple Windows PCs as described in [Cloud Setup](../cloud/cloud_setup.md)

### 5. Extract & analyze results

After the simulation, GOLIAT's `ResultsExtractor` and `Analyzer` components take over to process and interpret the vast amount of raw data.

-   **SAR Extraction**: The extractor pulls various SAR metrics from the simulation output:
  -   **Whole-Body SAR**: The average SAR over the entire phantom.
  -   **Localized SAR**: Average SAR in specific regions, such as the head or trunk, relevant for localized exposures.
  -   **psSAR10g**: Peak spatial-average SAR over a 10-gram tissue cube, typically reported for sensitive organs like the eyes, brain, and skin.
  -   **Power Balance**: A check to ensure energy conservation within the simulation, ideally close to 100%.
-   **Normalization**: All extracted SAR values are normalized to a 1W input power, providing a standardized basis for comparison.
-   **Output Files** (located in the `results/` folder):
  -   `sar_results.json`: A JSON file containing the primary normalized SAR values.
  -   `sar_stats_all_tissues.pkl`: A Python pickle file with detailed, tissue-specific SAR data.
  -   **Plots**: GOLIAT automatically generates a suite of visualizations, including SAR heatmaps (showing SAR distribution by tissue and frequency), bar charts (comparing SAR in different regions), and boxplots (illustrating SAR distributions).
-   **Aggregated Analysis**: You can run the dedicated analysis script (`goliat analyze --config your_config.json`) to aggregate results across multiple simulations and generate CSV reports and additional plots.
-   **Log Files**: For debugging and detailed tracking, GOLIAT generates two types of log files in the `logs/` directory for each run: a `.progress.log` for high-level updates and a `.log` for verbose, detailed information. The system automatically manages these files, keeping a maximum of 15 pairs to prevent excessive disk usage.

**Example output interpretation**: For a near-field 700MHz simulation with an antenna by the cheek, you might observe:
-   Head SAR: 0.5 mW/kg (per 1W input).
-   Brain psSAR10g: 2.1 mW/kg peak.
For far-field studies, the analysis often involves averaging results over different incident directions to determine typical exposure scenarios.

💡 If you simulate the whole-body, you get an overview of *all* the SAR values in each tissue (as defined by Sim4Life), their psSAR10g values and more! This is also displayed in HTML files. Moreover, we define a number of *tissue groups* of interest, including the **eyes, head, skin and genitals** which aggregate the above results for groups of tissues (as defined in `data/material_name_mapping.json`).

## 🔄 Near-field vs. far-field workflows: a comparison

While the core GOLIAT workflow remains consistent, the specifics of scene setup and analysis differ between near-field and far-field studies.

### Near-field workflow (device exposure)

-   **Primary Use Case**: Assessing localized EMF exposure from devices held close to the body, such as mobile phones, wearables, or other devices. The focus is on SAR in specific tissues and organs.

-   **Key Steps**:
  1.  **Configuration**: Set `"study_type": "near_field"` and define specific `placement_scenarios` (e.g., "by_cheek", "on_wrist").
  2.  **Scene Setup**: Involves importing a detailed CAD model of the device antenna and precisely positioning it relative to the phantom, often with a small air gap (e.g., 8mm).
  3.  **Simulation Run**: Typically uses a harmonic excitation (single frequency) to simulate continuous wave exposure.
  4.  **Results Analysis**: Concentrates on localized SAR values (e.g., head SAR, trunk SAR) and peak spatial-average SAR (psSAR10g) in sensitive tissues like the eyes, brain, and skin.

-   **Free-Space Mode**: GOLIAT supports a "freespace" phantom option, allowing you to run simulations of the antenna in isolation (without a body). This is useful for antenna characterization and validation.

-   **Gaussian Excitation**: For near-field studies, you can use Gaussian pulse excitation instead of harmonic. This enables frequency-domain analysis and antenna resonance detection. Set `"excitation_type": "Gaussian"` in your config and configure `bandwidth_mhz` (typically 50-150 MHz). Gaussian excitation requires longer simulation times due to frequency resolution requirements.

### Far-field workflow (environmental exposure)

-   **Primary Use Case**: Evaluating whole-body EMF exposure from distant sources, such as broadcast antennas, cellular base stations, or industrial equipment. The focus is on whole-body average SAR and overall field distribution. We reduce the complexity of impinging fields to all orthogonal directions and two polarizations, and assume that by normalizing this to 1 W, we can construct a *transfer functions* between measured E-field values and absorption values, especially for channel scenarios where the user is not down- or uploading anything.

-   **Key Steps**:
  1.  **Configuration**: Set `"study_type": "far_field"` and define `incident_directions` (e.g., `["x_pos", "y_neg"]`) and `polarizations` (e.g., `["theta", "phi"]`).
  2.  **Scene Setup**: Instead of a device, plane wave sources are configured to illuminate the phantom from multiple directions, covering a full range of exposure angles.
  3.  **Simulation Run**: Multiple simulations are typically run for each frequency, covering all specified directions and polarizations (e.g., 12 simulations per frequency: 6 directions × 2 polarizations).
  4.  **Results Analysis**: Focuses on whole-body average SAR and how SAR is distributed across the entire phantom, often aggregated over various exposure scenarios.

-   **Auto-Induced Mode**: While currently a placeholder, this mode is envisioned for future implementations to simulate EMF exposure induced by body motion or other dynamic scenarios.

## ✅ Tips for success

-   **Scale Up Your Studies**: For multi-core local execution, leverage `goliat parallel near_field_config.json --num-splits 4` to distribute simulations across multiple CPU cores. **Note**: On a single-GPU machine, this only parallelizes setup and extract phases; iSolve run phases will still execute sequentially. For true parallel run phases, use oSPARC batch or multiple Windows PCs.
-   **Cloud Computing with oSPARC**: For hundreds or thousands of simulations, oSPARC offers a cost-effective and fast cloud solution. Remember to set up your API keys in a `.env` file.
- **Manage disk space**: For serial workflows on machines with limited storage, use `"auto_cleanup_previous_results": ["output"]` to automatically delete previous simulation files. See [Configuration Guide](../developer_guide/configuration.md#execution-control) for details.
-   **Customize with Confidence**: Feel free to modify frequencies and placements in your configuration files. However, for consistency with GOLIAT's protocols, it's generally recommended to keep the core antenna models fixed.
-   **Effective Debugging**: Always consult the `logs/` directory for detailed error messages. You can also rerun specific phases of a study (e.g., `"do_setup": false, "do_run": false, "do_extract": true`) to isolate and debug issues more efficiently.

You can now navigate GOLIAT and perform EMF dosimetry simulations. For hands-on examples, proceed to the [Tutorials](../tutorials/overview.md). For a complete reference of all available features, see the [Full List of Features](../reference/full_features_list.md). If you have any further questions or encounter issues, please open a [GitHub Issue](https://github.com/rwydaegh/goliat/issues).
