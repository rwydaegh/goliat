# Auto-Induced Exposure: Air-Based Focus Search Implementation Plan

**Author**: GOLIAT Development Team  
**Date**: January 2026  
**Status**: Implementation Ready  
**Version**: 2.0 - Air-Based Search Algorithm

---

## Executive Summary

This document provides a comprehensive implementation plan for upgrading the auto-induced exposure feature in GOLIAT. The current implementation searches for worst-case focus points **on skin voxels**, which is physically incorrect. The new implementation will search for focus points **in air near the body surface**, which accurately represents how MaMIMO (Massive MIMO) base station beamforming actually works in the real world.

### Key Changes

| Aspect | Current (v1.0) | New (v2.0) |
|--------|----------------|------------|
| **Focus search location** | On skin voxels | In air near body surface |
| **Physical model** | Beam focuses on body | Beam focuses in air, illuminates body |
| **Scoring metric** | `Σ\|E_z,i(r)\|` at single point | `mean(\|E_combined\|²)` over skin hotspot |
| **Search space** | ~88k skin voxels | ~100 sampled air points (from ~500k-1M valid) |
| **Configuration** | `top_n`, `cube_size_mm`, `search_metric` | + `search.mode`, `n_samples`, `min_skin_volume_fraction`, `random_seed` |

### Impact

- **More accurate**: Physically correct representation of MaMIMO beamforming
- **Better SAPD estimates**: Accounts for beam-body coupling, not just field strength at a point
- **Configurable**: Legacy mode available for comparison
- **Efficient**: Random subsampling keeps computation tractable

---

## Table of Contents

