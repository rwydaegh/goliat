# ============================================================================
# One-shot SSH setup for a fresh Tensordock Windows VM.
# Run in PowerShell as Administrator. Idempotent — safe to re-run.
#
# Usage:
#   .\setup_tensordock_ssh.ps1 -PublicKey "ssh-ed25519 AAAA... user@host"
#
# After this runs, from the Linux side:
#   ssh -i ~/.ssh/<your_key> -p <ext> user@<vm_ip>
# where <ext> is whichever Tensordock external port forwards to internal :8888
# (Tensordock provisions one such forward by default; we re-purpose it for SSH
# so you don't have to add a :22 forward post-create).
#
# This script leaves DefaultShell at cmd.exe. After setup.bat installs Git,
# switch to bash via:
#   reg add "HKLM\SOFTWARE\OpenSSH" /v DefaultShell /t REG_SZ /d "C:\Program Files\Git\bin\bash.exe" /f
#   reg add "HKLM\SOFTWARE\OpenSSH" /v DefaultShellCommandOption /t REG_SZ /d "-lc" /f
# ============================================================================

param(
    [Parameter(Mandatory=$true)]
    [ValidatePattern('^ssh-(ed25519|rsa)\s+')]
    [string]$PublicKey
)

$ErrorActionPreference = 'Stop'

# --- 1. OpenSSH server ------------------------------------------------------
Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0 | Out-Null
Set-Service -Name sshd -StartupType 'Automatic'

# --- 2. Windows firewall (separate layer from Tensordock NAT) ---------------
foreach ($p in 22, 8888) {
    $name = "sshd_$p"
    if (-not (Get-NetFirewallRule -Name $name -ErrorAction SilentlyContinue)) {
        New-NetFirewallRule -Name $name -DisplayName "OpenSSH $p" `
            -Enabled True -Direction Inbound -Protocol TCP -Action Allow -LocalPort $p | Out-Null
    }
}

# --- 3. Authorized key for the admin account --------------------------------
# Windows quirk: for users in the Administrators group, sshd reads
# C:\ProgramData\ssh\administrators_authorized_keys (NOT ~/.ssh/authorized_keys),
# and the file ACL must be SYSTEM + Administrators only or sshd silently rejects it.
$keyf = "C:\ProgramData\ssh\administrators_authorized_keys"
if (-not (Test-Path $keyf)) { New-Item -Path $keyf -ItemType File -Force | Out-Null }
$existing = Get-Content $keyf -ErrorAction SilentlyContinue
if ($existing -notcontains $PublicKey) { Add-Content -Path $keyf -Value $PublicKey }
icacls.exe $keyf /inheritance:r /grant "Administrators:F" /grant "SYSTEM:F" | Out-Null

# --- 4. sshd_config: key-only, listen on :22 and :8888 ----------------------
# Port directives MUST be in the global section (before any Match block) or
# sshd treats them as Match-scoped and refuses to start.
$cfg   = "C:\ProgramData\ssh\sshd_config"
$lines = Get-Content $cfg

# Strip every uncommented "Port N" line so we can re-insert in the right spot.
$lines = $lines | Where-Object { $_ -notmatch '^\s*Port\s+\d+\s*$' }

# Toggle auth modes (replace if present, else leave defaults — sshd defaults
# to PubkeyAuthentication yes already).
$lines = $lines `
    -replace '^\s*#?\s*PasswordAuthentication.*', 'PasswordAuthentication no' `
    -replace '^\s*#?\s*PubkeyAuthentication.*',   'PubkeyAuthentication yes'

# Find first Match line; Port lines go BEFORE it.
$matchIdx = -1
for ($i = 0; $i -lt $lines.Count; $i++) {
    if ($lines[$i] -match '^\s*Match\s') { $matchIdx = $i; break }
}
if ($matchIdx -lt 0) { $matchIdx = $lines.Count }

$portBlock = @('Port 22', 'Port 8888', '')
$new = @()
if ($matchIdx -gt 0) { $new += $lines[0..($matchIdx - 1)] }
$new += $portBlock
if ($matchIdx -lt $lines.Count) { $new += $lines[$matchIdx..($lines.Count - 1)] }
Set-Content -Path $cfg -Value $new

# --- 5. Default shell = cmd.exe (Git/bash isn't installed yet on a fresh VM) -
$reg = 'HKLM:\SOFTWARE\OpenSSH'
if (-not (Test-Path $reg)) { New-Item -Path $reg -Force | Out-Null }
New-ItemProperty -Path $reg -Name DefaultShell `
    -Value 'C:\Windows\System32\cmd.exe' -PropertyType String -Force | Out-Null

# --- 5b. Give admin SSH sessions a full elevated token ----------------------
# Without this, UAC filters the token of admins logging in non-interactively
# (incl. SSH pubkey), so commands that need elevation silently fail. Setting
# LocalAccountTokenFilterPolicy=1 lifts that filtering for local-account admins.
New-ItemProperty -Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System' `
    -Name LocalAccountTokenFilterPolicy -PropertyType DWord -Value 1 -Force | Out-Null

# --- 6. Start / restart -----------------------------------------------------
Restart-Service sshd

# --- 7. Verify --------------------------------------------------------------
Write-Host "`n=== Verification ===" -ForegroundColor Cyan
Get-Service sshd | Format-Table Status, Name, DisplayName
Get-NetTCPConnection -LocalPort 22, 8888 -ErrorAction SilentlyContinue |
    Format-Table LocalAddress, LocalPort, State
Write-Host "Logged-in user: $env:USERNAME" -ForegroundColor Yellow
