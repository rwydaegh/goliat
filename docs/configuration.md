# GOLIAT Configuration Guide

GOLIAT uses a hierarchical JSON configuration system to define all aspects of a simulation study. This modular approach allows for flexibility and reproducibility. A study-specific configuration file (e.g., `near_field_config.json`) inherits settings from a `base_config.json` file, allowing you to override only the parameters you need for a specific study.

This guide provides a comprehensive reference for all available configuration parameters, their purpose, and valid values.

## Configuration Hierarchy

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

## **2. Execution Control** (`execution_control`)

This object controls which phases of the workflow are executed. This is useful for re-running specific parts of a study, such as only extracting results from an already completed simulation.

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `do_setup` | boolean | `true` | If `true`, the simulation scene will be built (phantoms loaded, materials assigned, etc.). |
| `do_run` | boolean | `true` | If `true`, the simulation solver will be executed. |
| `do_extract` | boolean | `true` | If `true`, the results will be extracted from the simulation output and processed. |
| `only_write_input_file` | boolean | `false` | If `true`, the `run` phase will only generate the solver input file (`.h5`) and then stop, without actually running the simulation. This is useful for debugging the setup or for preparing files for a manual cloud submission. |
| `batch_run` | boolean | `false` | If `true`, enables the oSPARC batch submission workflow. This is an advanced feature for running many simulations in parallel on the cloud. |
| `auto_cleanup_previous_results` | array | `[]` | A list of file types to automatically delete **after** a simulation's results have been successfully extracted. This helps to preserve disk space in serial workflows. Valid values are: `"output"` (`*_Output.h5`), `"input"` (`*_Input.h5`), and `"smash"` (`*.smash`). **Warning**: This feature is incompatible with parallel or batch runs and should only be used when `do_setup`, `do_run`, and `do_extract` are all `true`. |

The `do_setup` flag directly controls the project file (`.smash`) handling. Its behavior is summarized below:

| `do_setup` Value | File Exists? | Action |
| :--- | :--- | :--- |
| `true` | Yes | **Delete and Override** with a new project. |
| `true` | No | Create a new project. |
| `false` | Yes | **Open and Use** the existing project. |
| `false` | No | **Error** and terminate the program. |

**Example: Extraction-Only Workflow**
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

## **3. Simulation Parameters** (`simulation_parameters`)

These settings control the core behavior of the FDTD solver.

| Parameter | Type | Example Value | Description |
| :--- | :--- | :--- | :--- |
| `global_auto_termination` | string | `"GlobalAutoTerminationUserDefined"` | The solver's termination criteria. `"GlobalAutoTerminationWeak"` is a common default, while `"GlobalAutoTerminationUserDefined"` allows for a custom convergence level. |
| `convergence_level_dB` | number | `-15` | The convergence threshold in decibels (dB) when using user-defined termination. The simulation stops when the energy in the system decays below this level. |
| `simulation_time_multiplier` | number | `3.5` | A multiplier used to determine the total simulation time. The time is calculated as the duration it takes for a wave to traverse the simulation bounding box diagonal, multiplied by this value. |
| `number_of_point_sensors` | number | `8` | The number of point sensors to place at the corners of the simulation bounding box. These sensors monitor the electric field over time. |
| `point_source_order` | array | `["lower_left_bottom", ...]` | Defines the specific order and location of the point sensors at the 8 corners of the bounding box. |
| `excitation_type` | string | `"Harmonic"` | The type of excitation source. `"Harmonic"` is used for single-frequency simulations (standard for SAR). `"Gaussian"` is used for a frequency sweep, typically for antenna characterization in free-space. |
| `bandwidth_mhz` | number | `50.0` | The bandwidth in MHz for a Gaussian excitation. |
| `bbox_padding_mm` | number | `50` | **(Far-Field)** Padding in millimeters to add around the phantom's bounding box to define the simulation domain. |
| `freespace_antenna_bbox_expansion_mm` | array | `[20, 20, 20]` | **(Near-Field)** Padding in [x, y, z] millimeters to add around the antenna for free-space simulations. |

