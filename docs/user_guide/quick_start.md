# Quick start: Your first GOLIAT simulation

Welcome to GOLIAT! This guide will get you up and running with your first automated EMF dosimetry simulation in minutes. GOLIAT streamlines the entire process using Sim4Life, handling scene setup, execution, and results analysis. We'll walk through a simple "Hello World" near-field simulation to calculate Specific Absorption Rate (SAR) in a digital human phantom.

## What you'll achieve

By the end of this guide, you will have:
- Cloned the GOLIAT repository.
- Set up your Python environment with Sim4Life integration.
- Configured a basic near-field simulation.
- Run your first GOLIAT study.
- Understood where to find and interpret the simulation results.

## Prerequisites

Before you begin, please ensure you have the following:

-   **Sim4Life**: Version 8.2.0 with a valid license. If you don't have it, you can download it from [ZMT Zurich](https://zmt.swiss/zurich-model-of-the-human-body/). **Note**: GOLIAT has only been tested on Sim4Life 8.2.0; compatibility with newer versions is untested.
-   **Python**: Version 3.11 (GOLIAT is designed to use the Python distribution bundled with Sim4Life, so a separate Python installation is usually not required).
-   **Digital Phantom Models**: GOLIAT automatically downloads phantom models (e.g., "thelonious" for a child, "eartha" for an adult) on first run. You may be prompted to provide your email for licensing purposes.
-   **Antenna Models**: Antenna models for various frequencies are auto-downloaded as needed.

**💡 Pro Tip**: If you're new to EMF dosimetry or Sim4Life, familiarize yourself with core concepts. See the [User Guide](user_guide.md) for background on SAR and digital human phantoms.

## Step 1: Clone the repository and set up Sim4Life Python

First, open your terminal or command prompt and clone the GOLIAT repository:

```bash
git clone https://github.com/rwydaegh/goliat.git
cd goliat
```

Next, set up your Sim4Life Python environment:

```bash
source .bashrc
```

**Note**: The `.bashrc` file is created in the project directory and adds Sim4Life Python to your PATH. During setup, GOLIAT will prompt you if you want to copy this to your home directory (`~/.bashrc`) to make Sim4Life Python available automatically in all new bash windows. This is optional - you can keep using the project-local `.bashrc` and remember to run `source .bashrc` each time, or copy it to your home directory for convenience.

If Sim4Life is installed elsewhere or you're using a different version, GOLIAT will automatically detect it and update `.bashrc` accordingly.

**Important**: Install the GOLIAT package in editable mode:

```bash
python -m pip install -e .
```

This installs GOLIAT and its dependencies. The editable mode allows code modifications to be reflected immediately without reinstalling.

Now initialize GOLIAT by running:

```bash
goliat init
```

This will:
- Verify Sim4Life Python interpreter is being used
- Prepare data files (phantoms, antennas)

**Alternative**: If you skip `goliat init`, commands like `goliat study` will automatically prompt you to install when first run.

## Step 2: Configure your first study

GOLIAT uses a flexible JSON-based configuration system located in the `configs/` directory. For your first simulation, we'll use a simple near-field configuration.

1.  **Choose a template**:
    -   For **Near-Field** simulations (device close to the body), copy `configs/near_field_config.json` to `configs/my_first_near_field_study.json`.
    -   For **Far-Field** simulations (whole-body plane wave exposure), copy `configs/far_field_config.json` to `configs/my_first_far_field_study.json`.

2.  **Edit your custom config** (e.g., `configs/my_first_near_field_study.json`):

        ```json
        {
          "extends": "base_config.json",
          "study_type": "near_field",
          "phantoms": ["thelonious"],
          "frequencies_mhz": [700],
          "execution_control": {
            "do_setup": true,
            "do_run": true,
            "do_extract": true
          }
        }
        ```
    
    **Note**: In this example, we use the "thelonious" child phantom and a single frequency (700 MHz) for a quick test run. GOLIAT's configuration system supports inheritance. Your custom config extends `base_config.json`, allowing you to override only the settings you need. For a deep dive into all available parameters, refer to the [Configuration Guide](../developer_guide/configuration.md).

3.  **Environment Variables (Optional)**: Create a `.env` file in the project root if needed:
    - **oSPARC Cloud Runs**: Add API credentials if using cloud execution
    - **Phantom Downloads**: Add email if prompted during phantom download

For details, see [Troubleshooting](../troubleshooting.md).

## Step 3: Run your first simulation

Now you're ready to launch your first GOLIAT study! Execute the following command in your terminal:

```bash
goliat study my_first_near_field_study
```

**What happens:**

- GOLIAT GUI opens showing real-time progress and ETA
- Downloads phantom and antenna models (one-time)
- Builds simulation scene in Sim4Life (loads phantom, places antenna)
- Runs FDTD solver via iSolve
- Extracts SAR metrics (whole-body, head/trunk, peak 10g SAR)
- Duration: 5-10 minutes depending on hardware

![GOLIAT GUI during simulation](../img/tutorials/tut1_gui.gif)
*GOLIAT GUI displaying real-time progress and simulation status.*

## Step 4: View and analyze results

Once the simulation is complete, GOLIAT will save all results in a structured directory within the `results/` folder. For our example, you'll find outputs in `results/near_field/thelonious/700MHz/by_cheek/`.

**Key output files**:
- `sar_results.json`: Contains normalized SAR values (e.g., mW/kg per 1W input power).
- `sar_stats_all_tissues.pkl`: A detailed Python pickle file with tissue-specific data.
- **Plots**: Various plots, such as SAR heatmaps and bar charts, visualizing the results.

You can also run the dedicated analysis script to aggregate and further process your results:

```bash
goliat analyze --config my_first_near_field_study
```
This will generate additional CSV files and plots in the `results/` directory.

**Example results plot**:
![Example SAR Results Plot](../img/results_plot.png)
*Example plot generated by GOLIAT showing SAR distribution.*

**Troubleshooting**: Encountering issues? Refer to the [Troubleshooting Guide](../troubleshooting.md) for common problems and solutions (e.g., Sim4Life licensing, Python path errors, disk space management).

## Next steps

You've successfully run your first GOLIAT simulation. Here's what you can do next:

- **Explore all features**: Check out the [Full List of Features](../reference/full_features_list.md) to discover everything GOLIAT can do
- **Customize your studies**: Experiment with configuration files to explore different frequencies, phantoms, and antenna placements
- **Manage disk space**: For serial workflows, enable automatic cleanup: `"auto_cleanup_previous_results": ["output"]`. See [Configuration Guide](../developer_guide/configuration.md#execution-control)
- **Scale with the cloud**: Use oSPARC for parallel, large-scale simulations by setting `"batch_run": true` in your config
- **Explore tutorials**: Start with [Far-Field Basics Tutorial](../tutorials/01_far_field_basics.ipynb) or [Parallel and Cloud Execution Tutorial](../tutorials/05_parallel_and_cloud_execution.ipynb)

If you have questions or encounter issues, open a [GitHub Issue](https://github.com/rwydaegh/goliat/issues).

---