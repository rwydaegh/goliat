# Advanced Tutorial: oSPARC Batching and Parallel Execution

This tutorial covers scaling simulations with oSPARC cloud batching and local parallel execution. oSPARC is useful for large studies (hundreds of simulations), while parallel uses multiple CPU cores locally.

## Prerequisites

Complete [Basic Tutorial](basic.md). For oSPARC, add API keys to `.env` (see [User Guide](../user_guide.md)).

## oSPARC batching

oSPARC allows parallel cloud runs. Workflow: Generate inputs locally → Submit batch → Download results → Extract.

### Step 1: Generate input files

Edit your config (e.g., `configs/my_advanced.json`):

```json
{
  "extends": "base_config.json",
  "study_type": "far_field",
  "phantoms": ["thelonious", "eartha"],
  "frequencies_mhz": [700, 900],
  "execution_control": {
    "do_setup": true,
    "only_write_input_file": true,  // Generate .h5 files only
    "do_run": false,
    "do_extract": false,
    "batch_run": false
  }
}
```

Run:

```bash
python run_study.py --config configs/my_advanced.json
```

- Outputs .h5 input files in `results/far_field/{phantom}/{freq}MHz/{project}.smash_Results/`.

### Step 2: Submit batch to oSPARC

Update config for submission:

```json
{
  "execution_control": {
    "batch_run": true  // Enable batch submission
  }
}
```

Run:

```bash
python run_study.py --config configs/my_advanced.json
```

- GUI monitors jobs (PENDING → SUCCESS).
- Handles submission, polling, downloads automatically.
- Logs in `logs/osparc_submission_logs/`.

**Notes**:
- Max ~61 parallel jobs (oSPARC limit).
- Costs: Based on compute time; monitor in oSPARC dashboard.
- Pitfalls: Ensure .env keys valid; check quotas. If job fails, retry with `"do_run": false, "do_extract": true`.

### Step 3: Extract results

After jobs complete (GUI shows COMPLETED), update config:

```json
{
  "execution_control": {
    "do_setup": false,
    "do_run": false,
    "do_extract": true,
    "batch_run": false
  }
}
```

Run:

```bash
python run_study.py --config configs/my_advanced.json
```

- Processes downloaded results into JSON/CSV/plots.

**Expected**: Aggregated SAR over phantoms/freqs, plots in `results/far_field/plots/`.

## Local parallel execution

For multi-core local runs, use `run_parallel_studies.py`. Splits config into subsets (e.g., phantoms or frequencies).

### Step 1: Prepare config

Use a large config (e.g., full near-field with multiple freqs/phantoms).

### Step 2: Split and run

Run:

```bash
python run_parallel_studies.py --config configs/near_field_config.json --num-splits 4
```

- Splits: 4 configs in `configs/near_field_config_parallel/` (e.g., by phantoms).
- Launches 4 `run_study.py` processes (one GUI per process).
- Each handles subset; results merge in `results/`.

**Splitting Logic** (from code):
- 2 splits: Halve phantoms.
- 4 splits: One per first 4 phantoms.
- 8 splits: Split phantoms, then halve frequencies.

Use `--skip-split` for existing split dir.

**Notes**: Local parallel uses CPU cores; no cloud needed. For large studies, combine with batch for hybrid.

## Comparing results

After batch/parallel run, run analysis:

```bash
python run_analysis.py --config configs/my_advanced.json
```

- Aggregates all results.
- Plots: SAR distributions across scenarios.

## Troubleshooting

- oSPARC: "Invalid API key" – Check .env; regenerate keys.
- Parallel: "Lock file" – Delete stale `.lock` files in root.
- Memory: Reduce splits if RAM low.

For more config details, see [Configuration Guide](../configuration.md).

---