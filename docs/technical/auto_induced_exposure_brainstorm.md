# Auto-Induced Exposure Implementation: Brainstorming Document

## 1. Overview & Context

### 1.1 What is "Auto-Induced Exposure"?

Unlike **environmental exposure** (random plane waves hitting a phantom from various directions), **auto-induced exposure** simulates the worst-case scenario where a MaMIMO base station *focuses* its beams onto a human through beamforming. In TDD systems, the base station uses uplink channel estimates for downlink precoding - in theory allowing it to coherently combine signals to maximize power at any point.

### 1.2 The Core Idea

The physics insight is elegant:
- Each impinging wave direction can be thought of as a **tap** in a channel matrix
- In the freakish worst-case, we assume **100% phase controllability** (but not amplitude) for each tap
- We use **MRT (Maximum Ratio Transmission)** precoding to find optimal phases that maximize constructive interference at a target point
- The "measured signal" for MRT is the **z-component of the E-field** (or any other component) at a specific voxel

### 1.3 Relationship to Existing Code

| Concept | Environmental (current GOLIAT) | Auto-Induced (new) |
|---------|-------------------------------|-------------------|
| Source | Multiple plane waves, different directions | Same, but phase-weighted |
| Simulation | Independent sims per direction | Same (reuse outputs) |
| Combining | SAR averaging/summation | MRT-weighted complex E-field sum |
| Output | Average SAR | Focused SAR (worst-case) |

---

## 2. Technical Approach

### 2.1 High-Level Pipeline

```
[Step 1: Impulse Response Database]
    For each direction in tessellation (θ, φ):
        - Run FDTD simulation with plane wave from that direction
        - Save complex E-field vectors in _Output.h5

[Step 2: Channel Matrix Construction]
    - Pick a focus point (x, y, z) - could be any voxel
    - Extract E_z(x,y,z) from each direction's H5 file
    - Build H matrix: H[i] = E_z from direction i at focus point
        (H is a 1 × N_directions vector for single-point focusing)

[Step 3: MRT Precoding]
    - W = H^H / ||H^H||_F   (conjugate transpose, Frobenius normalized)
    - These are the complex weights (phase + normalized amplitude)

[Step 4: Weighted Field Combination]
    - For each voxel in the domain:
        E_combined(r) = Σ W[i] × E_i(r)
    - This is a massive weighted sum of 3D complex arrays

[Step 5: Write Combined H5 & Extract SAR]
    - Write the combined E-field to a new _Output.h5 file
    - Run the standard GOLIAT extraction pipeline on this file
```

### 2.2 Key Implementation Considerations

#### 2.2.1 Memory Management - The Big Challenge

**Problem**: Each `_Output.h5` file contains a full 3D E-field array, typically:
- Shape: `(3, Nx, Ny, Nz)` (x, y, z components for each voxel)
- Data type: `complex64` (8 bytes per element)
- For a 1mm full-body phantom: ~2 GB per field (E or H), ~4 GB total per direction

**Strategies** (inspired by hybridizer patterns):

1. **Memory-efficient iteration** (like `efficient_cluster_addition`):
   ```python
   E_combined = np.zeros((3, Nx, Ny, Nz), dtype=np.csingle)
   for i, direction in enumerate(directions):
       with h5py.File(f"dir_{i}_Output.h5", "r") as f:
           E_i = f["FieldGroup/.../E"][:]  # Load one at a time
           E_combined += weights[i] * E_i
           # E_i goes out of scope, memory freed
   ```

2. **HDF5 slicing** (never load full array):
   ```python
   with h5py.File(path, "r") as f:
       # Only load a chunk:
       E_chunk = f["E"][component, x1:x2, y1:y2, z1:z2]
   ```

3. **Chunked processing** (process domain in spatial blocks):
   - Divide domain into chunks (e.g., z-slabs)
   - For each chunk: load corresponding region from all H5 files, combine, write to output

4. **Memory-mapped arrays** (if files fit on disk but not RAM):
   ```python
   E_combined = np.memmap('combined.dat', dtype='complex64', mode='w+', shape=(3,Nx,Ny,Nz))
   ```

#### 2.2.2 Finding the Focus Point

Options for selecting where to focus:
1. **User-specified voxel** (for testing/validation)
2. **Maximum environmental SAR location** (focus on the hot spot from averaged exposure)
3. **Grid search** over sensitive regions (eyes, brain, skin)
4. **Multiple focus points** (compute worst-case for each, report maximum)

#### 2.2.3 Power Normalization

The MRT weights will have the property that `||W||² = 1` (unit power). But we need to normalize to match:
1. **1W total input power** (like current environmental sims)
2. **Equivalent EIRP** for regulatory comparison
3. **Per-tap power constraint** (if mimicking real antenna limitations)

