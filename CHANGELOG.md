# Changelog

All notable changes to GOLIAT will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0-beta.1] - 2025-10-14

### Added
- Initial **beta** release of GOLIAT 🚀. This version is actively used in research but is still under development.
- Comprehensive documentation overhaul with MkDocs, including tutorials, user guides, and API references.
- Automated near-field and far-field EMF dosimetry simulation support.
- Modular setup system for phantoms, materials, gridding, and sources.
- Dual execution modes: local (iSolve) for rapid testing and cloud (oSPARC) for large-scale batch processing.
- Built-in results extraction, analysis, and visualization (SAR metrics, plots, heatmaps).
- Responsive GUI with real-time progress tracking and ETA estimation.
- Robust configuration system with inheritance to streamline study setup.
- Self-improving profiling and timing system for accurate ETAs.
- GitHub Actions for CI/CD (testing, linting, docs deployment).
- Pre-commit hooks to ensure consistent code quality.
- Project templates for issues and pull requests.

### Changed
- Redesigned README for a more inviting and informative first impression, including a beta software warning.
- Reorganized documentation for improved navigation and clarity.

### Fixed
- Corrected syntax errors in `tests/test_config.py` to ensure tests pass.
- Resolved `mkdocs.yml` configuration issues to ensure successful documentation builds on GitHub Pages.

[Unreleased]: https://github.com/rwydaegh/goliat/compare/v1.0.0-beta.1...HEAD
[1.0.0-beta.1]: https://github.com/rwydaegh/goliat/releases/tag/v1.0.0-beta.1
