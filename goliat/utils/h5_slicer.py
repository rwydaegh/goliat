"""H5 file slicer for extracting regions around a center point.

Slices Sim4Life _Output.h5 files to a smaller cube around a given center,
preserving the HDF5 structure and updating axes/bounding boxes accordingly.
"""

import h5py
import numpy as np
from typing import Dict, Tuple, Optional


def get_slice_indices(axis: np.ndarray, b_min: float, b_max: float) -> slice:
    """Calculates start/end indices for a given axis and physical bounds."""
    start = np.searchsorted(axis, b_min, side="left")
    end = np.searchsorted(axis, b_max, side="right")
    # Clamp to axis range
    start = max(0, start)
    end = min(len(axis), end)
    return slice(start, end)


class H5Slicer:
    """Handles slicing of H5 datasets with proper mesh/bounds handling.

    Extracts the dataset copying logic from slice_h5_output into a class
    with dedicated methods for each dataset type.
    """

    def __init__(
        self,
        src: h5py.File,
        dst: h5py.File,
        mesh_slices: Dict[str, Tuple[slice, slice, slice, int, int, int]],
    ):
        """Initialize the slicer with source, destination, and mesh slice info.

        Args:
            src: Source H5 file (read mode).
            dst: Destination H5 file (write mode).
            mesh_slices: Dict mapping mesh paths to (sx, sy, sz, NX, NY, NZ).
        """
        self.src = src
        self.dst = dst
        self.mesh_slices = mesh_slices

    def find_best_mesh(self, data_shape: Tuple[int, ...]) -> Optional[str]:
        """Finds the mesh that matches a dataset's shape.

        Looks for a mesh where data_shape[0:3] matches either N or N-1
        of the axis lengths (for Yee grid staggering).

        Args:
            data_shape: Shape of the dataset (Nx, Ny, Nz, ...).

        Returns:
            Path to the matching mesh, or None if no match found.
        """
        for m_path, (sx, sy, sz, NX, NY, NZ) in self.mesh_slices.items():
            match = True
            for i, dim in enumerate(data_shape[:3]):
                ax_len = [NX, NY, NZ][i]
                if dim != ax_len and dim != ax_len - 1:
                    match = False
                    break
            if match:
                return m_path
        return None

    def copy_group(self, name: str, obj: h5py.Group) -> None:
        """Copies a group and its attributes to the destination."""
        if name in self.dst:
            return  # Already created
        dst_obj = self.dst.create_group(name)
        for key, val in obj.attrs.items():
            dst_obj.attrs[key] = val

    def _handle_axis_dataset(self, name: str, obj: h5py.Dataset) -> Optional[h5py.Dataset]:
        """Handles axis_x/y/z datasets by slicing them.

        Returns:
            The created dataset if handled, None otherwise.
        """
        parent_path = "/".join(name.split("/")[:-1])
        if parent_path not in self.mesh_slices:
            return None

        axis_map = {"axis_x": 0, "axis_y": 1, "axis_z": 2}
        for suffix, idx in axis_map.items():
            if name.endswith(suffix):
                current_slice = self.mesh_slices[parent_path][idx]
                data = obj[current_slice]
                return self.dst.create_dataset(name, data=data)
        return None

    def _handle_3d_dataset(self, name: str, obj: h5py.Dataset) -> Optional[h5py.Dataset]:
        """Handles 3D/4D field datasets by slicing them to match the mesh.

        Returns:
            The created dataset if handled, None otherwise.
        """
        if len(obj.shape) < 3:
            return None

        m_path = self.find_best_mesh(obj.shape)
        if m_path is None:
            return None

        sx, sy, sz, NX, NY, NZ = self.mesh_slices[m_path]
        slices = []

        for i, dim_len in enumerate(obj.shape[:3]):
            ax_len = [NX, NY, NZ][i]
            sl = [sx, sy, sz][i]
            start, stop = sl.start, sl.stop

            # Handle Yee grid offset (N vs N-1)
            if dim_len == ax_len - 1:
                stop = max(start, stop - 1)

            # Safety clamp
            stop = min(dim_len, stop)
            start = min(dim_len, start)
            slices.append(slice(start, stop))

        # Keep remaining dimensions intact
        for _ in obj.shape[3:]:
            slices.append(slice(None))

        data = obj[tuple(slices)]
        return self.dst.create_dataset(name, data=data)

    def _handle_bounding_box(self, name: str, obj: h5py.Dataset) -> h5py.Dataset:
        """Updates bounding box to match sliced dimensions.

        Returns:
            The created dataset with updated bounding box.
        """
        try:
            first_m = list(self.mesh_slices.values())[0]
            NX_new = first_m[0].stop - first_m[0].start
            NY_new = first_m[1].stop - first_m[1].start
            NZ_new = first_m[2].stop - first_m[2].start
            total_nodes_new = NX_new * NY_new * NZ_new
            bb_max = max(0, total_nodes_new - 1)
            return self.dst.create_dataset(name, data=np.array([0, bb_max], dtype=obj.dtype))
        except Exception:
            # Fallback: copy original
            return self.dst.create_dataset(name, data=obj[:])

    def _copy_dataset_verbatim(self, name: str, obj: h5py.Dataset) -> h5py.Dataset:
        """Copies a dataset without modification."""
        if obj.shape == ():
            return self.dst.create_dataset(name, data=obj[()])
        return self.dst.create_dataset(name, data=obj[:])

    def copy_dataset(self, name: str, obj: h5py.Dataset) -> None:
        """Copies a dataset, applying appropriate slicing based on type."""
        # Try axis dataset first
        dst_dataset = self._handle_axis_dataset(name, obj)

        # Try 3D dataset slicing
        if dst_dataset is None:
            dst_dataset = self._handle_3d_dataset(name, obj)

        # Handle bounding box
        if dst_dataset is None and name.endswith("bounding_box"):
            dst_dataset = self._handle_bounding_box(name, obj)

        # Fallback: copy verbatim
        if dst_dataset is None:
            dst_dataset = self._copy_dataset_verbatim(name, obj)

        # Copy attributes
        for key, val in obj.attrs.items():
            dst_dataset.attrs[key] = val

    def visit_item(self, name: str, obj) -> None:
        """Visitor callback for h5py.visititems."""
        if isinstance(obj, h5py.Group):
            self.copy_group(name, obj)
        elif isinstance(obj, h5py.Dataset):
            self.copy_dataset(name, obj)


