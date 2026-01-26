"""Focus optimizer for auto-induced exposure worst-case search.

Finds the worst-case focus point on skin where MRT-weighted fields
produce maximum constructive interference, then computes optimal phases.

Key insight: With phase-only weighting, the worst-case location is simply
argmax_r Σ|E_i(r)| - no optimization needed during search.
"""

import logging
import time
import warnings
from collections import OrderedDict
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple, Union

import h5py
import numpy as np
from tqdm import tqdm

from .field_reader import read_field_at_indices, find_overall_field_group, get_field_path
from ..utils.skin_voxel_utils import (
    extract_skin_voxels,
    get_skin_voxel_coordinates,
    find_valid_air_focus_points,
)


def _get_available_memory_gb() -> float:
    """Get available system memory in GB.

    Returns:
        Available memory in GB, or -1 if detection fails.
    """
    try:
        import psutil

        return psutil.virtual_memory().available / (1024**3)
    except ImportError:
        # psutil not available, try platform-specific fallback
        pass

    try:
        # Windows fallback
        import ctypes

        kernel32 = ctypes.windll.kernel32
        c_ulonglong = ctypes.c_ulonglong

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", c_ulonglong),
                ("ullAvailPhys", c_ulonglong),
                ("ullTotalPageFile", c_ulonglong),
                ("ullAvailPageFile", c_ulonglong),
                ("ullTotalVirtual", c_ulonglong),
                ("ullAvailVirtual", c_ulonglong),
                ("ullAvailExtendedVirtual", c_ulonglong),
            ]

        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(stat)
        kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
        return stat.ullAvailPhys / (1024**3)
    except Exception:
        pass

    return -1.0  # Unknown


def _estimate_cache_size_gb(h5_paths: Sequence[Union[str, Path]]) -> float:
    """Estimate the memory needed to cache all E-fields.

    Args:
        h5_paths: Paths to _Output.h5 files.

    Returns:
        Estimated cache size in GB.
    """
    total_bytes = 0
    for h5_path in h5_paths:
        try:
            with h5py.File(h5_path, "r") as f:
                fg_path = find_overall_field_group(f)
                if fg_path is None:
                    continue
                field_path = get_field_path(fg_path, "E")
                for comp in range(3):
                    ds = f[f"{field_path}/comp{comp}"]
                    # complex64 = 8 bytes per element
                    total_bytes += ds.shape[0] * ds.shape[1] * ds.shape[2] * 8
        except Exception:
            pass
    return total_bytes / (1024**3)


class SlabLRUCache:
    """LRU cache for z-slabs of field data.
    
    Caches rectangular z-slabs to exploit spatial locality when scoring
    nearby air focus points. Much faster than single-point reads.
    """
    
    def __init__(self, max_size_gb: float = 2.0, slab_thickness: int = 32):
        """Initialize the slab cache.
        
        Args:
            max_size_gb: Maximum cache size in GB.
            slab_thickness: Number of z-slices per slab (default 32).
        """
        self.max_size_bytes = int(max_size_gb * 1024**3)
        self.slab_thickness = slab_thickness
        self.current_size_bytes = 0
        # Key: (h5_path, comp, z_slab_idx) -> Value: np.ndarray
        self._cache: OrderedDict[Tuple[str, int, int], np.ndarray] = OrderedDict()
        self._hits = 0
        self._misses = 0
    
    def get_slab(
        self,
        h5_file: h5py.File,
        h5_path: str,
        field_path: str,
        comp: int,
        z_slab_idx: int,
    ) -> np.ndarray:
        """Get a z-slab from cache or load from disk.
        
        Args:
            h5_file: Open HDF5 file handle.
            h5_path: Path to H5 file (for cache key).
            field_path: Path to field group in H5.
            comp: Component index (0, 1, or 2).
            z_slab_idx: Which z-slab (z // slab_thickness).
            
        Returns:
            Complex array of shape (Nx, Ny, slab_thickness, 2) or smaller at boundary.
        """
        key = (h5_path, comp, z_slab_idx)
        
        if key in self._cache:
            # Move to end (most recently used)
            self._cache.move_to_end(key)
            self._hits += 1
            return self._cache[key]
        
        # Cache miss - load from disk
        self._misses += 1
        dataset = h5_file[f"{field_path}/comp{comp}"]
        shape = dataset.shape  # (Nx, Ny, Nz, 2)
        
        z_start = z_slab_idx * self.slab_thickness
        z_end = min(z_start + self.slab_thickness, shape[2])
        
        # Read the slab
        slab_data = dataset[:, :, z_start:z_end, :]
        # Convert to complex immediately to save memory
        slab_complex = (slab_data[..., 0] + 1j * slab_data[..., 1]).astype(np.complex64)
        
        # Evict old entries if needed
        slab_bytes = slab_complex.nbytes
        while self.current_size_bytes + slab_bytes > self.max_size_bytes and self._cache:
            _, evicted = self._cache.popitem(last=False)
            self.current_size_bytes -= evicted.nbytes
        
        # Add to cache
        self._cache[key] = slab_complex
        self.current_size_bytes += slab_bytes
        
        return slab_complex
    
    def get_stats(self) -> Dict[str, float]:
        """Get cache statistics."""
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0.0
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": hit_rate,
            "size_mb": self.current_size_bytes / 1e6,
            "n_slabs": len(self._cache),
        }


