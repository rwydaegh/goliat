"""Run ONE GOLIAT far-field study headlessly inside the Sim4Life python runner.

What is GOLIAT code here: everything from FarFieldStudy.run() on (phantom import
via PhantomSetup, FarFieldSetup, material/grid/boundary setup, SimulationRunner
with Sim4LifeAPIStrategy, ResultsExtractor incl. SAR/power-balance/SAPD).

What this driver adds (the "shims"), nothing else:
  1. Builds the validation phantom (sphere or slab) as a Sim4Life TriangleMesh
     named after an IT'IS 4.2 tissue and exports it to data/phantoms/<name>.sab,
     which is the file GOLIAT's PhantomSetup imports (same as a licensed phantom).
  2. Writes data/material_name_mapping.json for that phantom and a study config
     that `extends` GOLIAT's shipped far_field_config.json with the overrides in
     the run spec.
  3. Sets cwd to a scratch base_dir (BaseStudy picks cwd when it has configs/).
  4. After the study, reads grid axes from the solver input/output .h5 with h5py
     and copies small deliverables to the output folder.
"""

import glob
import json
import os
import shutil
import struct
import sys
import time
import traceback
from pathlib import Path

import numpy as np

SPEC = json.loads(Path(sys.argv[1]).read_text())
OUT = Path(os.environ["GOLIATVAL_OUT"])
SRC = Path(os.environ["GOLIATVAL_SRC"])
REPORT = {"spec": SPEC, "stages": {}}


def save_report():
    (OUT / "driver_report.json").write_text(json.dumps(REPORT, indent=1, default=str))


def stage(name):
    def deco(fn):
        def wrapped(*a, **k):
            t = time.time()
            try:
                r = fn(*a, **k)
                REPORT["stages"][name] = {"ok": True, "s": round(time.time() - t, 2)}
                return r
            except Exception:
                REPORT["stages"][name] = {"ok": False, "s": round(time.time() - t, 2), "tb": traceback.format_exc()}
                save_report()
                raise
            finally:
                save_report()

        return wrapped

    return deco


# ---------------------------------------------------------------- geometry
def icosphere(level):
    t = (1 + 5**0.5) / 2
    v = [
        (-1, t, 0),
        (1, t, 0),
        (-1, -t, 0),
        (1, -t, 0),
        (0, -1, t),
        (0, 1, t),
        (0, -1, -t),
        (0, 1, -t),
        (t, 0, -1),
        (t, 0, 1),
        (-t, 0, -1),
        (-t, 0, 1),
    ]
    f = [
        (0, 11, 5),
        (0, 5, 1),
        (0, 1, 7),
        (0, 7, 10),
        (0, 10, 11),
        (1, 5, 9),
        (5, 11, 4),
        (11, 10, 2),
        (10, 7, 6),
        (7, 1, 8),
        (3, 9, 4),
        (3, 4, 2),
        (3, 2, 6),
        (3, 6, 8),
        (3, 8, 9),
        (4, 9, 5),
        (2, 4, 11),
        (6, 2, 10),
        (8, 6, 7),
        (9, 8, 1),
    ]
    verts = [np.array(p, float) / np.linalg.norm(p) for p in v]
    for _ in range(level):
        cache = {}
        nf = []

        def mid(a, b):
            key = (min(a, b), max(a, b))
            if key not in cache:
                m = verts[a] + verts[b]
                verts.append(m / np.linalg.norm(m))
                cache[key] = len(verts) - 1
            return cache[key]

        for a, b, c in f:
            ab, bc, ca = mid(a, b), mid(b, c), mid(c, a)
            nf += [(a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)]
        f = nf
    return np.array(verts), np.array(f)


def box_mesh(lo, hi):
    x0, y0, z0 = lo
    x1, y1, z1 = hi
    V = np.array([[x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0], [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]], float)
    F = np.array(
        [[0, 2, 1], [0, 3, 2], [4, 5, 6], [4, 6, 7], [0, 1, 5], [0, 5, 4], [1, 2, 6], [1, 6, 5], [2, 3, 7], [2, 7, 6], [3, 0, 4], [3, 4, 7]]
    )
    return V, F


