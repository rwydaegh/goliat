# Antenna Detuning Feature Design

## Overview

This feature allows harmonic simulations to use calibrated detuning frequencies (in MHz) that account for body presence effects. Detuning values are determined through calibration runs (Gaussian excitation) and then applied during harmonic simulations.

## Configuration Structure

### Main Config Fields

Add these fields to your harmonic config file:

```json
{
  "extends": "nf_l_nd_f_minimal.json",
  "detuning_enabled": true,
  "detuning_config": "../data/detuning_calibration_nf_l_nd_f.json",
  "detuning_write_during_calibration": true,
  "simulation_parameters": {
    "excitation_type": "Harmonic"
  }
}
```

**Fields:**
- `detuning_enabled` (boolean): Master switch to enable/disable detuning feature
  - `true`: Enable detuning lookup and application
  - `false`: Disable detuning (ignore `detuning_config` if provided, warn once at startup)
  
- `detuning_config` (string, optional): Path to detuning JSON file, relative to config file location
  - Only used if `detuning_enabled: true`
  - Example: `"../data/detuning_calibration_nf_l_nd_f.json"` (from `configs/` folder)
  
- `detuning_write_during_calibration` (boolean): Enable writing/updating detuning file during calibration runs
  - `true`: Allow calibration runs to create/update detuning file
  - `false`: Read-only mode (only lookup, never write)

### Detuning File Structure

The detuning file (`data/detuning_calibration_*.json`) mirrors the directory structure:

```
results/near_field/{phantom}/{frequencyMHz}/{placement_name}/
```

**JSON Structure:**
```json
{
  "detuning_data": {
    "thelonious": {
      "700MHz": {
        "by_cheek_tragus_cheek_base": 20,
        "by_cheek_tragus_cheek_up": 18,
        "by_cheek_tragus_cheek_down": 22,
        "front_of_eyes_center_vertical": -5,
        "by_belly_center_vertical": 10
      },
      "835MHz": {
        "by_cheek_tragus_cheek_base": 15,
        "front_of_eyes_center_vertical": -8
      }
    },
    "eartha": {
      "700MHz": {
        "by_cheek_tragus_cheek_base": 25,
        "front_of_eyes_center_vertical": -3
      }
    }
  }
}
```

**Structure Rules:**
- Top level: `detuning_data` object
- Second level: Phantom name (normalized to lowercase for lookup)
- Third level: Frequency string in format `"{frequency}MHz"` (e.g., `"700MHz"`)
- Fourth level: Placement name (format: `{scenario}_{position}_{orientation}`)
- Leaf values: Detuning amount in MHz (integer or float, can be negative)

## Behavior

### Lookup Logic

When setting up a harmonic simulation:

1. **Check if enabled**: If `detuning_enabled: false`, skip detuning lookup
2. **Resolve path**: Resolve `detuning_config` relative to config file location
3. **Load detuning file**: Load JSON file (create empty structure if missing and write mode enabled)
4. **Normalize keys**:
   - Phantom name: `phantom_name.lower()`
   - Frequency: `f"{frequency_mhz}MHz"`
   - Placement name: `f"{scenario_name}_{position_name}_{orientation_name}"`
5. **Lookup**: `detuning_data[phantom_lower][freq_str][placement_name]`
6. **Apply**: `simulation_frequency = center_frequency + detuning_mhz`
   - If entry missing: default to `0` (no detuning)
   - If entry found: use the detuning value

### Missing Entry Handling

- **If `detuning_enabled: true`**:
  - Missing entry defaults to `0` (no detuning)
  - Warn **every time** a missing entry is found for a specific simulation
  - Warning format: `"WARNING: No detuning data for {phantom}/{frequencyMHz}/{placement_name}, using 0 MHz"`
  
- **If `detuning_enabled: false`** but `detuning_config` provided:
  - Warn **once** at startup: `"WARNING: detuning_config provided but detuning_enabled is false, ignoring detuning config"`
  - No per-simulation warnings

### Calibration Workflow

When `detuning_write_during_calibration: true`:

1. **Load existing file**: If file exists, load it. If not, create empty structure:
   ```json
   {
     "detuning_data": {}
   }
   ```
2. **For each simulation**:
   - Check if entry exists: `detuning_data[phantom][freq][placement]`
   - **If missing**: Add entry with value `0` (never overwrite existing values)
   - **If exists**: Skip (preserve existing value)
3. **Save file**: After calibration completes, save updated file

### Validation

- **Study type check**: If `detuning_enabled: true` and `study_type == "far_field"`, raise error:
  ```
  ValueError: "Detuning feature is only supported for near_field studies, not far_field"
  ```
- **No structure validation**: Don't validate that detuning structure matches expected simulations (just do lookups and default to 0)

## Path Resolution

The `detuning_config` path is resolved relative to the config file's directory:

- Config file: `configs/nf_l_nd_f_harmonic.json`
- Detuning config: `"../data/detuning_calibration_nf_l_nd_f.json"`
- Resolved: `{project_root}/data/detuning_calibration_nf_l_nd_f.json`

Implementation uses `os.path.normpath(os.path.join(os.path.dirname(config_path), detuning_config_path))` then converts to absolute path.

## Frequency Application

When detuning is applied:

- **Original**: `center_frequency` from `antenna_config.{frequency}.center_frequency`
- **Detuning**: Lookup value from detuning file (or 0 if missing)
- **Final frequency**: `center_frequency + detuning_mhz`
- **Applied to**: `edge_source_settings.Frequency` and `edge_source_settings.CenterFrequency` in harmonic simulations

## Example Workflow

### Calibration Run (Gaussian)

1. Run Gaussian excitation simulations to detect antenna resonance
2. Analyze results to determine detuning amounts
3. Create/update `data/detuning_calibration_nf_l_nd_f.json` with detected values
4. Missing entries are filled with `0` (never overwrite existing)

### Harmonic Run

1. Load config with `detuning_enabled: true`
2. Load detuning file
3. For each simulation:
   - Lookup detuning value
   - Apply: `frequency = center_frequency + detuning`
   - Run harmonic simulation at adjusted frequency
4. Warn if any entries are missing

## Implementation Notes

- Phantom name matching is case-insensitive (normalize to lowercase)
- Frequency format must match exactly: `"700MHz"` (not `"700"` or `"700 MHz"`)
- Placement name format: `{scenario}_{position}_{orientation}` (matches directory structure)
- Detuning values can be positive (shift up) or negative (shift down)
- File location: `data/` folder (ephemeral, can be regenerated)
