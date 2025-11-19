# Gaussian Pulse Timing and Frequency Resolution Analysis for FDTD Simulations

## Executive Summary

This document provides a detailed mathematical analysis of simulation time requirements and frequency resolution for Gaussian-modulated pulse excitations in FDTD simulations, specifically for near-field SAR studies in GOLIAT. The analysis reveals that:

1. **Pulse duration dominates**: For typical scenarios with bandwidths of 50-100 MHz and small-to-medium bounding boxes, the pulse duration (≈18-36 ns) dominates over propagation time (≈1-3 ns).

2. **Sim4Life performs automatic FFT**: The solver internally converts time-domain Gaussian pulse responses into frequency-domain data through post-processing, providing continuous frequency spectra.

3. **Frequency resolution is critical**: For detecting antenna detuning in narrowband antennas (10-30 MHz bandwidth, potential 50-100 MHz shift), frequency resolution Δf = 1/T_sim must be sufficiently fine (≈5 MHz or better).

4. **PML boundaries eliminate back-reflection**: With Perfectly Matched Layer boundaries, signals propagate forward and are absorbed, so 2× propagation time for reflections is NOT needed.

This comprehensive timing analysis ensures both adequate pulse duration for accurate FFT and sufficient simulation time for fine frequency resolution.

## Problem Statement

### Context

GOLIAT currently supports two excitation types:
- **Harmonic**: Single-frequency continuous wave excitation (standard for SAR compliance)
- **Gaussian**: Frequency-sweep excitation (currently only used for free-space antenna characterization)

We are extending Gaussian excitation support to near-field (phantom) simulations. A critical question arises: **How long must the simulation run to capture the complete Gaussian pulse response?**

### Current Implementation

The current simulation time calculation (`goliat/setups/base_setup.py`) uses a simple multiplier approach:

```python
time_multiplier = config["simulation_parameters.simulation_time_multiplier"]  # Default: 3.5
diagonal_length_m = np.linalg.norm(bbox_max - bbox_min) / 1000.0
time_to_travel_s = (time_multiplier * diagonal_length_m) / c
sim_time_periods = time_to_travel_s / (1 / (frequency_mhz * 1e6))
```

This approach assumes:
- The simulation needs `multiplier` times the time for a wave to traverse the bounding box diagonal
- For Harmonic excitation, this captures multiple cycles for convergence
- The multiplier (typically 3.5) provides sufficient time for steady-state behavior

### The Challenge

For Gaussian pulses, we must ensure:
1. The pulse propagates from source to all points in the domain
2. The pulse completes its full temporal evolution (ramp-up, peak, decay)
3. The response at the farthest point has time to develop

The current multiplier approach may be insufficient because it doesn't account for the finite pulse duration.

## Mathematical Model

### Gaussian-Modulated Pulse

A Gaussian-modulated pulse in the time domain is:

```
g(t) = A · exp(-(t - t₀)²/(2σ²)) · exp(i·2π·f₀·t)
```

Where:
- `A` = amplitude (arbitrary scaling)
- `t₀` = time shift (ramp-up delay to avoid sudden start)
- `σ` = temporal standard deviation (controls pulse width)
- `f₀` = center frequency (carrier frequency)

**Physical interpretation:**
- The Gaussian envelope `exp(-(t - t₀)²/(2σ²))` modulates the carrier wave
- The pulse is centered at time `t = t₀`
- The pulse width is controlled by `σ`

### Frequency Domain Representation

The Fourier transform of the Gaussian pulse is:

```
G(f) = A · σ · √(2π) · exp(-2π²σ²(f - f₀)²) · exp(-i·2π·f·t₀)
```

**Key properties:**
- The frequency spectrum is also Gaussian
- Centered at `f₀` (the carrier frequency)
- Frequency width inversely related to temporal width

### Relationship Between Temporal and Spectral Width

For a Gaussian pulse, the time-bandwidth product is fundamental:

**Temporal Full-Width at Half-Maximum (FWHM):**
```
Δt_FWHM = 2√(2 ln 2) · σ ≈ 2.35σ
```

**Frequency Full-Width at Half-Maximum (FWHM):**
```
Δf_FWHM = 2√(2 ln 2)/(2πσ) ≈ 0.94/(πσ)
```