def write_stl(path, V, F):
    with open(path, "wb") as fh:
        fh.write(b"goliat-validation".ljust(80, b" "))
        fh.write(struct.pack("<I", len(F)))
        for a, b, c in F:
            n = np.cross(V[b] - V[a], V[c] - V[a])
            n = n / (np.linalg.norm(n) or 1)
            fh.write(struct.pack("<12fH", *n, *V[a], *V[b], *V[c], 0))


def mesh_volume(V, F):
    return float(abs(np.einsum("ij,ij->i", V[F[:, 0]], np.cross(V[F[:, 1]], V[F[:, 2]])).sum()) / 6.0)


@stage("build_phantom")
def build_phantom(base):
    from goliat.utils.core import ensure_s4l_running

    ensure_s4l_running()
    import s4l_v1.document as document
    import s4l_v1.model as model
    import XCoreModeling

    try:
        import s4l_v1.simulation.emfdtd as emfdtd

        _s = emfdtd.Simulation()
        REPORT["sdk_sim_freq_attrs"] = [a for a in dir(_s) if "freq" in a.lower()]
        REPORT["sdk_version"] = str(getattr(__import__("s4l_v1"), "__version__", "?"))
    except Exception as e:  # noqa: BLE001
        REPORT["sdk_sim_freq_attrs"] = repr(e)
    geo = SPEC["geometry"]
    tissue = geo["tissue_entity"]
    if geo["kind"] == "sphere":
        V, F = icosphere(geo.get("ico_level", 6))
        V = V * geo["radius_mm"] + np.asarray(geo.get("center_mm", [0, 0, 0]), float)
    else:
        V, F = box_mesh(geo["lo_mm"], geo["hi_mm"])
    REPORT["mesh"] = {
        "n_vertices": len(V),
        "n_faces": len(F),
        "volume_mm3": mesh_volume(V, F),
        "bbox_min": V.min(0).tolist(),
        "bbox_max": V.max(0).tolist(),
    }
    stl = base / f"{tissue}.stl"
    write_stl(stl, V, F)
    document.New()
    ents = list(model.Import(str(stl)))
    info = []
    for e in ents:
        info.append({"name": e.Name, "type": type(e).__name__, "is_trimesh": isinstance(e, XCoreModeling.TriangleMesh)})
    REPORT["imported"] = info
    if not ents:
        raise RuntimeError("STL import returned nothing")
    ent = ents[0]
    ent.Name = tissue
    bb = model.GetBoundingBox([ent])
    REPORT["imported_bbox"] = [[float(c) for c in bb[0]], [float(c) for c in bb[1]]]
    if not isinstance(ent, XCoreModeling.TriangleMesh):
        raise RuntimeError(f"Imported entity is {type(ent).__name__}, not TriangleMesh")
    ph = base / "data" / "phantoms"
    ph.mkdir(parents=True, exist_ok=True)
    model.Export([ent], str(ph / f"{SPEC['phantom']}.sab"))
    document.New()


@stage("write_config")
def write_config(base):
    (base / "configs").mkdir(parents=True, exist_ok=True)
    (base / "data").mkdir(parents=True, exist_ok=True)
    tissue = SPEC["geometry"]["tissue_entity"]
    mapping = {
        SPEC["phantom"]: {
            tissue: SPEC["geometry"].get("itis_material", tissue),
            "_tissue_groups": {"skin_group": [tissue] if SPEC.get("skin_group") else []},
        }
    }
    (base / "data" / "material_name_mapping.json").write_text(json.dumps(mapping, indent=1))
    cfg = {"extends": "far_field_config.json"}
    cfg.update(SPEC["config"])
    (base / "configs" / "validation.json").write_text(json.dumps(cfg, indent=1))
    # Link GOLIAT defaults so Config can resolve far_field_config.json/base_config.json
    if not (base / "goliat").exists():
        os.symlink(SRC / "goliat", base / "goliat")


PERMISSIVE = []


