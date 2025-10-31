# Troubleshooting

This section addresses common issues encountered when using GOLIAT. Issues are grouped by category, with steps to resolve them.

## Sim4life setup issues

### Sim4life not found or python path error
- **Symptom**: "iSolve.exe not found" or import errors for s4l_v1.
- **Cause**: Sim4Life Python not in PATH.
- **Solution**:
  1. Locate Sim4Life installation (default: C:\Program Files\Sim4Life_8.2.0).
  2. Edit `.bashrc` in project root with your path:

     ```
     export PATH="/path/to/Sim4Life/Python:$PATH"
     ```

  3. Source: `source .bashrc`.
  4. Verify: `python -c "import s4l_v1; print('OK')"` - should print "OK".

### Linux/Cloud execution environment
- **Symptom**: Sim4Life interpreter check fails in AWS/Linux environments.
- **Cause**: Platform detection not recognizing cloud execution environment.
- **Solution**:
  1. GOLIAT automatically detects AWS/Linux environments and bypasses Windows-specific checks.
  2. If issues persist, ensure you're using the Sim4Life Python interpreter provided in the cloud environment.
  3. The system automatically adapts file locking mechanisms for cross-platform compatibility.

### Sim4Life Web (sim4life.science) limitations
- **Symptom**: GUI unavailable, phantom licensing issues, or iSolve.exe not found when running in Sim4Life Web environment (available at sim4life.science, built on the oSPARC platform).
- **Cause**: Sim4Life Web (sim4life.science) has different capabilities compared to desktop installations.
- **Limitations**:
  1. **GUI**: The graphical interface is not available in JupyterLab environments. Set `"use_gui": false` in your configuration.
  2. **Phantom Licensing**: Most phantoms require licensing through "The Shop". The `duke_posable` phantom is available without additional licensing. Other phantoms may require linking to a license server, which is not supported in this repository.
  3. **iSolve.exe**: The solver executable is not present in the JupyterLab app environment. The solver path points to a non-existent executable.

- **Workaround for setup-only runs**:
  For proof-of-concept setup-only runs in Sim4Life Web, use a configuration similar to `configs/far_field_sim4life_web.json`:

  ```json
  {
    "extends": "far_field_config.json",
    "use_gui": false,
    "execution_control": {
      "do_setup": true,
      "do_run": false,
      "do_extract": false
    },
    "phantoms": [
      "duke_posable"
    ]
  }
  ```

  This configuration enables scene setup and project file creation without requiring solver execution or result extraction. To run simulations, use a different Sim4Life app (such as the Framework or Python runner app) or process the generated project files through other means.

### Sim4life license or phantom download fails
- **Symptom**: "License error" or phantom download prompt fails.
- **Cause**: Missing license or invalid email.
- **Solution**:
  1. Ensure Sim4Life is licensed (check by opening the S4L GUI), or when running from Sim4Life Web (sim4life.science), that you have purchased the license seats.
  2. Update `download_email` in `configs/base_config.json` to the email of the person acquiring Sim4Life for your org.
  3. Rerun study - GOLIAT retries download.
  4. Manual alternative: Download phantoms yourself, place in `data/`.

### Phantom download rate limit error
- **Symptom**: `gdown` package error indicating "file has been accessed too many times" when downloading phantoms.
- **Cause**: Google Drive rate limiting on frequently accessed files.
- **Solution**:
  1. Wait a few minutes and try again. The rate limit is temporary.
  2. Retry the download: GOLIAT will attempt to download again on the next run.
- **Note**: This issue will be fixed in a future release.

## Project and file issues

### Lock files prevent access
- **Symptom**: "File locked" or "Project corruption" error.
- **Cause**: A previous run crashed, leaving a lock file behind. This is a hidden file with a `.s4l_lock` extension.
- **Solution**:
  1. Close all Sim4Life instances.
  2. Manually delete the lock file. It will be in the same directory as the `.smash` file.
  3. Rerun the simulation. If the issue persists, restarting your machine may be necessary.

### Corrupted project file (.smash)
- **Symptom**: "HDF5 format error" or "Could not open project".
- **Cause**: Incomplete save or disk issue.
- **Solution**:
  1. Set `"do_setup": true` in your configuration file. GOLIAT will automatically overwrite the corrupted file with a new one.
  3. Check disk space/logs for hardware issues.

## Execution issues

### Simulation run fails (iSolve.exe)
- **Symptom**: "iSolve.exe failed with return code" or no output.
- **Cause**: Path, kernel (Acceleware/CUDA), or input file issue.
- **Solution**:
  1. Verify iSolve path in code (goliat/simulation_runner.py).
  2. Try `"kernel": "Software"` in config for CPU fallback.
  3. Check `logs/*.log` for solver errors (e.g., grid too fine).
  4. Ensure `manual_isolve: true` in config.

### Parallel execution limitations