**Time-bandwidth product:**
```
Δt_FWHM · Δf_FWHM = (2√(2 ln 2))²/(2π) ≈ 0.87
```

This is a fundamental limit: narrower pulses in time have wider frequency spectra, and vice versa.

### Relating to Configured Bandwidth

In GOLIAT, we configure:
- `BW` = bandwidth in MHz (e.g., 100 MHz)
- `f₀` = center frequency in MHz (e.g., 700 MHz)

The configured bandwidth `BW` represents the frequency range over which significant energy exists. We approximate:

```
Δf_FWHM ≈ BW
```

This allows us to solve for `σ`:

```
σ ≈ 0.94/(π·BW)
```

**Example:** For `BW = 100 MHz = 100×10⁶ Hz`:
```
σ ≈ 0.94/(π·100×10⁶) ≈ 3.0×10⁻⁹ s = 3.0 ns
```

## Pulse Duration Analysis

### Ramp-Up Delay (t₀)

To avoid numerical artifacts from a sudden start, FDTD solvers shift the Gaussian pulse so it starts near zero at `t = 0`:

```
g(0) ≈ 0
```

This requires:
```
exp(-(0 - t₀)²/(2σ²)) = exp(-t₀²/(2σ²)) ≈ 0
```

Solving for the threshold where the pulse is negligible:

**For 1% of peak amplitude:**
```
exp(-t₀²/(2σ²)) = 0.01
-t₀²/(2σ²) = ln(0.01) ≈ -4.61
t₀² = 9.22σ²
t₀ ≈ 3.0σ
```

**For 0.1% of peak amplitude (more conservative):**
```
exp(-t₀²/(2σ²)) = 0.001
-t₀²/(2σ²) = ln(0.001) ≈ -6.91
t₀² = 13.82σ²
t₀ ≈ 3.7σ
```

### Total Pulse Duration

The pulse has significant energy from `t = t₀ - k·σ` to `t = t₀ + k·σ`, where `k` determines the threshold.

**For k = 3 (1% threshold):**
- Left side: `k·σ` before peak
- Right side: `k·σ` after peak
- **Total duration:** `2k·σ = 6σ`

**For k = 3.7 (0.1% threshold, more conservative):**
- **Total duration:** `2k·σ = 7.4σ`

### Pulse Duration in Terms of Bandwidth

Substituting `σ ≈ 0.94/(π·BW)`:

**For k = 3:**
```
T_pulse = 2k·σ = 2·3·0.94/(π·BW) = 5.64/(π·BW) ≈ 1.80/BW
```

**For k = 3.7:**
```
T_pulse = 2k·σ = 2·3.7·0.94/(π·BW) = 6.96/(π·BW) ≈ 2.22/BW
```

**Examples:**
- `BW = 100 MHz`: `T_pulse ≈ 18.0 ns` (k=3) or `22.2 ns` (k=3.7)
- `BW = 50 MHz`: `T_pulse ≈ 36.0 ns` (k=3) or `44.4 ns` (k=3.7)
- `BW = 200 MHz`: `T_pulse ≈ 9.0 ns` (k=3) or `11.1 ns` (k=3.7)

## Required Simulation Time

### Two Time Components

For a complete simulation, we need:

1. **Propagation Time (`T_prop`)**: Time for the field to travel from source to the farthest point
   ```
   T_prop = L_bbox / c
   ```
   Where:
   - `L_bbox` = diagonal length of simulation bounding box (meters)
   - `c = 2.998×10⁸ m/s` = speed of light

2. **Pulse Wait Time (`T_pulse`)**: Time for the complete pulse to pass through
   ```
   T_pulse = 2k·σ ≈ 1.80/BW  (for k=3)
   ```

### Total Required Time

```
T_required = T_prop + T_pulse = L_bbox/c + 2k·σ
```

**Substituting:**
```
T_required = L_bbox/c + 1.80/BW  (for k=3)
```

or more conservatively:
```
T_required = L_bbox/c + 2.22/BW  (for k=3.7)
```

## Current Allocation vs. Required Time

### Current Implementation

The current code allocates:
```
T_allocated = multiplier · L_bbox/c
```

Where `multiplier = 3.5` (default from config).

### Comparison Logic

We need to check:
```
Is T_allocated ≥ T_required?
```

