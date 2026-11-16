"""Case 5: dipole / 4x4 dipole array in front of the LEFT cheek of the ViP Ella head (Li et al. 2026 PMB 71 01NT02).

GOLIAT code that runs unmodified: NearFieldStudy.run() -> PhantomSetup (imports data/phantoms/ella.sab),
PlacementSetup._get_placement_details ('by_cheek*' landmark logic: Ear_skin bbox + phantom_definitions lips;
called and logged, its y/z reference is reused), NearFieldSetup._setup_simulation_entity (solver, sim time,
termination), _configure_overall_field_sensor, MaterialSetup (IT'IS 4.2 tissue mapping for Ella from
data/material_name_mapping.json + antenna PEC from antenna_config), GriddingSetup (global per-frequency
step + antenna_config component grids), BoundarySetup (PML strength from config), SourceSetup (edge source
+ edge sensor), _finalize_setup (voxelise), SimulationRunner, ResultsExtractor (input power, SAR, power
balance, SapdExtractor: GenericSAPDEvaluator on skin_group = Skin + Ear_skin, 4 cm^2, 10 mm threshold) and
NearFieldAnalysisStrategy.get_normalization_factor (target_power_mW = 10 -> per 10 mW input power).

SCRIPTED (documented in validation/README.md, Case 5):
  * antenna: PEC solid-cylinder half-wave dipole(s) (L = length_lambda * lambda, radius = 1 cell,
    feed gap = 2 cells), axis vertical (model z), array = 4x4 in the sagittal (y-z) plane, pitch lambda/2,
    all feeds driven by ONE EdgeSourceSettings (equal amplitude, in phase) -> patch of place_antenna and a
    proxy that expands GOLIAT's single-feed Add() to all feeds.
  * placement: cheek point = ear centre + frac * (lips - ear centre) in y/z (GOLIAT's by_cheek landmarks),
    mirrored to the LEFT side; antenna centre at distance d from the Skin surface (GetEntityPointDistance
    bisection along x).
  * domain: cropped face region (antenna bbox + >= pad_mm air on every side, tissue_depth_mm into the head);
    tissues whose bbox misses the crop are deleted before material assignment -> patch of
    _setup_bounding_boxes (Ella has no head/trunk separation definitions) and _create_simulation_bbox.
  * SAPD 1 cm^2: after GOLIAT's 4 cm^2 report, the same evaluator is re-run with AveragingArea = 1 cm^2.
  + the generic shims (S4L 9.6 setattr no-ops, 8 MB output threshold).
"""

import copy
import json
import os
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
SPEC = json.loads(Path(sys.argv[1]).read_text())
OUT = Path(os.environ["GOLIATVAL_OUT"])
SRC = Path(os.environ["GOLIATVAL_SRC"])
REPORT = {"spec": {k: v for k, v in SPEC.items() if k != "mapping"}, "stages": {}, "notes": []}
PHANTOM = "ella"
SCEN, POS, ORI = "by_cheek_li", "d", "vertical"
PLACEMENT = f"{SCEN}_{POS}_{ORI}"
C0 = 299792458.0
GEOM = {}


def save_report():
    (OUT / "driver_report.json").write_text(json.dumps(REPORT, indent=1, default=str))


