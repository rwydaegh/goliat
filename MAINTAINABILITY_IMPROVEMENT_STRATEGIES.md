# Maintainability Improvement Strategies

## Current Situation
- **Commit 67d7acad**: 3.9% technical debt
- **Commit 7b12ac7**: 5.85% technical debt
- **Target**: < 5% technical debt
- **Gap**: Need to reduce by ~0.85%+ (approximately 1.95 percentage points from current state)

## Key Changed Files Between Commits

Based on the diff analysis, the following Python files were modified:
- `goliat/analysis/analyzer.py`
- `goliat/analysis/plotter.py`
- `goliat/extraction/power_extractor.py`
- `goliat/extraction/reporter.py`
- `goliat/extraction/sar_extractor.py`
- `goliat/extraction/tissue_grouping.py`
- `goliat/gui/components/*` (multiple GUI components)
- `goliat/runners/sim4life_api_strategy.py`
- `goliat/setups/base_setup.py`
- `goliat/setups/material_setup.py`
- `goliat/setups/source_setup.py`
- And many others...

## Qlty CLI Analysis Results

### Critical Issues Found by Qlty Smells Analysis

#### `goliat/project_manager.py` (Total Complexity: 115)

**High Complexity Functions:**
1. **`_get_deliverables_status()`** - Complexity: 21
   - Location: Line 128
   - Issues: Multiple nested conditionals, complex file validation logic
   - Has 7 early return paths
   - Multiple file existence checks and size validations

2. **`create_new()`** - Complexity: 19
   - Location: Line 557
   - Issues: Multiple responsibilities (closing documents, deleting files, creating new project)

3. **`save()`** - Complexity: 18
   - Location: Line 638
   - Issues: Retry logic with nested exception handling

**Functions with Many Parameters:**
- `_validate_placement_params()` - 6 parameters (line 390)
- `create_or_open_project()` - 6 parameters (line 461)

**Functions with Many Returns:**
- `verify_simulation_metadata()` - 7 return statements (line 217)
  - Multiple early returns for different failure conditions
  - Complex validation logic with nested conditionals

**Deep Nesting:**
- Level 5 nesting found around line 591 (exception handling within nested loops)

#### `goliat/studies/base_study.py` (Total Complexity: 64)

**High Complexity Functions:**
1. **`_upload_results_if_assignment()`** - Complexity: 26
   - Location: Line 279
   - Issues: Complex path manipulation logic, multiple conditional branches
   - File collection, path normalization, and HTTP upload logic all in one method

#### `goliat/studies/near_field_study.py` (Total Complexity: 108) - **F Rating**

**Critical Issues:**
1. **`_run_study()`** - Cyclomatic: 31, Cognitive: 58, Lines: 115, LOC: 103
   - **Issues**: Extremely high complexity, deeply nested loops (5 levels)
   - Multiple nested loops: phantoms → frequencies → scenarios → positions → orientations
   - Complex conditional logic for execution control flags
   - Mixed responsibilities: validation, iteration, progress tracking

2. **`_run_placement()`** - Cyclomatic: 27, Cognitive: 43, Lines: 182, LOC: 146, **8 parameters**
   - **Issues**: Very long method, high complexity, too many parameters
   - Handles setup, run, and extract phases all in one method
   - Complex conditional logic for phase skipping
   - Multiple responsibilities: project management, simulation execution, extraction

3. **Deep Nesting** - Level 5 nesting found in `_run_study()` (line 109-135)
   - Five nested loops make code hard to follow and test

4. **`_validate_auto_cleanup_config()`** - Cyclomatic: 9, Cognitive: 6, Lines: 61, LOC: 54
   - Moderate complexity but could be simplified

#### `goliat/studies/far_field_study.py` (Total Complexity: 86) - **F Rating**

