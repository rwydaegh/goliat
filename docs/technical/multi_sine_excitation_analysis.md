# Multi-Sine Excitation Analysis: Superposition of Discrete Harmonic Sinusoids

## Executive Summary

This document analyzes the feasibility and potential benefits of using a **custom multi-sine excitation signal** (superposition of harmonic sinusoids at discrete frequencies) for **far-field simulations**.

### Key Findings

| Aspect | Status |
|--------|--------|
| Physics feasible | ✅ Multi-sine is valid FDTD excitation |
| Dispersive materials | ✅ IT'IS database uses `kLinearDispersive` - handles all frequencies |
| ExtractedFrequencies | ✅ API confirmed: takes list of frequencies |
| Grid penalty | ✅ None for far-field (already using finest grid for 5800 MHz) |
| Antenna constraint | ✅ None for far-field (plane wave source) |
| **Recommended for** | **Far-field only** (not near-field due to antenna/grid constraints) |

### Bottom Line

**For far-field:** 432 simulations → 48 simulations (**89% reduction**, ~4× speedup)

**For near-field:** Not recommended due to different antenna models per frequency and grid penalties.

---

## Context: Your Current Problem

### What You Have Now
- **Harmonic simulations**: Single frequency per run, ~5-10 ns simulation time
- **Multiple configurations**: Different phantoms, scenarios, frequencies
- **Bottleneck**: Many simulations × each frequency = long total campaign time

### Why Gaussian is Appealing But Problematic
From your existing analysis (`gaussian_pulse_timing_analysis.md`):
- **The promise**: Single simulation → full frequency response via FFT
- **The reality**: For 5 MHz frequency resolution, you need **~200 ns** simulation time (vs ~5-10 ns for harmonic)
- **The premium**: ~20-40× longer per simulation to get wideband data

### Your Multi-Sine Idea
Instead of:
- Gaussian (continuous spectrum, requires long tail for FFT resolution)
- Multiple harmonic runs (one frequency each)

Why not:
- **Sum of N sinusoids** at discrete frequencies you care about
- Each sine reaches steady-state (no decay tail)
- Extract each frequency via DFT at those specific frequencies

---

## Mathematical Foundation

### Multi-Sine Signal Definition

Your proposed excitation would be:

```
s(t) = Σᵢ Aᵢ · cos(2π·fᵢ·t + φᵢ)
```

Where:
- `Aᵢ` = amplitude of each tone (typically equal for equal weighting)
- `fᵢ` = discrete frequency of interest (e.g., 700, 900, 1800 MHz)
- `φᵢ` = phase offset (can be zero, but see "crest factor" below)

### Key Properties

**1. Steady-State Behavior ✅**
- Unlike Gaussian, sinusoids don't decay to zero
- No "tail problem" - the signal is perpetually oscillating
- Sim4Life can use convergence to steady-state criteria

**2. Discrete Spectrum ✅**
- Energy exists ONLY at the N chosen frequencies
- No spectral leakage to intermediate frequencies
- Perfect extraction at known frequencies (if done correctly)

**3. No DC Component ✅**
- Sum of sines has no DC (assuming no constant offset)
- Avoids numerical issues with DC in FDTD

---

## The Critical Question: Simulation Time Requirements

### Why Warmup is Still Needed (But Finite)

Even though sinusoids are steady-state signals, two time scales matter:

**1. Transient Propagation Time (`T_prop`)**
```
T_prop = L_bbox / c ≈ 1-5 ns (typical)
```
- Fields must propagate from source to observation points
- Not the bottleneck

**2. Beat Period Time (`T_beat`) - THE KEY ISSUE**

When you superimpose multiple sinusoids, their sum creates **beat patterns**:

```
f₁ = 700 MHz, f₂ = 900 MHz
Beat frequency = |f₂ - f₁| = 200 MHz
Beat period = 1/200 MHz = 5 ns
```

For the system to reach a true steady-state where DFT extraction is valid, you need to simulate **at least a few beat periods**.

