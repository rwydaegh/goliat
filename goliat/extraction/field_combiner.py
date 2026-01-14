"""Field combiner for auto-induced exposure.

Combines weighted E/H fields from multiple directions into a single combined field,
then writes the result to an _Output.h5 file that Sim4Life can load for SAPD extraction.

Memory-efficient: uses z-slab chunked processing to avoid loading full 3D arrays.
"""

import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence, Union, Optional, Tuple

import h5py
import numpy as np
from tqdm import tqdm

from .field_reader import find_overall_field_group, get_field_path, get_field_shape


@dataclass
class FieldCombineConfig:
    """Configuration for field combination operations."""

    h5_paths: Sequence[Path]
    weights: np.ndarray
    template_h5_path: Path
    output_h5_path: Path
    field_types: Sequence[str] = ("E", "H")


def _get_mesh_axes(h5_file: h5py.File) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Extracts mesh axes from an H5 file.

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


def _validate_grid_shapes(h5_paths: Sequence[Path]) -> Tuple[int, int, int]:
    """Validates all H5 files have matching grid shapes.

    Args:
        h5_paths: List of H5 file paths.

    Returns:
        Grid shape (Nx, Ny, Nz).

    Raises:
        ValueError: If grid shapes don't match.
    """
    Nx, Ny, Nz = get_field_shape(h5_paths[0])
    for i, h5_path in enumerate(h5_paths[1:], start=1):
        shape_i = get_field_shape(h5_path)
        if shape_i != (Nx, Ny, Nz):
            raise ValueError(
                f"Grid shape mismatch: {h5_paths[0].name} has {(Nx, Ny, Nz)}, "
                f"but {h5_path.name} has {shape_i}. "
                f"All H5 files must have identical grids. "
                f"Hint: Disable 'use_symmetry_reduction' for auto-induced exposure."
            )
    return Nx, Ny, Nz


def combine_fields_chunked(
    h5_paths: Sequence[Union[str, Path]],
    weights: np.ndarray,
    template_h5_path: Union[str, Path],
    output_h5_path: Union[str, Path],
    chunk_size: int = 50,
    field_types: Sequence[str] = ("E", "H"),
) -> dict:
    """Combine weighted fields from multiple H5 files and write to output.

    Uses z-slab chunking for memory efficiency. For a typical phantom with
    Nz=1900, chunk_size=50 gives ~38 chunks, each loading ~56MB per direction.

    Args:
        h5_paths: List of _Output.h5 file paths (one per direction).
        weights: Complex weights for each direction, shape (N,).
        template_h5_path: Path to an existing _Output.h5 to use as template.
        output_h5_path: Path for the combined output H5 file.
        chunk_size: Number of z-slabs to process at once.
        field_types: Which fields to combine ('E', 'H', or both).

    Returns:
        Dict with info about the combination (grid shape, num directions, etc.).
    """
    h5_paths = [Path(p) for p in h5_paths]
    template_h5_path = Path(template_h5_path)
    output_h5_path = Path(output_h5_path)

    if len(h5_paths) != len(weights):
        raise ValueError(f"Number of paths ({len(h5_paths)}) != number of weights ({len(weights)})")

    Nx, Ny, Nz = _validate_grid_shapes(h5_paths)

    # Copy template to output
    output_h5_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(template_h5_path, output_h5_path)

    # Open output for in-place modification
    with h5py.File(output_h5_path, "r+") as out_f:
        fg_path = find_overall_field_group(out_f)
        if fg_path is None:
            raise ValueError("No 'Overall Field' FieldGroup found in template")

        for field_type in field_types:
            _combine_single_field_chunked(
                h5_paths=h5_paths,
                weights=weights,
                out_file=out_f,
                fg_path=fg_path,
                field_type=field_type,
                Nz=Nz,
                chunk_size=chunk_size,
            )

    return {
        "grid_shape": (Nx, Ny, Nz),
        "n_directions": len(h5_paths),
        "output_path": str(output_h5_path),
        "chunk_size": chunk_size,
        "field_types": list(field_types),
    }