**Critical Issues:**
1. **`_run_study()`** - Cyclomatic: 25, Cognitive: 33, Lines: 101, LOC: 87
   - **Issues**: High complexity, deeply nested loops (5 levels)
   - Four nested loops: phantoms → frequencies → directions → polarizations
   - Similar structure to `near_field_study._run_study()` (code duplication)

2. **`_run_single_simulation()`** - Cyclomatic: 28, Cognitive: 47, Lines: 181, LOC: 150, **7 parameters**
   - **Issues**: Very long method, high complexity, too many parameters
   - Nearly identical to `near_field_study._run_placement()` (significant duplication)
   - Handles all three phases (setup, run, extract) in one method

3. **Deep Nesting** - Level 5 nesting found in two places (lines 105-110, 121-122)
   - Nested conditionals within nested loops

4. **`_validate_auto_cleanup_config()`** - Cyclomatic: 8, Cognitive: 6, Lines: 22, LOC: 19
   - Simpler than near_field version but still duplicated code

**Code Duplication Between Files:**
- `_run_study()` methods are very similar (only differ in loop structure)
- `_run_placement()` / `_run_single_simulation()` are nearly identical (~90% duplicate)
- `_validate_auto_cleanup_config()` is duplicated with minor differences

### Impact on Technical Debt

These high-complexity functions directly contribute to technical debt:
- Functions with cyclomatic complexity > 20 are considered "very high" risk
- Cognitive complexity > 30 indicates code is hard to understand
- Methods > 150 lines are difficult to maintain and test
- Deep nesting (>4 levels) increases bug risk and reduces readability
- Large parameter lists (7-8) indicate tight coupling
- Code duplication between files violates DRY principle

These high-complexity functions directly contribute to technical debt:
- Functions with complexity > 15 are considered "very high" risk
- Multiple return paths make testing difficult
- Deep nesting reduces readability and increases bug risk
- Large parameter lists indicate tight coupling

## Code Quality Issues Identified

### 1. Type Safety Issues (Pyright Errors)

**Issues Found:**
- `plotter.py:131`: Invalid `dropna()` call with list argument
- `plotter.py:200`: Invalid conditional operand with Series type
- `plotter.py:241`: Cannot access `.values` attribute on ndarray
- `sar_extractor.py:331`: Cannot access `.unique()` attribute on ndarray

**Impact**: Type errors reduce maintainability and can lead to runtime bugs. Qlty penalizes code with type issues.

**Strategy**: Fix all pyright type errors systematically:
1. Add proper type annotations for pandas/numpy operations
2. Use `.to_numpy()` or `.array` instead of `.values` where appropriate
3. Fix conditional checks with pandas Series (use `.any()`, `.all()`, or `.empty`)
4. Ensure proper type hints for all function parameters and return types

### 2. Large Files (High Complexity)

**Files Over 500 Lines:**
- `goliat/gui/components/plots.py`: **721 lines**
- `goliat/project_manager.py`: **714 lines**
- `goliat/setups/near_field_setup.py`: **673 lines**
- `goliat/analysis/plotter.py`: **554 lines**
- `goliat/runners/isolve_manual_strategy.py`: **511 lines**

**Impact**: Large files are harder to understand, test, and maintain. Qlty penalizes files with high cyclomatic complexity.

**Strategy**: Break down large files into smaller, focused modules:

#### For `plots.py` (721 lines):
- Split into separate classes/files:
  - `plots/time_remaining_plot.py`
  - `plots/overall_progress_plot.py`
  - `plots/pie_charts_manager.py`
  - `plots/system_utilization_plot.py`
- Extract common plotting utilities to `plots/utils.py`
- Each plot class should be < 200 lines

#### For `project_manager.py` (714 lines, Total Complexity: 115):
**Priority Refactoring Targets:**
- **`_get_deliverables_status()`** (Complexity 21): Extract to `project/deliverables_validator.py`
  - Split into: `_check_extract_deliverables()`, `_check_run_deliverables()`, `_validate_h5_file()`
  - Each method should have complexity < 5
