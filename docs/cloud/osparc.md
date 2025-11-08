# oSPARC cloud execution

oSPARC (Open Simulation Platform for Advanced Research and Computing) is a cloud platform that provides GPU compute resources for Sim4Life simulations. GOLIAT can submit simulations to oSPARC instead of running them locally, allowing you to scale beyond local hardware limits.

## When to use oSPARC

Use oSPARC batch execution when:

- You have 50+ simulations to run
- Local hardware is insufficient (limited GPU, RAM, or time)
- You need true parallel execution (each job gets its own GPU)
- You want to offload compute costs to cloud credits

For smaller studies (10-50 simulations), local parallel execution is usually faster and free. See [parallel execution](../tutorials/05_parallel_and_cloud_execution.ipynb) for local options.

## How it works

oSPARC batch execution uses a three-phase workflow:

1. Generate input files: Run setup locally to create `.h5` solver input files
2. Submit to cloud: Upload files and submit jobs to oSPARC compute nodes (oSPARC handles the run phase only)
3. Download and extract: Retrieve results when jobs complete, then extract SAR data locally

**Important**: oSPARC only handles the run phase. You are responsible for running setup and extraction yourself. Each simulation runs as an independent job on oSPARC. Jobs get their own GPU, so they execute in parallel (unlike local parallel execution where jobs queue for a single GPU). If you use Sim4Life Python Runner on the oSPARC cloud for setup and extraction phases, you'll need licenses for those phases in addition to your local licenses.

## Setup

### API credentials

oSPARC requires API credentials stored in a `.env` file in the project root:

```
OSPARC_API_KEY=your_api_key_here
OSPARC_API_SECRET=your_api_secret_here
```

Get credentials from https://api.sim4life.science. The GOLIAT EU Project has access to dedicated resources. For individual use, check pricing and quotas.

### Configuration

Enable batch mode in your config:

```json
{
  "execution_control": {
    "do_setup": true,
    "only_write_input_file": true,
    "do_run": false,
    "do_extract": false,
    "batch_run": true
  }
}
```

Setup phase (`do_setup: true`, `only_write_input_file: true`): Creates `.h5` input files locally without running simulations. This is fast and doesn't require GPU.

Batch submission (`batch_run: true`): Uploads input files and submits jobs to oSPARC. GOLIAT monitors job status and downloads results automatically.

Extraction phase (`do_extract: true`): Processes downloaded results to extract SAR data. Run this after jobs complete.

## Workflow example

### Step 1: Generate input files

```bash
goliat study my_config.json
```

With `only_write_input_file: true`, this creates `.h5` files in your project directory. No GPU needed for this step.

### Step 2: Submit batch

```bash
goliat study my_config.json
```

With `batch_run: true`, GOLIAT uploads all input files and submits jobs. The GUI shows job status:

```
--- Submitting Jobs to oSPARC in Parallel ---
  - Submitted job 1/50: duke_700_x_pos_theta
  - Submitted job 2/50: duke_700_x_neg_theta
  ...
  - Job 1/50: PENDING
  - Job 2/50: SUCCESS (downloaded)
  - Job 3/50: RUNNING
```

### Step 3: Extract results

After jobs complete, set `do_extract: true` and run:

```bash
goliat study my_config.json
```

This processes downloaded `.h5` result files and generates SAR extraction JSON/PKL files.

## Job status

Jobs progress through these states:

- PENDING: Queued, waiting for compute resources
- RUNNING: Executing on oSPARC GPU node
- SUCCESS: Completed, results downloaded automatically
- FAILED: Error occurred (check logs in `logs/osparc_submission_logs/`)

Monitor jobs in the GOLIAT GUI or at https://api.sim4life.science.

## Limits and costs

oSPARC platform limits:

- Maximum ~61 parallel jobs per user
- Storage quotas (varies by plan)
- API rate limits (handled automatically by GOLIAT)

Costs depend on compute time and storage. The GOLIAT EU Project has dedicated resources. For individual use, check current pricing at the oSPARC dashboard.

## Troubleshooting

### Jobs stuck in PENDING

- Check oSPARC dashboard for resource availability
- Verify you haven't exceeded the 61-job limit
- Wait for compute resources to free up

### Submission failures

- Verify `.env` file exists with correct credentials
- Test credentials: run a single simulation first
- Check `logs/osparc_submission_logs/` for error details
- GOLIAT auto-retries failed submissions (3 attempts)

### Cancel stuck jobs

Cancel all running jobs for a config:

```bash
python scripts/cancel_all_jobs.py --config my_config.json
```

Cancel up to N recent jobs:

```bash
python scripts/cancel_all_jobs.py --config my_config.json --max-jobs 10
```

## Comparison with other methods

| Method | Simulations | GPU usage | Cost | Setup |
|:---|:---|:---|:---|:---|
| Local sequential | 1-10 | Single GPU, sequential | Free | None |
| Local parallel | 10-50 | Single GPU, queued | Free | None |
| oSPARC batch | 50-500+ | Multiple GPUs, parallel | Paid | API credentials |
| Cloud VMs | Any | Multiple GPUs, parallel | Paid | VM setup |

For true parallel GPU execution, use oSPARC batch or multiple cloud VMs. Local parallel execution only speeds up setup/extract phases, not the run phase.

## Related documentation

- [Tutorial 5: Parallel and cloud execution](../tutorials/05_parallel_and_cloud_execution.ipynb): Detailed workflow and examples
- [Cloud setup](cloud_setup.md): Setting up cloud VMs as alternative to oSPARC
- [Configuration reference](../developer_guide/configuration.md): All config parameters including `batch_run`
- [Troubleshooting](../troubleshooting.md): Common issues and solutions

