# GOLIAT Configuration Guide

GOLIAT uses a hierarchical JSON configuration system to define all aspects of a simulation study. This modular approach allows for flexibility and reproducibility. A study-specific configuration file (e.g., `near_field_config.json`) inherits settings from a `base_config.json` file, allowing you to override only the parameters you need for a specific study.

This guide provides a reference for all available configuration parameters, their purpose, and valid values.

## Configuration hierarchy

The system is designed to avoid repetition by allowing configurations to "extend" a base file. The child's values will always override the parent's.

```mermaid
graph TD
    base[base_config.json<br/>Shared settings]
    nf[near_field_config.json<br/>Near-field specifics]
    ff[far_field_config.json<br/>Far-field specifics]
    
    base -->|extends| nf
    base -->|extends| ff
    
    style base fill:#4CAF50
    style nf fill:#2196F3
    style ff fill:#2196F3
```

To create a custom study, you can copy an existing configuration and modify it. For example, to create `my_study.json`:

```json
{
  "extends": "near_field_config.json",
  "phantoms": ["thelonious"],
  "frequencies_mhz": [900]
}
```

---

## **1. Core Settings** (`base_config.json`)

These are the foundational settings shared across all study types.

| Parameter | Type | Example Value | Description |
| :--- | :--- | :--- | :--- |
| `extends` | string | `"base_config.json"` | **(Optional)** Specifies the parent configuration file to inherit from. This is typically used in study-specific configs. |
| `study_type` | string | `"near_field"` | **(Required)** The type of study to run. Valid options are `"near_field"` or `"far_field"`. |
| `use_gui` | boolean | `true` | If `true`, the graphical user interface (GUI) will be launched to monitor progress. If `false`, the study runs in headless mode, printing logs to the console. |
| `phantoms` | array | `["thelonious", "eartha"]` | A list of the virtual human phantom models to be used in the study. For near-field studies, you can also include `"freespace"` to run a simulation of the antenna in isolation. |
| `verbose` | boolean | `false` | If `true`, enables detailed verbose logging to the console, in addition to the standard progress logs. |

<br>

## **2. Extraction Settings** (`extraction`)

This object controls which data is extracted from simulation results. All flags default to `true` except SAPD which defaults to `false`.

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `extraction.sar` | boolean | `true` | If `true`, extracts Specific Absorption Rate (SAR) statistics from simulation results including tissue-specific SAR, peak 10g SAR, and tissue group averages. When disabled, placeholder files are created for caching compatibility. |
| `extraction.power_balance` | boolean | `true` | If `true`, extracts power balance metrics (Pin, DielLoss, RadPower) to verify energy conservation. Balance should be close to 100% for accurate simulations. |
| `extraction.sapd` | boolean | `false` | If `true`, extracts Surface Absorbed Power Density (SAPD) from simulation results. Recommended for frequencies > 6 GHz where SAPD is the relevant exposure metric. Overridden to `true` in far-field configs. |
| `extraction.point_sensors` | boolean | `true` | If `true`, extracts time-domain E-field data from point sensors configured via `simulation_parameters.number_of_point_sensors`. Generates plots and raw data for field dynamics analysis. |

**Example:**
```json
{
    "extraction": {
        "sar": true,
        "power_balance": true,
        "sapd": false,
        "point_sensors": true
    }
}
```

**Backward Compatibility:** Legacy top-level keys (`extract_sar`, `extract_power_balance`, `extract_sapd`) are still supported but deprecated. The new `extraction.*` structure takes precedence.

<br>

## **3. Execution Control** (`execution_control`)