**Rearranging:**
```
multiplier · L_bbox/c ≥ L_bbox/c + 2k·σ
(multiplier - 1) · L_bbox/c ≥ 2k·σ
```

**If TRUE:** Current allocation is sufficient  
**If FALSE:** Current allocation is insufficient, need at least `T_required`

### Corrected Simulation Time Formula

The simulation time should be:

```
T_sim = max(multiplier · L_bbox/c, L_bbox/c + 2k·σ)
```

This ensures we always have sufficient time, taking the maximum of:
- The current multiplier-based approach (which may be sufficient for large bboxes)
- The explicit pulse duration requirement (which dominates for small bboxes)

## When Does Current Multiplier Fail?

### Failure Condition

The current multiplier approach fails when:

```
multiplier · L_bbox/c < L_bbox/c + 2k·σ
(multiplier - 1) · L_bbox/c < 2k·σ
L_bbox/c < 2k·σ/(multiplier - 1)
```

**For multiplier = 3.5, k = 3:**
```
L_bbox/c < 2·3·σ/2.5 = 2.4·σ
L_bbox < 2.4·c·σ
```

**Substituting σ:**
```
L_bbox < 2.4·c·0.94/(π·BW)
L_bbox < 0.72·c/BW
```

### Critical Bounding Box Sizes

**For BW = 100 MHz:**
```
L_bbox < 0.72 · 3×10⁸ / (100×10⁶) = 2.16 m
```

**For BW = 50 MHz:**
```
L_bbox < 0.72 · 3×10⁸ / (50×10⁶) = 4.32 m
```

**For BW = 200 MHz:**
```
L_bbox < 0.72 · 3×10⁸ / (200×10⁶) = 1.08 m
```

### Practical Implications

For typical near-field scenarios:
- Small antenna near head: `L_bbox ≈ 0.2-0.5 m`
- Medium setup with padding: `L_bbox ≈ 0.5-1.0 m`
- Large phantom with extensive padding: `L_bbox ≈ 1.0-2.0 m`

**Conclusion:** For typical near-field bboxes (< 1 m) and bandwidths (50-100 MHz), the current multiplier approach **fails** because the pulse duration term dominates.

## Detailed Examples

### Example 1: Small Bbox, 100 MHz Bandwidth

**Parameters:**
- `L_bbox = 0.3 m`
- `BW = 100 MHz`
- `f₀ = 700 MHz`
- `multiplier = 3.5`
- `k = 3`

**Calculations:**
```
T_prop = 0.3 / 3×10⁸ = 1.0×10⁻⁹ s = 1.0 ns
T_pulse = 1.80/(100×10⁶) = 18.0×10⁻⁹ s = 18.0 ns
T_required = 1.0 + 18.0 = 19.0 ns
T_allocated = 3.5 × 1.0 = 3.5 ns
```

**Result:** ❌ **FAILS** - `3.5 ns < 19.0 ns`

**Required simulation time:**
```
T_sim = max(3.5 ns, 19.0 ns) = 19.0 ns
N_periods = 19.0×10⁻⁹ / (1/(700×10⁶)) = 13.3 periods
```

### Example 2: Medium Bbox, 100 MHz Bandwidth

**Parameters:**
- `L_bbox = 0.5 m`
- `BW = 100 MHz`
- `multiplier = 3.5`
- `k = 3`

**Calculations:**
```
T_prop = 0.5 / 3×10⁸ = 1.67 ns
T_pulse = 18.0 ns
T_required = 1.67 + 18.0 = 19.67 ns
T_allocated = 3.5 × 1.67 = 5.84 ns
```

**Result:** ❌ **FAILS** - `5.84 ns < 19.67 ns`

**Required simulation time:**
```
T_sim = max(5.84 ns, 19.67 ns) = 19.67 ns
N_periods = 19.67×10⁻⁹ / (1/(700×10⁶)) = 13.8 periods
```

### Example 3: Large Bbox, 100 MHz Bandwidth

**Parameters:**
- `L_bbox = 1.0 m`
- `BW = 100 MHz`
- `multiplier = 3.5`
- `k = 3`

**Calculations:**
```
T_prop = 1.0 / 3×10⁸ = 3.33 ns
T_pulse = 18.0 ns
T_required = 3.33 + 18.0 = 21.33 ns
T_allocated = 3.5 × 3.33 = 11.67 ns
```

