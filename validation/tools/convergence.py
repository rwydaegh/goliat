"""Grid-convergence table + Richardson extrapolation for the sphere sweeps.

usage: convergence.py  (reads case3_convergence/*/results.json and case1 diag)
Writes case3_convergence/convergence_table.json and prints a markdown table.

Richardson (generalised, three grids h1>h2>h3, possibly non-constant ratio):
observed order p solved from (f1-f2)/(f2-f3) = (h1^p-h2^p)/(h2^p-h3^p);
f_ext = f3 + (f3-f2)*h3^p/(h2^p-h3^p). Only applied to monotone triplets.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(*rels):
    rows = {}
    for rel in rels:
        p = ROOT / rel
        if p.exists():
            for r in json.loads(p.read_text()):
                if r.get("wbSAR"):
                    rows[r["name"]] = r
    return rows


def order(h, f):
    (h1, h2, h3), (f1, f2, f3) = h, f
    d12, d23 = f1 - f2, f2 - f3
    if d12 == 0 or d23 == 0 or (d12 > 0) != (d23 > 0):
        return None, None
    target = d12 / d23
    lo, hi = 0.05, 20.0
    g = lambda p: (h1**p - h2**p) / (h2**p - h3**p) - target  # noqa: E731
    if g(lo) * g(hi) > 0:
        return None, None
    for _ in range(200):
        mid = (lo + hi) / 2
        if g(lo) * g(mid) <= 0:
            hi = mid
        else:
            lo = mid
    p = (lo + hi) / 2
    return p, f3 + (f3 - f2) * h3**p / (h2**p - h3**p)


def sweep(rows, names, label):
    pts = []
    for n in names:
        r = rows.get(n)
        if r:
            pts.append(
                {
                    "name": n,
                    "dx_mm": r["grid"][0][2] * 1000,
                    "cpw": r.get("cpw_tissue"),
                    "cells": r["solver"].get("cells"),
                    "wbSAR": r["wbSAR"],
                    "mie_wbSAR": r["mie_wbSAR"],
                    "err_wb_mie_pct": r["err_wbSAR_pct"],
                    "psSAR10g": r["psSAR10g"],
                    "psSAR1g": r["psSAR1g"],
                    "seconds_solver_job": None,
                }
            )
    pts.sort(key=lambda x: -x["dx_mm"])
    out = {"label": label, "points": pts, "richardson": {}}
    for q in ("wbSAR", "psSAR10g", "psSAR1g"):
        best = []
        for i in range(len(pts) - 2):
            tri = pts[i : i + 3]
            p, fx = order([t["dx_mm"] for t in tri], [t[q] for t in tri])
            best.append({"grids_mm": [round(t["dx_mm"], 3) for t in tri], "p": p, "f_ext": fx})
        out["richardson"][q] = best
    return out


def main():
    rows = load(
        "case3_convergence/sweep5800/results.json",
        "case3_convergence/followB/results.json",
        "case3_convergence/sweep2450/results.json",
        "case3_convergence/followA/results.json",
        "case3_convergence/pmltest/results.json",
        "case3_convergence/pmlhigh/results.json",
    )
    S58 = sweep(
        rows,
        ["h5800_dx1p4", "h5800_dx1p0", "h5800_dx0p7", "h5800_dx0p5", "s5800_dx0p35_pmlhigh"],
        "PRIMARY 5.8 GHz muscle sphere r=25 mm, pad 15 mm, 10x sim time, PML High",
    )
    S24 = sweep(
        rows,
        ["h2450_dx2p5", "h2450_dx1p482", "h2450_dx1p0", "s2450_dx0p7_pmlhigh"],
        "PRIMARY 2.45 GHz muscle sphere r=50 mm, pad 25 mm, default sim time, PML High",
    )
    L58 = sweep(
        rows, ["s5800_dx1p4", "s5800_dx1p0", "s5800_dx0p7", "s5800_dx0p5", "s5800_dx0p35"], "5.8 GHz same, PML Low (GOLIAT default)"
    )
    L24 = sweep(rows, ["s2450_dx2p5", "s2450_dx1p482", "s2450_dx1p0", "s2450_dx0p7"], "2.45 GHz same, PML Low (GOLIAT default)")
    res = {
        "5800": S58,
        "2450": S24,
        "5800_pmllow": L58,
        "2450_pmllow": L24,
        "extra": {
            k: {kk: rows[k].get(kk) for kk in ("wbSAR", "psSAR10g", "psSAR1g", "err_wbSAR_pct")}
            for k in rows
            if k not in {p["name"] for s in (S58, S24, L58, L24) for p in s["points"]}
        },
    }
    for s in (S58, S24, L58, L24):
        print(f"\n### {s['label']}")
        # reference for psSAR: Richardson on the finest monotone triplet if available, else finest grid
        refs = {q: s["points"][-1][q] for q in ("psSAR10g", "psSAR1g")}
        rich = {}
        for q in ("psSAR10g", "psSAR1g"):
            last = s["richardson"][q][-1] if s["richardson"][q] else None
            rich[q] = last["f_ext"] if last and last["p"] and 0.5 < last["p"] < 4 else None
        s["reference_finest"] = refs
        s["reference_richardson_finest_triplet"] = rich
        print(
            "| dx mm | cells/λ | WB-SAR vs Mie % | psSAR10g vs finest % | psSAR1g vs finest % | psSAR10g vs Rich. % | psSAR1g vs Rich. % |"
        )
        print("|---|---|---|---|---|---|---|")
        f = lambda v, r: "n/a" if r is None else f"{100 * (v / r - 1):+.2f}"  # noqa: E731
        for p in s["points"]:
            print(
                f"| {p['dx_mm']:.3f} | {p['cpw']:.1f} | {p['err_wb_mie_pct']:+.2f} | {f(p['psSAR10g'], refs['psSAR10g'])} | {f(p['psSAR1g'], refs['psSAR1g'])} | {f(p['psSAR10g'], rich['psSAR10g'])} | {f(p['psSAR1g'], rich['psSAR1g'])} |"
            )
        for q, lst in s["richardson"].items():
            for r in lst:
                if r["p"]:
                    extra = f" (vs Mie {100 * (r['f_ext'] / s['points'][0]['mie_wbSAR'] - 1):+.2f}%)" if q == "wbSAR" else ""
                    print(f"  {q} grids {r['grids_mm']}: p={r['p']:.2f} ext={r['f_ext']:.5e}{extra}")
                else:
                    print(f"  {q} grids {r['grids_mm']}: non-monotone, no Richardson")
    (ROOT / "case3_convergence" / "convergence_table.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
