# Refactoring Plan for Sensitivity Analysis

This document outlines the plan to refactor `run_sensitivity_analysis.py` to make it more dynamic, expandable, and configurable.

## 1. Create Configuration File

A new configuration file, `sensitivity_analysis_config.json`, will be created in `analysis/sensitivity_analysis/`. This file will centralize all settings.

### `sensitivity_analysis_config.json` Structure:

```json
{
  "base_config_path": "configs/todays_near_field_config.json",
  "results_dir": "analysis/sensitivity_analysis/results",
  "analysis_fig_dir": "analysis/sensitivity_analysis/plots",
  "config_dir": "analysis/sensitivity_analysis/configs",
  "profiling_config_path": "analysis/sensitivity_analysis/profiling_config.json",
  "sensitivity_parameters": [
    {
      "name": "simulation_time_multiplier",
      "values": [3, 6, 10]
    }
  ],
  "output_variables": {
    "whole_body_sar": {
      "source_type": "json",
      "file_path_template": "results/near_field/{phantom_name}/{frequency}MHz/{placement_name}/sar_results.json",
      "json_path": "SAR.Whole Body SAR.value"
    },
    "power_balance": {
      "source_type": "json",
      "file_path_template": "results/near_field/{phantom_name}/{frequency}MHz/{placement_name}/sar_results.json",
      "json_path": "power_balance.Balance"
    }
  }
}
```

## 2. Create Data Extractor Module

A new file, `src/data_extractor.py`, will be created. It will contain a generic function `get_parameter` that can extract data from different sources (e.g., JSON files, simulation outputs) based on the configuration.

## 3. Refactor `run_sensitivity_analysis.py`

The script will be modified to:
- Load settings from `sensitivity_analysis_config.json`.
- Use the new `data_extractor` module to retrieve output variables.
- Loop through multiple sensitivity parameters if defined.
- Handle multiple output variables.
- Save the results DataFrame to a pickle file (`sensitivity_results_{frequency}MHz.pkl`).

## 4. Refactor `plot_results` function

The plotting function will be updated to:
- Accept a list of output variables to plot.
- Create a plot with multiple lines, one for each output variable.
- Use labels and titles dynamically from the configuration.

## 5. Switch to Code Mode for Implementation

After approval of this plan, I will switch to Code mode to perform the file creation and modifications.