This object controls which phases of the workflow are executed. This is useful for re-running specific parts of a study, such as only extracting results from an already completed simulation.

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `do_setup` | boolean | `true` | If `true`, the simulation scene will be built (phantoms loaded, materials assigned, etc.). |
| `do_run` | boolean | `true` | If `true`, the simulation solver will be executed. |
| `do_extract` | boolean | `true` | If `true`, the results will be extracted from the simulation output and processed. |
| `only_write_input_file` | boolean | `false` | If `true`, the `run` phase will only generate the solver input file (`.h5`) and then stop, without actually running the simulation. This is useful for debugging the setup or for preparing files for a manual cloud submission. **Note**: This flag modifies the behavior of the run phase, so `do_run` must be `true` for this to have any effect. |
| `batch_run` | boolean | `false` | If `true`, enables the oSPARC batch submission workflow. This is an advanced feature for running many simulations in parallel on the cloud. |
| `auto_cleanup_previous_results` | array | `[]` | A list of file types to automatically delete **after** a simulation's results have been successfully extracted. This helps to preserve disk space in serial workflows. Valid values are: `"output"` (`*_Output.h5`), `"input"` (`*_Input.h5`), and `"smash"` (`*.smash`). **Warning**: This feature is incompatible with parallel or batch runs and should only be used when `do_setup`, `do_run`, and `do_extract` are all `true`. |

The `do_setup` flag directly controls the project file (`.smash`) handling. Its behavior is summarized below:

| `do_setup` Value | File Exists? | Action |
| :--- | :--- | :--- |
| `true` | Yes | **Delete and Override** with a new project. |
| `true` | No | Create a new project. |
| `false` | Yes | **Open and Use** the existing project. |
| `false` | No | **Error** and terminate the program. |

**Example: Write input file without running solver**
```json
"execution_control": {
  "do_setup": true,
  "do_run": true,
  "do_extract": false,
  "only_write_input_file": true
}
```

!!! warning "Common mistake"
    Setting `only_write_input_file: true` with `do_run: false` will skip the run phase entirely. The flag only affects the *behavior* of the run phase, not whether it executes. You must set `do_run: true` for the input file to be written.

**Example: Extraction-only workflow**
```json
"execution_control": {
  "do_setup": false,
  "do_run": false,
  "do_extract": true
}
```

**Example: Aggressive Cleanup in a Serial Workflow**
```json
"execution_control": {
  "do_setup": true,
  "do_run": true,
  "do_extract": true,
  "auto_cleanup_previous_results": ["output", "input"]
}
```

<br>

## **4. Simulation Parameters** (`simulation_parameters`)

These settings control the core behavior of the FDTD solver.

| Parameter | Type | Example Value | Description |
| :--- | :--- | :--- | :--- |
| `global_auto_termination` | string | `"GlobalAutoTerminationUserDefined"` | The solver's termination criteria. `"GlobalAutoTerminationWeak"` is a common default, while `"GlobalAutoTerminationUserDefined"` allows for a custom convergence level. |
| `convergence_level_dB` | number | `-15` | The convergence threshold in decibels (dB) when using user-defined termination. The simulation stops when the energy in the system decays below this level. |
| `simulation_time_multiplier` | number | `3.5` | A multiplier used to determine the total simulation time. The time is calculated as the duration it takes for a wave to traverse the simulation bounding box diagonal, multiplied by this value. |
| `number_of_point_sensors` | number | `8` | The number of point sensors to place at the corners of the simulation bounding box. These sensors monitor the electric field over time. |
| `point_source_order` | array | `["lower_left_bottom", ...]` | Defines the specific order and location of the point sensors at the 8 corners of the bounding box. |
| `excitation_type` | string | `"Harmonic"` | The type of excitation source. `"Harmonic"` is used for single-frequency simulations (standard for SAR). `"Gaussian"` is used for frequency-domain analysis, typically for antenna characterization or near-field detuning detection. |
| `bandwidth_mhz` | number | `50.0` | The bandwidth in MHz for a Gaussian excitation. Typical values are 50-150 MHz. Narrower bandwidths provide better frequency resolution but require longer simulation times. |
| `target_freq_resolution_mhz` | number | `10.0` | Target frequency resolution for Gaussian excitation simulations. Smaller values provide finer frequency resolution but increase simulation time. |
| `gaussian_pulse_k` | number | `3` | Gaussian pulse k parameter. When set to 5, uses Sim4Life's built-in Gaussian excitation. Values other than 5 use custom UserDefined waveforms. Lower k values create faster pulses. |
| `bbox_padding_mm` | number | `50` | **(Far-Field)** Padding in millimeters to add around the phantom's bounding box to define the simulation domain. |
| `freespace_antenna_bbox_expansion_mm` | array | `[20, 20, 20]` | **(Near-Field)** Padding in [x, y, z] millimeters to add around the antenna for free-space simulations. |
| `keep_awake` | boolean | `true` | If `true`, launches a keep-awake script when the simulation starts to prevent system sleep during long-running simulations. |
| `detuning_enabled` | boolean | `false` | **(Near-Field)** If `true`, applies calibrated frequency detuning to account for body loading effects on antenna resonance. Requires detuning values in the `detuning_config` object. |
| `detuning_config` | object | `{"700": -15}` | **(Near-Field)** Maps frequencies (MHz) to detuning offsets. E.g., `{"700": -15}` means the 700 MHz source is shifted down 15 MHz to compensate for body loading. |