**Result:** ❌ **FAILS** - `11.67 ns < 21.33 ns`

**Required simulation time:**
```
T_sim = max(11.67 ns, 21.33 ns) = 21.33 ns
N_periods = 21.33×10⁻⁹ / (1/(700×10⁶)) = 14.9 periods
```

### Example 4: Small Bbox, 50 MHz Bandwidth

**Parameters:**
- `L_bbox = 0.3 m`
- `BW = 50 MHz`
- `multiplier = 3.5`
- `k = 3`

**Calculations:**
```
T_prop = 1.0 ns
T_pulse = 1.80/(50×10⁶) = 36.0 ns
T_required = 1.0 + 36.0 = 37.0 ns
T_allocated = 3.5 ns
```

**Result:** ❌ **FAILS** - `3.5 ns < 37.0 ns`

**Required simulation time:**
```
T_sim = max(3.5 ns, 37.0 ns) = 37.0 ns
N_periods = 37.0×10⁻⁹ / (1/(700×10⁶)) = 25.9 periods
```

### Example 5: Very Large Bbox, 100 MHz Bandwidth

**Parameters:**
- `L_bbox = 2.5 m`
- `BW = 100 MHz`
- `multiplier = 3.5`
- `k = 3`

**Calculations:**
```
T_prop = 2.5 / 3×10⁸ = 8.33 ns
T_pulse = 18.0 ns
T_required = 8.33 + 18.0 = 26.33 ns
T_allocated = 3.5 × 8.33 = 29.17 ns
```

**Result:** ✅ **PASSES** - `29.17 ns > 26.33 ns`

**Required simulation time:**
```
T_sim = max(29.17 ns, 26.33 ns) = 29.17 ns
N_periods = 29.17×10⁻⁹ / (1/(700×10⁶)) = 20.4 periods
```

## Key Insights

### 1. Pulse Duration Dominates for Small Bboxes

For typical near-field scenarios (`L_bbox < 1 m`), the pulse duration term (`T_pulse ≈ 18-36 ns`) is much larger than the propagation time (`T_prop ≈ 1-3 ns`). This means:

- The current multiplier approach is insufficient
- We must explicitly add the pulse duration term
- The pulse duration is independent of bbox size (depends only on bandwidth)

### 2. Bandwidth Has Strong Impact

Wider bandwidths mean shorter pulses, but the relationship is inverse:
- `BW = 50 MHz` → `T_pulse ≈ 36 ns`
- `BW = 100 MHz` → `T_pulse ≈ 18 ns`
- `BW = 200 MHz` → `T_pulse ≈ 9 ns`

For narrow bandwidths, pulse duration becomes even more dominant.

### 3. Conservative Threshold Matters

Using `k = 3.7` (0.1% threshold) instead of `k = 3` (1% threshold) increases pulse duration by ~23%:
- `k = 3`: `T_pulse = 1.80/BW`
- `k = 3.7`: `T_pulse = 2.22/BW`

For safety, we should use the more conservative value.

## Implementation Formula

### Corrected Code Logic

For Gaussian excitation, the simulation time calculation should be:

```python
# Calculate base propagation time
diagonal_length_m = np.linalg.norm(bbox_max - bbox_min) / 1000.0
T_prop = diagonal_length_m / c  # seconds, where c = 2.998×10⁸ m/s

if excitation_type == "Gaussian":
    # Get bandwidth from config
    bandwidth_mhz = config["simulation_parameters.bandwidth_mhz"] or 50.0
    bandwidth_hz = bandwidth_mhz * 1e6
    
    # Conservative threshold (0.1% of peak)
    k = 3.7
    
    # Calculate temporal standard deviation
    sigma = 0.94 / (np.pi * bandwidth_hz)  # seconds
    
    # Pulse duration (2k·σ)
    T_pulse = 2 * k * sigma  # seconds
    
    # Required time
    T_required = T_prop + T_pulse
    
    # Allocated time (current multiplier approach)
    multiplier = config["simulation_parameters.simulation_time_multiplier"] or 3.5
    T_allocated = multiplier * T_prop
    
    # Use the maximum
    T_sim = max(T_allocated, T_required)
    
    # Convert to periods
    sim_time_periods = T_sim / (1 / (frequency_mhz * 1e6))
    
    # Log the decision
    if T_required > T_allocated:
        log(f"  - Gaussian pulse duration ({T_pulse*1e9:.1f} ns) dominates over "
            f"propagation time ({T_prop*1e9:.1f} ns)")
        log(f"  - Using explicit pulse duration requirement: {T_sim*1e9:.1f} ns")
    else:
        log(f"  - Multiplier approach sufficient: {T_allocated*1e9:.1f} ns")
        
else:
    # Harmonic: use multiplier approach
    multiplier = config["simulation_parameters.simulation_time_multiplier"] or 3.5
    T_sim = multiplier * T_prop
    sim_time_periods = T_sim / (1 / (frequency_mhz * 1e6))
```