def _combine_single_field_chunked(
    h5_paths: Sequence[Path],
    weights: np.ndarray,
    out_file: h5py.File,
    fg_path: str,
    field_type: str,
    Nz: int,
    chunk_size: int,
) -> None:
    """Combine a single field type (E or H) using chunked processing."""
    field_path = get_field_path(fg_path, field_type)

    n_chunks = (Nz + chunk_size - 1) // chunk_size
    for z_start in tqdm(range(0, Nz, chunk_size), total=n_chunks, desc=f"{field_type}-field", leave=False):
        z_end = min(z_start + chunk_size, Nz)

        for comp_idx in range(3):
            _combine_component_chunk(h5_paths, weights, out_file, field_path, field_type, comp_idx, z_start, z_end)


def _combine_component_chunk(
    h5_paths: Sequence[Path],
    weights: np.ndarray,
    out_file: h5py.File,
    field_path: str,
    field_type: str,
    comp_idx: int,
    z_start: int,
    z_end: int,
) -> None:
    """Combines a single component chunk across all directions."""
    comp_key = f"comp{comp_idx}"
    ds_path = f"{field_path}/{comp_key}"

    ds = out_file[ds_path]
    comp_Nz = ds.shape[2]

    # Adjust z-slice for Yee grid offsets
    z_start_comp = min(z_start, comp_Nz)
    z_end_comp = min(z_end, comp_Nz)

    if z_start_comp >= z_end_comp:
        return

    combined_chunk = _accumulate_weighted_chunk(h5_paths, weights, field_type, comp_key, z_start_comp, z_end_comp)

    if combined_chunk is not None:
        ds[:, :, z_start_comp:z_end_comp, 0] = np.real(combined_chunk)
        ds[:, :, z_start_comp:z_end_comp, 1] = np.imag(combined_chunk)


def _accumulate_weighted_chunk(
    h5_paths: Sequence[Path],
    weights: np.ndarray,
    field_type: str,
    comp_key: str,
    z_start: int,
    z_end: int,
) -> Optional[np.ndarray]:
    """Accumulates weighted field data from all sources for a z-chunk."""
    combined_chunk = None

    for h5_path, weight in zip(h5_paths, weights):
        with h5py.File(h5_path, "r") as src_f:
            src_fg_path = find_overall_field_group(src_f)
            if src_fg_path is None:
                raise ValueError(f"No 'Overall Field' in {h5_path}")

            src_field_path = get_field_path(src_fg_path, field_type)
            src_ds = src_f[f"{src_field_path}/{comp_key}"]

            chunk_data = src_ds[:, :, z_start:z_end, :]
            chunk_complex = chunk_data[..., 0] + 1j * chunk_data[..., 1]

            if combined_chunk is None:
                combined_chunk = weight * chunk_complex
            else:
                combined_chunk += weight * chunk_complex

    return combined_chunk


def combine_and_write(
    h5_paths: Sequence[Union[str, Path]],
    weights: np.ndarray,
    output_h5_path: Union[str, Path],
    template_h5_path: Optional[Union[str, Path]] = None,
    chunk_size: int = 50,
) -> dict:
    """Convenience function: combine fields and write to H5.

    If template_h5_path is not specified, uses the first h5_path as template.

    Args:
        h5_paths: List of _Output.h5 file paths.
        weights: Complex weights for each direction.
        output_h5_path: Where to write the combined output.
        template_h5_path: Optional template H5. Defaults to first in h5_paths.
        chunk_size: Z-slab chunk size for memory efficiency.

    Returns:
        Dict with combination info.
    """
    if template_h5_path is None:
        template_h5_path = h5_paths[0]

    return combine_fields_chunked(
        h5_paths=h5_paths,
        weights=weights,
        template_h5_path=template_h5_path,
        output_h5_path=output_h5_path,
        chunk_size=chunk_size,
        field_types=("E", "H"),
    )


