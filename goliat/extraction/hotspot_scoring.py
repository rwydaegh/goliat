"""Hotspot scoring for auto-induced exposure air-focus search.

Computes MRT beamforming hotspot scores at candidate air focus points,
which drive the worst-case focus search in _find_focus_air_based.
"""

import logging
import time
from pathlib import Path
from typing import List, Optional, Sequence, Tuple, Union

import h5py
import numpy as np
from tqdm import tqdm

from .field_cache import FieldCache
from .field_reader import find_overall_field_group, get_field_path, read_field_at_indices


def compute_hotspot_score_at_air_point(
    h5_paths: Sequence[Union[str, Path]],
    air_focus_idx: np.ndarray,
    skin_mask: np.ndarray,
    axis_x: np.ndarray,
    axis_y: np.ndarray,
    axis_z: np.ndarray,
    cube_size_mm: float = 50.0,
    field_cache: Optional[FieldCache] = None,
) -> float:
    """Compute hotspot score for an air focus point.

    The hotspot score is the mean |E_combined|² over skin voxels in a cube
    around the air focus point, where E_combined is the field resulting from
    MRT beamforming focused at that air point.

    Args:
        h5_paths: List of _Output.h5 files (one per direction/polarization).
        air_focus_idx: [ix, iy, iz] of the air focus point.
        skin_mask: Boolean mask of skin voxels.
        axis_x, axis_y, axis_z: Grid axes.
        cube_size_mm: Size of cube around focus to evaluate (mm).
        field_cache: Optional pre-loaded field cache (recommended for performance).

    Returns:
        Hotspot score (mean |E_combined|² over skin voxels in cube).
    """
    focus_idx_array = air_focus_idx.reshape(1, 3)
    E_z_at_focus = []

    for h5_path in h5_paths:
        h5_str = str(h5_path)
        if field_cache is not None:
            E_focus = field_cache.read_at_indices(h5_str, focus_idx_array)
        else:
            E_focus = read_field_at_indices(h5_str, focus_idx_array, field_type="E")
        E_z_at_focus.append(E_focus[0, 2])

    E_z_at_focus = np.array(E_z_at_focus)

    phases = -np.angle(E_z_at_focus)
    N = len(phases)
    weights = (1.0 / np.sqrt(N)) * np.exp(1j * phases)

    dx = np.mean(np.diff(axis_x))
    dy = np.mean(np.diff(axis_y))
    dz = np.mean(np.diff(axis_z))

    cube_size_m = cube_size_mm / 1000.0
    half_nx = int(np.ceil(cube_size_m / (2 * dx)))
    half_ny = int(np.ceil(cube_size_m / (2 * dy)))
    half_nz = int(np.ceil(cube_size_m / (2 * dz)))

    ix, iy, iz = air_focus_idx
    ix_min = max(0, ix - half_nx)
    ix_max = min(skin_mask.shape[0], ix + half_nx + 1)
    iy_min = max(0, iy - half_ny)
    iy_max = min(skin_mask.shape[1], iy + half_ny + 1)
    iz_min = max(0, iz - half_nz)
    iz_max = min(skin_mask.shape[2], iz + half_nz + 1)

    skin_cube = skin_mask[ix_min:ix_max, iy_min:iy_max, iz_min:iz_max]
    skin_indices_local = np.argwhere(skin_cube)

    if len(skin_indices_local) == 0:
        return 0.0

    skin_indices_global = skin_indices_local + np.array([ix_min, iy_min, iz_min])

    E_all_dirs = []
    for h5_path in h5_paths:
        h5_str = str(h5_path)
        if field_cache is not None:
            E = field_cache.read_at_indices(h5_str, skin_indices_global)
        else:
            E = read_field_at_indices(h5_str, skin_indices_global, field_type="E")
        E_all_dirs.append(E)

    E_all_dirs = np.array(E_all_dirs)

    E_combined = np.sum(weights[:, np.newaxis, np.newaxis] * E_all_dirs, axis=0)

    E_combined_sq = np.sum(np.abs(E_combined) ** 2, axis=1)
    return float(np.mean(E_combined_sq))