def install_permissive_setattr():
    """SHIM: Sim4Life 9.6 API wrappers raise AttributeError('Cannot set unknown attribute ...')
    where older SDKs silently accepted an arbitrary Python attribute. GOLIAT sets two such
    non-properties (Simulation.Frequency, GlobalGridSettings.BoundingBox; neither exists in
    the 8.2 API reference either), so restoring the old no-op semantics does not change the
    scene. Every intercepted assignment is recorded in driver_report.json."""
    import inspect

    import s4l_v1

    mods = [m for n, m in sys.modules.items() if n.startswith("s4l_v1") and m is not None]
    patched = []
    for mod in mods:
        for cname, cls in list(vars(mod).items()):
            if not inspect.isclass(cls) or "__setattr__" not in cls.__dict__ or getattr(cls, "_goliatval_patched", False):
                continue
            orig = cls.__dict__["__setattr__"]

            def make(orig, cname):
                def __setattr__(self, k, v):
                    try:
                        orig(self, k, v)
                    except AttributeError as e:
                        if "unknown attribute" not in str(e):
                            raise
                        PERMISSIVE.append(f"{cname}.{k}")
                        try:
                            object.__setattr__(self, k, v)
                        except Exception:  # noqa: BLE001
                            pass

                return __setattr__

            cls.__setattr__ = make(orig, cname)
            cls._goliatval_patched = True
            patched.append(f"{mod.__name__}.{cname}")
    REPORT["shim_patched_classes"] = patched
    _ = s4l_v1


@stage("study")
def run_study(base):
    os.chdir(base)
    install_permissive_setattr()
    # SHIM 2: GOLIAT treats an _Output.h5 <= 8 MB (constants.MIN_H5_FILE_SIZE_BYTES) as an
    # incomplete iSolve run and skips extraction. Valid outputs of these small validation
    # grids are smaller than that, so the threshold is lowered to 1 byte for these runs only.
    import goliat.project_manager as _pm
    from goliat.logging_manager import setup_loggers
    from goliat.studies.far_field_study import FarFieldStudy

    REPORT["shim_min_h5_bytes_original"] = _pm.MIN_H5_FILE_SIZE_BYTES
    _pm.MIN_H5_FILE_SIZE_BYTES = 1
    setup_loggers(process_id="val")
    study = FarFieldStudy(study_type="far_field", config_filename="validation.json", gui=None, no_cache=True)
    REPORT["merged_config"] = study.config.config
    try:
        study.run()
    finally:
        REPORT["permissive_setattr_hits"] = sorted(set(PERMISSIVE))


@stage("inspect_outputs")
def inspect_outputs(base):
    import h5py

    res = {}
    for h5 in glob.glob(str(base / "results" / "**" / "*.h5"), recursive=True):
        try:
            entry = {"bytes": os.path.getsize(h5)}
            with h5py.File(h5, "r") as f:
                axes = []

                def visit(name, obj):
                    if isinstance(obj, h5py.Dataset) and name.split("/")[-1] in ("axis_x", "axis_y", "axis_z"):
                        a = obj[()].ravel()
                        d = np.diff(a)
                        axes.append(
                            {
                                "path": name,
                                "n": int(a.size),
                                "min": float(a.min()),
                                "max": float(a.max()),
                                "dmin": float(d.min()) if d.size else None,
                                "dmax": float(d.max()) if d.size else None,
                            }
                        )

                f.visititems(visit)
                entry["axes"] = axes[:12]
            res[os.path.relpath(h5, base)] = entry
        except Exception as e:  # noqa: BLE001
            res[os.path.relpath(h5, base)] = {"error": repr(e)}
    REPORT["h5"] = res


def collect(base):
    keep_h5 = SPEC.get("keep_h5", False)
    dst = OUT / "files"
    for root, _dirs, files in os.walk(base):
        if "/goliat" in root[len(str(base)) :][:8]:
            continue
        for fn in files:
            p = Path(root) / fn
            rel = p.relative_to(base)
            if str(rel).startswith("goliat"):
                continue
            big = fn.endswith((".h5", ".smash", ".sab", ".stl"))
            if big and not (keep_h5 and fn.endswith("_Output.h5")):
                continue
            if p.stat().st_size > 50e6:
                continue
            (dst / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dst / rel)


def main():
    base = Path("/tmp/goliatval/runs") / SPEC["name"]
    if base.exists():
        shutil.rmtree(base)
    base.mkdir(parents=True)
    try:
        write_config(base)
        build_phantom(base)
        run_study(base)
    except Exception:  # noqa: BLE001
        REPORT["fatal"] = traceback.format_exc()
    try:
        inspect_outputs(base)
    except Exception:  # noqa: BLE001
        pass
    collect(base)
    save_report()


if __name__ == "__main__":
    main()
