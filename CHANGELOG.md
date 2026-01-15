# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.4.0] - 2025-01-15

Major release with Sim4Life 9.2 support, air-based auto-induced exposure analysis, SAPD extraction, and far-field optimizations. ~41 commits since v1.3.0.

### New features

#### Sim4Life 9.2 support
Full support for Sim4Life 9.2 alongside existing 8.2 compatibility.

- Version detection module prioritizes 9.2 when both are installed
- `goliat config show` displays current settings and detected version
- `goliat config set-version` interactive picker for switching versions
- Queue-based logging for child process output (fixes stdout issues in S4L 9.2)
- Robust handling for null `FieldValue` returns in S4L 9.2 API
- Note: Blackwell GPUs (RTX 5090, B100) only support CUDA kernel with S4L 9.2.1.19976 (not aXware)

#### Auto-induced air-based focus search
Physically correct MaMIMO beamforming simulation using focus points in air near the body surface.

- Search for beam focus in air shell around body (configurable `shell_size_mm`)
- Hotspot scoring by mean |E_combined|² over nearby skin voxels
- Percentile-based candidate selection (`selection_percentile`)
- Minimum distance constraint for body-wide coverage (`min_candidate_distance_mm`)
- CSV export of proxy scores and proxy-SAPD correlation data
- Legacy skin-based search mode still available (`search.mode: "skin"`)

#### SAPD extraction
Automated Surface Absorbed Power Density calculation on skin surfaces.

- `SapdExtractor` for IEC/IEEE 63195-2:2022 compliant SAPD calculation
- H5 slicing around peak SAR location for reduced memory overhead
- Mesh slicing using `PlanarCut` operations for fast localized computation
- Caching for merged skin surface entities

#### Far-field optimizations
- Symmetry reduction cuts phantom bbox at x=0 to exploit bilateral symmetry (~50% cell reduction)
- Spherical tessellation generates arbitrary incident directions via `theta_divisions` and `phi_divisions`
- Phantom bbox height reduction for high frequencies (automatic or manual limits)
- Power balance input method: `bounding_box` (default) or `phantom_cross_section` for absorption efficiency

#### Research tooling
- Skin mesh pipeline for extracting phantom outer surfaces
- Pre-computed phantom cross-sectional areas per incident direction (`data/phantom_skins/`)
- Batch cross-section analysis scripts

### Bug fixes

- Fixed `--reupload-results` flag interaction with `GOLIAT_SKIP_IF_EXISTS`
- Multiplicative ramping for multisine FDTD (improved signal quality)
- Power balance logging improvements
- Automatic Git LFS pull in `goliat init`

### Documentation

- Updated installation guide for S4L 9.2 paths and `.bashrc` workflow
- Added `goliat config` commands to CLI reference
- Documented `use_symmetry_reduction` parameter
- Added power normalization explanation (754× scaling, `power_balance.input_method`)
- Fixed `keep_awake` default (now `true`)
- Documented `--reupload-results` flag

---

## [1.3.0] - 2025-12-17

Major release with multi-sine excitation, antenna detuning, dispersion fitting, and significant infrastructure improvements. ~102 commits, ~40k insertions, ~12k deletions since v1.2.3.

### ✨ New features

#### 🌊 Multi-sine excitation (far-field)
Simulate multiple frequencies in a single FDTD run, extracting per-frequency SAR via DFT. Use `"700+2450"` syntax in `frequencies_mhz`. Up to ~4× speedup for widely-spaced frequencies.

- Custom `UserDefined` excitation using sum of cosines
- `ExtractedFrequencies` set on field sensor for DFT extraction
- Simulation time extended for beat period requirement
- Bandwidth filter explicitly disabled for multi-frequency components

#### 📡 Antenna detuning calibration (near-field)
Apply calibrated frequency shifts to account for body loading effects on antenna resonance.

- Run Gaussian calibration sims to detect resonance shift
- Store detuning values per frequency in config (e.g., `"700": -15`)
- Harmonic sims automatically apply detuning offset
- New config: `detuning_enabled`, `detuning_config`

#### 🧪 Material dispersion fitting
New `goliat/dispersion/` module for frequency-dependent material properties in multi-sine simulations.

