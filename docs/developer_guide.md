# Developer Guide

This guide is for developers extending or maintaining GOLIAT. It covers the codebase structure, testing, and contribution process. GOLIAT is modular Python code interfacing with Sim4Life for EMF simulations.

## Codebase structure

GOLIAT's architecture separates concerns:

- **src/config.py**: Loads JSON configs with inheritance (e.g., base + study-specific).
- **src/studies/**: Orchestrates workflows (NearFieldStudy, FarFieldStudy inherit from BaseStudy).
- **src/setups/**: Builds Sim4Life scenes (PhantomSetup, PlacementSetup, MaterialSetup, etc.).
- **src/project_manager.py**: Handles .smash files (create/open/save/close), including a "Verify and Resume" feature to avoid re-running simulations with unchanged configurations.
- **src/simulation_runner.py**: Executes simulations (local iSolve or oSPARC cloud).
- **src/results_extractor.py**: Extracts SAR/power data post-simulation.
- **src/analysis/**: Aggregates results (Analyzer with strategies for near/far-field).
- **src/gui_manager.py**: Multiprocessing GUI for progress/ETA.
- **src/logging_manager.py**: Dual loggers (progress/verbose) with colors.
- **src/profiler.py**: Tracks phases (setup/run/extract) for ETAs.
- **src/utils.py**: Helpers (format_time, non_blocking_sleep, simple Profiler).

Key flow: Config → BaseStudy.run() → Setups → Runner → Extractor → Analyzer. For more details on the high-level architecture, see the [Technical Guide](technical_guide.md).

## Testing

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

1.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```
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
from src.utils import format_time # This module has s4l_v1 dependencies

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

1. Create `src/setups/dipole_setup.py` inheriting BaseSetup.
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

Use MkDocs:

```bash
mkdocs serve  # Local server at http://127.0.0.1:8000
```

Build: `mkdocs build` – outputs to site/.

For UML (docs/classes.puml): Use PlantUML viewer or VS Code extension.

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

- Dependencies: requirements.txt (no Poetry).
- Gitignore: Ignore logs/, results/, .env.
- License: MIT – see LICENSE.
- Changelog: Update CHANGELOG.md for releases.

For more, see [Contributing](https://github.com/rwydaegh/goliat/blob/master/.github/CONTRIBUTING.md). For a deep dive into all available parameters, refer to the [Configuration Guide](configuration.md).

---