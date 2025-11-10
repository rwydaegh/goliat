# Technical Debt Reduction Plan: File Splitting Opportunities

Current status: **4.43% technical debt** (down from initial state)

## Analysis: Top Complexity Files

### 1. `goliat/utils/setup.py` (Complexity: 95, 11 functions, 0 classes)

**Current Structure:**
- Mixed concerns: package checks, interpreter detection, bashrc management, data prep, user preferences
- All functions are standalone (no class)

**Splitting Opportunities:**

#### Option A: Split by Domain
- **`goliat/utils/package_setup.py`** (complexity ~15)
  - `check_package_installed()`
  - `initial_setup()` (package installation part)

- **`goliat/utils/interpreter_setup.py`** (complexity ~30)
  - `check_python_interpreter()`
  - `find_sim4life_python_executables()`
  - `update_bashrc()`
  - `prompt_copy_bashrc_to_home()`
  - `sync_bashrc_to_home()`

- **`goliat/utils/data_preparation.py`** (complexity ~20)
  - `prepare_data()`
  - `check_repo_root()`

- **`goliat/utils/user_preferences.py`** (complexity ~10)
  - `get_user_preferences()`
  - `save_user_preferences()`

- **`goliat/utils/setup.py`** (complexity ~20)
  - `initial_setup()` (orchestrator)
  - Keep as main entry point

**Expected Impact:** Reduce from 95 to ~20-30 per file, total complexity similar but better organized

---

### 2. `goliat/config.py` (Complexity: 69, 27 functions, 1 class)

**Current Structure:**
- Single large `Config` class with many responsibilities:
  - Config loading/inheritance
  - Config access (many getters)
  - File cleanup
  - Profiling config management

**Splitting Opportunities:**

#### Option A: Extract Accessor Methods
- **`goliat/config/config_loader.py`** (complexity ~25)
  - `deep_merge()` (standalone function)
  - `_load_config_with_inheritance()`
  - `_load_json()`
  - `_resolve_config_path()`
  - `_load_or_create_profiling_config()`

- **`goliat/config/config_accessor.py`** (complexity ~20)
  - All `get_*()` methods (get_setting, get_simulation_parameters, get_antenna_config, etc.)
  - ~15 getter methods

- **`goliat/config/config_cleanup.py`** (complexity ~10)
  - `_cleanup_old_data_files()`

- **`goliat/config.py`** (complexity ~15)
  - Main `Config` class (orchestrator)
  - `__init__()`
  - Delegates to specialized modules

**Expected Impact:** Reduce main class complexity from 69 to ~15-20, better separation of concerns

---

### 3. `goliat/project_manager.py` (Complexity: 87, 17 functions, 2 classes)

**Current Structure:**
- Already partially refactored (validation/path building extracted)
- Still has: metadata handling, validation, file operations, project lifecycle

**Splitting Opportunities:**

#### Option A: Extract Validation & Metadata
- **`goliat/project/project_validator.py`** (complexity ~25)
  - `_is_valid_smash_file()`
  - `verify_simulation_metadata()`
  - `_get_deliverables_status()`
  - `get_setup_timestamp_from_metadata()`

- **`goliat/project/project_metadata.py`** (complexity ~20)
  - `write_simulation_metadata()`
  - `_generate_config_hash()`
  - Metadata reading/writing logic

- **`goliat/project/project_file_operations.py`** (complexity ~15)
  - `create_new()`
  - `open()`
  - `save()`
  - `close()`
  - `cleanup()`
  - `reload_project()`

- **`goliat/project_manager.py`** (complexity ~30)
  - Main `ProjectManager` class
  - `create_or_open_project()` (orchestrator)
  - Delegates to specialized modules

**Expected Impact:** Reduce from 87 to ~30 in main file, better testability

---

### 4. `goliat/simulation_runner.py` (Complexity: 71, 6 functions, 1 class)

**Current Structure:**
- Single class handling multiple execution strategies
- `_run_isolve_manual()` is very complex (threading, subprocess management)

**Splitting Opportunities:**

