# Cloud GPU setup

Don't have a GPU or sufficient resources on your local machine? For approximately €0.17-1.80 per hour (depending on GPU model), you can rent GPU instances from cloud providers to run GOLIAT simulations. This guide walks you through setting up a cloud Windows VM with GPU support.

## Overview

This setup allows you to:

1. Deploy a Windows VM with GPU support (from RTX 4090 to H100) via cloud providers
2. RDP into the machine remotely
3. Automatically install and configure everything needed to run GOLIAT
4. Launch simulations with minimal manual intervention

The entire setup process takes approximately 10 minutes and is fully automated once you copy the setup script to the VM.

## Prerequisites

- A cloud provider account (this guide uses TensorDock as an example, but the process is similar for other providers)
- Basic familiarity with Remote Desktop Protocol (RDP)
- Access to Sim4Life installer and license (these are downloaded automatically or can be provided manually)

## Step 1: Deploy a GPU instance

### Option A: Using the web interface

1. Visit [TensorDock Dashboard](https://dashboard.tensordock.com/deploy)
2. Select your GPU model (e.g., RTX 4090)
3. Configure resources:
   - **CPU**: 8+ cores recommended
   - **RAM**: 32 GB+ recommended
   - **Storage**: 250 GB+ recommended
   - **OS**: Windows 10 or Windows 11
4. Prefer **Dedicated IP** if available
5. Set a secure password for the VM
6. Deploy the instance

### Option B: Using the Python script

A Python script is provided in `cloud_setup/deploy_windows_vm.py` to automate VM deployment via the TensorDock API:

```bat
:: From the repository root:
copy .env.example .env
:: Set TENSORDOCK_API_TOKEN and TENSORDOCK_VM_PASSWORD in .env.

python cloud_setup\deploy_windows_vm.py
```

The same `.env` file is used by `gpu_dashboard.py`. It is ignored by Git; `.env.example` documents the supported variables without containing credentials. Rotate a token immediately if it is ever committed or printed in a log.

## Step 2: Connect via RDP

Once your VM is deployed:

1. Find the **public IP address** in your provider's dashboard
2. Use Windows Remote Desktop Connection (or any RDP client)
3. Connect using:
   - **IP**: The public IP from the dashboard
   - **Username**: Usually `Administrator` or `user` (check provider docs)
   - **Password**: The password you set during deployment

## Step 3: Run the setup script

The `cloud_setup/` directory contains a unified setup script that handles both fresh installation and reconnection scenarios.

### What the script does

The `setup.bat` script **automatically detects** whether GOLIAT has already been installed by checking if the `goliat/` folder exists in the user's home directory.

#### Fresh installation (goliat/ not found)

If this is a new machine, the script runs the **full setup flow**:

1. Checks computer name and administrator privileges
2. Downloads and installs OpenVPN
3. Downloads and installs Python 3.11
4. Installs gdown utility for Google Drive downloads
5. Downloads and installs Sim4Life
6. Downloads VPN configuration files
7. Connects to VPN (if required for Sim4Life license access)
8. Installs Git and clones the GOLIAT repository
9. Automatically configures Sim4Life license (enters license server, validates, and completes installation)
10. Git Bash automatically runs initialization commands (pip install, git config, goliat init)

#### Reconnection (goliat/ found)

If the setup has already been completed, the script runs the **reconnection flow**:

1. Connects to VPN
2. Opens File Explorer at the goliat/ directory
3. Launches Git Bash with automatic commands:
   - Sets git safe.directory
   - Configures git user.email and user.name
   - Runs `git pull` to fetch latest changes
   - Leaves the terminal ready for use

This means you only need **one script** - just run `setup.bat` every time you connect to the VM.

### Running the script

1. Copy `cloud_setup/setup.bat` to the VM.

2. Copy `.env.example` to `.env`, fill the `GOLIAT_*` bootstrap settings and
   `SIM4LIFE_LICENSE_SERVER`, and place that `.env` beside `setup.bat`. Do not
   edit credentials into the batch file. The local dashboard sends a filtered
   bootstrap `.env` automatically and never sends the TensorDock API token.

3. **Run as Administrator**:

   ```cmd
   Right-click setup.bat → Run as administrator
   ```

4. **First run**: Wait ~10 minutes while the script installs everything. License configuration is automated (takes 30-60 seconds for validation). If VPN is not connected, the license step will fail with a clear error message - you can configure it manually later.

5. **Subsequent runs**: The script detects the existing installation and runs the quick reconnection flow (~15 seconds).

## File structure

The `cloud_setup/` directory contains:

- **`setup.bat`**: Unified setup script for fresh installation and reconnection; reads settings from a neighboring `.env`
- **`license_automation.py`**: Automates Sim4Life license configuration, accepts `--license-server` argument
- **`deploy_windows_vm.py`**: Python script for API-based VM deployment; reads credentials from `.env`
- **`gpu_dashboard.py`**: Local VM dashboard; reads `TENSORDOCK_API_TOKEN` from `.env`

Do not create parallel credential-bearing source copies. Keep all local values
in `.env`, which is ignored by Git. Delete the VM copy when it is no longer
needed, and restrict access to the VM account because it contains bootstrap
credentials.

## Cost estimation

TensorDock pricing varies by GPU model and location, ranging from approximately **€0.17-1.80/hour**:

**Enterprise GPUs**: H100 (~€1.80/hr), A100 (~€0.78/hr), L40S (~€0.60/hr), Tesla V100 (~€0.19-0.27/hr)

**Workstation RTX GPUs**: RTX PRO 6000 (~€0.91/hr), RTX 6000 ADA (~€0.64/hr), RTX 5090 (~€0.45/hr), RTX A6000 (~€0.36/hr), RTX 4090 (~€0.32/hr), RTX 3090 (~€0.18/hr)

**Notable features**:

- High-memory configurations available (up to 512 GB RAM)
- Per-second billing with no minimum commitment
- Instances can be stopped when not in use to minimize costs

**Monthly estimate** (assuming 730 hours): ~€15-130/month for running instances, plus storage costs when stopped.

For current pricing and availability, consult TensorDock's dashboard directly.

### Provider comparison

**Hyperscalers (GCP, Azure, AWS):** Can create VM images/snapshots and duplicate them to new instances, but quota requests for GPU instances can take days or weeks to be approved. Generally higher pricing.

**Specialized GPU providers (e.g., TensorDock):** No quota requests - instant GPU access. Lower pricing (typically 20-40% cheaper than hyperscalers). Image duplication feature may be available depending on provider.

## Alternative providers

While this guide focuses on TensorDock, similar setups work with AWS EC2 (G4/G5 instances with Windows Server), Google Cloud Platform (GPU-enabled Windows VMs), and Azure (NV-series VMs with Windows). The setup script may need minor modifications for different providers (e.g., different default usernames, network configurations).

## Headless / SSH access

For managing the VM programmatically from a Linux host, see [`cloud_setup/ssh/README.md`](https://github.com/rwydaegh/goliat/blob/master/cloud_setup/ssh/README.md). It documents a one-shot script to enable key-only OpenSSH on the VM (reusing the Tensordock `:8888` port forward, locked-down ACL on `administrators_authorized_keys`, elevated admin tokens for SSH sessions), plus the conventions for running `goliat study` from SSH.

## Related documentation

- [oSPARC](osparc.md): Cloud batch execution via oSPARC platform (alternative to VM setup)
- [Monitoring dashboard](monitoring.md): When running studies across multiple cloud VMs, use the monitoring dashboard to track progress, view logs, and coordinate super studies across all workers
- [SSH bring-up](https://github.com/rwydaegh/goliat/blob/master/cloud_setup/ssh/README.md): Manage the VM from a Linux host
