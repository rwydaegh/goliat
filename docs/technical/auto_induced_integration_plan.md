# Auto-Induced Exposure: Integration Implementation Plan

## Overview

This document details the integration of auto-induced exposure analysis into the existing `FarFieldStudy` workflow, replacing the standalone CLI approach.

## Architecture Decision

**Approach: Post-processing hook in `FarFieldStudy`**

After all environmental simulations complete for a (phantom, frequency) pair, auto-induced processing runs as a post-processing phase within the same study.

```
goliat study test_auto_induced_poc.json
    │
    ├── For each (phantom, freq):
    │   │
    │   ├── For each (direction, polarization):
    │   │   └── _run_single_simulation() → produces _Output.h5
    │   │
    │   └── After ALL sims for this (phantom, freq) complete:
    │       └── _run_auto_induced_for_phantom_freq()
    │           ├── 1. Verify all required _Output.h5 files exist
    │           ├── 2. Focus search: find_focus_and_compute_weights()
    │           ├── 3. Field combining: combine_fields_sliced()
    │           ├── 4. Reopen project with phantom geometry
    │           ├── 5. SAPD extraction using existing SapdExtractor pattern
    │           └── 6. Save results to auto_induced/auto_induced_summary.json
    │
    └── Study complete
```

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| When to run | After each (phantom, freq) pair | Can reuse last simulation's loaded project with phantom geometry |
| If sims failed | Error out, don't run auto-induced | Caching allows resume; all _Output.h5 files required |
| Standalone CLI | Remove | Doesn't integrate with GUI/profiler; requires QApplication workarounds |
| SAPD extraction | Reuse existing `SapdExtractor` pattern | Proven, handles skin surface preparation correctly |

## File Changes Required

### 1. `goliat/studies/far_field_study.py`

**Modify `_iterate_far_field_simulations()`:**

```python
def _iterate_far_field_simulations(self, phantoms, frequencies, ...):
    for phantom_name in phantoms:
        for freq in frequencies:
            # Run all (direction, polarization) sims for this phantom/freq
            for direction_name in incident_directions:
                for polarization_name in polarizations:
                    self._process_single_far_field_simulation(...)
            
            # NEW: After all sims for this (phantom, freq) complete
            if self.config["auto_induced.enabled"]:
                self._run_auto_induced_for_phantom_freq(phantom_name, freq)
```

**Add new method `_run_auto_induced_for_phantom_freq()`:**

```python
def _run_auto_induced_for_phantom_freq(self, phantom_name: str, freq: int):
    """Runs auto-induced exposure analysis for a completed (phantom, freq) set.
    
    Prerequisites:
    - All environmental simulations for this (phantom, freq) must be complete.
    - All _Output.h5 files must exist.
    
    Args:
        phantom_name: Name of the phantom (e.g., "thelonious")
        freq: Frequency in MHz
    """
    # 1. Check if already done (caching)
    output_dir = self._get_auto_induced_output_dir(phantom_name, freq)
    summary_path = output_dir / "auto_induced_summary.json"
    if self._is_auto_induced_done(summary_path, phantom_name, freq):
        self._log("Auto-induced already complete, skipping.", log_type="success")
        return
    
    # 2. Gather all _Output.h5 files
    h5_paths = self._gather_output_h5_files(phantom_name, freq)
    if not h5_paths:
        self._log("ERROR: No _Output.h5 files found. Cannot run auto-induced.", log_type="error")
        raise FileNotFoundError(f"No environmental simulation outputs for {phantom_name}@{freq}MHz")
    
    input_h5 = self._find_input_h5(phantom_name, freq)
    
    # 3. Run auto-induced pipeline
    with self.subtask("auto_induced_total"):
        results = self._execute_auto_induced_pipeline(
            h5_paths=h5_paths,
            input_h5=input_h5,
            output_dir=output_dir,
            phantom_name=phantom_name,
            freq=freq
        )
    
    # 4. Save summary
    self._save_auto_induced_summary(summary_path, results)
```

### 2. New module: `goliat/extraction/auto_induced_processor.py`

This replaces the standalone `auto_induced_extractor.py` with proper integration:

```python
class AutoInducedProcessor:
    """Processes auto-induced exposure using existing SAPD extraction infrastructure.
    
    This class orchestrates:
    1. Focus point search (using focus_optimizer)
    2. Field combination (using field_combiner)
    3. SAPD extraction (reusing SapdExtractor patterns)
    """
    
    def __init__(self, parent_study, phantom_name: str, freq: int):
        self.study = parent_study
        self.config = parent_study.config
        self.phantom_name = phantom_name
        self.freq = freq
        # Share loggers, GUI, profiler from parent study
        
    def process(self, h5_paths: list, input_h5: Path, output_dir: Path) -> dict:
        """Main processing pipeline."""
        auto_cfg = self.config["auto_induced"] or {}
        top_n = auto_cfg.get("top_n", 3)
        cube_size_mm = auto_cfg.get("cube_size_mm", 100)
        
        # Step 1: Focus search
        with self.study.subtask("auto_induced_focus_search"):
            candidates = self._find_focus_candidates(h5_paths, input_h5, top_n)
        
        # Step 2: Combine fields for each candidate
        combined_h5_paths = []
        with self.study.subtask("auto_induced_field_combining"):
            for i, candidate in enumerate(candidates):
                combined_path = self._combine_fields_for_candidate(
                    h5_paths, candidate, output_dir, i+1, cube_size_mm
                )
                combined_h5_paths.append(combined_path)
        
        # Step 3: Extract SAPD for each candidate
        sapd_results = []
        with self.study.subtask("auto_induced_sapd_extraction"):
            for i, combined_h5 in enumerate(combined_h5_paths):
                result = self._extract_sapd(combined_h5, i+1)
                sapd_results.append(result)
        
        return {
            "candidates": candidates,
            "sapd_results": sapd_results,
            "worst_case": self._find_worst_case(sapd_results)
        }
```

### 3. Caching/Resume Logic

**New file check in `_is_auto_induced_done()`:**

```python
def _is_auto_induced_done(self, summary_path: Path, phantom_name: str, freq: int) -> bool:
    """Checks if auto-induced processing is already complete.
    
    Auto-induced is considered done if:
    1. auto_induced_summary.json exists
    2. It's newer than all corresponding _Output.h5 files
    """
    if not summary_path.exists():
        return False
    
    summary_mtime = summary_path.stat().st_mtime
    
    # Get all _Output.h5 files for this (phantom, freq)
    h5_paths = self._gather_output_h5_files(phantom_name, freq)
    for h5_path in h5_paths:
        if h5_path.stat().st_mtime > summary_mtime:
            return False  # An H5 file is newer than summary
    
    return True
```

### 4. Config Schema

Already exists in `configs/test_auto_induced_poc.json`:

```json
{
    "auto_induced": {
        "enabled": true,
        "top_n": 3,
        "cube_size_mm": 100
    }
}
```

### 5. SAPD Integration

The key insight: when we open a project to load combined H5 results, we can also load the phantom geometry OR use the already-cached skin SAB file.

**Approach A: Reopen last simulation's project**
- After all sims complete, the last project has the phantom loaded
- Just need to load the combined H5 into analysis

**Approach B: Open any completed simulation's project**
- Pick any project from the (phantom, freq) set
- Load it, then extract SAPD from combined H5

**Approach C: Load phantom separately + import skin SAB**
- Create new document
- Import cached skin SAB from `data/phantoms_skin/{phantom}_skin.sab`
- Load combined H5 for analysis

**Recommendation: Approach A** - reuse already-open project state.

## Profiling Integration

**Subtasks tracked:**
```
auto_induced_total                    # Top-level wrapper
├── auto_induced_focus_search         # ~4s
├── auto_induced_field_combining      # ~8s × top_n
└── auto_induced_sapd_extraction      # ~35s × top_n
```

**Progress display:**
```
Phase 2/2: Auto-Induced Analysis
  thelonious @ 2450MHz
  ├── Focus Search     ████████████████████ 100% (4s)
  ├── Field Combining  ████████████████████ 100% (24s, 3 candidates)
  └── SAPD Extraction  ████████░░░░░░░░░░░░ 67% (2/3 candidates)
```

## Files to Delete

After integration is complete, remove:
- `cli/run_auto_induced.py` - Standalone CLI (replaced by `goliat study`)
- `goliat/extraction/auto_induced_extractor.py` - Standalone SAPD extractor

## Files to Keep/Modify

- `goliat/utils/focus_optimizer.py` - ✅ Keep as-is
- `goliat/utils/field_combiner.py` - ✅ Keep as-is  
- `goliat/utils/field_reader.py` - ✅ Keep as-is
- `goliat/utils/skin_voxel_utils.py` - ✅ Keep as-is
- `cli/__main__.py` - Remove `auto-induced` command

## Implementation Order

1. **Modify `far_field_study.py`**
   - Add `_run_auto_induced_for_phantom_freq()` method
   - Modify `_iterate_far_field_simulations()` to call it
   - Add helper methods for H5 gathering and caching

2. **Create `AutoInducedProcessor` class**
   - In `goliat/extraction/auto_induced_processor.py`
   - Orchestrates focus search, combination, SAPD extraction
   - Reuses existing utilities

3. **Integrate SAPD extraction**
   - Either extend `SapdExtractor` or create parallel logic
   - Use already-loaded project geometry

4. **Update CLI**
   - Remove `auto-induced` command from `cli/__main__.py`
   - Update help text if needed

5. **Delete obsolete files**
   - `cli/run_auto_induced.py`
   - `goliat/extraction/auto_induced_extractor.py`

6. **Update documentation**
   - `docs/technical/auto_induced_exposure_actions.md`
   - Remove CLI usage, update to config-driven approach

7. **Test**
   - Run `goliat study test_auto_induced_poc.json` end-to-end
   - Verify caching/resume works
   - Verify SAPD results are extracted correctly