def write_config(base):
    f = str(SPEC["frequency_mhz"])
    nf = json.loads((SRC / "goliat" / "config" / "defaults" / "near_field_config.json").read_text())
    ella_def = copy.deepcopy(nf["phantom_definitions"][PHANTOM])
    for k in ("extends", "antenna_config", "placement_scenarios", "phantom_definitions", "phantoms"):
        nf.pop(k, None)
    lam_mm = C0 / (SPEC["frequency_mhz"] * 1e6) * 1e3
    dx = SPEC["grid_mm"]
    n = SPEC["array_n"]
    arms = [f"Arm_{s}_{i}" for i in range(n * n) for s in ("pos", "neg")]
    feeds = [f"Feed_{i}" for i in range(n * n)]
    GEOM.update({"lambda_mm": lam_mm, "arms": arms, "feeds": feeds})
    cfg = {"extends": "base_config.json", **nf}
    ella_def["placements"] = {f"do_{SCEN}": True, "distance_from_cheek": 0}
    ella_def["li_reference"] = [0, 0, 0]
    cfg.update(
        {
            "study_type": "near_field",
            "phantoms": [PHANTOM],
            "antenna_config": {
                f: {
                    "center_frequency": int(f),
                    "target_power_mW": 10,
                    "model_type": "DIPOLE",
                    "source_name": feeds[0],
                    "materials": {a: "PEC" for a in arms},
                    "gridding": {"automatic": feeds, "manual": {"arms": arms}, "manual_grid_step": {"arms": [dx, dx, dx]}},
                }
            },
            "placement_scenarios": {
                SCEN: {
                    "bounding_box": "default",
                    "phantom_reference": "li_reference",
                    "positions": {POS: [0, 0, 0]},
                    "orientations": {ORI: []},
                }
            },
            "phantom_definitions": {PHANTOM: ella_def},
        }
    )
    from specs_merge import deep_update

    deep_update(cfg, SPEC.get("config", {}))
    (base / "configs").mkdir(parents=True, exist_ok=True)
    (base / "configs" / "validation.json").write_text(json.dumps(cfg, indent=1))
    (base / "data" / "phantoms").mkdir(parents=True, exist_ok=True)
    (base / "data" / "material_name_mapping.json").write_text(json.dumps({PHANTOM: SPEC["mapping"]}, indent=1))
    sab = next(Path(os.environ.get("INPUT_FOLDER") or os.environ.get("INPUTS_FOLDER") or "/inputs").rglob(f"{PHANTOM}.sab"))
    dst = base / "data" / "phantoms" / f"{PHANTOM}.sab"
    if not dst.exists():
        os.symlink(sab, dst)
    REPORT["phantom_sab"] = [str(sab), sab.stat().st_size]
    if not (base / "goliat").exists():
        os.symlink(SRC / "goliat", base / "goliat")


def _walk(ents, out=None):
    out = [] if out is None else out
    for e in ents:
        if hasattr(e, "Name"):
            out.append(e)
        kids = getattr(e, "Entities", None)
        if kids:
            _walk(list(kids), out)
    return out


def _bbox(model, ents):
    lo, hi = model.GetBoundingBox(ents)
    return [lo[0], lo[1], lo[2]], [hi[0], hi[1], hi[2]]


