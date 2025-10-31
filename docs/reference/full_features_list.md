# Full List of Features

A list of all user-facing features in GOLIAT, organized by category.

This document provides a complete reference of every feature available in GOLIAT. Each feature is listed with a brief description. For detailed information on how to use these features, see the [User Guide](../user_guide/user_guide.md), [Configuration Guide](../developer_guide/configuration.md), and [Advanced Features Guide](../developer_guide/advanced_features.md).

## Installation and setup

- Initialize GOLIAT environment using `goliat init` command
- Automatically install Python dependencies from `requirements.txt`
- Install GOLIAT package in editable mode (code changes reflect immediately)
- Verify Sim4Life Python interpreter is being used
- Prepare data files (phantoms, antennas) during initialization
- Automatic prompt for installation when running `goliat study` if not initialized
- Check setup status with `goliat status` command
- Show GOLIAT version information with `goliat version` command
- Configure Sim4Life Python path via `.bashrc` file
- Support for Sim4Life bundled Python distribution (no separate Python installation required)

## Configuration system

- Hierarchical JSON configuration with inheritance from `base_config.json`
- Study-specific configs extend base config (e.g., `near_field_config.json`)
- Override only specific parameters without duplicating settings
- Validate configuration files with `goliat validate` command
- Automatic configuration merging with child configs overriding parent values
- Support for nested configuration paths using dot notation (e.g., `simulation_parameters.global_auto_termination`)
- Config inheritance supports multiple levels of nesting

## Study types

### Near-field studies

- Simulate device exposure scenarios (e.g., mobile phones close to body)
- Support for multiple antenna types (PIFA, IFA)
- Configure antenna placement scenarios (by_cheek, front_of_eyes, by_belly, on_wrist, etc.)
- Automatic antenna positioning relative to phantom anatomical landmarks
- Support for free-space antenna simulations (without phantom body)
- Calculate localized SAR values (head SAR, trunk SAR)
- Extract peak spatial-average SAR (psSAR10g) in sensitive tissues
- Scene alignment optimization for by_cheek placements (aligns entire scene with phone orientation)
- Phantom rotation towards phone for precise by_cheek contact (automatic angle detection)
- Configurable phantom rotation angle offset (additional rotation after contact detection)
- Binary search algorithm for finding exact touching angle (0-30 degrees, 0.5 degree precision)

### Far-field studies

- Simulate whole-body environmental exposure (plane waves)
- Configure incident directions (x_pos, x_neg, y_pos, y_neg, z_pos, z_neg)
- Support for multiple polarizations (theta, phi) per direction
- Calculate whole-body average SAR
- Aggregate results over multiple directions and polarizations
- Create transfer functions between E-field values and absorption values
- Support for environmental exposure scenarios (currently implemented)
- Placeholder for auto-induced mode (future implementation)

## Phantom management

- Automatic phantom model download on first use
- Support for multiple phantoms (thelonious, eartha, duke_posable, etc.)
- Configure phantom-specific settings (distances, placements, anatomical landmarks)
- Enable/disable specific placements per phantom
- Define separation distances per placement type (cheek, eye, belly)
- Configure anatomical reference points (nasion, tragus, belly_button)
- Relative offset coordinates for anatomical landmarks
- Automatic geometric center calculation for eye, ear, and trunk bounding boxes
- Phantom licensing handled through email prompt or environment variable
- Manual phantom download option for offline use

## Antenna configuration

- Frequency-specific antenna configuration
- Define antenna model type (PIFA, IFA)
- Configure antenna source name (e.g., "Lines 1")
- Map antenna CAD components to Sim4Life materials
- Configure gridding strategies per antenna component
- Support for automatic gridding refinement levels (VeryFine, Fine, Default, Coarse, VeryCoarse)
- Manual gridding with millimeter step sizes
- Subgridding support for specific antenna components
- Subgridding level multipliers (x9, x3, etc.)
- Subgridding auto-refinement levels (VeryFine, Fine, Default)
- Subgridding overrides manual gridding for specified components

## Placement scenarios

- Define multiple placement scenarios per study
- Configure positions as [x, y, z] offsets
- Define orientations as rotation sequences
- Support for dictionary format orientations (for phantom rotation)
- Configure bounding box selection (default, head, trunk, whole_body)
- Specify phantom reference points for placement calculations
- Configure antenna reference points (e.g., distance_from_top)
- Automatic default bounding box selection (head for eye/cheek, trunk for belly)
- Multiple orientations per position (e.g., base, up, rotate_z)

## Simulation parameters