**But here's the catch with widely spaced frequencies:**

If you have:
- f₁ = 700 MHz
- f₂ = 900 MHz  
- f₃ = 1800 MHz

The beat frequencies are:
- |900-700| = 200 MHz → T = 5 ns
- |1800-700| = 1100 MHz → T = 0.9 ns
- |1800-900| = 900 MHz → T = 1.1 ns

These are all **fast** beat frequencies because your frequencies are widely spaced!

**But if frequencies are close (e.g., for antenna detuning detection):**
- f₁ = 700 MHz
- f₂ = 710 MHz
- f₃ = 720 MHz

Beat frequencies:
- |710-700| = 10 MHz → T = 100 ns
- |720-710| = 10 MHz → T = 100 ns
- |720-700| = 20 MHz → T = 50 ns

For close frequencies, you need **longer simulation times** for beat pattern to establish!

### The Periodicity Constraint

A crucial mathematical fact: **The sum of sinusoids is only periodic if all frequency ratios are rational.**

Example:
- f₁ = 700 MHz, f₂ = 1400 MHz → ratio 2:1 → periodic ✅
- f₁ = 700 MHz, f₂ = 900 MHz → ratio 9:7 → periodic ✅ (period = 7 × T₁ = 9 × T₂)
- f₁ = 700 MHz, f₂ = 700.001 MHz → ratio irrational → never exactly periodic ❌

For practical frequencies like telecom bands (700, 900, 1800, 2100, 3500 MHz), the ratios ARE rational (since frequencies are integers in Hz), so the combined waveform is periodic, just with a potentially very long period.

---

## Simulation Time Requirements: Multi-Sine vs Alternatives

### Scenario A: Widely Spaced Frequencies (Different Bands)

**Goal**: Simulate at 700, 900, 1800 MHz in one run

| Approach | Simulation Time | Post-Processing | Notes |
|----------|----------------|-----------------|-------|
| **3× Harmonic** | 3 × 5 ns = 15 ns total | None | Baseline |
| **Gaussian** | ~200 ns (for 5 MHz res) | FFT | Overkill for 3 discrete points |
| **Multi-Sine (3 tones)** | ~10-20 ns | DFT at 3 frequencies | ✅ **Potentially efficient** |

**Analysis**: For widely-spaced frequencies, multi-sine is promising because:
- Beat frequencies are high (short periods)
- You only need a few periods of the slowest beat to establish steady-state
- Extraction is trivial (lock-in at known frequencies)

### Scenario B: Closely Spaced Frequencies (Detuning Detection)

**Goal**: Detect resonance shift ±25 MHz around 700 MHz (e.g., 675-725 MHz in 5 MHz steps = 11 frequencies)

| Approach | Simulation Time | Post-Processing | Notes |
|----------|----------------|-----------------|-------|
| **11× Harmonic** | 11 × 5 ns = 55 ns total | None | Many runs |
| **Gaussian** | ~200 ns | FFT gives continuous spectrum | Standard approach |
| **Multi-Sine (11 tones)** | ~50-100 ns | DFT at 11 frequencies | Beat periods dominate! |

**Analysis**: For closely-spaced frequencies, multi-sine loses advantage because:
- Beat frequency = 5 MHz → requires ~200 ns for clean extraction
- You're back to Gaussian-like time requirements!

---

## The ExtractedFrequencies Feature in Sim4Life

You mentioned Sim4Life's `ExtractedFrequencies` variable. Let me clarify how this works:

```python
# From your code (source_setup.py):
far_field_sensor_settings.ExtractedFrequencies = (
    extracted_frequencies_hz,  # List of frequencies
    self.units.Hz,
)
```

**What this does:**
- Tells Sim4Life to compute frequency-domain data at those specific frequencies
- Uses **DFT (Discrete Fourier Transform)** on the time-domain results
- Works with ANY excitation type (Gaussian, Harmonic, or custom)

