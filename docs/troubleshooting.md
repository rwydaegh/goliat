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
  4. Verify: `python -c "import s4l_v1; print('OK')"` – should print "OK".

### Sim4life license or phantom download fails
- **Symptom**: "License error" or phantom download prompt fails.
- **Cause**: Missing license or invalid email.
- **Solution**:
  1. Ensure Sim4Life is licensed (check via GUI).
  2. Update `download_email` in `configs/base_config.json` (e.g., "your@email.com").
  3. Rerun study – GOLIAT retries download.
  4. Manual alternative: Download phantoms from ZMT Zurich site, place in `data/`.

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
  1. Verify iSolve path in code (src/simulation_runner.py).
  2. Try `"kernel": "Software"` in config for CPU fallback.
  3. Check `logs/*.log` for solver errors (e.g., grid too fine).
  4. Ensure `manual_isolve: true` in config.

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
  2. Verify simulation completed (check power_balance ~100%).
  3. Rerun extraction: `"do_setup": false, "do_run": false, "do_extract": true`.

## Configuration issues

### Config loading error
- **Symptom**: "File not found" or "Unknown study_type".
- **Cause**: Invalid path or missing `study_type`.
- **Solution**:
  1. Use full path: `--config configs/near_field_config.json`.
  2. Ensure `study_type`: "near_field" or "far_field".
  3. Validate your JSON syntax. For a detailed guide on the configuration options, see the [Configuration Documentation](configuration.md).

### Placement or antenna not found
- **Symptom**: "Could not find component" or invalid placement.
- **Cause**: Custom config mismatch.
- **Solution**:
  1. Use default configs first.
  2. For custom, match `placement_scenarios` keys exactly.
  3. Antenna: Ensure freq in `antenna_config` keys.

## Gui and logging issues

### Gui freezes or no progress
- **Symptom**: Window unresponsive.
- **Cause**: Multiprocessing issue or long computation.
- **Solution**:
  1. Run headless: Set `"use_gui": false` in your config and run `python run_study.py --config your_config.json`.
  2. Check `logs/*.progress.log` for updates.
  3. Reduce grid size for faster tests.

### Logs not generating
- **Symptom**: Empty `logs/` or no output.
- **Cause**: Permissions or rotation lock.
- **Solution**:
  1. Check permissions: `chmod -R 755 logs/`.
  2. Delete stale locks: `rm logs/log_rotation.lock`.
  3. Run with `--pid 1` for unique logs.

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
  4. See [Configuration Guide](configuration.md#execution-control) for cleanup options.

## General tips

- Always check `logs/` and console for errors.
- Rerun phases individually using `execution_control`.
- For cloud: Monitor oSPARC dashboard for job details.
- For disk space: Use `auto_cleanup_previous_results` in serial workflows.
- Still stuck? Open [GitHub Issue](https://github.com/rwydaegh/goliat/issues) with log snippet.

See [User Guide](user_guide.md) for workflows.

---