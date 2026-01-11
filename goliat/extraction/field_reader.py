"""Utilities for reading E/H fields from Sim4Life _Output.h5 files.

Supports memory-efficient reading for auto-induced exposure calculations:
- Read fields at specific voxel indices (skin-only extraction)
- Read fields in z-slab chunks (for full-field combination)
- Handle Yee grid staggering (Nx-1, Ny-1, Nz-1 per component)
"""

import logging
from pathlib import Path
from typing import Tuple, Optional, Union

import h5py
import numpy as np


def find_overall_field_group(f: h5py.File) -> Optional[str]:
    """Find the FieldGroup containing 'Overall Field'.

    Args:
        f: Open h5py File object.

    Returns:
        Path to the FieldGroup (e.g., 'FieldGroups/0') or None if not found.
    """
    if "FieldGroups" not in f:
        return None

    for fg_key in f["FieldGroups"].keys():
        obj_path = f"FieldGroups/{fg_key}/_Object"
        if obj_path in f:
            name_attr = f[obj_path].attrs.get("name", b"")
            if isinstance(name_attr, bytes):
                name_attr = name_attr.decode("utf-8")
            if name_attr == "Overall Field":
                return f"FieldGroups/{fg_key}"

    return None


def get_field_path(fg_path: str, field_type: str = "E") -> str:
    """Get the HDF5 path for E or H field data.

    Args:
        fg_path: Path to the FieldGroup.
        field_type: 'E' for electric field, 'H' for magnetic field.

    Returns:
        Path to the field's Snapshots/0 group containing comp0/comp1/comp2.
    """
    field_name = f"EM {field_type}(x,y,z,f0)"
    return f"{fg_path}/AllFields/{field_name}/_Object/Snapshots/0"


def read_field_component(
    f: h5py.File,
    field_path: str,
    component: int,
    z_slice: Optional[slice] = None,
) -> np.ndarray:
    """Read a single field component as complex array.

    Args:
        f: Open h5py File object.
        field_path: Path to the Snapshots/0 group.
        component: 0, 1, or 2 for x, y, z component.
        z_slice: Optional slice for z-axis (for chunked reading).

    Returns:
        Complex64 array of shape (Nx, Ny, Nz) or (Nx, Ny, Nz_chunk).
        Note: Dimensions vary due to Yee staggering.
    """
    comp_name = f"comp{component}"
    dataset = f[f"{field_path}/{comp_name}"]

    if z_slice is not None:
        # Dataset shape is (Nx, Ny, Nz, 2) where last dim is [real, imag]
        data = dataset[:, :, z_slice, :]
    else:
        data = dataset[:]

    # Convert to complex
    return data[..., 0] + 1j * data[..., 1]


def read_field_at_indices(
    h5_path: Union[str, Path],
    indices: np.ndarray,
    field_type: str = "E",
) -> np.ndarray:
    """Read field values at specific voxel indices.

    Optimized for reading fields only at skin voxel locations.
    Uses vectorized numpy indexing for speed.

    Args:
        h5_path: Path to _Output.h5 file.
        indices: Array of shape (N, 3) with [ix, iy, iz] indices.
        field_type: 'E' or 'H'.

    Returns:
        Complex64 array of shape (N, 3) with [Ex, Ey, Ez] or [Hx, Hy, Hz].

    Note:
        Due to Yee staggering, we use the voxel center approximation.
        For component i, data shape is (N-1) in dimension i.
        We clamp indices to valid range.
    """
    result = np.zeros((len(indices), 3), dtype=np.complex64)

    with h5py.File(h5_path, "r") as f:
        fg_path = find_overall_field_group(f)
        if fg_path is None:
            raise ValueError(f"No 'Overall Field' found in {h5_path}")

        field_path = get_field_path(fg_path, field_type)

        for comp in range(3):
            dataset = f[f"{field_path}/comp{comp}"]
            shape = dataset.shape[:3]  # (Nx, Ny, Nz) for this component

            # Clamp indices to valid range for this component
            # Component 0 (Ex): shape is (Nx-1, Ny, Nz)
            # Component 1 (Ey): shape is (Nx, Ny-1, Nz)
            # Component 2 (Ez): shape is (Nx, Ny, Nz-1)
            ix = np.minimum(indices[:, 0], shape[0] - 1)
            iy = np.minimum(indices[:, 1], shape[1] - 1)
            iz = np.minimum(indices[:, 2], shape[2] - 1)

            # Read full component into memory (faster than many small reads)
            full_data = dataset[:]  # Shape: (Nx, Ny, Nz, 2)

            # Vectorized extraction using fancy indexing
            data = full_data[ix, iy, iz, :]  # Shape: (N, 2)
            result[:, comp] = data[:, 0] + 1j * data[:, 1]

    return result


