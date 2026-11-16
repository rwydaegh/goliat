"""Minimal oSPARC v0 client for the GOLIAT validation workstream (stdlib only).

Credentials come from OSPARC_API_KEY / OSPARC_API_SECRET in the environment
(load with `uv run --no-project --env-file ~/opensim4life/.env python ...`).
They are never printed or written. Every remote mutation is preceded by a
ledger write (validation/ledger.json) carrying the credit reservation estimate.

Usage:
  osparc_job.py price  SERVICE
  osparc_job.py wallet
  osparc_job.py submit SERVICE --label L --deadline S --input input_1=PATH [--input input_2=PATH ...]
  osparc_job.py poll   SERVICE JOB_ID [--wait S]
  osparc_job.py stop   SERVICE JOB_ID
  osparc_job.py collect SERVICE JOB_ID OUTDIR
SERVICE is one of: runner, runner-gpu, isolve-cpu, isolve-gpu
"""

import argparse
import base64
import json
import math
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

HOST = "https://api.sim4life.science"
SERVICES = {
    "runner": ("s4l-python-runner", "1.2.251"),
    "runner-gpu": ("s4l-python-runner-gpu", "1.2.251"),
    "isolve-cpu": ("isolve-cpu", "2.2.251"),
    "isolve-gpu": ("isolve-gpu", "2.2.251"),
}
LEDGER = Path(__file__).resolve().parent.parent / "ledger.json"
CAP_CREDITS = 60.0
TERMINAL = {"SUCCESS", "FAILED", "ABORTED"}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


OPENER = urllib.request.build_opener(NoRedirect)


def auth():
    key, sec = os.environ.get("OSPARC_API_KEY"), os.environ.get("OSPARC_API_SECRET")
    if not key or not sec:
        sys.exit("missing OSPARC credentials in environment")
    return "Basic " + base64.b64encode(f"{key}:{sec}".encode()).decode()


def req(method, path, body=None, ctype="application/json", raw=False, timeout=60):
    headers = {"Authorization": auth(), "Accept": "application/json"}
    data = None
    if body is not None:
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        headers["Content-Type"] = ctype
    r = urllib.request.Request(HOST + path, data=data, headers=headers, method=method)
    try:
        resp = OPENER.open(r, timeout=timeout)
    except urllib.error.HTTPError as e:
        if e.code in (301, 302, 303, 307, 308):
            return {"_redirect": e.headers.get("Location", "")}
        msg = e.read()[:2000].decode(errors="replace")
        raise RuntimeError(f"HTTP {e.code} {method} {path}: {msg}") from None
    with resp:
        content = resp.read()
    if raw:
        return content
    return json.loads(content) if content else {}


def fetch_unauth(url, limit=2 * 1024**3):
    p = urllib.parse.urlsplit(url)
    if p.scheme != "https":
        raise RuntimeError("refusing non-https redirect")
    with urllib.request.urlopen(url, timeout=300) as resp:
        return resp.read(limit)


def spath(service):
    name, ver = SERVICES[service]
    return f"/v0/solvers/simcore/services/comp/{name}/releases/{ver}"


def load_ledger():
    if LEDGER.exists():
        return json.loads(LEDGER.read_text())
    return {"cap_credits": CAP_CREDITS, "reserved_credits": 0.0, "jobs": []}


def _iso(t):
    import datetime as _dt

    return _dt.datetime.fromisoformat(t.replace("Z", "+00:00")).timestamp()


def committed_credits(led):
    """Finished jobs count at actual runtime x rate; open jobs at their full reservation."""
    tot = 0.0
    for j in led["jobs"]:
        if j.get("state") in TERMINAL and j.get("started_obs") and j.get("stopped_obs"):
            j["actual_cr"] = round(j["rate_cr_h"] * (_iso(j["stopped_obs"]) - _iso(j["started_obs"])) / 3600, 3)
            tot += j["actual_cr"]
        elif j.get("state") in TERMINAL and j.get("actual_cr") is not None:
            tot += j["actual_cr"]
        else:
            tot += j.get("est_reservation_cr", 0)
    return tot


