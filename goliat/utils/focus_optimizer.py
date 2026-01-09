"""Focus optimizer for auto-induced exposure worst-case search.

Finds the worst-case focus point on skin where MRT-weighted fields
produce maximum constructive interference, then computes optimal phases.

Key insight: With phase-only weighting, the worst-case location is simply
argmax_r Σ|E_i(r)| - no optimization needed during search.
"""

import numpy as np
from pathlib import Path
from typing import Sequence, Tuple, Union, Optional

from tqdm import tqdm

from .field_reader import read_field_at_indices
from .skin_voxel_utils import extract_skin_voxels, get_skin_voxel_coordinates


def compute_metric_sum_at_skin(
    h5_paths: Sequence[Union[str, Path]],
    skin_indices: np.ndarray,
    metric: str = "E_z_magnitude",
) -> np.ndarray:
    """Compute sum of field metric at skin voxels across all directions.

    This is the core of the efficient worst-case search. Since optimal phases
    always align phasors, the worst-case location is where Σ(metric) is maximum.

    Args:
        h5_paths: List of _Output.h5 file paths (one per direction).
        skin_indices: Array of shape (N_skin, 3) with [ix, iy, iz] indices.
        metric: Search metric to use:
            - "E_z_magnitude": |E_z| - vertical E-field component (MRT-consistent)
            - "poynting_z": |Re(E × H*)_z| - z-component of Poynting vector (SAPD-consistent)

    Returns:
        Array of shape (N_skin,) with metric sum at each skin voxel.
    """
    metric_sum = np.zeros(len(skin_indices), dtype=np.float64)

    for h5_path in tqdm(h5_paths, desc="Reading fields", leave=False):
        if metric == "E_z_magnitude":
            # Read only E-field, use z-component magnitude
            E_skin = read_field_at_indices(h5_path, skin_indices, field_type="E")
            # E_skin shape: (N_skin, 3) complex - [Ex, Ey, Ez]
            metric_values = np.abs(E_skin[:, 2])  # |E_z| only

        elif metric == "poynting_z":
            # Read both E and H, compute Poynting z-component
            E_skin = read_field_at_indices(h5_path, skin_indices, field_type="E")
            H_skin = read_field_at_indices(h5_path, skin_indices, field_type="H")
            # S = Re(E × H*), S_z = Re(Ex * Hy* - Ey * Hx*)
            S_z = np.real(E_skin[:, 0] * np.conj(H_skin[:, 1]) - E_skin[:, 1] * np.conj(H_skin[:, 0]))
            metric_values = np.abs(S_z)

        else:
            raise ValueError(f"Unknown metric: {metric}. Use 'E_z_magnitude' or 'poynting_z'")

        metric_sum += metric_values

    return metric_sum