### Simplified Formula

For quick reference, the pulse duration can be approximated as:

```
T_pulse ≈ 2.22/BW  (for k=3.7, BW in Hz)
```

So the total required time is:

```
T_sim = max(multiplier · L_bbox/c, L_bbox/c + 2.22/BW)
```

## Frequency Extraction Context

### Extracted Frequencies

From `goliat/setups/source_setup.py`, for Gaussian sources:
- **Number of samples:** `N = 21`
- **Frequency spacing:** `Δf_sample = BW / (N - 1) = BW / 20`
- **Frequency range:** `[f₀ - BW/2, f₀ + BW/2]`

**Example:** For `f₀ = 700 MHz, BW = 100 MHz`:
- Frequencies: `650 MHz, 655 MHz, 660 MHz, ..., 745 MHz, 750 MHz`
- Spacing: `5 MHz`

### Antenna Detuning Consideration

Antennas are narrowband devices. If an antenna is tuned to `f₀` but excited at `f₀ ± Δf_detune`, the response is reduced. Typical mobile antennas have:
- Quality factor: `Q ≈ 10-50`
- Maximum detuning: `Δf_detune_max ≈ f₀ / (2Q) ≈ 50-100 MHz`

However, for worst-case timing analysis, we use the full excitation bandwidth, as the pulse still contains energy across the entire bandwidth even if the antenna response is reduced.

## Frequency Resolution Analysis

### FFT Frequency Resolution

When Sim4Life performs FFT on the time-domain response to extract frequency-domain data, the frequency resolution is determined by the simulation time:

```
Δf = 1 / T_sim
```

Where:
- `Δf` = frequency resolution (Hz)
- `T_sim` = total simulation time (seconds)

**Practical examples:**
- `T_sim = 20 ns` → `Δf = 50 MHz` (too coarse!)
- `T_sim = 100 ns` → `Δf = 10 MHz` (marginal)
- `T_sim = 200 ns` → `Δf = 5 MHz` (good)

### Requirements for Antenna Detuning Detection

**Practical antenna characteristics** (from experimental data):
- **Antenna bandwidth (BW):** 10-30 MHz (narrowband)
- **Maximum detuning shift:** 50-100 MHz when near body
- **Typical resonance behavior:** Sharp peak with Q ≈ 20-40

**Required frequency resolution:** To accurately detect resonance shift and characterize antenna response:
- **Minimum requirement:** Δf ≤ 5 MHz (at least 2-6 points across antenna bandwidth)
- **Recommended:** Δf ≤ 2-3 MHz (at least 3-10 points across bandwidth)
- **Optimal:** Δf ≤ 1 MHz (dense sampling for accurate peak finding)

### Balancing Pulse Duration and Frequency Resolution

There's a **trade-off** between:
1. **Pulse duration requirement** (minimum time): `T_pulse = 2k·σ ≈ 2.22/BW_excitation`
2. **Frequency resolution requirement** (longer is better): `T_sim ≥ 1/Δf_required`

**For antenna characterization with narrow bandwidth:**

If we use `BW_excitation = 50 MHz` (narrower than typical 100 MHz):
- Pulse duration: `T_pulse ≈ 44 ns`
- For `Δf = 5 MHz` resolution: `T_sim ≥ 200 ns`
- Since `200 ns > 44 ns`, frequency resolution dominates

**Recommended approach:**
```
T_sim = max(multiplier · L_bbox/c, L_bbox/c + T_pulse, 1/Δf_target)
```

Where:
- `Δf_target` = desired frequency resolution (typically 5 MHz or better)
- This ensures adequate time for BOTH pulse completion AND frequency resolution