def combine_fields_sliced(
    h5_paths: Sequence[Union[str, Path]],
    weights: np.ndarray,
    template_h5_path: Union[str, Path],
    output_h5_path: Union[str, Path],
    center_idx: Sequence[int],
    side_length_mm: float = 100.0,
    field_types: Sequence[str] = ("E", "H"),
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

    Returns:
        Dict with info about the combination.
    """
    from ..utils.h5_slicer import slice_h5_output, get_slice_indices

    h5_paths = [Path(p) for p in h5_paths]
    template_h5_path = Path(template_h5_path)
    output_h5_path = Path(output_h5_path)

    if len(h5_paths) != len(weights):
        raise ValueError(f"Paths ({len(h5_paths)}) != weights ({len(weights)})")

    # Get center in physical coordinates
    with h5py.File(template_h5_path, "r") as f:
        axis_x, axis_y, axis_z = _get_mesh_axes(f)

    ix, iy, iz = center_idx
    center_m = (
        float(axis_x[min(ix, len(axis_x) - 1)]),
        float(axis_y[min(iy, len(axis_y) - 1)]),
        float(axis_z[min(iz, len(axis_z) - 1)]),
    )

    # Create sliced output H5
    output_h5_path.parent.mkdir(parents=True, exist_ok=True)
    slice_h5_output(str(template_h5_path), str(output_h5_path), center_m, side_length_mm / 1000.0)

    # Calculate bounds for source slicing
    half_len = (side_length_mm / 1000.0) / 2.0
    bounds = (
        (center_m[0] - half_len, center_m[0] + half_len),
        (center_m[1] - half_len, center_m[1] + half_len),
        (center_m[2] - half_len, center_m[2] + half_len),
    )

    # Replace field data with combined fields
    with h5py.File(output_h5_path, "r+") as out_f:
        fg_path = find_overall_field_group(out_f)
        if fg_path is None:
            raise ValueError("No 'Overall Field' in output")

        for field_type in field_types:
            _combine_sliced_field(h5_paths, weights, out_f, fg_path, field_type, bounds, get_slice_indices)

    # Get final shape
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
) -> None:
    """Combines a sliced field across all components."""
    field_path = get_field_path(fg_path, field_type)
    if field_path not in out_f:
        return

    for comp_idx in range(3):
        comp_key = f"comp{comp_idx}"
        out_ds = out_f[f"{field_path}/{comp_key}"]
        out_shape = out_ds.shape[:3]

        combined = _accumulate_sliced_component(h5_paths, weights, field_type, comp_key, bounds, out_shape, get_slice_indices)

        if combined is not None:
            combined = combined[: out_shape[0], : out_shape[1], : out_shape[2]]
            out_ds[..., 0] = np.real(combined)
            out_ds[..., 1] = np.imag(combined)


def _accumulate_sliced_component(
    h5_paths: Sequence[Path],
    weights: np.ndarray,
    field_type: str,
    comp_key: str,
    bounds: Tuple[Tuple[float, float], ...],
    out_shape: Tuple[int, int, int],
    get_slice_indices,
) -> Optional[np.ndarray]:
    """Accumulates weighted sliced data for a single component."""
    combined: Optional[np.ndarray] = None

    for h5_path, weight in zip(h5_paths, weights):
        with h5py.File(h5_path, "r") as src_f:
            src_fg = find_overall_field_group(src_f)
            if src_fg is None:
                raise ValueError(f"No 'Overall Field' in {h5_path}")

            src_field_path = get_field_path(src_fg, field_type)
            src_ds = src_f[f"{src_field_path}/{comp_key}"]

            # Get source axes and compute slices
            src_ax_x, src_ax_y, src_ax_z = _get_mesh_axes(src_f)
            sx = get_slice_indices(src_ax_x, bounds[0][0], bounds[0][1])
            sy = get_slice_indices(src_ax_y, bounds[1][0], bounds[1][1])
            sz = get_slice_indices(src_ax_z, bounds[2][0], bounds[2][1])

            # Clamp to data and output shape
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


# --- CLI for testing ---
if __name__ == "__main__":
    import argparse
    import glob
    import time

    from .focus_optimizer import find_focus_and_compute_weights, compute_optimal_phases, compute_weights

    # Set up basic logging for CLI usage
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
    )
    logger = logging.getLogger("verbose")

    parser = argparse.ArgumentParser(description="Combine weighted E/H fields for auto-induced exposure")
    parser.add_argument("results_dir", help="Directory containing _Output.h5 files")
    parser.add_argument("--input-h5", required=True, help="Path to _Input.h5 for skin mask")
    parser.add_argument("--output", required=True, help="Output H5 file path (or base path for --top-n)")
    parser.add_argument("--pattern", default="*_Output.h5", help="Glob pattern for output files")
    parser.add_argument("--cube-size", type=float, default=100.0, help="Cube side length in mm (default 100)")
    parser.add_argument("--full", action="store_true", help="Combine full field (slow, large output)")
    parser.add_argument("--chunk-size", type=int, default=50, help="Z-slab chunk size (only for --full)")
    parser.add_argument("--top-n", type=int, default=1, help="Generate N candidate focus points (default 1)")

    args = parser.parse_args()

    # Find all output H5 files
    h5_patterns = glob.glob(f"{args.results_dir}/**/{args.pattern}", recursive=True)
    h5_paths = sorted(h5_patterns)

    if not h5_paths:
        logger.error(f"No files matching {args.pattern} found in {args.results_dir}")
        exit(1)

    logger.info(f"\nFound {len(h5_paths)} _Output.h5 files:")
    for p in h5_paths:
        logger.info(f"  - {p}")
    logger.info(f"Input H5: {args.input_h5}")
    logger.info(f"Output: {args.output}")
    logger.info(f"Mode: {'FULL (slow)' if args.full else f'SLICED ({args.cube_size}mm cube)'}")
    logger.info(f"Top N candidates: {args.top_n}")

    total_start = time.perf_counter()

    # Step 1: Find focus point(s) and compute weights
    logger.info(f"\nStep 1: Finding top-{args.top_n} worst-case focus points...")
    t1 = time.perf_counter()
    focus_indices, weights, info = find_focus_and_compute_weights(h5_paths, args.input_h5, top_n=args.top_n)
    t1_elapsed = time.perf_counter() - t1

    # Handle both single and multiple focus points
    if args.top_n == 1:
        focus_indices = np.array([focus_indices])  # Make it 2D for uniform handling

    for i, (focus_idx, mag_sum) in enumerate(zip(focus_indices, info["all_metric_sums"])):
        logger.info(f"  #{i + 1}: voxel [{focus_idx[0]}, {focus_idx[1]}, {focus_idx[2]}], Σ|E|={mag_sum:.4e}")
    logger.info(f"  Time: {t1_elapsed:.2f}s")

    # Step 2: Combine fields for each candidate
    logger.info(f"\nStep 2: Combining weighted fields for {args.top_n} candidate(s)...")
    t2 = time.perf_counter()

    for i, focus_idx in enumerate(focus_indices):
        # Compute phases specific to this focus point
        phases = compute_optimal_phases(h5_paths, focus_idx)
        candidate_weights = compute_weights(phases)

        # Generate output path
        if args.top_n == 1:
            output_path = args.output
        else:
            base, ext = args.output.rsplit(".", 1) if "." in args.output else (args.output, "h5")
            output_path = f"{base}_candidate{i + 1}.{ext}"

        logger.info(f"  Candidate #{i + 1}: {output_path}")

        if args.full:
            result = combine_and_write(
                h5_paths=h5_paths,
                weights=candidate_weights,
                output_h5_path=output_path,
                chunk_size=args.chunk_size,
            )
            shape_info = f"Grid shape: {result['grid_shape']}"
        else:
            result = combine_fields_sliced(
                h5_paths=h5_paths,
                weights=candidate_weights,
                template_h5_path=h5_paths[0],
                output_h5_path=output_path,
                center_idx=focus_idx,
                side_length_mm=args.cube_size,
            )
            shape_info = f"Sliced shape: {result['sliced_shape']}"

    t2_elapsed = time.perf_counter() - t2
    logger.info(f"  Time: {t2_elapsed:.2f}s")

    total_elapsed = time.perf_counter() - total_start

    logger.info("\n" + "=" * 50)
    logger.info("Combination complete!")
    logger.info("=" * 50)
    logger.info(f"  Candidates: {args.top_n}")
    logger.info(f"  Directions: {len(h5_paths)}")
    logger.info(f"  Total time: {total_elapsed:.2f}s")
