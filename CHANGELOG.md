# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.2.0] - 2025-01-27

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

[Unreleased]: https://github.com/rwydaegh/goliat/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/rwydaegh/goliat/compare/v1.0.0...v1.1.0
[0.3.0-beta.1]: https://github.com/rwydaegh/goliat/compare/v0.2.0-beta.1...v0.3.0-beta.1
[0.2.0-beta.1]: https://github.com/rwydaegh/goliat/compare/v0.1.0-beta.1...v0.2.0-beta.1
