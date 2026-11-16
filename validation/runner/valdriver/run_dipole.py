"""Case 4: IEEE 1528 reference dipole over a flat phantom, through GOLIAT's NEAR-FIELD study path.

GOLIAT code that runs unmodified: NearFieldStudy.run() -> PhantomSetup (imports the .sab),
NearFieldSetup._setup_simulation_entity (solver settings, sim time, termination),
_configure_overall_field_sensor, MaterialSetup (background + antenna PEC from antenna_config),
GriddingSetup (global per-frequency grid + antenna_config component grids), BoundarySetup,
SourceSetup (edge source + edge sensor on 'Feed'), _finalize_setup (voxelize), SimulationRunner,
ResultsExtractor (near-field input power from 'Input Power', SAR stats incl. psSAR 1 g / 10 g,
power balance) and NearFieldStrategy.get_normalization_factor (target_power_mW = 1000 -> per 1 W).

SCRIPTED (replaces GOLIAT's phone import + anatomical landmark placement; NOT GOLIAT evidence):
  * the dipole (two PEC cylinders d = 3.6 mm + 1 mm feed gap, 'Feed' polyline), its placement
    (axis parallel to the liquid surface at distance s, centred) and the 'Antenna bounding box'
    -> patch of PlacementSetup.place_antenna
  * the simulation bounding box (phantom + dipole + air margins) -> patch of _create_simulation_bbox
  * head/trunk bbox creation skipped (no anatomy) -> patch of _setup_bounding_boxes
  * liquid / shell dielectric constants (not in IT'IS 4.2) -> patch of _assign_phantom_materials
  + the same two generic shims as run_one.py (S4L 9.6 setattr no-ops, 8 MB output threshold).
"""

import json
import os
import sys
import time
import traceback
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
SPEC = json.loads(Path(sys.argv[1]).read_text())
OUT = Path(os.environ["GOLIATVAL_OUT"])
SRC = Path(os.environ["GOLIATVAL_SRC"])
REPORT = {"spec": SPEC, "stages": {}, "notes": []}
PHANTOM = "valflat"
SCEN, POS, ORI = "ieee_flat", "center", "base"
PLACEMENT = f"{SCEN}_{POS}_{ORI}"


def save_report():
    (OUT / "driver_report.json").write_text(json.dumps(REPORT, indent=1, default=str))


def box_mesh(lo, hi):
    x0, y0, z0 = lo
    x1, y1, z1 = hi
    V = np.array([[x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0], [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]], float)
    F = np.array(
        [[0, 2, 1], [0, 3, 2], [4, 5, 6], [4, 6, 7], [0, 1, 5], [0, 5, 4], [1, 2, 6], [1, 6, 5], [2, 3, 7], [2, 7, 6], [3, 0, 4], [3, 4, 7]]
    )
    return V, F


def write_stl(path, V, F):
    import struct

    with open(path, "wb") as fh:
        fh.write(b"goliat-validation".ljust(80, b" "))
        fh.write(struct.pack("<I", len(F)))
        for a, b, c in F:
            n = np.cross(V[b] - V[a], V[c] - V[a])
            n = n / (np.linalg.norm(n) or 1)
            fh.write(struct.pack("<12fH", *n, *V[a], *V[b], *V[c], 0))


def build_phantom(base):
    """Liquid box (top face z = 0) + 2 mm shell slab on top (0 < z < 2 mm); exported to .sab."""
    from goliat.utils.core import ensure_s4l_running

    ensure_s4l_running()
    import s4l_v1.document as document
    import s4l_v1.model as model

    g = SPEC["geometry"]
    Lx, Ly, D, t = g["liquid_x_mm"], g["liquid_y_mm"], g["liquid_depth_mm"], g["shell_mm"]
    parts = {"Liquid": ([-Lx / 2, -Ly / 2, -D], [Lx / 2, Ly / 2, 0.0]), "Shell": ([-Lx / 2, -Ly / 2, 0.0], [Lx / 2, Ly / 2, t])}
    document.New()
    ents = []
    for name, (lo, hi) in parts.items():
        stl = base / f"{name}.stl"
        write_stl(stl, *box_mesh(lo, hi))
        e = list(model.Import(str(stl)))[0]
        e.Name = name
        ents.append(e)
    REPORT["phantom_entities"] = [(e.Name, type(e).__name__) for e in ents]
    ph = base / "data" / "phantoms"
    ph.mkdir(parents=True, exist_ok=True)
    model.Export(ents, str(ph / f"{PHANTOM}.sab"))
    document.New()