| `sapd_mesh_slicing_side_length_mm` | number | `100.0` | Side length in mm for the mesh slicing box around the peak SAR location for faster SAPD calculation. |
| `sapd_slicing_side_length_mm` | number | `100.0` | Side length in mm for the H5 data slicing box around the peak SAR location to optimize extraction speed. |

### Overall Field Sensor Configuration (`overall_field_sensor`)

This object controls the overall field sensor that records E-field and H-field data during the simulation. By default, Sim4Life uses its built-in defaults. Configuring this explicitly allows you to control exactly which fields are recorded.

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `overall_field_sensor.enabled` | boolean | `true` | If `false`, skips explicit sensor configuration (uses Sim4Life defaults). |
| `overall_field_sensor.record_e_field` | boolean | `true` | If `true`, records the Electric field (E). Required for SAR extraction. |
| `overall_field_sensor.record_h_field` | boolean | `false` | If `true`, records the Magnetic field (H). May significantly increase output file size. |
| `overall_field_sensor.recording_domain` | string | `"frequency"` | Recording domain. Options: `"frequency"` (recommended for most cases), `"time"`, or `"both"`. |
| `overall_field_sensor.on_the_fly_dft` | boolean | `true` | If `true`, performs DFT during simulation (memory-efficient). Recommended for frequency domain. |

**Example: Record only E-field in frequency domain (default, smallest output)**
```json
"simulation_parameters": {
    "overall_field_sensor": {
        "enabled": true,
        "record_e_field": true,
        "record_h_field": false,
        "recording_domain": "frequency"
    }
}
```

**Example: Record both E and H fields (needed for Poynting vector / SAPD)**
```json
"simulation_parameters": {
    "overall_field_sensor": {
        "enabled": true,
        "record_e_field": true,
        "record_h_field": true,
        "recording_domain": "frequency"
    }
}
```

!!! note "Multi-sine simulations"
    For multi-sine far-field simulations (e.g., `"700+2450"`), both E and H fields are **always** recorded regardless of this config. This is required for SAPD extraction with combined fields.

<br>

## **5. Gridding Parameters** (`gridding_parameters`)

These settings define the spatial discretization of the simulation domain.