#### 2.2.4 Phase-Only Weighting (Recommended Approach)

Since we're simulating plane waves from discrete directions (not actual ray-traced paths), and real base stations have limited amplitude control, we adopt a **phase-only weighting** model with equal amplitudes:

```
w_i = (1/√N) × exp(j × φ_i)
```

Where:
- `N` = number of directions (tessellation points)
- `|w_i| = 1/√N` for all i (equal power per direction)
- `Σ |w_i|² = 1` (total power normalized automatically)
- `φ_i` = controllable phase for direction i

**Advantages:**
1. **Physically realistic**: Base stations can control phase but typically have equal power per antenna element
2. **Automatic power normalization**: Total power is always 1W regardless of phases
3. **Simpler optimization**: Only N phase values to determine, not 2N (amplitude + phase)

**Optimal Phase Selection**

To maximize |E_combined(r)| at a target point r, the optimal phases are:

```
φ_i* = -arg(E_i(r))
```

This causes all complex phasors to **align** (constructive interference), giving:

```
|E_combined(r)|_max = (1/√N) × Σ_i |E_i(r)|
```

The maximum field is simply the **sum of magnitudes** from all directions, normalized by √N.

#### 2.2.5 Efficient Worst-Case Search Algorithm

A naive worst-case search would:
1. For each voxel r, compute optimal phases and resulting SAR
2. Find maximum across all voxels
3. Complexity: O(N × M × M) where M = number of voxels, N = directions

**Key Insight: Phase optimization is unnecessary for the search!**

Since optimal phases always align phasors, the worst-case SAR at any point r is:

```
SAR_max(r) ∝ |E_combined|² = (1/N) × (Σ_i |E_i(r)|)²
```

This is a **monotonic function of the sum of magnitudes**. Therefore:

```
argmax_r SAR_max(r) = argmax_r Σ_i |E_i(r)|
```

**Efficient Algorithm:**

```python
# Single-pass worst-case location search
# Memory: O(M) - just one accumulated array
# Disk I/O: O(N) - same as single-target case

magnitude_sum = np.zeros((Nx, Ny, Nz))

for i, h5_path in enumerate(direction_h5_files):
    with h5py.File(h5_path, 'r') as f:
        E_i = load_complex_E_field(f)           # Shape: (Nx, Ny, Nz, 3)
        E_mag = np.linalg.norm(E_i, axis=-1)    # |E_i| at each voxel
        magnitude_sum += E_mag

# Worst-case location is where sum of magnitudes is maximum
worst_voxel = np.unravel_index(np.argmax(magnitude_sum), magnitude_sum.shape)

# Optimal phases for this location (second pass, single voxel only)
optimal_phases = []
for h5_path in direction_h5_files:
    E_i_at_peak = load_single_voxel(h5_path, worst_voxel)
    optimal_phases.append(-np.angle(E_i_at_peak[2]))  # Phase of E_z
```

**Complexity:**
- Memory: O(Nx × Ny × Nz) - one accumulated array
- Disk reads: O(N) full H5 reads - **same as single-target focusing**
- Computation: O(N × Nx × Ny × Nz) - linear, highly parallelizable

**The worst-case search is essentially FREE compared to single-point focusing!**

#### 2.2.6 SAPD-Specific Optimization

Since we only care about **peak SAPD on the skin surface**, not SAR in the volume:

1. **Skin surface mask**: During environmental setup, save a binary mask of skin-surface voxels
2. **Reduced search space**: ~100k surface voxels vs ~10M volume voxels (100× reduction)
3. **Search algorithm**: Only compute `magnitude_sum` on skin surface voxels

```python
# Even more efficient with skin mask
magnitude_sum_skin = np.zeros(num_skin_voxels)

for h5_path in direction_h5_files:
    E_i = load_skin_voxels_only(h5_path, skin_mask)  # Much smaller!
    magnitude_sum_skin += np.linalg.norm(E_i, axis=-1)

worst_skin_idx = np.argmax(magnitude_sum_skin)
worst_voxel = skin_voxel_coords[worst_skin_idx]
```

This makes the worst-case SAPD search extremely efficient.

#### 2.2.7 Heuristic Search Optimizations

The brute-force algorithm (sum all magnitudes, find max) requires reading all voxels from all N H5 files. For large grids, this is I/O bound. Here are heuristics to accelerate the search:

**1. Coarse-to-Fine Search**
```python
# Phase 1: Coarse grid (every 10th voxel)
coarse_magnitude_sum = compute_on_subgrid(h5_files, subsample=10)
candidate_regions = find_peaks(coarse_magnitude_sum, top_k=5)

# Phase 2: Fine grid only in candidate regions  
for region in candidate_regions:
    fine_magnitude_sum = compute_in_region(h5_files, region)
    refine_peak(region, fine_magnitude_sum)
```
Reduces I/O by ~1000× for coarse pass, then only reads fine data near peaks.

