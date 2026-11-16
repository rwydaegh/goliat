"""Case 5 run specs (Li et al. 2026 PMB 71 01NT02 consistency check, ViP Ella left cheek).

usage: python tools/case5.py <out case.json> <run>[,<run>...] [--budget S]
run tokens: <ant>_<fGHz>_<dmm>, e.g. dip_10_15, arr_30_10
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from specs import deep_update  # noqa: E402

MAPPING = json.load(open(Path(__file__).resolve().parents[2] / "data" / "material_name_mapping.json"))["ella"]
GRID = {10: 0.5, 30: 0.25}
CFG = {
    "solver_settings": {"kernel": "software", "server": "localhost", "boundary_conditions": {"type": "UpmlCpml", "strength": "High"}},
    "manual_isolve": False,
    "use_gui": False,
    "use_web": False,
    "execution_control": {
        "do_setup": True,
        "do_run": True,
        "do_extract": True,
        "only_write_input_file": False,
        "batch_run": False,
        "auto_cleanup_previous_results": [],
    },
    "extraction": {
        "sar": True,
        "power_balance": True,
        "sapd": True,
        "sapd_field": False,
        "point_sensors": False,
        "psSAR_averaging_masses_g": [10],
    },
    "export_material_properties": False,
}


def run(tok, timeout_s=3000):
    ant, f, d = tok.split("_")
    f, d = int(f), float(d)
    cfg = deep_update(
        json.loads(json.dumps(CFG)),
        {"gridding_parameters": {"global_gridding": {"grid_mode": "manual"}, "global_gridding_per_frequency": {str(f * 1000): GRID[f]}}},
    )
    return {
        "name": f"c5_{tok}",
        "driver": "run_head.py",
        "frequency_mhz": f * 1000,
        "grid_mm": GRID[f],
        "distance_mm": d,
        "array_n": 4 if ant == "arr" else 1,
        "length_lambda": 0.45,
        "pitch_lambda": 0.5,
        "pad_mm": 20.0,
        "min_half_mm": 30.0,
        "tissue_depth_mm": 30.0 if f == 10 else 20.0,
        "placement": {"frac_ear_to_lips": 0.5, "fallback_forward_mm": 40.0, "fallback_up_mm": -15.0},
        "timeout_s": timeout_s,
        "keep_h5": False,
        "mapping": MAPPING,
        "config": cfg,
    }


if __name__ == "__main__":
    out, toks = sys.argv[1], sys.argv[2].split(",")
    budget = int(sys.argv[sys.argv.index("--budget") + 1]) if "--budget" in sys.argv else None
    spec = {"runs": [run(t) for t in toks]}
    if budget:
        spec["budget_s"] = budget
    json.dump(spec, open(out, "w"), indent=1)
    print(out, [r["name"] for r in spec["runs"]])
