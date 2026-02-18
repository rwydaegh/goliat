"""Focus optimizer for auto-induced exposure worst-case search.

Finds the worst-case focus point on skin where MRT-weighted fields
produce maximum constructive interference, then computes optimal phases.

Key insight: With phase-only weighting, the worst-case location is simply
argmax_r Σ|E_i(r)| - no optimization needed during search.
"""

import logging
import time
from pathlib import Path
from typing import Optional, Sequence, Tuple, Union

import h5py
import numpy as np
from tqdm import tqdm

from .field_cache import FieldCache, _estimate_cache_size_gb, _get_available_memory_gb
from .field_reader import find_overall_field_group, get_field_path, read_field_at_indices
from .hotspot_scoring import compute_all_hotspot_scores_streaming, compute_hotspot_score_at_air_point
from ..utils.skin_voxel_utils import (
    compute_distance_to_skin,
    extract_skin_voxels,
    find_valid_air_focus_points,
    get_distances_at_indices,
    get_skin_voxel_coordinates,
)


def compute_metric_sum_at_skin(
    h5_paths: Sequence[Union[str, Path]],
    skin_indices: np.ndarray,
    metric: str = "E_magnitude",
) -> np.ndarray:
    """Compute sum of field metric at skin voxels across all directions.

    This is the core of the efficient worst-case search. Since optimal phases
    always align phasors, the worst-case location is where Σ(metric) is maximum.

    Args:
        h5_paths: List of _Output.h5 file paths (one per direction).
        skin_indices: Array of shape (N_skin, 3) with [ix, iy, iz] indices.
        metric: Search metric to use:
            - "E_magnitude": |E| = sqrt(|Ex|²+|Ey|²+|Ez|²) - SAPD-consistent (default)
            - "E_z_magnitude": |E_z| - vertical E-field component (MRT-consistent)
            - "poynting_z": |Re(E × H*)_z| - z-component of Poynting vector

    Returns:
        Array of shape (N_skin,) with metric sum at each skin voxel.
    """
    metric_sum = np.zeros(len(skin_indices), dtype=np.float64)

    for h5_path in tqdm(h5_paths, desc="Reading fields", leave=False):
        if metric == "E_magnitude":
            E_skin = read_field_at_indices(h5_path, skin_indices, field_type="E")
            metric_values = np.linalg.norm(E_skin, axis=1)

        elif metric == "E_z_magnitude":
            E_skin = read_field_at_indices(h5_path, skin_indices, field_type="E")
            metric_values = np.abs(E_skin[:, 2])

        elif metric == "poynting_z":
            E_skin = read_field_at_indices(h5_path, skin_indices, field_type="E")
            H_skin = read_field_at_indices(h5_path, skin_indices, field_type="H")
            S_z = np.real(E_skin[:, 0] * np.conj(H_skin[:, 1]) - E_skin[:, 1] * np.conj(H_skin[:, 0]))
            metric_values = np.abs(S_z)

        else:
            raise ValueError(f"Unknown metric: {metric}. Use 'E_magnitude', 'E_z_magnitude', or 'poynting_z'")

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
    skin_mask, axis_x, axis_y, axis_z, _ = extract_skin_voxels(str(input_h5_path), skin_keywords)
    skin_indices = np.argwhere(skin_mask)  # (N_skin, 3)

    if len(skin_indices) == 0:
        raise ValueError("No skin voxels found in input H5")

    metric_sum = compute_metric_sum_at_skin(h5_paths, skin_indices, metric=metric)

    top_n = min(top_n, len(metric_sum))
    top_skin_indices = np.argpartition(metric_sum, -top_n)[-top_n:]
    top_skin_indices = top_skin_indices[np.argsort(metric_sum[top_skin_indices])[::-1]]

    worst_voxel_indices = skin_indices[top_skin_indices]  # (top_n, 3)
    top_metric_sums = metric_sum[top_skin_indices]  # (top_n,)

    return worst_voxel_indices, top_skin_indices, top_metric_sums