- **`verify_simulation_metadata()`** (7 returns): Extract to `project/metadata_verifier.py`
  - Split into: `_verify_config_hash()`, `_verify_project_file()`, `_verify_deliverables()`
  - Use early returns pattern consistently
- **`create_new()`** (Complexity 19): Extract to `project/project_creator.py`
  - Split into: `_close_existing_project()`, `_cleanup_cache_files()`, `_initialize_new_project()`
- **`save()`** (Complexity 18): Extract retry logic to `project/save_handler.py`
  - Create `SaveHandler` class with retry logic
- **Reduce parameter lists**: Use dataclasses for `_validate_placement_params()` and `create_or_open_project()`
- Extract configuration management to `project/config_manager.py`
- Extract file operations to `project/file_manager.py`
- Keep core orchestration logic in main file (< 300 lines)

#### For `near_field_setup.py` (673 lines):
- Split setup phases into separate classes:
  - `setups/near_field/phantom_setup.py`
  - `setups/near_field/source_setup.py`
  - `setups/near_field/gridding_setup.py`
  - `setups/near_field/boundary_setup.py`
- Use composition pattern instead of one large class

#### For `plotter.py` (554 lines):
- Split by plot type:
  - `analysis/plotting/sar_plots.py` (bar charts, line plots)
  - `analysis/plotting/heatmap_plots.py` (heatmap generation)
  - `analysis/plotting/power_plots.py` (power balance plots)
- Extract common utilities to `analysis/plotting/utils.py`

#### For `isolve_manual_strategy.py` (511 lines):
- Extract process management to `runners/isolve/process_manager.py`
- Extract output parsing to `runners/isolve/output_parser.py`
- Extract retry logic to `runners/isolve/retry_handler.py`
- Keep strategy orchestration in main file (< 200 lines)

### 3. Complex Methods (High Cyclomatic Complexity)

**Issues Identified:**

#### `power_extractor.py`:
- `_extract_far_field_power()`: Complex conditional logic, multiple responsibilities
- `_extract_near_field_power()`: Multiple fallback paths, nested conditionals

**Strategy**: Extract smaller helper methods:
```python
# Instead of one large method, break into:
def _extract_far_field_power(self, ...):
    theoretical_power = self._calculate_theoretical_power()
    manual_power = self._extract_manual_power_from_s4l(...)
    return self._select_power_source(theoretical_power, manual_power)

def _calculate_theoretical_power(self) -> float:
    # Extract calculation logic

def _extract_manual_power_from_s4l(self, ...) -> float | None:
    # Extract manual extraction logic
```

#### `sar_extractor.py`:
- `_calculate_group_sar()`: Long method with nested conditionals and loops
- `extract_sar_statistics()`: Orchestrates many operations

**Strategy**:
- Extract group filtering logic to `_filter_present_tissues()`
- Extract SAR calculation to `_compute_weighted_avg_sar()`
- Extract peak SAR extraction to `_extract_peak_sar_for_group()`
- Each method should have single responsibility

#### `plotter.py`:
- `plot_power_balance_overview()`: Very long method (~190 lines) with multiple responsibilities
- `plot_sar_heatmap()`: Complex nested logic

**Strategy**:
- Break `plot_power_balance_overview()` into:
  - `_plot_balance_distribution()`
  - `_plot_power_components()`
  - `_plot_balance_heatmap()`
- Extract heatmap data preparation to separate methods

#### `reporter.py`:
- `_build_html_content()`: Complex string manipulation and DataFrame operations

**Strategy**:
- Extract HTML table generation to `_build_tissue_groups_html()`
- Extract SAR statistics formatting to `_format_sar_statistics_html()`
- Extract peak SAR details formatting to `_format_peak_sar_html()`

### 4. Long Parameter Lists

**Issues**: Many methods have 4+ parameters, making them hard to call and test.

**Examples**:
- `save_reports(df, tissue_groups, group_sar_stats, results_data)` - 4 parameters
- `_build_html_content(df, tissue_groups, group_sar_stats, results_data)` - 4 parameters

