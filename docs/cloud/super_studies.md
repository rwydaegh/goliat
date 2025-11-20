# Super Studies - Distributed Execution

Super Studies allow you to split a large GOLIAT configuration into multiple smaller pieces and distribute them across multiple workers.

## Overview

A Super Study:
- Splits a config file into N assignments (similar to `goliat parallel`)
- Uploads the split configs to the web dashboard
- Allows workers to claim and run individual assignments
- Tracks progress across all assignments

## Usage

### 1. Create a Super Study

On your control machine:

```bash
# Optional: set custom dashboard URL (defaults to https://monitor.goliat.waves-ugent.be)
export GOLIAT_MONITORING_URL=https://your-dashboard.com
goliat super_study configs/near_field_config.json --name my_study --num-splits 8
```

This will:
- Split `near_field_config.json` into 8 assignments
- Upload them to the web dashboard
- Display the super study ID

### 2. Run Workers

On each worker machine:

```bash
# Optional: set custom dashboard URL (defaults to https://monitor.goliat.waves-ugent.be)
export GOLIAT_MONITORING_URL=https://your-dashboard.com
export GOLIAT_WEBGUI_ENABLED=true

# Worker 0 runs assignment 0
goliat worker 0 my_study

# Worker 1 runs assignment 1
goliat worker 1 my_study

# ... and so on
```

Each worker will:
- Fetch its assigned config from the web
- Claim the assignment
- Run the simulation
- Report progress to the dashboard

## Commands

### `goliat super_study`

Creates a super study and uploads it to the web dashboard.

```bash
goliat super_study <config> --name <name> [options]
```

**Arguments:**
- `config`: Path to the configuration file to split
- `--name`: Name for the super study (used by workers)
- `--description`: Optional description
- `--num-splits`: Number of assignments to create (default: 4)
- `--server-url`: Dashboard URL (default: from `GOLIAT_MONITORING_URL` env var, or `https://monitor.goliat.waves-ugent.be`)

**Example:**
```bash
goliat super_study configs/near_field_config.json \
  --name full_study_2025 \
  --description "Complete 9-frequency study across 2 phantoms" \
  --num-splits 16
```

### `goliat worker`

Runs a specific assignment from a super study.

```bash
goliat worker <assignment_index> <super_study_name> [options]
```

**Arguments:**
- `assignment_index`: Index of the assignment to run (0-based)
- `super_study_name`: Name of the super study
- `--title`: GUI window title
- `--no-cache`: Force re-running even if cached
- `--server-url`: Dashboard URL (default: from `GOLIAT_MONITORING_URL` env var, or `https://monitor.goliat.waves-ugent.be`)

**Example:**
```bash
goliat worker 0 full_study_2025 --title "Worker 0"
```

## Splitting Strategy

The splitting algorithm (same as `goliat parallel`):
1. Prioritizes splitting phantoms first
2. Then splits frequencies/antennas
3. Creates a cartesian product for the final assignments

**Example:** 2 phantoms × 9 frequencies with `--num-splits 6`:
- Will create 2 phantom groups × 3 frequency groups = 6 assignments
- Each assignment gets 1 phantom and 3 frequencies

## API Endpoints

### Create Super Study
```
POST /api/super-studies
{
  "name": "my_study",
  "description": "Study description",
  "baseConfig": {...},
  "assignments": [
    {"splitConfig": {...}, "status": "PENDING"},
    ...
  ]
}
```

### List Super Studies
```
GET /api/super-studies?name=my_study
```

### Get Assignments
```
GET /api/super-studies/{id}/assignments
```

### Claim Assignment
```
POST /api/assignments/{id}/claim
{
  "machineId": "192.168.1.100"
}
```

## Comparison with `goliat parallel`

| Feature | `goliat parallel` | Super Studies |
|---------|-------------------|---------------|
| **Splitting** | Local, creates files | Client-side split, uploaded to server |
| **Execution** | All on one machine | Distributed across workers |
| **Coordination** | Manual | Automatic via web |
| **Progress Tracking** | Local GUIs only | Centralized dashboard |
| **Worker Assignment** | Manual | Workers claim assignments |
| **Use Case** | Single powerful machine | Multiple machines/VMs |

## Best Practices

1. **Set Environment Variables (optional):**

   ```bash
   export GOLIAT_MONITORING_URL=https://your-dashboard.com
   export GOLIAT_WEBGUI_ENABLED=true
   ```
   
   If `GOLIAT_MONITORING_URL` is not set, the default dashboard URL `https://monitor.goliat.waves-ugent.be` will be used.

2. **Name Studies Clearly:** Use descriptive names like `full_9freq_2phantoms_2025`

3. **Choose Appropriate Splits:** Match the number of splits to your available workers

4. **Monitor Progress:** Check the web dashboard to see which assignments are running/completed

5. **Handle Failures:** If a worker fails, another worker can claim the same assignment (implement retry logic)

## Future Enhancements

- Automatic worker assignment (workers pull next available assignment)
- Retry logic for failed assignments
- Result aggregation and analysis
- Worker pool management
- Priority queues for assignments

