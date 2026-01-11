"""Test script to stress-test the full air focus flow.

Tests: Input.h5 reading + dilation + scoring loop

Usage:
    python scripts/test_full_flow_stress.py <input_h5> <output_h5>
"""

import argparse
import time
import numpy as np
from tqdm import tqdm
from scipy import ndimage
from goliat.utils.skin_voxel_utils import extract_skin_voxels, extract_air_voxels
from goliat.extraction.field_reader import read_field_at_indices


def test_input_h5_and_dilation(input_h5_path: str):
    """Test Input.h5 reading and binary dilation."""
    print("=" * 60)
    print("TEST 1: Input.h5 reading + binary dilation")
    print("=" * 60)

    print("Extracting air voxels...")
    t0 = time.perf_counter()
    air_mask, ax_x, ax_y, ax_z, _ = extract_air_voxels(input_h5_path)
    print(f"  Done in {time.perf_counter() - t0:.2f}s")
    print(f"  Air mask shape: {air_mask.shape}, sum: {np.sum(air_mask):,}")

    print("Extracting skin voxels...")
    t0 = time.perf_counter()
    skin_mask, _, _, _, _ = extract_skin_voxels(input_h5_path)
    print(f"  Done in {time.perf_counter() - t0:.2f}s")
    print(f"  Skin mask shape: {skin_mask.shape}, sum: {np.sum(skin_mask):,}")

    print("Running binary dilation (10mm shell)...")
    dx = np.mean(np.diff(ax_x))
    shell_size_mm = 10.0
    half_n = max(1, int(np.ceil((shell_size_mm / 1000.0) / (2 * dx))))
    struct_size = 2 * half_n + 1
    print(f"  Structuring element size: {struct_size}x{struct_size}x{struct_size}")

    t0 = time.perf_counter()
    struct = np.ones((struct_size, struct_size, struct_size), dtype=bool)
    dilated = ndimage.binary_dilation(skin_mask, structure=struct)
    print(f"  Done in {time.perf_counter() - t0:.2f}s")

    valid_air = air_mask & dilated
    valid_indices = np.argwhere(valid_air)
    print(f"  Valid air points: {len(valid_indices):,}")

    print("TEST 1 PASSED!")
    return valid_indices, skin_mask, ax_x, ax_y, ax_z


def test_scoring_loop(
    output_h5_path: str,
    valid_indices: np.ndarray,
    skin_mask: np.ndarray,
    ax_x,
    ax_y,
    ax_z,
    n_samples: int = 100,
    cube_size_mm: float = 50.0,
):
    """Test the hotspot scoring loop."""
    print("\n" + "=" * 60)
    print("TEST 2: Hotspot scoring loop")
    print("=" * 60)

    # Sample indices
    np.random.seed(42)
    n_to_sample = min(n_samples, len(valid_indices))
    sampled_idx = np.random.choice(len(valid_indices), size=n_to_sample, replace=False)
    sampled_air = valid_indices[sampled_idx]
    print(f"Sampling {n_to_sample} air points for scoring...")

    # Get cube params
    dx = np.mean(np.diff(ax_x))
    dy = np.mean(np.diff(ax_y))
    dz = np.mean(np.diff(ax_z))
    cube_size_m = cube_size_mm / 1000.0
    half_nx = int(np.ceil(cube_size_m / (2 * dx)))
    half_ny = int(np.ceil(cube_size_m / (2 * dy)))
    half_nz = int(np.ceil(cube_size_m / (2 * dz)))
    print(f"Cube half-size in voxels: ({half_nx}, {half_ny}, {half_nz})")

    scores = []
    t0 = time.perf_counter()

    for i, air_idx in enumerate(tqdm(sampled_air, desc="Scoring")):
        ix, iy, iz = air_idx

        # Find skin voxels in cube
        ix_min = max(0, ix - half_nx)
        ix_max = min(skin_mask.shape[0], ix + half_nx + 1)
        iy_min = max(0, iy - half_ny)
        iy_max = min(skin_mask.shape[1], iy + half_ny + 1)
        iz_min = max(0, iz - half_nz)
        iz_max = min(skin_mask.shape[2], iz + half_nz + 1)

        skin_cube = skin_mask[ix_min:ix_max, iy_min:iy_max, iz_min:iz_max]
        skin_local = np.argwhere(skin_cube)

        if len(skin_local) == 0:
            scores.append(0.0)
            continue

        skin_global = skin_local + np.array([ix_min, iy_min, iz_min])

        # Read E-field at focus
        focus_arr = air_idx.reshape(1, 3)
        E_focus = read_field_at_indices(output_h5_path, focus_arr, field_type="E")

        # Read E-field at skin voxels
        E_skin = read_field_at_indices(output_h5_path, skin_global, field_type="E")

        # Compute score
        E_combined_sq = np.sum(np.abs(E_skin) ** 2, axis=1)
        score = float(np.mean(E_combined_sq))
        scores.append(score)

        # Progress
        if (i + 1) % 20 == 0:
            elapsed = time.perf_counter() - t0
            print(f"  [{i + 1}/{n_to_sample}] Elapsed: {elapsed:.1f}s, Last score: {score:.2e}")

    elapsed = time.perf_counter() - t0
    print(f"\nCompleted in {elapsed:.1f}s")
    print(f"Scores: min={min(scores):.2e}, max={max(scores):.2e}, mean={np.mean(scores):.2e}")
    print("TEST 2 PASSED!")


def main():
    parser = argparse.ArgumentParser(description="Stress test full air focus flow")
    parser.add_argument("input_h5", help="Path to _Input.h5 file")
    parser.add_argument("output_h5", help="Path to _Output.h5 file")
    parser.add_argument("-n", "--samples", type=int, default=100, help="Number of air points to score (default: 100)")

    args = parser.parse_args()

    # Test 1: Input.h5 + dilation
    valid_indices, skin_mask, ax_x, ax_y, ax_z = test_input_h5_and_dilation(args.input_h5)

    # Test 2: Scoring loop
    test_scoring_loop(args.output_h5, valid_indices, skin_mask, ax_x, ax_y, ax_z, args.samples)

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    main()