- **Symptom**: Running `goliat parallel` with multiple splits, but simulations take as long as sequential runs.
- **Cause**: **iSolve can only run one simulation at a time on a single GPU**. When multiple parallel processes try to use iSolve, they queue sequentially.
- **Explanation**: 
  - Setup and extract phases can run in parallel (CPU-based)
  - Run phase (iSolve) cannot run in parallel on a single GPU machine
  - Multiple processes will queue for GPU access, effectively running one at a time
- **Solution**:
  1. **For true parallel run phases**: Use oSPARC batch execution (`batch_run: true`), where each cloud job gets its own GPU
  2. **For multiple local machines**: Set up GOLIAT on multiple Windows PCs as described in [Cloud Setup](developer_guide/cloud_setup.md)
  3. **Accept limitation**: Understand that local parallel execution only speeds up setup and extract phases, not the run phase

**When parallel execution helps**: Setup and extract phases benefit from parallelization even on single-GPU machines. The run phase will still be sequential, but overall time can be reduced if setup/extract phases are significant.

### oSPARC batch submission fails
- **Symptom**: "Invalid API key" or "Job failed".
- **Cause**: .env missing/invalid or quota exceeded.
- **Solution**:
  1. Verify `.env` in root (OSPARC_API_KEY etc.; see User Guide).
  2. Test keys: Run a single cloud sim first.
  3. Check quotas in oSPARC dashboard (max ~61 jobs).
  4. For "RETRYING": Code auto-retries 3 times; check logs/osparc_submission_logs/.
  5. Cancel stuck jobs: `python scripts/cancel_all_jobs.py --config your_config.json`.

### No results extracted
- **Symptom**: Empty JSON/PKL or "No SAR data".
- **Cause**: `do_extract: false` or simulation failed.
- **Solution**:
  1. Set `"do_extract": true` in config.
  2. Verify simulation completed and has deliverables (check for warnings in the logs)
  3. Rerun extraction: `"do_setup": false, "do_run": false, "do_extract": true`.

## Configuration issues

### Manual grid size exceeds 3 mm limit

- **Symptom**: Error message: "Manual grid size of X mm exceeds the 3 mm maximum. GOLIAT refuses to continue..."
- **Cause**: Manual gridding configuration specifies a grid size larger than 3 mm.
- **Explanation**: GOLIAT enforces a 3 mm maximum for manual grid sizes, even though coarser grids (e.g., 5 mm) may be acceptable from an FDTD standpoint at low frequencies. This restriction exists because:
  - Coarser grids lead to poor voxelization quality, affecting simulation accuracy
  - Downstream GOLIAT features like peak SAR cube computation require adequate voxelization resolution
  - Testing with coarse grids can mask issues that appear later in production runs
- **Solution**:
  1. Reduce `manual_fallback_max_step_mm` in your config to 3.0 or smaller
  2. If using per-frequency gridding, ensure all values in `global_gridding_per_frequency` are ≤ 3.0 mm
  3. The default fallback value is now 3.0 mm in base configs
  4. For now, you could use an Automatic Coarse (or Default at low frequencies) grid since GOLIAT does not yet support checking if the automatic grid is too coarse for its liking

### Config loading error
- **Symptom**: "File not found" or "Unknown study_type".
- **Cause**: Invalid path or missing `study_type`.
- **Solution**:
  1. Use full path: `--config near_field_config.json`.
  2. Ensure `study_type`: "near_field" or "far_field".
  3. Validate your JSON syntax. For a detailed guide on the configuration options, see the [Configuration Documentation](developer_guide/configuration.md).

### Placement or antenna not found
- **Symptom**: "Could not find component" or invalid placement.
- **Cause**: Custom config mismatch.
- **Solution**:
  1. Use default configs first.
  2. For custom, match `placement_scenarios` keys exactly.
  3. Antenna: Ensure freq in `antenna_config` keys.

## GUI and logging issues

### GUI freezes or no progress
- **Symptom**: Window unresponsive.
- **Cause**: Multiprocessing issue or long computation.
- **Solution**:
  1. Run headless: Set `"use_gui": false` in your config and run `goliat study your_config.json`.
  2. Check `logs/*.progress.log` for updates.
  3. Reduce grid size for faster tests.

## Disk space issues

### Running out of disk space

- **Symptom**: "No space left on device" or simulation failures.
- **Cause**: Large simulation output files accumulating.
- **Solution**:
  1. Enable automatic cleanup for serial workflows:

     ```json
     "execution_control": {
       "auto_cleanup_previous_results": ["output"]
     }
     ```

  2. Manually delete old `*_Output.h5`, `*_Input.h5` files from `results/` directories.
  3. Archive completed studies to external storage.
  4. See [Configuration Guide](developer_guide/configuration.md#execution-control) for cleanup options.

## General tips

- Always check `logs/` and console for errors.
- Rerun phases individually using `execution_control`.
- For cloud: Monitor oSPARC dashboard for job details.
- For disk space: Use `auto_cleanup_previous_results` in serial workflows.
- Still stuck? Open [GitHub Issue](https://github.com/rwydaegh/goliat/issues) with log snippet.

See [User Guide](user_guide/user_guide.md) for workflows. For a complete reference of all available features, see the [Full List of Features](reference/full_features_list.md).

---