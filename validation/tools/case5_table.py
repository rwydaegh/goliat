"""Collect Case 5 driver reports and compare with Li et al. 2026 (PMB 71 01NT02) Tables 2-3 (10 mW input power).

usage: python tools/case5_table.py   (scans case5_li/*/out/**/driver_report.json, writes case5_li/results.json)
"""

import glob
import json
from pathlib import Path

V = Path(__file__).resolve().parents[1]
# Table 3 (inter-lab mean +- SD, pooled over Alvar + VHP): (f GHz, d mm) -> {ant: (sAPD1, sd1, sAPD4, sd4)}
T3 = {
    (10, 10): {"dip": (3.09, 0.85, 1.87, 0.47), "arr": (0.96, 0.37, 0.72, 0.29)},
    (10, 15): {"dip": (2.01, 0.52, 1.48, 0.35), "arr": (1.61, 0.54, 1.31, 0.39)},
    (10, 20): {"dip": (1.29, 0.35, 1.04, 0.25), "arr": (1.48, 0.61, 1.25, 0.48)},
    (30, 10): {"dip": (4.15, 0.75, 2.37, 0.40), "arr": (12.42, 2.85, 5.97, 1.45)},
    (30, 15): {"dip": (2.14, 0.41, 1.55, 0.25), "arr": (11.59, 2.89, 5.17, 1.25)},
    (30, 20): {"dip": (1.27, 0.24, 1.03, 0.18), "arr": (9.71, 2.53, 4.57, 1.17)},
}
# Table 2, VHP-Female column (pooled over antennas): (f, d) -> (sAPD1, sd1, sAPD4, sd4)
T2_VHP = {
    (10, 10): (2.3, 1.37, 1.47, 0.76),
    (10, 15): (1.9, 0.65, 1.46, 0.44),
    (10, 20): (1.6, 0.52, 1.3, 0.4),
    (30, 10): (7.45, 3.71, 3.74, 1.61),
    (30, 15): (6.15, 4.33, 3.08, 1.69),
    (30, 20): (5.03, 3.99, 2.65, 1.72),
}


def main():
    rows = []
    for rp in sorted(glob.glob(str(V / "case5_li" / "*" / "out" / "**" / "driver_report.json"), recursive=True)):
        r = json.loads(Path(rp).read_text())
        s = r["spec"]
        n = r.get("normalised_10mW") or {}
        if n.get("sAPD_1cm2_W_m2") is None:
            continue
        ant = "arr" if s["array_n"] > 1 else "dip"
        f, d = s["frequency_mhz"] // 1000, int(s["distance_mm"])
        ref = T3[(f, d)][ant]
        row = {
            "run": s["name"],
            "report": str(Path(rp).relative_to(V)),
            "ant": ant,
            "f_GHz": f,
            "d_mm": d,
            "grid_mm": s["grid_mm"],
            "P_in_W": n.get("input_power_W"),
            "sAPD1": n.get("sAPD_1cm2_W_m2"),
            "sAPD4": n.get("sAPD_4cm2_W_m2"),
            "ref_T3": ref,
            "ref_T2_VHP": T2_VHP[(f, d)],
            "geometry": {
                k: (r.get("geometry") or {}).get(k)
                for k in ("rule", "lips_ok", "antenna_centre_mm", "closest_skin_point_mm", "centre_to_skin_mm", "n_deleted")
            },
            "antenna": r.get("antenna"),
            "sim_cells_estimate": r.get("sim_cells_estimate"),
            "fatal": bool(r.get("fatal")),
        }
        for key, (m, sd) in (("sAPD1", ref[:2]), ("sAPD4", ref[2:])):
            v = row[key]
            if v is not None:
                row[key + "_z"] = round((v - m) / sd, 2)
                row[key + "_rel_pct"] = round(100 * (v / m - 1), 1)
        rows.append(row)
    (V / "case5_li" / "results.json").write_text(json.dumps(rows, indent=1))
    print(f"{'run':16s} {'Pin mW':>8s} {'sAPD1':>7s} {'Li T3':>13s} {'z':>6s} {'sAPD4':>7s} {'Li T3':>13s} {'z':>6s}")
    for w in rows:
        r3 = w["ref_T3"]
        f1 = f"{w['sAPD1']:.2f}" if w["sAPD1"] is not None else "-"
        f4 = f"{w['sAPD4']:.2f}" if w["sAPD4"] is not None else "-"
        p = f"{w['P_in_W'] * 1e3:.2f}" if w["P_in_W"] else "-"
        print(
            f"{w['run']:16s} {p:>8s} {f1:>7s} {r3[0]:6.2f}±{r3[1]:<5.2f} {w.get('sAPD1_z', ''):>6} {f4:>7s} {r3[2]:6.2f}±{r3[3]:<5.2f} {w.get('sAPD4_z', ''):>6}"
        )


if __name__ == "__main__":
    main()
