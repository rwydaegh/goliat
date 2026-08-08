# Scale a Sim4Life phantom (.sab) by a uniform factor and save under a new
# phantom name, preserving entity names and material grouping so that
# goliat can reuse the existing material-name mapping for the parent
# phantom.
#
# Used by the AEGIS scaled-thelonious validation campaign: scale_thelonious.py
# on the AEGIS side produces the surface STL; this script produces the
# matching Sim4Life-side voxel model (`thelonious_one_third.sab`) by applying
# the same transform to the entire CAD entity tree.
#
# Usage on the VM:
#   cd ~/goliat && "/c/Program Files/Sim4Life_8.2.0.16876/Python/python" \
#       goliat/utils/scripts/scale_phantom.py \
#           --src data/phantoms/thelonious.sab \
#           --dst data/phantoms/thelonious_one_third.sab \
#           --factor 0.3333333333333333

import argparse
import logging
import os

import s4l_v1
import s4l_v1.document as document
import s4l_v1.model as model
import XCoreModeling
from s4l_v1._api.application import run_application
from s4l_v1.model import Vec3

logger = logging.getLogger("scale_phantom")


def scale_sab(src_path: str, dst_path: str, factor: float) -> None:
    """Open `src_path`, apply uniform `factor` to all imported entities, save
    to `dst_path`."""
    if not os.path.exists(src_path):
        raise FileNotFoundError(f"Source .sab not found: {src_path}")

    print(f"[scale_phantom] importing {src_path}")
    document.New()
    imported = list(XCoreModeling.Import(src_path))
    print(f"[scale_phantom] imported {len(imported)} top-level entities")

    # Build a uniform-scale transform around the world origin.  The phantom
    # coordinates remain self-consistent (skin, organs, eyes all shrink
    # together).  Goliat builds its sim bbox from the phantom entities so the
    # padding is recomputed automatically.
    scale_vec = Vec3(factor, factor, factor)
    rot = Vec3(0.0, 0.0, 0.0)
    trans = Vec3(0.0, 0.0, 0.0)
    transform = model.Transform(scale_vec, rot, trans)

    # Apply transform to each top-level entity (groups propagate to children).
    n_applied = 0
    for entity in imported:
        try:
            entity.ApplyTransform(transform)
            n_applied += 1
        except Exception as exc:  # noqa: BLE001
            print(f"[scale_phantom] WARNING: could not transform {entity.Name!r}: {exc}")

    print(f"[scale_phantom] transformed {n_applied} entities by factor {factor}")

    # Sanity-check: print the new bounding box.
    try:
        bbox = model.GetBoundingBox(imported)
        bb_min, bb_max = bbox[0], bbox[1]
        print(
            f"[scale_phantom] bbox: "
            f"({bb_min[0]:+.4f}, {bb_min[1]:+.4f}, {bb_min[2]:+.4f}) "
            f"to ({bb_max[0]:+.4f}, {bb_max[1]:+.4f}, {bb_max[2]:+.4f}) m"
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[scale_phantom] bbox query failed: {exc}")

    print(f"[scale_phantom] exporting {dst_path}")
    os.makedirs(os.path.dirname(dst_path), exist_ok=True)
    model.Export(imported, dst_path)
    document.Close()
    print("[scale_phantom] done")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--src", required=True, help="Source .sab file path")
    ap.add_argument("--dst", required=True, help="Destination .sab file path")
    ap.add_argument("--factor", type=float, required=True, help="Uniform scale factor")
    args = ap.parse_args()

    run_application(disable_ui_plugins=True)
    try:
        scale_sab(args.src, args.dst, args.factor)
    finally:
        if s4l_v1.document.IsOpen():
            s4l_v1.document.Close()


if __name__ == "__main__":
    main()
