# Auto-Induced Exposure Implementation Plan

## 1. Overview

### 1.1 What is Auto-Induced Exposure?

Unlike **environmental exposure** (random plane waves hitting a phantom from various directions), **auto-induced exposure** simulates the worst-case scenario where a MaMIMO base station *focuses* its beams onto a human through beamforming.

**Key insight:** We don't need new FDTD simulations—we combine existing environmental far-field outputs with optimal phase weights that maximize constructive interference at a target point.

### 1.2 Key Decisions

| Topic | Decision | Rationale |
|-------|----------|-----------|
| Target metric | Peak SAPD on skin | EU project requirement; IEC compliance |
| Weighting scheme | Phase-only, equal amplitudes | Simplifies optimization; automatic power normalization |
| SAPD computation | Use Sim4Life | IEC standard compliance; existing `SapdExtractor` |
| H5 handling | Copy template, replace field data | Proven pattern in `slice_h5_output` |
| Autocleaning | Must be OFF | Need `_Output.h5` and `_Input.h5` for post-processing |

### 1.3 How It Works

```
[Phase 1: Run Environmental Simulations]
    goliat study tessellation_config.json
    → N directions × 2 polarizations per (phantom, frequency)
    → Each produces _Output.h5 with E/H fields + _Input.h5 with tissue data
    
[Phase 2: Auto-Induced Combination]
    For each (phantom, frequency):
        1. Load skin mask from any _Input.h5 (grids are identical)
        2. Search for worst-case focus point: argmax_r Σ|E_i(r)| over skin voxels
        3. Compute optimal phases: φ_i = -arg(E_i(r_max))
        4. Combine fields: E_combined = Σ (1/√N) exp(jφ_i) × E_i
                          H_combined = Σ (1/√N) exp(jφ_i) × H_i
        5. Write combined_Output.h5 (copy template, replace E/H)
        6. Run SAPD extraction via Sim4Life
```

---

## 2. Physics & Math

### 2.1 Phase-Only Weighting

We assume phase control but equal amplitudes—a realistic model for base station behavior:

```
w_i = (1/√N) × exp(j × φ_i)
```

Where:
- `N` = number of directions × polarizations
- `|w_i| = 1/√N` for all i (equal power per direction)
- `Σ |w_i|² = 1` (total power normalized to 1W automatically)
- `φ_i` = controllable phase for direction i

### 2.2 Optimal Phase for Focusing

To maximize |E_combined(r)| at target point r:

```
φ_i* = -arg(E_i(r))
```

This aligns all complex phasors for constructive interference:

```
|E_combined(r)|_max = (1/√N) × Σ_i |E_i(r)|
```

### 2.3 Efficient Worst-Case Search

**Key insight: Phase optimization is unnecessary for the search!**

Since optimal phases always align phasors, the worst-case location is simply:

```
r_worst = argmax_r Σ_i |E_i(r)|
```

This is just a sum of magnitudes—no optimization needed during search.

**Algorithm:**
```python
magnitude_sum = np.zeros(num_skin_voxels)

for h5_path in direction_h5_paths:
    E_skin = read_efield_at_skin_voxels(h5_path, skin_mask)
    magnitude_sum += np.linalg.norm(E_skin, axis=-1)

worst_skin_idx = np.argmax(magnitude_sum)
worst_voxel = skin_voxel_coords[worst_skin_idx]
```

**Complexity:**
- Memory: O(num_skin_voxels) ≈ 88k instead of 8M
- Disk reads: O(N) H5 files—same as single-point focusing
- Search is essentially FREE compared to brute-force

---

## 3. H5 File Structures

### 3.1 _Output.h5 Field Layout

```
FieldGroups/{id}/AllFields/EM E(x,y,z,f0)/_Object/Snapshots/0/
  ├── comp0  [Nx-1, Ny, Nz, 2]  # Ex: [real, imag]
  ├── comp1  [Nx, Ny-1, Nz, 2]  # Ey
  └── comp2  [Nx, Ny, Nz-1, 2]  # Ez
```

Note the Yee grid staggering: N vs N-1 dimensions per component.

### 3.2 _Input.h5 Tissue Data