## PML Boundaries and Propagation Time

### Why 1× Propagation Time is Sufficient

**With PML (Perfectly Matched Layer) boundaries:**
- Electromagnetic waves propagate forward through the domain
- PML boundaries absorb outgoing waves without reflection
- Signals do NOT bounce back into the domain

**The propagation time requirement is for:**
- Allowing transient fields to propagate from source to domain edges
- Letting fields dissipate into the PML (forward propagation only)
- NOT for waiting for reflected signals to return

**Therefore:** `T_prop = L_bbox/c` (1×) is sufficient, NOT `2 × L_bbox/c`

The multiplier (3.5×) provides additional margin for:
- Multiple round-trips within the domain before reaching PML
- Ensuring complete energy dissipation
- Accounting for longer paths than the diagonal

**Antenna self-reflection** (for S11 measurement):
- Happens locally at the antenna (L_antenna ≈ 10 cm)
- Time scale: `L_antenna/c ≈ 0.3 ns` (much faster than bbox propagation)
- Fully captured within the pulse duration and propagation time

### Convergence Criteria Considerations

**Note on GlobalAutoTermination:**
- Sim4Life's automatic convergence criteria can be unreliable in some cases
- For Gaussian pulses, the criteria are designed for harmonic steady-state
- **Best practice:** Rely on explicit time calculation rather than convergence

**Validation approach:**
- Check point sensors at bbox corners
- Verify E-field amplitude has decayed to negligible levels
- For Gaussian: ensure pulse has fully propagated and decayed

## Practical Implementation Recommendations

### Recommended Excitation Bandwidths

Based on antenna characteristics (BW = 10-30 MHz, shift up to 100 MHz):

**Option 1: Narrow bandwidth (Recommended for high resolution)**
- `BW_excitation = 50 MHz` (covers ±25 MHz around nominal)
- Frequency resolution: 5 MHz (T_sim = 200 ns)
- Pulse duration: ~44 ns
- **Pros:** Better resolution, less computational cost
- **Cons:** May need to run multiple simulations if shift > 25 MHz

**Option 2: Wide bandwidth (Better coverage)**
- `BW_excitation = 150 MHz` (covers ±75 MHz around nominal)
- Frequency resolution: 5 MHz (T_sim = 200 ns)
- Pulse duration: ~15 ns
- **Pros:** Captures larger shifts in single simulation
- **Cons:** Wastes computation on frequencies where antenna doesn't respond

**Option 3: Two-stage approach (Optimal)**
- Stage 1: Wide bandwidth (150 MHz) for coarse detection
- Stage 2: Narrow bandwidth (30-50 MHz) centered on detected resonance for refinement

### Updated Simulation Time Formula

**Complete formula accounting for all factors:**

```python
# Constants
c = 2.998e8  # m/s
k = 3.7      # Conservative threshold

# Configuration
bandwidth_mhz = 50  # MHz (narrower for better resolution)
target_freq_resolution_mhz = 5  # MHz (for accurate antenna characterization)
multiplier = 3.5  # For propagation with margin

# Calculate components
sigma = 0.94 / (np.pi * bandwidth_mhz * 1e6)  # seconds
T_pulse = 2 * k * sigma  # Pulse duration
T_prop = diagonal_length_m / c  # Propagation time
T_resolution = 1 / (target_freq_resolution_mhz * 1e6)  # For frequency resolution

# Required simulation time (take maximum of all constraints)
T_sim = max(
    multiplier * T_prop,          # Multiplier-based approach
    T_prop + T_pulse,             # Propagation + pulse duration
    T_resolution                  # Frequency resolution requirement
)

# Convert to periods at center frequency
sim_time_periods = T_sim / (1 / (frequency_mhz * 1e6))
```

### Verification Examples with New Formula

**Example: 700 MHz antenna, L_bbox = 0.5 m, BW = 50 MHz**

```
T_prop = 0.5 / 3e8 = 1.67 ns
T_pulse = 2.22 / (50e6) = 44.4 ns
T_resolution = 1 / (5e6) = 200 ns

Component 1 (multiplier): 3.5 × 1.67 = 5.84 ns
Component 2 (propagation + pulse): 1.67 + 44.4 = 46.1 ns
Component 3 (resolution): 200 ns

T_sim = max(5.84, 46.1, 200) = 200 ns  ← FREQUENCY RESOLUTION DOMINATES!

N_periods = 200e-9 / (1/700e6) = 140 periods
```

