"""Sliced field combiner for auto-induced exposure.

Combines weighted E/H fields in a small cube around the focus point.
Much faster and produces smaller output than the full-volume combiner.
"""

from pathlib import Path
from typing import Optional, Sequence, Tuple, Union

import h5py
import numpy as np
from tqdm import tqdm

from .field_reader import find_overall_field_group, get_field_path


def _get_mesh_axes(h5_file: h5py.File) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Extract mesh axes from an H5 file.

    Args:
        h5_file: Open H5 file handle.

    Returns:
        Tuple of (axis_x, axis_y, axis_z) arrays.

    Raises:
        ValueError: If no mesh with axes is found.
    """
    for mesh_key in h5_file["Meshes"].keys():
        mesh = h5_file[f"Meshes/{mesh_key}"]
        if "axis_x" in mesh:
            return mesh["axis_x"][:], mesh["axis_y"][:], mesh["axis_z"][:]
    raise ValueError("No mesh with axes found in file")


def combine_fields_sliced(
    h5_paths: Sequence[Union[str, Path]],
    weights: np.ndarray,
    template_h5_path: Union[str, Path],
    output_h5_path: Union[str, Path],
    center_idx: Sequence[int],
    side_length_mm: float = 100.0,
    field_types: Sequence[str] = ("E", "H"),
    progress_bar: Optional[tqdm] = None,
) -> dict:
    """Combine weighted fields in a small cube around the focus point.

    MUCH faster than full-field combination - only processes a small region.
    The output H5 is also much smaller (MBs instead of GBs).

    Uses slice_h5_output to create a properly structured sliced H5 first,
    then modifies the field data with the weighted combination.

    Args:
        h5_paths: List of _Output.h5 file paths (one per direction).
        weights: Complex weights for each direction, shape (N,).
        template_h5_path: Path to an existing _Output.h5 to use as template.
        output_h5_path: Path for the combined output H5 file.
        center_idx: [ix, iy, iz] voxel indices of the focus point.
        side_length_mm: Side length of the cube to extract (default 100mm for SAPD).
        field_types: Which fields to combine ('E', 'H', or both).
        progress_bar: Optional tqdm progress bar to update (will be updated per component).

    Returns:
        Dict with info about the combination.
    """
    from ..utils.h5_slicer import get_slice_indices, slice_h5_output

    h5_paths = [Path(p) for p in h5_paths]
    template_h5_path = Path(template_h5_path)
    output_h5_path = Path(output_h5_path)

    if len(h5_paths) != len(weights):
        raise ValueError(f"Paths ({len(h5_paths)}) != weights ({len(weights)})")

    with h5py.File(template_h5_path, "r") as f:
        axis_x, axis_y, axis_z = _get_mesh_axes(f)

    ix, iy, iz = center_idx
    center_m = (
        float(axis_x[min(ix, len(axis_x) - 1)]),
        float(axis_y[min(iy, len(axis_y) - 1)]),
        float(axis_z[min(iz, len(axis_z) - 1)]),
    )

    output_h5_path.parent.mkdir(parents=True, exist_ok=True)
    slice_h5_output(str(template_h5_path), str(output_h5_path), center_m, side_length_mm / 1000.0)

    half_len = (side_length_mm / 1000.0) / 2.0
    bounds = (
        (center_m[0] - half_len, center_m[0] + half_len),
        (center_m[1] - half_len, center_m[1] + half_len),
        (center_m[2] - half_len, center_m[2] + half_len),
    )

    with h5py.File(output_h5_path, "r+") as out_f:
        fg_path = find_overall_field_group(out_f)
        if fg_path is None:
            raise ValueError("No 'Overall Field' in output")

        for field_type in field_types:
            _combine_sliced_field(h5_paths, weights, out_f, fg_path, field_type, bounds, get_slice_indices, progress_bar)

    with h5py.File(output_h5_path, "r") as f:
        try:
            axis_x, axis_y, axis_z = _get_mesh_axes(f)
            sliced_shape = (len(axis_x), len(axis_y), len(axis_z))
        except ValueError:
            sliced_shape = (0, 0, 0)

    return {
        "center_m": center_m,
        "side_length_mm": side_length_mm,
        "sliced_shape": sliced_shape,
        "n_directions": len(h5_paths),
        "output_path": str(output_h5_path),
        "field_types": list(field_types),
    }


def _combine_sliced_field(
    h5_paths: Sequence[Path],
    weights: np.ndarray,
    out_f: h5py.File,
    fg_path: str,
    field_type: str,
    bounds: Tuple[Tuple[float, float], ...],
    get_slice_indices,
    progress_bar: Optional[tqdm] = None,
) -> None:
    """Combine a sliced field across all components."""
    field_path = get_field_path(fg_path, field_type)
    if field_path not in out_f:
        return

    comp_names = ["x", "y", "z"]
    for comp_idx in range(3):
        comp_key = f"comp{comp_idx}"
        comp_name = comp_names[comp_idx]
        out_ds = out_f[f"{field_path}/{comp_key}"]
        out_shape = out_ds.shape[:3]

        combined = _accumulate_sliced_component(h5_paths, weights, field_type, comp_key, bounds, out_shape, get_slice_indices)

        if combined is not None:
            combined = combined[: out_shape[0], : out_shape[1], : out_shape[2]]
            out_ds[..., 0] = np.real(combined)
            out_ds[..., 1] = np.imag(combined)

        if progress_bar is not None:
            progress_bar.set_postfix_str(f"{field_type}_{comp_name}")
            progress_bar.update(1)


def _accumulate_sliced_component(
    h5_paths: Sequence[Path],
    weights: np.ndarray,
    field_type: str,
    comp_key: str,
    bounds: Tuple[Tuple[float, float], ...],
    out_shape: Tuple[int, int, int],
    get_slice_indices,
) -> Optional[np.ndarray]:
    """Accumulate weighted sliced data for a single component."""
    combined: Optional[np.ndarray] = None

    for h5_path, weight in zip(h5_paths, weights):
        with h5py.File(h5_path, "r") as src_f:
            src_fg = find_overall_field_group(src_f)
            if src_fg is None:
                raise ValueError(f"No 'Overall Field' in {h5_path}")

            src_field_path = get_field_path(src_fg, field_type)
            src_ds = src_f[f"{src_field_path}/{comp_key}"]

            src_ax_x, src_ax_y, src_ax_z = _get_mesh_axes(src_f)
            sx = get_slice_indices(src_ax_x, bounds[0][0], bounds[0][1])
            sy = get_slice_indices(src_ax_y, bounds[1][0], bounds[1][1])
            sz = get_slice_indices(src_ax_z, bounds[2][0], bounds[2][1])

            sx = slice(sx.start, min(sx.stop, src_ds.shape[0], sx.start + out_shape[0]))
            sy = slice(sy.start, min(sy.stop, src_ds.shape[1], sy.start + out_shape[1]))
            sz = slice(sz.start, min(sz.stop, src_ds.shape[2], sz.start + out_shape[2]))

            data = src_ds[sx, sy, sz, :]
            chunk_complex = data[..., 0] + 1j * data[..., 1]

            if combined is None:
                combined = weight * chunk_complex
            else:
                combined += weight * chunk_complex

    return combined
