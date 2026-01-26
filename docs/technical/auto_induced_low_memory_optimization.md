# Auto-Induced Pipeline Low-Memory Optimization

## Executive Summary

The auto-induced exposure pipeline scores **10,000 air focus points** to find the worst-case MRT beamforming scenario. 

| Mode | RAM Required | Time | Status |
|------|-------------|------|--------|
| High-RAM | >65 GB | ~3 minutes | ✅ Working |
| Low-RAM | <65 GB | **42+ hours** | ❌ Needs optimization |

**The goal**: Make low-RAM mode complete in a reasonable time (ideally <30 minutes).

---

## Pipeline Overview

### What the Pipeline Does

The auto-induced exposure pipeline simulates a **Massive MIMO (MaMIMO) beamforming attack** where an adversary focuses RF energy on a person's skin. The pipeline:

1. **Runs 72 FDTD simulations** (18 directions × 4 polarizations) with plane wave excitation
2. **Finds the worst-case focus point** in air near the skin where beamforming would cause maximum exposure
3. **Computes optimal phases** for each direction to maximize constructive interference at that point
4. **Evaluates the combined field** on skin to get the final exposure metric

### The Scoring Algorithm

For each candidate air focus point, we compute a "hotspot score":

```
For each air focus point r_air:
    1. Read E_z(r_air) from all 72 directions
    2. Compute MRT phases: φ_i = -arg(E_z_i(r_air))
    3. Compute weights: w_i = (1/√72) * exp(j*φ_i)
    4. Find all skin voxels in a 50mm cube around r_air (~37,000 voxels)
    5. For each skin voxel r_skin:
       - Read E(r_skin) from all 72 directions
       - Compute E_combined = Σ w_i * E_i(r_skin)
       - Compute |E_combined|²
    6. Score = mean(|E_combined|²) over all skin voxels
```

### Data Sizes

- **Grid size**: ~500 × 500 × 500 voxels
- **E-field per direction**: 500×500×500 × 3 components × 8 bytes = **~3 GB**
- **Total for 72 directions**: 72 × 3 GB = **~216 GB** (but we only have 4 directions in test = 12 GB)
- **Skin voxels per cube**: ~37,000
- **Air focus points to score**: 10,000

---

## The Memory Problem

### High-RAM Mode (Working)

When RAM > 65 GB:
1. Pre-load all E-fields into memory (~57 GB for 72 directions)
2. Simple loop: score each air point using in-memory numpy indexing
3. Time: ~3 minutes for 10,000 points

### Low-RAM Mode (Broken)

When RAM < 65 GB:
1. Cannot pre-load all fields
2. Must read from disk for each access
3. **Original naive approach**: 42+ hours (individual HDF5 point reads)
4. **Current streaming approach**: Still very slow

---

## Attempted Optimizations (All Failed)

### Attempt 1: Slab-Based LRU Cache

**Idea**: Cache z-slabs (32 z-slices at a time) in an LRU cache. Nearby skin voxels share slabs.

**Problem**: The 10,000 air focus points are randomly distributed across the entire volume. Reading E_z at 10,000 scattered points requires reading almost ALL z-slabs, defeating the cache.

**Result**: Still slow (~5.7 minutes per file just for Step 1)

### Attempt 2: Z-Slice Iteration

**Idea**: Instead of reading individual points, iterate through z-slices and extract needed points.

**Implementation**:
```python
for z_val in unique_z:
    z_slice = dataset[:, :, z_val, :]  # Read entire z-slice (~2 MB)
    data = z_slice[ix_at_z, iy_at_z, :]  # Extract points
```

**Result**: Step 1 improved from 5.7 min/file to ~16 sec/file. But Step 2 still hangs.

### Attempt 3: Chunked Processing with Deduplication

**Idea**: Process air points in chunks of 100. Nearby points share skin voxels, so deduplicate before reading.

**Problem**: Even with deduplication, each chunk has ~3.3 million unique skin voxels (only ~10% overlap). Reading 3.3M voxels × 72 directions × 100 chunks = massive I/O.

**Result**: Step 2 hangs at "Processing chunks: 0%"

---

## Current Code Structure

### Key Files

1. **`goliat/extraction/focus_optimizer.py`** - Main scoring logic
   - `FieldCache` class: Handles memory vs streaming mode
   - `compute_hotspot_score_at_air_point()`: Scores one air point
   - `compute_all_hotspot_scores_chunked()`: Chunked streaming approach
   - `_find_focus_air_based()`: Main entry point