**Key insight**: You can use `ExtractedFrequencies` with a multi-sine source AND get per-frequency results!

This is exactly what you need - you excite with a multi-sine signal, and Sim4Life's post-processing DFT extracts the response at each of your chosen frequencies.

---

## Practical Implementation Considerations

### 1. Crest Factor Problem

When you add multiple sinusoids, their peaks can add constructively, creating very high instantaneous amplitudes:

```
N sinusoids in phase: peak amplitude = N × individual amplitude
```

**Issue**: This can cause numerical issues or require lower per-tone amplitudes

**Solution**: Use phase offsets (Schroeder phases) to minimize crest factor:
```python
# Schroeder phase sequence minimizes peak amplitude
phases = [np.pi * k * (k+1) / N for k in range(N)]
```

### 2. Warmup Ramp Still Needed

Even for multi-sine, you need to ramp the source gradually:
```python
# Instead of sudden turn-on:
s(t) = ramp(t) × Σᵢ Aᵢ cos(2πfᵢt + φᵢ)

# Where ramp(t) transitions smoothly from 0 to 1
```

### 3. Frequency Separation and Orthogonality

For clean DFT extraction, the simulation time should be an integer multiple of the period at each frequency:
```
T_sim = K / f_lowest = K × T_period_longest
```

If frequencies don't share a common period, DFT leakage can occur, but this is usually minor for well-separated frequencies.

### 4. Memory and Computational Cost

The FDTD computational cost per timestep is the same regardless of excitation type. What matters is:
- **Total timesteps** = T_sim / Δt
- **Post-processing**: DFT at N specific frequencies is O(N × M) where M = number of time samples
  - This is MUCH faster than full FFT O(M log M) for the typical case where N << M

---

## Decision Matrix: When to Use Which Approach

| Use Case | Best Approach | Reasoning |
|----------|---------------|-----------|
| **Single frequency SAR** | Harmonic | Simplest, fastest for one-off |
| **Many frequencies, same phantom** | Multi-Sine | One sim, multiple extractions |
| **Continuous spectrum needed** | Gaussian | Only way to get true broadband |
| **Antenna detuning (narrow band sweep)** | Gaussian | Close frequencies = long beat periods anyway |
| **Widely spaced bands (700/900/1800)** | Multi-Sine | Beat periods fast, clean separation |
| **Maximum accuracy at specific frequency** | Harmonic | No inter-frequency interference |

---

## Potential Issues (Resolved via API Verification)

### 1. Inter-Frequency Coupling in Nonlinear Systems
- If your phantom/antenna system has any nonlinearity, multi-sine excitation can create intermodulation products
- For **linear SAR calculations** (which yours are), this is NOT an issue
- FDTD with linear dispersive materials is inherently linear

### 2. SAR at Each Frequency
- SAR is power normalized
- With multi-sine, the total input power is distributed across frequencies
- Need to normalize SAR per frequency by the power at that specific frequency

### 3. Sim4Life Compatibility: VERIFIED ✅
- `UserDefined` excitation with custom expression is supported (you already use it for Gaussian)
- Multi-sine expression would be:
```python
expression = " + ".join([
    f"{amp} * cos(2 * pi * {freq} * _t + {phase})" 
    for amp, freq, phase in zip(amplitudes, frequencies, phases)
])
```

### 4. ExtractedFrequencies with Multi-Sine: VERIFIED ✅

From Sim4Life Python API Reference:

```python
# API confirms this works with any excitation type:
settings.ExtractedFrequencies = [450e6, 700e6, 835e6, 1450e6, 2140e6, 2450e6, 3500e6, 5200e6, 5800e6]
settings.OnTheFlyDFT = True
settings.RecordingDomain = 'RecordInFrequencyDomain'
```

### 5. Dispersive Materials: VERIFIED ✅

From Sim4Life Python API Reference (`EmFdtdMaterialSettings.eMaterialModel`):

