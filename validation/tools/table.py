import json
import sys

rows = json.load(open(sys.argv[1]))
for d in rows:
    g = d.get("grid")
    s = d.get("solver", {})

    def f(x, n=2):
        return None if x is None else round(x, n)

    print(
        d["name"],
        "cells",
        s.get("cells"),
        "dx_mm",
        f(g[0][2] * 1000, 4) if g else None,
        "cpw",
        f(d.get("cpw_tissue"), 1),
        "t_ns",
        f(s.get("sim_time_ns")),
        "it",
        s.get("iterations"),
        "/",
        s.get("iter_planned"),
        "bal%",
        f(d.get("balance_pct"), 1),
        "errP%",
        f(d.get("err_Pabs_pct")),
        "errWB%",
        f(d.get("err_wbSAR_pct")),
        "wb",
        d.get("wbSAR"),
        "ps10",
        d.get("psSAR10g"),
        "ps1",
        d.get("psSAR1g"),
        "sapd/S",
        f(d.get("sapd_per_Wm2"), 4),
        "T",
        f(d.get("analytic_APD_per_Wm2"), 4),
        "errSAPD%",
        f(d.get("err_sapd_pct")),
        d.get("apd_field") or "",
        "FATAL" if d.get("fatal") else "",
    )