def write_config(base):
    f = str(SPEC["frequency_mhz"])
    nf = json.loads((SRC / "goliat" / "config" / "defaults" / "near_field_config.json").read_text())
    for k in ("extends", "antenna_config", "placement_scenarios", "phantom_definitions", "phantoms"):
        nf.pop(k, None)
    a = SPEC["antenna"]
    cfg = {"extends": "base_config.json", **nf}
    cfg.update(
        {
            "study_type": "near_field",
            "phantoms": [PHANTOM],
            "antenna_config": {
                f: {
                    "center_frequency": int(f),
                    "target_power_mW": 1000,
                    "model_type": "DIPOLE",
                    "source_name": "Feed",
                    "materials": {"Arm_pos": "PEC", "Arm_neg": "PEC"},
                    "gridding": {
                        "automatic": ["Feed"],
                        "manual": {"arms": ["Arm_pos", "Arm_neg"]},
                        "manual_grid_step": {"arms": a["arm_grid_mm"]},
                    },
                }
            },
            "placement_scenarios": {SCEN: {"bounding_box": "whole_body", "positions": {POS: [0, 0, 0]}, "orientations": {ORI: []}}},
            "phantom_definitions": {PHANTOM: {"placements": {f"do_{SCEN}": True}}},
        }
    )
    from specs_merge import deep_update

    deep_update(cfg, SPEC.get("config", {}))
    (base / "configs").mkdir(parents=True, exist_ok=True)
    (base / "configs" / "validation.json").write_text(json.dumps(cfg, indent=1))
    mapping = {PHANTOM: {"Liquid": "Liquid", "Shell": "Shell", "_tissue_groups": {"skin_group": []}}}
    (base / "data").mkdir(parents=True, exist_ok=True)
    (base / "data" / "material_name_mapping.json").write_text(json.dumps(mapping, indent=1))
    if not (base / "goliat").exists():
        os.symlink(SRC / "goliat", base / "goliat")


def install_patches():
    import s4l_v1.model as model
    import XCoreModeling
    from shims import install_permissive_setattr

    import goliat.project_manager as _pm
    from goliat.setups.material_setup import MaterialSetup
    from goliat.setups.near_field_setup import NearFieldSetup
    from goliat.setups.placement_setup import PlacementSetup

    install_permissive_setattr(REPORT)
    REPORT["shim_min_h5_bytes_original"] = _pm.MIN_H5_FILE_SIZE_BYTES
    _pm.MIN_H5_FILE_SIZE_BYTES = 1
    a, g = SPEC["antenna"], SPEC["geometry"]
    Vec3 = model.Vec3

    def place_antenna(self):  # SCRIPTED dipole + placement
        L, r, gap, s = a["length_mm"], a["diameter_mm"] / 2, a["gap_mm"], a["distance_mm"]
        z = float(s)  # dipole axis to LIQUID surface (z = 0); the 2 mm shell lies in between
        arm_p = XCoreModeling.CreateSolidCylinder(Vec3(gap / 2, 0, z), Vec3(L / 2, 0, z), r)
        arm_p.Name = "Arm_pos"
        arm_n = XCoreModeling.CreateSolidCylinder(Vec3(-L / 2, 0, z), Vec3(-gap / 2, 0, z), r)
        arm_n.Name = "Arm_neg"
        feed = XCoreModeling.CreatePolyLine([Vec3(-gap / 2, 0, z), Vec3(gap / 2, 0, z)])
        feed.Name = "Feed"
        grp = XCoreModeling.CreateGroup(f"Antenna {self.antenna.frequency_mhz} MHz ({self.placement_name})")
        for e in (arm_p, arm_n, feed):
            grp.Add(e)
        bmin, bmax = model.GetBoundingBox([arm_p, arm_n])
        bb = XCoreModeling.CreateWireBlock(bmin, bmax)
        bb.Name = f"Antenna bounding box ({self.placement_name})"
        REPORT["dipole"] = {"axis_z_mm": z, "length_mm": L, "radius_mm": r, "gap_mm": gap, "group_children": [e.Name for e in grp.Entities]}

    def create_sim_bbox(self):  # SCRIPTED domain
        m = SPEC["domain_margin_mm"]
        ph = [e for e in self.model.AllEntities() if isinstance(e, XCoreModeling.TriangleMesh)]
        pmin, pmax = self.model.GetBoundingBox(ph)
        lo = np.array([pmin[0], pmin[1], pmin[2]]) - np.array(m["lateral_below"])
        hi = np.array([pmax[0], pmax[1], a["distance_mm"]]) + np.array(m["lateral_above"])
        sb = XCoreModeling.CreateWireBlock(Vec3(*lo), Vec3(*hi))
        sb.Name = f"{self.placement_name.lower()}_simulation_bbox"
        REPORT["sim_bbox_mm"] = [lo.tolist(), hi.tolist()]

    def assign_phantom_materials(self):  # SCRIPTED IEEE 1528 liquid + shell
        ents = {e.Name.split("(")[0].strip(): e for e in self.model.AllEntities() if isinstance(e, XCoreModeling.TriangleMesh)}
        for name, props in (("Liquid", g["liquid"]), ("Shell", g["shell"])):
            ms = self.emfdtd.MaterialSettings()
            ms.Name = name
            ms.ElectricProps.RelativePermittivity = props["eps_r"]
            ms.ElectricProps.Conductivity = props["sigma"]
            ms.MassDensity = props["rho"]
            self.simulation.Add(ms, [ents[name]])
        REPORT["phantom_materials"] = {"Liquid": g["liquid"], "Shell": g["shell"]}

    PlacementSetup.place_antenna = place_antenna
    NearFieldSetup._create_simulation_bbox = create_sim_bbox
    NearFieldSetup._setup_bounding_boxes = lambda self: None
    MaterialSetup._assign_phantom_materials = assign_phantom_materials


