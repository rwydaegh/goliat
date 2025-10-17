# Configuration File Documentation

The framework is controlled by a hierarchical JSON configuration system. A study-specific config (e.g., `near_field_config.json`) inherits settings from `base_config.json` and can override them. Below is a comprehensive list of available parameters.

## `base_config.json`

| Key | Type | Example Value | Description |
| --- | --- | --- | --- |
| `extends` | string | `"base_config.json"` | Specifies the parent configuration file to inherit from. |
| `phantoms` | array | `["thelonious"]` | List of virtual human phantoms. |
| `execution_control` | object | `{"do_setup": true, ...}` | Booleans (`do_setup`, `do_run`, `do_extract`) to control the main workflow stages. Allows re-running parts of a study, e.g., only extraction. |
| `execution_control.only_write_input_file` | boolean | `false` | If `true`, the `run` phase will only generate the solver input file and then stop, without actually running the simulation. This is useful for debugging the setup. |
| `simulation_parameters.global_auto_termination` | string | `"GlobalAutoTerminationUserDefined"` | Sets the FDTD solver's termination criteria. |
| `simulation_parameters.convergence_level_dB` | number | `-15` | If the termination is set to user defined, this is the convergence level in dB. |
| `simulation_parameters.simulation_time_multiplier` | number | `5` | To determine the simulation time, we compute the time it takes to traverse the longest diagonal at the speed of light, and multiply by this number. |
| `simulation_parameters.number_of_point_sensors` | number | `8` | Number of point sensors to place at the simulation bounding box corners for field monitoring. |
| `simulation_parameters.point_source_order` | array | `["lower_left_bottom", ...]` | Defines the specific order and location of the point sensors. |
| `gridding_parameters.global_gridding.grid_mode` | string | `"automatic"` or `"manual"` | Sets the global gridding strategy. |
| `gridding_parameters.global_gridding.refinement` | string | `"AutoRefinementDefault"` | The refinement level for automatic gridding, from very fine to coarse. |
| `gridding_parameters.global_gridding.manual_fallback_max_step_mm` | number | `5.0` | Maximum grid step size if manual gridding is used. |
| `gridding_parameters.padding.padding_mode` | string | `"automatic"` or `"manual"` | Defines how padding is applied around the simulation domain. |
| `solver_settings.kernel` | string | `"Software"`, `"Acceleware"` or `"CUDA"` | Software disable the GPU (slow, but useful on a laptop). The latter two determine the GPU's handling of FDTD time updates. When using the GPU, must be `"Acceleware"` for near-field studies due to SIBC limitations in CUDA. |
| `solver_settings.boundary_conditions.type` | string | `"UpmlCpml"` | The type of boundary conditions to use. |
| `solver_settings.boundary_conditions.strength` | string | `"Medium"` | Strength of the boundary conditions. |
| `manual_isolve` | boolean | `true` | If `true`, runs the `iSolve.exe` solver directly instead of through Ares. This should always be true due to a bug with Ares. |
| `download_email` | string | `"example@email.com"` | Email address required by Sim4Life to download phantom models. |
| `export_material_properties` | boolean | `false` | If `true`, the framework will extract and save material properties from the simulation. |
| `line_profiling.enabled` | boolean | `false` | Enables detailed line-by-line profiling for specific functions. |
| `line_profiling.subtasks` | object | `{ "setup_simulation": ["src.setups.base_setup.BaseSetup._finalize_setup"] }` | A map of subtasks to a list of function paths (e.g. `"module.class.method"`) to be profiled. |
| `simulation_parameters.excitation_type` | string | `"Harmonic"` | The excitation type for the simulation. Usually everything is done harmonically at one frequency. Only for free-space antenna simulations is a Guassian frequency-sweep useful to determine resonances. |
| `simulation_parameters.bandwidth_mhz` | number | `50.0` | The bandwidth in MHz for the simulation. Only relevant for Gaussian simulations. |

## Credentials

oSPARC API credentials are no longer stored in configuration files for security reasons. Instead, they are loaded from environment variables:

- `OSPARC_API_KEY`: Your oSPARC API key
- `OSPARC_API_SECRET`: Your oSPARC API secret

These should be set in a `.env` file in the project root.

## `far_field_config.json`

| Key | Type | Example Value | Description |
| --- | --- | --- | --- |
| `study_type` | string | `"far_field"` | For far-field studies, should always be set to far_field. |
| `frequencies_mhz` | array | `[450, 700, ...]` | Frequencies in MHz to simulate. Each one corresponds to one `.smash` file containting the various simulations with each direction/polarization. |
| `far_field_setup.type` | string | `"environmental"` or `"auto_induced"` | Defines the far-field "scenario". Environmental means the phantom is exposed to plane-waves from orthogonal directions. Auto-induced means the incident waves modulate the amplitudes and phases. For now, only far-field is implemented.  |
| `far_field_setup.environmental.incident_directions` | array | `["x_pos", "y_neg", ...]` | List of up to 12 plane wave incident directions. |
| `far_field_setup.environmental.polarizations` | array | `["theta", "phi"]` | Vertical (theta) or horizontal (phi) polarizations for each incident direction, based on spherical coordinates from the center. |
| `simulation_parameters.bbox_padding_mm` | number | `50` | Padding in mm to add to the phantom's bounding box to define the simulation domain. |
| `gridding_parameters.global_gridding_per_frequency` | object | `{"450": 8.021, ...}` | A mapping of frequency to a specific manual grid step size. |

## `near_field_config.json`

| Key | Type | Example Value | Description |
| --- | --- | --- | --- |
| `study_type` | string | `"near_field"` | For near-field *and free-space* studies, should always be set to near_field. To do a free-space study, set the phantom to `freespace`.|
| `simulation_parameters.freespace_antenna_bbox_expansion_mm` | array | `[20, 20, 20]` | Padding for free-space antenna simulations (no phantom). |
| `antenna_config` | object | `{ "700": { ... } }` | A dictionary where each key is a frequency. Contains all antenna-specific information for that frequency. For the GOLIAT project, these should remain unchanged to achieve comparisons with partners. |
| `antenna_config.{freq}.model_type` | string | `"PIFA"` or `"IFA"` | The type of antenna model, used to select specific setup logic. |
| `antenna_config.{freq}.source_name` | string | `"Lines 1"` | The name of the source entity within the antenna's CAD model. |
| `antenna_config.{freq}.materials` | object | `{ "Extrude 1": "Copper", ...}` | Maps component names in the CAD model to Sim4Life material names. |
| `antenna_config.{freq}.gridding` | object | `{ "automatic": [...], "manual": {...} }` | Defines gridding strategies for different parts of the antenna model. |
| `placement_scenarios` | object | `{ "front_of_eyes": { ... } }` | Defines device placements. Each key is a scenario name. These should also remain unchanged for the GOLIAT project as they are determined by the protocol. |
| `placement_scenarios.{name}.positions` | object | `{ "center": [0,0,0], ...}` | A set of relative positions for the placement scenario. |
| `placement_scenarios.{name}.orientations` | object | `{ "vertical": [], ...}` | A set of orientations to be applied at each position. |
| `phantoms.{name}.placements` | object | `{ "do_front_of_eyes": true, ...}` | Booleans to enable or disable specific placement scenarios for a given phantom. |
| `phantoms.{name}.distance_from_eye` | number | `200` | The separation distance in mm for the "front_of_eyes" placement. |
| `phantoms.{name}.distance_from_cheek` | number | `8` | The separation distance in mm for the "by_cheek" placement. |
| `phantoms.{name}.distance_from_belly` | number | `100` | The separation distance in mm for the "by_belly" placement. |