def install_patches():
    import numpy as np
    import s4l_v1.model as model
    import s4l_v1.units as units
    import XCoreModeling
    from shims import install_permissive_setattr

    import goliat.project_manager as _pm
    from goliat.extraction.sapd_extractor import SapdExtractor
    from goliat.setups.near_field_setup import NearFieldSetup
    from goliat.setups.placement_setup import PlacementSetup
    from goliat.setups.source_setup import SourceSetup

    install_permissive_setattr(REPORT)
    REPORT["shim_min_h5_bytes_original"] = _pm.MIN_H5_FILE_SIZE_BYTES
    _pm.MIN_H5_FILE_SIZE_BYTES = 1
    Vec3 = model.Vec3
    pl = SPEC["placement"]

    def geometry_and_crop(self):  # SCRIPTED landmarks -> antenna centre, crop of the face region
        t = time.time()
        allents = _walk(self.model.AllEntities())
        REPORT["entity_names"] = sorted(f"{e.Name}|{type(e).__name__}" for e in allents)
        top = [e for e in self.model.AllEntities()]
        REPORT["top_level"] = [(e.Name, type(e).__name__, len(list(getattr(e, "Entities", []) or []))) for e in top]
        try:
            ella = next(e for e in top if e.Name == "Ella")
            REPORT["ella_group_attrs"] = [a for a in dir(ella) if not a.startswith("_")]
        except Exception as ex:  # noqa: BLE001
            REPORT["ella_group_attrs"] = repr(ex)
        save_report()
        ents = {e.Name: e for e in allents}
        lower = {e.Name.split("(")[0].strip().lower(): e for e in allents}
        skin = ents.get("Skin") or lower.get("skin")
        ear = ents.get("Ear_skin") or lower.get("ear_skin")
        if skin is None or ear is None:
            raise KeyError(f"Skin/Ear_skin not found; {len(allents)} entities, see entity_names")
        ear_lo, ear_hi = _bbox(self.model, [ear])
        ear_c = [(a + b) / 2 for a, b in zip(ear_lo, ear_hi)]
        eyes = [e for n, e in ents.items() if ("Eye" in n or "Cornea" in n) and isinstance(e, XCoreModeling.TriangleMesh)]
        eye_lo, eye_hi = _bbox(self.model, eyes)
        eye_c = [(a + b) / 2 for a, b in zip(eye_lo, eye_hi)]
        s_y = 1.0 if eye_c[1] > ear_c[1] else -1.0  # facing direction along y
        s_left = -s_y  # left = up x forward = z x (s_y y) = -s_y x
        lips = (self.config["phantom_definitions"] or {})[PHANTOM].get("lips")
        frac = pl["frac_ear_to_lips"]
        d_lips = [lips[i] - ear_c[i] for i in range(3)] if lips else None
        ok_lips = bool(lips) and 40 < abs(d_lips[1]) < 160 and abs(d_lips[2]) < 120 and s_y * d_lips[1] > 0
        if ok_lips:
            yc, zc = ear_c[1] + frac * d_lips[1], ear_c[2] + frac * d_lips[2]
            rule = f"ear centre + {frac} * (lips - ear centre)"
        else:
            yc, zc = ear_c[1] + s_y * pl["fallback_forward_mm"], ear_c[2] + pl["fallback_up_mm"]
            rule = f"fallback: ear centre + {pl['fallback_forward_mm']} mm forward, {pl['fallback_up_mm']} mm up"
        yc += s_y * pl.get("extra_forward_mm", 0.0)
        zc += pl.get("extra_up_mm", 0.0)
        d = SPEC["distance_mm"]

        def dist(x):
            return XCoreModeling.GetEntityPointDistance(skin, Vec3(x, yc, zc)).Distance

        x0 = ear_c[0]
        x_out = x0 + s_left * 250.0
        prev = x_out
        x = x_out
        dx_ = dist(x)
        while dx_ > d:  # step by (distance - d): the d-level set cannot lie closer than that
            prev = x
            x -= s_left * max(0.5, dx_ - d)
            if s_left * (x - x0) < 0:
                raise RuntimeError("no skin found along the cheek line")
            dx_ = dist(x)
        a, b = prev, x  # dist(a) > d >= dist(b)
        for _ in range(24):
            m = (a + b) / 2
            if dist(m) > d:
                a = m
            else:
                b = m
        xa = (a + b) / 2
        r = XCoreModeling.GetEntityPointDistance(skin, Vec3(xa, yc, zc))
        cp = r.ClosestPosition
        GEOM.update({"center": [xa, yc, zc], "s_left": s_left, "s_y": s_y, "skin_point": [cp[0], cp[1], cp[2]]})
        # antenna extent (dipoles along z, array in the y-z plane)
        lam = GEOM["lambda_mm"]
        L = SPEC["length_lambda"] * lam
        n = SPEC["array_n"]
        pitch = SPEC.get("pitch_lambda", 0.5) * lam
        half_y = (n - 1) / 2 * pitch + SPEC["grid_mm"]
        half_z = (n - 1) / 2 * pitch + L / 2
        pad = SPEC["pad_mm"]
        hy, hz = max(half_y + pad, SPEC["min_half_mm"]), max(half_z + pad, SPEC["min_half_mm"])
        x_air = xa + s_left * pad
        x_tis = cp[0] - s_left * SPEC["tissue_depth_mm"]
        lo = [min(x_air, x_tis), yc - hy, zc - hz]
        hi = [max(x_air, x_tis), yc + hy, zc + hz]
        GEOM["crop"] = [lo, hi]
        # delete tissue meshes that do not reach into the crop box
        kept, deleted = [], []
        for e in [e for e in self.model.AllEntities() if isinstance(e, XCoreModeling.TriangleMesh)]:
            elo, ehi = _bbox(self.model, [e])
            inside = all(elo[i] <= hi[i] and ehi[i] >= lo[i] for i in range(3))
            if inside:
                kept.append(e.Name)
            else:
                deleted.append(e.Name)
                e.Delete()
        REPORT["geometry"] = {
            "ear_skin_bbox": [ear_lo, ear_hi],
            "ear_centre": ear_c,
            "eyes_centre": eye_c,
            "lips": lips,
            "lips_ok": ok_lips,
            "rule": rule,
            "facing_sign_y": s_y,
            "left_sign_x": s_left,
            "antenna_centre_mm": GEOM["center"],
            "closest_skin_point_mm": GEOM["skin_point"],
            "centre_to_skin_mm": r.Distance,
            "lambda_mm": lam,
            "dipole_length_mm": L,
            "pitch_mm": pitch,
            "crop_mm": [lo, hi],
            "tissues_kept": sorted(kept),
            "n_deleted": len(deleted),
            "s": round(time.time() - t, 1),
        }
        save_report()

    def place_antenna(self):  # SCRIPTED dipole(s); GOLIAT landmark details called and logged
        try:
            bt, off = self._get_placement_details()
            REPORT["goliat_by_cheek_details"] = {
                "base_target_point": [bt[0], bt[1], bt[2]],
                "offset": off,
                "orientation_rotations": self.orientation_rotations,
            }
        except Exception as e:  # noqa: BLE001
            REPORT["goliat_by_cheek_details"] = {"error": repr(e)}
        lam, dx, n = GEOM["lambda_mm"], SPEC["grid_mm"], SPEC["array_n"]
        L, r, gap = SPEC["length_lambda"] * lam, dx, 2 * dx
        pitch = SPEC.get("pitch_lambda", 0.5) * lam
        xc, yc, zc = GEOM["center"]
        grp = XCoreModeling.CreateGroup(f"Antenna {self.antenna.frequency_mhz} MHz ({self.placement_name})")
        parts, k = [], 0
        for iy in range(n):
            for iz in range(n):
                y = yc + (iy - (n - 1) / 2) * pitch
                z = zc + (iz - (n - 1) / 2) * pitch
                ap = XCoreModeling.CreateSolidCylinder(Vec3(xc, y, z + gap / 2), Vec3(xc, y, z + L / 2), r)
                ap.Name = f"Arm_pos_{k}"
                an = XCoreModeling.CreateSolidCylinder(Vec3(xc, y, z - L / 2), Vec3(xc, y, z - gap / 2), r)
                an.Name = f"Arm_neg_{k}"
                fd = XCoreModeling.CreatePolyLine([Vec3(xc, y, z - gap / 2), Vec3(xc, y, z + gap / 2)])
                fd.Name = f"Feed_{k}"
                for e in (ap, an, fd):
                    grp.Add(e)
                parts += [ap, an]
                k += 1
        lo, hi = _bbox(model, parts)
        bb = XCoreModeling.CreateWireBlock(Vec3(*lo), Vec3(*hi))
        bb.Name = f"Antenna bounding box ({self.placement_name})"
        skin = next(e for e in model.AllEntities() if getattr(e, "Name", "") == "Skin")
        ear = next(e for e in model.AllEntities() if getattr(e, "Name", "") == "Ear_skin")
        dmin_skin = min(XCoreModeling.GetEntityEntityDistance(skin, p)[0].Distance for p in parts)
        dmin_ear = min(XCoreModeling.GetEntityEntityDistance(ear, p)[0].Distance for p in parts)
        REPORT["antenna"] = {
            "n_elements": k,
            "length_mm": L,
            "radius_mm": r,
            "gap_mm": gap,
            "pitch_mm": pitch,
            "bbox_mm": [lo, hi],
            "min_metal_to_Skin_mm": dmin_skin,
            "min_metal_to_Ear_skin_mm": dmin_ear,
        }
        save_report()

    def create_sim_bbox(self):  # SCRIPTED cropped domain
        lo, hi = GEOM["crop"]
        sb = XCoreModeling.CreateWireBlock(Vec3(*lo), Vec3(*hi))
        sb.Name = f"{self.placement_name.lower()}_simulation_bbox"
        REPORT["sim_bbox_mm"] = [lo, hi]
        REPORT["sim_cells_estimate"] = int(np.prod([(hi[i] - lo[i]) / SPEC["grid_mm"] for i in range(3)]))
        save_report()

    class _AddProxy:
        """Expands GOLIAT's single-feed simulation.Add(settings, [Feed_0]) to all array feeds."""

        def __init__(self, sim, feeds):
            self._sim, self._feeds = sim, feeds

        def Add(self, settings, ents):  # noqa: N802
            if len(ents) == 1 and getattr(ents[0], "Name", "") == GEOM["feeds"][0]:
                ents = self._feeds
                REPORT.setdefault("feed_expansion", []).append(type(settings).__name__)
            return self._sim.Add(settings, ents)

        def __getattr__(self, k):
            return getattr(self._sim, k)

    orig_source = SourceSetup.setup_source_and_sensors

    def setup_source_and_sensors(self, antenna_components):
        feeds = [antenna_components[f] for f in GEOM["feeds"]]
        real = self.simulation
        if len(feeds) > 1:
            self.simulation = _AddProxy(real, feeds)
        try:
            return orig_source(self, antenna_components)
        finally:
            self.simulation = real

    orig_store = SapdExtractor._extract_and_store_results

    def extract_and_store(self, ev):  # GOLIAT 4 cm^2 report, then the same evaluator at 1 cm^2
        ok = orig_store(self, ev)
        res = self.results_data.setdefault("sapd_results", {})
        try:
            ev.AveragingArea = 1.0, units.SquareCentiMeters
            ev.UpdateAttributes()
            rep = ev.Outputs["Spatial-Averaged Power Density Report"]
            rep.Update()
            pk, loc = self._parse_sapd_data(rep.Data.DataSimpleDataCollection)
            res["peak_sapd_1cm2_W_m2"], res["peak_sapd_1cm2_location_m"] = pk, loc
            res["peak_sapd_4cm2_W_m2"] = res.get("peak_sapd_W_m2")
            dc = rep.Data.DataSimpleDataCollection
            res["report_keys_1cm2"] = list(dc.Keys())
        except Exception:  # noqa: BLE001
            res["sapd_1cm2_error"] = traceback.format_exc()
        REPORT["sapd_raw"] = res
        save_report()
        return ok

    NearFieldSetup._setup_bounding_boxes = geometry_and_crop
    PlacementSetup.place_antenna = place_antenna
    NearFieldSetup._create_simulation_bbox = create_sim_bbox
    SourceSetup.setup_source_and_sensors = setup_source_and_sensors
    SapdExtractor._extract_and_store_results = extract_and_store