- Debye pole dispersion model fitting (exact for 2 frequencies)
- IT'IS V5.0 database Cole-Cole model support via `material_cache.py`
- `scipy` added as dependency for optimization

#### 🤖 AI assistant improvements
Refactored `goliat ai` command with new capabilities.

- Animated thinking spinner (TTY-aware)
- `--simple` and `--complex` flags to force model selection
- Markdown formatting for responses
- Detailed cost breakdown with token usage
- Modular architecture: `embedding_indexer`, `query_processor`, `cost_tracker`, `chat_handler`

#### 📊 Analysis enhancements
- **Excel generation**: Automatic `.xlsx` file generation during analysis workflow
- **Unified stats command**: Merged `stats` and `parse-log` into single `goliat stats` command
  - Single `.log` file → parses to JSON
  - Directory → generates visualizations from all `verbose.log` files
- **Analysis GUI component**: New progress tracking for analysis phase
- **UGent vs CNR comparison tool**: Cross-institution result validation

#### 🌐 Web dashboard improvements
- Screenshot streaming (1 FPS, JPEG compression)
- Message ordering with timestamps and sequence numbers
- Smart batching to adapt to network latency
- NTP time for plot timestamps (bypasses VM clock issues)
- Adaptive timeouts to prevent freeze on exit

#### ☁️ Cloud setup improvements
- OpenVPN verification before launch
- Working directory fixes when run as administrator
- Parallel launch of license installer and Git Bash
- NVIDIA GPU driver validation

### 🔧 Infrastructure

#### Simulation runner refactoring
Complete refactor using Strategy pattern. `simulation_runner.py` reduced from ~620 to ~245 lines.

New modules:
- `goliat/runners/execution_strategy.py` (abstract base)
- `goliat/runners/isolve_manual_strategy.py` (local iSolve)
- `goliat/runners/osparc_direct_strategy.py` (cloud)
- `goliat/runners/sim4life_api_strategy.py` (Sim4Life API)
- `goliat/runners/isolve_process_manager.py`
- `goliat/runners/keep_awake_handler.py`
- `goliat/runners/retry_handler.py`

#### Gaussian near-field support
Use Gaussian pulses for frequency-domain analysis (antenna characterization, detuning detection).

- `excitation_type: "Gaussian"` config option
- Custom Gaussian waveform support (`gaussian_pulse_k` parameter)
- `ResonanceExtractor` for detecting antenna resonance
- Bandwidth and frequency resolution config parameters

### 🐛 Bug fixes

- **Subgridding contamination**: Created separate `Automatic (Subgrid)` grid settings to prevent all components getting subgridded
- **Antenna fallback**: Auto-fallback to nearest frequency antenna file when exact match not found
- **Setup timestamp preservation**: Preserve `setup_timestamp` when setup is skipped (caching)
- **Unicode on old Windows**: Replace ✓/✗/⚠ with ASCII equivalents for cp1252 console compatibility
- **scipy dependency**: Added to dependencies (was missing, broke dispersion fitter tests)
- **openpyxl dependency**: Added for Excel generation
- **Power balance calculation**: Improved accuracy
- **Bbox expansion**: Added for low-frequency whole_body simulations
- **Point sensor extraction**: Ensure results directory exists

### 📝 Documentation

- Configuration guide: multi-sine frequency format, keep_awake, detuning parameters
- Analysis documentation: Excel generation, `generate_excel` config option
- User guide: detuning workflow, multi-sine excitation, `goliat stats` command
- AI assistant: `--simple`/`--complex` flags, cost tracking, setup instructions
- Troubleshooting: antenna file fallback behavior
- Technical docs: `multi_sine_excitation_analysis.md`, `detuning_feature_design.md`, `dispersion_model_guide.md`
- Capita selecta gallery with nested collapsible sections

### 🔄 Environment variables

- `GOLIAT_SKIP_IF_EXISTS`: Skip simulation if extract deliverables already exist
- `GOLIAT_AUTO_CLEANUP`: Enable automatic cleanup of simulation files after extraction

---

## [1.2.3] - 2025-11-15

### Added