1. [Background & Motivation](#1-background--motivation)
2. [Technical Architecture](#2-technical-architecture)
3. [Algorithm Design](#3-algorithm-design)
4. [Implementation Details](#4-implementation-details)
5. [Configuration Changes](#5-configuration-changes)
6. [Testing & Validation](#6-testing--validation)
7. [Migration Guide](#7-migration-guide)
8. [Appendices](#8-appendices)

---

## 1. Background & Motivation

### 1.1 Current Implementation Problems

The existing auto-induced exposure feature (introduced in GOLIAT v1.0) searches for worst-case focus points directly on skin voxels. While computationally efficient, this approach has several fundamental issues:

#### Physical Incorrectness

**Current approach**: Focus point searched ON skin voxels
- Assumes MaMIMO base station can "focus" electromagnetic fields directly onto tissue
- Ignores that EM waves propagate through air before reaching the body
- Does not model the actual beam-body coupling mechanism

**Reality**: MaMIMO focuses in free space (air)
- Base station array creates a focused beam in air near the body
- The beam then illuminates the skin surface
- Body loading and coupling affect how much power is actually absorbed

#### Scoring Limitations

**Current metric**: `score = Σ|E_z,i(r)|` at a single voxel
- Only considers field strength at one point
- Doesn't account for spatial extent of the hotspot
- Ignores that SAPD is averaged over 4 cm² (ICNIRP standard)

**What we need**: Hotspot-aware scoring
- Evaluate mean power density over nearby skin surface
- Account for beam width and skin illumination pattern
- Better predictor of actual SAPD values

### 1.2 New Physical Model

The new implementation models the physical reality of MaMIMO beamforming:

```
┌──────────────────────────────────────────────────────────────┐
│ MaMIMO Base Station Array                                    │
│ (N antenna elements with adaptive phases)                    │
└──────────────────────────────────────────────────────────────┘
                         │
                         │ Transmit with phases φᵢ
                         ▼
┌──────────────────────────────────────────────────────────────┐
│ FOCUS POINT IN AIR (r₀)                                      │
│ - Maximum constructive interference                          │
│ - Phases chosen: φᵢ = -arg(E_z,i(r₀))                        │
│ - Beam width determined by array geometry                    │
└──────────────────────────────────────────────────────────────┘
                         │
                         │ Beam propagates and illuminates
                         ▼
┌──────────────────────────────────────────────────────────────┐
│ SKIN SURFACE HOTSPOT                                         │
│ - Spatially distributed power absorption                     │
│ - SAPD averaged over 4 cm² (IEC 62209-3)                    │
│ - Depends on incident angle, beam width, skin curvature     │
└──────────────────────────────────────────────────────────────┘
```

**Key insight**: The worst-case SAPD does NOT necessarily occur where the beam is focused, but rather where the focused beam creates the strongest hotspot on the skin surface.

### 1.3 Why This Matters

1. **Regulatory Compliance**: IEC/ICNIRP standards define exposure limits for MaMIMO
2. **Accurate Assessment**: Must predict worst-case exposure correctly
3. **Scientific Rigor**: Model should match physical reality
4. **Publication Quality**: Results defensible in peer review

---

## 2. Technical Architecture

### 2.1 GOLIAT System Overview

The auto-induced exposure feature integrates into GOLIAT's far-field study workflow.

#### Key Components

**FarFieldStudy** (`goliat/studies/far_field_study.py`)
- Orchestrates the entire far-field workflow  
- After all (phantom, freq) simulations complete, calls `_run_auto_induced_for_phantom_freq()`
- Manages project files and result caching

**AutoInducedProcessor** (`goliat/extraction/auto_induced_processor.py`)
- Entry point for auto-induced analysis
- Workflow: Focus Search → Field Combination → SAPD Extraction  
- Handles top-N candidates, logging, and result aggregation

**FocusOptimizer** (`goliat/extraction/focus_optimizer.py`) ⭐ **PRIMARY MODIFICATION TARGET**
- Currently: Searches skin voxels for max `Σ|E_z,i(r)|`
- **New**: Searches air voxels near body for max hotspot score
- Computes MRT phases for optimal constructive interference

**FieldCombiner** (`goliat/extraction/field_combiner.py`)
- Combines weighted E/H fields from multiple `_Output.h5` files
- Uses sliced extraction (cube around focus) for efficiency
- ✓ No changes needed (already supports arbitrary focus points)

**SkinVoxelUtils** (`goliat/utils/skin_voxel_utils.py`) ⭐ **NEEDS NEW FUNCTION**
- Currently: Extracts skin voxels from `_Input.h5`
- **New**: Add `extract_air_voxels()` to identify background voxels

### 2.2 File Structure

Files to modify or create:

```
goliat/
├── extraction/
│   ├── focus_optimizer.py          ⭐ PRIMARY MODIFICATIONS
│   │   └── NEW: find_valid_air_focus_points()
│   │   └── NEW: compute_hotspot_score_at_air_point()
│   │   └── MODIFY: find_focus_and_compute_weights()
│   │
│   ├── auto_induced_processor.py   ⭐ MINOR UPDATE
│   │   └── MODIFY: _find_focus_candidates()
│   │
│   ├── field_combiner.py            ✓ NO CHANGES
│   └── field_reader.py              ✓ NO CHANGES
│
├── utils/
│   └── skin_voxel_utils.py         ⭐ NEW FUNCTION
│       └── NEW: extract_air_voxels()
│
├── config/defaults/
│   └── far_field_config.json       ⭐ NEW CONFIG SECTION
│
└── docs/
    ├── developer_guide/
    │   └── configuration.md          ⭐ UPDATE DOCUMENTATION
    └── technical/
        └── auto_induced_air_search_implementation_plan.md  📄 THIS FILE
```

---

## 3. Algorithm Design

### 3.1 Air Voxel Identification

**Goal**: Identify which voxels in the simulation grid are air/background (not tissue).

**Method**: In `_Input.h5`, voxels are mapped to tissues via UUIDs. Air voxels are those with **no UUID mapping**.

```python
def extract_air_voxels(input_h5_path: str) -> Tuple[np.ndarray, ...]:
    """Extract air/background voxel mask from _Input.h5.
    
    Air voxels = voxels whose ID has no UUID mapping in AllMaterialMaps.
    """
    with h5py.File(input_h5_path, "r") as f:
        # Build UUID → material_name mapping
        uuid_to_name = _build_uuid_material_map(f)
        
        # Find mesh with voxel data
        for mesh_key in f["Meshes"].keys():
            mesh = f[f"Meshes/{mesh_key}"]
            if "voxels" not in mesh:
                continue
                
            voxels = mesh["voxels"][:]
            id_map = mesh["id_map"][:]
            axis_x = mesh["axis_x"][:]
            axis_y = mesh["axis_y"][:]
            axis_z = mesh["axis_z"][:]
            
            # Map voxel IDs → tissue names
            voxel_id_to_name = _build_voxel_id_map(id_map, uuid_to_name)
            
            # Find unmapped IDs (= air/background)
            unique_ids = np.unique(voxels)
            air_ids = [vid for vid in unique_ids if vid not in voxel_id_to_name]
            
            # Create air mask
            air_mask = np.isin(voxels, air_ids)
            
            return air_mask, axis_x, axis_y, axis_z, voxel_id_to_name
```

**Integration**: Add to `goliat/utils/skin_voxel_utils.py` alongside existing `extract_skin_voxels()`.

### 3.2 Valid Air Focus Point Selection

**Goal**: From all air voxels, find those that are **near the body surface** (valid focus candidates).

**Criterion**: An air voxel is valid if it has ≥ threshold skin voxels within a surrounding cube.

```python
def find_valid_air_focus_points(
    input_h5_path: str,
    cube_size_mm: float = 50.0,
    min_skin_volume_fraction: float = 0.05,
    skin_keywords: Optional[Sequence[str]] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """Find air voxels that are valid focus point candidates.
    
    Args:
        input_h5_path: Path to _Input.h5.
        cube_size_mm: Size of cube for validity check (mm).
        min_skin_volume_fraction: Min fraction of cube that must be skin.
        skin_keywords: Keywords to match skin tissues.
        
    Returns:
        valid_air_indices: (N_valid, 3) array of [ix, iy, iz]
        skin_counts: (N_valid,) array of skin voxel counts
    """
    # Load voxel masks
    air_mask, ax_x, ax_y, ax_z, _ = extract_air_voxels(input_h5_path)
    skin_mask, _, _, _, _ = extract_skin_voxels(input_h5_path, skin_keywords)
    
    # Get voxel spacing
    dx = np.mean(np.diff(ax_x))
    dy = np.mean(np.diff(ax_y))
    dz = np.mean(np.diff(ax_z))
    
    # Cube half-width in voxels
    half_nx = int(np.ceil((cube_size_mm / 1000.0) / (2 * dx)))
    half_ny = int(np.ceil((cube_size_mm / 1000.0) / (2 * dy)))
    half_nz = int(np.ceil((cube_size_mm / 1000.0) / (2 * dz)))
    
    # Cube volume
    cube_volume_voxels = (2 * half_nx + 1) * (2 * half_ny + 1) * (2 * half_nz + 1)
    min_skin_voxels = int(cube_volume_voxels * min_skin_volume_fraction)
    
    # Get all air voxel indices
    air_indices = np.argwhere(air_mask)  # (N_air, 3)
    
    valid_indices = []
    skin_counts = []
    
    for idx in tqdm(air_indices, desc="Finding valid air points"):
        ix, iy, iz = idx
        
        # Define cube bounds
        ix_min = max(0, ix - half_nx)
        ix_max = min(air_mask.shape[0], ix + half_nx + 1)
        iy_min = max(0, iy - half_ny)
        iy_max = min(air_mask.shape[1], iy + half_ny + 1)
        iz_min = max(0, iz - half_nz)
        iz_max = min(air_mask.shape[2], iz + half_nz + 1)
        
        # Count skin voxels in cube
        skin_cube = skin_mask[ix_min:ix_max, iy_min:iy_max, iz_min:iz_max]
        n_skin = np.sum(skin_cube)
        
        if n_skin >= min_skin_voxels:
            valid_indices.append(idx)
            skin_counts.append(n_skin)
    
    return np.array(valid_indices), np.array(skin_counts)
```

**Optimization**: Could use scipy.ndimage.convolve for faster neighbor counting, but loop is clearer.

### 3.3 Random Subsampling

**Goal**: Reduce ~500k-1M valid air points to ~100 samples for tractable hotspot scoring.

```python
def subsample_air_points(
    valid_air_indices: np.ndarray,
    n_samples: int = 100,
    random_seed: Optional[int] = None,
) -> np.ndarray:
    """Randomly subsample valid air focus points.
    
    Args:
        valid_air_indices: (N_valid, 3) array of air voxel indices.
        n_samples: Number of samples to draw.
        random_seed: Random seed for reproducibility (None = no seed).
        
    Returns:
        Subsampled indices (min(n_samples, N_valid), 3).
    """
    if random_seed is not None:
        np.random.seed(random_seed)
    
    n_valid = len(valid_air_indices)
    n_samples = min(n_samples, n_valid)
    
    sampled_idx = np.random.choice(n_valid, size=n_samples, replace=False)
    return valid_air_indices[sampled_idx]
```

### 3.4 Hotspot Scoring

**Goal**: For each sampled air point, compute a score that predicts SAPD.

**Key Insight**: SAPD is proportional to mean(|E_combined|²) over skin surface.

Algorithm pseudocode:

```
FOR each sampled air point r₀:
    1. Read E_z,i(r₀) from all 12 _Output.h5 files
    2. Compute MRT phases: φᵢ = -arg(E_z,i(r₀))
    3. Compute weights: wᵢ = (1/√N) × exp(jφᵢ)
    4. Find skin voxels in cube around r₀
    5. FOR each skin voxel r_skin:
           Read E_i(r_skin) from all directions
           E_combined(r_skin) = Σ wᵢ × E_i(r_skin)
       END FOR
    6. hotspot_score = mean(|E_combined|²) over all skin voxels
END FOR
```

**Performance**: For 100 samples × 100 skin voxels × 12 directions = 120k E-field reads total. Manageable.

### 3.5 Top-N Selection

**Goal**: Sort sampled points by hotspot score, return top-N for full SAPD extraction.

```python
def select_top_n_candidates(
    sampled_indices: np.ndarray,
    hotspot_scores: np.ndarray,
    top_n: int = 10,
) -> Tuple[np.ndarray, np.ndarray]:
    """Select top-N candidates by hotspot score.
    
    Args:
        sampled_indices: (N_samples, 3) air voxel indices.
        hotspot_scores: (N_samples,) hotspot scores.
        top_n: Number of top candidates to return.
        
    Returns:
        top_indices: (top_n, 3) voxel indices
        top_scores: (top_n,) hotspot scores
    """
    top_n = min(top_n, len(hotspot_scores))
    
    # Use argpartition for efficiency (O(N) instead of O(N log N))
    top_n_idx = np.argpartition(hotspot_scores, -top_n)[-top_n:]
    
    # Sort top_n by score descending
    top_n_idx = top_n_idx[np.argsort(hotspot_scores[top_n_idx])[::-1]]
    
    return sampled_indices[top_n_idx], hotspot_scores[top_n_idx]
```

---

# Section 4: Implementation Details

## 4.1 Code Changes in `skin_voxel_utils.py`

**File**: `goliat/utils/skin_voxel_utils.py`

### Add `extract_air_voxels()` Function

Add this function right after `extract_skin_voxels()`:

```python
def extract_air_voxels(
    input_h5_path: str,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, Dict[int, str]]:
    """Extract air/background voxel mask from a Sim4Life _Input.h5 file.
    
    Air voxels are those whose voxel ID has no UUID mapping in AllMaterialMaps.
    This identifies external background and any unmapped regions.
    
    Args:
        input_h5_path: Path to the _Input.h5 file.
    
    Returns:
        Tuple of:
            - air_mask: Boolean array (Nx, Ny, Nz) where True = air voxel
            - axis_x: X-axis coordinates (Nx,)
            - axis_y: Y-axis coordinates (Ny,)
            - axis_z: Z-axis coordinates (Nz,)
            - tissue_map: Dict mapping voxel ID -> tissue name (for debugging)
    
    Raises:
        ValueError: If no mesh with voxel data is found.
    """
    with h5py.File(input_h5_path, "r") as f:
        # Step 1: Build UUID -> material_name mapping from AllMaterialMaps
        uuid_to_name = _build_uuid_material_map(f)
        
        # Step 2: Find mesh with voxel data and extract
        for mesh_key in f["Meshes"].keys():
            mesh = f[f"Meshes/{mesh_key}"]
            if "voxels" not in mesh:
                continue
            
            voxels = mesh["voxels"][:]
            id_map = mesh["id_map"][:]
            axis_x = mesh["axis_x"][:]
            axis_y = mesh["axis_y"][:]
            axis_z = mesh["axis_z"][:]
            
            # Step 3: Map voxel IDs to tissue names
            voxel_id_to_name = _build_voxel_id_map(id_map, uuid_to_name)
            
            # Step 4: Find air voxel IDs (those NOT in the mapping)
            unique_ids = np.unique(voxels)
            air_ids = [vid for vid in unique_ids if vid not in voxel_id_to_name]
            
            # Step 5: Create boolean mask
            air_mask = np.isin(voxels, air_ids)
            
            return air_mask, axis_x, axis_y, axis_z, voxel_id_to_name
    
    raise ValueError(f"No mesh with voxel data found in {input_h5_path}")
```

**Testing**: Add to the CLI test at the bottom of the file:

```python
if __name__ == "__main__":
    # ... existing argparse code ...
    
    parser.add_argument("--test-air", action="store_true", help="Test air voxel extraction")
    
    # ... existing extraction code ...
    
    if args.test_air:
        air_mask, ax_x, ax_y, ax_z, tissue_map = extract_air_voxels(args.input_h5)
        
        n_air = np.sum(air_mask)
        n_total = air_mask.size
        
        print("\nAir voxel extraction complete:")
        print(f"  Air voxels: {n_air:,} / {n_total:,} ({100 * n_air / n_total:.2f}%)")
        
        # Show first few air voxel coordinates
        air_coords = get_skin_voxel_coordinates(air_mask, ax_x, ax_y, ax_z)
        print("\nFirst 5 air voxel coordinates (meters):")
        for i, (x, y, z) in enumerate(air_coords[:5]):
            print(f"  [{i}]: ({x:.4f}, {y:.4f}, {z:.4f})")
```

---

## 4.2 Code Changes in `focus_optimizer.py`

**File**: `goliat/extraction/focus_optimizer.py`

### 4.2.1 Add Import

At the top of the file, update imports:

```python
from ..utils.skin_voxel_utils import (
    extract_skin_voxels, 
    get_skin_voxel_coordinates,
    extract_air_voxels,  # NEW
)
```

### 4.2.2 Add `find_valid_air_focus_points()`

Add this new function after `find_worst_case_focus_point()`:

```python
def find_valid_air_focus_points(
    input_h5_path: str,
    cube_size_mm: float = 50.0,
    min_skin_volume_fraction: float = 0.05,
    skin_keywords: Optional[Sequence[str]] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """Find air voxels that are valid focus point candidates.
    
    A valid air focus point is an air voxel with at least min_skin_volume_fraction
    of the surrounding cube filled with skin voxels. This ensures the focus point
    is near the body surface.
    
    Args:
        input_h5_path: Path to _Input.h5.
        cube_size_mm: Size of the cube (in mm) to check around each air point.
        min_skin_volume_fraction: Minimum fraction of cube volume that must be skin (0-1).
        skin_keywords: Keywords to match skin tissues (default: ["skin"]).
        
    Returns:
        Tuple of:
            - valid_air_indices: Array (N_valid, 3) of [ix, iy, iz] indices
            - skin_counts: Array (N_valid,) with count of skin voxels in cube
    """
    # Load voxel masks
    air_mask, ax_x, ax_y, ax_z, _ = extract_air_voxels(input_h5_path)
    skin_mask, _, _, _, _ = extract_skin_voxels(input_h5_path, skin_keywords)
    
    # Get voxel spacing (meters)
    dx = np.mean(np.diff(ax_x))
    dy = np.mean(np.diff(ax_y))
    dz = np.mean(np.diff(ax_z))
    
    # Cube half-width in voxels
    cube_size_m = cube_size_mm / 1000.0
    half_nx = int(np.ceil(cube_size_m / (2 * dx)))
    half_ny = int(np.ceil(cube_size_m / (2 * dy)))
    half_nz = int(np.ceil(cube_size_m / (2 * dz)))
    
    # Cube volume in voxels
    cube_volume_voxels = (2 * half_nx + 1) * (2 * half_ny + 1) * (2 * half_nz + 1)
    min_skin_voxels = int(cube_volume_voxels * min_skin_volume_fraction)
    
    print(f"Cube size: ±{half_nx}x{half_ny}x{half_nz} voxels (~{cube_size_mm}mm)")
    print(f"Min skin voxels: {min_skin_voxels} ({100*min_skin_volume_fraction:.1f}% of {cube_volume_voxels})")
    
    # Get all air voxel indices
    air_indices = np.argwhere(air_mask)  # (N_air, 3)
    print(f"Total air voxels: {len(air_indices):,}")
    
    valid_indices = []
    skin_counts = []
    
    # Check each air voxel for nearby skin
    for idx in tqdm(air_indices, desc="Finding valid air focus points"):
        ix, iy, iz = idx
        
        # Define cube bounds (clamped to grid)
        ix_min = max(0, ix - half_nx)
        ix_max = min(air_mask.shape[0], ix + half_nx + 1)
        iy_min = max(0, iy - half_ny)
        iy_max = min(air_mask.shape[1], iy + half_ny + 1)
        iz_min = max(0, iz - half_nz)
        iz_max = min(air_mask.shape[2], iz + half_nz + 1)
        
        # Count skin voxels in cube
        skin_cube = skin_mask[ix_min:ix_max, iy_min:iy_max, iz_min:iz_max]
        n_skin = np.sum(skin_cube)
        
        if n_skin >= min_skin_voxels:
            valid_indices.append(idx)
            skin_counts.append(n_skin)
    
    valid_indices = np.array(valid_indices) if valid_indices else np.empty((0, 3), dtype=int)
    skin_counts = np.array(skin_counts) if skin_counts else np.empty(0, dtype=int)
    
    print(f"Valid air focus points: {len(valid_indices):,} ({100*len(valid_indices)/len(air_indices):.2f}% of all air)")
    
    return valid_indices, skin_counts
```

### 4.2.3 Add `compute_hotspot_score_at_air_point()`

Add this function after `find_valid_air_focus_points()`:

```python
def compute_hotspot_score_at_air_point(
    h5_paths: Sequence[Union[str, Path]],
    air_focus_idx: np.ndarray,
    input_h5_path: str,
    cube_size_mm: float = 50.0,
    skin_keywords: Optional[Sequence[str]] = None,
) -> float:
    """Compute hotspot score for an air focus point.
    
    The hotspot score is the mean |E_combined|² over skin voxels in a cube
    around the air focus point, where E_combined is the field resulting from
    MRT beamforming focused at that air point.
    
    This score predicts how much SAPD would result from focusing at this point.
    
    Args:
        h5_paths: List of _Output.h5 files (one per direction/polarization).
        air_focus_idx: [ix, iy, iz] of the air focus point.
        input_h5_path: Path to _Input.h5 for skin mask.
        cube_size_mm: Size of cube around focus to evaluate (mm).
        skin_keywords: Keywords to match skin tissues.
        
    Returns:
        Hotspot score (mean |E_combined|² over skin voxels in cube).
    """
    # Step 1: Read E_z at air focus point from all directions
    focus_idx_array = air_focus_idx.reshape(1, 3)
    E_z_at_focus = []
    
    for h5_path in h5_paths:
        E_focus = read_field_at_indices(h5_path, focus_idx_array, field_type="E")
        E_z_at_focus.append(E_focus[0, 2])  # E_z component
    
    E_z_at_focus = np.array(E_z_at_focus)  # (N_directions,)
    
    # Step 2: Compute MRT phases
    phases = -np.angle(E_z_at_focus)
    N = len(phases)
    weights = (1.0 / np.sqrt(N)) * np.exp(1j * phases)
    
    # Step 3: Find skin voxels in cube around focus
    skin_mask, ax_x, ax_y, ax_z, _ = extract_skin_voxels(input_h5_path, skin_keywords)
    
    # Cube bounds (same logic as find_valid_air_focus_points)
    dx = np.mean(np.diff(ax_x))
    dy = np.mean(np.diff(ax_y))
    dz = np.mean(np.diff(ax_z))
    
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
    
    # Extract skin voxels in cube
    skin_cube = skin_mask[ix_min:ix_max, iy_min:iy_max, iz_min:iz_max]
    skin_indices_local = np.argwhere(skin_cube)
    
    # Convert to global indices
    skin_indices_global = skin_indices_local + np.array([ix_min, iy_min, iz_min])
    
    if len(skin_indices_global) == 0:
        return 0.0  # No skin in cube
    
    # Step 4: Read E-field at each skin voxel and combine
    E_combined_sq_sum = 0.0
    
    for skin_idx in skin_indices_global:
        E_skin = []
        skin_idx_array = skin_idx.reshape(1, 3)
        
        for h5_path in h5_paths:
            E = read_field_at_indices(h5_path, skin_idx_array, field_type="E")
            E_skin.append(E[0])  # (3,) vector
        
        E_skin = np.array(E_skin)  # (N_directions, 3)
        
        # Combine with weights
        E_combined = np.sum(weights[:, np.newaxis] * E_skin, axis=0)  # (3,)
        
        # Add |E_combined|² to score
        E_combined_sq_sum += np.sum(np.abs(E_combined)**2)
    
    # Step 5: Return mean
    return E_combined_sq_sum / len(skin_indices_global)
```

### 4.2.4 Modify `find_focus_and_compute_weights()`

Update this function to support both modes:

```python
def find_focus_and_compute_weights(
    h5_paths: Sequence[Union[str, Path]],
    input_h5_path: Union[str, Path],
    skin_keywords: Optional[Sequence[str]] = None,
    top_n: int = 1,
    metric: str = "E_z_magnitude",
    # NEW parameters for air-based search:
    search_mode: str = "skin",  # "air" (new) or "skin" (legacy)
    n_samples: int = 100,
    cube_size_mm: float = 50.0,
    min_skin_volume_fraction: float = 0.05,
    random_seed: Optional[int] = None,
) -> Tuple[np.ndarray, np.ndarray, dict]:
    """Complete workflow: find worst-case focus point(s) and compute weights.
    
    Args:
        h5_paths: List of _Output.h5 file paths.
        input_h5_path: Path to _Input.h5 for skin/air mask.
        skin_keywords: Keywords to match skin tissues.
        top_n: Number of candidate focus points to return.
        metric: Search metric - "E_z_magnitude" (default) or "poynting_z".
        search_mode: "air" (new, physically correct) or "skin" (legacy).
        n_samples: Number of air points to sample (only for mode="air").
        cube_size_mm: Cube size for validity check and scoring (only for mode="air").
        min_skin_volume_fraction: Min skin fraction in cube (only for mode="air").
        random_seed: Random seed for sampling (only for mode="air").
        
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
            min_skin_volume_fraction=min_skin_volume_fraction,
            random_seed=random_seed,
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
    """Legacy skin-based focus search (existing implementation)."""
    # This is the EXISTING find_worst_case_focus_point logic
    focus_voxel_indices, skin_indices, metric_sums = find_worst_case_focus_point(
        h5_paths, input_h5_path, skin_keywords, top_n=top_n, metric=metric
    )
    
    # Compute optimal phases for the top-1 focus point
    top_focus_idx = focus_voxel_indices[0]
    phases = compute_optimal_phases(h5_paths, top_focus_idx)
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
    min_skin_volume_fraction: float,
    random_seed: Optional[int],
) -> Tuple[np.ndarray, np.ndarray, dict]:
    """New air-based focus search."""
    # Step 1: Find valid air focus points
    valid_air_indices, skin_counts = find_valid_air_focus_points(
        input_h5_path=str(input_h5_path),
        cube_size_mm=cube_size_mm,
        min_skin_volume_fraction=min_skin_volume_fraction,
        skin_keywords=skin_keywords,
    )
    
    if len(valid_air_indices) == 0:
        raise ValueError("No valid air focus points found near body surface")
    
    # Step 2: Random subsample
    if random_seed is not None:
        np.random.seed(random_seed)
    
    n_samples = min(n_samples, len(valid_air_indices))
    sampled_idx = np.random.choice(len(valid_air_indices), size=n_samples, replace=False)
    sampled_air_indices = valid_air_indices[sampled_idx]
    
    print(f"Subsampled to {n_samples} air points")
    
    # Step 3: Score each sampled point
    hotspot_scores = []
    for i, air_idx in enumerate(tqdm(sampled_air_indices, desc="Scoring air focus points")):
        score = compute_hotspot_score_at_air_point(
            h5_paths=h5_paths,
            air_focus_idx=air_idx,
            input_h5_path=str(input_h5_path),
            cube_size_mm=cube_size_mm,
            skin_keywords=skin_keywords,
        )
        hotspot_scores.append(score)
    
    hotspot_scores = np.array(hotspot_scores)
    
    # Step 4: Select top-N
    top_n = min(top_n, len(hotspot_scores))
    top_n_idx = np.argpartition(hotspot_scores, -top_n)[-top_n:]
    top_n_idx = top_n_idx[np.argsort(hotspot_scores[top_n_idx])[::-1]]
    
    top_air_indices = sampled_air_indices[top_n_idx]
    top_scores = hotspot_scores[top_n_idx]
    
    # Step 5: Compute weights for top-1
    top_focus_idx = top_air_indices[0]
    phases = compute_optimal_phases(h5_paths, top_focus_idx)
    weights = compute_weights(phases)
    
    # Get physical coordinates
    air_mask, ax_x, ax_y, ax_z, _ = extract_air_voxels(str(input_h5_path))
    ix, iy, iz = top_focus_idx
    focus_coords_m = np.array([
        float(ax_x[min(ix, len(ax_x) - 1)]),
        float(ax_y[min(iy, len(ax_y) - 1)]),
        float(ax_z[min(iz, len(ax_z) - 1)]),
    ])
    
    info = {
        "search_mode": "air",
        "phases_rad": phases,
        "phases_deg": np.degrees(phases),
        "max_hotspot_score": float(top_scores[0]),
        "focus_coords_m": focus_coords_m,
        "n_directions": len(h5_paths),
        "n_valid_air_points": len(valid_air_indices),
        "n_sampled": n_samples,
        "top_n": top_n,
        "all_focus_indices": top_air_indices,
        "all_hotspot_scores": top_scores,
        "cube_size_mm": cube_size_mm,
        "min_skin_volume_fraction": min_skin_volume_fraction,
        "random_seed": random_seed,
    }
    
    if top_n == 1:
        return top_focus_idx, weights, info
    else:
        return top_air_indices, weights, info
```

---

## 4.3 Code Changes in `auto_induced_processor.py`

**File**: `goliat/extraction/auto_induced_processor.py`

Minimal changes needed - just pass new config params to `find_focus_and_compute_weights()`:

### Update `_find_focus_candidates()`

Around line 176-183, modify the function call:

```python
def _find_focus_candidates(
    self,
    h5_paths: list[Path],
    input_h5: Path,
    top_n: int,
    search_metric: str = "E_z_magnitude",
) -> list[dict]:
    """Find top-N worst-case focus candidates."""
    import time
    import numpy as np
    from .focus_optimizer import compute_optimal_phases, compute_weights

    start_time = time.monotonic()

    # Get search config
    auto_cfg = self.config["auto_induced"] or {}
    search_cfg = auto_cfg.get("search", {})
    
    # Extract search parameters
    search_mode = search_cfg.get("mode", "skin")  # NEW
    n_samples = search_cfg.get("n_samples", 100)  # NEW
    min_skin_volume_fraction = search_cfg.get("min_skin_volume_fraction", 0.05)  # NEW
    random_seed = search_cfg.get("random_seed", None)  # NEW
    cube_size_mm = auto_cfg.get("cube_size_mm", 100.0)

    try:
        focus_indices, weights, info = find_focus_and_compute_weights(
            h5_paths=[str(p) for p in h5_paths],
            input_h5_path=str(input_h5),
            top_n=top_n,
            metric=search_metric,
            # NEW parameters:
            search_mode=search_mode,
            n_samples=n_samples,
            cube_size_mm=cube_size_mm,
            min_skin_volume_fraction=min_skin_volume_fraction,
            random_seed=random_seed,
        )

        # ... rest of function unchanged ...
```

---

## 4.4 Summary of Changes

| File | Lines Added | Lines Modified | Complexity |
|------|-------------|----------------|------------|
| `skin_voxel_utils.py` | ~40 | 0 | Low - mirrors existing function |
| `focus_optimizer.py` | ~250 | ~50 | High - new algorithm logic |
| `auto_induced_processor.py` | ~10 | ~5 | Low - config passthrough |
| **Total** | **~300** | **~55** | **Medium** |

---

# Section 5: Configuration Changes

## 5.1 Update `far_field_config.json`

**File**: `goliat/config/defaults/far_field_config.json`

### Current Configuration (v1.0)

```json
{
    "auto_induced": {
        "grid_resolution_deg": 15
    }
}
```

### New Configuration (v2.0)

```json
{
    "auto_induced": {
        "enabled": false,
        "top_n": 10,
        "cube_size_mm": 50,
        "search_metric": "E_magnitude",
        "save_intermediate_files": false,
        "search": {
            "mode": "air",
            "n_samples": 100,
            "min_skin_volume_fraction": 0.05,
            "random_seed": 42
        }
    }
}
```

### Parameter Descriptions

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `enabled` | boolean | `false` | Enable auto-induced analysis after environmental sims complete |
| `top_n` | integer | `10` | Number of candidate focus points to evaluate for SAPD |
| `cube_size_mm` | float | `50` | Side length (mm) of cube for field extraction and scoring |
| `search_metric` | string | `"E_magnitude"` | **Legacy only**. Metric for skin-based search |
| `save_intermediate_files` | boolean | `false` | Save `.smash` files after SAPD extraction for debugging |
| **`search.mode`** | string | `"air"` | **NEW**. Search mode: `"air"` (physical) or `"skin"` (legacy) |
| **`search.n_samples`** | integer | `100` | **NEW**. Number of air points to sample and score |
| **`search.min_skin_volume_fraction`** | float | `0.05` | **NEW**. Min fraction of cube that must be skin (5% default) |
| **`search.random_seed`** | integer/null | `42` | **NEW**. Random seed for reproducibility (`null` = random) |

### Configuration Examples

**Example 1: Default Air-Based Search**

```json
{
    "auto_induced": {
        "enabled": true,
        "top_n": 10,
        "cube_size_mm": 50,
        "search": {
            "mode": "air",
            "n_samples": 100,
            "min_skin_volume_fraction": 0.05,
            "random_seed": 42
        }
    }
}
```

**Example 2: Legacy Skin-Based Search (for comparison)**

```json
{
    "auto_induced": {
        "enabled": true,
        "top_n": 10,
        "cube_size_mm": 100,
        "search_metric": "E_z_magnitude",
        "search": {
            "mode": "skin"
        }
    }
}
```

**Example 3: High-Resolution Air Search**

```json
{
    "auto_induced": {
        "enabled": true,
        "top_n": 20,
        "cube_size_mm": 50,
        "search": {
            "mode": "air",
            "n_samples": 500,
            "min_skin_volume_fraction": 0.03,
            "random_seed": null
        }
    }
}
```

---

## 5.2 Update Documentation

**File**: `docs/developer_guide/configuration.md`

Replace the auto-induced section (lines 189-217) with:

```markdown
### Auto-induced exposure (`auto_induced`)

Auto-induced exposure simulates the worst-case scenario where a MaMIMO base station focuses its beams onto a human through beamforming. After all environmental simulations complete for each (phantom, frequency) pair, GOLIAT can optionally combine the results with optimal phase weights to find the worst-case SAPD.

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `auto_induced.enabled` | boolean | `false` | If `true`, runs auto-induced analysis after environmental simulations complete for each (phantom, freq) pair. Requires `do_run: true` since it needs all `_Output.h5` files. |
| `auto_induced.top_n` | number | `10` | Number of candidate focus points to evaluate. The algorithm finds the top N candidates, combines fields for each, and reports the worst-case SAPD. |
| `auto_induced.cube_size_mm` | number | `50` | Side length in mm of the extraction cube around each focus point. Only fields within this cube are combined, dramatically reducing computation time and output file size. |
| `auto_induced.search_metric` | string | `"E_magnitude"` | **[Legacy mode only]** Metric used for worst-case focus search in skin-based mode. Options: `"E_magnitude"`, `"E_z_magnitude"`, `"poynting_z"`. |
| `auto_induced.save_intermediate_files` | boolean | `false` | If `true`, saves `.smash` project files after SAPD extraction for debugging. |
| `auto_induced.search.mode` | string | `"air"` | Search mode for focus points. `"air"` (recommended, physically correct) searches in air near body surface. `"skin"` (legacy) searches directly on skin voxels. |
| `auto_induced.search.n_samples` | number | `100` | **[Air mode only]** Number of air points to randomly sample and score. Higher values increase accuracy but take longer. |
| `auto_induced.search.min_skin_volume_fraction` | number | `0.05` | **[Air mode only]** Minimum fraction of the cube (0-1) that must contain skin voxels for an air point to be considered valid. Default `0.05` = 5% of cube volume. |
| `auto_induced.search.random_seed` | number/null | `42` | **[Air mode only]** Random seed for sampling reproducibility. Set to `null` for non-reproducible random sampling. |

**Example: Enable auto-induced exposure with air-based search**
```json
{
    "auto_induced": {
        "enabled": true,
        "top_n": 10,
        "cube_size_mm": 50,
        "search": {
            "mode": "air",
            "n_samples": 100,
            "min_skin_volume_fraction": 0.05,
            "random_seed": 42
        }
    }
}
```

**Important notes:**

- **Physical correctness**: The `"air"` mode models how MaMIMO beamforming actually works (beam focused in air, illuminating body). The `"skin"` mode is legacy and physically incorrect.
- **Symmetry reduction incompatibility**: Do not use `phantom_bbox_reduction.use_symmetry_reduction: true` with auto-induced exposure. Symmetry reduction cuts the bounding box at x=0, keeping only one half of the body - you'd miss half the skin surface and cannot find the true worst-case focus point.
- **Results location**: Auto-induced results are saved to `results/far_field/{phantom}/{freq}MHz/auto_induced/auto_induced_summary.json`.
- **Caching**: The analysis is skipped if the summary file exists and is newer than all `_Output.h5` files.
- **Performance**: Air-based search with `n_samples=100` typically takes 5-10 minutes per (phantom, freq) pair on a modern CPU.
```

---

## 5.3 Configuration Access in Code

The new parameters are accessed via the hierarchical config system:

```python
# In auto_induced_processor.py
auto_cfg = self.config["auto_induced"] or {}
search_cfg = auto_cfg.get("search", {})

# Access parameters with defaults
search_mode = search_cfg.get("mode", "skin")  # Default to legacy for backward compat
n_samples = search_cfg.get("n_samples", 100)
min_skin_volume_fraction = search_cfg.get("min_skin_volume_fraction", 0.05)
random_seed = search_cfg.get("random_seed", None)
cube_size_mm = auto_cfg.get("cube_size_mm", 100.0)
```

**Backward Compatibility**: If `search.mode` is not specified, default to `"skin"` to preserve existing behavior.

---

## 5.4 Validation Rules

Add validation in `Config` class to catch common errors:

```python
def _validate_auto_induced_config(self):
    """Validate auto-induced configuration."""
    auto_cfg = self.data.get("auto_induced")
    if not auto_cfg or not auto_cfg.get("enabled"):
        return
    
    search_cfg = auto_cfg.get("search", {})
    mode = search_cfg.get("mode", "skin")
    
    # Check mode is valid
    if mode not in ["air", "skin"]:
        raise ValueError(f"auto_induced.search.mode must be 'air' or 'skin', got '{mode}'")
    
    # Air mode specific validation
    if mode == "air":
        n_samples = search_cfg.get("n_samples", 100)
        min_frac = search_cfg.get("min_skin_volume_fraction", 0.05)
        
        if not isinstance(n_samples, int) or n_samples < 1:
            raise ValueError(f"auto_induced.search.n_samples must be positive integer, got {n_samples}")
        
        if not (0 < min_frac < 1):
            raise ValueError(f"auto_induced.search.min_skin_volume_fraction must be in (0, 1), got {min_frac}")
    
    # Check cube size
    cube_size = auto_cfg.get("cube_size_mm", 100)
    if cube_size < 10 or cube_size > 500:
        warnings.warn(f"auto_induced.cube_size_mm = {cube_size}mm is unusual (typical: 50-100mm)")
```

---

## 5.5 Migration Path

For users with existing configs:

### Automatic Migration

If `auto_induced.search` is not present, automatically inject defaults:

```python
# In Config.__init__() or similar
if "auto_induced" in self.data and "search" not in self.data["auto_induced"]:
    # User has old config without search section
    self.data["auto_induced"]["search"] = {
        "mode": "skin",  # Preserve legacy behavior
    }
    self.logger.info("Auto-migrated auto_induced config to v2.0 (legacy skin mode)")
```

### User Notification

On first run with auto-induced enabled, log a message:

```python
if auto_cfg.get("enabled") and search_cfg.get("mode") == "skin":
    self._log(
        "NOTE: Using legacy skin-based search. Consider upgrading to air-based search "
        "(set auto_induced.search.mode='air') for physically correct results.",
        log_type="warning",
    )
```

---

# Section 6: Testing & Validation

## 6.1 Unit Tests

### Test `extract_air_voxels()`

**File**: `tests/test_skin_voxel_utils.py` (create if doesn't exist)

```python
import pytest
import numpy as np
import tempfile
import h5py
from goliat.utils.skin_voxel_utils import extract_air_voxels, extract_skin_voxels

def test_extract_air_voxels_basic():
    """Test that extract_air_voxels identifies unmapped voxels."""
    # Create a mock _Input.h5 file
    with tempfile.NamedTemporaryFile(suffix='.h5', delete=False) as tmp:
        with h5py.File(tmp.name, 'w') as f:
            # Create simple grid: 10x10x10
            meshes = f.create_group("Meshes")
            mesh0 = meshes.create_group("0")
            
            # Create voxel data: IDs 0 (air), 1 (skin), 2 (other tissue)
            voxels = np.zeros((10, 10, 10), dtype=np.uint8)
            voxels[2:8, 2:8, 2:8] = 1  # Skin cube in center
            voxels[4:6, 4:6, 4:6] = 2  # Other tissue in very center
            
            mesh0.create_dataset("voxels", data=voxels)
            mesh0.create_dataset("axis_x", data=np.linspace(0, 0.1, 10))
            mesh0.create_dataset("axis_y", data=np.linspace(0, 0.1, 10))
            mesh0.create_dataset("axis_z", data=np.linspace(0, 0.1, 10))
            
            # Create id_map with only IDs 1 and 2 mapped (0 is unmapped = air)
            id_map = np.zeros((3, 16), dtype=np.uint8)
            id_map[1] = [0x01] * 16  # Dummy UUID for skin
            id_map[2] = [0x02] * 16  # Dummy UUID for other
            mesh0.create_dataset("id_map", data=id_map)
            
            # Create AllMaterialMaps with mappings
            # (simplified - in real file this is more complex)
        
        # Test extraction
        air_mask, ax_x, ax_y, ax_z, tissue_map = extract_air_voxels(tmp.name)
        
        # Air should be ID 0 voxels (outer shell)
        assert air_mask.shape == (10, 10, 10)
        assert np.sum(air_mask) > 0
        assert not air_mask[5, 5, 5]  # Center should not be air
        
        # Clean up
        import os
        os.unlink(tmp.name)
```

### Test `find_valid_air_focus_points()`

```python
def test_find_valid_air_focus_points():
    """Test that valid air points are near skin."""
    # Use same mock file as above
    # ...
    
    valid_indices, skin_counts = find_valid_air_focus_points(
        input_h5_path=tmp.name,
        cube_size_mm=20,
        min_skin_volume_fraction=0.05,
    )
    
    # Should find air voxels adjacent to skin
    assert len(valid_indices) > 0
    assert all(skin_counts > 0)
```

### Test `compute_hotspot_score_at_air_point()`

```python
def test_hotspot_score():
    """Test hotspot scoring returns reasonable values."""
    # Create mock _Output.h5 files with known E-fields
    # ...
    
    score = compute_hotspot_score_at_air_point(
        h5_paths=[output1.h5, output2.h5],
        air_focus_idx=np.array([5, 5, 5]),
        input_h5_path=input.h5,
        cube_size_mm=50,
    )
    
    assert score > 0
    assert np.isfinite(score)
```

---

## 6.2 Integration Tests

### Test Full Air-Based Workflow

**File**: `tests/test_auto_induced_air_search.py`

```python
import pytest
from pathlib import Path
from goliat.extraction.focus_optimizer import find_focus_and_compute_weights

@pytest.mark.integration
def test_air_based_search_full_workflow(sample_environmental_results):
    """Test complete air-based focus search workflow."""
    h5_paths = sample_environmental_results["output_h5_files"]
    input_h5 = sample_environmental_results["input_h5"]
    
    focus_idx, weights, info = find_focus_and_compute_weights(
        h5_paths=h5_paths,
        input_h5_path=input_h5,
        top_n=3,
        search_mode="air",
        n_samples=20,  # Small for test speed
        cube_size_mm=50,
        min_skin_volume_fraction=0.05,
        random_seed=42,
    )
    
    # Validate results
    assert focus_idx.shape == (3,)  # Voxel index
    assert weights.shape == (len(h5_paths),)
    assert info["search_mode"] == "air"
    assert "all_focus_indices" in info
    assert len(info["all_focus_indices"]) == 3
    assert all(np.isfinite(info["all_hotspot_scores"]))
```

### Test Backward Compatibility

```python
@pytest.mark.integration
def test_legacy_skin_mode_still_works(sample_environmental_results):
    """Ensure legacy skin-based search still functions."""
    h5_paths = sample_environmental_results["output_h5_files"]
    input_h5 = sample_environmental_results["input_h5"]
    
    focus_idx, weights, info = find_focus_and_compute_weights(
        h5_paths=h5_paths,
        input_h5_path=input_h5,
        top_n=3,
        search_mode="skin",
        metric="E_z_magnitude",
    )
    
    assert info["search_mode"] == "skin"
    assert "max_metric_sum" in info
```

---

## 6.3 Validation Against Known Data

### Compare Air vs Skin Modes

Create a test case where we know the physical answer:

```python
def test_air_vs_skin_comparison():
    """Compare air-based vs skin-based results on test data."""
    # Run both modes on same data
    air_results = run_auto_induced(mode="air", ...)
    skin_results = run_auto_induced(mode="skin", ...)
    
    # Air mode should find focus points IN AIR (not on skin)
    # We can't directly compare SAPD values, but can check:
    assert air_results["worst_case"]["peak_sapd_w_m2"] > 0
    assert skin_results["worst_case"]["peak_sapd_w_m2"] > 0
    
    # Log comparison for manual review
    print(f"Air mode SAPD: {air_results['worst_case']['peak_sapd_w_m2']:.3e} W/m²")
    print(f"Skin mode SAPD: {skin_results['worst_case']['peak_sapd_w_m2']:.3e} W/m²")
```

---

## 6.4 Performance Benchmarks

### Measure Runtime

```python
import time

def benchmark_air_search():
    """Measure performance of air-based search."""
    times = {
        "find_valid_air": [],
        "subsample": [],
        "score_candidates": [],
        "total": [],
    }
    
    for trial in range(3):
        start = time.perf_counter()
        
        # Find valid air points
        t0 = time.perf_counter()
        valid_indices, _ = find_valid_air_focus_points(...)
        times["find_valid_air"].append(time.perf_counter() - t0)
        
        # Subsample
        t0 = time.perf_counter()
        sampled = subsample_air_points(valid_indices, n_samples=100)
        times["subsample"].append(time.perf_counter() - t0)
        
        # Score
        t0 = time.perf_counter()
        for idx in sampled:
            score = compute_hotspot_score_at_air_point(...)
        times["score_candidates"].append(time.perf_counter() - t0)
        
        times["total"].append(time.perf_counter() - start)
    
    # Print summary
    for phase, t_list in times.items():
        print(f"{phase:20s}: {np.mean(t_list):.2f}s ± {np.std(t_list):.2f}s")
```

**Expected Performance** (on modern CPU):
- Find valid air: ~30-60s
- Subsample: <1s
- Score candidates (n=100): ~3-5 minutes
- **Total: ~5-7 minutes per (phantom, freq)**

---

## 6.5 Visual Validation

### Visualization Script

Create a script to visualize focus point locations:

```python
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

def visualize_focus_points(air_mask, skin_mask, focus_indices, output_path):
    """3D scatter plot of air/skin voxels and focus points."""
    fig = plt.figure(figsize=(12, 10))
    ax = fig.add_subplot(111, projection='3d')
    
    # Subsample for visualization
    air_coords = np.argwhere(air_mask)[::100]  # Every 100th
    skin_coords = np.argwhere(skin_mask)[::10]  # Every 10th
    
    ax.scatter(air_coords[:, 0], air_coords[:, 1], air_coords[:, 2],
               c='lightblue', alpha=0.1, s=1, label='Air')
    ax.scatter(skin_coords[:, 0], skin_coords[:, 1], skin_coords[:, 2],
               c='pink', alpha=0.3, s=2, label='Skin')
    ax.scatter(focus_indices[:, 0], focus_indices[:, 1], focus_indices[:, 2],
               c='red', s=50, marker='*', label='Focus Points')
    
    ax.set_xlabel('X')
    ax.set_ylabel('Y')
    ax.set_zlabel('Z')
    ax.legend()
    plt.title('Focus Point Locations (Air Mode)')
    plt.savefig(output_path, dpi=150)
    plt.close()
```

**Manual Check**: Visually confirm that focus points are:
1. In air (not inside body)
2. Near skin surface
3. Distributed around body (not clustered)

---

## 6.6 Acceptance Criteria

Before merging, verify:

- [ ] All unit tests pass
- [ ] Integration tests pass with real simulation data
- [ ] Air mode produces reasonable SAPD values (same order of magnitude as skin mode)
- [ ] Performance is acceptable (<10 min per phantom/freq)
- [ ] Legacy skin mode still works (backward compatibility)
- [ ] Configuration validation catches invalid inputs
- [ ] Documentation is updated
- [ ] Visual inspection confirms focus points are in air near body

---

# Section 7: Migration Guide

## 7.1 For End Users

### Existing Configs

**If you have auto-induced disabled**: No action needed.

**If you have auto-induced enabled with default settings**:

Your config probably looks like:
```json
{
    "auto_induced": {
        "enabled": true,
        "top_n": 10,
        "cube_size_mm": 100
    }
}
```

**Action**: Add the new `search` section to use the improved air-based algorithm:

```json
{
    "auto_induced": {
        "enabled": true,
        "top_n": 10,
        "cube_size_mm": 50,
        "search": {
            "mode": "air",
            "n_samples": 100,
            "min_skin_volume_fraction": 0.05,
            "random_seed": 42
        }
    }
}
```

**Why**: The new air-based mode is physically correct and should give more accurate results.

### Comparing Results

To compare old vs new approach on the same data:

1. **Run with legacy mode first**:
```json
{ "auto_induced": { "enabled": true, "search": { "mode": "skin" } } }
```

2. **Run with new mode**:
```json
{ "auto_induced": { "enabled": true, "search": { "mode": "air" } } }
```

3. **Compare results**: Look at `auto_induced_summary.json` in both runs.

Expected differences:
- Focus point locations will differ (air vs skin)
- SAPD values may differ by 10-30% (air mode should be more conservative/higher in most cases)
- Air mode may be ~2-5x slower due to extra computation

---

## 7.2 For Developers

### Code Migration Checklist

If you've customized GOLIAT's auto-induced code:

- [ ] **Check imports**: Ensure you import from correct modules
- [ ] **Update function calls**: `find_focus_and_compute_weights()` has new parameters
- [ ] **Config access**: Use `config["auto_induced.search.mode"]` pattern
- [ ] **Test compatibility**: Run your custom code with both modes
- [ ] **Update documentation**: If you have custom docs, update them

### API Changes

| Old API | New API | Notes |
|---------|---------|-------|
| `find_focus_and_compute_weights(h5_paths, input_h5, top_n, metric)` | `find_focus_and_compute_weights(..., search_mode="air", ...)` | Added optional params; defaults preserve backward compat |
| N/A | `extract_air_voxels(input_h5_path)` | New function in `skin_voxel_utils` |
| N/A | `find_valid_air_focus_points(...)` | New function in `focus_optimizer` |
| N/A | `compute_hotspot_score_at_air_point(...)` | New function in `focus_optimizer` |

### Deprecation Timeline

**v2.0 (current)**: Both modes supported, skin mode is default for backward compat
**v2.1 (future)**: Air mode becomes default, skin mode deprecated with warning
**v3.0 (future)**: Skin mode removed entirely

---

# Section 8: Appendices

## 8.1 Mathematical Background

### MRT (Maximum Ratio Transmission)

For N antenna elements transmitting at a point **r₀**, the optimal phase for element i is:

$$
\phi_i^* = -\arg(E_{z,i}(\mathbf{r}_0))
$$

This maximizes constructive interference at **r₀**. With equal amplitude weights:

$$
w_i = \frac{1}{\sqrt{N}} e^{j\phi_i^*}
$$

The combined field is:

$$
\mathbf{E}_{\text{combined}}(\mathbf{r}) = \sum_{i=1}^{N} w_i \mathbf{E}_i(\mathbf{r})
$$

### SAPD Calculation

SAPD (Spatially Averaged Power Density) is defined as:

$$
\text{SAPD} = \frac{1}{A} \int_A |\mathbf{S}| \, dA
$$

where **S** is the time-averaged Poynting vector:

$$
\mathbf{S} = \frac{1}{2} \text{Re}(\mathbf{E} \times \mathbf{H}^*)
$$

For our purposes, we use the approximation:

$$
\text{SAPD} \propto \langle |\mathbf{E}|^2 \rangle
$$

averaged over skin surface within the averaging area (4 cm² for ICNIRP).

### Hotspot Score Justification

Our hotspot score is:

$$
\text{score} = \frac{1}{N_{\text{skin}}} \sum_{r \in \text{skin}} |\mathbf{E}_{\text{combined}}(\mathbf{r})|^2
$$

This is proportional to the SAPD that would be computed by GenericSAPDEvaluator, making it a good predictor for ranking candidates.

---

## 8.2 Performance Optimization Notes

### Current Bottlenecks

1. **Finding valid air points**: O(N_air × cube_volume) where N_air ~ 5-6M
   - **Optimization**: Could use scipy.ndimage.convolve with a box kernel
   - **Expected speedup**: 5-10x

2. **Hotspot scoring**: O(n_samples × n_skin_per_cube × n_directions)
   - Currently: 100 × 100 × 12 = 120k E-field reads
   - **Optimization**: Batch reads, use vectorized field_reader
   - **Expected speedup**: 2-3x

3. **I/O from _Output.h5**: Each `read_field_at_indices()` opens file
   - **Optimization**: Keep files open, cache datasets
   - **Expected speedup**: 1.5-2x

### Future Improvements

**Adaptive Sampling**: Instead of uniform random sampling, use:
1. Coarse grid search (n=50)
2. Identify top-10 regions
3. Dense sampling around those regions
4. Expected: Better worst-case detection with same compute

**GPU Acceleration**: Move E-field combination to GPU
- Use CuPy for array operations
- Expected: 10-50x speedup for scoring phase

**Precomputed Validity Mask**: Cache valid air points per phantom
- Saves ~30s per run (valid_air_points.npy)
- Invalidate if grid changes

---

## 8.3 Troubleshooting

### Common Issues

**Issue**: "No valid air focus points found"

**Cause**: `min_skin_volume_fraction` too high or `cube_size_mm` too small

**Solution**: Lower `min_skin_volume_fraction` to 0.01-0.03, or increase `cube_size_mm` to 75-100mm

---

**Issue**: Air mode much slower than expected

**Cause**: Too many samples or large cube size

**Solution**: Reduce `n_samples` to 50-75, or reduce `cube_size_mm` to 40mm

---

**Issue**: Different results each run (non-reproducible)

**Cause**: `random_seed` is `null`

**Solution**: Set `random_seed: 42` in config for reproducibility

---

**Issue**: SAPD values very different from skin mode

**Cause**: Expected - different physical model

**Solution**: Use air mode going forward. Skin mode is physically incorrect.

---

## 8.4 References

1. IEC 62209-3:2019 - "Measurement procedure for the assessment of specific absorption rate of human exposure to radio frequency fields from handheld and body-mounted wireless communication devices - Part 3: Vector measurement-based systems (Frequency range of 600 MHz to 6 GHz)"

2. ICNIRP Guidelines (2020) - "Guidelines for Limiting Exposure to Electromagnetic Fields (100 kHz to 300 GHz)"

3. Thors et al. (2017) - "Assessment of human exposure to electromagnetic fields from MIMO-enabled wireless communication systems" IEEE Access

4. Sim4Life Documentation - GenericSAPDEvaluator API

5. GOLIAT Internal Documentation:
   - `docs/developer_guide/system_architecture.md`
   - `docs/developer_guide/configuration.md`
   - `docs/technical/auto_induced_air_search_implementation_plan.md` (this document)

---

## 8.5 Glossary

| Term | Definition |
|------|------------|
| **MaMIMO** | Massive MIMO - Multi-antenna systems with many elements (e.g., 64+) |
| **MRT** | Maximum Ratio Transmission - Beamforming technique for focusing |
| **SAPD** | Spatially Averaged Power Density (W/m²) |
| **Hotspot** | Region of locally elevated power density on skin surface |
| **Focus point** | Location in space where MRT beam is aimed |
| **Air voxel** | Voxel in simulation grid representing air/background |
| **Skin voxel** | Voxel in simulation grid representing skin tissue |
| **Yee grid** | FDTD grid with staggered E and H components |

---

## 8.6 Acknowledgments

This implementation was developed based on discussions about the physical accuracy of MaMIMO beamforming models for EMF dosimetry. Special thanks to:

- GOLIAT development team
- Sim4Life support for clarifications on SAPD evaluator behavior
- IEC TC106 for standards guidance

---

## 8.7 Change Log

**v2.0 (January 2026)**
- Added air-based focus search algorithm
- New config parameters: `search.mode`, `search.n_samples`, etc.
- Backward compatible with legacy skin-based mode
- Performance optimizations in field reading
- Comprehensive documentation and tests

**v1.0 (2024)**
- Initial auto-induced exposure implementation
- Skin-based focus search
- Basic MRT phase computation

---

**END OF IMPLEMENTATION PLAN**

---

*For questions or issues, contact the GOLIAT development team or file an issue on GitHub.*