**This is a CRITICAL finding:** For narrowband antenna characterization, **frequency resolution requirements dominate** over both propagation and pulse duration!

**Example: Comparison with 100 MHz bandwidth**

```
With BW = 100 MHz:
T_pulse = 22.2 ns (shorter)
T_resolution = 200 ns (same, set by target resolution)
T_sim = 200 ns (still dominated by resolution requirement)
```

**Conclusion:** The excitation bandwidth affects pulse duration, but for accurate antenna characterization, the simulation time is primarily determined by the required frequency resolution, not the pulse width!

## Signal Processing Considerations and Uncertainties

### What We Don't Know: Sim4Life's Internal Processing

**Critical caveat:** Sim4Life is commercial software with proprietary post-processing. We don't know exactly what it does internally:

**Potential techniques that could improve frequency resolution:**
1. **Zero padding**: Interpolates FFT spectrum without improving true resolution, but enables better peak localization
2. **Windowing**: May apply Hanning/Hamming windows to reduce spectral leakage (slightly worsens resolution)
3. **ARMA/Prony estimation**: The manual mentions ARMA for "high-Q resonators" - might extrapolate beyond raw FFT resolution
4. **Parabolic/Gaussian interpolation**: Sub-bin peak finding (could give 10-100× better peak location accuracy)

**What this means:**
- The strict `Δf = 1/T_sim` requirement may be **overly conservative**
- For **single-peak detection** (our use case), interpolation techniques can find the peak much more accurately than bin spacing suggests
- A simulation with `Δf = 20 MHz` bins + interpolation might accurately locate a peak to ±1-2 MHz

### The Problem with Speculation

**We cannot rely on undocumented features.** The only scientifically valid approach is:
1. **Start with conservative theoretical bounds** (this document provides that)
2. **Run empirical tests** to determine what actually works
3. **Update implementation** based on measured results

### Theoretical vs. Practical Requirements

**Theoretical (this document):**
```
T_sim = max(multiplier · L_bbox/c, L_bbox/c + 2k·σ, 1/Δf_target)
```
- Conservative bound assuming standard FFT with no advanced post-processing
- Guarantees sufficient data for accurate frequency analysis
- For 5 MHz resolution: **T_sim ≥ 200 ns**

**Practical (needs empirical validation):**
```
T_sim = max(multiplier · L_bbox/c, L_bbox/c + 2k·σ, ?)
```
- The `?` depends on Sim4Life's actual post-processing capabilities
- Could be as low as **50-100 ns** if ARMA/interpolation work well
- Or could be **200+ ns** if they don't apply to our case

**Our use case specifics:**
- **Single narrowband resonance** (easier to detect than multiple peaks)
- **Need peak location accuracy** (not spectral resolution of two close peaks)
- **Detecting 50-100 MHz shifts** (large compared to potential bin spacing)

### Recommended Approach: Implement with Tunable Parameter

**Pragmatic engineering approach:**

1. **Implement with conservative defaults**:
   ```python
   s4l_arma_speedup_factor = 1.0  # Conservative: assume standard FFT only
   T_resolution = s4l_arma_speedup_factor / (target_freq_resolution_mhz * 1e6)
   ```
   - Guaranteed correct
   - No assumptions about Sim4Life internals
   - For 5 MHz resolution: T_sim = 200 ns

2. **Make it tunable via config**:
   ```json
   "simulation_parameters": {
       "target_freq_resolution_mhz": 5.0,
       "s4l_arma_speedup_factor": 1.0
   }
   ```

3. **Test after implementation** (optional optimization):
   - Run with speedup factors: [1.0, 1.5, 2.0, 3.0, 4.0]
   - Compare results: accuracy vs. simulation time
   - Find optimal tradeoff
   - Update default if validated

**Benefits:**
- ✅ Can't break what you haven't built yet (need working code first!)
- ✅ Conservative default guarantees correctness
- ✅ Tunable for optimization without code changes
- ✅ Empirical validation happens after stable implementation
- ✅ Easy to test: just change one config parameter

