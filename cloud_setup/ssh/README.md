# SSH bring-up for a fresh Tensordock Windows VM

This directory has the one-shot script + procedure to get key-only SSH access
from a Linux box to a freshly provisioned Tensordock Windows VM, so an agent
can drive `my_setup.bat` and goliat from the Linux side.

## Current state (as of 2026-04-25)

There is **one VM already set up** following the procedure below. From this
Linux box (`/home/user`), you can reach it with `ssh goliat` — alias is in
`~/.ssh/config`, key is `~/.ssh/goliat`. `my_setup.bat` has been run, license
installed manually, and SSH already lands in bash (`~/goliat` is on the VM).
Connection details: `40.142.110.132:20819` → internal `:8888`. If the VM has
been torn down or recycled by the time you're reading this, follow the
from-scratch steps below; otherwise just `ssh goliat` and go.

## Prereqs

- A Tensordock Windows VM you can RDP into.
- An ed25519 keypair on the Linux box: `ssh-keygen -t ed25519 -f ~/.ssh/goliat`.
- The Tensordock VM panel showing its public IP and **forwarded ports**. A new
  VM ships with at least one external→internal mapping besides RDP — typically
  `<some_external_port> → :8888`. The script makes sshd listen on internal
  `:8888` (and `:22`), so you re-purpose that existing forward for SSH.
  No need to add a `:22` mapping (which you often can't post-create).

## Step 1 — get your public key on the Linux box

```bash
cat ~/.ssh/goliat.pub
```

## Step 2 — run the script on the VM (RDP, PowerShell as Admin)

Save `setup_tensordock_ssh.ps1` to the Desktop, then:

```powershell
cd $HOME\Desktop
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\setup_tensordock_ssh.ps1 -PublicKey "ssh-ed25519 AAAA... your-key-here"
```

Idempotent. The script:

1. Installs OpenSSH Server, autostart, firewall rules for `:22` and `:8888`.
2. Drops your public key into `C:\ProgramData\ssh\administrators_authorized_keys`
   with the **required** locked ACL (SYSTEM + Administrators only — sshd
   silently rejects the file otherwise; this is the #1 footgun on Windows).
3. Writes `Port 22` + `Port 8888` to `sshd_config` **before** any `Match` block
   (Port directives in a Match scope are a parse error).
4. Sets `LocalAccountTokenFilterPolicy=1` — without it, admin SSH sessions get
   a UAC-filtered token and `net session`, MSI installers, etc. silently fail.
5. Sets `DefaultShell` to `cmd.exe` (bash isn't installed yet on a fresh VM).

## Step 3 — `~/.ssh/config` on the Linux box

From the Tensordock panel, grab:
- Public IP (e.g. `40.142.110.132`)
- The external port mapped to `:8888` (e.g. `20819`)

```
Host goliat
    HostName 40.142.110.132
    Port 20819
    User user
    IdentityFile ~/.ssh/goliat
    StrictHostKeyChecking accept-new
```

Test: `ssh goliat 'whoami'` should return `<vm-hostname>\user`.

## Step 4 — run `my_setup.bat`

This is the long step (~10–15 min on a 3090 VM). The bat is interactive-by-design
and assumes "right-click → Run as administrator". A few launch mechanisms that
*don't* work cleanly over SSH:

- Foreground SSH (`ssh goliat 'cmd /c my_setup.bat'`): SSH disconnect on the
  Linux side will SIGHUP the cmd, killing the install mid-flight.
- `powershell -Command "Start-Process -WindowStyle Hidden ..."`: the spawned
  process *appears* detached but actually dies when its parent SSH session
  closes on this VM image. Don't use it.

**Use `schtasks`** — it's the only reliable detach. From the Linux box:

```bash
# 1. Ship the bat + a tiny redirect wrapper to the VM.
scp -i ~/.ssh/goliat -P 20819 ../my_setup.bat user@<ip>:Desktop/

cat > /tmp/run_setup.cmd <<'EOF'
@echo off
cd /d %~dp0
my_setup.bat < nul > setup.log 2>&1
EOF
scp -i ~/.ssh/goliat -P 20819 /tmp/run_setup.cmd user@<ip>:Desktop/

# 2. Schedule + run.
ssh goliat 'schtasks /create /tn goliat-setup /tr "C:\Users\user\Desktop\run_setup.cmd" /sc once /st 23:59 /rl HIGHEST /f'
ssh goliat 'schtasks /run /tn goliat-setup'

# 3. Watch.
ssh goliat 'powershell -NoProfile -Command "Get-Content C:\Users\user\Desktop\setup.log -Tail 30"'
```

The wrapper redirects stdin from `nul` so the bat's `pause` calls become no-ops,
and captures stdout/stderr to `setup.log` for tailing.

The schtasks job runs in the user's interactive session (RDP-Tcp#N), so any GUI
that the bat launches (Sim4Life license installer, Git Bash, File Explorer)
will appear in your RDP window — that's expected.

### Things that go wrong during `my_setup.bat`

- **License automation is flaky.** Step 8 calls `license_automation.py` which
  drives the Sim4Life License Installer GUI via pywinauto to enter
  `@wicacib.private.ugent.be`. It frequently fails ("FAILED at 0s") — it is
  *known to be buggy even when launched interactively via "right-click → Run
  as administrator" in RDP*, so this isn't an SSH/schtasks artifact. The race
  with the VPN handshake is one cause, but not the only one. Fix path: skip
  it, then run the installer manually via RDP:
  `C:\Users\Public\Documents\ZMT\Licensing Tools\8.2\LicenseInstall.exe`,
  enter `@wicacib.private.ugent.be`, click Next.
  TODO for a future agent with time: either rewrite the pywinauto flow to be
  robust (verify VPN routes are up, retry validation, handle UI variants), or
  ask Robin what the actual reproducible failure mode is and patch it.
- **"ERROR: Input redirection is not supported, exiting the process immediately"**
  in the log: harmless, comes from MSI installers complaining about `< nul`.
  The bat continues past it.
- **Empty cmd window in your RDP**: normal — output is in `setup.log`.
- **VPN is split-tunnel** (Intec/iGent subnet only). RDP and SSH survive the
  handshake.

## Step 5 — switch SSH to bash (after the bat finishes)

`my_setup.bat` installs Git for Windows. Switch the SSH default shell so you
land in a Unix-style env with `goliat` on `PATH`:

```bash
ssh goliat 'reg add "HKLM\SOFTWARE\OpenSSH" /v DefaultShell /t REG_SZ /d "C:\Program Files\Git\bin\bash.exe" /f && reg add "HKLM\SOFTWARE\OpenSSH" /v DefaultShellCommandOption /t REG_SZ /d "-lc" /f'
```

The `-lc` makes bash a login shell for SSH command mode, so `~/.bash_profile`
(and via it, `~/.bashrc`) is sourced for both interactive and command sessions.

Test: `ssh goliat 'pwd; which goliat; goliat version'`.

`goliat` manages `~/.bashrc` itself (`goliat.utils.bashrc.sync_bashrc_to_home`)
— don't hand-write one. The Sim4Life Python is added to `PATH` there with a
marked auto-synced section.

## Step 6 — run goliat from SSH

By default leave `use_gui: true`. The Qt GUI shows up in your RDP session and
that's the conventional way to monitor a study — Robin watches it through RDP.
Per-study `.log` files are always written under
`~/goliat/results/<study>/.../verbose.log` regardless, so an agent driving via
SSH can still see everything that happened without needing the GUI rendered in
its own session.

`use_web: true` (the default in `base_config.json`) is fine to leave on for
small runs, but flip it off for really long, big runs (full studies with many
phantoms × frequencies × placements) — the web server adds overhead.

Only set `use_gui: false` when you specifically want a pure-console run with
`ConsoleLogger` streaming to stdout, e.g. for a quick smoke test where you
don't want a Qt window in RDP. In that case:

```json
{ "use_gui": false, "use_web": false, ... }
```

Detach the run from SSH with `nohup`:

```bash
ssh goliat 'cd ~/goliat && nohup bash -lc "goliat study X --auto-close > X.log 2>&1" > /dev/null 2>&1 & disown'
```

### goliat-specific gotchas

- **Manual grid size is capped at 3 mm.** Anything coarser is rejected by
  `gridding_setup._validate_grid_size`. The reason is downstream voxelization
  quality (peak SAR cube etc.), not FDTD itself. Don't try to "go fast" by
  going coarser — pick `3.0` and use a smaller `simulation_time_multiplier`
  if you want a quick smoke test.
- **Don't write configs from scratch.** They are long and have many
  inter-related fields. Always start from an existing working config in
  `configs/` (`tutorial_*`, `near_field_config`, `far_field_*_short`, …),
  use `"extends": "<that_file>.json"`, and override only the few fields you
  actually need to change. The merge is deep, so `simulation_parameters` and
  `gridding_parameters` overrides only touch the keys you specify.

## Reconnect VPN after a VM reboot — over SSH (no RDP needed)

`my_connect_vpn.bat` lives in your Linux-side `goliat/cloud_setup/`, NOT
on the VM. Don't try to run it on the VM (UAC-aware shortcut, GUI
prompts, paths assume an interactive desktop). Replicate its core actions
over SSH instead — the SSH session is already elevated thanks to
`LocalAccountTokenFilterPolicy=1` (Step 2.4 above), so `net session`
returns success and OpenVPN can write to its config dir.

```bash
# 0. Verify the cert + auth files are still on the VM Desktop. Done once
#    after a fresh provision; persists across reboots:
ssh goliat 'ls "/c/Users/$USERNAME/Desktop/certs/"'
# Should show: ca-vpn-zp.crt, Intec-iGent.ovpn, openvpn_auth.txt

# 1. Launch openvpn detached. The VM's pre-installed OpenVPNService is
#    the auto-start service; this launches a *user-mode* tunnel using
#    your stored auth file. Both can coexist.
ssh goliat 'cd "/c/Users/$USERNAME/Desktop/certs/" && \
    nohup "/c/Program Files/OpenVPN/bin/openvpn.exe" \
        --config Intec-iGent.ovpn --auth-user-pass openvpn_auth.txt \
        > /tmp/openvpn.log 2>&1 &'

# 2. Wait ~10 s, then verify the tunnel is up.
ssh goliat 'tail -10 /tmp/openvpn.log; ipconfig | grep -A 4 "TAP-Windows6"'
# Look for: "Initialization Sequence Completed" in the openvpn log,
# and "IPv4 Address. . . . . . . . . . . : 192.168.126.X" on TAP-Windows6.
```

Without VPN, `import s4l_v1` hangs >60 s waiting on the license server
(symptom: goliat run starts, log stays at 0 bytes). First diagnostic
when a goliat run looks stuck: `ipconfig` for `TAP-Windows6` IP.

## Reference: filesystem map

| Linux box | VM |
|---|---|
| `/home/user/goliat/` | `/c/Users/user/goliat/` (== `~/goliat`) |
| `~/.ssh/goliat[.pub]` | `C:\ProgramData\ssh\administrators_authorized_keys` |
| (this dir) | (cloned alongside, available at `~/goliat/cloud_setup/ssh/`) |
