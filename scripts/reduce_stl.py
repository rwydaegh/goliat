#!/usr/bin/env python
"""
Reduce an STL mesh using Blender's Remesh and Decimate modifiers.

Usage:
    "C:\Program Files\Blender Foundation\Blender 4.4\blender.exe" --background --python scripts/reduce_stl.py -- input.stl output.stl
"""

import sys
from pathlib import Path


def get_script_args():
    """Parse arguments passed after '--' in the Blender command line."""
    try:
        idx = sys.argv.index("--")
        return sys.argv[idx + 1 :]
    except ValueError:
        return []


def main():
    import bpy

    args = get_script_args()

    if len(args) < 2:
        print("Usage: blender --background --python reduce_stl.py -- input.stl output.stl [voxel_size_mm] [decimate_ratio]")
        sys.exit(1)

    input_stl = Path(args[0])
    output_stl = Path(args[1])
    voxel_size_mm = float(args[2]) if len(args) > 2 else 1.0
    decimate_ratio = float(args[3]) if len(args) > 3 else 0.3

    print(f"\n{'=' * 60}")
    print("STL Mesh Reducer (Blender)")
    print(f"{'=' * 60}")
    print(f"Input:  {input_stl}")
    print(f"Output: {output_stl}")
    print(f"Voxel size: {voxel_size_mm} mm")
    print(f"Decimate ratio: {decimate_ratio}")

    # Clear scene
    bpy.ops.wm.read_factory_settings(use_empty=True)

    # Import STL
    print("\nImporting STL...")
    bpy.ops.wm.stl_import(filepath=str(input_stl))

    obj = bpy.context.selected_objects[0]
    bpy.context.view_layer.objects.active = obj

    print(f"Loaded: {len(obj.data.vertices):,} vertices, {len(obj.data.polygons):,} faces")

    # Add Remesh modifier
    print(f"\nApplying Remesh (voxel mode, {voxel_size_mm}mm)...")
    remesh = obj.modifiers.new(name="Remesh", type="REMESH")
    remesh.mode = "VOXEL"
    remesh.voxel_size = voxel_size_mm / 1000.0  # Convert mm to m
    remesh.adaptivity = 0.3
    remesh.use_smooth_shade = False

    # Add Decimate modifier
    print(f"Applying Decimate (ratio={decimate_ratio})...")
    decimate = obj.modifiers.new(name="Decimate", type="DECIMATE")
    decimate.decimate_type = "COLLAPSE"
    decimate.ratio = decimate_ratio

    # Apply modifiers
    print("Applying modifiers...")
    for mod in list(obj.modifiers):
        bpy.ops.object.modifier_apply(modifier=mod.name)

    print(f"Result: {len(obj.data.vertices):,} vertices, {len(obj.data.polygons):,} faces")

    # Export
    output_stl.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.stl_export(
        filepath=str(output_stl),
        export_selected_objects=True,
        ascii_format=False,
    )

    size_mb = output_stl.stat().st_size / (1024 * 1024)
    print(f"\nExported: {output_stl} ({size_mb:.2f} MB)")
    print("Done!")


if __name__ == "__main__":
    main()