**2. Use Environmental SAR Peaks as Seeds**
The worst-case focused location is likely near places that already had high SAR in individual directions:
```python
# Collect peak SAR locations from each direction's sar_results.json
candidate_points = []
for direction in directions:
    peak_loc = load_sar_results(direction)["peak_sar_location"]
    candidate_points.append(peak_loc)

# Evaluate magnitude sum only at these candidate points (+ neighbors)
for point in candidate_points:
    score = sum(|E_i(point)| for each direction)
    
# Best candidate is likely near the true optimum
```
Leverages already-computed SAR peaks as starting points.

**3. Progressive Pruning**
```python
# After loading each direction, prune voxels that can't beat current best
best_so_far = 0
active_mask = np.ones((Nx, Ny, Nz), dtype=bool)  # All voxels active

for i, h5_path in enumerate(h5_files):
    E_mag = load_magnitude(h5_path)
    magnitude_sum[active_mask] += E_mag[active_mask]
    
    # Upper bound: current sum + max possible from remaining directions
    remaining = N - i - 1
    max_possible = magnitude_sum + remaining * E_mag.max()
    
    # Prune voxels that can't possibly win
    active_mask &= (max_possible > best_so_far)
    best_so_far = max(best_so_far, magnitude_sum[active_mask].max())
```
Progressively eliminates voxels that can't beat the current best.

**4. Skin-Only + Spatial Clustering**
Since SAPD cares only about skin, and skin surfaces have spatial coherence:
```python
# Cluster skin voxels into ~100 regions
skin_clusters = spatial_clustering(skin_voxels, n_clusters=100)

# Evaluate one representative per cluster (fast)
cluster_scores = []
for cluster in skin_clusters:
    rep = cluster.centroid
    score = sum(|E_i(rep)| for each direction)
    cluster_scores.append(score)

# Only do full search in top-k clusters
top_clusters = argsort(cluster_scores)[-5:]
fine_search(top_clusters)
```

**Recommendation**: Start with **Skin-Only + Coarse-to-Fine**. This reduces search space by 100× (skin vs volume) and another 10-100× (coarse grid), making it tractable even for large phantoms.

#### 2.2.8 Extracting Skin Voxel Locations from H5 Files

**Good news: Tissue voxel data IS available in the `_Input.h5` files!**

The H5 file contains:
```
Meshes/<mesh_id>/voxels          # (Nx, Ny, Nz) uint16 array of tissue IDs
Meshes/<mesh_id>/id_map          # (N_tissues, 16) bytes - UUID per tissue ID  
AllMaterialMaps/<grp>/<uuid>/Property_*/_Object  # Has material_name attribute
```

**Extraction algorithm:**

```python
import h5py
import numpy as np

def extract_skin_voxels(input_h5_path):
    with h5py.File(input_h5_path, 'r') as f:
        # 1. Build UUID -> material_name mapping
        uuid_to_name = {}
        def find_mats(name, obj):
            if hasattr(obj, 'attrs') and 'material_name' in obj.attrs:
                mat_name = obj.attrs['material_name'].decode('utf-8')
                uuid_str = name.split('/')[2]  # Extract UUID from path
                uuid_to_name[uuid_str] = mat_name
        f.visititems(find_mats)
        
        # 2. Get voxel grid and ID mapping
        for mesh_key in f['Meshes'].keys():
            mesh = f[f'Meshes/{mesh_key}']
            if 'voxels' not in mesh:
                continue
                
            voxels = mesh['voxels'][:]
            id_map = mesh['id_map'][:]
            axis_x = mesh['axis_x'][:]
            axis_y = mesh['axis_y'][:]
            axis_z = mesh['axis_z'][:]
            
            # 3. Map voxel IDs to tissue names
            voxel_id_to_name = {}
            for i in range(len(id_map)):
                h = ''.join(f'{b:02x}' for b in id_map[i])
                uuid_str = f'{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:]}'
                if uuid_str in uuid_to_name:
                    voxel_id_to_name[i] = uuid_to_name[uuid_str]
            
            # 4. Find skin voxel IDs
            skin_ids = [i for i, name in voxel_id_to_name.items() 
                        if 'skin' in name.lower()]
            
            # 5. Create skin mask
            skin_mask = np.isin(voxels, skin_ids)
            
            return skin_mask, axis_x, axis_y, axis_z
```

**Tested on actual data:**
- Skin (ID 26): 87,485 voxels
- Ear_skin (ID 56): 755 voxels  
- Total skin surface: ~88,000 voxels (vs 8.2M total phantom voxels)

This is **100× smaller** than the full volume - exactly what we need for efficient worst-case search!




---


