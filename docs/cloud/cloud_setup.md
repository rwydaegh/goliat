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

```python
# Edit deploy_windows_vm.py and set your credentials:
API_TOKEN = "YOUR_TENSORDOCK_API_TOKEN"
# ... other configuration ...

# Then run:
python deploy_windows_vm.py
```

**Note**: The template script (`deploy_windows_vm.py`) contains placeholders. Copy it to `my_deploy_windows_vm.py` and fill in your actual credentials. The `my_*.py` files are gitignored.

## Step 2: Connect via RDP

Once your VM is deployed:

1. Find the **public IP address** in your provider's dashboard
2. Use Windows Remote Desktop Connection (or any RDP client)
3. Connect using:
   - **IP**: The public IP from the dashboard
   - **Username**: Usually `Administrator` or `user` (check provider docs)
   - **Password**: The password you set during deployment

## Step 3: Run the setup script

The `cloud_setup/` directory contains an automated setup script that installs everything needed:

### What the script does

The `setup_and_run.bat` script automates the following steps:

1. Checks computer name (configurable)
2. Checks for administrator privileges
3. Downloads OpenVPN installer
4. Downloads and installs Python 3.11
5. Installs gdown utility for Google Drive downloads
6. Downloads and installs Sim4Life
7. Downloads VPN configuration files (if needed)
8. Installs OpenVPN and connects to VPN (if required for Sim4Life license access)
9. Installs Git and clones the GOLIAT repository
10. Launches Sim4Life license installer and Git Bash in parallel

The script includes error handling to prevent premature execution and verifies that required files exist before launching processes.

### Running the script

1. **Copy the setup script** to your VM (you can use RDP file transfer or download it)

2. **Edit the script** if needed:
   - Replace `YOUR_COMPUTER_NAME` with the expected computer name (or remove the check if not needed)
   - Replace `YOUR_PRIVATE_GDRIVE_FOLDER_ID` with your Google Drive folder ID which should contain your `.ovpn` and `.crt` files.
   - Replace `YOUR_PRIVATE_GDRIVE_FILE_ID` with your Sim4Life `.exe` installer (for private use *only* with the express intent to *only* transfer this to the remote machine).
   - Replace `YOUR_VPN_USERNAME` and `YOUR_VPN_PASSWORD` if using VPN
   - Replace `YOUR_USERNAME` with your GitHub username

3. **Run as Administrator**:

        ```cmd
        Right-click setup_and_run.bat → Run as administrator
        ```

4. **Wait ~10 minutes** while the script installs everything

5. **Both windows launch simultaneously**:
   - The Sim4Life license installer opens automatically
   - Git Bash launches in the GOLIAT repository directory with initialization commands already executed
   - You can install the license while working in Git Bash

6. **Git Bash is ready to use**: The script automatically runs initialization commands from `start.sh` (pip install, git config, goliat init), so the terminal is ready for immediate use

## VPN reconnection

If you need to reconnect to VPN later without rerunning the full setup, use `connect_vpn.bat`:

```cmd
Right-click connect_vpn.bat → Run as administrator
```

**Note**: Before running `connect_vpn.bat`, edit it to replace `YOUR_VPN_USERNAME` and `YOUR_VPN_PASSWORD` with your actual VPN credentials. This script assumes OpenVPN is already installed and that the VPN configuration files exist in the `certs/` directory.

## File structure

The `cloud_setup/` directory contains:

- **`setup_and_run.bat`**: Complete automated setup (template with placeholders for open source use)
- **`my_setup_and_run.bat`**: Personal copy with actual credentials (gitignored)
- **`connect_vpn.bat`**: VPN reconnection script (template)
- **`my_connect_vpn.bat`**: Personal VPN script with credentials (gitignored)
- **`deploy_windows_vm.py`**: Python script for API-based VM deployment (template)
- **`my_deploy_windows_vm.py`**: Personal deployment script with credentials (gitignored)

The `my_*` versions contain actual credentials and are gitignored. The template versions use placeholders like `YOUR_VPN_USERNAME` for open source distribution.

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

## Related documentation

- [oSPARC](osparc.md): Cloud batch execution via oSPARC platform (alternative to VM setup)
- [Monitoring dashboard](monitoring.md): When running studies across multiple cloud VMs, use the monitoring dashboard to track progress, view logs, and coordinate super studies across all workers