2. **`goliat/extraction/field_reader.py`** - HDF5 reading utilities
   - `read_field_at_indices()`: Read E-field at specific voxel indices

3. **`goliat/utils/skin_voxel_utils.py`** - Skin mask extraction
   - `find_valid_air_focus_points()`: Find air points near skin

### Current Flow (Low-RAM Mode)

```
_find_focus_air_based()
  ├── find_valid_air_focus_points()     # Find 37M valid air points
  ├── Sample 10,000 air points
  ├── FieldCache(streaming_mode=True)   # Initialize slab cache
  └── compute_all_hotspot_scores_chunked()
        ├── Step 1: Read E_z at all 10K focus points
        │   └── For each of 72 files:
        │       └── _read_at_indices_direct()  # Z-slice iteration
        └── Step 2: Process in chunks of 100
            └── For each chunk:
                ├── Find ~3.3M unique skin voxels
                ├── Read E at all skin voxels from 72 files  # BOTTLENECK
                └── Compute scores for 100 air points
```

---

## The Fundamental Bottleneck

### The Math

For Step 2 (chunk processing):
- Chunk size: 100 air points
- Skin voxels per air point: ~37,000
- Unique skin voxels per chunk (after dedup): ~3,300,000
- Z-range of skin voxels: ~500 z-slices (entire phantom height)
- Files: 72 directions (or 4 in test)

**I/O per chunk**:
- 3.3M voxels spread across 500 z-slices
- Must read ~500 z-slices per file
- 500 z-slices × 72 files × 3 components = 108,000 z-slice reads per chunk
- 100 chunks = **10.8 million z-slice reads total**

Each z-slice read is ~2 MB and takes ~10-50 ms. Total: **30-150 hours**.

### Why High-RAM Mode is Fast

In high-RAM mode, all fields are pre-loaded as numpy arrays. Reading 3.3M voxels is just:
```python
result = data[ix, iy, iz]  # Vectorized numpy indexing, ~10 ms
```

In streaming mode, we must read from HDF5:
```python
for z_val in unique_z:  # 500 iterations
    z_slice = dataset[:, :, z_val, :]  # HDF5 read, ~10-50 ms each
```

---

## Potential Solutions (Not Yet Implemented)

### Option 1: Reduce Problem Size

- **Reduce `n_samples`**: Score 1,000 points instead of 10,000
- **Reduce `cube_size_mm`**: Use 25mm cubes instead of 50mm (fewer skin voxels)
- **Subsample skin voxels**: Use every 10th skin voxel for scoring

**Pros**: Easy to implement, guaranteed to work
**Cons**: May miss the true worst-case focus point

### Option 2: Spatial Sorting

Sort air points by location so nearby points are in the same chunk. This maximizes skin voxel overlap between points in a chunk.

**Current**: Random sampling → ~10% overlap
**With sorting**: Spatial clustering → potentially 50-80% overlap

**Implementation**:
```python
# Sort air points by z, then y, then x
sorted_idx = np.lexsort((air_indices[:, 0], air_indices[:, 1], air_indices[:, 2]))
sampled_air_indices = air_indices[sorted_idx]
```

### Option 3: Two-Phase Approach

**Phase 1**: Coarse scoring with subsampled skin voxels
- Use every 10th skin voxel
- Score all 10,000 air points quickly
- Identify top 100 candidates

**Phase 2**: Fine scoring with all skin voxels
- Only score the top 100 candidates
- Use full skin voxel set

### Option 4: Direction-Major Processing

Instead of processing by air point, process by direction:

```
For each direction i (72 total):
    Load entire E-field into memory (3 GB)
    For each air point:
        Read E_z at focus point
        Read E at all skin voxels in cube
        Accumulate weighted contribution
    Free memory
```

**Pros**: Only 3 GB memory needed at a time
**Cons**: Still need to read 72 × 3 GB = 216 GB total, but sequentially

### Option 5: Pre-compute Skin Voxel Indices

The skin mask is the same for all air points. Pre-compute which skin voxels are in each air point's cube:

```python
# Pre-compute once
air_to_skin_map = {}
for i, air_idx in enumerate(sampled_air_indices):
    skin_indices = find_skin_in_cube(air_idx, skin_mask, cube_size)
    air_to_skin_map[i] = skin_indices

# Then during scoring, just look up the indices
```

This doesn't reduce I/O but reduces CPU overhead.

### Option 6: Memory-Mapped Files

