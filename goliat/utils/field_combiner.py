"""Field combiner for auto-induced exposure.

Combines weighted E/H fields from multiple directions into a single combined field,
then writes the result to an _Output.h5 file that Sim4Life can load for SAPD extraction.

Memory-efficient: uses z-slab chunked processing to avoid loading full 3D arrays.
"""

import shutil
from pathlib import Path
from typing import Sequence, Union, Optional

import h5py
import numpy as np
from tqdm import tqdm

from .field_reader import find_overall_field_group, get_field_path, get_field_shape


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

    # Get grid shape from first file and validate all match
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

    # Process in z-slab chunks
    n_chunks = (Nz + chunk_size - 1) // chunk_size
    for z_start in tqdm(range(0, Nz, chunk_size), total=n_chunks, desc=f"{field_type}-field", leave=False):
        z_end = min(z_start + chunk_size, Nz)

        # Combine each component separately
        for comp_idx in range(3):
            comp_key = f"comp{comp_idx}"
            ds_path = f"{field_path}/{comp_key}"

            # Get dataset for shape info
            ds = out_file[ds_path]
            # Shape is (Nx', Ny', Nz', 2) where Nx'/Ny'/Nz' may be N-1 due to Yee grid
            comp_Nz = ds.shape[2]

            # Adjust z-slice for this component (may be shorter due to Yee grid)
            z_start_comp = min(z_start, comp_Nz)
            z_end_comp = min(z_end, comp_Nz)

            if z_start_comp >= z_end_comp:
                continue

            # Accumulate weighted sum for this chunk
            combined_chunk = None

            for h5_path, weight in zip(h5_paths, weights):
                with h5py.File(h5_path, "r") as src_f:
                    src_fg_path = find_overall_field_group(src_f)
                    if src_fg_path is None:
                        raise ValueError(f"No 'Overall Field' in {h5_path}")

                    src_field_path = get_field_path(src_fg_path, field_type)
                    src_ds = src_f[f"{src_field_path}/{comp_key}"]

                    # Read chunk: shape (Nx', Ny', chunk_z, 2)
                    chunk_data = src_ds[:, :, z_start_comp:z_end_comp, :]

                    # Convert to complex
                    chunk_complex = chunk_data[..., 0] + 1j * chunk_data[..., 1]

                    # Weighted accumulation
                    if combined_chunk is None:
                        combined_chunk = weight * chunk_complex
                    else:
                        combined_chunk += weight * chunk_complex

            # Write back to output
            if combined_chunk is not None:
                ds[:, :, z_start_comp:z_end_comp, 0] = np.real(combined_chunk)
                ds[:, :, z_start_comp:z_end_comp, 1] = np.imag(combined_chunk)


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


# --- CLI for testing ---
if __name__ == "__main__":
    import argparse
    import glob
    import time

    from .focus_optimizer import find_focus_and_compute_weights

    parser = argparse.ArgumentParser(description="Combine weighted E/H fields for auto-induced exposure")
    parser.add_argument("results_dir", help="Directory containing _Output.h5 files")
    parser.add_argument("--input-h5", required=True, help="Path to _Input.h5 for skin mask")
    parser.add_argument("--output", required=True, help="Output H5 file path")
    parser.add_argument("--pattern", default="*_Output.h5", help="Glob pattern for output files")
    parser.add_argument("--chunk-size", type=int, default=50, help="Z-slab chunk size")

    args = parser.parse_args()

    # Find all output H5 files
    h5_patterns = glob.glob(f"{args.results_dir}/**/{args.pattern}", recursive=True)
    h5_paths = sorted(h5_patterns)

    if not h5_paths:
        print(f"No files matching {args.pattern} found in {args.results_dir}")
        exit(1)

    print(f"\nFound {len(h5_paths)} _Output.h5 files:")
    for p in h5_paths:
        print(f"  - {p}")
    print(f"Input H5: {args.input_h5}")
    print(f"Output: {args.output}")

    total_start = time.perf_counter()

    # Step 1: Find focus point and compute weights
    print("\nStep 1: Finding worst-case focus point...")
    t1 = time.perf_counter()
    focus_idx, weights, info = find_focus_and_compute_weights(h5_paths, args.input_h5)
    t1_elapsed = time.perf_counter() - t1
    print(f"  Focus voxel: [{focus_idx[0]}, {focus_idx[1]}, {focus_idx[2]}]")
    print(f"  Max Σ|E_i|: {info['max_magnitude_sum']:.4e}")
    print(f"  ⏱ {t1_elapsed:.2f}s")

    # Step 2: Combine fields
    print("\nStep 2: Combining weighted fields...")
    t2 = time.perf_counter()
    result = combine_and_write(
        h5_paths=h5_paths,
        weights=weights,
        output_h5_path=args.output,
        chunk_size=args.chunk_size,
    )
    t2_elapsed = time.perf_counter() - t2
    print(f"  ⏱ {t2_elapsed:.2f}s")

    total_elapsed = time.perf_counter() - total_start

    print("\n" + "=" * 50)
    print("Combination complete!")
    print("=" * 50)
    print(f"  Grid shape: {result['grid_shape']}")
    print(f"  Directions: {result['n_directions']}")
    print(f"  Output: {result['output_path']}")
    print(f"  Total time: {total_elapsed:.2f}s")
