"""Focus optimizer for auto-induced exposure worst-case search.

Finds the worst-case focus point on skin where MRT-weighted fields
produce maximum constructive interference, then computes optimal phases.

Key insight: With phase-only weighting, the worst-case location is simply
argmax_r Σ|E_i(r)| - no optimization needed during search.
"""

import numpy as np
from pathlib import Path
from typing import Sequence, Tuple, Union, Optional

from .field_reader import read_field_at_indices
from .skin_voxel_utils import extract_skin_voxels, get_skin_voxel_coordinates


def compute_magnitude_sum_at_skin(
    h5_paths: Sequence[Union[str, Path]],
    skin_indices: np.ndarray,
) -> np.ndarray:
    """Compute sum of E-field magnitudes at skin voxels across all directions.

    This is the core of the efficient worst-case search. Since optimal phases
    always align phasors, the worst-case SAR location is where Σ|E_i| is maximum.

    Args:
        h5_paths: List of _Output.h5 file paths (one per direction).
        skin_indices: Array of shape (N_skin, 3) with [ix, iy, iz] indices.

    Returns:
        Array of shape (N_skin,) with |E| sum at each skin voxel.
    """
    magnitude_sum = np.zeros(len(skin_indices), dtype=np.float64)

    for h5_path in h5_paths:
        # Read E-field at skin voxels only
        E_skin = read_field_at_indices(h5_path, skin_indices, field_type="E")
        # E_skin shape: (N_skin, 3) complex

        # Compute |E| = sqrt(|Ex|² + |Ey|² + |Ez|²)
        E_magnitude = np.linalg.norm(E_skin, axis=1)
        magnitude_sum += E_magnitude

    return magnitude_sum


def find_worst_case_focus_point(
    h5_paths: Sequence[Union[str, Path]],
    input_h5_path: Union[str, Path],
    skin_keywords: Optional[Sequence[str]] = None,
) -> Tuple[np.ndarray, int, float]:
    """Find the worst-case focus point on skin.

    Args:
        h5_paths: List of _Output.h5 file paths (one per direction/polarization).
        input_h5_path: Path to _Input.h5 for skin mask extraction.
        skin_keywords: Keywords to match skin tissues (default: ["skin"]).

    Returns:
        Tuple of:
            - worst_voxel_idx: Array [ix, iy, iz] of worst-case voxel indices
            - skin_idx: Index within skin voxels array
            - max_magnitude_sum: Maximum Σ|E_i| value
    """
    # Extract skin mask and indices
    skin_mask, axis_x, axis_y, axis_z, _ = extract_skin_voxels(str(input_h5_path), skin_keywords)
    skin_indices = np.argwhere(skin_mask)  # Shape: (N_skin, 3)

    if len(skin_indices) == 0:
        raise ValueError("No skin voxels found in input H5")

    # Compute magnitude sum at all skin voxels
    magnitude_sum = compute_magnitude_sum_at_skin(h5_paths, skin_indices)

    # Find maximum
    worst_skin_idx = np.argmax(magnitude_sum)
    worst_voxel_idx = skin_indices[worst_skin_idx]
    max_magnitude_sum = magnitude_sum[worst_skin_idx]

    return worst_voxel_idx, worst_skin_idx, max_magnitude_sum


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
) -> Tuple[np.ndarray, np.ndarray, dict]:
    """Complete workflow: find worst-case focus point and compute weights.

    Args:
        h5_paths: List of _Output.h5 file paths.
        input_h5_path: Path to _Input.h5 for skin mask.
        skin_keywords: Keywords to match skin tissues.

    Returns:
        Tuple of:
            - focus_voxel_idx: [ix, iy, iz] of worst-case focus point
            - weights: Complex weights for each direction
            - info: Dict with additional info (phases, max_magnitude_sum, etc.)
    """
    # Find worst-case focus point
    focus_voxel_idx, skin_idx, max_mag_sum = find_worst_case_focus_point(h5_paths, input_h5_path, skin_keywords)

    # Compute optimal phases
    phases = compute_optimal_phases(h5_paths, focus_voxel_idx)

    # Compute weights
    weights = compute_weights(phases)

    # Get physical coordinates
    skin_mask, ax_x, ax_y, ax_z, _ = extract_skin_voxels(str(input_h5_path), skin_keywords)
    coords = get_skin_voxel_coordinates(skin_mask, ax_x, ax_y, ax_z)
    focus_coords_m = coords[skin_idx]

    info = {
        "phases_rad": phases,
        "phases_deg": np.degrees(phases),
        "max_magnitude_sum": max_mag_sum,
        "focus_coords_m": focus_coords_m,
        "n_directions": len(h5_paths),
        "n_skin_voxels": len(coords),
    }

    return focus_voxel_idx, weights, info


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