def read_field_chunk(
    h5_path: Union[str, Path],
    z_start: int,
    z_end: int,
    field_type: str = "E",
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Read a z-slab chunk of the field.

    For memory-efficient full-field combination.

    Args:
        h5_path: Path to _Output.h5 file.
        z_start: Start z-index (inclusive).
        z_end: End z-index (exclusive).
        field_type: 'E' or 'H'.

    Returns:
        Tuple of (comp0, comp1, comp2) complex64 arrays.
        Shapes vary due to Yee staggering:
        - comp0: (Nx-1, Ny, z_end-z_start)
        - comp1: (Nx, Ny-1, z_end-z_start)
        - comp2: (Nx, Ny, z_end-z_start-1) - one less in z!
    """
    with h5py.File(h5_path, "r") as f:
        fg_path = find_overall_field_group(f)
        if fg_path is None:
            raise ValueError(f"No 'Overall Field' found in {h5_path}")

        field_path = get_field_path(fg_path, field_type)
        z_slice = slice(z_start, z_end)

        components = []
        for comp in range(3):
            # For comp2 (Ez), the z-dimension is Nz-1, so adjust slice
            if comp == 2:
                # Clamp to valid range
                dataset = f[f"{field_path}/comp{comp}"]
                max_z = dataset.shape[2]
                z_slice_adj = slice(z_start, min(z_end, max_z))
                data = read_field_component(f, field_path, comp, z_slice_adj)
            else:
                data = read_field_component(f, field_path, comp, z_slice)
            components.append(data)

    return tuple(components)


def read_full_field(
    h5_path: Union[str, Path],
    field_type: str = "E",
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Read the entire E or H field.

    Warning: Can be very memory intensive (~2GB for typical phantom).

    Args:
        h5_path: Path to _Output.h5 file.
        field_type: 'E' or 'H'.

    Returns:
        Tuple of (comp0, comp1, comp2) complex64 arrays.
    """
    with h5py.File(h5_path, "r") as f:
        fg_path = find_overall_field_group(f)
        if fg_path is None:
            raise ValueError(f"No 'Overall Field' found in {h5_path}")

        field_path = get_field_path(fg_path, field_type)

        components = []
        for comp in range(3):
            data = read_field_component(f, field_path, comp)
            components.append(data)

    return tuple(components)


def get_field_shape(h5_path: Union[str, Path]) -> Tuple[int, int, int]:
    """Get the grid shape from an _Output.h5 file.

    Returns the node count (Nx, Ny, Nz), not voxel count.
    Field components have shapes (Nx-1, Ny, Nz), etc. due to Yee grid.

    Args:
        h5_path: Path to _Output.h5 file.

    Returns:
        Tuple (Nx, Ny, Nz) - node counts.
    """
    with h5py.File(h5_path, "r") as f:
        fg_path = find_overall_field_group(f)
        if fg_path is None:
            raise ValueError(f"No 'Overall Field' found in {h5_path}")

        field_path = get_field_path(fg_path, "E")
        # comp0 has shape (Nx-1, Ny, Nz, 2), so Nx = shape[0] + 1
        shape = f[f"{field_path}/comp0"].shape
        return (shape[0] + 1, shape[1], shape[2])


# --- CLI for testing ---
if __name__ == "__main__":
    import argparse

    # Set up basic logging for CLI usage
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
    )
    logger = logging.getLogger("verbose")

    parser = argparse.ArgumentParser(description="Read fields from Sim4Life _Output.h5")
    parser.add_argument("output_h5", help="Path to _Output.h5 file")
    parser.add_argument("--field", choices=["E", "H"], default="E", help="Field type")
    parser.add_argument("--chunk-test", action="store_true", help="Test chunked reading")

    args = parser.parse_args()

    logger.info(f"\nReading from: {args.output_h5}")

    # Get shape
    shape = get_field_shape(args.output_h5)
    logger.info(f"Grid shape (nodes): {shape}")

    if args.chunk_test:
        # Test chunked reading
        chunk_size = 50
        logger.info(f"\nTesting chunked read (z=0:{chunk_size})...")
        comps = read_field_chunk(args.output_h5, 0, chunk_size, args.field)
        for i, c in enumerate(comps):
            logger.info(f"  comp{i}: shape={c.shape}, dtype={c.dtype}")
            logger.info(f"          max|{args.field}|={np.abs(c).max():.4e}")
    else:
        # Test single-point reading
        test_indices = np.array([[10, 10, 10], [20, 20, 20], [50, 50, 100]])
        logger.info(f"\nReading {args.field}-field at {len(test_indices)} test points...")
        field_vals = read_field_at_indices(args.output_h5, test_indices, args.field)
        for i, (idx, val) in enumerate(zip(test_indices, field_vals)):
            mag = np.linalg.norm(val)
            logger.info(f"  [{idx[0]:3d},{idx[1]:3d},{idx[2]:3d}]: |{args.field}|={mag:.4e}")
