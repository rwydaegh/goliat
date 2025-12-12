# Multi-Sine Frequency Grouping: Practical Math for Your Frequencies

## Your Frequencies

From `near_field_config.json` and `far_field_config.json`:

```
450, 700, 835, 1450, 2140, 2450, 3500, 5200, 5800 MHz
```

That's **9 frequencies** × phantoms × placements × orientations = **a lot of simulations**.

---

## The Core Question: What Limits How Many Frequencies You Can Group?

### Constraint 1: Beat Period (Simulation Time)

When you combine sinusoids, beats occur at the *difference frequencies*. The simulation must run long enough for the beat pattern to establish steady-state.

**Rule of thumb**: Need at least 3-5 beat periods to reach steady-state.

**Minimum simulation time**:
```
T_sim ≈ 5 / f_beat_min = 5 / min(|fᵢ - fⱼ|)
```

### Constraint 2: Grid Resolution (The Physics Killer)

**THIS IS THE BIG CATCH:**

FDTD grid step must resolve the **highest frequency** in the signal:
```
Δx ≤ λ_min / N  where N = 10-20 points per wavelength
```

If you group 700 MHz with 5800 MHz:
- λ(700 MHz) = 428 mm
- λ(5800 MHz) = 52 mm

Your grid step is set for the **highest frequency** in the group!

From your config, you already have different grid steps per frequency:
```json
"global_gridding_per_frequency": {
    "450": 2.5 mm,
    "700": 2.5 mm,
    "835": 2.5 mm,
    "1450": 2.5 mm,
    "2140": 1.694 mm,
    "2450": 1.482 mm,
    "3500": 1.0 mm,
    "5200": 1.0 mm,
    "5800": 1.0 mm
}
```

**Implication**: If you group 700 MHz + 5800 MHz, you must use 1.0 mm grid step for the entire simulation (the finest grid), which MASSIVELY increases computational cost.

### Constraint 3: Antenna Model (More Physics)

Look at your `antenna_config`:
- 700, 835 MHz → PIFA antenna
- 1450, 2140, 2450, 3500, 5200, 5800 MHz → IFA antenna

**You cannot mix different antenna models in one simulation!**

Each antenna is tuned for specific frequencies. A PIFA operating at 5800 MHz won't behave realistically.

---

## Practical Grouping Analysis

### Group by Antenna Type (MANDATORY)

**PIFA Group**: 700, 835 MHz  
**IFA Group**: 1450, 2140, 2450, 3500, 5200, 5800 MHz

### Within Each Group: Grid Compatibility

**PIFA Group (700, 835 MHz)**:
- Both use 2.5 mm grid step ✅
- Can be grouped without grid penalty

**IFA Group**:
| Frequency | Grid Step | Can group with... |
|-----------|-----------|-------------------|
| 1450 MHz  | 2.5 mm    | 1450 only (2.5mm) |
| 2140 MHz  | 1.694 mm  | 2140-2450 (similar) |
| 2450 MHz  | 1.482 mm  | 2140-2450 |
| 3500 MHz  | 1.0 mm    | 3500-5800 |
| 5200 MHz  | 1.0 mm    | 3500-5800 |
| 5800 MHz  | 1.0 mm    | 3500-5800 |

---

## Beat Period Calculations

### PIFA Group: 700 + 835 MHz

```
f_beat = |835 - 700| = 135 MHz
T_beat = 1/135 MHz = 7.4 ns
T_sim = 5 × T_beat = 37 ns
```

Compare to: 2 × ~5 ns = 10 ns (two harmonic runs)

**Overhead**: 37 ns / 10 ns = **3.7× longer per sim**

But you get 2 frequency results from 1 sim, so:
- **Total work**: 37 ns (multi-sine) vs 10 ns (2× harmonic)
- **Speedup**: None! Actually 3.7× slower!

Wait, that doesn't seem right. Let me reconsider...

