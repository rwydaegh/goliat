# Basic Tutorial: Running a Default Study

This tutorial shows how to run a default near-field study using the provided configuration. It uses the "thelonious" phantom at 700 MHz with a cheek placement. The process includes loading the config, executing the simulation, and reviewing the results.

## Prerequisites

Follow the [Quick Start](../quick_start.md) to install dependencies and set up Sim4Life.

## Step 1: Use the Default Config

The default near-field configuration is `configs/near_field_config.json`. For this tutorial, we limit to one phantom and frequency for simplicity.

Key settings in `near_field_config.json`:
- `study_type`: "near_field"
- `phantoms`: ["thelonious"] (6-year-old male phantom)
- `frequencies_mhz`: [700] (single frequency; full config has more)
- Placement: "by_cheek" (antenna 8 mm from cheek, default for this scenario)

The config inherits from `base_config.json` for common settings like solver and gridding.

## Step 2: Execute the Study

Run the study from the terminal:

```bash
python run_study.py --config configs/near_field_config.json
```

- The GUI opens.
- Click "Load Config" and select `near_field_config.json` (or specify via CLI).
- Click "Run Study".
- The process:
  1. Downloads the phantom and antenna model if not present.
  2. Builds the simulation scene: Loads the phantom, positions the antenna.
  3. Configures materials and grid.
  4. Runs the simulation using the iSolve solver.
  5. Extracts results: SAR values and statistics.

The GUI displays progress, estimated time, and logs. Check the console or `logs/` for detailed output.

## Step 3: Examine the Results

Results are saved in `results/near_field/thelonious/700MHz/by_cheek/`:

- `sar_results.json`: Summary metrics (e.g., "head_SAR": 0.45 mW/kg per 1W input).
- `sar_stats_all_tissues.pkl`: Detailed SAR for all tissues (use pandas to load).
- `sar_stats_all_tissues.html`: HTML table of tissue SAR values.
- `point_sensor_data.png`: E-field magnitude plot at monitoring points (if enabled).

Example from `sar_results.json`:

```json
{
  "head_SAR": 0.45,
  "peak_sar_10g_W_kg": 2.1,
  "power_balance": {"Balance": 99.87}
}
```

SAR values are normalized to 1W input power.

## Step 4: Run the Analysis Script

To aggregate and visualize results:

```bash
python run_analysis.py --config configs/near_field_config.json
```

This generates:
- `normalized_results_detailed.csv`: Per-simulation data.
- `normalized_results_summary.csv`: Averages by frequency/scenario.
- Plots in `results/near_field/plots/` (e.g., SAR by tissue).

Load in Python for further analysis:

```python
import pandas as pd
df = pd.read_csv("results/near_field/normalized_results_detailed.csv")
print(df.describe())
```

## Expected Results

For thelonious/700MHz/cheek (approximate; varies by run):

- Head SAR: 0.4-0.5 mW/kg.
- Brain psSAR10g: 1.5-2.5 mW/kg.
- Whole-body SAR: ~0.2 mW/kg.

These are normalized values. For far-field, see the far-field config.

## Troubleshooting

- "Phantom download failed": Ensure internet and email in `base_config.json`. Rerun to retry.
- Simulation slow: Reduce frequencies or use coarser grid in config.
- No output: Check `do_extract: true` in config; review logs for errors.

## Next Steps

- Customize placements/frequencies: [Intermediate Tutorial](intermediate.md).
- Run far-field: Change config to `far_field_config.json`.
- Batch processing: [Advanced Tutorial](advanced.md).

This tutorial verifies the basic workflow. For more, see [User Guide](../user_guide.md).

---
*Last updated: {date}*