def compute_optimal_phases(
    h5_paths: Sequence[Union[str, Path]],
    focus_voxel_idx: np.ndarray,
) -> np.ndarray:
    """Compute optimal phases for focusing at a specific voxel.

    For maximum constructive interference at the focus point:
        φ_i* = -arg(E_i(r))

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
        E_z = E_focus[0, 2]
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
    search_mode: str = "skin",
    n_samples: int = 100,
    cube_size_mm: float = 50.0,
    random_seed: Optional[int] = None,
    shell_size_mm: float = 10.0,
    selection_percentile: float = 95.0,
    min_candidate_distance_mm: float = 50.0,
    low_memory: Optional[bool] = None,
    slab_cache_gb: float = 2.0,
    skin_subsample: int = 4,
) -> Tuple[np.ndarray, np.ndarray, dict]:
    """Complete workflow: find worst-case focus point(s) and compute weights.

    Args:
        h5_paths: List of _Output.h5 file paths.
        input_h5_path: Path to _Input.h5 for skin mask.
        skin_keywords: Keywords to match skin tissues.
        top_n: Number of candidate focus points to return.
        metric: Search metric - "E_z_magnitude" (default) or "poynting_z".
            Only used in skin mode.
        search_mode: "air" (new, physically correct) or "skin" (legacy).
        n_samples: Number of air points to sample (only for mode="air").
        cube_size_mm: Cube size for validity check and scoring (only for mode="air").
        random_seed: Random seed for sampling (only for mode="air").
        selection_percentile: Percentile threshold for candidate selection (e.g., 95 = top 5%).
        min_candidate_distance_mm: Minimum distance between selected candidates.
        low_memory: If True, use streaming mode. If None, auto-detect.
        slab_cache_gb: Size of slab LRU cache in GB for streaming mode.
        skin_subsample: Subsampling factor for skin voxels in low-memory mode.

    Returns:
        Tuple of:
            - focus_voxel_indices: Shape (top_n, 3) or (3,) if top_n=1
            - weights: Complex weights for each direction (for top-1 focus)
            - info: Dict with additional info
    """
    if search_mode == "air":
        return _find_focus_air_based(
            h5_paths=h5_paths,
            input_h5_path=input_h5_path,
            skin_keywords=skin_keywords,
            top_n=top_n,
            n_samples=n_samples,
            cube_size_mm=cube_size_mm,
            random_seed=random_seed,
            shell_size_mm=shell_size_mm,
            selection_percentile=selection_percentile,
            min_candidate_distance_mm=min_candidate_distance_mm,
            low_memory=low_memory,
            slab_cache_gb=slab_cache_gb,
            skin_subsample=skin_subsample,
        )
    else:
        return _find_focus_skin_based(
            h5_paths=h5_paths,
            input_h5_path=input_h5_path,
            skin_keywords=skin_keywords,
            top_n=top_n,
            metric=metric,
        )


def _find_focus_skin_based(
    h5_paths: Sequence[Union[str, Path]],
    input_h5_path: Union[str, Path],
    skin_keywords: Optional[Sequence[str]],
    top_n: int,
    metric: str,
) -> Tuple[np.ndarray, np.ndarray, dict]:
    """Legacy skin-based focus search."""
    focus_voxel_indices, skin_indices, metric_sums = find_worst_case_focus_point(
        h5_paths, input_h5_path, skin_keywords, top_n=top_n, metric=metric
    )

    top_focus_idx = focus_voxel_indices[0]
    phases = compute_optimal_phases(h5_paths, top_focus_idx)
    weights = compute_weights(phases)

    skin_mask, ax_x, ax_y, ax_z, _ = extract_skin_voxels(str(input_h5_path), skin_keywords)
    coords = get_skin_voxel_coordinates(skin_mask, ax_x, ax_y, ax_z)
    focus_coords_m = coords[skin_indices[0]]

    info = {
        "search_mode": "skin",
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

    if top_n == 1:
        return top_focus_idx, weights, info
    else:
        return focus_voxel_indices, weights, info


def _find_focus_air_based(
    h5_paths: Sequence[Union[str, Path]],
    input_h5_path: Union[str, Path],
    skin_keywords: Optional[Sequence[str]],
    top_n: int,
    n_samples: int,
    cube_size_mm: float,
    random_seed: Optional[int],
    shell_size_mm: float = 10.0,
    selection_percentile: float = 95.0,
    min_candidate_distance_mm: float = 50.0,
    low_memory: Optional[bool] = None,
    slab_cache_gb: float = 2.0,
    skin_subsample: int = 4,
    compute_distance: bool = True,
) -> Tuple[np.ndarray, np.ndarray, dict]:
    """Air-based focus search - physically correct MaMIMO beamforming model.

    In low-memory mode, uses direction-major streaming with skin subsampling:
    - Loads one E-field at a time (3 GB) instead of all 72 (216 GB)
    - Uses subsampled skin voxels for scoring (unbiased estimate)
    - Completes in ~30-40 minutes instead of 42+ hours

    Args:
        compute_distance: If True, compute distance-to-skin for each air point.
    """
    logger = logging.getLogger("progress")

    valid_air_indices, ax_x, ax_y, ax_z, skin_mask = find_valid_air_focus_points(
        input_h5_path=str(input_h5_path),
        cube_size_mm=cube_size_mm,
        skin_keywords=skin_keywords,
        shell_size_mm=shell_size_mm,
    )

    n_valid = len(valid_air_indices)
    logger.info(f"Found {n_valid:,} valid air focus points near skin")

    distance_map = None
    if compute_distance:
        logger.info("  Computing distance-to-skin map (EDT)...")
        distance_map = compute_distance_to_skin(skin_mask, ax_x, ax_y, ax_z)

    if random_seed is not None:
        np.random.seed(random_seed)

    if n_samples <= 1.0:
        n_to_sample = max(100, int(n_valid * n_samples))
        logger.info(f"Coverage mode: {n_samples * 100:.1f}% → {n_to_sample:,} samples")
    else:
        n_to_sample = min(int(n_samples), n_valid)

    sampled_idx = np.random.choice(n_valid, size=n_to_sample, replace=False)
    sampled_air_indices = valid_air_indices[sampled_idx]

    logger.info(f"Sampling {n_to_sample:,} air points for hotspot scoring")

    available_gb = _get_available_memory_gb()
    estimated_gb = _estimate_cache_size_gb(h5_paths)

    if low_memory is None:
        use_streaming = available_gb > 0 and estimated_gb > available_gb - FieldCache.MIN_HEADROOM_GB
    else:
        use_streaming = low_memory

    if available_gb > 0:
        logger.info(f"  Memory check: {estimated_gb:.1f} GB needed, {available_gb:.1f} GB available")

    t_scoring_start = time.perf_counter()
    cache_stats = None

    if use_streaming:
        logger.info(
            f"  Using DIRECTION-MAJOR STREAMING mode (low memory)\n"
            f"  - Loads one E-field at a time (~3 GB)\n"
            f"  - Uses {skin_subsample}x skin subsampling for scoring\n"
            f"  - Expected time: ~30-40 minutes for 72 directions"
        )

        hotspot_scores = compute_all_hotspot_scores_streaming(
            h5_paths=h5_paths,
            sampled_air_indices=sampled_air_indices,
            skin_mask=skin_mask,
            axis_x=ax_x,
            axis_y=ax_y,
            axis_z=ax_z,
            cube_size_mm=cube_size_mm,
            skin_subsample=skin_subsample,
        )

        field_cache = None

    else:
        logger.info("  Using IN-MEMORY mode (high RAM) - pre-loading all E-fields...")

        field_cache = FieldCache(h5_paths, field_type="E", low_memory=False, slab_cache_gb=slab_cache_gb)

        hotspot_scores = []
        for air_idx in tqdm(sampled_air_indices, desc="Scoring air focus points", dynamic_ncols=True, mininterval=30.0):
            score = compute_hotspot_score_at_air_point(
                h5_paths=h5_paths,
                air_focus_idx=air_idx,
                skin_mask=skin_mask,
                axis_x=ax_x,
                axis_y=ax_y,
                axis_z=ax_z,
                cube_size_mm=cube_size_mm,
                field_cache=field_cache,
            )
            hotspot_scores.append(score)
        hotspot_scores = np.array(hotspot_scores)

        cache_stats = field_cache.get_cache_stats()

    t_scoring_end = time.perf_counter()

    n_with_skin = np.sum(hotspot_scores > 0)
    n_no_skin = np.sum(hotspot_scores == 0)
    logger.info(f"  Scoring stats: {n_with_skin}/{len(hotspot_scores)} points had skin in cube, {n_no_skin} had no skin (score=0)")
    logger.info(
        f"  [timing] Scoring completed in {t_scoring_end - t_scoring_start:.1f}s ({(t_scoring_end - t_scoring_start) / n_to_sample * 1000:.1f}ms/sample)"
    )

    if cache_stats is not None:
        logger.info(
            f"  [cache] Slab cache: {cache_stats['hits']:,} hits, {cache_stats['misses']:,} misses "
            f"({cache_stats['hit_rate']:.1%} hit rate), {cache_stats['size_mb']:.0f} MB in {cache_stats['n_slabs']} slabs"
        )
    if n_with_skin > 0:
        valid_scores = hotspot_scores[hotspot_scores > 0]
        logger.info(f"  Score range: min={np.min(valid_scores):.4e}, max={np.max(valid_scores):.4e}, mean={np.mean(valid_scores):.4e}")

    if n_with_skin == 0:
        raise ValueError("No valid hotspot scores computed (all air points had no skin in cube)")

    dx_mm = np.mean(np.diff(ax_x)) * 1000
    min_distance_voxels = int(min_candidate_distance_mm / dx_mm)

    top_air_indices, top_scores = _select_diverse_candidates(
        sampled_air_indices=sampled_air_indices,
        hotspot_scores=hotspot_scores,
        top_n=top_n,
        percentile=selection_percentile,
        min_distance_voxels=min_distance_voxels,
        ax_x=ax_x,
        ax_y=ax_y,
        ax_z=ax_z,
    )
    actual_top_n = len(top_air_indices)

    all_candidate_phases = []
    all_candidate_weights = []

    if field_cache is not None:
        for candidate_idx in top_air_indices:
            focus_idx_array = candidate_idx.reshape(1, 3)
            E_z_at_focus = []
            for h5_path in h5_paths:
                h5_str = str(h5_path)
                E_focus = field_cache.read_at_indices(h5_str, focus_idx_array)
                E_z_at_focus.append(E_focus[0, 2])
            candidate_phases = -np.angle(np.array(E_z_at_focus))
            candidate_weights = compute_weights(candidate_phases)
            all_candidate_phases.append(candidate_phases)
            all_candidate_weights.append(candidate_weights)
    else:
        logger.info(f"  Reading phases for {actual_top_n} selected candidates...")
        for candidate_idx in top_air_indices:
            focus_idx_array = candidate_idx.reshape(1, 3)
            E_z_at_focus = []
            for h5_path in h5_paths:
                with h5py.File(h5_path, "r") as f:
                    fg_path = find_overall_field_group(f)
                    assert fg_path is not None
                    field_path = get_field_path(fg_path, "E")
                    dataset = f[f"{field_path}/comp2"]
                    shape = dataset.shape[:3]
                    ix = min(candidate_idx[0], shape[0] - 1)
                    iy = min(candidate_idx[1], shape[1] - 1)
                    iz = min(candidate_idx[2], shape[2] - 1)
                    data = dataset[ix, iy, iz, :]
                    E_z_at_focus.append(data[0] + 1j * data[1])
            candidate_phases = -np.angle(np.array(E_z_at_focus))
            candidate_weights = compute_weights(candidate_phases)
            all_candidate_phases.append(candidate_phases)
            all_candidate_weights.append(candidate_weights)

    top_focus_idx = top_air_indices[0]
    phases = all_candidate_phases[0]
    weights = all_candidate_weights[0]

    ix, iy, iz = top_focus_idx
    focus_coords_m = np.array(
        [
            float(ax_x[min(ix, len(ax_x) - 1)]),
            float(ax_y[min(iy, len(ax_y) - 1)]),
            float(ax_z[min(iz, len(ax_z) - 1)]),
        ]
    )

    sampled_distances_mm = None
    if distance_map is not None:
        sampled_distances_mm = get_distances_at_indices(distance_map, sampled_air_indices)

    all_scores_data = []
    for i, (idx, score) in enumerate(zip(sampled_air_indices, hotspot_scores)):
        x_mm = float(ax_x[min(idx[0], len(ax_x) - 1)]) * 1000
        y_mm = float(ax_y[min(idx[1], len(ax_y) - 1)]) * 1000
        z_mm = float(ax_z[min(idx[2], len(ax_z) - 1)]) * 1000

        entry = {
            "idx": i,
            "voxel_x": int(idx[0]),
            "voxel_y": int(idx[1]),
            "voxel_z": int(idx[2]),
            "x_mm": x_mm,
            "y_mm": y_mm,
            "z_mm": z_mm,
            "proxy_score": float(score),
        }

        if sampled_distances_mm is not None:
            entry["distance_to_skin_mm"] = float(sampled_distances_mm[i])

        all_scores_data.append(entry)

    candidate_distances_mm = None
    if distance_map is not None:
        candidate_distances_mm = get_distances_at_indices(distance_map, top_air_indices)

    info = {
        "search_mode": "air",
        "phases_rad": phases,
        "phases_deg": np.degrees(phases),
        "max_hotspot_score": float(top_scores[0]),
        "focus_coords_m": focus_coords_m,
        "n_directions": len(h5_paths),
        "n_valid_air_points": n_valid,
        "n_sampled": n_to_sample,
        "top_n": actual_top_n,
        "all_focus_indices": top_air_indices,
        "all_hotspot_scores": top_scores,
        "all_candidate_phases": all_candidate_phases,
        "all_candidate_weights": all_candidate_weights,
        "candidate_distances_mm": candidate_distances_mm,
        "cube_size_mm": cube_size_mm,
        "random_seed": random_seed,
        "all_scores_data": all_scores_data,
        "cache_stats": cache_stats,
        "streaming_mode": use_streaming,
        "skin_subsample": skin_subsample if use_streaming else 1,
    }

    if field_cache is not None:
        field_cache.close()

    if actual_top_n == 1:
        return top_focus_idx, weights, info
    else:
        return top_air_indices, weights, info


def _select_diverse_candidates(
    sampled_air_indices: np.ndarray,
    hotspot_scores: np.ndarray,
    top_n: int,
    percentile: float,
    min_distance_voxels: int,
    ax_x: np.ndarray,
    ax_y: np.ndarray,
    ax_z: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    """Select top candidates with diversity constraint.

    Instead of just taking top-N, we:
    1. Filter to top percentile (e.g., top 5%)
    2. From those, greedily select candidates that are at least min_distance apart

    Args:
        sampled_air_indices: All sampled voxel indices (N, 3)
        hotspot_scores: Corresponding scores (N,)
        top_n: Maximum number of candidates to return
        percentile: Only consider scores above this percentile
        min_distance_voxels: Minimum voxel distance between candidates

    Returns:
        Tuple of (selected_indices, selected_scores)
    """
    logger = logging.getLogger("progress")

    valid_mask = hotspot_scores > 0
    if not np.any(valid_mask):
        raise ValueError("No valid scores")

    threshold = np.percentile(hotspot_scores[valid_mask], percentile)
    top_mask = hotspot_scores >= threshold
    n_in_percentile = np.sum(top_mask)
    logger.info(f"  Selection: {n_in_percentile} points in top {100 - percentile:.0f}% (threshold={threshold:.4e})")

    top_indices = np.where(top_mask)[0]
    sorted_order = np.argsort(hotspot_scores[top_indices])[::-1]
    top_indices = top_indices[sorted_order]

    selected = []
    selected_positions = []

    for idx in top_indices:
        if len(selected) >= top_n:
            break

        pos = sampled_air_indices[idx]

        is_diverse = True
        for prev_pos in selected_positions:
            dist = np.sqrt(np.sum((pos - prev_pos) ** 2))
            if dist < min_distance_voxels:
                is_diverse = False
                break

        if is_diverse:
            selected.append(idx)
            selected_positions.append(pos)

    if len(selected) == 0:
        logger.info("  Warning: diversity constraint too strict, falling back to top-N")
        selected = top_indices[:top_n].tolist()

    selected = np.array(selected)
    logger.info(f"  Selected {len(selected)} diverse candidates from top {100 - percentile:.0f}%")

    return sampled_air_indices[selected], hotspot_scores[selected]


# --- CLI for testing ---
if __name__ == "__main__":
    import argparse
    import glob

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logger = logging.getLogger("verbose")

    parser = argparse.ArgumentParser(description="Find worst-case focus point for auto-induced exposure")
    parser.add_argument("results_dir", help="Directory containing _Output.h5 files")
    parser.add_argument("--input-h5", required=True, help="Path to _Input.h5 for skin mask")
    parser.add_argument("--pattern", default="*_Output.h5", help="Glob pattern for output files")

    args = parser.parse_args()

    h5_patterns = glob.glob(f"{args.results_dir}/**/{args.pattern}", recursive=True)
    h5_paths = sorted(h5_patterns)

    if not h5_paths:
        logger.error(f"No files matching {args.pattern} found in {args.results_dir}")
        exit(1)

    logger.info(f"\nFound {len(h5_paths)} _Output.h5 files")
    logger.info(f"Input H5: {args.input_h5}")

    logger.info("\nSearching for worst-case focus point on skin...")
    focus_idx, weights, info = find_focus_and_compute_weights(h5_paths, args.input_h5)

    logger.info("\n" + "=" * 50)
    logger.info("Results:")
    logger.info("=" * 50)
    logger.info(f"Focus voxel indices: [{focus_idx[0]}, {focus_idx[1]}, {focus_idx[2]}]")
    logger.info(
        f"Focus coordinates:   ({info['focus_coords_m'][0]:.4f}, {info['focus_coords_m'][1]:.4f}, {info['focus_coords_m'][2]:.4f}) m"
    )
    logger.info(f"Max metric sum:      {info['max_metric_sum']:.4e}")
    logger.info(f"Skin voxels:         {info['n_skin_voxels']:,}")
    logger.info(f"Directions:          {info['n_directions']}")

    logger.info("\nOptimal phases (degrees):")
    for i, (path, phase_deg) in enumerate(zip(h5_paths, info["phases_deg"])):
        name = Path(path).parent.name
        logger.info(f"  [{i:2d}] {name:30s}: {phase_deg:+7.1f} deg")

    logger.info("\nWeight magnitudes (should all be equal):")
    logger.info(f"  |w_i| = {np.abs(weights[0]):.6f} (for unit total power)")
