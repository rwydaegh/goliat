import h5py
import numpy as np
from typing import Tuple


def get_slice_indices(axis, b_min, b_max):
    """Calculates start/end indices for a given axis and physical bounds."""
    start = np.searchsorted(axis, b_min, side="left")
    end = np.searchsorted(axis, b_max, side="right")
    # Clamp to axis range
    start = max(0, start)
    end = min(len(axis), end)
    return slice(start, end)


def slice_h5_output(input_file: str, output_file: str, center_m: Tuple[float, float, float], side_length_m: float):
    """Creates a sliced copy of a Sim4Life _Output.h5 file."""
    half_len = side_length_m / 2.0
    bounds = (
        (center_m[0] - half_len, center_m[0] + half_len),
        (center_m[1] - half_len, center_m[1] + half_len),
        (center_m[2] - half_len, center_m[2] + half_len),
    )

    print(f"Slicing {input_file} -> {output_file}")
    print(f"Center: {center_m} m, Side: {side_length_m} m")
    print(f"Bounds: {bounds}")

    with h5py.File(input_file, "r") as src, h5py.File(output_file, "w") as dst:
        # 1. Map meshes to their slices
        mesh_slices = {}  # mesh_path -> (slice_x, slice_y, slice_z)

        # We'll first pre-scan the meshes to determine slices for each one
        if "Meshes" in src:
            for mesh_id in src["Meshes"]:
                m_path = f"Meshes/{mesh_id}"
                if "axis_x" in src[m_path]:
                    ax_x = src[f"{m_path}/axis_x"][:]
                    ax_y = src[f"{m_path}/axis_y"][:]
                    ax_z = src[f"{m_path}/axis_z"][:]

                    sx = get_slice_indices(ax_x, bounds[0][0], bounds[0][1])
                    sy = get_slice_indices(ax_y, bounds[1][0], bounds[1][1])
                    sz = get_slice_indices(ax_z, bounds[2][0], bounds[2][1])
                    mesh_slices[m_path] = (sx, sy, sz, len(ax_x), len(ax_y), len(ax_z))
                    print(f"Mesh {mesh_id}: X:{sx}, Y:{sy}, Z:{sz}")

        # 2. Identify which mesh each FieldGroup uses
        # FieldGroups usually have a RefId or similar, but often it's direct.
        # Sim4Life FDTD results usually use the discretization grid.
        # We can try to guess by looking for meshes with similar dimensions or by common naming.

        # For this implementation, we'll assume field datasets should be sliced using
        # the mesh that has the same prefix if possible, or the largest mesh.
        # Actually, let's just find the mesh that fits the FieldGroup's dimensions.

        def find_best_mesh(data_shape):
            # data_shape is (NX, NY, NZ, ...)
            # We look for a mesh where data_shape[0..2] is either N or N-1 of axis lengths
            for m_path, (sx, sy, sz, NX, NY, NZ) in mesh_slices.items():
                match = True
                for i, dim in enumerate(data_shape[:3]):
                    ax_len = [NX, NY, NZ][i]
                    if dim != ax_len and dim != ax_len - 1:
                        match = False
                        break
                if match:
                    return m_path
            return None

        # 3. Recursively copy and slice
        def copy_visitor(name, obj):
            if isinstance(obj, h5py.Group):
                if name in dst:
                    return  # Already created
                dst_obj = dst.create_group(name)
                for key, val in obj.attrs.items():
                    dst_obj.attrs[key] = val
            elif isinstance(obj, h5py.Dataset):
                # Determine if we slice this dataset
                should_slice = False
                current_slice = None

                # Case 1: Axis datasets in Meshes
                parent_path = "/".join(name.split("/")[:-1])
                if parent_path in mesh_slices:
                    if name.endswith("axis_x"):
                        should_slice = True
                        current_slice = mesh_slices[parent_path][0]
                    elif name.endswith("axis_y"):
                        should_slice = True
                        current_slice = mesh_slices[parent_path][1]
                    elif name.endswith("axis_z"):
                        should_slice = True
                        current_slice = mesh_slices[parent_path][2]

                # Case 2: 3D/4D datasets (voxels, fields, etc.)
                if not should_slice and len(obj.shape) >= 3:
                    m_path = find_best_mesh(obj.shape)
                    if m_path:
                        sx, sy, sz, NX, NY, NZ = mesh_slices[m_path]
                        s = []
                        for i, dim_len in enumerate(obj.shape[:3]):
                            ax_len = [NX, NY, NZ][i]
                            sl = [sx, sy, sz][i]

                            start = sl.start
                            stop = sl.stop

                            # Correct handle for Yee grid (N vs N-1)
                            # If axis slice is start:stop (length N), the data slice
                            # for intervals should be start:stop-1 (length N-1).
                            if dim_len == ax_len - 1:
                                stop = max(start, stop - 1)

                            # Safety clamp
                            stop = min(dim_len, stop)
                            start = min(dim_len, start)

                            s.append(slice(start, stop))

                        for dim_len in obj.shape[3:]:
                            s.append(slice(None))

                        should_slice = True
                        current_slice = tuple(s)

                # Create and copy dataset
                if should_slice:
                    # print(f"  SLICING dataset: {name} | shape {obj.shape} -> {current_slice}")
                    data = obj[current_slice]
                    dst_dataset = dst.create_dataset(name, data=data)
                elif name.endswith("bounding_box"):
                    # Update bounding box to match the NEW total dimensions
                    # We assume the bounding box now covers the entire sliced region
                    # for the referenced mesh.
                    # Sim4Life bounding_box for rectilinear meshes is often [0, TotalCells-1]
                    # Find any mesh axis to compute new total
                    try:
                        # Find the best mesh for this bounding box?
                        # Usually the parent mesh has the axes, or it's a submesh.
                        # For now, let's just use the FIRST mesh that was sliced.
                        first_m = list(mesh_slices.values())[0]
                        # Correct sliced lengths (N-1 for cells if it was a cell-based BB)
                        # Original BB was [0, NX*NY*NZ - 1]
                        NX_new = first_m[0].stop - first_m[0].start
                        NY_new = first_m[1].stop - first_m[1].start
                        NZ_new = first_m[2].stop - first_m[2].start

                        # Node count (NX*NY*NZ) instead of Voxel count
                        total_nodes_new = NX_new * NY_new * NZ_new
                        bb_max = max(0, total_nodes_new - 1)

                        print(f"  Updating bounding_box {name}: [0, {bb_max}]")
                        dst_dataset = dst.create_dataset(name, data=np.array([0, bb_max], dtype=obj.dtype))
                    except Exception as e:
                        print(f"  Warning: Could not update bounding_box {name}: {e}")
                        dst_dataset = dst.create_dataset(name, data=obj[:])
                else:
                    # Copy entirely
                    # print(f"  COPYING dataset: {name} | shape {obj.shape}")
                    if obj.shape == ():
                        dst_dataset = dst.create_dataset(name, data=obj[()])
                    else:
                        dst_dataset = dst.create_dataset(name, data=obj[:])

                # Copy attributes
                for key, val in obj.attrs.items():
                    dst_dataset.attrs[key] = val

        src.visititems(copy_visitor)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Slice Sim4Life _Output.h5 file around a center point.")
    parser.add_argument("input", help="Source H5 file")
    parser.add_argument("output", help="Destination H5 file")
    parser.add_argument("--center", type=float, nargs=3, required=True, help="Center coordinates in meters (x y z)")
    parser.add_argument("--size", type=float, default=0.05, help="Cube side length in meters (default 0.05m)")

    args = parser.parse_args()
    slice_h5_output(args.input, args.output, tuple(args.center), args.size)