- Configure solver termination criteria (GlobalAutoTerminationWeak, GlobalAutoTerminationUserDefined)
- Set custom convergence level in decibels (dB)
- Configure simulation time multiplier
- Set number of point sensors (default: 8)
- Configure point sensor placement order (8 corners of bounding box)
- Select excitation type (Harmonic for single frequency, Gaussian for frequency sweep)
- Configure Gaussian excitation bandwidth in MHz
- Set bounding box padding for far-field simulations (millimeters)
- Configure free-space antenna bounding box expansion [x, y, z] in millimeters

## Gridding configuration

- Global gridding mode selection (automatic or manual)
- Automatic gridding refinement levels (VeryFine, Fine, Default, Coarse, VeryCoarse)
- Manual gridding with maximum step size fallback (millimeters)
- Per-frequency manual grid step sizes for far-field studies
- Padding mode selection (automatic or manual)
- Manual padding configuration for bottom and top of domain [x, y, z]
- Intelligent gridding around critical areas (finer cells near antenna/phantom surface)
- Automatic gridding optimization for computational efficiency

## Solver configuration

- Select solver kernel (Software/CPU, Acceleware/GPU, CUDA/GPU)
- Configure boundary conditions type (UpmlCpml)
- Set boundary condition strength (Weak, Medium, Strong)
- Enable manual iSolve execution (bypasses Ares scheduler bug)
- Export material properties to pickle file (advanced option)
- Enable line-by-line code profiling for specific functions
- Configure profiling targets (subtasks and function names)

## Execution control

- Enable/disable setup phase (`do_setup`)
- Enable/disable run phase (`do_run`)
- Enable/disable extract phase (`do_extract`)
- Write input file only without running solver (`only_write_input_file`)
- Enable batch run mode for oSPARC cloud (`batch_run`)
- Automatic cleanup of previous results (`auto_cleanup_previous_results`)
- Selective cleanup options: output files (*_Output.h5), input files (*_Input.h5), project files (*.smash)
- Cleanup incompatible with parallel or batch runs (serial workflows only)
- Automatic project file handling (create new or open existing based on do_setup flag)
- Bypass caching system with `--no-cache` command-line flag

## Project management

- Automatic Sim4Life project file (`.smash`) creation
- Project file validation (checks for file locks and HDF5 structure)
- File lock detection and handling (`.s4l_lock` files)
- Automatic project file cleanup on corruption detection
- Structured results directory organization (`results/{study_type}/{phantom}/{frequency}MHz/{scenario}/`)
- Unique project file per simulation scenario
- Project isolation for reliability

## Verify and resume (caching system)

- Configuration hashing (SHA256) for simulation fingerprinting
- Surgical configuration creation (single simulation parameters only)
- Metadata validation (config.json in results directory)
- Deliverable-first verification approach
- Check for run phase deliverables (*_Output.h5 file)
- Check for extract phase deliverables (sar_results.json, sar_stats_all_tissues.pkl, sar_stats_all_tissues.html)
- Modification timestamp validation (deliverables newer than setup timestamp)
- Automatic phase skipping for completed simulations
- Dynamic status reporting (setup_done, run_done, extract_done flags)
- Metadata update after successful phase completion
- Resilient to interrupted runs or manual file deletions
- Override cache with `--no-cache` flag (deletes existing project and reruns all phases)

## Simulation execution

### Local execution

- Direct invocation of Sim4Life `iSolve.exe` solver
- Real-time solver output logging
- Non-blocking reader thread for solver output capture
- Manual iSolve execution (bypasses Ares scheduler)
- Support for GPU acceleration (Acceleware, CUDA kernels)
- CPU fallback option (Software kernel)
- Power normalization to 1W input for consistency

### Cloud execution (oSPARC)

- Generate solver input files (`.h5`) for cloud submission
- Automatic batch job submission to oSPARC platform
- Job status monitoring (PENDING → RUNNING → SUCCESS)
- Automatic result download upon job completion
- Support for API key authentication via `.env` file
- Retry mechanism for failed submissions (3 automatic retries)
- Logging in dedicated directory (`logs/osparc_submission_logs/`)
- Maximum ~61 parallel jobs (oSPARC platform limit)
- Job cancellation script (`scripts/cancel_all_jobs.py --config <config>`)
- Cancel specific number of recent jobs (`--max-jobs` argument, default: 500)
- Paginated job fetching (50 jobs per page)
- Cancel jobs by status (PENDING, PUBLISHED, WAITING_FOR_CLUSTER, WAITING_FOR_RESOURCES, STARTED, RETRYING)
- Cost monitoring via oSPARC dashboard

## Results extraction

