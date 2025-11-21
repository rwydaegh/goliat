# Developer Guide

This guide is for developers extending or maintaining GOLIAT. It covers the codebase structure, testing, and contribution process. GOLIAT is modular Python code interfacing with Sim4Life for EMF simulations.

## Codebase structure

GOLIAT's architecture separates concerns:

- **goliat/config.py**: Loads JSON configs with inheritance (e.g., base + study-specific).
- **goliat/studies/**: Orchestrates workflows (NearFieldStudy, FarFieldStudy inherit from BaseStudy).
- **goliat/setups/**: Builds Sim4Life scenes (PhantomSetup, PlacementSetup, MaterialSetup, etc.). See [Sim4Life API snippets](../reference/useful_s4l_snippets.md) for API patterns used.
- **goliat/project_manager.py**: Handles .smash files (create/open/save/close), including a "Verify and Resume" feature to avoid re-running simulations with unchanged configurations.
- **goliat/simulation_runner.py**: Executes simulations (local iSolve or oSPARC cloud).
- **goliat/results_extractor.py**: Extracts SAR/power data post-simulation.
- **goliat/analysis/**: Aggregates results (Analyzer with strategies for near/far-field). Includes paper generation via `cli/generate_paper.py`.
- **goliat/gui_manager.py**: Multiprocessing GUI for progress/ETA.
- **goliat/logging_manager.py**: Dual loggers (progress/verbose) with colors.
- **goliat/profiler.py**: Tracks phases (setup/run/extract) for ETAs.
- **goliat/utils.py**: Helpers (format_time, non_blocking_sleep, simple Profiler).

Key flow: Config → BaseStudy.run() → Setups → Runner → Extractor → Analyzer. For more details on the high-level architecture, see the [Technical Guide](technical_guide.md).

## Installation

For development, use editable installation from the repository. Users can install from PyPI instead. See the [installation guide](../installation.md) for both options.

**Developer setup**:

1. Clone the repository:

   ```bash
   git clone https://github.com/rwydaegh/goliat.git
   cd goliat
   ```

2. Set up Sim4Life Python environment:

   ```bash
   source .bashrc
   ```

3. Install GOLIAT package in editable mode (or in a venv):

   ```bash
   python -m pip install -e .
   ```

   > **Always use `python -m pip`**: Always use `python -m pip` instead of `pip` directly. This ensures you're using the pip associated with Sim4Life's Python interpreter. The same applies to other Python commands: use `python -m <module>` when possible.

4. Run the initialization command:

   ```bash
   goliat init
   ```

This will:
- Verify Sim4Life Python interpreter is being used
- Prepare data files (phantoms, antennas)

**Benefits of editable install**:
- Code modifications are immediately reflected (no reinstall needed)
- Better IDE support and autocomplete
- Full repository access (scripts, tests, docs)
- Can contribute to development

**Note**: If you need to reinstall (e.g., after pulling updates), you can manually run:
```bash
python -m pip install -e .
```

GOLIAT uses `pytest` for testing, with tests located in the `tests/` directory.

### Handling the `s4l_v1` dependency

Much of the codebase requires `s4l_v1`, a proprietary library available only within the Sim4Life Python environment on Windows. This prevents tests that rely on it from running in the Linux-based CI environment.

To manage this, tests requiring `s4l_v1` are marked with `@pytest.mark.skip_on_ci`. The CI pipeline is configured to exclude these marked tests, allowing it to validate platform-independent code while avoiding environment-specific failures.

```bash
# Command used in .github/workflows/test.yml
pytest -m "not skip_on_ci" tests/
```

### Local testing setup

To run the complete test suite, your local development environment must use the Sim4Life Python interpreter.

#### VS Code Configuration

1.  Open the Command Palette (`Ctrl+Shift+P`).
2.  Run the `Python: Select Interpreter` command.
3.  Select `+ Enter interpreter path...` and find the `python.exe` in your Sim4Life installation directory (e.g., `C:\Program Files\Sim4Life_8.2.0.16876\Python\python.exe`).
This configures VS Code to use the correct interpreter, which includes the `s4l_v1` library.

### Running tests locally

With the interpreter set, run the full test suite from the terminal.

1.  **First-time Setup**: Run `goliat init` to install dependencies and set up the environment. Alternatively, run any command (e.g., `goliat --help`) and accept the dependency installation prompt when asked.
2.  **Run Pytest**:

   ```bash
   # This executes all tests, including those skipped by CI
   pytest tests/ -v
   ```

### Adding new tests

-   If a new test depends on `s4l_v1` (or imports a module that does), it must be decorated with `@pytest.mark.skip_on_ci`.
-   If a test is self-contained and has no Sim4Life dependencies, it does not need the marker.

```python
import pytest
from goliat.utils import format_time # This module has s4l_v1 dependencies

# This test requires the Sim4Life environment and will be skipped on CI.
@pytest.mark.skip_on_ci
def test_a_function_that_needs_s4l():
    # ... test logic ...
    pass

# This test is self-contained and will run everywhere.
def test_a_self_contained_function():
    assert 2 + 2 == 4
```

## Extending the framework

### Adding a new setup

To add a custom source (e.g., dipole):

1. Create `goliat/setups/dipole_setup.py` inheriting BaseSetup.
2. Implement `run_full_setup()`: Load dipole CAD, position.
3. Update NearFieldStudy/FarFieldStudy to use it (e.g., if "study_type": "dipole").
4. Add to config schema in config.py.

Example in dipole_setup.py:

```python
class DipoleSetup(BaseSetup):
    def run_full_setup(self, project_manager):
        # Custom logic
        pass
```

### Contribution workflow

1. Fork the repo.
2. Create branch: `git checkout -b feature/new-setup`.
3. Code: Follow style (Ruff-formatted, type hints).
4. Test locally: `pytest`.
5. Commit: `git commit -m "Add dipole setup"`.
6. PR to main: Describe changes, reference issues.

PR requirements:
- Run pre-commit: `pre-commit run --all-files`.
- Tests: Add for new features.
- Docs: Update user_guide.md if user-facing.

## Building docs

To build the documentation, you first need to install the documentation-specific dependencies.

```bash
# Install docs dependencies
python -m pip install -e .[docs]
```

Then, you can use MkDocs to serve the documentation locally or build the static site.

```bash
# Serve the docs locally
mkdocs serve  # Local server at http://127.0.0.1:8000

# Build the static site
mkdocs build  # Outputs to site/
```

## Code style

- Formatting & Linting: Ruff (replaces Black, flake8, isort).
- Type Checking: Pyright.
- Types: Use typing (e.g., `Dict[str, Any]`).
- Docs: Google-style docstrings.

Pre-commit hook (install: `pre-commit install`):

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.14.2 # Or newer
    hooks:
      - id: ruff-format
      - id: ruff
        args: [--fix]
  - repo: https://github.com/RobertCraigie/pyright-python
    rev: v1.1.407 # Or newer
    hooks:
      - id: pyright
```

Run: `pre-commit run`.

## Other notes

- Dependencies: Defined in `pyproject.toml` (PEP 621 standard).
- Gitignore: Ignore logs/, results/, .env.
- License: Apache-2.0 - see LICENSE.
- Changelog: Update CHANGELOG.md for releases.
- **Version management**: Version is stored in `pyproject.toml` (`[project] version`) as the single source of truth. The package reads it via `importlib.metadata` when installed, or from `pyproject.toml` directly when running from source.

## Paper generation

GOLIAT includes automated LaTeX paper generation for near-field analysis results. The `goliat generate-paper` command scans the plots directory and generates a structured LaTeX document with all figures organized by section and subsection.

Check out the auto-generated first draft paper (only results):
- [Results PDF](https://github.com/rwydaegh/goliat/raw/feat/analysis-improvements-and-paper-generation/paper/near_field/pure_results/results.pdf) - Download the compiled PDF
- [Results LaTeX Source](https://github.com/rwydaegh/goliat/raw/feat/analysis-improvements-and-paper-generation/paper/near_field/pure_results/results.tex) - Download the LaTeX source

For more, see [Contributing](https://github.com/rwydaegh/goliat/blob/master/.github/CONTRIBUTING.md). For a deep dive into all available parameters, refer to the [Configuration Guide](configuration.md). For a complete reference of all features, see the [Full List of Features](../reference/full_features_list.md).

---