Actually, the 5 ns harmonic time is for the EM wave to propagate and establish steady-state. The multi-sine beat period constraint is **additional** to propagation.

**Revised calculation**:
- Propagation time: ~5 ns (both cases)
- Harmonic: 5 ns × 2 runs = 10 ns total wall clock
- Multi-sine: ~5 ns propagation + 37 ns beats = ~40 ns wall clock

**Verdict for PIFA group**: NOT WORTH IT for this frequency pair (135 MHz is too close to low frequency = long beat period relative to base time).

### IFA High-Frequency Group: 3500 + 5200 + 5800 MHz

```
Beat frequencies:
|5200 - 3500| = 1700 MHz → T = 0.59 ns
|5800 - 3500| = 2300 MHz → T = 0.43 ns
|5800 - 5200| = 600 MHz  → T = 1.67 ns

T_beat_slowest = 1.67 ns
T_sim ≈ 5 × 1.67 = 8.4 ns
```

Compare to: 3 × ~5 ns = 15 ns (three harmonic runs)

**This looks better!**

- Multi-sine: ~8.4 ns (one sim, 3 frequencies)
- Harmonic: ~15 ns (three sims)
- **Speedup**: 15/8.4 = **1.8×** 

Grid penalty: All three use 1.0 mm, so none!

### IFA Mid-Frequency: 2140 + 2450 MHz

```
f_beat = |2450 - 2140| = 310 MHz
T_beat = 3.2 ns
T_sim ≈ 5 × 3.2 = 16 ns
```

Compare to: 2 × ~5 ns = 10 ns

**Speedup**: 10/16 = **0.625× (SLOWER!)**

---

## The Math Summary

Let me calculate this properly with a general formula:

### Time for N Harmonic Simulations
```
T_harmonic_total = N × T_harmonic_single ≈ N × 5 ns
```

### Time for N-frequency Multi-Sine Simulation
```
T_multisine = max(T_propagation, 5 × T_beat_slowest)
            = max(5 ns, 5 / min(|fᵢ - fⱼ|))
```

### Condition for Multi-Sine to be Faster
```
T_multisine < N × T_harmonic_single
5 / min(Δf) < N × 5 ns
1 / min(Δf) < N ns
min(Δf) > 1/N GHz = 1000/N MHz
```

**Rule**: Multi-sine is faster when the minimum frequency difference exceeds `1000/N MHz`.

| N frequencies | min(Δf) required |
|---------------|------------------|
| 2 | > 500 MHz |
| 3 | > 333 MHz |
| 4 | > 250 MHz |
| 5 | > 200 MHz |

---

## Applying to Your Frequencies

### PIFA: 700 + 835 MHz
- Δf = 135 MHz
- Need Δf > 500 MHz for 2-group
- **FAILS** ❌

### IFA Low-Mid: 1450 + 2140 + 2450 MHz
- Minimum Δf = |2450-2140| = 310 MHz
- Need Δf > 333 MHz for 3-group
- **FAILS** (barely) ❌

But wait, let's check 2-groups:
- 1450 + 2140: Δf = 690 MHz > 500 MHz ✅
- 2140 + 2450: Δf = 310 MHz < 500 MHz ❌
- 1450 + 2450: Δf = 1000 MHz > 500 MHz ✅

### IFA High: 3500 + 5200 + 5800 MHz
- Minimum Δf = |5800-5200| = 600 MHz
- Need Δf > 333 MHz for 3-group
- **PASSES** ✅

---

## Grid Penalty Consideration

Even when beat periods allow grouping, different grid requirements may cancel the benefit:

**Example: 1450 + 3500 MHz**
- Beat: Δf = 2050 MHz > 500 MHz ✅
- Grid: 1450 uses 2.5 mm, 3500 uses 1.0 mm
- If combined: must use 1.0 mm throughout

Grid cells scale as:
```
N_cells ∝ (1/Δx)³
```