#### Option A: Extract Execution Strategies
- **`goliat/simulation/execution/isolve_runner.py`** (complexity ~40)
  - `_run_isolve_manual()` logic
  - Threading/subprocess management
  - Output reading logic

- **`goliat/simulation/execution/osparc_runner.py`** (complexity ~15)
  - `_run_osparc_direct()` logic

- **`goliat/simulation/execution/api_runner.py`** (complexity ~10)
  - `_get_server_id()` logic
  - Sim4Life API execution

- **`goliat/simulation_runner.py`** (complexity ~20)
  - Main `SimulationRunner` class
  - `run()` method (orchestrator)
  - Delegates to strategy classes

**Expected Impact:** Reduce from 71 to ~20 in main file, isolate complex threading logic

---

### 5. `goliat/studies/near_field_study.py` (Complexity: 91, 3 functions, 1 class)

**Current Structure:**
- `_run_study()` is very complex (nested loops, orchestration)
- `_run_placement()` handles full simulation lifecycle

**Splitting Opportunities:**

#### Option A: Extract Orchestration Logic
- **`goliat/studies/simulation_loop.py`** (complexity ~30)
  - Nested loop logic for iterating phantoms/frequencies/placements
  - Progress tracking
  - Simulation counting

- **`goliat/studies/placement_executor.py`** (complexity ~40)
  - `_run_placement()` logic
  - Setup/run/extract orchestration for single placement

- **`goliat/studies/near_field_study.py`** (complexity ~25)
  - Main `NearFieldStudy` class
  - `_run_study()` (orchestrator)
  - `_validate_auto_cleanup_config()`
  - Delegates to specialized modules

**Expected Impact:** Reduce from 91 to ~25 in main file, better separation of iteration vs execution

---

## Priority Ranking

### Tier 1: High Impact, Low Risk
1. **`goliat/utils/setup.py`** → Split into 4-5 focused modules
   - **Impact:** High (complexity 95 → ~20-30 per file)
   - **Risk:** Low (functions are independent)
   - **Effort:** Medium

2. **`goliat/config.py`** → Extract accessor methods
   - **Impact:** Medium-High (complexity 69 → ~15-20)
   - **Risk:** Low (getters are simple)
   - **Effort:** Medium

### Tier 2: High Impact, Medium Risk
3. **`goliat/project_manager.py`** → Extract validation/metadata/file ops
   - **Impact:** High (complexity 87 → ~30)
   - **Risk:** Medium (more interconnected)
   - **Effort:** Medium-High

4. **`goliat/simulation_runner.py`** → Extract execution strategies
   - **Impact:** High (complexity 71 → ~20)
   - **Risk:** Medium (threading complexity)
   - **Effort:** Medium-High

### Tier 3: Medium Impact, Higher Risk
5. **`goliat/studies/near_field_study.py`** → Extract orchestration
   - **Impact:** Medium-High (complexity 91 → ~25)
   - **Risk:** Medium-High (core study logic)
   - **Effort:** High

---

## Expected Overall Impact

If all Tier 1 and Tier 2 refactorings are completed:

**Before:**
- `setup.py`: 95
- `config.py`: 69
- `project_manager.py`: 87
- `simulation_runner.py`: 71
- **Subtotal:** 322

**After (estimated):**
- Split files: ~20-40 each (distributed complexity)
- Main orchestrators: ~15-30 each
- **Subtotal:** ~150-200 (distributed across more files)

**Estimated reduction:** ~120-170 complexity points (~37-53% reduction in these files)

**Overall impact:** Could reduce technical debt from 4.43% to ~3-3.5%

---

## Implementation Strategy

1. **Start with Tier 1** (lowest risk, good impact)
2. **Test thoroughly** after each split
3. **Update imports** across codebase
4. **Update documentation** (UML diagrams, etc.)
5. **Measure qlty metrics** after each change

---

## Notes

- File splitting helps even if total complexity stays similar (better organization)
- Smaller files are easier to test, understand, and maintain
- Follows Single Responsibility Principle
- Makes codebase more navigable
