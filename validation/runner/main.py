"""oSPARC s4l-python-runner entrypoint for GOLIAT validation runs.

Inputs (any port; located by file name anywhere under the inputs folder):
  main.py            this file
  goliat_bundle.zip  goliat/ package + pyproject.toml + valdriver/ (run_one.py)
  wheels.zip         pure/cp311 wheels for pandas, colorama, python-dotenv, line_profiler, pytz, tzdata
  case.json          {"runs": [ {run spec}, ... ], "probe": bool}

Each run executes in its own subprocess (valdriver/run_one.py) so a crash in
one Sim4Life session does not lose the others. Everything small is copied to
OUTPUT/<run name>/; large .h5/.smash files are not copied unless requested.
"""

import json
import os
import platform
import subprocess
import sys
import time
import traceback
import zipfile
from pathlib import Path

T0 = time.time()


def find_dirs():
    inp = os.environ.get("INPUT_FOLDER") or os.environ.get("INPUTS_FOLDER") or "/inputs"
    out = os.environ.get("OUTPUT_FOLDER") or os.environ.get("OUTPUTS_FOLDER") or "/outputs"
    return Path(inp), Path(out)


def find_file(root, name):
    for p in root.rglob(name):
        return p
    return None


def env_report(out):
    rep = {
        "python": sys.version,
        "executable": sys.executable,
        "platform": platform.platform(),
        "nproc": os.cpu_count(),
        "cwd": os.getcwd(),
    }
    for k in (
        "INPUT_FOLDER",
        "OUTPUT_FOLDER",
        "INPUTS_FOLDER",
        "OUTPUTS_FOLDER",
        "Z43_MAX_CPU_RESOURCES",
        "SC_COMP_SERVICES_SCHEDULED_AS",
        "NVIDIA_VISIBLE_DEVICES",
    ):
        rep[k] = os.environ.get(k)
    sm = Path("/home/smu/services/supermash")
    hits = []
    if sm.exists():
        for p in sm.rglob("*"):
            n = p.name.lower()
            if ("isolve" in n or "solver" in n) and len(hits) < 60:
                hits.append(str(p))
    rep["solver_like_files"] = hits
    try:
        rep["nvidia_smi"] = subprocess.run(["nvidia-smi", "-L"], capture_output=True, text=True, timeout=20).stdout
    except Exception as e:  # noqa: BLE001
        rep["nvidia_smi"] = repr(e)
    try:
        rep["mem"] = Path("/proc/meminfo").read_text().splitlines()[:3]
    except Exception:  # noqa: BLE001
        pass
    (out / "env_report.json").write_text(json.dumps(rep, indent=1))
    return rep


def main():
    inp, out = find_dirs()
    out.mkdir(parents=True, exist_ok=True)
    status = {"started": T0, "runs": []}
    try:
        env_report(out)
        work = Path("/tmp/goliatval")
        work.mkdir(parents=True, exist_ok=True)
        bundle = find_file(inp, "goliat_bundle.zip")
        wheels = find_file(inp, "wheels.zip")
        case = find_file(inp, "case.json")
        status["inputs"] = [str(p.relative_to(inp)) for p in inp.rglob("*") if p.is_file()]
        # The runner auto-extracts uploaded zips into the inputs folder.
        if (inp / "goliat").is_dir() and (inp / "valdriver").is_dir():
            src = inp
        else:
            src = work / "src"
            with zipfile.ZipFile(bundle) as z:
                z.extractall(src)
        whl = sorted(str(p) for p in inp.rglob("*.whl"))
        if not whl and wheels:
            wd = work / "wheels"
            with zipfile.ZipFile(wheels) as z:
                z.extractall(wd)
            whl = sorted(str(p) for p in wd.rglob("*.whl"))
        if whl:
            r = subprocess.run([sys.executable, "-m", "pip", "install", "--no-index", "--no-deps", *whl], capture_output=True, text=True)
            (out / "pip_install.log").write_text(r.stdout + "\n" + r.stderr)
        sm = Path("/home/smu/services/supermash/Solvers")
        if sm.exists():
            (out / "solvers_dir.txt").write_text("\n".join(sorted(str(p) for p in sm.rglob("*"))[:300]))
        spec = json.loads(case.read_text())
        budget = spec.get("budget_s")  # finish (and publish outputs) before the client-side watchdog fires
        for run in spec["runs"]:
            name = run["name"]
            timeout = run.get("timeout_s", 3000)
            if budget:
                left = budget - (time.time() - T0) - 90
                if left < 60:
                    status["runs"].append({"name": name, "rc": "skipped_budget"})
                    print(f"[goliatval] skip {name}: budget exhausted", flush=True)
                    continue
                timeout = min(timeout, left)
            print(f"[goliatval] start {name} (timeout {timeout:.0f}s, t={time.time() - T0:.0f}s)", flush=True)
            rdir = out / name
            rdir.mkdir(parents=True, exist_ok=True)
            (rdir / "run_spec.json").write_text(json.dumps(run, indent=1))
            t = time.time()
            env = dict(os.environ)
            env["PYTHONPATH"] = str(src) + os.pathsep + env.get("PYTHONPATH", "")
            env["GOLIATVAL_OUT"] = str(rdir)
            env["GOLIATVAL_SRC"] = str(src)
            try:
                r = subprocess.run(
                    [sys.executable, str(src / "valdriver" / run.get("driver", "run_one.py")), str(rdir / "run_spec.json")],
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
                rc = r.returncode
                (rdir / "stdout.log").write_text(r.stdout[-4_000_000:])
                (rdir / "stderr.log").write_text(r.stderr[-2_000_000:])
            except subprocess.TimeoutExpired as e:
                rc = "timeout"
                (rdir / "stdout.log").write_text(str(e.stdout)[-2_000_000:] if e.stdout else "")
            status["runs"].append({"name": name, "rc": rc, "seconds": round(time.time() - t, 1)})
            print(f"[goliatval] done {name} rc={rc} in {time.time() - t:.0f}s", flush=True)
            (out / "status.json").write_text(json.dumps(status, indent=1))
    except Exception:  # noqa: BLE001
        status["fatal"] = traceback.format_exc()
    status["total_seconds"] = round(time.time() - T0, 1)
    (out / "status.json").write_text(json.dumps(status, indent=1))


if __name__ == "__main__":
    main()