- Extract whole-body average SAR
- Extract localized SAR (head SAR, trunk SAR)
- Extract peak spatial-average SAR over 10g tissue cubes (psSAR10g)
- Extract SAR for specific tissues (eyes, brain, skin, genitals)
- Extract SAR for all tissues defined by Sim4Life
- Calculate power balance (energy conservation check, ideally ~100%)
- Normalize all SAR values to 1W input power
- Generate JSON summary file (`sar_results.json`)
- Generate detailed pickle file (`sar_stats_all_tissues.pkl`)
- Generate HTML report (`sar_results_all_tissues.html`)
- Extract point sensor data (electric field magnitude)
- Generate point sensor plots (`point_sensor_data.png`)
- Extract tissue-specific SAR statistics
- Tissue group aggregation (eyes, head, skin, genitals) via material name mapping

## Analysis and visualization

- Aggregate results across multiple simulations
- Generate CSV files (normalized_results_detailed.csv, normalized_results_summary.csv)
- Create SAR heatmaps by tissue and frequency
- Generate bar charts comparing SAR in different regions
- Create boxplots showing SAR distributions
- Generate line plots for peak spatial-average SAR
- Run analysis with `goliat analyze --config` command
- Strategy-based analysis (NearFieldAnalysisStrategy, FarFieldAnalysisStrategy)
- Per-simulation detailed data export
- Summary statistics by frequency and scenario
- Plot generation in dedicated plots directory

## GUI and monitoring

- Real-time graphical user interface (PySide6-based)
- Overall progress tracking (e.g., 5 out of 108 simulations complete)
- Stage progress tracking (setup, run, extract phases for current simulation)
- Estimated time remaining (ETA) calculation
- Live log display with color-coding
- Status message updates
- Progress bar animations for long-running phases
- Smooth animation system (50ms timer ticks)
- Weighted progress calculation based on phase durations
- Session-based timing configuration files
- Unique session hash for timing file identification
- Progress tracking CSV files (time_remaining, overall_progress)
- Timing data visualization (pie charts, tables)
- System tray integration for background operation
- Responsive GUI (multiprocessing architecture prevents freezing)
- Headless mode option (`use_gui: false` for console-only operation)
- Window title customization via `--title` command-line argument

## Logging system

- Dual logger system (progress and verbose)
- Progress logger for high-level user-facing messages
- Verbose logger for detailed internal messages
- Progress logs saved to `*.progress.log`
- Verbose logs saved to `*.log`
- Automatic log rotation (keeps maximum 15 log file pairs)
- Automatic deletion of oldest logs when limit exceeded
- Color-coded console output
- File handlers and stream handlers for each logger
- Log propagation control (prevents duplicate output)
- Process ID support for unique log identification (`--pid` flag)

## Profiling and timing

- Phase-level timing tracking (setup, run, extract)
- Subtask-level timing tracking
- Session-specific profiling configuration files
- Average time calculation per phase and subtask
- ETA calculation based on historical timing data
- Weighted progress calculation using phase durations
- Timing data persistence in JSON format
- Automatic cleanup of old profiling files (keeps maximum 50 files)
- Timestamp and hash-based file naming for profiling configs
- Real-time elapsed time tracking for current simulation

## Parallel execution

### Local parallel execution

- Split configuration into multiple subsets (`goliat parallel`)
- Configure number of splits (`--num-splits` argument)
- Automatic splitting logic (by phantoms, frequencies, or combinations)
- Launch multiple `goliat study` processes simultaneously
- One GUI per parallel process
- Skip splitting step with existing parallel directory (`--skip-split` flag)
- Results automatically merged in shared `results/` directory
- Support for multi-core CPU utilization
- **Important limitation**: On a single-GPU machine, iSolve run phases execute sequentially (only setup and extract phases benefit from parallelization)
- **For true parallel iSolve execution**: Use oSPARC batch or multiple Windows PCs

### Splitting logic

- 2 splits: Halve phantoms
- 4 splits: One per first 4 phantoms
- 8 splits: Split phantoms, then halve frequencies
- Automatic factor-based splitting for any positive integer

## Cloud computing setup

- Deploy Windows VM with GPU support from cloud providers
- Remote Desktop Protocol (RDP) connection support
- Automated setup script (`setup_and_run.bat`)
- Automatic OpenVPN client installation
- Automatic Python 3.11 installation
- Automatic Git installation
- Automatic Sim4Life download and installation
- VPN configuration file download from Google Drive
- VPN connection automation
- Sim4Life license installer GUI launch
- Automatic GOLIAT repository cloning
- Automatic study launch after setup
- Python script for API-based VM deployment (`deploy_windows_vm.py`)
- Support for multiple cloud providers (TensorDock, AWS, GCP, Azure)
- Cost estimation and monitoring
- Per-second billing support
- Instance stopping when not in use

## Data management

