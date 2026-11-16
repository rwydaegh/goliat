"""Summarise GOLIAT validation runs and compare with analytic references.

usage: analyze.py OUT_DIR [OUT_DIR ...] [--json results.json]
Each OUT_DIR is an unzipped runner output (contains <run>/driver_report.json).
Material values (eps_r, sigma, rho) are taken from what GOLIAT logged after
Sim4Life evaluated the IT'IS 4.2 database, so the reference uses exactly the
values the solver used. S_inc = |E0|^2/(2 eta0) with E0 = 1 V/m peak, as assumed
by GOLIAT's power_extractor/far_field_strategy.
"""

import glob
import json
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from goliat.validation import analytic as A  # noqa: E402

ETA0 = 376.730313668
S_INC = 1.0 / (2 * ETA0)


def parse_materials(text):
    mats = {}
    for m in re.finditer(
        r"Material: '([^']+)'.*?Relative Permittivity: ([\d.]+).*?Conductivity \(S/m\): ([\d.]+).*?Density \(kg/m\^3\): ([\d.]+)",
        text,
        re.S,
    ):
        mats[m.group(1)] = {"eps_r": float(m.group(2)), "sigma": float(m.group(3)), "rho": float(m.group(4))}
    return mats


def parse_solver(text):
    d = {}
    for key, pat in [
        ("dt_s", r"Simulation Time Step:\s*([\d.eE+-]+)"),
        ("iterations", r"Simulation performed (\d+) iterations"),
        ("iter_planned", r"Simulation Iterations:\s*(\d+)"),
        ("cells", r"Number of cells: (\d+x\d+x\d+)"),
        ("mcells", r"Number of cells: \S+ = \d+ cells = ([\d.]+) MCells"),
        ("speed", r"@ ([\d.]+) MCells/s"),
    ]:
        ms = re.findall(pat, text)
        if ms:
            d[key] = ms[-1]
    if "dt_s" in d and "iterations" in d:
        d["sim_time_ns"] = float(d["dt_s"]) * int(d["iterations"]) * 1e9
    return d