Use numpy memory-mapped arrays instead of HDF5:

```python
# Convert HDF5 to numpy memmap once
E_field = np.memmap('E_field.dat', dtype=np.complex64, mode='r', shape=(500, 500, 500, 3))

# Then access like regular numpy array
E_at_indices = E_field[ix, iy, iz, :]
```

**Pros**: OS handles caching efficiently
**Cons**: Requires converting HDF5 to memmap format

---

## Code Snippets for Reference

### Current Streaming Read (Z-Slice Iteration)

```python
def _read_at_indices_direct(self, h5_path: str, indices: np.ndarray) -> np.ndarray:
    """Read points by iterating through z-slices."""
    result = np.zeros((len(indices), 3), dtype=np.complex64)
    
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
            
            # Read single z-slice (contiguous, ~2 MB)
            z_slice = dataset[:, :, int(z_val), :]
            
            # Extract points from this slice
            ix_at_z = ix[mask]
            iy_at_z = iy[mask]
            data = z_slice[ix_at_z, iy_at_z, :]
            result[point_indices, comp] = data[:, 0] + 1j * data[:, 1]
    
    return result
```

### Chunked Processing Loop

```python
def compute_all_hotspot_scores_chunked(...):
    # Step 1: Read E_z at ALL focus points
    for dir_idx, h5_path in enumerate(h5_paths):
        E_focus = field_cache.read_at_indices(h5_str, all_focus_indices)
        E_z_at_focus_all[dir_idx, :] = E_focus[:, 2]
    
    # Step 2: Process in chunks
    for chunk_idx in range(n_chunks):
        chunk_air_indices = sampled_air_indices[chunk_start:chunk_end]
        
        # Find all skin voxels for this chunk and deduplicate
        all_skin_indices_list = []
        for air_idx in chunk_air_indices:
            skin_indices = find_skin_in_cube(air_idx, skin_mask)
            all_skin_indices_list.append(skin_indices)
        
        # Deduplicate
        all_skin_concat = np.vstack(all_skin_indices_list)
        unique_skin_indices = np.unique(all_skin_concat, axis=0)
        
        # Read E-field at unique skin voxels from all directions
        for dir_idx, h5_path in enumerate(h5_paths):
            E_skin = field_cache.read_at_indices(h5_str, unique_skin_indices)
            E_skin_unique[dir_idx, :, :] = E_skin
        
        # Compute scores for each air point in chunk
        for air_idx in chunk_air_indices:
            # ... compute score using E_skin_unique
```

---

## Test Environment

- **High-RAM machine**: 83 GB available, 72 directions
- **Low-RAM machine**: 38 GB available, 4 directions (test subset)
- **Grid size**: ~500 × 500 × 500
- **E-field per direction**: ~3 GB (complex64, 3 components)
- **Skin voxels**: ~37,000 per 50mm cube
- **Air focus points**: 10,000 sampled from 37 million valid

---

## Key Insight

The fundamental issue is that **skin voxels span the entire z-range of the phantom**. Even a small 50mm cube around an air focus point contains skin voxels at many different z-levels (because the skin wraps around the entire body).

This means:
- Reading skin voxels for ONE air point requires reading ~50-100 z-slices
- Reading skin voxels for 100 air points (one chunk) requires reading ~500 z-slices (almost all of them)
- There's no spatial locality to exploit at the z-slice level

**Possible insight**: Maybe we should process by z-slice instead of by air point:
1. Read one z-slice from all 72 files
2. For all air points whose cubes include this z-slice, accumulate the contribution
3. Repeat for all z-slices

This would read each z-slice exactly once (500 × 72 × 3 = 108,000 reads total) instead of potentially millions of times.

---

## Files to Read

1. `goliat/extraction/focus_optimizer.py` - Main logic (1400 lines)
2. `goliat/extraction/field_reader.py` - HDF5 reading utilities
3. `goliat/utils/skin_voxel_utils.py` - Skin mask extraction
4. `goliat/extraction/auto_induced_processor.py` - Higher-level orchestration

---

## Summary of What Works

✅ High-RAM mode: Pre-load all fields, simple loop, ~3 minutes
✅ Step 1 of low-RAM: Z-slice iteration for reading E_z at focus points, ~1 minute
❌ Step 2 of low-RAM: Reading E at skin voxels, still extremely slow

The next AI should focus on **Step 2** - finding a way to efficiently read E-field values at ~3.3 million skin voxels per chunk without loading entire fields into memory.