class FieldCache:
    """Cache for pre-loaded E-field data from multiple H5 files.

    Supports three modes:
    - Memory mode (default): Load all fields into RAM for fast access.
      Best when you have enough RAM to hold all field data (~3 min).
    - Streaming mode (optimized): Uses slab-based LRU cache for efficient
      disk access. Much faster than naive streaming (~10-30 min vs 42 hours).
    - Legacy streaming mode: Single-point reads (extremely slow, deprecated).

    Mode is automatically selected based on available RAM,
    or can be forced via the low_memory parameter.
    """

    # Minimum recommended headroom (GB) after loading cache
    MIN_HEADROOM_GB = 8.0
    
    # Default slab cache size for streaming mode (GB)
    DEFAULT_SLAB_CACHE_GB = 2.0

    def __init__(
        self,
        h5_paths: Sequence[Union[str, Path]],
        field_type: str = "E",
        low_memory: Optional[bool] = None,
        slab_cache_gb: float = DEFAULT_SLAB_CACHE_GB,
    ):
        """Initialize the field cache.

        Args:
            h5_paths: Paths to _Output.h5 files.
            field_type: 'E' or 'H'.
            low_memory: If True, use streaming mode (no pre-loading).
                If False, always use memory mode (may cause paging on low-RAM).
                If None (default), auto-detect based on available RAM.
            slab_cache_gb: Size of slab LRU cache in GB (only for streaming mode).
        """
        self.h5_paths = [str(p) for p in h5_paths]
        self.field_type = field_type
        self.fields: Dict[str, List[np.ndarray]] = {}
        self.shapes: Dict[str, Tuple[int, int, int]] = {}
        self.slab_cache_gb = slab_cache_gb
        
        # Slab cache for streaming mode (initialized lazily)
        self._slab_cache: Optional[SlabLRUCache] = None
        # Keep file handles open in streaming mode for efficiency
        self._open_files: Dict[str, h5py.File] = {}
        self._field_paths: Dict[str, str] = {}

        logger = logging.getLogger("progress")

        # Check available memory
        available_gb = _get_available_memory_gb()
        estimated_gb = _estimate_cache_size_gb(h5_paths)
        has_enough_ram = (
            available_gb < 0  # Unknown RAM = assume enough
            or estimated_gb <= available_gb - self.MIN_HEADROOM_GB
        )

        # Determine whether to use streaming mode
        if low_memory is None:
            # Auto-detect: use streaming if RAM is insufficient
            self.streaming_mode = not has_enough_ram
        else:
            self.streaming_mode = low_memory

        if available_gb > 0:
            logger.info(f"  Memory check: {estimated_gb:.1f} GB needed, {available_gb:.1f} GB available")

        if self.streaming_mode:
            # Streaming mode with optimized slab-based caching
            logger.info(
                f"  Using OPTIMIZED STREAMING mode with {slab_cache_gb:.1f} GB slab cache\n"
                f"  This is ~100x faster than naive streaming. "
                f"For fastest processing, use a machine with >{estimated_gb + self.MIN_HEADROOM_GB:.0f} GB RAM."
            )
            # Initialize slab cache and open files
            self._init_streaming_mode()
        else:
            # Memory mode: pre-load all fields
            if not has_enough_ram:
                warning_msg = (
                    f"\n{'=' * 70}\n"
                    f"  WARNING: Insufficient RAM for field cache!\n"
                    f"  - Cache size: {estimated_gb:.1f} GB\n"
                    f"  - Available RAM: {available_gb:.1f} GB\n"
                    f"  - Recommended: {estimated_gb + self.MIN_HEADROOM_GB:.1f} GB\n"
                    f"\n"
                    f"  This may cause severe slowdowns due to disk paging.\n"
                    f"  Consider:\n"
                    f"    1. Closing other applications to free RAM\n"
                    f"    2. Running on a machine with more RAM\n"
                    f"    3. Reducing n_samples in config\n"
                    f"    4. Setting low_memory_mode=true in config\n"
                    f"{'=' * 70}\n"
                )
                logger.warning(warning_msg)
                warnings.warn(
                    f"Field cache ({estimated_gb:.1f} GB) exceeds available RAM ({available_gb:.1f} GB). Expect severe slowdowns.",
                    ResourceWarning,
                    stacklevel=2,
                )

            logger.info(f"  Pre-loading {field_type}-fields from {len(h5_paths)} files...")
            t0 = time.perf_counter()

            for h5_path in tqdm(self.h5_paths, desc=f"Loading {field_type}-fields"):
                self._load_field(h5_path)

            total_mb = sum(sum(c.nbytes for c in comps) for comps in self.fields.values()) / 1e6
            logger.info(f"  [timing] Field cache loaded: {time.perf_counter() - t0:.2f}s, {total_mb:.0f} MB")
    
    def _init_streaming_mode(self):
        """Initialize streaming mode with slab cache and open file handles."""
        self._slab_cache = SlabLRUCache(
            max_size_gb=self.slab_cache_gb,
            slab_thickness=32,  # ~32 z-slices per slab, good balance
        )
        
        # Open all files and cache field paths
        for h5_path in self.h5_paths:
            f = h5py.File(h5_path, "r")
            self._open_files[h5_path] = f
            
            fg_path = find_overall_field_group(f)
            if fg_path is None:
                raise ValueError(f"No 'Overall Field' found in {h5_path}")
            
            field_path = get_field_path(fg_path, self.field_type)
            self._field_paths[h5_path] = field_path
            
            # Get shape from first component
            dataset = f[f"{field_path}/comp0"]
            self.shapes[h5_path] = dataset.shape[:3]

    def _load_shapes_only(self):
        """Load only field shapes (for streaming mode index clamping)."""
        for h5_path in self.h5_paths:
            with h5py.File(h5_path, "r") as f:
                fg_path = find_overall_field_group(f)
                if fg_path is None:
                    raise ValueError(f"No 'Overall Field' found in {h5_path}")
                field_path = get_field_path(fg_path, self.field_type)
                # Get shape from first component
                dataset = f[f"{field_path}/comp0"]
                self.shapes[h5_path] = dataset.shape[:3]

    def _load_field(self, h5_path: str):
        """Load a single field file into the cache."""
        with h5py.File(h5_path, "r") as f:
            fg_path = find_overall_field_group(f)
            if fg_path is None:
                raise ValueError(f"No 'Overall Field' found in {h5_path}")

            field_path = get_field_path(fg_path, self.field_type)

            # Load all 3 components into a combined array
            components = []
            for comp in range(3):
                dataset = f[f"{field_path}/comp{comp}"]
                data = dataset[:]
                complex_data = data[..., 0] + 1j * data[..., 1]
                components.append(complex_data)
                if comp == 0:
                    self.shapes[h5_path] = dataset.shape[:3]

            # Store as (Nx, Ny, Nz, 3) but components have different shapes due to Yee
            # We'll handle indexing in read_at_indices
            self.fields[h5_path] = components

    def read_at_indices(self, h5_path: str, indices: np.ndarray) -> np.ndarray:
        """Read field values at specific indices.

        In memory mode, reads from pre-loaded cached data.
        In streaming mode, uses slab-based caching for efficiency.

        Args:
            h5_path: Which file to read from.
            indices: (N, 3) array of [ix, iy, iz] indices.

        Returns:
            (N, 3) complex array of field values.
        """
        if self.streaming_mode:
            return self._read_at_indices_streaming_optimized(h5_path, indices)
        else:
            return self._read_at_indices_memory(h5_path, indices)

    def _read_at_indices_memory(self, h5_path: str, indices: np.ndarray) -> np.ndarray:
        """Read from pre-loaded in-memory cache (fast)."""
        components = self.fields[h5_path]
        result = np.zeros((len(indices), 3), dtype=np.complex64)

        for comp in range(3):
            data = components[comp]
            shape = data.shape

            # Clamp indices to valid range for this component
            ix = np.minimum(indices[:, 0], shape[0] - 1)
            iy = np.minimum(indices[:, 1], shape[1] - 1)
            iz = np.minimum(indices[:, 2], shape[2] - 1)

            result[:, comp] = data[ix, iy, iz]

        return result

    def _read_at_indices_streaming_optimized(self, h5_path: str, indices: np.ndarray) -> np.ndarray:
        """Read using slab-based LRU cache (optimized streaming).
        
        Instead of reading individual points, reads z-slabs and caches them.
        This exploits:
        1. Spatial locality: nearby air focus points share skin voxels
        2. HDF5 chunking: reading a slab is almost as fast as reading one point
        3. LRU eviction: keeps hot slabs in memory
        """
        result = np.zeros((len(indices), 3), dtype=np.complex64)
        n_points = len(indices)
        
        if n_points == 0:
            return result
        
        f = self._open_files[h5_path]
        field_path = self._field_paths[h5_path]
        slab_thickness = self._slab_cache.slab_thickness
        
        for comp in range(3):
            dataset = f[f"{field_path}/comp{comp}"]
            shape = dataset.shape[:3]
            
            # Clamp indices to valid range for this component
            ix = np.minimum(indices[:, 0], shape[0] - 1)
            iy = np.minimum(indices[:, 1], shape[1] - 1)
            iz = np.minimum(indices[:, 2], shape[2] - 1)
            
            # Group points by z-slab for efficient batch reads
            z_slab_indices = iz // slab_thickness
            unique_slabs = np.unique(z_slab_indices)
            
            for z_slab_idx in unique_slabs:
                # Get slab from cache (loads from disk if not cached)
                slab = self._slab_cache.get_slab(
                    h5_file=f,
                    h5_path=h5_path,
                    field_path=field_path,
                    comp=comp,
                    z_slab_idx=int(z_slab_idx),
                )
                
                # Find points in this slab
                mask = z_slab_indices == z_slab_idx
                point_indices = np.where(mask)[0]
                
                # Local z-index within slab
                z_local = iz[mask] - (z_slab_idx * slab_thickness)
                
                # Vectorized read from cached slab
                result[point_indices, comp] = slab[ix[mask], iy[mask], z_local]
        
        return result
    
    def get_cache_stats(self) -> Optional[Dict[str, float]]:
        """Get slab cache statistics (streaming mode only)."""
        if self._slab_cache is not None:
            return self._slab_cache.get_stats()
        return None
    
    def close(self):
        """Close open file handles (streaming mode cleanup)."""
        for f in self._open_files.values():
            try:
                f.close()
            except Exception:
                pass
        self._open_files.clear()
    
    def __del__(self):
        """Cleanup on garbage collection."""
        self.close()


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
            # Read E-field, compute full vector magnitude
            E_skin = read_field_at_indices(h5_path, skin_indices, field_type="E")
            # |E| = sqrt(|Ex|² + |Ey|² + |Ez|²)
            metric_values = np.linalg.norm(E_skin, axis=1)

        elif metric == "E_z_magnitude":
            # Read only E-field, use z-component magnitude
            E_skin = read_field_at_indices(h5_path, skin_indices, field_type="E")
            metric_values = np.abs(E_skin[:, 2])  # |E_z| only

        elif metric == "poynting_z":
            # Read both E and H, compute Poynting z-component
            E_skin = read_field_at_indices(h5_path, skin_indices, field_type="E")
            H_skin = read_field_at_indices(h5_path, skin_indices, field_type="H")
            # S = Re(E × H*), S_z = Re(Ex * Hy* - Ey * Hx*)
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

    # Read E_z at focus from all directions
    for h5_path in h5_paths:
        h5_str = str(h5_path)
        if field_cache is not None:
            E_focus = field_cache.read_at_indices(h5_str, focus_idx_array)
        else:
            E_focus = read_field_at_indices(h5_str, focus_idx_array, field_type="E")
        E_z_at_focus.append(E_focus[0, 2])

    E_z_at_focus = np.array(E_z_at_focus)

    # Compute MRT phases and weights
    phases = -np.angle(E_z_at_focus)
    N = len(phases)
    weights = (1.0 / np.sqrt(N)) * np.exp(1j * phases)

    # Find skin voxels in cube around focus
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

    # Read E-field at all skin voxels for all directions
    E_all_dirs = []
    for h5_path in h5_paths:
        h5_str = str(h5_path)
        if field_cache is not None:
            E = field_cache.read_at_indices(h5_str, skin_indices_global)
        else:
            E = read_field_at_indices(h5_str, skin_indices_global, field_type="E")
        E_all_dirs.append(E)

    E_all_dirs = np.array(E_all_dirs)

    # Combine with weights
    E_combined = np.sum(weights[:, np.newaxis, np.newaxis] * E_all_dirs, axis=0)

    # Compute |E_combined|² and return mean
    E_combined_sq = np.sum(np.abs(E_combined) ** 2, axis=1)
    return float(np.mean(E_combined_sq))