def analyze_run(rdir):
    rep = json.loads((rdir / "driver_report.json").read_text())
    spec = rep["spec"]
    text = "".join((rdir / n).read_text(errors="replace") for n in ("stderr.log", "stdout.log") if (rdir / n).exists())
    mats = parse_materials(text)
    solver = parse_solver(text)
    sr = glob.glob(str(rdir / "files" / "results" / "**" / "sar_results.json"), recursive=True)
    sapd = glob.glob(str(rdir / "files" / "results" / "**" / "sapd_results.json"), recursive=True)
    res = json.loads(Path(sr[0]).read_text()) if sr else {}
    out = {
        "name": spec["name"],
        "ok": bool(sr),
        "fatal": rep.get("fatal"),
        "solver": solver,
        "materials": mats,
        "permissive": rep.get("permissive_setattr_hits"),
        "freq_mhz": spec["config"]["frequencies_mhz"][0],
    }
    grid = None
    for h5, e in (rep.get("h5") or {}).items():
        if h5.endswith("_Input.h5") and e.get("axes"):
            grid = [(a["n"] - 1, a["dmin"], a["dmax"]) for a in e["axes"][:3]]
    out["grid"] = grid
    out["gridding_cfg"] = spec["config"].get("gridding_parameters")
    if not res:
        return out
    pb = res.get("power_balance", {})
    out.update(
        {
            "wbSAR": res.get("whole_body_sar"),
            "psSAR10g": res.get("peak_sar_10g_W_kg"),
            "psSAR1g": res.get("peak_sar_1g_W_kg"),
            "DielLoss": pb.get("DielLoss"),
            "RadPower": pb.get("RadPower"),
            "balance_pct": pb.get("Balance"),
        }
    )
    f = out["freq_mhz"] * 1e6
    geo = spec["geometry"]
    tissue = geo["tissue_entity"]
    m = mats.get(tissue) or next((v for k, v in mats.items() if k != "Air"), None)
    if m and geo["kind"] == "sphere":
        a = geo["radius_mm"] / 1000
        P = A.sphere_absorbed_power(a, f, m["eps_r"], m["sigma"], s_inc=S_INC)
        wb = A.sphere_wb_sar(a, f, m["eps_r"], m["sigma"], m["rho"], s_inc=S_INC)
        out.update(
            {
                "mie_Pabs": P,
                "mie_wbSAR": wb,
                "err_Pabs_pct": 100 * (out["DielLoss"] / P - 1) if out["DielLoss"] else None,
                "err_wbSAR_pct": 100 * (out["wbSAR"] / wb - 1) if out["wbSAR"] else None,
                # normalised to S_inc = 1 W/m^2, as GOLIAT's far_field_strategy does (x754)
                "wbSAR_per_Wm2_goliat754": out["wbSAR"] * 754 if out["wbSAR"] else None,
                "mie_wbSAR_per_Wm2": wb / S_INC,
            }
        )
        lam_t = 299792458 / f / math.sqrt(m["eps_r"]) * 1000
        if grid:
            out["cpw_tissue"] = lam_t / (grid[0][2] * 1000)
    if m and geo["kind"] == "box":
        T = A.halfspace_apd(m["eps_r"], m["sigma"], f, s_inc=1.0)
        out["analytic_APD_per_Wm2"] = T
        if sapd:
            sd = json.loads(Path(sapd[0]).read_text())
            out["sapd"] = sd
            pk = sd.get("peak_sapd_W_m2")
            if pk is not None:
                out["sapd_per_Wm2"] = pk / S_INC
                out["err_sapd_pct"] = 100 * (pk / S_INC / T - 1)
        npz = glob.glob(str(rdir / "files" / "results" / "**" / "skin_apd.npz"), recursive=True)
        if npz:
            import numpy as np

            z = np.load(npz[0])
            v, apd = z["vertices_m"], z["apd_w_m2"]
            out["apd_field"] = {"n": int(apd.size), "max": float(apd.max())}
            if apd.size == len(v):
                lo, hi = np.array(geo["lo_mm"]) / 1000, np.array(geo["hi_mm"]) / 1000
                c = (lo + hi) / 2
                top = np.isclose(v[:, 2], hi[2], atol=1e-4)
                for rad in (0.005, 0.01, 0.02):
                    sel = top & (np.abs(v[:, 0] - c[0]) < rad) & (np.abs(v[:, 1] - c[1]) < rad)
                    if sel.any():
                        out["apd_field"][f"center_mean_{int(rad * 2000)}mm_square"] = float(apd[sel].mean())
                        out["apd_field"][f"err_center_{int(rad * 2000)}mm_pct"] = 100 * (float(apd[sel].mean()) / T - 1)
        lam_t = 299792458 / f / math.sqrt(m["eps_r"]) * 1000
        if grid:
            out["cpw_tissue"] = lam_t / (max(g[2] for g in grid) * 1000)
    return out


def main():
    args = sys.argv[1:]
    jpath = None
    if "--json" in args:
        i = args.index("--json")
        jpath = args[i + 1]
        args = args[:i] + args[i + 2 :]
    rows = []
    for d in args:
        for rep in sorted(Path(d).glob("*/driver_report.json")):
            rows.append(analyze_run(rep.parent))
    for r in rows:
        keys = [
            "name",
            "ok",
            "freq_mhz",
            "grid",
            "cpw_tissue",
            "solver",
            "wbSAR",
            "psSAR10g",
            "psSAR1g",
            "balance_pct",
            "err_Pabs_pct",
            "err_wbSAR_pct",
            "analytic_APD_per_Wm2",
            "sapd_per_Wm2",
            "err_sapd_pct",
            "apd_field",
            "permissive",
            "fatal",
        ]
        print({k: r.get(k) for k in keys if r.get(k) is not None})
    if jpath:
        Path(jpath).write_text(json.dumps(rows, indent=1, default=str))


if __name__ == "__main__":
    main()
