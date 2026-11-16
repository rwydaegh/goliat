import glob
import os
import shutil
from pathlib import Path

import numpy as np


def inspect_h5(base):
    import h5py

    res = {}
    for h5 in glob.glob(str(base / "results" / "**" / "*.h5"), recursive=True):
        entry = {"bytes": os.path.getsize(h5)}
        try:
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
        except Exception as e:  # noqa: BLE001
            entry["error"] = repr(e)
        res[os.path.relpath(h5, base)] = entry
    return res


def collect(base, out, keep_h5=False):
    dst = Path(out) / "files"
    for root, _dirs, files in os.walk(base):
        rel_root = os.path.relpath(root, base)
        if rel_root == "goliat" or rel_root.startswith("goliat" + os.sep):
            continue
        for fn in files:
            p = Path(root) / fn
            rel = p.relative_to(base)
            big = fn.endswith((".h5", ".smash", ".sab", ".stl"))
            if big and not (keep_h5 and fn.endswith("_Output.h5")):
                continue
            if p.stat().st_size > 50e6:
                continue
            (dst / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dst / rel)