def compute_all_hotspot_scores_batched(
    h5_paths: Sequence[Union[str, Path]],
    sampled_air_indices: np.ndarray,
    skin_mask: np.ndarray,
    axis_x: np.ndarray,
    axis_y: np.ndarray,
    axis_z: np.ndarray,
    cube_size_mm: float = 50.0,
    field_cache: Optional[FieldCache] = None,
) -> np.ndarray:
    """Compute hotspot scores for ALL air focus points in a batched manner.
    
    This is much more efficient than calling compute_hotspot_score_at_air_point
    in a loop because it:
    1. Processes one H5 file at a time (better I/O pattern)
    2. Collects all unique indices needed across all air points
    3. Reads each file only once with all needed indices
    
    Args:
        h5_paths: List of _Output.h5 files (one per direction/polarization).
        sampled_air_indices: (N_air, 3) array of air focus point indices.
        skin_mask: Boolean mask of skin voxels.
        axis_x, axis_y, axis_z: Grid axes.
        cube_size_mm: Size of cube around focus to evaluate (mm).
        field_cache: Optional pre-loaded field cache.
        
    Returns:
        Array of shape (N_air,) with hotspot scores.
    """
    logger = logging.getLogger("progress")
    n_air = len(sampled_air_indices)
    n_dirs = len(h5_paths)
    
    # Pre-compute cube half-sizes in voxels
    dx = np.mean(np.diff(axis_x))
    dy = np.mean(np.diff(axis_y))
    dz = np.mean(np.diff(axis_z))
    cube_size_m = cube_size_mm / 1000.0
    half_nx = int(np.ceil(cube_size_m / (2 * dx)))
    half_ny = int(np.ceil(cube_size_m / (2 * dy)))
    half_nz = int(np.ceil(cube_size_m / (2 * dz)))
    
    # Step 1: For each air point, find its skin voxels and store metadata
    # We need: focus point index, skin voxel indices for that point
    logger.info("  [batched] Step 1: Finding skin voxels for each air point...")
    
    air_point_data = []  # List of (focus_idx, skin_indices_global) tuples
    all_focus_indices = []  # All focus points (for batch read)
    all_skin_indices_list = []  # All skin indices across all air points
    skin_index_ranges = []  # (start, end) for each air point's skin indices
    
    current_skin_idx = 0
    for i, air_idx in enumerate(sampled_air_indices):
        ix, iy, iz = air_idx
        
        # Cube bounds
        ix_min = max(0, ix - half_nx)
        ix_max = min(skin_mask.shape[0], ix + half_nx + 1)
        iy_min = max(0, iy - half_ny)
        iy_max = min(skin_mask.shape[1], iy + half_ny + 1)
        iz_min = max(0, iz - half_nz)
        iz_max = min(skin_mask.shape[2], iz + half_nz + 1)
        
        # Find skin voxels in cube
        skin_cube = skin_mask[ix_min:ix_max, iy_min:iy_max, iz_min:iz_max]
        skin_indices_local = np.argwhere(skin_cube)
        
        if len(skin_indices_local) == 0:
            skin_index_ranges.append((current_skin_idx, current_skin_idx))  # Empty range
        else:
            skin_indices_global = skin_indices_local + np.array([ix_min, iy_min, iz_min])
            all_skin_indices_list.append(skin_indices_global)
            skin_index_ranges.append((current_skin_idx, current_skin_idx + len(skin_indices_global)))
            current_skin_idx += len(skin_indices_global)
        
        all_focus_indices.append(air_idx)
    
    # Concatenate all skin indices
    if all_skin_indices_list:
        all_skin_indices = np.vstack(all_skin_indices_list)
    else:
        all_skin_indices = np.zeros((0, 3), dtype=np.int64)
    
    all_focus_indices = np.array(all_focus_indices)
    total_skin_voxels = len(all_skin_indices)
    
    logger.info(f"  [batched] Total unique reads needed: {n_air} focus + {total_skin_voxels} skin = {n_air + total_skin_voxels} points")
    
    # Step 2: Read E_z at all focus points from all directions (for MRT weights)
    logger.info("  [batched] Step 2: Reading E_z at focus points...")
    E_z_at_focus_all = np.zeros((n_dirs, n_air), dtype=np.complex64)
    
    for dir_idx, h5_path in enumerate(tqdm(h5_paths, desc="Reading focus E_z", leave=False)):
        h5_str = str(h5_path)
        if field_cache is not None:
            E_focus = field_cache.read_at_indices(h5_str, all_focus_indices)
        else:
            E_focus = read_field_at_indices(h5_str, all_focus_indices, field_type="E")
        E_z_at_focus_all[dir_idx, :] = E_focus[:, 2]  # E_z component
    
    # Step 3: Read E-field at all skin voxels from all directions
    logger.info("  [batched] Step 3: Reading E-field at skin voxels...")
    if total_skin_voxels > 0:
        E_skin_all = np.zeros((n_dirs, total_skin_voxels, 3), dtype=np.complex64)
        
        for dir_idx, h5_path in enumerate(tqdm(h5_paths, desc="Reading skin E-fields", leave=False)):
            h5_str = str(h5_path)
            if field_cache is not None:
                E_skin = field_cache.read_at_indices(h5_str, all_skin_indices)
            else:
                E_skin = read_field_at_indices(h5_str, all_skin_indices, field_type="E")
            E_skin_all[dir_idx, :, :] = E_skin
    else:
        E_skin_all = np.zeros((n_dirs, 0, 3), dtype=np.complex64)
    
    # Step 4: Compute hotspot scores for each air point
    logger.info("  [batched] Step 4: Computing hotspot scores...")
    hotspot_scores = np.zeros(n_air, dtype=np.float64)
    
    for i in range(n_air):
        # Get E_z at this focus point from all directions
        E_z_focus = E_z_at_focus_all[:, i]  # (n_dirs,)
        
        # Compute MRT phases and weights
        phases = -np.angle(E_z_focus)
        weights = (1.0 / np.sqrt(n_dirs)) * np.exp(1j * phases)  # (n_dirs,)
        
        # Get skin voxel range for this air point
        start_idx, end_idx = skin_index_ranges[i]
        
        if start_idx == end_idx:
            # No skin voxels in cube
            hotspot_scores[i] = 0.0
            continue
        
        # Get E-field at skin voxels for this air point
        E_skin = E_skin_all[:, start_idx:end_idx, :]  # (n_dirs, n_skin, 3)
        
        # Combine with weights: E_combined = sum_d(w_d * E_d)
        E_combined = np.sum(weights[:, np.newaxis, np.newaxis] * E_skin, axis=0)  # (n_skin, 3)
        
        # Compute |E_combined|² and mean
        E_combined_sq = np.sum(np.abs(E_combined) ** 2, axis=1)  # (n_skin,)
        hotspot_scores[i] = float(np.mean(E_combined_sq))
    
    return hotspot_scores


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
        low_memory: If True, use streaming mode (read from disk, slower but works on low-RAM).
            If False, use in-memory cache (fast but needs lots of RAM).
            If None (default), auto-detect based on available RAM.
        slab_cache_gb: Size of slab LRU cache in GB for streaming mode (default 2.0).
            Larger cache = faster but uses more RAM. Only used when low_memory=True.

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
        )
    else:
        # Legacy skin-based search
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

    # Return single focus if top_n=1, else return all
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
) -> Tuple[np.ndarray, np.ndarray, dict]:
    """Air-based focus search - physically correct MaMIMO beamforming model."""
    valid_air_indices, ax_x, ax_y, ax_z, skin_mask = find_valid_air_focus_points(
        input_h5_path=str(input_h5_path),
        cube_size_mm=cube_size_mm,
        skin_keywords=skin_keywords,
        shell_size_mm=shell_size_mm,
    )

    n_valid = len(valid_air_indices)
    logging.getLogger("progress").info(f"Found {n_valid:,} valid air focus points near skin")

    if random_seed is not None:
        np.random.seed(random_seed)

    # Support coverage percentage: if n_samples <= 1.0, treat as fraction of valid points
    if n_samples <= 1.0:
        n_to_sample = max(100, int(n_valid * n_samples))  # At least 100 samples
        logging.getLogger("progress").info(f"Coverage mode: {n_samples * 100:.1f}% → {n_to_sample:,} samples")
    else:
        n_to_sample = min(int(n_samples), n_valid)

    sampled_idx = np.random.choice(n_valid, size=n_to_sample, replace=False)
    sampled_air_indices = valid_air_indices[sampled_idx]

    logging.getLogger("progress").info(f"Sampling {n_to_sample:,} air points for hotspot scoring")

    # Pre-load all E-fields into cache to avoid memory thrashing
    # In low-memory mode, this uses optimized slab-based streaming instead of pre-loading
    t_cache_start = time.perf_counter()
    field_cache = FieldCache(h5_paths, field_type="E", low_memory=low_memory, slab_cache_gb=slab_cache_gb)

    # Score ALL sampled points using batched approach (much more efficient I/O pattern)
    t_scoring_start = time.perf_counter()
    hotspot_scores = compute_all_hotspot_scores_batched(
        h5_paths=h5_paths,
        sampled_air_indices=sampled_air_indices,
        skin_mask=skin_mask,
        axis_x=ax_x,
        axis_y=ax_y,
        axis_z=ax_z,
        cube_size_mm=cube_size_mm,
        field_cache=field_cache,
    )
    
    t_scoring_end = time.perf_counter()

    # Log scoring statistics
    n_with_skin = np.sum(hotspot_scores > 0)
    n_no_skin = np.sum(hotspot_scores == 0)
    logger = logging.getLogger("progress")
    logger.info(f"  Scoring stats: {n_with_skin}/{len(hotspot_scores)} points had skin in cube, {n_no_skin} had no skin (score=0)")
    logger.info(f"  [timing] Scoring completed in {t_scoring_end - t_scoring_start:.1f}s ({(t_scoring_end - t_scoring_start) / n_to_sample * 1000:.1f}ms/sample)")
    
    # Log cache statistics for streaming mode
    cache_stats = field_cache.get_cache_stats()
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

    # Select candidates with diversity constraint
    # Convert distance from mm to voxels (approximate using mean voxel spacing)
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

    # Compute phases for ALL selected candidates using the still-alive cache
    # This avoids expensive re-reads later when we need phases for each candidate
    all_candidate_phases = []
    all_candidate_weights = []
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

    # Use top-1 for backward compatibility
    top_focus_idx = top_air_indices[0]
    phases = all_candidate_phases[0]
    weights = all_candidate_weights[0]

    # Get physical coordinates of focus point
    ix, iy, iz = top_focus_idx
    focus_coords_m = np.array(
        [
            float(ax_x[min(ix, len(ax_x) - 1)]),
            float(ax_y[min(iy, len(ax_y) - 1)]),
            float(ax_z[min(iz, len(ax_z) - 1)]),
        ]
    )

    # Prepare all scores data for export
    all_scores_data = []
    for i, (idx, score) in enumerate(zip(sampled_air_indices, hotspot_scores)):
        x_mm = float(ax_x[min(idx[0], len(ax_x) - 1)]) * 1000
        y_mm = float(ax_y[min(idx[1], len(ax_y) - 1)]) * 1000
        z_mm = float(ax_z[min(idx[2], len(ax_z) - 1)]) * 1000
        all_scores_data.append(
            {
                "idx": i,
                "voxel_x": int(idx[0]),
                "voxel_y": int(idx[1]),
                "voxel_z": int(idx[2]),
                "x_mm": x_mm,
                "y_mm": y_mm,
                "z_mm": z_mm,
                "proxy_score": float(score),
            }
        )

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
        "all_candidate_phases": all_candidate_phases,  # Pre-computed phases for all candidates
        "all_candidate_weights": all_candidate_weights,  # Pre-computed weights for all candidates
        "cube_size_mm": cube_size_mm,
        "random_seed": random_seed,
        "all_scores_data": all_scores_data,  # For CSV export
        "cache_stats": cache_stats,  # Slab cache statistics (streaming mode only)
        "streaming_mode": field_cache.streaming_mode,
    }
    
    # Cleanup: close file handles in streaming mode
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

    # Filter to top percentile
    valid_mask = hotspot_scores > 0
    if not np.any(valid_mask):
        raise ValueError("No valid scores")

    threshold = np.percentile(hotspot_scores[valid_mask], percentile)
    top_mask = hotspot_scores >= threshold
    n_in_percentile = np.sum(top_mask)
    logger.info(f"  Selection: {n_in_percentile} points in top {100 - percentile:.0f}% (threshold={threshold:.4e})")

    # Get indices sorted by score (descending)
    top_indices = np.where(top_mask)[0]
    sorted_order = np.argsort(hotspot_scores[top_indices])[::-1]
    top_indices = top_indices[sorted_order]

    # Greedy selection with diversity
    selected = []
    selected_positions = []

    for idx in top_indices:
        if len(selected) >= top_n:
            break

        pos = sampled_air_indices[idx]

        # Check distance to all already selected
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
        # Fallback: just take top-N without diversity
        logger.info("  Warning: diversity constraint too strict, falling back to top-N")
        selected = top_indices[:top_n].tolist()

    selected = np.array(selected)
    logger.info(f"  Selected {len(selected)} diverse candidates from top {100 - percentile:.0f}%")

    return sampled_air_indices[selected], hotspot_scores[selected]


# --- CLI for testing ---
if __name__ == "__main__":
    import argparse
    import glob

    # Set up basic logging for CLI usage
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
    )
    logger = logging.getLogger("verbose")

    parser = argparse.ArgumentParser(description="Find worst-case focus point for auto-induced exposure")
    parser.add_argument("results_dir", help="Directory containing _Output.h5 files")
    parser.add_argument("--input-h5", required=True, help="Path to _Input.h5 for skin mask")
    parser.add_argument("--pattern", default="*_Output.h5", help="Glob pattern for output files")

    args = parser.parse_args()

    # Find all output H5 files
    h5_patterns = glob.glob(f"{args.results_dir}/**/{args.pattern}", recursive=True)
    h5_paths = sorted(h5_patterns)

    if not h5_paths:
        logger.error(f"No files matching {args.pattern} found in {args.results_dir}")
        exit(1)

    logger.info(f"\nFound {len(h5_paths)} _Output.h5 files")
    logger.info(f"Input H5: {args.input_h5}")

    # Run the full workflow
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