def find_worst_case_focus_point(
    h5_paths: Sequence[Union[str, Path]],
    input_h5_path: Union[str, Path],
    skin_keywords: Optional[Sequence[str]] = None,
    top_n: int = 1,
    metric: str = "E_z_magnitude",
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Find the worst-case focus point(s) on skin.

    Args:
        h5_paths: List of _Output.h5 file paths (one per direction/polarization).
        input_h5_path: Path to _Input.h5 for skin mask extraction.
        skin_keywords: Keywords to match skin tissues (default: ["skin"]).
        top_n: Number of top candidate focus points to return.
        metric: Search metric - "E_z_magnitude" (default) or "poynting_z".

    Returns:
        Tuple of:
            - worst_voxel_indices: Array of shape (top_n, 3) with [ix, iy, iz] indices
            - skin_indices_arr: Array of shape (top_n,) with indices within skin voxels
            - metric_sums: Array of shape (top_n,) with sum of metric values
    """
    # Extract skin mask and indices
    skin_mask, axis_x, axis_y, axis_z, _ = extract_skin_voxels(str(input_h5_path), skin_keywords)
    skin_indices = np.argwhere(skin_mask)  # Shape: (N_skin, 3)

    if len(skin_indices) == 0:
        raise ValueError("No skin voxels found in input H5")

    # Compute metric sum at all skin voxels
    metric_sum = compute_metric_sum_at_skin(h5_paths, skin_indices, metric=metric)

    # Find top N maxima (use argpartition for efficiency)
    top_n = min(top_n, len(metric_sum))
    top_skin_indices = np.argpartition(metric_sum, -top_n)[-top_n:]
    # Sort by metric descending
    top_skin_indices = top_skin_indices[np.argsort(metric_sum[top_skin_indices])[::-1]]

    worst_voxel_indices = skin_indices[top_skin_indices]  # Shape: (top_n, 3)
    top_metric_sums = metric_sum[top_skin_indices]  # Shape: (top_n,)

    return worst_voxel_indices, top_skin_indices, top_metric_sums


def compute_optimal_phases(
    h5_paths: Sequence[Union[str, Path]],
    focus_voxel_idx: np.ndarray,
) -> np.ndarray:
    """Compute optimal phases for focusing at a specific voxel.

    For maximum constructive interference at the focus point:
        φ_i* = -arg(E_i(r))

    This aligns all complex phasors to add constructively.

    Args:
        h5_paths: List of _Output.h5 file paths (one per direction).
        focus_voxel_idx: Array [ix, iy, iz] of focus voxel indices.

    Returns:
        Array of shape (N_directions,) with optimal phases in radians.
    """
    phases = np.zeros(len(h5_paths), dtype=np.float64)
    focus_idx = focus_voxel_idx.reshape(1, 3)

    for i, h5_path in enumerate(h5_paths):
        E_focus = read_field_at_indices(h5_path, focus_idx, field_type="E")
        # E_focus shape: (1, 3) complex

        # Use E_z component for phase reference (or could use |E| weighted)
        # Following the MRT convention from the brainstorm doc
        E_z = E_focus[0, 2]

        # Optimal phase is negative of the E_z angle
        phases[i] = -np.angle(E_z)

    return phases


def compute_weights(phases: np.ndarray) -> np.ndarray:
    """Compute complex weights from phases with equal amplitudes.

    Weights are normalized so Σ|w_i|² = 1 (unit total power).

    Args:
        phases: Array of phases in radians.

    Returns:
        Complex64 array of weights.
    """
    N = len(phases)
    amplitude = 1.0 / np.sqrt(N)
    return amplitude * np.exp(1j * phases).astype(np.complex64)


def find_focus_and_compute_weights(
    h5_paths: Sequence[Union[str, Path]],
    input_h5_path: Union[str, Path],
    skin_keywords: Optional[Sequence[str]] = None,
    top_n: int = 1,
    metric: str = "E_z_magnitude",
) -> Tuple[np.ndarray, np.ndarray, dict]:
    """Complete workflow: find worst-case focus point(s) and compute weights.

    Args:
        h5_paths: List of _Output.h5 file paths.
        input_h5_path: Path to _Input.h5 for skin mask.
        skin_keywords: Keywords to match skin tissues.
        top_n: Number of candidate focus points to return.
        metric: Search metric - "E_z_magnitude" (default) or "poynting_z".

    Returns:
        Tuple of:
            - focus_voxel_indices: Shape (top_n, 3) or (3,) if top_n=1
            - weights: Complex weights for each direction (for top-1 focus)
            - info: Dict with additional info
    """
    # Find worst-case focus points
    focus_voxel_indices, skin_indices, metric_sums = find_worst_case_focus_point(
        h5_paths, input_h5_path, skin_keywords, top_n=top_n, metric=metric
    )

    # Compute optimal phases for the top-1 focus point
    top_focus_idx = focus_voxel_indices[0]
    phases = compute_optimal_phases(h5_paths, top_focus_idx)

    # Compute weights
    weights = compute_weights(phases)

    # Get physical coordinates
    skin_mask, ax_x, ax_y, ax_z, _ = extract_skin_voxels(str(input_h5_path), skin_keywords)
    coords = get_skin_voxel_coordinates(skin_mask, ax_x, ax_y, ax_z)
    focus_coords_m = coords[skin_indices[0]]

    info = {
        "phases_rad": phases,
        "phases_deg": np.degrees(phases),
        "max_metric_sum": float(metric_sums[0]),
        "metric": metric,
        "focus_coords_m": focus_coords_m,
        "n_directions": len(h5_paths),
        "n_skin_voxels": len(coords),
        "top_n": top_n,
        "all_focus_indices": focus_voxel_indices,
        "all_metric_sums": metric_sums,
    }

    # Return single focus if top_n=1, else return all
    if top_n == 1:
        return top_focus_idx, weights, info
    else:
        return focus_voxel_indices, weights, info


# --- CLI for testing ---
if __name__ == "__main__":
    import argparse
    import glob

    parser = argparse.ArgumentParser(description="Find worst-case focus point for auto-induced exposure")
    parser.add_argument("results_dir", help="Directory containing _Output.h5 files")
    parser.add_argument("--input-h5", required=True, help="Path to _Input.h5 for skin mask")
    parser.add_argument("--pattern", default="*_Output.h5", help="Glob pattern for output files")

    args = parser.parse_args()

    # Find all output H5 files
    h5_patterns = glob.glob(f"{args.results_dir}/**/{args.pattern}", recursive=True)
    h5_paths = sorted(h5_patterns)

    if not h5_paths:
        print(f"No files matching {args.pattern} found in {args.results_dir}")
        exit(1)

    print(f"\nFound {len(h5_paths)} _Output.h5 files")
    print(f"Input H5: {args.input_h5}")

    # Run the full workflow
    print("\nSearching for worst-case focus point on skin...")
    focus_idx, weights, info = find_focus_and_compute_weights(h5_paths, args.input_h5)

    print("\n" + "=" * 50)
    print("Results:")
    print("=" * 50)
    print(f"Focus voxel indices: [{focus_idx[0]}, {focus_idx[1]}, {focus_idx[2]}]")
    print(f"Focus coordinates:   ({info['focus_coords_m'][0]:.4f}, {info['focus_coords_m'][1]:.4f}, {info['focus_coords_m'][2]:.4f}) m")
    print(f"Max Σ|E_i|:          {info['max_magnitude_sum']:.4e}")
    print(f"Skin voxels:         {info['n_skin_voxels']:,}")
    print(f"Directions:          {info['n_directions']}")

    print("\nOptimal phases (degrees):")
    for i, (path, phase_deg) in enumerate(zip(h5_paths, info["phases_deg"])):
        name = Path(path).parent.name
        print(f"  [{i:2d}] {name:30s}: {phase_deg:+7.1f}°")

    print("\nWeight magnitudes (should all be equal):")
    print(f"  |w_i| = {np.abs(weights[0]):.6f} (for unit total power)")
