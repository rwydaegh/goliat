# Auto-Cleanup Implementation Notes

## How "Previous" Simulation Detection Works

### Directory-Based Isolation

Each simulation configuration (unique combination of phantom + frequency + placement) gets its own dedicated directory:

```
results/
  near_field/
    thelonious/
      700MHz/
        by_cheek_base_base/     ← Simulation 1's directory
          *.smash
          *_Input.h5
          *_Output.h5
        by_cheek_base_up/       ← Simulation 2's directory
          *.smash
          *_Input.h5
          *_Output.h5
      900MHz/
        by_cheek_base_base/     ← Simulation 3's directory
          *.smash
          *_Input.h5
          *_Output.h5
```

### Cleanup Logic

When `auto_cleanup_previous_results` is enabled:

1. **Before** running simulation 1 again, the cleanup function looks in `results/near_field/thelonious/700MHz/by_cheek_base_base/`
2. It finds ALL files matching the configured patterns (`*_Output.h5`, `*_Input.h5`, `*.smash`)
3. It deletes these files - they are from the "previous" run of this EXACT same configuration

### Key Points

**"Previous" means**: Files from the last run of this exact simulation configuration (same phantom, frequency, placement), not the chronologically previous simulation in a batch.

**Why this works safely**:
- Each unique simulation has its own isolated directory
- When you re-run simulation 1, it only affects simulation 1's directory
- Other simulations (2, 3, etc.) in different directories are unaffected

**Example workflow**:
```python
# First run (creates files)
Run: thelonious/700MHz/by_cheek_base_base
  → Creates: abc123_Output.h5, abc123_Input.h5, project.smash

# Second run (with cleanup enabled)
Run: thelonious/700MHz/by_cheek_base_base  (same configuration)
  → BEFORE simulation: Deletes abc123_Output.h5, abc123_Input.h5, project.smash
  → DURING simulation: Creates new xyz789_Output.h5, xyz789_Input.h5, etc.
```

### Code Location

The cleanup happens in [`src/simulation_runner.py`](../src/simulation_runner.py):

```python
def run(self, simulation):
    # Clean up previous output files if configured
    if self.config.get_auto_cleanup_previous_results():
        self._cleanup_previous_output_files()  # ← Deletes files HERE
    
    with self.study.subtask("run_simulation_total"):
        # ... rest of simulation ...
```

The project directory is determined by [`src/project_manager.py`](../src/project_manager.py):

```python
def create_or_open_project(self, phantom_name, frequency_mhz, placement_name):
    # Creates path like: results/near_field/thelonious/700MHz/by_cheek/
    project_dir = os.path.join(
        self.base_results_dir,
        phantom_name,
        f"{frequency_mhz}MHz",
        placement_name
    )
    self.project_path = os.path.join(project_dir, "project.smash")
```

### Why This Is Safe for Serial Workflows

In a serial workflow where you run simulations one at a time:
1. Setup creates the project and files
2. Run executes the simulation and generates output
3. Extract pulls the results
4. When re-running the SAME simulation again, cleanup removes the old files
5. Each simulation configuration is in its own directory, so they don't interfere

### Why This Is Dangerous for Parallel Workflows

In parallel execution:
- Multiple processes might try to access the same directory simultaneously
- One process could delete files while another is reading them
- This is why the safety checks auto-disable cleanup when `batch_run: true`

## Implementation Details

### Glob Patterns Used

```python
file_patterns = {
    "output": ("*_Output.h5", "output"),
    "input": ("*_Input.h5", "input"),
    "smash": ("*.smash", "project"),
}
```

The `*` wildcard matches the hash prefix (e.g., `abc123_Output.h5`).

### Cleanup Timing

Cleanup happens:
- **When**: At the end of `ResultsExtractor.extract()`, after all results have been saved.
- **Where**: In the current project's directory and its `_Results` subdirectory.
- **What**: All files matching the specified patterns for the **current** simulation.