**Example optimization tests** (run AFTER implementation):
```
speedup=1.0 → T_sim=200 ns → Δf=5.0 MHz (baseline, guaranteed correct)
speedup=1.5 → T_sim=133 ns → Test: Does peak detection still work?
speedup=2.0 → T_sim=100 ns → Test: Does peak detection still work?
speedup=3.0 → T_sim=67 ns  → Test: Does peak detection still work?
speedup=4.0 → T_sim=50 ns  → Test: Does peak detection still work?
```

Find the "knee" where accuracy degrades, use that as new default.

## Summary

### Key Formula (Theoretical Conservative Bound)

**Required simulation time for Gaussian excitation with antenna characterization:**
```
T_sim = max(multiplier · L_bbox/c, L_bbox/c + 2k·σ, 1/Δf_target)
```

Where:
- `σ = 0.94/(π·BW)` (temporal standard deviation of Gaussian pulse)
- `k = 3.7` (conservative threshold for 0.1% of peak amplitude)
- `2k·σ ≈ 2.22/BW` (pulse duration)
- `Δf_target` = required frequency resolution (typically 5 MHz for narrowband antennas)

**⚠️ CAVEAT:** This formula assumes standard FFT with no advanced post-processing. **Empirical validation required** to determine if Sim4Life's internal processing (ARMA, interpolation, zero-padding) allows shorter simulation times.

### Key Findings

1. **For narrowband antenna characterization** (BW = 10-30 MHz), **frequency resolution theoretically dominates** over pulse duration and propagation time.

2. **Theoretical minimum simulation times** are much longer than traditional pulse duration estimates:
   - For Δf = 5 MHz: T_sim ≥ 200 ns (140 periods @ 700 MHz)
   - For Δf = 2 MHz: T_sim ≥ 500 ns (350 periods @ 700 MHz)
   - **BUT:** Signal processing techniques might relax this significantly

3. **Signal processing considerations**:
   - Zero padding + interpolation: Better peak location without longer simulation
   - ARMA extrapolation: Sim4Life manual mentions it for "high-Q resonators"
   - Sub-bin peak finding: 10-100× better accuracy than bin spacing
   - **Uncertainty:** We don't know what Sim4Life actually does

4. **Our use case is favorable** for shorter times:
   - Single peak detection (not resolving multiple close peaks)
   - Large detuning detection (50-100 MHz) vs bin spacing
   - Narrowband antenna (high-Q) may benefit from ARMA if implemented

5. **PML boundaries** absorb outgoing waves, so 1× propagation time (with multiplier) is sufficient - no need for 2× to account for reflections.

6. **Convergence criteria** may be unreliable for Gaussian pulses; explicit time calculation is essential.

7. **The old multiplier approach** (3.5 × L_bbox/c) is **insufficient** for antenna characterization, giving only ~5-10 ns when 50-200+ ns is needed (exact value TBD via testing).

### Practical Recommendations

1. **FIRST: Run empirical sensitivity study** (see Phase 0.5 in implementation TODO)
   - Test T_sim from 200 ns down to 35 ns
   - Measure actual frequency resolution and peak detection accuracy
   - Determine minimum viable simulation time
   - Document Sim4Life's actual behavior

2. **Use narrower excitation bandwidth** (50 MHz) for better resolution-to-bandwidth ratio

3. **Start conservative** (T_sim ≥ 1/Δf_target), optimize after empirical validation

4. **Validate with point sensors** rather than relying solely on convergence criteria

5. **Consider two-stage approach**: wide bandwidth for detection, narrow for characterization

### Implementation Impact

The implementation will:
- **Initially use conservative formula** (200 ns for 5 MHz resolution)
- **Include empirical validation phase** BEFORE full deployment
- Account for frequency resolution requirements (NEW and CRITICAL)
- Include pulse duration requirements (as previously analyzed)
- Use 1× propagation time with appropriate multiplier (NOT 2×)
- **Update formula based on empirical findings** after validation
- Log which constraint dominated (resolution, pulse, or propagation)
- Enable accurate detection of 50-100 MHz frequency shifts in narrowband antennas

**Timeline:**
1. Phase 0.5: Sensitivity study (4-6 hours) → determines actual requirements
2. Phase 1-6: Full implementation with validated formula

This ensures both complete Gaussian pulse capture AND sufficient frequency resolution for accurate antenna detuning detection, **without over-conservative assumptions that waste computational resources**.