**Strategy**: Use dataclasses or TypedDict for related parameters:
```python
from dataclasses import dataclass
from typing import TypedDict

class ReportData(TypedDict):
    df: pd.DataFrame
    tissue_groups: dict
    group_sar_stats: dict
    results_data: dict

def save_reports(self, data: ReportData):
    # Now single parameter
```

### 5. Duplicate Code Patterns

**Issues Found**:
- Repeated error handling patterns
- Similar logging patterns across files
- Repeated DataFrame operations

**Strategy**:
- Create utility functions for common patterns:
  - `utils/error_handling.py`: Standardized exception handling decorators
  - `utils/logging_helpers.py`: Common logging patterns
  - `utils/dataframe_ops.py`: Common pandas operations

### 6. Missing Type Hints

**Issues**: Many methods lack proper type hints, especially for:
- Sim4Life API objects (`analysis.Extractor`)
- Complex return types
- Optional parameters

**Strategy**:
- Add comprehensive type hints using `TYPE_CHECKING` for Sim4Life imports
- Use `typing.Protocol` for Sim4Life API interfaces
- Add return type annotations to all public methods
- Use `Optional[]` and `Union[]` where appropriate

### 7. Deep Nesting

**Issues**: Some methods have 4+ levels of nesting (if/for/try/with).

**Examples**:
- `power_extractor.py`: Nested try-except blocks
- `sar_extractor.py`: Nested loops and conditionals

**Strategy**:
- Use early returns to reduce nesting
- Extract nested logic to separate methods
- Use guard clauses for error conditions
- Consider using `match/case` for complex conditionals (Python 3.10+)

### 8. Magic Numbers and Strings

**Issues**: Hard-coded values scattered throughout code:
- Column names like `"Peak Spatial-Average SAR[IEEE/IEC62704-1] (10g)"`
- Threshold values
- Color codes

**Strategy**:
- Create constants module: `goliat/constants.py`
- Use enums for categorical values
- Extract configuration values to config files

### 9. Tight Coupling

**Issues**: Classes have many dependencies injected via `__init__`:
- `PowerExtractor` has 8+ instance variables from parent
- `SarExtractor` has similar pattern

**Strategy**:
- Use dependency injection containers
- Create smaller, focused service classes
- Use composition over inheritance where appropriate

### 10. Inconsistent Error Handling

**Issues**: Some methods use exceptions, others return None, others log and continue.

**Strategy**:
- Standardize error handling patterns
- Create custom exception hierarchy
- Use result types (Success/Error) for operations that can fail

## Prioritized Action Plan

### Phase 1: Quick Wins (Target: ~0.4% reduction)
1. **Fix all pyright type errors** (highest impact, relatively quick)
   - Fix `plotter.py` type issues
   - Fix `sar_extractor.py` type issues
   - Add missing type hints to changed files
   - **Estimated effort**: 4-6 hours

2. **Refactor `_get_deliverables_status()` in `project_manager.py`** (Complexity 21 → < 5 per method)
   - Extract `_check_extract_deliverables()` method
   - Extract `_check_run_deliverables()` method
   - Extract `_validate_h5_file()` method
   - **Impact**: High - reduces complexity by ~15 points
   - **Estimated effort**: 3-4 hours

3. **Refactor `verify_simulation_metadata()` in `project_manager.py`** (7 returns → structured)
   - Extract `_verify_config_hash()` method
   - Extract `_verify_project_file()` method
   - Extract `_verify_deliverables()` method
   - Consolidate return statements
   - **Impact**: High - improves testability and readability
   - **Estimated effort**: 3-4 hours

4. **Extract magic numbers to constants**
   - Create `constants.py` module
   - Replace hard-coded strings/numbers
   - **Estimated effort**: 2-3 hours

5. **Reduce method complexity in `plotter.py`**
   - Break `plot_power_balance_overview()` into smaller methods
   - Extract helper methods for heatmap generation
   - **Estimated effort**: 3-4 hours