<br>

## **4. Gridding Parameters** (`gridding_parameters`)

These settings define the spatial discretization of the simulation domain.

| Parameter | Type | Example Value | Description |
| :--- | :--- | :--- | :--- |
| `global_gridding.grid_mode` | string | `"automatic"` | The global gridding strategy. Can be `"automatic"` or `"manual"`. |
| `global_gridding.refinement` | string | `"AutoRefinementDefault"` | For automatic gridding, this sets the refinement level. Options: `"VeryFine"`, `"Fine"`, `"Default"`, `"Coarse"`, `"VeryCoarse"`. |
| `global_gridding.manual_fallback_max_step_mm` | number | `5.0` | For manual gridding, this is the maximum grid step size in millimeters used as a fallback. |
| `global_gridding_per_frequency` | object | `{"700": 3.0}` | **(Far-Field)** A mapping of frequency (in MHz) to a specific manual grid step size in millimeters. This allows for finer grids at higher frequencies. |
| `padding.padding_mode` | string | `"automatic"` | Defines how padding is applied around the simulation domain. Can be `"automatic"` or `"manual"`. |
| `padding.manual_bottom_padding_mm` | array | `[0, 0, 0]` | For manual padding, the [x, y, z] padding in millimeters at the bottom of the domain. |
| `padding.manual_top_padding_mm` | array | `[0, 0, 0]` | For manual padding, the [x, y, z] padding in millimeters at the top of the domain. |

<br>

## **5. Solver and Miscellaneous Settings**

| Parameter | Type | Example Value | Description |
| :--- | :--- | :--- | :--- |
| `solver_settings.kernel` | string | `"Acceleware"` | The solver kernel to use. `"Software"` (CPU), `"Acceleware"` (GPU, required for near-field due to SIBC support), or `"CUDA"` (GPU). |
| `solver_settings.boundary_conditions.type` | string | `"UpmlCpml"` | The type of Perfectly Matched Layer (PML) boundary conditions. |
| `solver_settings.boundary_conditions.strength` | string | `"Medium"` | The strength of the PML boundary conditions. Options: `"Weak"`, `"Medium"`, `"Strong"`. |
| `manual_isolve` | boolean | `true` | If `true`, runs the `iSolve.exe` solver directly. This is the recommended setting to avoid a known bug with the Ares scheduler. |
| `export_material_properties` | boolean | `false` | **(Advanced)** If `true`, the framework will extract and save material properties from the simulation to a `.pkl` file. |
| `line_profiling` | object | See below | **(Advanced)** Enables detailed line-by-line code profiling for specific functions to debug performance. |

**Example: Line Profiling**
```json
"line_profiling": {
  "enabled": true,
  "subtasks": {
    "setup_simulation": ["src.setups.base_setup.BaseSetup._finalize_setup"]
  }
}
```

---

## **6. Far-Field Specifics** (`far_field_config.json`)

These settings are unique to far-field (environmental exposure) studies.

| Parameter | Type | Example Value | Description |
| :--- | :--- | :--- | :--- |
| `frequencies_mhz` | array | `[450, 700, 900]` | An array of frequencies in MHz to simulate. Each frequency will generate a separate `.smash` project file containing simulations for all directions and polarizations. |
| `far_field_setup.type` | string | `"environmental"` | The far-field scenario type. Currently, only `"environmental"` (plane waves) is fully implemented. |
| `far_field_setup.environmental.incident_directions` | array | `["x_pos", "y_neg"]` | A list of plane wave incident directions. Supported values are single-axis directions: `"x_pos"`, `"x_neg"`, `"y_pos"`, `"y_neg"`, `"z_pos"`, `"z_neg"`. |
| `far_field_setup.environmental.polarizations` | array | `["theta", "phi"]` | A list of polarizations to simulate for each incident direction. `"theta"` corresponds to vertical polarization and `"phi"` to horizontal. |

