# Troubleshooting

This section addresses common issues encountered when using GOLIAT. Issues are grouped by category, with steps to resolve them.

## Sim4Life Setup Issues

### Sim4Life Not Found or Python Path Error
- **Symptom**: "iSolve.exe not found" or import errors for s4l_v1.
- **Cause**: Sim4Life Python not in PATH.
- **Solution**:
  1. Locate Sim4Life installation (default: C:\Program Files\Sim4Life_8.2.2).
  2. Edit `.bashrc` in project root with your path:
     ```
     export PATH="/path/to/Sim4Life/Python:$PATH"
     export PYTHONPATH="/path/to/Sim4Life/Python/Lib/site-packages:$PYTHONPATH"
     ```
  3. Source: `source .bashrc`.
  4. Verify: `python -c "import s4l_v1; print('OK')"` – should print "OK".

### Sim4Life License or Phantom Download Fails
- **Symptom**: "License error" or phantom download prompt fails.
- **Cause**: Missing license or invalid email.
- **Solution**:
  1. Ensure Sim4Life is licensed (check via GUI).
  2. Update `download_email` in `configs/base_config.json` (e.g., "your@email.com").
  3. Rerun study – GOLIAT retries download.
  4. Manual alternative: Download phantoms from ZMT Zurich site, place in `data/`.

## Project and File Issues

### Lock Files Prevent Access (.smash.s4l_lock)
- **Symptom**: "File locked" or "Project corruption" error.
- **Cause**: Previous run crashed; lock file remains.
- **Solution**:
  1. Close all Sim4Life instances.
  2. Delete lock file: `rm results/.../.{project}.smash.s4l_lock`.
  3. Rerun. If persistent, restart machine.

### Corrupted Project File (.smash)
- **Symptom**: "HDF5 format error" or "Could not open project".
- **Cause**: Incomplete save or disk issue.
- **Solution**:
  1. Delete .smash file: `rm results/.../project.smash`.
  2. Set `"do_setup": true` in config to recreate.
  3. Check disk space/logs for hardware issues.

## Execution Issues

### Simulation Run Fails (iSolve.exe)
- **Symptom**: "iSolve.exe failed with return code" or no output.
- **Cause**: Path, kernel (Acceleware/CUDA), or input file issue.
- **Solution**:
  1. Verify iSolve path in code (src/simulation_runner.py).
  2. Try `"kernel": "Software"` in config for CPU fallback.
  3. Check `logs/*.log` for solver errors (e.g., grid too fine).
  4. Ensure `manual_isolve: true` in config.

### oSPARC Batch Submission Fails
- **Symptom**: "Invalid API key" or "Job failed".
- **Cause**: .env missing/invalid or quota exceeded.
- **Solution**:
  1. Verify `.env` in root (OSPARC_API_KEY etc.; see User Guide).
  2. Test keys: Run a single cloud sim first.
  3. Check quotas in oSPARC dashboard (max ~61 jobs).
  4. For "RETRYING": Code auto-retries 3 times; check logs/osparc_submission_logs/.
  5. Cancel stuck jobs: `python scripts/cancel_all_jobs.py --config your_config.json`.

### No Results Extracted
- **Symptom**: Empty JSON/PKL or "No SAR data".
- **Cause**: `do_extract: false` or simulation failed.
- **Solution**:
  1. Set `"do_extract": true` in config.
  2. Verify simulation completed (check power_balance ~100%).
  3. Rerun extraction: `"do_setup": false, "do_run": false, "do_extract": true`.

## Configuration Issues

### Config Loading Error
- **Symptom**: "File not found" or "Unknown study_type".
- **Cause**: Invalid path or missing `study_type`.
- **Solution**:
  1. Use full path: `--config configs/near_field_config.json`.
  2. Ensure `study_type`: "near_field" or "far_field".
  3. Validate JSON syntax.

### Placement or Antenna Not Found
- **Symptom**: "Could not find component" or invalid placement.
- **Cause**: Custom config mismatch.
- **Solution**:
  1. Use default configs first.
  2. For custom, match `placement_scenarios` keys exactly.
  3. Antenna: Ensure freq in `antenna_config` keys.

## GUI and Logging Issues

### GUI Freezes or No Progress
- **Symptom**: Window unresponsive.
- **Cause**: Multiprocessing issue or long computation.
- **Solution**:
  1. Run headless: `python run_study_no_gui.py --config config.json`.
  2. Check `logs/*.progress.log` for updates.
  3. Reduce grid size for faster tests.

### Logs Not Generating
- **Symptom**: Empty `logs/` or no output.
- **Cause**: Permissions or rotation lock.
- **Solution**:
  1. Check permissions: `chmod -R 755 logs/`.
  2. Delete stale locks: `rm logs/log_rotation.lock`.
  3. Run with `--pid 1` for unique logs.

## General Tips

- Always check `logs/` and console for errors.
- Rerun phases individually using `execution_control`.
- For cloud: Monitor oSPARC dashboard for job details.
- Still stuck? Open [GitHub Issue](https://github.com/rwydaegh/goliat/issues) with log snippet.

See [User Guide](../user_guide.md) for workflows.

---
*Last updated: {date}*