def run_study(base):
    os.chdir(base)
    from goliat.utils.core import ensure_s4l_running

    ensure_s4l_running()
    install_patches()
    from goliat.logging_manager import setup_loggers
    from goliat.studies.near_field_study import NearFieldStudy

    setup_loggers(process_id="val")
    study = NearFieldStudy(study_type="near_field", config_filename="validation.json", gui=None, no_cache=True)
    try:
        study.run()
    finally:
        from shims import PERMISSIVE

        REPORT["permissive_setattr_hits"] = sorted(set(PERMISSIVE))
    import glob

    from goliat.analysis.near_field_strategy import NearFieldAnalysisStrategy

    for sr in glob.glob(str(base / "results" / "**" / "sar_results.json"), recursive=True):
        res = json.loads(Path(sr).read_text())
        k = NearFieldAnalysisStrategy(study.config, PHANTOM).get_normalization_factor(int(SPEC["frequency_mhz"]), res.get("input_power_W"))
        sp = {}
        for p in glob.glob(str(Path(sr).parent / "sapd_results.json")):
            sp = json.loads(Path(p).read_text())
        REPORT["normalised_10mW"] = {
            "norm_factor": k,
            "input_power_W": res.get("input_power_W"),
            "sAPD_1cm2_W_m2": (sp.get("peak_sapd_1cm2_W_m2") or 0) * k if sp.get("peak_sapd_1cm2_W_m2") is not None else None,
            "sAPD_4cm2_W_m2": (sp.get("peak_sapd_W_m2") or 0) * k if sp.get("peak_sapd_W_m2") is not None else None,
            "psSAR10g_W_kg": (res.get("peak_sar_10g_W_kg") or 0) * k,
            "sar_results": sr,
            "sapd_results": sp,
        }


def main():
    base = Path("/tmp/goliatval/runs") / SPEC["name"]
    base.mkdir(parents=True, exist_ok=True)
    for name, fn in (("write_config", write_config), ("study", run_study)):
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
