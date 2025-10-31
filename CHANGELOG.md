# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