Going from 2.5 mm to 1.0 mm:
```
Penalty = (2.5/1.0)³ = 15.6×
```

**The 1.8× speedup from grouping is completely destroyed by the 15.6× grid penalty!**

---

## Final Recommendations

### Viable Multi-Sine Groups (minimal overhead):

| Group | Frequencies | Δf_min | Grid | Speedup |
|-------|------------|--------|------|---------|
| High-freq IFA | 3500, 5200, 5800 | 600 MHz | 1.0 mm (same) | **~1.8×** |

### NOT Worth Grouping:

| Pair/Group | Reason |
|------------|--------|
| 700 + 835 | Beat period too slow (Δf = 135 MHz) |
| Any PIFA + IFA | Different antennas! |
| 1450 + 2140 | Grid penalty (2.5→1.7 mm) |
| 2140 + 2450 | Beat period marginal (Δf = 310 MHz) |
| Any low + high freq | Massive grid penalty |

### Practical Strategy

For your 9 frequencies:

**Run separately (8 simulations)**:
- 450 MHz (PIFA? or standalone)
- 700 MHz (PIFA)
- 835 MHz (PIFA)  
- 1450 MHz (IFA)
- 2140 MHz (IFA)
- 2450 MHz (IFA)

**Group into 1 simulation (saves 2 simulations)**:
- [3500 + 5200 + 5800] MHz (IFA, all 1.0 mm grid)

**Total**: 8 + 1 = 9 simulations → **7 simulations** (22% reduction)

That's not as dramatic as I hoped, but for your full matrix:
- 9 freqs × 4 phantoms × 3 placements × 6 orientations = 648 simulations
- With grouping: 7 × 4 × 3 × 6 = 504 simulations
- **Savings: 144 simulations (~22%)**

---

## Alternative: Cherry-Pick for Specific Studies

If you only need a subset of frequencies for certain phantoms/placements, the grouping math changes.

For example, if you only care about "telecom bands":
- 700, 1800, 2600 MHz (LTE bands)

```
Δf_min = |1800-700| = 1100 MHz > 333 MHz ✅
```

This WOULD work... if they used the same antenna model and similar grids.

---

## Conclusion

**Multi-sine grouping is marginally useful for your current setup:**

1. **Only viable group**: 3500 + 5200 + 5800 MHz (~1.8× speedup, 22% fewer sims overall)
2. **Main blockers**: Different antenna models, different grid requirements, close frequencies
3. **The grid penalty is brutal**: Mixing grids often costs more than you save