def compute_all_hotspot_scores_chunked(
    h5_paths: Sequence[Union[str, Path]],
    sampled_air_indices: np.ndarray,
    skin_mask: np.ndarray,
    axis_x: np.ndarray,
    axis_y: np.ndarray,
    axis_z: np.ndarray,
    cube_size_mm: float = 50.0,
    field_cache: Optional[FieldCache] = None,
    chunk_size: int = 100,
) -> np.ndarray:
    """Compute hotspot scores using chunked processing with deduplication.

    DEPRECATED: This function is kept for backward compatibility.
    Use compute_all_hotspot_scores_streaming() instead for low-memory mode.

    Args:
        h5_paths: List of _Output.h5 files (one per direction/polarization).
        sampled_air_indices: (N_air, 3) array of air focus point indices.
        skin_mask: Boolean mask of skin voxels.
        axis_x, axis_y, axis_z: Grid axes.
        cube_size_mm: Size of cube around focus to evaluate (mm).
        field_cache: Optional pre-loaded field cache.
        chunk_size: Number of air points to process per chunk.

    Returns:
        Array of shape (N_air,) with hotspot scores.
    """
    logger = logging.getLogger("progress")
    n_air = len(sampled_air_indices)
    n_dirs = len(h5_paths)

    dx = np.mean(np.diff(axis_x))
    dy = np.mean(np.diff(axis_y))
    dz = np.mean(np.diff(axis_z))
    cube_size_m = cube_size_mm / 1000.0
    half_nx = int(np.ceil(cube_size_m / (2 * dx)))
    half_ny = int(np.ceil(cube_size_m / (2 * dy)))
    half_nz = int(np.ceil(cube_size_m / (2 * dz)))

    logger.info("  [chunked] Step 1: Reading E_z at all focus points...")
    all_focus_indices = np.array(sampled_air_indices)
    E_z_at_focus_all = np.zeros((n_dirs, n_air), dtype=np.complex64)

    for dir_idx, h5_path in enumerate(tqdm(h5_paths, desc="Reading focus E_z", leave=False)):
        h5_str = str(h5_path)
        if field_cache is not None:
            E_focus = field_cache.read_at_indices(h5_str, all_focus_indices)
        else:
            E_focus = read_field_at_indices(h5_str, all_focus_indices, field_type="E")
        E_z_at_focus_all[dir_idx, :] = E_focus[:, 2]

    n_chunks = (n_air + chunk_size - 1) // chunk_size
    logger.info(f"  [chunked] Step 2: Processing {n_air} air points in {n_chunks} chunks of {chunk_size}...")

    hotspot_scores = np.zeros(n_air, dtype=np.float64)
    first_chunk_time = None

    for chunk_idx in tqdm(range(n_chunks), desc="Processing chunks"):
        chunk_start_time = time.perf_counter()
        chunk_start = chunk_idx * chunk_size
        chunk_end = min(chunk_start + chunk_size, n_air)
        chunk_air_indices = sampled_air_indices[chunk_start:chunk_end]

        all_skin_indices_list = []
        skin_ranges = []

        for air_idx in chunk_air_indices:
            ix, iy, iz = air_idx

            ix_min = max(0, ix - half_nx)
            ix_max = min(skin_mask.shape[0], ix + half_nx + 1)
            iy_min = max(0, iy - half_ny)
            iy_max = min(skin_mask.shape[1], iy + half_ny + 1)
            iz_min = max(0, iz - half_nz)
            iz_max = min(skin_mask.shape[2], iz + half_nz + 1)

            skin_cube = skin_mask[ix_min:ix_max, iy_min:iy_max, iz_min:iz_max]
            skin_indices_local = np.argwhere(skin_cube)

            if len(skin_indices_local) == 0:
                skin_ranges.append((None, None))
            else:
                skin_indices_global = skin_indices_local + np.array([ix_min, iy_min, iz_min])
                all_skin_indices_list.append(skin_indices_global)
                skin_ranges.append(len(all_skin_indices_list) - 1)

        if not all_skin_indices_list:
            continue

        all_skin_concat = np.vstack(all_skin_indices_list)

        skin_tuples = [tuple(idx) for idx in all_skin_concat]
        unique_tuples = list(set(skin_tuples))
        unique_skin_indices = np.array(unique_tuples)

        tuple_to_unique_idx = {t: i for i, t in enumerate(unique_tuples)}

        n_unique = len(unique_skin_indices)

        if chunk_idx == 0:
            logger.info(f"  [chunk 0] {n_unique:,} unique skin voxels from {len(all_skin_concat):,} total")

        E_skin_unique = np.zeros((n_dirs, n_unique, 3), dtype=np.complex64)

        for dir_idx, h5_path in enumerate(h5_paths):
            h5_str = str(h5_path)
            if field_cache is not None:
                E_skin = field_cache.read_at_indices(h5_str, unique_skin_indices)
            else:
                E_skin = read_field_at_indices(h5_str, unique_skin_indices, field_type="E")
            E_skin_unique[dir_idx, :, :] = E_skin

        if chunk_idx == 0:
            first_chunk_time = time.perf_counter() - chunk_start_time
            estimated_total = first_chunk_time * n_chunks
            logger.info(f"  [chunk 0] Took {first_chunk_time:.1f}s, estimated total: {estimated_total / 60:.1f} min")

        for local_i, air_idx in enumerate(chunk_air_indices):
            global_i = chunk_start + local_i
            range_info = skin_ranges[local_i]

            if range_info == (None, None):
                hotspot_scores[global_i] = 0.0
                continue

            skin_indices_for_point = all_skin_indices_list[range_info]

            unique_idx_for_point = np.array([tuple_to_unique_idx[tuple(idx)] for idx in skin_indices_for_point])

            E_z_focus = E_z_at_focus_all[:, global_i]
            phases = -np.angle(E_z_focus)
            weights = (1.0 / np.sqrt(n_dirs)) * np.exp(1j * phases)

            E_skin_point = E_skin_unique[:, unique_idx_for_point, :]  # (n_dirs, n_skin, 3)
            E_combined = np.sum(weights[:, np.newaxis, np.newaxis] * E_skin_point, axis=0)

            E_combined_sq = np.sum(np.abs(E_combined) ** 2, axis=1)
            hotspot_scores[global_i] = float(np.mean(E_combined_sq))

    return hotspot_scores