def save_ledger(led, only=None):
    """Locked read-merge-write so concurrent pollers never drop each other's entries."""
    import fcntl

    with open(LEDGER.with_suffix(".lock"), "w") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        try:
            disk = json.loads(LEDGER.read_text()) if LEDGER.exists() else {"jobs": []}
        except json.JSONDecodeError:
            disk = {"jobs": []}
        key = lambda j: j.get("label", "") + "|" + j.get("created_at", "")  # noqa: E731  (stable before job_id exists)
        by_id = {key(j): j for j in disk.get("jobs", [])}
        for j in led.get("jobs", []):
            if only is None or key(j) in only:
                by_id.setdefault(key(j), {}).update(j)
        seen = [key(j) for j in disk.get("jobs", [])]
        order = seen + [key(j) for j in led["jobs"] if key(j) not in seen and (only is None or key(j) in only)]
        merged = {k: v for k, v in led.items() if k != "jobs"}
        merged["reserved_credits"] = round(sum(j.get("est_reservation_cr", 0) for j in by_id.values()), 2)
        merged["jobs"] = [by_id[i] for i in order]
        led["jobs"] = merged["jobs"]
        tmp = LEDGER.with_name(f"ledger.{os.getpid()}.tmp")
        tmp.write_text(json.dumps(merged, indent=1))
        os.replace(tmp, LEDGER)


def price(service):
    plan = req("GET", spath(service) + "/pricing_plan")
    return plan


def default_rate(service):
    plan = price(service)
    units = plan.get("pricingUnits", [])
    d = [u for u in units if u.get("default")]
    return d[0]["currentCostPerUnit"], d[0]["unitName"], d[0]["pricingUnitId"]


def upload(path):
    raw = Path(path).read_bytes()
    b = "goliatval-" + uuid.uuid4().hex
    body = (
        (
            f'--{b}\r\nContent-Disposition: form-data; name="file"; filename="{Path(path).name}"\r\n'
            "Content-Type: application/octet-stream\r\n\r\n"
        ).encode()
        + raw
        + f"\r\n--{b}--\r\n".encode()
    )
    res = req("PUT", "/v0/files/content", body, ctype=f"multipart/form-data; boundary={b}", timeout=7200)
    return res["id"], Path(path).name, len(raw)


def find_job(led, job_id):
    for j in led["jobs"]:
        if j.get("job_id") == job_id:
            return j
    return None


def cmd_submit(a):
    rate, unit, unit_id = default_rate(a.service)
    est = math.ceil(rate * (a.deadline + 120) / 3600 * 100) / 100
    led = load_ledger()
    open_jobs = [j for j in led["jobs"] if j.get("state") not in TERMINAL and j.get("job_id")]
    if open_jobs and not a.allow_parallel:
        sys.exit(f"open jobs exist: {[j['job_id'] for j in open_jobs]}")
    committed = committed_credits(led)
    if committed + est > led["cap_credits"]:
        sys.exit(f"reservation {est} would exceed cap (committed {committed:.2f}/{led['cap_credits']})")
    entry = {
        "label": a.label,
        "service": a.service,
        "rate_cr_h": rate,
        "unit": unit,
        "deadline_s": a.deadline,
        "est_reservation_cr": est,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "inputs": {},
        "job_id": None,
        "state": "upload_pending",
    }
    led["reserved_credits"] = round(led["reserved_credits"] + est, 2)
    led["jobs"].append(entry)
    save_ledger(led)
    values = {}
    for spec in a.input:
        port, p = spec.split("=", 1)
        if p.startswith("fileid:"):  # reuse an already uploaded file: fileid:<uuid>:<filename>
            _, fid, name = p.split(":", 2)
            values[port] = {"id": fid, "filename": name}
            entry["inputs"][port] = {"reused_file_id": fid, "filename": name}
            continue
        fid, name, n = upload(p)
        values[port] = {"id": fid, "filename": name}
        entry["inputs"][port] = {"path": str(p), "file_id": fid, "bytes": n}
        save_ledger(led)
    entry["state"] = "create_pending"
    save_ledger(led)
    job = req("POST", spath(a.service) + "/jobs", {"values": values})
    entry["job_id"] = job["id"]
    entry["state"] = "created"
    save_ledger(led)
    pu = req("GET", spath(a.service) + f"/jobs/{job['id']}/pricing_unit")
    entry["job_pricing_unit"] = {k: pu.get(k) for k in ("unitName", "currentCostPerUnit")}
    save_ledger(led)
    req("POST", spath(a.service) + f"/jobs/{job['id']}:start")
    entry["state"] = "started"
    entry["started_at"] = time.time()
    save_ledger(led)
    print(json.dumps({"job_id": job["id"], "est_reservation_cr": est, "rate": rate, "unit": unit}))


