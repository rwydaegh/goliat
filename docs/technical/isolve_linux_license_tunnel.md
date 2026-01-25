# Running iSolve on Remote Linux VM with University License Server

## The Problem

You have:
- **iSolve/Sim4Life** installed on a remote Linux VM (e.g., TensorDock cloud server in the USA)
- A **university license server** (FlexNet) that's only accessible from the university network
- Your **Windows laptop** connected to the university VPN
- **VNC** access to the Linux VM through an SSH tunnel

The challenge: The Linux VM cannot directly reach the university license server because it's outside the university network.

## The Solution: SSH Reverse Tunnel

Use your Windows laptop (on VPN) as a **bridge** between the remote Linux VM and the university license server.

```
┌─────────────┐     SSH Tunnel      ┌─────────────┐      VPN        ┌─────────────────┐
│  Linux VM   │◄───────────────────►│   Windows   │◄───────────────►│ License Server  │
│  (USA)      │   Reverse Tunnel    │   Laptop    │   University    │ (UGent)         │
│  iSolve     │   Port 51380        │   (on VPN)  │   Network       │ Port 51380      │
└─────────────┘                     └─────────────┘                 └─────────────────┘
```

---

## Step-by-Step Setup

### 1. Install iSolve on Linux VM

```bash
# Download and extract the .deb packages
mkdir ~/Downloads/isolve
cd ~/Downloads/isolve
# (transfer your installer files here)
unzip <installer_archive>

# Install the packages
sudo apt install ./isolve-sim4life_9.2.1-19976_amd64.deb
# If dependencies are missing:
sudo apt-get install -f

# Optionally install neuron package
sudo apt install ./isolve-neuron_9.2.1-19976_amd64.deb
```

### 2. Find the Correct License Server Port

The license server port is often NOT the default FlexNet port (27000). To find the actual port:

**On Windows (while Sim4Life is running):**
```powershell
Get-NetTCPConnection | Where-Object {$_.RemoteAddress -eq "<LICENSE_SERVER_IP>"} | Select-Object LocalPort, RemotePort, State
```

In our case, the license server `wicacib.private.ugent.be` (IP: `172.18.30.92`) uses **port 51380**.

### 3. Create the SSH Reverse Tunnel

**From your Windows laptop (connected to university VPN):**

```bash
ssh -p <VM_SSH_PORT> -i ~/.ssh/<YOUR_KEY> \
    -R 51380:<LICENSE_SERVER_IP>:51380 \
    user@<VM_IP_ADDRESS>
```

**Concrete example for this setup:**
```bash
ssh -p 20400 -i ~/.ssh/tensordock_key -R 51380:172.18.30.92:51380 user@174.94.145.71
```

**Combined with VNC tunnel:**
```bash
ssh -p 20400 -i ~/.ssh/tensordock_key \
    -L 5901:localhost:5901 \
    -R 51380:172.18.30.92:51380 \
    user@174.94.145.71
```

### 4. Configure and Run iSolve

**On the Linux VM:**

```bash
# Set the license server to use localhost (the tunnel endpoint)
export LM_LICENSE_FILE=51380@localhost

# Navigate to iSolve
cd /usr/local/isolve-sim4life_9.2.1-19976_amd64/bin

# Run iSolve with your simulation file
./iSolve ~/path/to/your/simulation.h5
```

---

## Troubleshooting

### Verify the tunnel is working

**On Linux VM:**
```bash
# Check if the port is listening
ss -tlnp | grep 51380

# Test connectivity
nc -zv localhost 51380
# Should output: Connection to localhost 51380 port [tcp/*] succeeded!
```

### Common errors and fixes

| Error | Cause | Fix |
|-------|-------|-----|
| `License server machine is down or not responding` | Tunnel not established or wrong port | Verify tunnel is running and port is correct |
| `Cannot read data from license server system` | Partial connection, possibly wrong/missing vendor daemon port | Check the actual port using PowerShell command above |
| `remote port forwarding failed for listen port` | Port already in use by another SSH session | Close all SSH sessions and reconnect |
| `Address already in use` on local forward | Another tunnel is using that port | This is fine if it's from another session doing the same thing |

### X Display issues (for GUI apps)

If running graphical applications through VNC terminal:
```bash
export DISPLAY=:1
xhost +local:
# Now run your GUI app
```

---

## Quick Reference

### Environment Details
- **Linux VM**: Ubuntu 24.04, TensorDock cloud (174.94.145.71:20400)
- **License Server**: wicacib.private.ugent.be (172.18.30.92)
- **License Port**: 51380 (NOT the default 27000!)
- **VNC Port**: 5901
- **iSolve Version**: 9.2.1

### One-liner command (VNC + License Tunnel)
```bash
ssh -p 20400 -i ~/.ssh/tensordock_key -L 5901:localhost:5901 -R 51380:172.18.30.92:51380 user@174.94.145.71
```

### On VM before running iSolve
```bash
export LM_LICENSE_FILE=51380@localhost
/usr/local/isolve-sim4life_9.2.1-19976_amd64/bin/iSolve <your_file.h5>
```

---

## Key Insights

1. **Finding the license port is critical** - Don't assume it's 27000. Use `Get-NetTCPConnection` on Windows while the licensed software is running.

2. **Use IP address instead of hostname** in the tunnel - The hostname resolution happens on your laptop, so it should work either way, but IP is more reliable.

3. **Reverse tunnel (-R) vs Forward tunnel (-L)**:
   - `-L` (forward): Access remote service from local machine
   - `-R` (reverse): Access local network service from remote machine

4. **Close old SSH sessions** before creating new tunnels to avoid "port already in use" errors.

---

## Date
Solution documented: 2026-01-23
