# ============================================================================
# One-shot SSH setup for a fresh Blue Lobster Windows VM.
# Run in PowerShell as Administrator. Idempotent - safe to re-run.
#
# Usage (over RDP, PowerShell as Admin):
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
#   .\setup_bluelobster_ssh.ps1 -PublicKey "ssh-ed25519 AAAA... user@host"
#
# Differs from the Tensordock version (setup_tensordock_ssh.ps1):
#   * Blue Lobster gives the VM a REAL public IP with native ports - there is no
#     :8888 NAT to repurpose, so sshd listens on the standard :22 only.
#   * Inbound :22 must also be opened in the Blue Lobster *cloud* firewall
#     (separate layer, done via the API from the Linux side - see ssh/README.md).
#     This script only handles the Windows firewall + OpenSSH config.
#   * The cloudbase-init admin account is "Admin", so SSH lands as Admin.
#
# After this runs, from the Linux side:  ssh -i ~/.ssh/goliat Admin@<public_ip>
#
# Leaves DefaultShell at cmd.exe. After setup.bat installs Git, switch to
# bash via:
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

# --- 2. Windows firewall (separate layer from the Blue Lobster cloud firewall) -
$name = "sshd_22"
if (-not (Get-NetFirewallRule -Name $name -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -Name $name -DisplayName "OpenSSH 22" `
        -Enabled True -Direction Inbound -Protocol TCP -Action Allow -LocalPort 22 | Out-Null
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

# --- 4. sshd_config: key-only, listen on :22 --------------------------------
# Port directives MUST be in the global section (before any Match block) or
# sshd treats them as Match-scoped and refuses to start.
$cfg = "C:\ProgramData\ssh\sshd_config"

# The OpenSSH capability only writes the default sshd_config on the service's
# FIRST start, so on a brand-new box $cfg won't exist yet. Materialize it.
if (-not (Test-Path $cfg)) {
    $default = "$env:WINDIR\System32\OpenSSH\sshd_config_default"
    New-Item -ItemType Directory -Force -Path (Split-Path $cfg) | Out-Null
    if (Test-Path $default) {
        Copy-Item $default $cfg -Force
    } else {
        Start-Service sshd        # generates the default config, then stop to edit it
        Start-Sleep -Seconds 2
        Stop-Service sshd
    }
}

$lines = Get-Content $cfg

# Strip every uncommented "Port N" line so we can re-insert in the right spot.
$lines = $lines | Where-Object { $_ -notmatch '^\s*Port\s+\d+\s*$' }

# Toggle auth modes (replace if present; sshd defaults to PubkeyAuthentication yes).
$lines = $lines `
    -replace '^\s*#?\s*PasswordAuthentication.*', 'PasswordAuthentication no' `
    -replace '^\s*#?\s*PubkeyAuthentication.*',   'PubkeyAuthentication yes'

# Find first Match line; the Port directive goes BEFORE it.
$matchIdx = -1
for ($i = 0; $i -lt $lines.Count; $i++) {
    if ($lines[$i] -match '^\s*Match\s') { $matchIdx = $i; break }
}
if ($matchIdx -lt 0) { $matchIdx = $lines.Count }

$portBlock = @('Port 22', '')
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
Get-NetTCPConnection -LocalPort 22 -ErrorAction SilentlyContinue |
    Format-Table LocalAddress, LocalPort, State
Write-Host "Logged-in user: $env:USERNAME" -ForegroundColor Yellow
Write-Host "Remember: open tcp/22 in the Blue Lobster cloud firewall too (API)." -ForegroundColor Yellow
