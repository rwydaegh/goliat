"""Field data caching for auto-induced exposure processing.

Provides memory-aware caching for E/H field data loaded from H5 files:
- SlabLRUCache: z-slab LRU cache for streaming/low-memory mode.
- FieldCache: high-level cache with automatic mode selection (memory vs streaming).
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

from .field_reader import find_overall_field_group, get_field_path


def _get_available_memory_gb() -> float:
    """Get available system memory in GB.

    Returns:
        Available memory in GB, or -1 if detection fails.
    """
    try:
        import psutil

        return psutil.virtual_memory().available / (1024**3)
    except ImportError:
        pass

    try:
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

    return -1.0


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
            self._cache.move_to_end(key)
            self._hits += 1
            return self._cache[key]

        self._misses += 1
        dataset = h5_file[f"{field_path}/comp{comp}"]
        shape = dataset.shape  # (Nx, Ny, Nz, 2)

        z_start = z_slab_idx * self.slab_thickness
        z_end = min(z_start + self.slab_thickness, shape[2])

        slab_data = dataset[:, :, z_start:z_end, :]
        slab_complex = (slab_data[..., 0] + 1j * slab_data[..., 1]).astype(np.complex64)

        slab_bytes = slab_complex.nbytes
        while self.current_size_bytes + slab_bytes > self.max_size_bytes and self._cache:
            _, evicted = self._cache.popitem(last=False)
            self.current_size_bytes -= evicted.nbytes

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

    MIN_HEADROOM_GB = 8.0
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

        self._slab_cache: Optional[SlabLRUCache] = None
        self._open_files: Dict[str, h5py.File] = {}
        self._field_paths: Dict[str, str] = {}

        logger = logging.getLogger("progress")

        available_gb = _get_available_memory_gb()
        estimated_gb = _estimate_cache_size_gb(h5_paths)
        has_enough_ram = available_gb < 0 or estimated_gb <= available_gb - self.MIN_HEADROOM_GB

        if low_memory is None:
            self.streaming_mode = not has_enough_ram
        else:
            self.streaming_mode = low_memory

        if available_gb > 0:
            logger.info(f"  Memory check: {estimated_gb:.1f} GB needed, {available_gb:.1f} GB available")

        if self.streaming_mode:
            logger.info(
                f"  Using OPTIMIZED STREAMING mode with {slab_cache_gb:.1f} GB slab cache\n"
                f"  This is ~100x faster than naive streaming. "
                f"For fastest processing, use a machine with >{estimated_gb + self.MIN_HEADROOM_GB:.0f} GB RAM."
            )
            self._init_streaming_mode()
        else:
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
        self._slab_cache = SlabLRUCache(max_size_gb=self.slab_cache_gb, slab_thickness=32)

        for h5_path in self.h5_paths:
            f = h5py.File(h5_path, "r")
            self._open_files[h5_path] = f

            fg_path = find_overall_field_group(f)
            if fg_path is None:
                raise ValueError(f"No 'Overall Field' found in {h5_path}")

            field_path = get_field_path(fg_path, self.field_type)
            self._field_paths[h5_path] = field_path

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
                dataset = f[f"{field_path}/comp0"]
                self.shapes[h5_path] = dataset.shape[:3]

    def _load_field(self, h5_path: str):
        """Load a single field file into the cache."""
        with h5py.File(h5_path, "r") as f:
            fg_path = find_overall_field_group(f)
            if fg_path is None:
                raise ValueError(f"No 'Overall Field' found in {h5_path}")

            field_path = get_field_path(fg_path, self.field_type)

            components = []
            for comp in range(3):
                dataset = f[f"{field_path}/comp{comp}"]
                data = dataset[:]
                complex_data = data[..., 0] + 1j * data[..., 1]
                components.append(complex_data)
                if comp == 0:
                    self.shapes[h5_path] = dataset.shape[:3]

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

            ix = np.minimum(indices[:, 0], shape[0] - 1)
            iy = np.minimum(indices[:, 1], shape[1] - 1)
            iz = np.minimum(indices[:, 2], shape[2] - 1)

            result[:, comp] = data[ix, iy, iz]

        return result

    def _read_at_indices_streaming_optimized(self, h5_path: str, indices: np.ndarray) -> np.ndarray:
        """Route to direct reads for scattered points, slab cache for clustered points."""
        result = np.zeros((len(indices), 3), dtype=np.complex64)
        n_points = len(indices)

        if n_points == 0:
            return result

        assert self._slab_cache is not None
        slab_thickness = self._slab_cache.slab_thickness

        sample_iz = np.minimum(indices[:, 2], self.shapes[h5_path][2] - 1)
        unique_slabs_needed = len(np.unique(sample_iz // slab_thickness))
        total_slabs = (self.shapes[h5_path][2] + slab_thickness - 1) // slab_thickness

        use_direct_reads = n_points < 1000 or unique_slabs_needed > total_slabs * 0.5

        if use_direct_reads:
            return self._read_at_indices_direct(h5_path, indices)
        else:
            return self._read_at_indices_slab_cached(h5_path, indices)

    def _read_at_indices_direct(self, h5_path: str, indices: np.ndarray) -> np.ndarray:
        """Read points by iterating z-slices (memory efficient, reasonably fast)."""
        result = np.zeros((len(indices), 3), dtype=np.complex64)

        if len(indices) == 0:
            return result

        f = self._open_files[h5_path]
        field_path = self._field_paths[h5_path]

        for comp in range(3):
            dataset = f[f"{field_path}/comp{comp}"]
            shape = dataset.shape[:3]

            ix = np.minimum(indices[:, 0], shape[0] - 1)
            iy = np.minimum(indices[:, 1], shape[1] - 1)
            iz = np.minimum(indices[:, 2], shape[2] - 1)

            unique_z = np.unique(iz)

            for z_val in unique_z:
                mask = iz == z_val
                point_indices = np.where(mask)[0]

                z_slice = dataset[:, :, int(z_val), :]  # (Nx, Ny, 2)

                ix_at_z = ix[mask]
                iy_at_z = iy[mask]
                data = z_slice[ix_at_z, iy_at_z, :]  # (n_points_at_z, 2)
                result[point_indices, comp] = data[:, 0] + 1j * data[:, 1]

        return result

    def _read_at_indices_slab_cached(self, h5_path: str, indices: np.ndarray) -> np.ndarray:
        """Read using slab-based LRU cache (for spatially clustered points)."""
        result = np.zeros((len(indices), 3), dtype=np.complex64)

        if len(indices) == 0:
            return result

        f = self._open_files[h5_path]
        field_path = self._field_paths[h5_path]
        assert self._slab_cache is not None
        slab_thickness = self._slab_cache.slab_thickness

        for comp in range(3):
            dataset = f[f"{field_path}/comp{comp}"]
            shape = dataset.shape[:3]

            ix = np.minimum(indices[:, 0], shape[0] - 1)
            iy = np.minimum(indices[:, 1], shape[1] - 1)
            iz = np.minimum(indices[:, 2], shape[2] - 1)

            z_slab_indices = iz // slab_thickness
            unique_slabs = np.unique(z_slab_indices)

            for z_slab_idx in unique_slabs:
                slab = self._slab_cache.get_slab(
                    h5_file=f,
                    h5_path=h5_path,
                    field_path=field_path,
                    comp=comp,
                    z_slab_idx=int(z_slab_idx),
                )

                mask = z_slab_indices == z_slab_idx
                point_indices = np.where(mask)[0]

                z_local = iz[mask] - (z_slab_idx * slab_thickness)

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