def _precompute_skin_indices_for_air_points(
    sampled_air_indices: np.ndarray,
    skin_mask: np.ndarray,
    half_nx: int,
    half_ny: int,
    half_nz: int,
    subsample: int = 1,
) -> Tuple[List[np.ndarray], int]:
    """Precompute (subsampled) skin voxel indices for each air focus point.

    Args:
        sampled_air_indices: (N_air, 3) array of air focus point indices.
        skin_mask: Boolean mask of skin voxels.
        half_nx, half_ny, half_nz: Half-cube sizes in voxels.
        subsample: Subsampling factor (1 = no subsampling, 4 = every 4th voxel).

    Returns:
        Tuple of:
            - List of (N_skin_i, 3) arrays, one per air point
            - Total number of skin voxels across all air points
    """
    air_to_skin = []
    total_skin = 0

    for air_idx in sampled_air_indices:
        ix, iy, iz = air_idx

        ix_min = max(0, ix - half_nx)
        ix_max = min(skin_mask.shape[0], ix + half_nx + 1)
        iy_min = max(0, iy - half_ny)
        iy_max = min(skin_mask.shape[1], iy + half_ny + 1)
        iz_min = max(0, iz - half_nz)
        iz_max = min(skin_mask.shape[2], iz + half_nz + 1)

        skin_cube = skin_mask[ix_min:ix_max, iy_min:iy_max, iz_min:iz_max]
        skin_indices_local = np.argwhere(skin_cube)

        if len(skin_indices_local) == 0:
            air_to_skin.append(np.zeros((0, 3), dtype=np.int32))
        else:
            skin_indices_global = skin_indices_local + np.array([ix_min, iy_min, iz_min])

            if subsample > 1 and len(skin_indices_global) > subsample:
                skin_indices_global = skin_indices_global[::subsample]

            air_to_skin.append(skin_indices_global.astype(np.int32))
            total_skin += len(skin_indices_global)

    return air_to_skin, total_skin


