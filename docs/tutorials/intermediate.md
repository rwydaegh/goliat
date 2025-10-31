# 🧑‍💻 Intermediate Tutorial: Customizing Placements and Frequencies

This tutorial builds upon the [Basic Tutorial](basic.md) by demonstrating how to customize antenna placements and simulation frequencies in GOLIAT. You'll learn to modify configuration files to explore different exposure scenarios.

## 🎯 What you'll achieve

By the end of this tutorial, you will be able to:
-   Create a custom configuration file for intermediate studies.
-   Define multiple frequencies for a single study.
-   Specify custom antenna placements relative to the phantom.
-   Run a study with your customized settings.

## 📋 Prerequisites

Ensure you have completed the [Basic Tutorial](basic.md) and have a working GOLIAT environment.

## Step 1: Create a custom configuration file

Instead of modifying the default `near_field_config.json`, we'll create a new configuration file to keep your changes organized.

1.  Copy `configs/near_field_config.json` to `configs/my_intermediate_study.json`.
    ```bash
    cp configs/near_field_config.json configs/my_intermediate_study.json
    ```

2.  Open `configs/my_intermediate_study.json` in your code editor.

## Step 2: Define multiple frequencies

Let's add another frequency to our study. We'll simulate at both 700 MHz and 900 MHz.

Locate the `"frequencies_mhz"` array and modify it:

```json
{
  "extends": "base_config.json",
  "study_type": "near_field",
  "phantoms": ["thelonious"],
  "frequencies_mhz": [700, 900], // Added 900 MHz
  "execution_control": {
    "do_setup": true,
    "do_run": true,
    "do_extract": true
  },
  // ... rest of the config
}
```

## Step 3: Specify custom antenna placements

GOLIAT allows you to define various antenna placement scenarios. We'll add a new placement called "by_ear" and enable it for the "thelonious" phantom.

1.  Add a `"placement_scenarios"` block to your `my_intermediate_study.json` (if it doesn't exist, or modify if it does). This block defines the base positions and orientations.

    ```json
    {
      "extends": "base_config.json",
      "study_type": "near_field",
      "phantoms": ["thelonious"],
      "frequencies_mhz": [700, 900],
      "execution_control": {
        "do_setup": true,
        "do_run": true,
        "do_extract": true
      },
      "placement_scenarios": {
        "by_cheek": {
          "positions": {"base": [0, 0, 0]},
          "orientations": {"base": [], "up": [{"axis": "X", "angle_deg": 10}]}
        },
        "by_ear": { // New placement scenario
          "positions": {"base": [0, 50, 0]}, // Example: 50mm along Y-axis from origin
          "orientations": {"base": [], "rotate_z": [{"angle_deg": 90}]} // Example: Rotate 90 deg around Z
        }
      },
      // ... rest of the config
    }
    ```
    **Note**: The exact coordinates and rotations will depend on your antenna model and desired position. These are illustrative examples.

2.  Enable the new placement for the "thelonious" phantom in the `"phantom_definitions"` section:

    ```json
    {
      // ...
      "phantom_definitions": {
        "thelonious": {
          "placements": {
            "do_by_cheek": true,
            "do_by_ear": true // Enable the new placement
          },
          "distance_from_cheek": 8,
          "distance_from_ear": 5 // Example: 5mm distance for "by_ear"
        }
      }
    }
    ```

## Step 4: Run the customized study

Save your `configs/my_intermediate_study.json` file. Now, execute the study using your new configuration:

```bash
python run_study.py --config configs/my_intermediate_study.json
```

GOLIAT will now run simulations for:
-   "thelonious" phantom at 700 MHz with "by_cheek" placement.
-   "thelonious" phantom at 700 MHz with "by_ear" placement.
-   "thelonious" phantom at 900 MHz with "by_cheek" placement.
-   "thelonious" phantom at 900 MHz with "by_ear" placement.

You will see the GUI update as each simulation scenario is processed.

## Step 5: Examine the results

After the study completes, navigate to your `results/` directory. You will find new subdirectories corresponding to the additional frequency and placement:

-   `results/near_field/thelonious/700MHz/by_ear/`
-   `results/near_field/thelonious/900MHz/by_cheek/`
-   `results/near_field/thelonious/900MHz/by_ear/`

Each directory will contain its own `sar_results.json`, `sar_stats_all_tissues.pkl`, and plots.

Run the analysis script to aggregate all results from this multi-scenario study:

```bash
python run_analysis.py --config configs/my_intermediate_study.json
```

This will generate aggregated CSVs and plots that include data from all frequencies and placements you defined.

## ⚠️ Troubleshooting

-   **"Placement not found"**: Double-check that the placement name in `"phantom_definitions"` (e.g., `"do_by_ear": true`) exactly matches a key in your `"placement_scenarios"` block (e.g., `"by_ear"`).
-   **JSON Syntax Errors**: Ensure your JSON file is correctly formatted. Use a JSON validator if you encounter issues.
-   **Simulation Time**: Running multiple frequencies and placements will increase the total simulation time. Consider using fewer scenarios for quick tests.

## ➡️ Next steps

-   **Advanced Batching**: Learn how to run many simulations in parallel using oSPARC cloud batching in the [Advanced Tutorial](advanced.md).
-   **Far-Field Studies**: Explore environmental exposure scenarios by configuring a far-field study.
-   **Developer Guide**: If you're interested in extending GOLIAT, refer to the [Developer Guide](../developer_guide.md).