- **PyPI Publishing:** Full PyPI package support with automated publishing workflow ([#69](https://github.com/rwydaegh/goliat/issues/69))
  - Package can now be installed via `pip install goliat`
  - Configs and scripts moved into package structure for distribution
  - Automated PyPI publishing on GitHub releases
  - ASCII art banner displayed at start of CLI commands
- **Documentation:** Sim4Life API snippets reference guide with practical examples ([#61](https://github.com/rwydaegh/goliat/issues/61))
- **Installation Guide:** Centralized installation documentation with PyPI and editable install options

### Changed

- **Project Structure:** Refactored for PyPI distribution while maintaining editable install compatibility
  - Configs moved to `goliat/config/defaults/` for package inclusion
  - Utility scripts moved to `goliat/utils/scripts/` for package inclusion
  - Improved `base_dir` resolution to work for both PyPI and editable installs
- **Documentation:** Updated installation instructions to prioritize PyPI for users, editable install for developers
- **README:** Updated quick start to use PyPI installation with virtual environment setup

### Fixed

- **Config Setup:** Fixed material_name_mapping.json copying during `goliat init`
- **Repairability:** Improved `goliat init` to detect and repair incomplete setups
- **Config Overwrites:** Prevented unnecessary config file overwrite prompts after initial setup
- **Execution Control:** Corrected config access pattern for `execution_control` flags to properly handle `False` values
- **Config Access Patterns:** Fixed multiple instances where falsy values (`False`, `0`, empty lists/strings) were incorrectly replaced with truthy defaults
  - Fixed `use_gui`, `bbox_padding_mm`, `freespace_antenna_bbox_expansion_mm`, `point_source_order`, `download_email`, `far_field_setup.type`, `excitation_type`, `save_retry_count`, and `only_write_input_file`
- **Tests:** Fixed several failing tests related to simulation counting, execution control logic, and profiler timing

### Refactoring

- **Complexity Reduction:** Reduced technical debt with Tier 1 refactorings ([#63](https://github.com/rwydaegh/goliat/issues/63), [#64](https://github.com/rwydaegh/goliat/issues/64))
  - Extracted tissue grouping logic to separate module
  - Split config and setup modules for better maintainability
  - Reduced cyclomatic complexity by 14 (-8.8%) and cognitive complexity by 30 (-13.0%)
- **Config Access:** Replaced `get_setting()` with dictionary-style access using `__getitem__` ([#66](https://github.com/rwydaegh/goliat/issues/66))
- **Gridding Setup:** Reduced complexity by extracting helper methods ([#63](https://github.com/rwydaegh/goliat/issues/63))
- **Code Organization:** Removed duplicate config.py file, improved module structure
- **Config Access Patterns:** Replaced all problematic `or default` patterns with explicit `None` checks to preserve falsy values correctly

## [1.1.0] - 2025-11-04

Note that the code was already finished last weekend.

### Added
- **Linux Compatibility:** Automatic detection of AWS/Linux environments for Sim4Life cloud execution ([#55](https://github.com/rwydaegh/goliat/issues/55))
- **GUI Enhancements:** Major GUI improvements including componentized architecture, enhanced progress reporting, pie charts, timings table, and system tray integration ([#52](https://github.com/rwydaegh/goliat/issues/52))
- **Subgridding Support:** Fine-grained subgridding for antenna components with configurable subgrid levels and refinement ([#38](https://github.com/rwydaegh/goliat/issues/38))
- **Grid Rotation:** Automatic scene alignment for `by_cheek` placements to align computational grid with phone orientation ([#35](https://github.com/rwydaegh/goliat/issues/35))
- **Phantom Reference Points:** Support for anatomical reference points (nasion, tragus, belly_button) in placement scenarios ([#24](https://github.com/rwydaegh/goliat/issues/24))
- **Verify and Resume:** Deliverable-based caching system for resuming interrupted studies and skipping completed phases ([#45](https://github.com/rwydaegh/goliat/issues/45), [#26](https://github.com/rwydaegh/goliat/issues/26))
- **Command-Line Flag:** `--no-cache` flag to bypass resume logic and force fresh runs ([#43](https://github.com/rwydaegh/goliat/issues/43))
- **Phantom Rotation:** Enhanced phantom rotation for `by_cheek` placement with automatic angle detection ([#40](https://github.com/rwydaegh/goliat/issues/40), [#41](https://github.com/rwydaegh/goliat/issues/41))

### Changed
- **Far-Field Architecture:** Refactored to use one project file per simulation for better isolation and reliability ([#29](https://github.com/rwydaegh/goliat/issues/29))
- **SimulationRunner:** Simplified and decoupled GUI logic for better maintainability ([#48](https://github.com/rwydaegh/goliat/issues/48), [#47](https://github.com/rwydaegh/goliat/issues/47))
- **Profiling System:** Improved session-based timing with weighted progress calculations for more accurate ETAs ([#49](https://github.com/rwydaegh/goliat/issues/49))
- **Config Inheritance:** Enhanced configuration inheritance system for better modularity

### Fixed
- **Profiling:** Fixed inaccurate profiling system calculations ([#49](https://github.com/rwydaegh/goliat/issues/49))
- **Placement Bug:** Fixed bug where antenna would also get rotated with phantom rotation ([#41](https://github.com/rwydaegh/goliat/issues/41))
- **Tests:** Resolved test failures in config and GUI manager ([#53](https://github.com/rwydaegh/goliat/issues/53))
- **Typing:** Fixed typing errors in pyright and Pylance
- **CI:** Updated CI workflows to handle Sim4Life dependencies correctly

### Refactoring
- **Package Structure:** Rename src/ directory to goliat/, introduce CLI, reorganize several dirs
  - Rename src/ directory to goliat/ to match package name
  - Move top-level CLI scripts (run_analysis.py, run_study.py, run_free_space_study.py, run_parallel_studies.py) into cli/ directory
  - Update imports and references throughout codebase to reflect new structure
  - Reorganize *md locations in docs
- **GUI:** Significantly improved GUI architecture with modular components ([#52](https://github.com/rwydaegh/goliat/issues/52))
- **Runner:** Simplified SimulationRunner and consolidated GUI logic ([#48](https://github.com/rwydaegh/goliat/issues/48))
- **Config Files:** Refactored config files to use `extends` for better inheritance

## [0.3.0-beta.1] - 2025-10-31

### Added
- Initial release tracking with semantic versioning

## [0.2.0-beta.1] - 2025-10-22

### Features
- **Phantoms:** Add cheek placement and refactor config ([#22](https://github.com/rwydaegh/goliat/pull/22))
- **Docs:** Improve documentation and code quality ([#20](https://github.com/rwydaegh/goliat/pull/20))
- **osparc:** Implement batch run GUI and logic ([#13](https://github.com/rwydaegh/goliat/pull/13))
- **Extraction:** Refactor ResultsExtractor into modular components ([#12](https://github.com/rwydaegh/goliat/pull/12))
- **Config:** Add use_gui flag to select execution mode ([#8](https://github.com/rwydaegh/goliat/pull/8), [#9](https://github.com/rwydaegh/goliat/pull/9))
- **Placement:** Expand 'by_cheek' placement with Z-axis tilts ([#7](https://github.com/rwydaegh/goliat/pull/7))

### Bug Fixes
- **Docs:** Minor fixes in docs and improved UML diagrams
- **Logging:** Standardize traceback logging ([#17](https://github.com/rwydaegh/goliat/pull/17))
- **CI:** Correct token variable for semantic-release

### Refactoring
- **Analysis:** Split strategies.py into multiple files ([#14](https://github.com/rwydaegh/goliat/pull/14), [#15](https://github.com/rwydaegh/goliat/pull/15))

[Unreleased]: https://github.com/rwydaegh/goliat/compare/v1.4.0...HEAD
[1.4.0]: https://github.com/rwydaegh/goliat/compare/v1.3.0...v1.4.0
[1.3.0]: https://github.com/rwydaegh/goliat/compare/v1.2.3...v1.3.0
[1.2.3]: https://github.com/rwydaegh/goliat/compare/v1.1.0...v1.2.3
[1.1.0]: https://github.com/rwydaegh/goliat/compare/v1.0.0...v1.1.0
[0.3.0-beta.1]: https://github.com/rwydaegh/goliat/compare/v0.2.0-beta.1...v0.3.0-beta.1
[0.2.0-beta.1]: https://github.com/rwydaegh/goliat/compare/v0.1.0-beta.1...v0.2.0-beta.1