### Phase 2: Medium Impact (Target: ~0.6% reduction)
4. **Refactor `_run_study()` in `near_field_study.py`** (Cyclomatic 31, Cognitive 58 → < 10 each)
   - Extract loop iteration logic to `_iterate_simulations()` method
   - Extract progress tracking to `_update_progress()` method
   - Extract execution control validation to `_validate_execution_control()` method
   - Reduce nesting by extracting inner loops to separate methods
   - **Impact**: Very High - reduces complexity by ~40 points
   - **Estimated effort**: 4-5 hours

5. **Refactor `_run_placement()` in `near_field_study.py`** (Cyclomatic 27, Cognitive 43, 8 params → < 10 each, < 5 params)
   - Extract setup phase to `_execute_setup_phase()` method
   - Extract run phase to `_execute_run_phase()` method (already exists, reuse)
   - Extract extract phase to `_execute_extract_phase()` method
   - Create `SimulationParams` dataclass to reduce parameter count
   - **Impact**: Very High - reduces complexity by ~30 points
   - **Estimated effort**: 4-5 hours

6. **Refactor `_run_study()` in `far_field_study.py`** (Cyclomatic 25, Cognitive 33 → < 10 each)
   - Extract loop iteration logic (similar to near_field refactoring)
   - Extract progress tracking
   - **Impact**: High - reduces complexity by ~20 points
   - **Estimated effort**: 3-4 hours

7. **Refactor `_run_single_simulation()` in `far_field_study.py`** (Cyclomatic 28, Cognitive 47, 7 params → < 10 each, < 5 params)
   - Extract setup/run/extract phases (similar to near_field refactoring)
   - Create `SimulationParams` dataclass
   - **Impact**: Very High - reduces complexity by ~30 points
   - **Estimated effort**: 4-5 hours

8. **Eliminate code duplication between study files**
   - Extract common `_run_simulation_phases()` method to `BaseStudy`
   - Extract common `_validate_execution_control()` to `BaseStudy`
   - Extract common `_validate_auto_cleanup_config()` to `BaseStudy` (unified version)
   - **Impact**: High - reduces duplication and maintenance burden
   - **Estimated effort**: 3-4 hours

9. **Refactor `_upload_results_if_assignment()` in `base_study.py`** (Complexity 26 → < 8 per method)
   - Extract `_collect_result_files()` method
   - Extract `_normalize_relative_path()` method
   - Extract `_upload_files_to_server()` method
   - **Impact**: High - reduces complexity by ~18 points
   - **Estimated effort**: 3-4 hours

10. **Refactor `create_new()` and `save()` in `project_manager.py`**
   - Extract `_close_existing_project()` method
   - Extract `_cleanup_cache_files()` method
   - Extract retry logic to `SaveHandler` class
   - **Impact**: Medium - reduces complexity by ~15 points total
   - **Estimated effort**: 4-5 hours

11. **Reduce parameter lists in `project_manager.py`**
   - Create `PlacementParams` dataclass for `_validate_placement_params()`
   - Create `ProjectParams` dataclass for `create_or_open_project()`
   - **Impact**: Medium - improves maintainability
   - **Estimated effort**: 2-3 hours

12. **Split `plots.py` into smaller modules**
   - Create separate plot classes in `plots/` subdirectory
   - Extract common utilities
   - **Estimated effort**: 6-8 hours

13. **Refactor `sar_extractor.py` methods**
   - Break `_calculate_group_sar()` into smaller methods
   - Extract helper methods for group filtering
   - **Estimated effort**: 4-5 hours

14. **Refactor `power_extractor.py` methods**
   - Extract calculation logic to separate methods
   - Simplify conditional branches
   - **Estimated effort**: 3-4 hours

### Phase 3: Structural Improvements (Target: ~0.3% reduction)
7. **Split `project_manager.py`**
   - Extract configuration management
   - Extract file operations
   - **Estimated effort**: 6-8 hours