def run_study(base):
    os.chdir(base)
    install_patches()
    from goliat.logging_manager import setup_loggers
    from goliat.studies.near_field_study import NearFieldStudy

    setup_loggers(process_id="val")
    study = NearFieldStudy(study_type="near_field", config_filename="validation.json", gui=None, no_cache=True)
    REPORT["merged_config_keys"] = sorted(study.config.config.keys())
    try:
        study.run()
    finally:
        from shims import PERMISSIVE

        REPORT["permissive_setattr_hits"] = sorted(set(PERMISSIVE))
    # GOLIAT's own near-field normalisation (target_power_mW = 1000 -> per 1 W input power)
    import glob

    from goliat.analysis.near_field_strategy import NearFieldAnalysisStrategy

    for sr in glob.glob(str(base / "results" / "**" / "sar_results.json"), recursive=True):
        res = json.loads(Path(sr).read_text())
        k = NearFieldAnalysisStrategy(study.config, PHANTOM).get_normalization_factor(int(SPEC["frequency_mhz"]), res.get("input_power_W"))
        REPORT["normalised_per_1W"] = {
            "norm_factor": k,
            "input_power_W": res.get("input_power_W"),
            "psSAR1g": (res.get("peak_sar_1g_W_kg") or 0) * k,
            "psSAR10g": (res.get("peak_sar_10g_W_kg") or 0) * k,
            "sar_results": sr,
        }


def main():
    base = Path("/tmp/goliatval/runs") / SPEC["name"]
    base.mkdir(parents=True, exist_ok=True)
    for name, fn in (("write_config", write_config), ("build_phantom", build_phantom), ("study", run_study)):
        t = time.time()
        try:
            fn(base)
            REPORT["stages"][name] = {"ok": True, "s": round(time.time() - t, 1)}
        except Exception:  # noqa: BLE001
            REPORT["stages"][name] = {"ok": False, "tb": traceback.format_exc()}
            REPORT["fatal"] = traceback.format_exc()
            save_report()
            break
        save_report()
    from run_one_collect import collect, inspect_h5

    try:
        REPORT["h5"] = inspect_h5(base)
    except Exception as e:  # noqa: BLE001
        REPORT["h5"] = repr(e)
    collect(base, OUT, SPEC.get("keep_h5", False))
    save_report()


if __name__ == "__main__":
    main()