**Better speedup strategies** (if you haven't already):
1. Cloud parallelization (run all harmonic sims in parallel)
2. Reduce phantom/placement combinations where scientifically appropriate
3. Coarser grids for exploratory runs, fine grids for final results

---

*Calculations based on T_propagation ≈ 5 ns and 5 beat periods for steady-state. Actual values may vary with phantom size and convergence criteria.*

---

## CORRECTION: Far-Field Analysis (You're Right!)

### Far-Field is Different!

For **far-field simulations**, the constraints I listed for near-field **don't apply**:

1. ✅ **No antenna models** - Plane wave excitation is the same for all frequencies
2. ✅ **Grid already paid for** - You MUST use the finest grid (1.0 mm for 5800 MHz) regardless
3. ✅ **Same phantom setup** - No placement/orientation complexity per frequency

**The ONLY constraint is beat period!**

### Recalculating for Far-Field

Your frequencies: `450, 700, 835, 1450, 2140, 2450, 3500, 5200, 5800 MHz`

Since we're already paying for 1.0 mm grid (for 5800 MHz), let's see what groupings are possible:

#### All 9 Frequencies in One Simulation?

```
Frequencies: 450, 700, 835, 1450, 2140, 2450, 3500, 5200, 5800 MHz

Minimum frequency difference: |700 - 450| = 250 MHz
                              |835 - 700| = 135 MHz  ← SMALLEST
                              
T_beat_slowest = 1 / 135 MHz = 7.4 ns
T_sim ≈ 5 × 7.4 ns = 37 ns
```

Compare to 9 separate harmonic runs: 9 × 5 ns = 45 ns

**Speedup: 45/37 = 1.2×** (but only 1 simulation instead of 9!)

Actually wait - the simulation time for each harmonic isn't just 5 ns, let me think about this more carefully...

### Correct Time Analysis

For far-field with full-body phantom (L_bbox ~ 2m diagonal):
```
T_propagation = L_bbox / c = 2.0 m / 3×10⁸ m/s = 6.7 ns
With multiplier (3.5×): T_harmonic ≈ 23 ns per simulation
```

For 9 frequencies:
- **Harmonic approach**: 9 × 23 ns = 207 ns total (but could parallelize)
- **Multi-sine (9 freqs)**: max(23 ns, 5 × 7.4 ns) = max(23 ns, 37 ns) = 37 ns

**If running serially**: 207 ns → 37 ns = **5.6× speedup!**
**If parallelized fully**: Same wall-clock, but **9× fewer GPU-hours**

### But What About Directions & Polarizations?

From your config:
```json
"incident_directions": ["x_pos", "x_neg", "y_pos", "y_neg", "z_pos", "z_neg"],
"polarizations": ["theta", "phi"]
```

That's 6 × 2 = 12 simulations per frequency per phantom.

**Current approach**: 9 freqs × 12 directions = 108 simulations per phantom
**Multi-sine approach**: 1 freq-group × 12 directions = 12 simulations per phantom

**Speedup: 9× fewer simulations!** (with ~1.6× longer per sim for beats)

**Net speedup: 9 / 1.6 ≈ 5.6×**

### Optimal Grouping Strategy

The 135 MHz gap (700-835) is the bottleneck. Options:

#### Option A: All 9 frequencies together
- T_beat = 37 ns (limited by 135 MHz gap)
- Speedup: ~5-6× vs serial harmonic
- Simplest to implement

#### Option B: Split by gap size
Group frequencies into clusters where min(Δf) is large:

**Group 1**: 450, 700 MHz
- Δf = 250 MHz → T_beat = 20 ns ✅

**Group 2**: 835, 1450, 2140, 2450 MHz  
- Minimum Δf = |2450-2140| = 310 MHz → T_beat = 16 ns ✅

**Group 3**: 3500, 5200, 5800 MHz
- Minimum Δf = 600 MHz → T_beat = 8.3 ns ✅

Total: 3 simulations per direction/polarization instead of 9
- Current: 108 sims per phantom
- Grouped: 36 sims per phantom
- **Speedup: 3×** (with minimal beat overhead)

#### Option C: Remove the bottleneck
If you could skip 835 MHz:

**8 frequencies without 835**: 450, 700, 1450, 2140, 2450, 3500, 5200, 5800
- Minimum Δf = |700-450| = 250 MHz → T_beat = 20 ns

Or skip 700 MHz:
- Minimum Δf = |835-450| = 385 MHz → T_beat = 13 ns

### Summary Table

| Strategy | Sims/phantom | Beat overhead | Net speedup |
|----------|-------------|---------------|-------------|
| All separate | 108 | 0 | 1× (baseline) |
| All 9 together | 12 | 1.6× | **5.6×** |
| 3 smart groups | 36 | 1.1× | **2.7×** |
| Skip 835, all 8 | 12 | 1.0× | **9×** |

### Grid Reality Check

You mentioned "we have to run 5800 anyway". Let's verify the grid situation:

For far-field, the grid must resolve the **shortest wavelength** in the signal:
- λ(5800 MHz) = 52 mm
- λ/20 = 2.6 mm per cell

Your config says 1.0 mm for 5800 MHz. If running multi-sine with all 9 frequencies, you still use 1.0 mm grid.

**There is NO additional grid penalty** - you're already paying for the finest grid!

### Conclusion: Far-Field Multi-Sine is VERY Worth It

For far-field:
- **5-9× fewer simulations** per phantom
- **No antenna model constraint**  
- **No additional grid penalty**
- **Only cost**: Slightly longer simulation time per run (~1.6× for beat periods)

**Recommended approach**: Group all 9 frequencies, or group into 3 clusters to minimize beat overhead.

| Phantom | Directions | Polarizations | Sims (old) | Sims (new) | Savings |
|---------|------------|---------------|------------|------------|---------|
| duke | 6 | 2 | 108 | 12-36 | **67-89%** |
| ella | 6 | 2 | 108 | 12-36 | **67-89%** |
| eartha | 6 | 2 | 108 | 12-36 | **67-89%** |
| thelonious | 6 | 2 | 108 | 12-36 | **67-89%** |
| **TOTAL** | - | - | **432** | **48-144** | **67-89%** |

That's potentially **400 fewer simulations** just for far-field!

---

## API Verification: Materials and Extraction

### Dispersive Materials: CONFIRMED ✅

From Sim4Life Python API (`EmFdtdMaterialSettings.eMaterialModel`):

```python
kConst             # Constant (frequency-independent)
kLinearDispersive  # Linear dispersive (frequency-dependent!) ← IT'IS uses this
kMetaMaterial      # Metamaterial
```

**What this means:**
- IT'IS database tissues use `kLinearDispersive` material model
- Each frequency in multi-sine signal sees correct ε(f) and σ(f)
- No special handling needed - FDTD solver does this automatically via ADE method

**Debye parameters available:**
```python
kDebyeAmplitude
kDebyeDamping  
kDebyeInfinityPermittivity
kDebyeStaticPermittivity
```

### ExtractedFrequencies: CONFIRMED ✅

From Sim4Life Python API (`FieldSensorSettings`):

```python
settings.ExtractedFrequencies = (2e9,)  # Single frequency
settings.ExtractedFrequencies = [1e9, 2e9, 3e9]  # Multiple frequencies
settings.ExtractedFrequencies = np.linspace(1e9, 3e9, 11)  # Range

settings.OnTheFlyDFT = True  # Enable frequency-domain extraction
settings.RecordingDomain = 'RecordInFrequencyDomain'  # Or 'RecordInFrequencyAndTimeDomain'
```

**Works with:**
- `FieldSensorSettings` (for SAR extraction)
- `FarFieldSensorSettings` (for radiation patterns)
- `InterpolatedFieldSensorSettings` (for point sensors)

### Implementation Path: CLEAR ✅

For multi-sine far-field:

1. **Source setup**: Use `ExcitationType = 'UserDefined'` with multi-sine expression
2. **Sensor setup**: Set `ExtractedFrequencies = [450e6, 700e6, ..., 5800e6]`
3. **Extraction**: DFT gives per-frequency SAR/field data automatically

---

## Final Summary

### For Far-Field (Primary Use Case)

| Aspect | Status |
|--------|--------|
| Physics feasible | ✅ Multi-sine is valid |
| Materials handle it | ✅ Dispersive models work automatically |
| Extraction supported | ✅ ExtractedFrequencies takes list |
| Grid penalty | ✅ None (already using finest grid) |
| Antenna constraint | ✅ None (plane wave source) |
| **Net speedup** | **~4× fewer simulations** |

### Recommended Implementation

**Far-field only** (for now):
- Group all 9 frequencies: `[450, 700, 835, 1450, 2140, 2450, 3500, 5200, 5800]` MHz
- Set `simulation_time_multiplier` to accommodate beat period (~2.2× current value)
- Use `ExtractedFrequencies` for per-frequency SAR extraction

**Result**: 
- 432 simulations → 48 simulations (89% reduction)
- ~2.2× longer per sim, but 9× fewer sims
- **Net: ~4× speedup**

---

*Document updated: 2025-12-12*
*API verification performed on Sim4Life Python API Reference*
