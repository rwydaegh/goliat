# Monitoring dashboard

**Dashboard:** [https://goliat.waves-ugent.be](https://goliat.waves-ugent.be)

Web-based interface for monitoring GOLIAT simulation studies across multiple worker machines. Track progress, monitor worker status, and coordinate large-scale studies.

![Dashboard Overview](../img/cloud/monitoring_dashboard.png)

*The main dashboard showing an overview of all workers and their status.*

## Overview

The dashboard shows:

- Status of all worker machines in one place
- Real-time progress bars, stage information, and ETA for each worker
- Super study coordination across multiple workers
- Color-coded log messages from each worker
- GPU, CPU, and RAM information for each worker

## Features

### Worker status monitoring

Each worker shows:

- Status indicator: Green (online/idle), Blue (running), Red (offline/error)
- Progress percentage: Overall completion (0-100%)
- Current stage: Simulation stage (e.g., "Setup", "Run", "Extract")
- Time remaining: Estimated completion time
- Warnings and errors: Count of issues encountered
- System specs: GPU model, CPU cores, RAM capacity
- Last seen: When the worker last sent a heartbeat

![Workers Page](../img/cloud/monitoring_workers.png)

*The workers page showing detailed information about each worker machine.*

### Real-time progress tracking

The dashboard shows:

- Overall progress: Percentage completion for each worker
- Stage progress: Progress within the current simulation stage
- Master progress: Aggregated progress across all workers in a super study
- ETA: Estimated time to completion based on current progress rate

### Live log streaming

Log messages stream to the dashboard in real-time with color-coded formatting:

- Green: Success messages
- Yellow: Warnings
- Red: Errors
- Cyan: Info messages
- Gray: Standard progress messages

### Super studies

Super studies split a large configuration file into multiple assignments and distribute them across workers:

![Super Studies](../img/cloud/monitoring_super_studies.png)

*The super studies page showing distributed studies across multiple workers.*

- Automatic splitting: Config files split into N assignments
- Worker assignment: Workers claim and run available assignments automatically
- Progress aggregation: Master progress bar shows overall completion
- Assignment tracking: See which worker runs which assignment

## How it works

### Automatic connection

When you run a GOLIAT study with web monitoring enabled, the GUI:

1. Detects your machine's public IP address (or uses local IP if no public IP)
2. Connects to the monitoring dashboard at `https://goliat.waves-ugent.be`
3. Sends periodic heartbeats every 30 seconds
4. Forwards GUI messages (progress, logs, status) to the dashboard

### Connection status indicator

The GOLIAT GUI shows a connection status indicator:

- Green dot: Successfully connected to dashboard
- Red dot: Connection failed or dashboard unavailable

The GUI continues to function normally even if the dashboard connection fails.

### Message forwarding

The GUI bridge forwards messages to the dashboard:

- Progress updates: Overall and stage progress percentages
- Status messages: Log messages with color coding
- System information: GPU, CPU, RAM, hostname
- Heartbeats: Periodic messages every 30 seconds

Messages are throttled to prevent overwhelming the API (typically 10 messages/second).

## Usage

### Enabling web monitoring

Web monitoring enables automatically when:

1. The `requests` library is installed (`pip install requests`)
2. A machine ID can be detected (public IP or local IP)
3. The dashboard URL is accessible

No configuration required. GOLIAT connects to the hardcoded dashboard URL automatically.

### Viewing worker details

Click "View Details" on any worker to see:

- Detailed progress information
- Recent log messages (last 50)
- System specifications (GPU, CPU, RAM)
- Worker metadata (IP address, hostname, machine label)

### Creating super studies

Create a super study:

```bash
goliat super_study configs/near_field_config.json \
  --name my_study \
  --num-splits 8 \
  --description "Distributed study across 8 workers"
```

This splits your config into 8 assignments, uploads them to the dashboard, and displays the super study ID and dashboard URL.

### Running workers

On each worker machine:

```bash
export GOLIAT_WEBGUI_ENABLED=true
goliat worker 0 my_study  # Worker 0 runs assignment 0
goliat worker 1 my_study  # Worker 1 runs assignment 1
# ... and so on
```

Each worker fetches its assigned config from the dashboard, claims the assignment, runs the simulation, reports progress in real-time, and marks the assignment complete when finished.

When deploying multiple cloud VMs, the monitoring dashboard provides a centralized view of all workers. See [Cloud setup](cloud_setup.md) for instructions on setting up cloud GPU instances.

## Technical details

### Worker identification

Workers are identified by their IP address. If a worker's IP changes (e.g., VPN reconnection), it may appear as a new worker. The dashboard handles this by matching workers by hostname when IP changes, transferring running assignments to the new worker session, and marking stale workers (no heartbeat for 5+ minutes) as inactive.

### Message throttling

To prevent API overload, messages are throttled:

- Progress updates: Up to 50 Hz (immediate for progress)
- Log messages: Batched every 300ms (up to 20 messages per batch)
- Heartbeats: Every 30 seconds

### Offline behavior

If the dashboard is unavailable, the GUI continues to function normally. Progress is still displayed locally, the connection status indicator shows red, and messages are silently dropped (not queued).

### Privacy and security

The dashboard is publicly accessible (no authentication required). Workers are identified by IP address only. No sensitive data (passwords, API keys) is transmitted. Log messages may contain simulation details but no credentials.

## Troubleshooting

### Worker not appearing

If your worker doesn't appear on the dashboard:

1. Check connection: Look for the green/red status indicator in the GOLIAT GUI
2. Verify network: Ensure the worker can reach `https://goliat.waves-ugent.be`
3. Check requests library: Ensure `pip install requests` has been run
4. Check logs: Look for "Web GUI bridge" messages in verbose logs

### Connection status red

If the connection indicator is red, the dashboard may be temporarily unavailable, there may be network connectivity issues, a firewall may be blocking HTTPS connections, or the `requests` library may not be installed.

The GUI continues to work normally. You just won't see updates on the web dashboard.

### Stale workers

Workers that haven't sent a heartbeat in 5+ minutes are marked as stale. This is normal if the worker finished its study and stopped, lost network connectivity, or was shut down.

Stale workers are automatically resolved when a new worker session starts with the same hostname.

## Related documentation

- [Cloud setup](cloud_setup.md): Instructions for deploying and configuring cloud GPU instances that can serve as monitoring dashboard workers
- [Super Studies](super_studies.md): Detailed guide on creating and managing super studies
- [Troubleshooting](../troubleshooting.md): General troubleshooting guide