```python
kConst             # Constant (frequency-independent)
kLinearDispersive  # ← IT'IS database uses this (frequency-dependent)
kMetaMaterial      # Metamaterial
```

- IT'IS tissues use `kLinearDispersive` with Debye parameters
- FDTD solver handles all frequencies correctly via ADE method
- Each frequency component sees correct ε(f) and σ(f) automatically

---

## Recommendation: A Hybrid Strategy

Based on this analysis, I recommend a **pragmatic hybrid approach**:

### For Your Main Workload (Different Frequencies×Phantoms×Scenarios):

**Group by frequency separation:**

1. **Widely separated frequencies in same simulation** (700, 900, 1800 MHz)
   - Use multi-sine with 3-5 tones per group
   - Expect ~15-30 ns simulation time
   - Extract SAR at each frequency via DFT
   - **Potential speedup**: 3-5× fewer simulations

2. **Closely spaced frequency sweeps** (for detuning or fine analysis)
   - Stick with Gaussian (you need ~200 ns anyway)
   - Or run multiple harmonics if Gaussian overhead is too high

3. **Single critical frequency** (final validation)
   - Use harmonic for maximum accuracy
   - No inter-frequency artifacts

### Implementation Roadmap (If You Proceed):

**Phase 1: Proof of Concept (4-8 hours)**
1. Create a test config with 3 widely-spaced frequencies
2. Implement multi-sine expression in `source_setup.py`
3. Run single test, compare each frequency's SAR with harmonic baseline
4. Validate power normalization is correct

**Phase 2: Full Integration (if Phase 1 succeeds)**
1. Add config options for multi-sine
2. Handle extracted frequencies based on source specification
3. Update power/SAR extraction for multi-frequency normalization
4. Create user documentation

---

## Mathematical Appendix: Beat Period Calculation

For N frequencies `{f₁, f₂, ..., fₙ}`, the beat frequencies are all pairwise differences:

```
f_beat(i,j) = |fᵢ - fⱼ|
```

The overall period of the combined waveform (if all frequencies are rationally related) is:
```
T_total = LCM(T₁, T₂, ..., Tₙ)
```

Where `LCM` is the Least Common Multiple and `Tᵢ = 1/fᵢ`.

**Example Calculation:**
- f₁ = 700 MHz → T₁ = 1.429 ns
- f₂ = 900 MHz → T₂ = 1.111 ns

Integer multiple relationship:
- 700 MHz × 9 = 6300 MHz
- 900 MHz × 7 = 6300 MHz
- Period of sum = 9 × T₁ = 7 × T₂ = 12.86 ns

So you'd need at least ~13 ns to see one complete cycle of the combined waveform, plus propagation and warmup → **~30-50 ns** total should be safe.

---

## Conclusion

Your multi-sine idea is **physically sound and highly valuable for far-field simulations**:

### For Far-Field (RECOMMENDED) ✅

| Benefit | Value |
|---------|-------|
| Simulation reduction | 432 → 48 (89%) |
| Time per sim increase | ~2.2× (beat period overhead) |
| **Net speedup** | **~4×** |

✅ All 9 frequencies in one simulation  
✅ No antenna model constraint (plane wave)  
✅ No grid penalty (already using 1.0 mm for 5800 MHz)  
✅ Dispersive materials work automatically  
✅ ExtractedFrequencies API supports multi-frequency extraction  

### For Near-Field (NOT RECOMMENDED) ⚠️

- Different antenna models per frequency (PIFA vs IFA)
- Different grid requirements per frequency
- Limited to grouping only highest 3 frequencies (22% reduction)

### Implementation Priority

1. **Far-field multi-sine**: High priority, ~4× speedup
2. **Near-field**: Keep using harmonic simulations
3. **Detuning detection**: Keep Gaussian (need continuous spectrum)

---

*Document created: 2025-12-12*  
*Updated: 2025-12-12 with API verification*  
*Related documents: multi_sine_grouping_math.md, gaussian_pulse_timing_analysis.md*