| Parameter | Type | Example Value | Description |
| :--- | :--- | :--- | :--- |
| `global_gridding.grid_mode` | string | `"automatic"` | The global gridding strategy. Can be `"automatic"` or `"manual"`. |
| `global_gridding.refinement` | string | `"AutoRefinementDefault"` | For automatic gridding, this sets the refinement level. Options: `"VeryFine"`, `"Fine"`, `"Default"`, `"Coarse"`, `"VeryCoarse"`. |
| `global_gridding.manual_fallback_max_step_mm` | number | `3.0` | For manual gridding, this is the maximum grid step size in millimeters used as a fallback. **Note**: GOLIAT enforces a hard limit of 3.0 mm for manual grids. Values larger than 3.0 mm will cause an error. See [Troubleshooting](../troubleshooting.md#manual-grid-size-exceeds-3-mm-limit) for details. |
| `global_gridding_per_frequency` | object | `{"700": 3.0}` | **(Far-Field)** A mapping of frequency (in MHz) to a specific manual grid step size in millimeters. This allows for finer grids at higher frequencies. **Note**: All values must be ≤ 3.0 mm (GOLIAT enforces a hard limit). |
| `padding.padding_mode` | string | `"automatic"` | Defines how padding is applied around the simulation domain. Can be `"automatic"` or `"manual"`. |
| `padding.manual_bottom_padding_mm` | array | `[0, 0, 0]` | For manual padding, the [x, y, z] padding in millimeters at the bottom (minimum corner) of the domain. Positive values expand the domain **away** from the computational region (i.e., in the negative x, y, z directions). |
| `padding.manual_top_padding_mm` | array | `[0, 0, 0]` | For manual padding, the [x, y, z] padding in millimeters at the top (maximum corner) of the domain. Positive values expand the domain **away** from the computational region (i.e., in the positive x, y, z directions). |
| `phantom_bbox_reduction.auto_reduce_bbox` | boolean | `false` | **(Far-Field)** If `true`, enables automatic phantom height reduction for frequencies above `reference_frequency_mhz`. |
| `phantom_bbox_reduction.reference_frequency_mhz` | number | `5800` | **(Far-Field)** The reference frequency where full-body simulation fits in memory. For higher frequencies, height is reduced by `(reference/current)³`. |
| `phantom_bbox_reduction.height_limit_per_frequency_mm` | object | `{}` | **(Far-Field)** Manual height limits per frequency in mm (e.g., `{"10000": 400}`). Overrides automatic calculation. |
| `phantom_bbox_reduction.use_symmetry_reduction` | boolean | `false` | **(Far-Field)** If `true`, cuts the phantom bounding box at x=0 to exploit left-right symmetry. Reduces cell count by ~50%. **Not compatible with auto-induced exposure** (you'd miss half the body's skin surface). |

<br>

## **6. Solver and Miscellaneous Settings**

| Parameter | Type | Example Value | Description |
| :--- | :--- | :--- | :--- |
| `solver_settings.kernel` | string | `"Acceleware"` | The solver kernel to use. `"Software"` (CPU), `"Acceleware"` (GPU, required for near-field due to SIBC support), or `"CUDA"` (GPU). |
| `solver_settings.boundary_conditions.type` | string | `"UpmlCpml"` | The type of Perfectly Matched Layer (PML) boundary conditions. |
| `solver_settings.boundary_conditions.strength` | string | `"Medium"` | The strength of the PML boundary conditions. Options: `"Weak"`, `"Medium"`, `"Strong"`. |
| `manual_isolve` | boolean | `true` | If `true`, runs the `iSolve.exe` solver directly. This is the recommended setting to avoid a known bug with the Ares scheduler. |
| `save_retry_count` | number | `4` | The number of times to retry saving a project file if Sim4Life randomly errors out. Each retry attempt logs a warning. If all attempts fail, the error is raised. |
| `export_material_properties` | boolean | `false` | **(Advanced)** If `true`, the framework will extract and save material properties from the simulation to a `.pkl` file. |
| `line_profiling` | object | See below | **(Advanced)** Enables detailed line-by-line code profiling for specific functions to debug performance. |

**Example: Line Profiling**
```json
"line_profiling": {
  "enabled": true,
  "subtasks": {
    "setup_simulation": ["goliat.setups.base_setup.BaseSetup._finalize_setup"]
  }
}
```

---

## **7. Far-Field Specifics** (`far_field_config.json`)

These settings are unique to far-field (environmental exposure) studies.

| Parameter | Type | Example Value | Description |
| :--- | :--- | :--- | :--- |
| `frequencies_mhz` | array | `[450, 700, 900]` | An array of frequencies in MHz to simulate. Each frequency generates a separate `.smash` project file. For multi-sine excitation (multiple frequencies in one simulation), use `"700+2450"` format, e.g., `["700+2450", 5800]`. See the [technical docs](../technical/multi_sine_excitation_analysis.md) for details. |
| `far_field_setup.type` | string | `"environmental"` | The far-field scenario type. Currently, only `"environmental"` (plane waves) is fully implemented. |
| `far_field_setup.environmental.incident_directions` | array | `["x_pos", "y_neg"]` | A list of plane wave incident directions. Supported values are single-axis directions: `"x_pos"`, `"x_neg"`, `"y_pos"`, `"y_neg"`, `"z_pos"`, `"z_neg"`. **Mutually exclusive with `spherical_tessellation`.** |
| `far_field_setup.environmental.spherical_tessellation` | object | See below | Alternative to `incident_directions`. Generates arbitrary incident wave directions using either explicit angle lists or divisions. Supports two modes: **Explicit lists** (`theta_values`, `phi_values`) for precise control, or **Divisions** (`theta_divisions`, `phi_divisions`) for auto-generation. Explicit lists take precedence when both are provided. Direction names use `"theta_phi"` format in degrees (e.g., `"90_180"`). |
| `far_field_setup.environmental.spherical_tessellation.theta_values` | array | `[90]` | Explicit list of theta angles in degrees. Theta is the polar angle from +z axis (0° = `z_pos`, 90° = equator, 180° = `z_neg`). |
| `far_field_setup.environmental.spherical_tessellation.phi_values` | array | `[135, 165, 195, 225]` | Explicit list of phi angles in degrees. Phi is the azimuthal angle defining wave propagation direction (phi=180° = wave travels toward -x, coming from +x side like `x_neg`). |
| `far_field_setup.environmental.spherical_tessellation.theta_divisions` | number | `2` | Number of divisions for theta (0°-180°). Generates `theta_divisions + 1` values including endpoints. Ignored if `theta_values` is provided. |
| `far_field_setup.environmental.spherical_tessellation.phi_divisions` | number | `4` | Number of divisions for phi (0°-360°, exclusive of 360°). Ignored if `phi_values` is provided. |
| `far_field_setup.environmental.polarizations` | array | `["theta", "phi"]` | A list of polarizations to simulate for each incident direction. `"theta"` corresponds to vertical polarization and `"phi"` to horizontal. |
| `power_balance.input_method` | string | `"bounding_box"` | Method for computing input power in far-field power balance. `"bounding_box"` uses simulation domain cross-section (default, gives ~100% balance). `"phantom_cross_section"` uses pre-computed phantom projected area (physically meaningful but gives >100% balance). See [power normalization](../technical/power_normalization_philosophy.md) for details. |

### Auto-induced exposure (`auto_induced`)

Auto-induced exposure simulates the worst-case scenario where a MaMIMO base station focuses its beams onto a human through beamforming. After all environmental simulations complete for each (phantom, frequency) pair, GOLIAT can optionally combine the results with optimal phase weights to find the worst-case SAPD.

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `auto_induced.enabled` | boolean | `false` | If `true`, runs auto-induced analysis after environmental simulations complete for each (phantom, freq) pair. Requires all `_Output.h5` files to exist (can use files from previous runs even if `do_run: false`). |
| `auto_induced.top_n` | number | `10` | Number of candidate focus points to evaluate. The algorithm finds the top N candidates, combines fields for each, and reports the worst-case SAPD. |
| `auto_induced.cube_size_mm` | number | `50` | Side length in mm of the extraction cube around each focus point. Only fields within this cube are combined, dramatically reducing computation time and output file size. |
| `auto_induced.search_metric` | string | `"E_magnitude"` | **[Legacy mode only]** Metric used for worst-case focus search in skin-based mode. Options: `"E_magnitude"`, `"E_z_magnitude"`, `"poynting_z"`. |
| `auto_induced.save_intermediate_files` | boolean | `false` | If `true`, saves `.smash` project files after SAPD extraction for debugging. |
| `auto_induced.use_xy_diagonal_for_sim_time` | boolean | `false` | If `true`, calculates simulation time based on XY-plane diagonal only (ignoring Z). Useful when phantom height is reduced via `phantom_bbox_reduction`, since the Z-extent no longer reflects the actual simulation domain size. |
| `auto_induced.search.mode` | string | `"air"` | Search mode for focus points. `"air"` (recommended, physically correct) searches in air near body surface. `"skin"` (legacy) searches directly on skin voxels. |
| `auto_induced.search.n_samples` | number | `10000` | **[Air mode only]** Number of air points to randomly sample and score. Can be an integer (exact count) or a float < 1 (fraction of valid points, e.g., `0.01` = 1%). |
| `auto_induced.search.shell_size_mm` | number | `10.0` | **[Air mode only]** Maximum distance from skin surface for a valid air focus point. Smaller values keep focus points closer to the body. |
| `auto_induced.search.selection_percentile` | number | `95.0` | **[Air mode only]** Percentile threshold for candidate selection. Only points scoring above this percentile are considered. Default `95.0` = top 5%. |
| `auto_induced.search.min_candidate_distance_mm` | number | `50.0` | **[Air mode only]** Minimum distance in mm between selected candidates. Ensures spatial diversity across the body surface. |
| `auto_induced.search.random_seed` | number/null | `42` | **[Air mode only]** Random seed for sampling reproducibility. Set to `null` for non-reproducible random sampling. |
| `auto_induced.search.low_memory_mode` | boolean/null | `null` | **[Air mode only]** Memory mode for field cache. `true` = streaming mode (reads from disk, slower but works on low-RAM machines). `false` = in-memory mode (fast but needs lots of RAM). `null` (default) = auto-detect based on available RAM. |

**Example: Enable auto-induced exposure with air-based search**
```json
{
    "auto_induced": {
        "enabled": true,
        "top_n": 10,
        "cube_size_mm": 50,
        "search": {
            "mode": "air",
            "n_samples": 10000,
            "shell_size_mm": 10.0,
            "selection_percentile": 95.0,
            "min_candidate_distance_mm": 50.0,
            "random_seed": 42,
            "low_memory_mode": null
        }
    }
}
```

**Example: Legacy skin-based search (for comparison)**
```json
{
    "auto_induced": {
        "enabled": true,
        "top_n": 10,
        "cube_size_mm": 100,
        "search_metric": "E_z_magnitude",
        "search": {
            "mode": "skin"
        }
    }
}
```

**Important notes:**

- **Physical correctness**: The `"air"` mode models how MaMIMO beamforming actually works (beam focused in air, illuminating body). The `"skin"` mode is legacy and physically incorrect.
- **Symmetry reduction incompatibility**: Do not use `phantom_bbox_reduction.use_symmetry_reduction: true` with auto-induced exposure. Symmetry reduction cuts the bounding box at x=0, keeping only one half of the body - you'd miss half the skin surface and cannot find the true worst-case focus point.
- **Results location**: Auto-induced results are saved to `results/far_field/{phantom}/{freq}MHz/auto_induced/auto_induced_summary.json`.
- **Caching**: The analysis is skipped if the summary file exists and is newer than all `_Output.h5` files.
- **Performance**: Air-based search with `n_samples=100` typically takes 5-10 minutes per (phantom, freq) pair on a modern CPU.

<br>

## **8. Near-Field Specifics** (`near_field_config.json`)

These settings are unique to near-field (device exposure) studies.

### Antenna configuration (`antenna_config`)
This object defines all antenna-specific information, with a separate entry for each frequency.

| Parameter | Type | Example Value | Description |
| :--- | :--- | :--- | :--- |
| `antenna_config.{freq}.model_type` | string | `"PIFA"` | The type of antenna model, used to select specific setup logic. Options: `"PIFA"`, `"IFA"`. |
| `antenna_config.{freq}.source_name` | string | `"Lines 1"` | The name of the source entity within the antenna's CAD model. |
| `antenna_config.{freq}.materials` | object | `{ "Extrude 1": "Copper", ...}` | Maps component names in the antenna's CAD model to Sim4Life material names. |
| `antenna_config.{freq}.gridding` | object | `{ "automatic": [...], "manual": {...} }` | Defines gridding strategies (automatic or manual with specific step sizes) for different parts of the antenna model. |
| `antenna_config.{freq}.gridding.subgridding` | object | `{ "components": [...], ...}` | **(Optional)** Enables subgridding for a list of components, which overrides any manual gridding settings for those components. This is useful for finely detailed parts that require a much higher resolution than the rest of the model. See below for subgridding configuration details. |

### Placement scenarios (`placement_scenarios`)
This object defines the different device placements to be simulated.

| Parameter | Type | Example Value | Description |
| :--- | :--- | :--- | :--- |
| `placement_scenarios.{name}.positions` | object | `{ "center": [0,0,0], ...}` | A set of named relative positions (as [x, y, z] offsets) for the placement scenario. |
| `placement_scenarios.{name}.orientations` | object | `{ "vertical": [], ...}` | A set of named orientations to be applied at each position. Each orientation is a list of rotation steps. See below for an alternative dictionary format for `by_cheek` phantom rotation. |
| `placement_scenarios.{name}.bounding_box` | string | `"default"` | Determines which part of the phantom to include in the simulation bounding box. Options: `"default"`, `"head"`, `"trunk"`, `"whole_body"`. The `"default"` option intelligently chooses "head" for eye/cheek placements and "trunk" for belly placements. |
| `placement_scenarios.{name}.phantom_reference` | string | `"tragus"` | **(Optional)** Specifies an anatomical reference point used for placement calculations. The reference point coordinates are defined in `phantom_definitions.{phantom_name}`. Common values: `"nasion"` (for `front_of_eyes`), `"tragus"` (for `by_cheek`), `"belly_button"` (for `by_belly`). If not specified, the default placement center is used. |
| `placement_scenarios.{name}.antenna_reference` | object | `{ "distance_from_top": 10 }` | **(Optional)** Defines antenna positioning relative to a reference point on the antenna model. |

<br>

**Alternative orientation format for `by_cheek` phantom rotation**

For the `by_cheek` scenario, an alternative dictionary format can be used to enable automatic phantom rotation towards the phone. This is useful for precise placement based on contact.

```json
"orientations": {
  "cheek_base": {
    "rotate_phantom_to_cheek": true,
    "angle_offset_deg": 0
  }
}
```

- **`rotate_phantom_to_cheek`**: (boolean) If `true`, the phantom rotates on its Z-axis to touch the phone.
- **`angle_offset_deg`**: (number) An additional angle in degrees to rotate the phantom away from the phone after contact is detected.

**Subgridding configuration**

Subgridding allows specific antenna components to use a finer grid resolution than the global grid. This is configured in the `antenna_config.{freq}.gridding.subgridding` object:

```json
{
  "antenna_config": {
    "700": {
      "gridding": {
        "subgridding": {
          "components": ["component1:Battery", "component1:Patch", "Extrude 1", "component1:ShortingPin"],
          "SubGridMode": "Box",
          "SubGridLevel": "x9",
          "AutoRefinement": "AutoRefinementVeryFine"
        }
      }
    }
  }
}
```

- **`components`**: (array of strings) List of component names to apply subgridding to. These components will use the subgrid resolution instead of the global or manual grid settings.
- **`SubGridMode`**: (string) The subgrid mode, typically `"Box"`.
- **`SubGridLevel`**: (string) The subgrid level multiplier relative to the global grid. Common values: `"x9"` (9x finer), `"x3"` (3x finer). Higher values provide finer resolution but increase computation time.
- **`AutoRefinement`**: (string) The refinement level for subgridded components. Options: `"AutoRefinementVeryFine"`, `"AutoRefinementFine"`, `"AutoRefinementDefault"`.

Subgridding overrides any manual gridding settings for the specified components. Components not listed in the `components` array use the global gridding strategy (automatic or manual) as configured.

### Phantom definitions (`phantom_definitions`)
This object contains phantom-specific settings, such as which placements to run and the separation distances.

| Parameter | Type | Example Value | Description |
| :--- | :--- | :--- | :--- |
| `phantom_definitions.{name}.placements` | object | `{ "do_by_cheek": true, ...}` | A set of booleans to enable or disable specific placement scenarios for a given phantom. The key must match a scenario name from `placement_scenarios`. |
| `phantom_definitions.{name}.distance_from_cheek` | number | `8` | The separation distance in millimeters for the "by_cheek" placement. |
| `phantom_definitions.{name}.distance_from_eye` | number | `200` | The separation distance in millimeters for the "front_of_eyes" placement. |
| `phantom_definitions.{name}.distance_from_belly` | number | `100` | The separation distance in millimeters for the "by_belly" placement. |
| `phantom_definitions.{name}.lips` | array | `[0, 122, 31]` | The [x, y, z] coordinates of the center of the lips, used for the 'cheek' placement calculation. |
| `phantom_definitions.{name}.nasion` | array | `[-1, 0, 0]` | **(Optional)** Relative [x, y, z] offset coordinates for the nasion landmark, used as a reference point for `front_of_eyes` placement when `phantom_reference: "nasion"` is specified. These coordinates are offsets from the geometrically calculated eye center (derived from eye entity bounding boxes). The coordinate system: X (inside head to right ear out), Y (out of face), Z (up head and out). |
| `phantom_definitions.{name}.tragus` | array | `[0, 7, -5]` | **(Optional)** Relative [x, y, z] offset coordinates for the tragus landmark, used as a reference point for `by_cheek` placement when `phantom_reference: "tragus"` is specified. These coordinates are offsets from the geometrically calculated ear center (derived from Ear_skin entity bounding box). The coordinate system: X (inside head to right ear out), Y (out of face), Z (up head and out). |
| `phantom_definitions.{name}.belly_button` | array | `[-5, 0, -140]` | **(Optional)** Relative [x, y, z] offset coordinates for the belly button landmark, used as a reference point for `by_belly` placement when `phantom_reference: "belly_button"` is specified. These coordinates are offsets from the geometrically calculated trunk center (derived from trunk bounding box). The coordinate system: X (inside head to right ear out), Y (out of face), Z (up head and out). |

**How reference point coordinates are derived:**

The reference point coordinates (nasion, tragus, belly_button) are relative offsets, not absolute positions. They are calculated as offsets from geometrically derived centers:

- **`nasion`**: Offset from the center of the eye bounding box (calculated from Eye/Cornea entities)
- **`tragus`**: Offset from the center of the ear bounding box (calculated from Ear_skin entity)
- **`belly_button`**: Offset from the center of the trunk bounding box (calculated from Trunk_BBox entity)

These offsets are determined through anatomical landmark identification techniques and are added to the calculated geometric centers during placement. The coordinate system is consistent across all phantoms: X-axis extends from inside the head toward the right ear, Y-axis extends outward from the face, and Z-axis extends upward along the head.

---

## **9. Credentials and Data**

For security and portability, certain information is handled outside the main configuration files.

### oSPARC Credentials
oSPARC API credentials should be stored in a `.env` file in the project root directory.

```
# .env file
OSPARC_API_KEY=your_osparc_api_key
OSPARC_API_SECRET=your_osparc_api_secret
```

### Phantom downloads
Some phantom models require an email address for download, which can also be set in the `.env` file. This should be the email associated with your institution's Sim4Life license.

```
# .env file
DOWNLOAD_EMAIL=your_email@example.com
```

---

## **10. Accessing Configuration in Code**

The `Config` class supports dictionary-style access with dot-notation for nested paths:

```python
# Simple top-level access
sim_params = config["simulation_parameters"] or {}
antenna_config = config["antenna_config"] or {}

# Nested path access
excitation_type = config["simulation_parameters.excitation_type"] or "Harmonic"
gridding_params = config["gridding_parameters"] or {}

# With fallback values
expansion = config["simulation_parameters.freespace_antenna_bbox_expansion_mm"] or [10, 10, 10]
```

**Note**: The `or` operator provides a fallback when a key doesn't exist (returns `None`). This is the standard pythonic pattern.

### Accessing Complex Structures

For accessing nested dictionaries within config values:

```python
# Get a top-level dict, then access nested keys
placement_scenarios = config["placement_scenarios"] or {}
scenario = placement_scenarios.get("by_cheek") if isinstance(placement_scenarios, dict) else None

# Or use dot notation directly
scenario = config["placement_scenarios.by_cheek"]
```

---

This structure makes every aspect of a GOLIAT simulation controllable, reproducible, and easy to manage. For more workflow-oriented information, please see the [User Guide](../user_guide/user_guide.md). For a complete list of all GOLIAT features, see the [Full List of Features](../reference/full_features_list.md).