<br>

## **7. Near-Field Specifics** (`near_field_config.json`)

These settings are unique to near-field (device exposure) studies.

### Antenna Configuration (`antenna_config`)
This object defines all antenna-specific information, with a separate entry for each frequency.

| Parameter | Type | Example Value | Description |
| :--- | :--- | :--- | :--- |
| `antenna_config.{freq}.model_type` | string | `"PIFA"` | The type of antenna model, used to select specific setup logic. Options: `"PIFA"`, `"IFA"`. |
| `antenna_config.{freq}.source_name` | string | `"Lines 1"` | The name of the source entity within the antenna's CAD model. |
| `antenna_config.{freq}.materials` | object | `{ "Extrude 1": "Copper", ...}` | Maps component names in the antenna's CAD model to Sim4Life material names. |
| `antenna_config.{freq}.gridding` | object | `{ "automatic": [...], "manual": {...} }` | Defines gridding strategies (automatic or manual with specific step sizes) for different parts of the antenna model. |
| `antenna_config.{freq}.gridding.subgridding` | object | `{ "components": [...], ...}` | **(Optional)** Enables subgridding for a list of components, which overrides any manual gridding settings for those components. This is useful for finely detailed parts that require a much higher resolution than the rest of the model. |

### Placement Scenarios (`placement_scenarios`)
This object defines the different device placements to be simulated.

| Parameter | Type | Example Value | Description |
| :--- | :--- | :--- | :--- |
| `placement_scenarios.{name}.positions` | object | `{ "center": [0,0,0], ...}` | A set of named relative positions (as [x, y, z] offsets) for the placement scenario. |
| `placement_scenarios.{name}.orientations` | object | `{ "vertical": [], ...}` | A set of named orientations to be applied at each position. Each orientation is a list of rotation steps. |
| `placement_scenarios.{name}.bounding_box` | string | `"default"` | Determines which part of the phantom to include in the simulation bounding box. Options: `"default"`, `"head"`, `"trunk"`, `"whole_body"`. The `"default"` option intelligently chooses "head" for eye/cheek placements and "trunk" for belly placements. |

### Phantom Definitions (`phantom_definitions`)
This object contains phantom-specific settings, such as which placements to run and the separation distances.

| Parameter | Type | Example Value | Description |
| :--- | :--- | :--- | :--- |
| `phantom_definitions.{name}.placements` | object | `{ "do_by_cheek": true, ...}` | A set of booleans to enable or disable specific placement scenarios for a given phantom. The key must match a scenario name from `placement_scenarios`. |
| `phantom_definitions.{name}.distance_from_cheek` | number | `8` | The separation distance in millimeters for the "by_cheek" placement. |
| `phantom_definitions.{name}.distance_from_eye` | number | `200` | The separation distance in millimeters for the "front_of_eyes" placement. |
| `phantom_definitions.{name}.distance_from_belly` | number | `100` | The separation distance in millimeters for the "by_belly" placement. |
| `phantom_definitions.{name}.lips` | array | `[0, 122, 31]` | The [x, y, z] coordinates of the center of the lips, used for the 'cheek' placement calculation. |

---

## **8. Credentials and Data**

For security and portability, certain information is handled outside the main configuration files.

### oSPARC Credentials
oSPARC API credentials should be stored in a `.env` file in the project root directory.

```
# .env file
OSPARC_API_KEY=your_osparc_api_key
OSPARC_API_SECRET=your_osparc_api_secret
```

### Phantom Downloads
Some phantom models require an email address for download, which can also be set in the `.env` file. This should be the email associated with your institution's Sim4Life license.

```
# .env file
DOWNLOAD_EMAIL=your_email@example.com
```

This comprehensive structure ensures that every aspect of a GOLIAT simulation is controllable, reproducible, and easy to manage. For more workflow-oriented information, please see the [User Guide](user_guide.md).