## 3. Implementation Options - Deep Dive

The fundamental challenge is: **GOLIAT's architecture is built around the assumption that one simulation produces one H5 output, which then gets extracted once.**

Auto-induced exposure breaks this: we need to:
1. Run N simulations (one per direction)  
2. Combine N H5 files into one synthetic H5
3. Extract from the combined result

This doesn't map cleanly to the existing Setup → Run → Extract phases.

---

### 3.1 Option A: Standalone Post-Processing Script

**Description**: A new Python script that runs *after* all environmental far-field simulations complete. Completely outside GOLIAT's study framework.

**Workflow**:
```
[User runs: goliat study far_field_tessellation_config.json]
    → Runs N simulations (environmental mode - already works!)
    → Produces N result directories with _Output.h5 files

[User runs: python scripts/combine_focused_far_field.py --config X --focus Z]
    → Reads N _Output.h5 files
    → Computes MRT weights
    → Writes combined_Output.h5
    → Calls SAR extraction (reimplemented or via S4L API)
    → Writes sar_results.json, etc.
```

**Sub-phases**:
1. **H5 Discovery**: Find all `_Output.h5` files matching the tessellation config
2. **Grid Alignment**: Verify all H5 files have the same mesh (they should, same phantom/freq)
3. **Channel Matrix**: Extract E_z at focus point from each H5
4. **MRT Computation**: `W = H^H / ||H^H||_F`
5. **Weighted Combination**: For each voxel: `E_combined += W[i] * E_i`
6. **H5 Write**: Write combined field to new H5 file
7. **SAR Extraction**: Either reimplemeent or use Sim4Life API

**Challenges**:

1. ❌ **SAR extraction dependency on Sim4Life project**: The current `SarExtractor` uses `simulation.Results()["Overall Field"]` which requires an open Sim4Life project with a simulation object. A synthetic H5 file won't have this - we'd need to either:
   - Create a dummy Sim4Life project and load the H5 into it
   - Reimplement SAR calculation from scratch (get tissue ID grid, compute |E|²σ/2ρ)
   
2. ❌ **No integration with verify-and-resume**: The caching system wouldn't know about this script. Running it twice would redo all work.

3. ❌ **Separate config/invocation**: User has to understand a second workflow.

4. ✅ **Doesn't touch GOLIAT core**: Safe, low risk of breaking existing functionality.

5. ✅ **Can be developed incrementally**: Start with proof-of-concept, iterate.

**Verdict**: Good for PoC, but not a production solution.

---

### 3.2 Option B: Integrated "auto_induced" Far-Field Type

**Description**: Add `far_field_setup.type = "auto_induced"` as a new mode that the study understands natively.

The question is: **What does "auto_induced" mean for setup/run/extract?**

#### The Problem with 3-Phase Model

Currently:
- **Setup**: Creates Sim4Life project, configures plane wave, materials, grid
- **Run**: Calls iSolve, produces `_Output.h5`
- **Extract**: Reads simulation results, computes SAR

For auto-induced with N directions:
- We need N FDTD simulations (one per direction)
- Then one combination step
- Then one extraction from the combined result

This is fundamentally a **2-level hierarchy**:
```
Level 1: N "environmental" simulations (each has setup/run/extract-raw-fields)
Level 2: 1 "combine + extract SAR" operation
```

#### Sub-Option B1: "auto_induced" as a Meta-Study

Make `auto_induced` trigger multiple environmental sims plus a combine step:

```python
# In FarFieldStudy._run_study():
if far_field_type == "auto_induced":
    # Phase 1: Run all environmental simulations
    for direction in tessellation_directions:
        for polarization in polarizations:
            self._run_single_simulation(...)  # Setup + Run only, no SAR extract yet
    
    # Phase 2: Combine and extract
    self._combine_and_extract_auto_induced(directions, polarization, focus_point)
```

**Challenges**:

1. ❌ **What about caching/resume?** If we crash after direction 50/100, how do we resume?
   - The environmental sims would have caching (they're normal sims)
   - But the combine step has no H5 file to cache on

2. ❌ **Results directory structure confusion**: Currently: `results/far_field/{phantom}/{freq}/environmental_{dir}_{pol}/`
   - Where does the auto_induced result go? `results/far_field/{phantom}/{freq}/auto_induced_{pol}/` ?
   - But that's only one directory, vs N environmental directories

3. ❌ **Profiler/GUI doesn't know about 2-level structure**: It shows "Simulation 1/100" but auto_induced is really "100 base sims + 1 combine"

4. ❌ **Extract phase meaning is confusing**: For environmental, extract = SAR from that sim. For auto_induced, "extract" = combine + SAR.

#### Sub-Option B2: Separate "combine" Study Type

Create a new `FocusedExposureStudy` that operates on existing environmental results:

```python
class FocusedExposureStudy(BaseStudy):
    """Combines environmental far-field results with MRT for focused exposure."""
    
    def _run_study(self):
        # No setup phase (no Sim4Life project to create)
        # No run phase (no FDTD simulation)
        # Only "combine" and "extract"
        
        for phantom, freq, polarization in product(...):
            self._combine_focused_exposure(phantom, freq, polarization)
```

**Challenges**:

1. ❌ **Doesn't fit BaseStudy's 3-phase model**: There's no simulation object to pass around. `_execute_run_phase()` expects a `s4l_v1.simulation.emfdtd.Simulation`.

2. ❌ **ProfileManager expects setup/run/extract**: Would need to rework profiling

3. ❌ **Config structure**: How do you specify "combine results from config X"? A new config type?

4. ✅ **Clear separation**: It's obvious this is a post-processing step

---

### 3.3 Option C: Hybrid Approach with New CLI Command

**Description**: Environmental simulations run normally, then a new `goliat combine` command does the combination.

**Workflow**:
```
[User runs: goliat study far_field_tessellation_config.json]
    → Runs N simulations as normal
    → Results in results/far_field/{phantom}/{freq}/environmental_{dir}_{pol}/

[User runs: goliat combine far_field_tessellation_config.json --focus 0.1,0.2,0.3]
    → Finds all matching results
    → Loads E-fields, computes MRT, combines
    → Writes to results/far_field/{phantom}/{freq}/auto_induced_{pol}/
    → Runs extraction
```

**Sub-phases for `goliat combine`**:
1. **Discovery**: Parse config, find all environmental result directories
2. **Validation**: Check all expected H5 files exist
3. **Field Loading**: Load E-field arrays from each H5
4. **MRT Computation**: Compute channel matrix and weights
5. **Combination**: Weighted sum of complex fields
6. **H5 Synthesis**: Write combined_Output.h5
7. **Extraction**: Either:
   - Create minimal Sim4Life project with the synthetic H5
   - Or reimplement SAR calculation

**Challenges**:

1. ❌ **Still has SAR extraction problem**: Same as Option A - how do we extract SAR without a real simulation?

2. ❌ **Two-step user workflow**: User must remember to run `combine` after `study`

3. ✅ **Clean separation**: Each command does one thing well

4. ✅ **Config reuse**: Same config for both commands, `combine` just reads different parts

5. ✅ **Could integrate with caching**: `combine` could write its own `config.json` metadata

---

### 3.4 Option D: Environmental Simulations Save Raw E-fields, New Extractor Combines

**Description**: Modify environmental extraction to save raw E-field arrays (not just SAR). Then a "FocusedSarExtractor" reads all raw fields and produces the combined SAR.

**Workflow**:
```
[Environmental simulation extracts to:]
results/far_field/{phantom}/{freq}/environmental_{dir}_{pol}/
    sar_results.json       # Normal SAR (already exists)
    raw_e_field.npz        # NEW: Complex E-field array (Nx, Ny, Nz, 3)
    raw_mesh.npz           # NEW: axis_x, axis_y, axis_z arrays

[New FocusedSarExtractor reads all raw_e_field.npz files, combines, computes SAR]
```

**Advantages**:
1. ✅ **SAR is computed directly from E-field**: No need for Sim4Life, just `SAR = σ|E|²/(2ρ)`
2. ✅ **Raw fields are smaller than full H5**: Only E, not H or all the Sim4Life metadata
3. ✅ **Can be incremental**: As each environmental sim finishes, its raw field is saved

**Challenges**:

1. ❌ **Massive storage requirements**: Raw E-fields are still huge (50+ GB per direction)
   - 100 directions × 50 GB = 5 TB per phantom/frequency combo 😱
   - Maybe compress? Complex float32 doesn't compress well...

2. ❌ **Need tissue ID grid**: To compute SAR, we need to know which voxel is which tissue. This requires either:
   - Saving tissue ID grid separately (once per phantom/freq - not huge)
   - Accessing the original H5 file

3. ❌ **Modifies environmental extraction**: Existing code changes

4. ✅ **Most mathematically clean**: E_combined = Σ w_i E_i, then SAR = σ|E_combined|²/(2ρ)

---

### 3.5 Option E: Keep H5 Files, Memory-Map During Combination

**Description**: Don't save separate .npz files. The environmental `_Output.h5` files already contain the E-fields. During combination, memory-map them and process chunk-by-chunk.

**Key insight**: We don't need to load all N fields into memory at once. We can:
```python
E_combined = np.zeros((Nx, Ny, Nz, 3), dtype=np.csingle)

for z_chunk in range(0, Nz, chunk_size):
    for i, h5_path in enumerate(h5_paths):
        with h5py.File(h5_path, 'r') as f:
            E_chunk = f['FieldGroups/.../EM E'][..., z_chunk:z_chunk+chunk_size]
            E_combined[..., z_chunk:z_chunk+chunk_size] += weights[i] * E_chunk
```

This is O(chunk_size) memory instead of O(N × full_grid).

**Workflow**:
- Environmental simulations run as normal, keep their H5 files (no auto-cleanup!)
- Combination phase uses chunked processing
- Write combined_Output.h5 using same chunked approach

**Challenges**:

1. ❌ **H5 files must be kept**: Can't use auto-cleanup, disk space grows
2. ❌ **Slow disk I/O**: For 100 directions, we read each H5 file once per chunk. That's a lot of disk seeks.
3. ✅ **Memory efficient**: Only one chunk in memory at a time
4. ✅ **No code change to environmental sims**: They already produce the H5 files we need

---

### 3.6 Option F: Compute SAR Without Sim4Life (The Nuclear Option)

**Description**: Given the combined E-field and the tissue property grid, compute SAR ourselves:

```
SAR(r) = σ(r) × |E(r)|² / (2 × ρ(r))
```

Where:
- `σ(r)` = electrical conductivity at location r [S/m]
- `ρ(r)` = mass density at location r [kg/m³]
- `E(r)` = electric field at location r [V/m]

**What we need**:
1. Combined E-field (we compute this from MRT)
2. Conductivity grid: Can be extracted from Sim4Life voxel data or computed from material assignment
3. Density grid: Same source
4. Tissue ID grid: For psSAR by tissue

**How to get σ(r) and ρ(r)**:

Looking at the H5 file structure, Sim4Life stores:
- Material assignment per voxel (in the _Input.h5 or via voxeler output)
- Material properties are in the database (we already have `material_cache.py` with conductivity/permittivity!)

**This could actually work:**
1. During environmental setup (first run only), save the tissue_id grid and material properties
2. During combination, use those to compute local SAR
3. For psSAR10g averaging, implement the averaging algorithm (it's documented in IEC standards)

**Challenges**:

1. ❌ **Reimplementing SAR averaging**: The 10g cube averaging is non-trivial (need to find cubes that maximize, handle boundaries, etc.)
2. ❌ **Validation**: How do we verify our SAR calculation matches Sim4Life's?
3. ✅ **No Sim4Life dependency for extraction**: Faster, could even run headless
4. ✅ **Most flexible**: We control everything

## 3.7 Revised Recommendation: Efficient Search + Sim4Life SAPD Extraction

**Key insight**: We won't reimplement SAPD computation (IEC standard compliance requires Sim4Life). But the tissue/voxel data enables massive efficiency gains in the **search and combination** phases.

### Revised Workflow

```
[Phase 1: Environmental Simulations]
    goliat study tessellation_config.json
    → N simulations produce N _Output.h5 files (keep them, no auto-cleanup)
    → Each also has _Input.h5 with tissue/voxel data

[Phase 2: Efficient Worst-Case Focus Point Search]
    1. Load skin mask from _Input.h5 (88k voxels, not 8M)
    2. For each direction's _Output.h5:
       - Load ONLY skin-region E-field slices (memory efficient)
       - Accumulate |E_i| at skin voxels only
    3. Find max(Σ|E_i|) → worst-case focus point on skin
    4. Compute optimal phases: φ_i = -arg(E_i(focus_point))

[Phase 3: Combine Fields at Focus Point]
    Option A: Full field combination (for Sim4Life SAPD)
        - Chunked processing: for each z-slab, combine weighted E-fields
        - Write combined_Output.h5 matching Sim4Life format
        - Use Sim4Life to compute SAPD on combined field
    
    Option B: Quick local SAPD estimate (for screening)
        - Only combine E-field in small region around focus point
        - Approximate SAPD ≈ |E_combined|² × σ_skin / 2
        - Use for rapid iteration, validate with full Sim4Life later

[Phase 4: SAPD Extraction via Sim4Life]
    - Load combined_Output.h5 into Sim4Life project
    - Use existing SapdExtractor (IEC-compliant)
    - Get proper SAPD statistics
```

### Why This Works

1. **Search efficiency**: Skin mask reduces search from 8M to 88k voxels (100×)
2. **Memory efficiency**: Only load skin-region E-field slices during search
3. **Phase-only math**: Optimal focus point search is just `argmax Σ|E_i|` - no phase optimization needed
4. **Sim4Life SAPD**: Keep IEC compliance, no reimplementation
5. **Tissue data available**: H5 files contain full voxel→tissue mapping

### Open Question: Loading Combined H5 into Sim4Life

The remaining challenge is: how do we feed the combined E-field back into Sim4Life for SAPD extraction?

**Simpler approach: Create/modify an `_Output.h5` directly, then load with SimulationExtractor.**

#### How Sim4Life Loads Results

Looking at `SapdExtractor._setup_em_sensor_extractor()`:

```python
# Create extractor pointing to H5 file
sliced_extractor = analysis.extractors.SimulationExtractor(inputs=[])
sliced_extractor.FileName = h5_path  # Our combined field H5
sliced_extractor.UpdateAttributes()

# Access the "Overall Field" sensor
em_sensor_extractor = sliced_extractor["Overall Field"]

# Get Poynting vector output
S_output = em_sensor_extractor.Outputs["S(x,y,z,f0)"]
```

This means we need to create an H5 file with the right structure that `SimulationExtractor` can read.

#### Approach: Copy Template, Replace Field Data

1. **Copy an existing `_Output.h5`** from one of the environmental simulations
2. **Locate the E/H field datasets** (in FieldGroups after sim runs)
3. **Replace the field values** with our combined fields
4. **Load into Sim4Life** using `SimulationExtractor`
5. **Run SAPD extraction** as usual

The key advantage: we don't need to understand the full H5 structure, just replace the field data arrays while keeping all metadata intact.

#### Implementation Sketch

```python
import h5py
import shutil

def create_combined_output_h5(template_h5_path, output_path, E_combined, H_combined):
    """Create an _Output.h5 with combined field data."""
    
    # 1. Copy the template (from any completed environmental sim)
    shutil.copy(template_h5_path, output_path)
    
    # 2. Replace the field data
    with h5py.File(output_path, 'r+') as f:
        # Find FieldGroups -> Overall Field -> E/H data
        # Structure: FieldGroups/{id}/AllFields/EM E(x,y,z,f0)/_Object/Snapshots/0/comp{0,1,2}
        
        for fg_key in f['FieldGroups'].keys():
            fg = f['FieldGroups'][fg_key]
            if '_Object' in fg and fg['_Object'].attrs.get('name', b'') == b'Overall Field':
                # Found it!
                for field, data in [('EM E(x,y,z,f0)', E_combined), ('EM H(x,y,z,f0)', H_combined)]:
                    for dim, comp in enumerate(['comp0', 'comp1', 'comp2']):
                        path = f'AllFields/{field}/_Object/Snapshots/0/{comp}'
                        if path in fg:
                            ds = fg[path]
                            ds[:, :, :, 0] = np.real(data[dim])
                            ds[:, :, :, 1] = np.imag(data[dim])
```

**Prerequisite**: We need at least one completed environmental simulation to use as a template. The template provides all the metadata, mesh structure, and correct H5 layout.

#### Alternative: Create H5 from Scratch

If we don't have a completed simulation template, we'd need to reverse-engineer the full H5 structure. This is complex but doable - the key datasets are:

- `Meshes/{id}/axis_x, axis_y, axis_z` - grid coordinates
- `FieldGroups/{id}/AllFields/EM E(x,y,z,f0)/_Object/Snapshots/0/comp{0,1,2}` - E-field components
- `FieldGroups/{id}/_Object` attributes: `name` = "Overall Field"

The metadata and auxiliary structures can be copied from `_Input.h5` if needed.




---

## 4. Learnings from Hybridizer

The `hybridizer/simulation.py` code already implements exactly what we need:

### 4.1 Channel Matrix & MRT

```python
# From DeterministicSimulation.compute_channel_matrix
self.channel_matrix = np.matrix(np.empty((N_receivers, N_transmitters), dtype=np.csingle))
# ... fills in with E-field at receiver locations

# From compute_precoding_matrix
if scheme == 'MRT':
    self.precoding_matrix = self.channel_matrix.H  # Conjugate transpose
self.precoding_matrix /= np.linalg.norm(self.precoding_matrix, 'fro')
```

### 4.2 Weighted Combination

```python
# From DeterministicSimulation.focus
for tx, weight in zip(self.radiating_collection.elements, weights):
    self.E += weight * tx.E
    self.H += weight * tx.H
```

### 4.3 Memory-Efficient Approach

```python
# From efficient_cluster_addition - process one source at a time
for tx in tqdm(self.radiating_collection.elements):
    tx.compute_fields(self)
    self.E += tx.E
    tx.clear_unimportant_data(also_clear_fields=True)  # Free memory immediately
```

---

## 5. H5 File Structure (Sim4Life)

Based on `h5_slicer.py` and `exposure_simulation.py`:

```
_Output.h5
├── Meshes/
│   └── <mesh_id>/
│       ├── axis_x    [N_x floats]
│       ├── axis_y    [N_y floats]  
│       ├── axis_z    [N_z floats]
│       └── _Object/  (attributes: mesh_name, etc.)
├── FieldGroups/
│   └── <field_group_id>/
│       └── AllFields/
│           └── EM E(x,y,z,f0)/
│               └── _Object/
│                   └── Snapshots/
│                       └── 0/
│                           ├── comp0   [Nx-1, Ny, Nz, 2] (real, imag) - Ex
│                           ├── comp1   [Nx, Ny-1, Nz, 2] - Ey
│                           └── comp2   [Nx, Ny, Nz-1, 2] - Ez
└── bounding_box   [2 ints: start, end]
```

**Key insight**: The field data is stored as separate real/imag components in the last dimension. Components have different shapes due to Yee grid staggering.

---

## 6. Feasibility Assessment

### 6.1 What's Already Done
- ✅ Spherical tessellation of directions (just implemented!)
- ✅ Far-field plane wave simulations work
- ✅ H5 file handling utilities exist (h5_slicer)
- ✅ SAR extraction pipeline is robust
- ✅ Hybridizer shows MRT math works

### 6.2 What Needs to Be Built

| Component | Difficulty | Notes |
|-----------|------------|-------|
| H5 E-field reader | ⭐⭐ | Adapt from h5_slicer patterns |
| Channel matrix builder | ⭐ | Simple: read E_z at one voxel |
| MRT precoding | ⭐ | 3 lines of numpy |
| Weighted combination | ⭐⭐⭐⭐ | Memory is the hard part |
| SAR calculation (local) | ⭐⭐ | Well-defined formula |
| psSAR10g averaging | ⭐⭐⭐ | Algorithm complexity |
| Tissue ID grid extraction | ⭐⭐ | From _Input.h5 or voxeler |

### 6.3 Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Memory overflow | High | High | Chunked processing, memmap |
| H5 format mismatch | Medium | Medium | Test with small cases first |
| SAR calculation differs from S4L | Medium | Medium | Validate against known cases |
| Results not physically meaningful | Low | High | Validate against literature/theory |

---

## 7. Recommended Path Forward

### Phase 1: Proof of Concept (1-2 weeks)
1. Create a test case with 4-6 directions (minimal tessellation)
2. Write a standalone script that:
   - Reads E-field from each H5
   - Picks an arbitrary focus point
   - Computes MRT weights
   - Combines fields (in-memory for small case)
   - Computes local SAR manually
3. Verify the focused SAR is higher than environmental average

### Phase 2: Memory Optimization (1 week)
1. Implement chunked processing
2. Test with full-body phantom at moderate frequency (700 MHz)
3. Benchmark memory usage and processing time

### Phase 3: Integration (1-2 weeks)
1. Add `goliat combine` CLI command  
2. Integrate with extraction pipeline
3. Auto-detect focus point options (peak environmental SAR, etc.)
4. Add config options and documentation

### Phase 4: Validation (1 week)
1. Compare with literature on MaMIMO exposure
2. Verify power normalization is correct
3. Test at multiple frequencies and tessellation densities

---

## 8. Resolved Questions & Decisions

| Question | Answer |
|----------|--------|
| **Metric** | Peak SAPD on skin surface (not wbaSAR) |
| **Tessellation density** | 6-50 directions |
| **Weighting** | Phase-only with equal amplitudes: `w_i = (1/√N) × exp(jφ_i)` |
| **Power normalization** | Automatic from equal amplitude constraint |
| **SAPD computation** | Keep in Sim4Life (IEC compliance) |
| **Worst-case search** | Efficient O(N) algorithm: `argmax Σ|E_i|` over skin voxels |
| **Skin voxel extraction** | Available from `_Input.h5` via voxel→tissue ID mapping |

## 9. Concrete Next Steps

### Immediate (Next Session)
1. **Run spherical tessellation simulations to completion** (need at least 6 directions)
2. **Inspect completed `_Output.h5` structure** to understand FieldGroups layout
3. **Write PoC script** that:
   - Loads skin mask from `_Input.h5`
   - Reads E-field at skin voxels from each direction's `_Output.h5`
   - Computes `Σ|E_i|` to find worst-case focus point
   - Computes optimal phases

### Phase 2
4. **Combine full E/H fields** with optimal weights
5. **Create combined `_Output.h5`** from template
6. **Test SAPD extraction** using Sim4Life on combined file

### Future Integration
7. Add `goliat combine` CLI command
8. Integrate with caching system
9. Documentation and validation


---

## 10. References & Resources

- `hybridizer/simulation.py`: `DeterministicSimulation.compute_channel_matrix`, `focus`
- `goliat/utils/h5_slicer.py`: H5 file structure, axis handling
- `goliat/extraction/sapd_extractor.py`: How to reload extractors from H5
- `goliat/setups/far_field_setup.py`: Spherical tessellation implementation
- IEC/IEEE 63195-2:2022: SAPD evaluation standards

---

*Document created: 2026-01-08*
*Last updated: 2026-01-08*
