# 🚀 Quick Start: Your First GOLIAT Simulation

Welcome to GOLIAT! This guide will get you up and running with your first automated EMF dosimetry simulation in minutes. GOLIAT streamlines the entire process using Sim4Life, from scene setup to results analysis. We'll walk through a simple "Hello World" near-field simulation to calculate Specific Absorption Rate (SAR) in a digital human phantom.

## 🎯 What You'll Achieve

By the end of this guide, you will have:
- Cloned the GOLIAT repository.
- Set up your Python environment with Sim4Life integration.
- Configured a basic near-field simulation.
- Run your first GOLIAT study.
- Understood where to find and interpret the simulation results.

## 📋 Prerequisites

Before you begin, please ensure you have the following:

-   **Sim4Life**: Version 8.2.2 or later, with a valid license. If you don't have it, you can download it from [ZMT Zurich](https://zmt.swiss/zurich-model-of-the-human-body/).
-   **Python**: Version 3.11+ (GOLIAT is designed to use the Python distribution bundled with Sim4Life, so a separate Python installation is usually not required).
-   **Digital Phantom Models**: GOLIAT will automatically download necessary phantom models (e.g., "thelonious" for a child, "eartha" for an adult) on its first run. You may be prompted to provide your email for licensing purposes.
-   **Antenna Models**: Supported antenna models for various frequencies (e.g., a 700 MHz PIFA antenna) are also auto-downloaded as needed.

**💡 Pro Tip**: If you're new to EMF dosimetry or Sim4Life, it's helpful to familiarize yourself with core concepts like SAR (Specific Absorption Rate – the rate at which electromagnetic energy is absorbed by biological tissue) and digital human phantoms (realistic 3D models of the human body used for simulation).

## Step 1: Clone the Repository and Install Dependencies

First, open your terminal or command prompt and clone the GOLIAT repository:

```bash
git clone https://github.com/rwydaegh/goliat.git
cd goliat
```

Next, install the required Python dependencies. It's crucial to use the Python environment provided by your Sim4Life installation.

```bash
# 1. Source .bashrc to add Sim4Life Python to your PATH (one-time setup)
#    Edit .bashrc in the project root if your Sim4Life path differs from the default.
source .bashrc

# Example .bashrc content for Windows (adjust path as necessary):
# export PATH="/c/Program Files/Sim4Life_8.2.2/Python:$PATH"
# export PYTHONPATH="/c/Program Files/Sim4Life_8.2.2/Python/Lib/site-packages:$PYTHONPATH"

# 2. Install Python packages
pip install -r requirements.txt
```

## Step 2: Configure Your First Study

GOLIAT uses a flexible JSON-based configuration system located in the `configs/` directory. For your first simulation, we'll use a simple near-field configuration.

1.  **Choose a template**:
    -   For **Near-Field** simulations (device close to the body), copy `configs/near_field_config.json` to `configs/my_first_near_field_study.json`.
    -   For **Far-Field** simulations (whole-body plane wave exposure), copy `configs/far_field_config.json` to `configs/my_first_far_field_study.json`.

2.  **Edit your custom config** (e.g., `configs/my_first_near_field_study.json`):
    ```json
    {
      "extends": "base_config.json",
      "study_type": "near_field",
      "phantoms": ["thelonious"],  // We'll use the child phantom for this example
      "frequencies_mhz": [700],    // A single frequency for a quick test run
      "execution_control": {
        "do_setup": true,
        "do_run": true,
        "do_extract": true
      }
      // GOLIAT will default to a "by_cheek" placement for near-field if not specified
    }
    ```
    **Note**: GOLIAT's configuration system supports inheritance. Your custom config extends `base_config.json`, allowing you to override only the settings you need. For a deep dive into all available parameters, refer to the [Configuration Guide](configuration.md).

3.  **For oSPARC Cloud Runs (Optional)**: If you plan to use oSPARC for cloud-based simulations, create a `.env` file in your project root with your credentials:
    ```
    OSPARC_API_KEY=your_osparc_api_key
    OSPARC_API_SECRET=your_osparc_api_secret
    OSPARC_API_SERVER=https://api.sim4life.science
    OSPARC_API_VERSION=v0
    ```

## Step 3: Run Your First Simulation

Now you're ready to launch your first GOLIAT study! Execute the following command in your terminal:

```bash
python run_study.py --config configs/my_first_near_field_study.json
```

**What to Expect:**
-   A GOLIAT GUI window will open, displaying real-time progress, status messages, and an estimated time of arrival (ETA).
-   **Behind the Scenes**:
    1.  GOLIAT will check for and download any required phantom and antenna models (this is a one-time process).
    2.  It will then automatically build the simulation scene in Sim4Life, loading the specified phantom and placing the antenna (e.g., 8mm from the cheek).
    3.  The simulation will run using the iSolve solver (locally) or be submitted to oSPARC (if configured for cloud batching).
    4.  Finally, GOLIAT will extract key SAR metrics, including whole-body SAR, head/trunk SAR, and peak 10g SAR in various tissues (eyes, brain, skin).
-   **Duration**: This initial test simulation typically takes 5-10 minutes, depending on your system and Sim4Life configuration.

**Visual Aid**:
![GOLIAT GUI during simulation](docs/img/gui_placeholder.png)
*Placeholder for a screenshot of the GOLIAT GUI during a simulation run.*

## Step 4: View and Analyze Results

Once the simulation is complete, GOLIAT will save all results in a structured directory within the `results/` folder. For our example, you'll find outputs in `results/near_field/thelonious/700MHz/by_cheek/`.

**Key Output Files**:
-   `sar_results.json`: Contains normalized SAR values (e.g., mW/kg per 1W input power).
-   `sar_stats_all_tissues.pkl`: A detailed Python pickle file with comprehensive tissue-specific data.
-   **Plots**: Various plots, such as SAR heatmaps and bar charts, visualizing the results.

You can also run the dedicated analysis script to aggregate and further process your results:

```bash
python run_analysis.py --config configs/my_first_near_field_study.json
```
This will generate additional CSV files and plots in the `results/` directory.

**Example Results Plot**:
![Example SAR Results Plot](docs/img/results_plot_placeholder.png)
*Placeholder for an example plot generated by GOLIAT, showcasing SAR distribution.*

**Troubleshooting**: Encountering issues? Refer to the [Troubleshooting Guide](troubleshooting.md) for common problems and solutions (e.g., Sim4Life licensing, Python path errors).

## Next Steps

Congratulations, you've successfully run your first GOLIAT simulation! Here's what you can do next:

-   **Customize Your Studies**: Experiment with your configuration files to explore different frequencies, phantoms, and antenna placements.
-   **Scale with the Cloud**: Learn how to leverage oSPARC for parallel, large-scale simulations by setting `"batch_run": true` in your config.
-   **Explore Tutorials**: Dive deeper with our [Basic Tutorial](tutorials/basic.md) for more default runs, or the [Advanced Tutorial](tutorials/advanced.md) for batching and complex scenarios.

You're now simulating EMF exposure like a pro! If you have any questions or encounter further issues, please don't hesitate to open a [GitHub Issue](https://github.com/rwydaegh/goliat/issues).

---
*Last updated: {date}*