def inspect(service, job_id):
    return req("POST", spath(service) + f"/jobs/{job_id}:inspect")


def cmd_poll(a):
    led = load_ledger()
    entry = find_job(led, a.job_id)
    end = time.time() + a.wait
    while True:
        st = inspect(a.service, a.job_id)
        state = st.get("state")
        if entry is not None:
            entry["state"] = state
            entry["progress"] = st.get("progress")
            if state in TERMINAL and "stopped_obs" not in entry:
                entry["stopped_obs"] = st.get("stopped_at")
                entry["started_obs"] = st.get("started_at")
            save_ledger(led, only=[entry["label"] + "|" + entry["created_at"]])
        print(
            json.dumps({"state": state, "progress": st.get("progress"), "started": st.get("started_at"), "stopped": st.get("stopped_at")}),
            flush=True,
        )
        if state in TERMINAL or time.time() > end:
            break
        # watchdog: stop if beyond deadline
        if entry is not None and entry.get("started_at") and time.time() - entry["started_at"] > entry["deadline_s"]:
            print("deadline exceeded -> stopping", flush=True)
            req("POST", spath(a.service) + f"/jobs/{a.job_id}:stop")
            entry["stop_requested"] = True
            save_ledger(led, only=[entry["label"] + "|" + entry["created_at"]])
        time.sleep(10)


def cmd_stop(a):
    print(json.dumps(req("POST", spath(a.service) + f"/jobs/{a.job_id}:stop"))[:500])


def cmd_collect(a):
    out = Path(a.outdir)
    out.mkdir(parents=True, exist_ok=True)
    try:
        res = req("GET", spath(a.service) + f"/jobs/{a.job_id}/outputs")
        (out / "outputs.json").write_text(json.dumps(res, indent=1))
        for port, val in (res.get("results") or {}).items():
            if isinstance(val, dict) and val.get("id"):
                r = req("GET", f"/v0/files/{val['id']}/content", raw=True, timeout=600)
                data = fetch_unauth(r["_redirect"]) if isinstance(r, dict) and "_redirect" in r else r
                fn = out / f"{port}_{val.get('filename', 'file')}"
                fn.write_bytes(data)
                print(f"{port}: {fn} {len(data)} bytes")
    except RuntimeError as e:
        print("outputs:", e)
    try:
        r = req("GET", spath(a.service) + f"/jobs/{a.job_id}/outputs/logfile", raw=True, timeout=300)
        data = fetch_unauth(r["_redirect"]) if isinstance(r, dict) and "_redirect" in r else r
        (out / "logs.zip").write_bytes(data)
        print(f"log: {out / 'logs.zip'} {len(data)} bytes")
    except RuntimeError as e:
        print("log:", e)


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("price")
    s.add_argument("service")
    sub.add_parser("wallet")
    s = sub.add_parser("submit")
    s.add_argument("service")
    s.add_argument("--label", required=True)
    s.add_argument("--deadline", type=int, required=True)
    s.add_argument("--input", action="append", required=True)
    s.add_argument("--allow-parallel", action="store_true")
    s = sub.add_parser("poll")
    s.add_argument("service")
    s.add_argument("job_id")
    s.add_argument("--wait", type=int, default=0)
    s = sub.add_parser("stop")
    s.add_argument("service")
    s.add_argument("job_id")
    s = sub.add_parser("collect")
    s.add_argument("service")
    s.add_argument("job_id")
    s.add_argument("outdir")
    a = p.parse_args()
    if a.cmd == "price":
        plan = price(a.service)
        print(
            json.dumps(
                [
                    {k: u.get(k) for k in ("unitName", "currentCostPerUnit", "default", "specificInfo", "unitExtraInfo")}
                    for u in plan.get("pricingUnits", [])
                ],
                indent=1,
            )
        )
    elif a.cmd == "wallet":
        w = req("GET", "/v0/wallets/default")
        print(json.dumps({"status": w.get("status"), "available_credits": w.get("availableCredits")}))
    elif a.cmd == "submit":
        cmd_submit(a)
    elif a.cmd == "poll":
        cmd_poll(a)
    elif a.cmd == "stop":
        cmd_stop(a)
    elif a.cmd == "collect":
        cmd_collect(a)


if __name__ == "__main__":
    main()