def compute_all_hotspot_scores_streaming(
    h5_paths: Sequence[Union[str, Path]],
    sampled_air_indices: np.ndarray,
    skin_mask: np.ndarray,
    axis_x: np.ndarray,
    axis_y: np.ndarray,
    axis_z: np.ndarray,
    cube_size_mm: float = 50.0,
    skin_subsample: int = 4,
) -> np.ndarray:
    """Compute hotspot scores using direction-major streaming with subsampled skin.

    This is the FAST low-memory algorithm. Key insights:

    1. Direction-major processing: Load one E-field at a time (3 GB), process
       ALL air points, then free memory. This is sequential I/O = fast.

    2. Skin subsampling: Use every Nth skin voxel for scoring. Since the score
       is a mean, subsampling gives an unbiased estimate with acceptable variance.

    3. Accumulate E_combined incrementally: Store partial sums for each
       (air_point, skin_voxel) pair. Memory: ~150 MB for 10K air points.

    Args:
        h5_paths: List of _Output.h5 files (one per direction/polarization).
        sampled_air_indices: (N_air, 3) array of air focus point indices.
        skin_mask: Boolean mask of skin voxels.
        axis_x, axis_y, axis_z: Grid axes.
        cube_size_mm: Size of cube around focus to evaluate (mm).
        skin_subsample: Subsampling factor for skin voxels (default 4 = use 1/4 of voxels).

    Returns:
        Array of shape (N_air,) with hotspot scores.
    """
    logger = logging.getLogger("progress")
    n_air = len(sampled_air_indices)
    n_dirs = len(h5_paths)

    logger.info(f"  [streaming] Direction-major streaming with {skin_subsample}x skin subsampling")

    dx = np.mean(np.diff(axis_x))
    dy = np.mean(np.diff(axis_y))
    dz = np.mean(np.diff(axis_z))
    cube_size_m = cube_size_mm / 1000.0
    half_nx = int(np.ceil(cube_size_m / (2 * dx)))
    half_ny = int(np.ceil(cube_size_m / (2 * dy)))
    half_nz = int(np.ceil(cube_size_m / (2 * dz)))

    logger.info("  [streaming] Step 1: Precomputing skin indices...")
    air_to_skin, total_skin = _precompute_skin_indices_for_air_points(
        sampled_air_indices, skin_mask, half_nx, half_ny, half_nz, subsample=skin_subsample
    )

    n_with_skin = sum(1 for s in air_to_skin if len(s) > 0)
    avg_skin_per_point = total_skin / max(n_with_skin, 1)
    indices_memory_mb = sum(s.nbytes for s in air_to_skin) / 1e6
    logger.info(
        f"  [streaming] {n_with_skin}/{n_air} air points have skin, "
        f"avg {avg_skin_per_point:.0f} skin voxels/point, {indices_memory_mb:.1f} MB for indices"
    )

    logger.info("  [streaming] Step 2: Reading E_z at all focus points...")
    logger.info("    Loading entire E_z component per file (~1.5 GB) - much faster than slice-by-slice")
    E_z_at_focus_all = np.zeros((n_dirs, n_air), dtype=np.complex64)

    for dir_idx, h5_path in enumerate(tqdm(h5_paths, desc="Reading focus E_z", leave=False)):
        t_file_start = time.perf_counter()

        with h5py.File(h5_path, "r") as f:
            fg_path = find_overall_field_group(f)
            assert fg_path is not None
            field_path = get_field_path(fg_path, "E")

            dataset = f[f"{field_path}/comp2"]
            shape = dataset.shape[:3]

            t_load_start = time.perf_counter()
            E_z_full = dataset[:]  # (Nx, Ny, Nz, 2)
            t_load = time.perf_counter() - t_load_start

            E_z_complex = (E_z_full[..., 0] + 1j * E_z_full[..., 1]).astype(np.complex64)
            del E_z_full

            ix = np.minimum(sampled_air_indices[:, 0], shape[0] - 1)
            iy = np.minimum(sampled_air_indices[:, 1], shape[1] - 1)
            iz = np.minimum(sampled_air_indices[:, 2], shape[2] - 1)

            E_z_at_focus_all[dir_idx, :] = E_z_complex[ix, iy, iz]

            del E_z_complex

            t_total = time.perf_counter() - t_file_start
            if dir_idx == 0:
                logger.info(f"    [dir 0] First file: load={t_load:.1f}s, total={t_total:.1f}s")

    logger.info("  [streaming] Step 3: Computing MRT weights...")
    phases = -np.angle(E_z_at_focus_all)  # (n_dirs, n_air)
    weights = (1.0 / np.sqrt(n_dirs)) * np.exp(1j * phases).astype(np.complex64)  # (n_dirs, n_air)

    logger.info("  [streaming] Step 4: Allocating accumulators...")
    E_combined_accum = [np.zeros((len(skin_idx), 3), dtype=np.complex64) if len(skin_idx) > 0 else None for skin_idx in air_to_skin]
    accum_memory_mb = sum(a.nbytes for a in E_combined_accum if a is not None) / 1e6
    logger.info(f"  [streaming] Accumulator memory: {accum_memory_mb:.1f} MB")

    logger.info(f"  [streaming] Step 5: Streaming through {n_dirs} directions...")
    t_stream_start = time.perf_counter()

    for dir_idx, h5_path in enumerate(tqdm(h5_paths, desc="Processing directions")):
        t_dir_start = time.perf_counter()

        with h5py.File(h5_path, "r") as f:
            fg_path = find_overall_field_group(f)
            assert fg_path is not None
            field_path = get_field_path(fg_path, "E")

            E_components = []
            for comp in range(3):
                dataset = f[f"{field_path}/comp{comp}"]
                data = dataset[:]
                E_components.append((data[..., 0] + 1j * data[..., 1]).astype(np.complex64))

        t_load = time.perf_counter() - t_dir_start

        dir_weights = weights[dir_idx, :]  # (n_air,)

        for air_idx in range(n_air):
            skin_indices = air_to_skin[air_idx]
            if len(skin_indices) == 0:
                continue

            w = dir_weights[air_idx]

            E_at_skin = np.zeros((len(skin_indices), 3), dtype=np.complex64)
            for comp in range(3):
                E_comp = E_components[comp]
                ix = np.minimum(skin_indices[:, 0], E_comp.shape[0] - 1)
                iy = np.minimum(skin_indices[:, 1], E_comp.shape[1] - 1)
                iz = np.minimum(skin_indices[:, 2], E_comp.shape[2] - 1)
                E_at_skin[:, comp] = E_comp[ix, iy, iz]

            E_combined_accum[air_idx] += w * E_at_skin

        t_process = time.perf_counter() - t_dir_start - t_load

        if dir_idx == 0:
            estimated_total = (t_load + t_process) * n_dirs
            logger.info(f"  [dir 0] Load: {t_load:.1f}s, Process: {t_process:.1f}s, Est. total: {estimated_total / 60:.1f} min")

        del E_components

    t_stream_total = time.perf_counter() - t_stream_start
    logger.info(f"  [streaming] Streaming completed in {t_stream_total / 60:.1f} min")

    logger.info("  [streaming] Step 6: Computing final hotspot scores...")
    hotspot_scores = np.zeros(n_air, dtype=np.float64)

    for air_idx in range(n_air):
        E_accum = E_combined_accum[air_idx]
        if E_accum is None or len(E_accum) == 0:
            hotspot_scores[air_idx] = 0.0
        else:
            E_combined_sq = np.sum(np.abs(E_accum) ** 2, axis=1)
            hotspot_scores[air_idx] = float(np.mean(E_combined_sq))

    return hotspot_scores