def _build_mesh_slices(
    src: h5py.File,
    bounds: Tuple[Tuple[float, float], Tuple[float, float], Tuple[float, float]],
) -> Dict[str, Tuple[slice, slice, slice, int, int, int]]:
    """Scans meshes and computes slice indices for each.

    Args:
        src: Source H5 file.
        bounds: ((x_min, x_max), (y_min, y_max), (z_min, z_max)) in meters.

    Returns:
        Dict mapping mesh paths to (sx, sy, sz, NX, NY, NZ).
    """
    mesh_slices = {}
    if "Meshes" not in src:
        return mesh_slices

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

    return mesh_slices


def slice_h5_output(
    input_file: str,
    output_file: str,
    center_m: Tuple[float, float, float],
    side_length_m: float,
) -> None:
    """Creates a sliced copy of a Sim4Life _Output.h5 file.

    Args:
        input_file: Path to source H5 file.
        output_file: Path to destination H5 file.
        center_m: Center point in meters (x, y, z).
        side_length_m: Side length of the cube to extract in meters.
    """
    half_len = side_length_m / 2.0
    bounds = (
        (center_m[0] - half_len, center_m[0] + half_len),
        (center_m[1] - half_len, center_m[1] + half_len),
        (center_m[2] - half_len, center_m[2] + half_len),
    )

    with h5py.File(input_file, "r") as src, h5py.File(output_file, "w") as dst:
        mesh_slices = _build_mesh_slices(src, bounds)
        slicer = H5Slicer(src, dst, mesh_slices)
        src.visititems(slicer.visit_item)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Slice Sim4Life _Output.h5 file around a center point.")
    parser.add_argument("input", help="Source H5 file")
    parser.add_argument("output", help="Destination H5 file")
    parser.add_argument("--center", type=float, nargs=3, required=True, help="Center coordinates in meters (x y z)")
    parser.add_argument("--size", type=float, default=0.05, help="Cube side length in meters (default 0.05m)")

    args = parser.parse_args()
    slice_h5_output(args.input, args.output, tuple(args.center), args.size)