```
Meshes/<mesh_id>/
  ├── voxels     # (Nx, Ny, Nz) uint16 - tissue ID per voxel
  ├── id_map     # (N_tissues, 16) bytes - UUID per tissue ID
  ├── axis_x, axis_y, axis_z  # Grid coordinates

AllMaterialMaps/<grp>/<uuid>/Property_*/_Object
  └── attrs['material_name']  # e.g., "Skin", "Ear_skin"
```

**Tested result:** ~88k skin voxels vs ~8M total phantom voxels (100× reduction).

### 3.3 Writing Combined H5

Copy a template from any completed environmental simulation, then replace field data:

```python
import shutil
shutil.copy(template_h5_path, output_path)

with h5py.File(output_path, 'r+') as f:
    # Find "Overall Field" FieldGroup by name attribute
    for fg_key in f['FieldGroups'].keys():
        if f[f'FieldGroups/{fg_key}/_Object'].attrs.get('name') == b'Overall Field':
            # Replace E/H field datasets in-place
            for dim, comp in enumerate(['comp0', 'comp1', 'comp2']):
                ds = fg[f'AllFields/EM E(x,y,z,f0)/_Object/Snapshots/0/{comp}']
                ds[:,:,:,0] = np.real(E_combined[dim, ...])  # Handle Yee slicing
                ds[:,:,:,1] = np.imag(E_combined[dim, ...])
```

This mirrors the proven `SapdExtractor._create_sliced_h5` approach.

---

## 4. Implementation Roadmap

### Phase 1: PoC Script (Weeks 1-2)

Standalone Python script that:
1. Takes directory of completed environmental sim results
2. Extracts skin mask from `_Input.h5`
3. Finds worst-case focus point on skin
4. Combines E/H fields with optimal phases
5. Writes valid `combined_Output.h5`

**Validation:** Manual load into Sim4Life to verify fields are readable.

### Phase 2: SAPD Integration (Week 3)

- Integrate with `SapdExtractor` using same `SimulationExtractor` pattern
- Run SAPD extraction on combined H5
- Compare auto-induced vs environmental SAPD (focusing effect should be visible)

### Phase 3: CLI Command (Week 4)

```bash
goliat combine tessellation_config.json --output-dir results/auto_induced/
```

---

## 5. Proposed PR Structure

| PR | Component | Status | Description |
|----|-----------|--------|-------------|
| 1 | `skin_voxel_utils.py` | ✅ Done (#124, #125) | Extract skin voxel mask from `_Output.h5` |
| 2 | `field_reader.py` | ⬜ | Memory-efficient E/H field reading from `_Output.h5` |
| 3 | `optimizer.py` | ⬜ | Worst-case search + phase computation |
| 4 | `combiner.py` | ⬜ | Chunked field combination (memory efficient) |
| 5 | `h5_writer.py` | ⬜ | Write combined H5 from template |
| 6 | SAPD integration | ⬜ | Load combined H5 into existing extraction |
| 7 | CLI command | ⬜ | `goliat combine` with config options |

---

## 6. Memory Considerations

**Typical phantom at 1mm resolution:** 300×500×1900 voxels

**Per-direction storage:**
- E-field: 3 components × complex64 = ~2.1 GB
- H-field: 3 components × complex64 = ~2.1 GB

**Chunked processing approach:**
```python
for z_start in range(0, Nz, chunk_size):
    z_end = min(z_start + chunk_size, Nz)
    for h5_path in h5_paths:
        E_chunk = read_efield_chunk(h5_path, z_start, z_end)
        E_combined[:,:,:,z_start:z_end] += weight * E_chunk
```

With chunk_size=50 z-slabs: ~56MB per direction per chunk—manageable.

---

## 7. Open Questions

1. **Focus component:** Use E_z specifically, or |E| (full magnitude)?
   - Document currently uses E_z for MRT
   - Physically, |E| is more relevant for SAR

2. **Polarization handling:** Each direction has θ and φ polarizations
   - Treat as 2N separate channels (N directions × 2 pols)?
   - Or aggregate polarizations first?

---

## 8. References

**Existing code patterns:**
- `goliat/utils/h5_slicer.py` - H5 slicing and copying
- `goliat/extraction/sapd_extractor.py` - Loading sliced H5 into Sim4Life
- `goliat/studies/far_field_study.py` - Spherical tessellation

**Standards:**
- IEC/IEEE 63195-2:2022 - SAPD evaluation

---

*Document created: 2026-01-08*
*Last updated: 2026-01-08*