8. **Split `near_field_setup.py`**
   - Create setup phase classes
   - Use composition pattern
   - **Estimated effort**: 8-10 hours

9. **Split `isolve_manual_strategy.py`**
   - Extract process management
   - Extract output parsing
   - **Estimated effort**: 5-6 hours

10. **Standardize error handling**
    - Create exception hierarchy
    - Add error handling utilities
    - **Estimated effort**: 4-5 hours

### Phase 4: Long-term Improvements (Target: ~0.2% reduction)
11. **Reduce parameter lists using dataclasses**
    - Create `ReportData` TypedDict
    - Refactor methods to use structured data
    - **Estimated effort**: 3-4 hours

12. **Add comprehensive type hints**
    - Add Protocol interfaces for Sim4Life API
    - Complete type annotations
    - **Estimated effort**: 8-10 hours

13. **Create utility modules for common patterns**
    - Error handling utilities
    - Logging helpers
    - DataFrame operations
    - **Estimated effort**: 4-5 hours

## Measurement Strategy

After each phase:
1. Run `~/.qlty/bin/qlty.exe smells --all` to check for code smells (complexity, duplication, etc.)
2. Run `~/.qlty/bin/qlty.exe metrics --all --functions --sort complexity` to track complexity metrics
3. Run `pyright goliat/` to verify type errors are resolved
4. Run `ruff check goliat/` to ensure code style compliance
5. Review file sizes and method complexity metrics
6. Check technical debt percentage on qlty.sh dashboard (web interface)

**Key Metrics to Track:**
- Total file complexity (target: < 50 per file)
- Function complexity (target: < 8 per function, max 15)
- Number of functions with > 6 parameters (target: 0)
- Number of functions with > 5 return statements (target: 0)
- Maximum nesting depth (target: < 4 levels)

## Expected Impact

- **Phase 1**: ~0.4% reduction (from 5.85% to ~5.45%)
  - Refactoring `_get_deliverables_status()` and `verify_simulation_metadata()` will significantly reduce complexity
- **Phase 2**: ~0.6% reduction (from 5.45% to ~4.85%)
  - **Critical**: Refactoring study files (`near_field_study.py` and `far_field_study.py`) addresses F-rated files
  - Refactoring `_run_study()` and `_run_placement()`/`_run_single_simulation()` will dramatically reduce complexity
  - Eliminating code duplication between study files reduces maintenance burden
  - Refactoring `_upload_results_if_assignment()` addresses high-complexity function
- **Phase 3**: ~0.3% reduction (from 4.85% to ~4.55%)
  - Structural improvements from splitting large files
- **Phase 4**: ~0.2% reduction (from 4.55% to ~4.35%)

**Total Expected Reduction**: ~1.5 percentage points, bringing technical debt from 5.85% to approximately **4.35%**, well below the 5% target.

**Key Complexity Reductions:**
- `project_manager.py`: From 115 → ~60 (target: < 50 per file)
- `base_study.py`: From 64 → ~40 (target: < 50 per file)
- `near_field_study.py`: From 108 → ~50 (target: < 50 per file) - **Addresses F rating**
- `far_field_study.py`: From 86 → ~45 (target: < 50 per file) - **Addresses F rating**
- Individual functions: All high-complexity functions (>20 cyclomatic) reduced to < 10
- Deep nesting: Reduced from level 5 to < 3
- Parameter counts: Reduced from 7-8 to < 5 using dataclasses

## Notes

- Focus on the files that changed between the two commits first
- Each refactoring should be done incrementally with tests
- Maintain backward compatibility during refactoring
- Use feature flags if needed for gradual rollout
- Document breaking changes clearly

## Tools to Use

- **Type checking**: `pyright` (already configured)
- **Linting**: `ruff` (already configured)
- **Complexity analysis**: Consider adding `radon` or `mccabe` to CI
- **Code quality**: `qlty` CLI (for tracking technical debt percentage)