- Automatic phantom model download
- Automatic antenna model download
- Email-based phantom licensing (via DOWNLOAD_EMAIL environment variable)
- Data file preparation during initialization
- Automatic cleanup of old CSV and JSON files in data directory (keeps maximum 50 files)
- Timestamp-based file naming for easy identification
- Automatic disk space management for serial workflows
- Manual file cleanup options
- Manual cleanup script for simulation output files (`scripts/cleanup_results.py`)
- Filter cleanup by study type (near-field, far-field)
- Filter cleanup by frequency (specific frequencies in MHz)
- Interactive confirmation prompt before deletion
- Scan and list files to be deleted before confirmation

## Command-line interface

### Study commands

- `goliat study <config>` - Run a dosimetric assessment study
- `goliat study <config> --no-cache` - Bypass caching and rerun all phases
- `goliat study <config> --title <title>` - Set GUI window title
- `goliat study <config> --pid <pid>` - Set process ID for logging

### Analysis commands

- `goliat analyze --config <config>` - Run analysis for near-field or far-field studies

### Parallel commands

- `goliat parallel <config> --num-splits <n>` - Split config and run studies in parallel
- `goliat parallel <config> --skip-split` - Run from existing parallel directory
- `goliat parallel <config> --no-cache` - Bypass caching in parallel runs

### Utility commands

- `goliat init` - Initialize GOLIAT environment (install dependencies, check setup)
- `goliat status` - Show setup status and environment information
- `goliat validate <config>` - Validate a GOLIAT config file
- `goliat version` - Show GOLIAT version information
- `goliat free-space` or `goliat freespace` - Run free-space validation runs

### Utility scripts

- `python scripts/cancel_all_jobs.py --config <config>` - Cancel all running oSPARC jobs
- `python scripts/cancel_all_jobs.py --config <config> --max-jobs <n>` - Cancel up to N recent oSPARC jobs (default: 500)
- `python scripts/cleanup_results.py --near-field` - Clean up near-field simulation output files
- `python scripts/cleanup_results.py --far-field` - Clean up far-field simulation output files
- `python scripts/cleanup_results.py --near-field --far-field --frequencies <freq1> <freq2>` - Clean up specific frequencies across study types

## File outputs

### Result files

- `sar_results.json` - Normalized SAR values summary
- `sar_stats_all_tissues.pkl` - Detailed tissue-specific SAR data (Python pickle)
- `sar_stats_all_tissues.html` - HTML table of tissue SAR values
- `point_sensor_data.png` - Electric field magnitude plot at monitoring points
- `*_Output.h5` - Simulation output file (HDF5 format)
- `*_Input.h5` - Solver input file (HDF5 format)
- `*.smash` - Sim4Life project file
- `config.json` - Metadata file with configuration hash and completion flags

### Analysis files

- `normalized_results_detailed.csv` - Per-simulation detailed data
- `normalized_results_summary.csv` - Summary statistics by frequency/scenario
- Plots directory with various visualizations (heatmaps, bar charts, boxplots, line plots)

### Log files

- `*.progress.log` - High-level progress logs
- `*.log` - Detailed verbose logs
- `logs/osparc_submission_logs/` - Cloud submission logs

### Data files

- `profiling_config_DD-MM_HH-MM-SS_hash.json` - Session-specific timing configuration
- `time_remaining_DD-MM_HH-MM-SS_hash.csv` - Time remaining tracking data
- `overall_progress_DD-MM_HH-MM-SS_hash.csv` - Overall progress tracking data

## Environment variables

- `OSPARC_API_KEY` - oSPARC cloud API key (in `.env` file)
- `OSPARC_API_SECRET` - oSPARC cloud API secret (in `.env` file)
- `DOWNLOAD_EMAIL` - Email for phantom model downloads (in `.env` file)

## Platform support

- Windows platform support (primary)
- Linux/Cloud execution environment detection
- Automatic platform adaptation for file locking mechanisms
- Sim4Life Web (sim4life.science) compatibility with limitations
- Cross-platform compatibility considerations

## Sim4Life Web limitations

- GUI unavailable in JupyterLab environments
- Most phantoms require licensing through "The Shop"
- `duke_posable` phantom available without additional licensing
- iSolve.exe not present in JupyterLab app environment
- Setup-only runs supported for proof-of-concept

## Error handling and troubleshooting

- Automatic file lock detection and handling
- Project file corruption detection and recovery
- Automatic retry for oSPARC job submissions (3 attempts)
- Detailed error logging for debugging
- Graceful handling of missing dependencies
- Clear error messages for common issues
- File validation before operations

## Performance optimizations

- Scene alignment optimization for by_cheek placements (reduces simulation time)
- Gridding optimization for computational efficiency
- GPU acceleration support (Acceleware, CUDA)
- Automatic cleanup for disk space management
- Efficient caching system to avoid redundant computations
- Parallel execution for multi-core utilization
- Cloud batching for large-scale parallel runs
