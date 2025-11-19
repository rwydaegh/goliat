# TODO: Gaussian Excitation Support for Near-Field Simulations with Antenna Detuning Detection

## Overview

This document outlines the complete implementation plan for adding Gaussian excitation support to near-field (phantom) simulations in GOLIAT. Currently, Gaussian excitation is only used for free-space antenna characterization. This work extends it to SAR compliance studies **with the primary goal of detecting antenna detuning when devices are near the body**.

## Context and Motivation

### Current State
- **Harmonic excitation**: Standard for SAR compliance (single frequency)
- **Gaussian excitation**: Currently only for free-space simulations (frequency sweep)
- **Free-space limitation**: Code checks `free_space` flag to determine excitation type
- **Material workaround**: Copper→PEC forced only for free-space Gaussian (Sim4Life limitation)
- **No detuning detection**: Cannot determine actual antenna resonant frequency in near-field conditions

### Primary Goal: Antenna Detuning Detection

**The Problem:**
- Antennas are narrowband devices (10-30 MHz bandwidth)
- When near the body, antenna resonance shifts significantly (50-100 MHz)
- Running at nominal frequency may miss the actual resonant frequency
- Current harmonic simulations assume antenna operates at design frequency

**The Solution:**
- Use Gaussian pulse excitation to sweep a frequency range
- Extract continuous frequency response from Sim4Life's automatic FFT
- Identify actual resonant frequency (maximum accepted power)
- Quantify detuning and assess impact on SAR patterns

### Secondary Goals
- Enable frequency-sweep SAR studies
- Material handling (Copper→PEC workaround for all Gaussian)
- Proper simulation timing (pulse duration + frequency resolution)
- Power/SAR extraction at appropriate frequencies

## Critical Realizations

### 1. Sim4Life Performs Automatic FFT Post-Processing
**Key Discovery:** Sim4Life automatically converts time-domain Gaussian pulse responses into frequency-domain data via FFT.

**What This Means:**
- **No manual frequency sampling needed**: The 21-frequency setup for far-field sensors is ONLY for radiation patterns
- **Continuous frequency spectra**: Edge sensor outputs like `"EM Input Power(f)"` provide complete frequency arrays
- **Data structure**: `Data.Axis` contains the full frequency array (Hz), `Data.GetComponent(0)` contains values at each frequency
- **Resolution**: Determined by simulation time: `Δf = 1/T_sim` (NOT by manual sampling!)

**Example extraction:**
```python
input_power_output = input_power_extractor.Outputs["EM Input Power(f)"]
freq_axis_hz = input_power_output.Data.Axis  # Full frequency array (e.g., 1000+ points)
power_data_w = input_power_output.Data.GetComponent(0)  # Power at each frequency
```

### 2. Simulation Time Requirements (UPDATED)
**Three constraints determine simulation time:**

1. **Propagation time**: `T_prop = L_bbox/c` (with PML, 1× is sufficient, NOT 2×)
2. **Pulse duration**: `T_pulse = 2k·σ ≈ 2.22/BW` (for complete pulse)
3. **Frequency resolution** (NEW and DOMINANT): `T_resolution = 1/Δf_target`

**Critical Finding:** For narrowband antenna characterization (BW = 10-30 MHz, detecting 50-100 MHz shifts), **frequency resolution dominates**:
- Required: `Δf ≤ 5 MHz` (at least 2-6 points across antenna bandwidth)
- This requires: `T_sim ≥ 200 ns` (140 periods @ 700 MHz)
- Compare to old approach: ~5-10 ns (SEVERELY insufficient!)

**Updated Formula:**
```
T_sim = max(multiplier · L_bbox/c, L_bbox/c + 2k·σ, 1/Δf_target)
```

See `docs/technical/gaussian_pulse_timing_analysis.md` for complete analysis.

### 3. Power Extraction is Straightforward
**Resolution:** `GetPower()` returns total accepted power (integrated, not density).

**For Gaussian excitation:**
- Extract full frequency-dependent power: `"EM Input Power(f)"`
- Data is already computed by Sim4Life's FFT
- Maximum power → resonant frequency
- No integration needed (Sim4Life does it internally)

**For SAR normalization:**
- Extract power at center frequency (or detected resonance)
- Use this single value for SAR normalization
- Consistent with harmonic approach

### 4. Practical Antenna Characteristics (From Experiments)
**Measured antenna behavior:**
- **Bandwidth:** 10-30 MHz (narrowband, high Q ≈ 20-40)
- **Detuning when near body:** 50-100 MHz shift (can be substantial!)
- **Implications:** 
  - Need excellent frequency resolution (≤5 MHz)
  - Excitation bandwidth must cover potential shift range
  - Sharp resonance peaks require dense frequency sampling

### 5. Material Limitation
**Sim4Life Limitation:** Gaussian excitation doesn't support dispersive materials like Copper. Must force to PEC.

**Current Code:** Only applies when `free_space AND gaussian`  
**Required:** Apply for ANY Gaussian excitation (not just free-space)

### 6. Recommended Excitation Bandwidths
Based on antenna characteristics:

**Option 1: Narrow bandwidth (50 MHz) - Recommended**
- Covers ±25 MHz around nominal frequency
- Better frequency resolution for given simulation time
- May need multiple simulations if shift > 25 MHz

**Option 2: Wide bandwidth (150 MHz) - Better coverage**
- Covers ±75 MHz (handles most detuning cases)
- Slightly shorter pulse duration
- Wastes computation on non-responsive frequencies

**Option 3: Two-stage (Optimal but complex)**
- Stage 1: Wide sweep (150 MHz) for coarse detection
- Stage 2: Narrow sweep (30-50 MHz) centered on detected resonance

## Implementation Strategy

**Pragmatic Approach: Build First, Optimize Later**

Rather than trying to validate Sim4Life's internal post-processing before implementation, we'll:
1. ✅ **Build full working implementation** with conservative defaults
2. ✅ **Make simulation time tunable** via config parameter
3. ✅ **Start conservative** (assume standard FFT: `Δf = 1/T_sim`)
4. ✅ **Add speedup factor** for later optimization (`s4l_arma_speedup_factor`)
5. ✅ **Run sensitivity analysis AFTER** stable code exists

**Key insight:** We can't validate without working code, so build it first!

## Implementation Tasks

---

## Phase 0: Configuration Design (NEW - Quick Setup)

**Purpose:** Define config parameters that make implementation tunable and future-proof.

### 0.1 Add Config Parameters to `base_config.json`

#### Task 0.1.1: Add Gaussian-specific parameters
- [ ] Open `configs/base_config.json`
- [ ] Add to `simulation_parameters` section:

```json
"simulation_parameters": {
    "excitation_type": "Harmonic",
    "bandwidth_mhz": 50.0,
    "target_freq_resolution_mhz": 5.0,
    "s4l_arma_speedup_factor": 1.0,
    "simulation_time_multiplier": 3.5,
    "global_auto_termination": "GlobalAutoTerminationUserDefined",
    "convergence_level_dB": -15,
    // ... existing params
}
```

#### Task 0.1.2: Document new parameters
Add inline comments:
- [ ] `excitation_type`: `"Harmonic"` (default) or `"Gaussian"` (broadband frequency sweep)
- [ ] `bandwidth_mhz`: Excitation bandwidth for Gaussian pulse (typical: 50-150 MHz)
- [ ] `target_freq_resolution_mhz`: Desired frequency resolution for antenna characterization (smaller = better resolution = longer sim time)
- [ ] `s4l_arma_speedup_factor`: Speedup multiplier if Sim4Life uses advanced post-processing (1.0 = conservative, no assumptions; 2.0 = assume 2× ARMA speedup; test empirically)

**Estimated Time:** 15 minutes  
**Dependencies:** None

---

### Phase 0 Summary

**Outcome:** Config structure ready for Gaussian implementation with tunable timing.

**Key Design:** The `s4l_arma_speedup_factor` makes it easy to test different assumptions:
- Start with 1.0 (conservative, guaranteed correct)
- After implementation, run tests with [1.0, 1.5, 2.0, 3.0, 4.0]
- Update default based on empirical findings

---

## Phase 1: Core Code Changes

### 1.1 Source Setup (`goliat/setups/source_setup.py`)

**File:** `goliat/setups/source_setup.py`  
**Current Behavior:** Hardcodes Harmonic for non-free-space, Gaussian only for free-space  
**Required Changes:** Make excitation type config-driven

#### Task 1.1.1: Replace free_space check with excitation_type config
- [ ] Remove `if self.free_space:` check on line 60
- [ ] Read `excitation_type` from config: `self.config["simulation_parameters.excitation_type"]`
- [ ] Default to `"Harmonic"` if not set
- [ ] Normalize to lowercase for comparison
- [ ] Set excitation type based on config value

**Code Pattern:**
```python
excitation_type = self.config["simulation_parameters.excitation_type"] or "Harmonic"
excitation_type_lower = excitation_type.lower() if isinstance(excitation_type, str) else "harmonic"

if excitation_type_lower == "gaussian":
    # Gaussian setup
else:
    # Harmonic setup
```

#### Task 1.1.2: Read bandwidth from config
- [ ] Read `bandwidth_mhz` from config: `self.config["simulation_parameters.bandwidth_mhz"]`
- [ ] Default to `50.0` MHz if not set
- [ ] Use config value instead of hardcoded `50.0` on line 65
- [ ] Add validation: ensure bandwidth is positive and reasonable (e.g., 10-200 MHz)
- [ ] Log bandwidth value being used

#### Task 1.1.3: Configure Gaussian excitation
- [ ] Set `edge_source_settings.ExcitationType = excitation_enum.Gaussian`
- [ ] Set `edge_source_settings.CenterFrequency = self.frequency_mhz, self.units.MHz`
- [ ] Set `edge_source_settings.Bandwidth = bandwidth_mhz, self.units.MHz` (from config)
- [ ] Update log message to include bandwidth

#### Task 1.1.4: Configure Harmonic excitation (default)
- [ ] Set `edge_source_settings.ExcitationType = excitation_enum.Harmonic`
- [ ] Set both `Frequency` and `CenterFrequency` to `self.frequency_mhz`
- [ ] Keep existing behavior for backward compatibility

#### Task 1.1.5: Add far-field sensors for Gaussian (not just free-space)
- [ ] Move far-field sensor setup outside `if self.free_space:` block
- [ ] Add far-field sensors when `excitation_type_lower == "gaussian"`
- [ ] Calculate extracted frequencies using config bandwidth
- [ ] Use same logic as current free-space code (21 frequencies)
- [ ] Update log message to remove "free-space" reference

**Frequency Calculation:**
```python
if excitation_type_lower == "gaussian":
    center_freq_hz = self.frequency_mhz * 1e6
    bandwidth_mhz = self.config["simulation_parameters.bandwidth_mhz"] or 50.0
    bandwidth_hz = bandwidth_mhz * 1e6
    start_freq_hz = center_freq_hz - (bandwidth_hz / 2)
    end_freq_hz = center_freq_hz + (bandwidth_hz / 2)
    num_samples = 21
    extracted_frequencies_hz = [
        start_freq_hz + i * (bandwidth_hz / (num_samples - 1)) 
        for i in range(num_samples)
    ]
```

#### Task 1.1.6: Update docstring
- [ ] Update method docstring to reflect config-driven behavior
- [ ] Remove mention of "free-space" determining excitation type
- [ ] Document `excitation_type` and `bandwidth_mhz` config parameters
- [ ] Add note about far-field sensors for Gaussian

**Estimated Time:** 2-3 hours  
**Dependencies:** None  
**Testing:** Unit tests, manual verification with both Harmonic and Gaussian configs

---

### 1.2 Material Setup (`goliat/setups/material_setup.py`)

**File:** `goliat/setups/material_setup.py`  
**Current Behavior:** Copper→PEC workaround only for `free_space AND gaussian`  
**Required Changes:** Apply workaround for ANY Gaussian excitation

#### Task 1.2.1: Remove free_space condition from Copper workaround
- [ ] Remove `self.free_space` check on line 153
- [ ] Keep `excitation_type` check
- [ ] Apply PEC workaround whenever `excitation_type == "gaussian"` AND material contains "Copper"

**Code Pattern:**
```python
excitation_type = self.config["simulation_parameters.excitation_type"]
if excitation_type is None:
    excitation_type = "Harmonic"
excitation_type_lower = excitation_type.lower() if isinstance(excitation_type, str) else "harmonic"

# Sim4Life limitation: Gaussian excitation doesn't support dispersive materials like Copper
if "Copper" in mat_name and excitation_type_lower == "gaussian":
    material_settings.Type = "PEC"
    # ... rest of workaround code
```

#### Task 1.2.2: Update warning message
- [ ] Remove "free-space" reference from warning message (lines 161-168)
- [ ] Update to: "Gaussian excitation with dispersive materials like Copper"
- [ ] Keep the prominent warning format (80-character separator)

#### Task 1.2.3: Update docstring
- [ ] Update `_assign_antenna_materials` docstring (line 132)
- [ ] Remove "free-space Gaussian" reference
- [ ] Update to: "forces PEC for Copper in Gaussian excitation (Sim4Life limitation)"

**Estimated Time:** 1 hour  
**Dependencies:** Task 1.1.1 (excitation_type config)  
**Testing:** Verify Copper components become PEC in Gaussian config, remain normal in Harmonic

---

### 1.3 Simulation Time Calculation (`goliat/setups/base_setup.py`) - UPDATED

**File:** `goliat/setups/base_setup.py`  
**Method:** `_apply_simulation_time_and_termination`  
**Current Behavior:** Simple multiplier approach: `multiplier · L_bbox/c`  
**Required Changes:** Add Gaussian pulse duration AND frequency resolution requirements

#### Task 1.3.1: Detect excitation type
- [ ] Read `excitation_type` from config in `_apply_simulation_time_and_termination`
- [ ] Check if excitation type is Gaussian

#### Task 1.3.2: Calculate pulse duration for Gaussian
- [ ] Read `bandwidth_mhz` from config (default: 50 MHz for narrow bandwidth)
- [ ] Convert to Hz: `bandwidth_hz = bandwidth_mhz * 1e6`
- [ ] Calculate temporal standard deviation: `sigma = 0.94 / (np.pi * bandwidth_hz)`
- [ ] Use conservative threshold: `k = 3.7` (for 0.1% of peak)
- [ ] Calculate pulse duration: `T_pulse = 2 * k * sigma`

#### Task 1.3.3: Calculate frequency resolution requirement with ARMA speedup factor (NEW - CRITICAL!)
- [ ] Read `target_freq_resolution_mhz` from config (default: 5 MHz for antenna characterization)
- [ ] Read `s4l_arma_speedup_factor` from config (default: 1.0 = conservative, no ARMA assumptions)
- [ ] Convert to Hz: `target_freq_resolution_hz = target_freq_resolution_mhz * 1e6`
- [ ] Calculate time for resolution WITH speedup: `T_resolution = s4l_arma_speedup_factor / target_freq_resolution_hz`
- [ ] Examples:
  - speedup=1.0, Δf=5MHz → T_resolution = 200 ns (conservative)
  - speedup=2.0, Δf=5MHz → T_resolution = 100 ns (assumes ARMA helps 2×)
  - speedup=4.0, Δf=5MHz → T_resolution = 50 ns (aggressive)
- [ ] With default (speedup=1.0), resolution typically dominates (~200 ns) over pulse (~44 ns) and propagation (~5 ns)

#### Task 1.3.4: Calculate required time (THREE constraints)
- [ ] Calculate propagation time: `T_prop = diagonal_length_m / c` (already done)
- [ ] Calculate allocated time: `T_allocated = multiplier * T_prop` (current approach)
- [ ] Use maximum of ALL THREE constraints: `T_sim = max(T_allocated, T_prop + T_pulse, T_resolution)`

#### Task 1.3.5: Convert to periods
- [ ] Use `T_sim` (not `T_allocated`) for period calculation
- [ ] Convert: `sim_time_periods = T_sim / (1 / (frequency_mhz * 1e6))`
- [ ] Note: This may result in 100-200+ periods (much more than typical 3-10)

#### Task 1.3.6: Add comprehensive logging
- [ ] Log all three time components (propagation, pulse, resolution)
- [ ] Log which constraint dominated
- [ ] Log final simulation time in ns and periods
- [ ] Warn if simulation time seems excessive (> 500 ns)

**Updated Code Pattern:**
```python
excitation_type = self.config["simulation_parameters.excitation_type"]
excitation_type_lower = excitation_type.lower() if isinstance(excitation_type, str) else "harmonic"

time_multiplier = self.config["simulation_parameters.simulation_time_multiplier"]
T_prop = diagonal_length_m / 299792458.0  # c in m/s

if excitation_type_lower == "gaussian":
    # Get configuration
    bandwidth_mhz = self.config["simulation_parameters.bandwidth_mhz"]
    target_freq_resolution_mhz = self.config["simulation_parameters.target_freq_resolution_mhz"]
    arma_speedup = self.config["simulation_parameters.s4l_arma_speedup_factor"]  # Default: conservative
    
    # Calculate constraints
    bandwidth_hz = bandwidth_mhz * 1e6
    k = 3.7  # Conservative threshold
    sigma = 0.94 / (np.pi * bandwidth_hz)
    T_pulse = 2 * k * sigma
    
    # Frequency resolution WITH speedup factor
    # arma_speedup = 1.0 → conservative (200 ns for 5 MHz)
    # arma_speedup = 2.0 → moderate (100 ns for 5 MHz, assumes ARMA helps)
    # arma_speedup = 4.0 → aggressive (50 ns for 5 MHz)
    T_resolution = arma_speedup / (target_freq_resolution_mhz * 1e6)
    
    # Three competing requirements
    T_allocated = time_multiplier * T_prop  # Multiplier approach
    T_prop_plus_pulse = T_prop + T_pulse    # Propagation + pulse
    
    # Take maximum
    T_sim = max(T_allocated, T_prop_plus_pulse, T_resolution)
    
    # Log decision
    self._log(f"  - Gaussian excitation timing breakdown:", log_type="info")
    self._log(f"    - Propagation (with multiplier): {T_allocated*1e9:.1f} ns", log_type="info")
    self._log(f"    - Propagation + Pulse: {T_prop_plus_pulse*1e9:.1f} ns", log_type="info")
    self._log(f"    - Frequency resolution ({target_freq_resolution_mhz} MHz, speedup={arma_speedup}): {T_resolution*1e9:.1f} ns", log_type="info")
    
    if T_sim == T_resolution:
        self._log(f"  - FREQUENCY RESOLUTION DOMINATES (typical for antenna characterization)", log_type="highlight")
    elif T_sim == T_prop_plus_pulse:
        self._log(f"  - Pulse duration dominates", log_type="info")
    else:
        self._log(f"  - Multiplier approach sufficient", log_type="info")
    
    self._log(f"  - Final simulation time: {T_sim*1e9:.1f} ns", log_type="highlight")
    sim_time_periods = T_sim / (1 / (frequency_mhz * 1e6))
    
else:
    # Harmonic: use multiplier approach
    sim_time_periods = (time_multiplier * T_prop) / (1 / (frequency_mhz * 1e6))
```

#### Task 1.3.7: Add configuration parameters (DONE in Phase 0)
- [x] Add to `base_config.json`: `"target_freq_resolution_mhz": 5.0`
- [x] Add to `base_config.json`: `"s4l_arma_speedup_factor": 1.0`
- [ ] Document that smaller `target_freq_resolution_mhz` (better resolution) = longer simulation time
- [ ] Document relationship WITH speedup factor: `T_sim = speedup/Δf`
  - speedup=1.0, Δf=5MHz → 200 ns (conservative)
  - speedup=2.0, Δf=5MHz → 100 ns (moderate, test later)
  - speedup=4.0, Δf=5MHz → 50 ns (aggressive, test later)

#### Task 1.3.8: Import numpy if needed
- [ ] Ensure `numpy` is imported as `np` (check existing imports)

**Estimated Time:** 3-4 hours (more complex due to three constraints)  
**Dependencies:** None  
**Testing:** Verify simulation time is appropriate for antenna characterization (expect ~200 ns, 140+ periods)

---

### 1.4 Power Extraction (`goliat/extraction/power_extractor.py`) - CLARIFIED

**File:** `goliat/extraction/power_extractor.py`  
**Current Behavior:** Handles multi-frequency data, extracts at center frequency  
**Status:** Already works correctly! Sim4Life does FFT automatically.

**Key Understanding:** 
- `GetPower()` returns total integrated power (NOT density)
- For Gaussian, Sim4Life provides frequency-dependent power via FFT
- Current code (lines 228-243) already handles multi-frequency correctly

#### Task 1.4.1: Verify GetPower() behavior with Gaussian (Low priority)
- [ ] Test `GetPower(0)` with Gaussian source to confirm it returns total power
- [x] **RESOLVED**: It returns integrated power, not density
- [ ] Document in code comments for future reference

#### Task 1.4.2: Verify multi-frequency extraction
- [ ] Current code (lines 236-243) already handles multi-frequency data
- [ ] Verify it correctly finds center frequency using `np.argmin(np.abs(axis - center_freq_hz))`
- [ ] Test with Gaussian source to ensure it works
- [ ] Add logging to show which frequency was selected

#### Task 1.4.3: Consider bandwidth integration (if needed)
- [ ] If `GetPower()` returns density, implement integration
- [ ] Integrate `EM Input Power(f)` over bandwidth range
- [ ] Use trapezoidal rule or simple sum
- [ ] Document integration method

**Integration Pattern (if needed):**
```python
# Get frequency axis and power data
axis = input_power_output.Data.Axis  # Hz
power_data = input_power_output.Data.GetComponent(0)  # W or W/Hz

# Find bandwidth range
center_freq_hz = self.frequency_mhz * 1e6
bandwidth_mhz = self.config["simulation_parameters.bandwidth_mhz"] or 50.0
bandwidth_hz = bandwidth_mhz * 1e6
start_freq = center_freq_hz - bandwidth_hz / 2
end_freq = center_freq_hz + bandwidth_hz / 2

# Find indices in range
mask = (axis >= start_freq) & (axis <= end_freq)
freqs_in_range = axis[mask]
power_in_range = power_data[mask]

# Integrate (trapezoidal rule)
if len(freqs_in_range) > 1:
    total_power = np.trapz(power_in_range, freqs_in_range)
else:
    total_power = power_in_range[0] * bandwidth_hz  # Fallback
```

#### Task 1.4.4: Add excitation type detection
- [ ] Read `excitation_type` from config
- [ ] Add logging for Gaussian vs Harmonic
- [ ] Use appropriate extraction method based on type

#### Task 1.4.5: Update docstring
- [ ] Document Gaussian source handling
- [ ] Explain power extraction strategy
- [ ] Note any limitations or assumptions

**Estimated Time:** 3-4 hours (includes testing/investigation)  
**Dependencies:** Task 1.1.1 (excitation_type config)  
**Testing:** Compare power values between Harmonic and Gaussian at center frequency

---

### 1.5 SAR Extraction (`goliat/extraction/sar_extractor.py`)

**File:** `goliat/extraction/sar_extractor.py`  
**Current Behavior:** Uses `ExtractedFrequency = "All"`  
**Status:** May work, but needs verification for Gaussian

#### Task 1.5.1: Investigate SAR extraction with Gaussian
- [ ] Test current `ExtractedFrequency = "All"` approach with Gaussian
- [ ] Verify SAR evaluator handles multi-frequency data correctly
- [ ] Determine: Does it extract SAR at all frequencies or just one?
- [ ] Check if "f0" output name means first frequency only

#### Task 1.5.2: Implement frequency selection strategy
- [ ] **Option A:** Extract at center frequency only
  - Set `ExtractedFrequency = center_freq_hz` (not "All")
  - Simpler, matches Harmonic behavior
- [ ] **Option B:** Extract at all frequencies, report center
  - Keep "All", but select center frequency from results
  - More complex, but preserves all data
- [ ] **Option C:** Extract at all frequencies, integrate/average
  - Most complex, may not be needed

**Recommendation:** Start with Option A (center frequency only), test, then consider others if needed.

#### Task 1.5.3: Add excitation type detection
- [ ] Read `excitation_type` from config
- [ ] Set `ExtractedFrequency` based on excitation type
- [ ] For Harmonic: use "All" (current behavior)
- [ ] For Gaussian: use center frequency (or "All" if testing)

**Code Pattern:**
```python
excitation_type = self.config["simulation_parameters.excitation_type"] or "Harmonic"
excitation_type_lower = excitation_type.lower() if isinstance(excitation_type, str) else "harmonic"

em_sensor_extractor = simulation_extractor["Overall Field"]

if excitation_type_lower == "gaussian":
    # Extract at center frequency for Gaussian
    center_freq_hz = self.frequency_mhz * 1e6
    em_sensor_extractor.FrequencySettings.ExtractedFrequency = center_freq_hz, self.units.Hz
    self._log(f"  - Extracting SAR at center frequency: {self.frequency_mhz} MHz", log_type="info")
else:
    # Harmonic: extract all frequencies
    em_sensor_extractor.FrequencySettings.ExtractedFrequency = "All"
```

#### Task 1.5.4: Verify SAR normalization
- [ ] Ensure SAR values are normalized correctly
- [ ] Power used for normalization should match extraction method
- [ ] Compare SAR values between Harmonic and Gaussian at center frequency
- [ ] They should be similar (within numerical tolerance)

#### Task 1.5.5: Update docstring
- [ ] Document frequency selection strategy
- [ ] Explain why center frequency is used for Gaussian
- [ ] Note any limitations

**Estimated Time:** 3-4 hours (includes testing/investigation)  
**Dependencies:** Task 1.1.1 (excitation_type config), Task 1.4 (power extraction)  
**Testing:** Compare SAR values between Harmonic and Gaussian, verify normalization

---

### 1.6 Resonance Frequency Extraction (NEW - CRITICAL FOR ANTENNA CHARACTERIZATION)

**File:** NEW - `goliat/extraction/resonance_extractor.py` OR add to existing `power_extractor.py`  
**Purpose:** Extract antenna resonant frequency and detuning information from Gaussian results  
**Status:** This is the **main goal** of using Gaussian excitation!

#### Task 1.6.1: Create extraction method

**Core functionality:**
```python
def extract_resonance_frequency(self, simulation_extractor):
    """Extract antenna resonant frequency from Gaussian pulse results.
    
    Analyzes frequency-dependent accepted power to identify resonance peak.
    Calculates detuning relative to nominal frequency.
    Generates frequency response plot.
    
    Returns:
        dict: Contains resonant_freq_mhz, detuning_mhz, max_power_w, freq_resolution_mhz
    """
    # Extract full frequency spectrum
    input_power_extractor = simulation_extractor["Input Power"]
    self.document.AllAlgorithms.Add(input_power_extractor)
    input_power_extractor.Update()
    
    input_power_output = input_power_extractor.Outputs["EM Input Power(f)"]
    input_power_output.Update()
    
    # Get continuous frequency data (automatically from FFT)
    freq_axis_hz = input_power_output.Data.Axis  # Full freq array
    power_data_w = input_power_output.Data.GetComponent(0)  # Power at each freq
    
    # Convert to MHz
    freq_axis_mhz = freq_axis_hz / 1e6
    
    # Find resonant frequency (maximum accepted power)
    max_idx = np.argmax(power_data_w)
    resonant_freq_mhz = freq_axis_mhz[max_idx]
    max_power_w = power_data_w[max_idx]
    
    # Calculate detuning
    nominal_freq_mhz = self.frequency_mhz
    detuning_mhz = resonant_freq_mhz - nominal_freq_mhz
    
    # Calculate frequency resolution
    freq_resolution_mhz = (freq_axis_hz[1] - freq_axis_hz[0]) / 1e6
    
    # Log results
    self._log(f"\n{'='*80}", log_type="highlight")
    self._log(f"  ANTENNA RESONANCE ANALYSIS", log_type="highlight")
    self._log(f"{'='*80}", log_type="highlight")
    self._log(f"  Nominal frequency: {nominal_freq_mhz} MHz", log_type="info")
    self._log(f"  Detected resonance: {resonant_freq_mhz:.2f} MHz", log_type="highlight")
    self._log(f"  Detuning: {detuning_mhz:+.2f} MHz ({detuning_mhz/nominal_freq_mhz*100:+.1f}%)", 
              log_type="highlight" if abs(detuning_mhz) > 10 else "info")
    self._log(f"  Max power at resonance: {max_power_w*1000:.2f} mW", log_type="info")
    self._log(f"  Frequency resolution: {freq_resolution_mhz:.2f} MHz", log_type="info")
    self._log(f"  Number of frequency points: {len(freq_axis_hz)}", log_type="info")
    self._log(f"{'='*80}\n", log_type="highlight")
    
    # Store results
    resonance_data = {
        "resonant_freq_mhz": float(resonant_freq_mhz),
        "nominal_freq_mhz": float(nominal_freq_mhz),
        "detuning_mhz": float(detuning_mhz),
        "detuning_percent": float(detuning_mhz / nominal_freq_mhz * 100),
        "max_power_w": float(max_power_w),
        "freq_resolution_mhz": float(freq_resolution_mhz),
        "num_freq_points": int(len(freq_axis_hz)),
        "frequency_axis_mhz": freq_axis_mhz.tolist(),  # For plotting
        "power_data_w": power_data_w.tolist(),  # For plotting
    }
    
    # Clean up
    self.document.AllAlgorithms.Remove(input_power_extractor)
    
    return resonance_data
```

#### Task 1.6.2: Generate frequency response plot
- [ ] Create matplotlib plot of power vs frequency
- [ ] Mark resonant frequency with vertical line
- [ ] Mark nominal frequency with vertical line
- [ ] Add bandwidth indicators (±BW/2 at half-power points)
- [ ] Save as PNG in results directory
- [ ] Include in HTML report

**Plot code:**
```python
def plot_frequency_response(self, freq_axis_mhz, power_data_w, 
                           resonant_freq_mhz, nominal_freq_mhz, 
                           output_path):
    """Generate and save frequency response plot."""
    import matplotlib.pyplot as plt
    
    fig, ax = plt.subplots(figsize=(12, 7))
    
    # Plot power vs frequency
    ax.plot(freq_axis_mhz, power_data_w * 1000, 'b-', linewidth=2, label='Accepted Power')
    
    # Mark resonance
    ax.axvline(resonant_freq_mhz, color='r', linestyle='--', linewidth=2,
               label=f'Resonance: {resonant_freq_mhz:.1f} MHz')
    
    # Mark nominal
    ax.axvline(nominal_freq_mhz, color='g', linestyle='--', linewidth=2,
               label=f'Nominal: {nominal_freq_mhz} MHz')
    
    # Labels and formatting
    detuning = resonant_freq_mhz - nominal_freq_mhz
    ax.set_xlabel('Frequency (MHz)', fontsize=14)
    ax.set_ylabel('Accepted Power (mW)', fontsize=14)
    ax.set_title(f'Antenna Frequency Response\nDetuning: {detuning:+.1f} MHz ({detuning/nominal_freq_mhz*100:+.1f}%)', 
                 fontsize=16, fontweight='bold')
    ax.grid(True, alpha=0.3, linestyle=':', linewidth=1)
    ax.legend(fontsize=12, loc='best')
    
    # Format axes
    ax.tick_params(labelsize=12)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    self._log(f"  - Frequency response plot saved: {output_path}", log_type="success")
```

#### Task 1.6.3: Integrate into results extraction pipeline
- [ ] Call `extract_resonance_frequency()` from `ResultsExtractor.extract()` when Gaussian
- [ ] Add to `results_data` dictionary
- [ ] Include in JSON output
- [ ] Add to HTML report generation

#### Task 1.6.4: Warning for severe detuning
- [ ] Check if `abs(detuning_mhz) > threshold` (e.g., 50 MHz)
- [ ] Log prominent warning if antenna is significantly detuned
- [ ] Suggest re-running simulation at detected resonance for better accuracy
- [ ] Document that SAR pattern may be affected by operating off-resonance

**Warning code:**
```python
if abs(detuning_mhz) > 50:
    self._log("\n" + "!" * 80, log_type="warning")
    self._log("  WARNING: SIGNIFICANT ANTENNA DETUNING DETECTED!", log_type="warning")
    self._log(f"  The antenna has shifted {detuning_mhz:+.1f} MHz from nominal frequency.", log_type="warning")
    self._log("  Consider:", log_type="warning")
    self._log(f"    1. Re-running simulation at detected resonance ({resonant_freq_mhz:.0f} MHz)", log_type="warning")
    self._log("    2. Verifying antenna design for this placement scenario", log_type="warning")
    self._log("    3. Checking if SAR pattern is affected by off-resonance operation", log_type="warning")
    self._log("!" * 80 + "\n", log_type="warning")
```

#### Task 1.6.5: Add to HTML report template
- [ ] Create new section "Antenna Characterization" in HTML report
- [ ] Display resonance frequency, detuning, and resolution
- [ ] Embed frequency response plot
- [ ] Add interpretation text explaining significance

#### Task 1.6.6: Unit tests
- [ ] Test with synthetic frequency data (known peak)
- [ ] Test edge cases (peak at boundary, flat response, multiple peaks)
- [ ] Verify calculation accuracy
- [ ] Test plot generation

**Estimated Time:** 6-8 hours (new functionality, plotting, integration)  
**Dependencies:** Task 1.4 (power extraction)  
**Testing:** 
- Run with Gaussian config
- Verify resonance detection matches visual inspection
- Compare free-space (no detuning) vs near-field (detuning expected)
- Validate plot generation and HTML integration

**Priority:** HIGH - This is the main deliverable for Gaussian excitation support!

---

## Phase 2: Configuration Files

### 2.1 Harmonic Config (`configs/near_field_harmonic.json`)

**Purpose:** Baseline config for comparison testing  
**Based on:** `configs/near_field_config.json`

#### Task 2.1.1: Create config file
- [ ] Copy `configs/near_field_config.json` as template
- [ ] Set `excitation_type: "Harmonic"`
- [ ] Reduce to single phantom: `["thelonious"]`
- [ ] Reduce to single frequency: Keep only `"700"` in `antenna_config`
- [ ] Reduce to single placement: Keep only `"front_of_eyes"` with `"center"` position and `"vertical"` orientation
- [ ] Keep all other settings identical (gridding, materials, etc.)

#### Task 2.1.2: Verify config structure
- [ ] Ensure extends `base_config.json`
- [ ] Verify `study_type: "near_field"`
- [ ] Check all required fields present
- [ ] Validate JSON syntax

**Estimated Time:** 30 minutes  
**Dependencies:** None  
**Testing:** Load config, verify it parses correctly

---

### 2.2 Gaussian Config (`configs/near_field_gaussian.json`) - UPDATED

**Purpose:** Test config for Gaussian excitation with antenna characterization  
**Based on:** `configs/near_field_harmonic.json`

#### Task 2.2.1: Create config file
- [ ] Copy `configs/near_field_harmonic.json` as template
- [ ] Add simulation_parameters section with Gaussian-specific settings:
  - `"excitation_type": "Gaussian"`
  - `"bandwidth_mhz": 50.0` (narrow for high resolution, covers ±25 MHz)
  - `"target_freq_resolution_mhz": 5.0` (for 200 ns simulation time)
- [ ] Keep all other settings identical to harmonic config

**Example addition to config:**
```json
"simulation_parameters": {
    "excitation_type": "Gaussian",
    "bandwidth_mhz": 50.0,
    "target_freq_resolution_mhz": 5.0,
    "simulation_time_multiplier": 3.5,
    "global_auto_termination": "GlobalAutoTerminationUserDefined",
    "convergence_level_dB": -15
}
```

#### Task 2.2.2: Document simulation time expectations
- [ ] Add comment: "Note: Simulation time will be ~200 ns (140 periods @ 700 MHz)"
- [ ] Add comment: "This is driven by frequency resolution requirement, NOT pulse duration"
- [ ] Add comment: "For better resolution, decrease target_freq_resolution_mhz (increases sim time)"

#### Task 2.2.3: Create wide-bandwidth variant (optional)
- [ ] Create `near_field_gaussian_wide.json` for comparison
- [ ] Set `bandwidth_mhz: 150.0` (covers ±75 MHz)
- [ ] Keep same frequency resolution
- [ ] Use for cases where large detuning expected

#### Task 2.2.4: Verify config structure
- [ ] Ensure extends `base_config.json`
- [ ] Verify `study_type: "near_field"`
- [ ] Check all Gaussian parameters are set correctly
- [ ] Validate JSON syntax

**Estimated Time:** 45 minutes (includes documentation)  
**Dependencies:** Task 2.1.1  
**Testing:** Load config, verify it parses correctly, check simulation time calculation

---

## Phase 3: Testing & Validation

### 3.1 Unit Tests

#### Task 3.1.1: Test source setup with Gaussian
- [ ] Test `SourceSetup.setup_source_and_sensors()` with Gaussian config
- [ ] Verify excitation type is set to Gaussian
- [ ] Verify bandwidth is read from config
- [ ] Verify far-field sensors are added
- [ ] Verify extracted frequencies are correct (21 samples across bandwidth)

#### Task 3.1.2: Test material setup with Gaussian
- [ ] Test `MaterialSetup._assign_antenna_materials()` with Gaussian config
- [ ] Verify Copper components are forced to PEC
- [ ] Verify warning message is logged
- [ ] Verify other materials (Rogers, PEC) are handled correctly

#### Task 3.1.3: Test simulation time calculation
- [ ] Test `BaseSetup._apply_simulation_time_and_termination()` with Gaussian
- [ ] Test with small bbox (should use pulse duration)
- [ ] Test with large bbox (should use multiplier)
- [ ] Verify transition point is correct
- [ ] Verify logging is correct

#### Task 3.1.4: Test power extraction
- [ ] Test `PowerExtractor._extract_near_field_power()` with Gaussian
- [ ] Verify multi-frequency data is handled
- [ ] Verify center frequency is selected correctly
- [ ] Compare with Harmonic power (should be similar)

#### Task 3.1.5: Test SAR extraction
- [ ] Test `SarExtractor.extract_sar_statistics()` with Gaussian
- [ ] Verify frequency selection works
- [ ] Verify SAR values are reasonable
- [ ] Compare with Harmonic SAR (should be similar at center frequency)

**Estimated Time:** 4-6 hours  
**Dependencies:** All Phase 1 tasks  
**Testing:** Run test suite, fix any failures

---

### 3.2 Integration Tests

#### Task 3.2.1: End-to-end Harmonic test
- [ ] Run full simulation with Harmonic config
- [ ] Verify setup, run, and extract phases complete
- [ ] Verify results are reasonable
- [ ] Document baseline values (power, SAR)

#### Task 3.2.2: End-to-end Gaussian test
- [ ] Run full simulation with Gaussian config
- [ ] Verify setup, run, and extract phases complete
- [ ] Verify results are reasonable
- [ ] Compare with Harmonic baseline

#### Task 3.2.3: Compare results
- [ ] Power at center frequency: Should be similar between Harmonic and Gaussian
- [ ] SAR at center frequency: Should be similar (within tolerance)
- [ ] Simulation time: Should be longer for Gaussian (due to pulse duration)
- [ ] Material assignment: Copper should be PEC in Gaussian, normal in Harmonic

#### Task 3.2.4: Test edge cases
- [ ] Very small bandwidth (10 MHz): Pulse duration should be very long
- [ ] Very large bandwidth (200 MHz): Pulse duration should be short
- [ ] Very small bbox: Pulse duration should dominate
- [ ] Very large bbox: Multiplier should dominate

**Estimated Time:** 4-6 hours  
**Dependencies:** All Phase 1 and Phase 2 tasks  
**Testing:** Run full simulations, analyze results

---

### 3.3 Validation Against Requirements

#### Task 3.3.1: Verify Sim4Life compatibility
- [ ] Verify simulations run without errors in Sim4Life
- [ ] Verify results can be extracted correctly
- [ ] Verify no Sim4Life API errors

#### Task 3.3.2: Verify backward compatibility
- [ ] Existing Harmonic configs still work
- [ ] No breaking changes to existing functionality
- [ ] Default behavior unchanged (Harmonic)

#### Task 3.3.3: Verify power extraction accuracy
- [ ] Power values are reasonable
- [ ] Power normalization works correctly
- [ ] SAR normalization uses correct power

#### Task 3.3.4: Verify SAR accuracy
- [ ] SAR values match Harmonic at center frequency
- [ ] SAR normalization is correct
- [ ] Peak SAR locations are reasonable

**Estimated Time:** 2-3 hours  
**Dependencies:** Task 3.2  
**Testing:** Manual verification, result analysis

---

## Phase 4: Documentation

### 4.1 Code Documentation

#### Task 4.1.1: Update source_setup.py docstrings
- [ ] Update class docstring
- [ ] Update `setup_source_and_sensors()` docstring
- [ ] Document `excitation_type` and `bandwidth_mhz` parameters
- [ ] Remove free-space references

#### Task 4.1.2: Update material_setup.py docstrings
- [ ] Update `_assign_antenna_materials()` docstring
- [ ] Document Copper→PEC workaround applies to all Gaussian
- [ ] Remove free-space references

#### Task 4.1.3: Update base_setup.py docstrings
- [ ] Update `_apply_simulation_time_and_termination()` docstring
- [ ] Document Gaussian pulse duration calculation
- [ ] Explain when pulse duration dominates

#### Task 4.1.4: Update power_extractor.py docstrings
- [ ] Document Gaussian source handling
- [ ] Explain power extraction strategy
- [ ] Document any integration methods

#### Task 4.1.5: Update sar_extractor.py docstrings
- [ ] Document frequency selection for Gaussian
- [ ] Explain why center frequency is used
- [ ] Document any limitations

**Estimated Time:** 2 hours  
**Dependencies:** All Phase 1 tasks  
**Testing:** Review docstrings, ensure clarity

---

### 4.2 User Documentation

#### Task 4.2.1: Update configuration guide
- [ ] Document `excitation_type` parameter
- [ ] Document `bandwidth_mhz` parameter
- [ ] Add examples of Harmonic vs Gaussian configs
- [ ] Explain when to use each

**File:** `docs/developer_guide/configuration.md`

#### Task 4.2.2: Update technical guide
- [ ] Add section on Gaussian excitation
- [ ] Explain simulation time calculation
- [ ] Document material limitations
- [ ] Add troubleshooting section

**File:** `docs/developer_guide/technical_guide.md`

#### Task 4.2.3: Update API reference
- [ ] Document new config parameters
- [ ] Update any API changes
- [ ] Add examples

**File:** `docs/reference/api_reference.md`

#### Task 4.2.4: Create user guide section
- [ ] Explain Gaussian vs Harmonic excitation
- [ ] When to use each
- [ ] Configuration examples
- [ ] Known limitations

**File:** `docs/user_guide/user_guide.md` (or new section)

**Estimated Time:** 3-4 hours  
**Dependencies:** All implementation tasks  
**Testing:** Review documentation, ensure accuracy

---

## Phase 5: Error Handling & Edge Cases

### 5.1 Configuration Validation

#### Task 5.1.1: Validate excitation_type
- [ ] Check if set when needed
- [ ] Validate value is "Harmonic" or "Gaussian" (case-insensitive)
- [ ] Provide helpful error messages

#### Task 5.1.2: Validate bandwidth_mhz
- [ ] Check if set when `excitation_type == "Gaussian"`
- [ ] Validate value is positive
- [ ] Validate value is reasonable (e.g., 10-200 MHz)
- [ ] Provide helpful error messages

#### Task 5.1.3: Validate frequency range
- [ ] Check `center_frequency - bandwidth/2 > 0`
- [ ] Check `center_frequency + bandwidth/2` is reasonable
- [ ] Provide helpful error messages

**Estimated Time:** 2 hours  
**Dependencies:** Phase 1 tasks  
**Testing:** Test with invalid configs, verify error messages

---

### 5.2 Runtime Error Handling

#### Task 5.2.1: Handle GetPower() failures
- [ ] Graceful fallback if `GetPower()` not available
- [ ] Fallback to frequency axis extraction
- [ ] Log warnings appropriately

#### Task 5.2.2: Handle frequency extraction failures
- [ ] Handle missing frequency in extracted data
- [ ] Handle empty frequency axis
- [ ] Provide helpful error messages

#### Task 5.2.3: Handle SAR extraction failures
- [ ] Handle missing SAR data
- [ ] Handle frequency selection failures
- [ ] Provide helpful error messages

**Estimated Time:** 2 hours  
**Dependencies:** Phase 1 tasks  
**Testing:** Test error scenarios, verify graceful handling

---

## Phase 6: Performance & Optimization

### 6.1 Performance Considerations

#### Task 6.1.1: Monitor simulation time
- [ ] Compare simulation times between Harmonic and Gaussian
- [ ] Verify Gaussian doesn't take excessively long
- [ ] Document any performance impacts

#### Task 6.1.2: Monitor memory usage
- [ ] Gaussian extracts 21 frequencies vs 1 for Harmonic
- [ ] Verify memory usage is acceptable
- [ ] Document any memory impacts

#### Task 6.1.3: Optimize if needed
- [ ] If performance issues, consider optimizations
- [ ] May need to reduce number of extracted frequencies
- [ ] May need to optimize frequency selection

**Estimated Time:** 2-3 hours  
**Dependencies:** Phase 3 testing  
**Testing:** Profile performance, identify bottlenecks

---

## Summary

### Estimated Total Time (UPDATED)
- **Phase 0 (Config Design):** 15 minutes
- **Phase 1 (Core Code):** 18-24 hours (includes new resonance extraction)
  - 1.1 Source setup: 2-3 hours
  - 1.2 Material setup: 1 hour
  - 1.3 Simulation time (with tunable speedup factor): 3-4 hours
  - 1.4 Power extraction (minimal): 1-2 hours
  - 1.5 SAR extraction: 3-4 hours
  - **1.6 Resonance extraction (NEW): 6-8 hours ← Critical deliverable**
- **Phase 2 (Config Files):** 1-2 hours
- **Phase 3 (Testing):** 12-18 hours (more comprehensive)
- **Phase 4 (Documentation):** 5-6 hours
- **Phase 5 (Error Handling):** 4 hours
- **Phase 6 (Performance):** 2-3 hours
- **Total:** 42-57 hours (original estimate)

**Post-Implementation Optimization (Optional):**
- **Phase 7 (Sensitivity Study):** 4-6 hours
  - Run with `s4l_arma_speedup_factor` = [1.0, 1.5, 2.0, 3.0, 4.0]
  - Compare results, measure accuracy vs. sim time
  - Update default based on findings

### Critical Path (UPDATED)
1. **Config setup (0.1)** - Add tunable parameters (15 min)
2. **Source setup changes (1.1)** - Enable Gaussian excitation
3. **Material setup changes (1.2)** - Copper→PEC for Sim4Life compatibility
4. **Simulation time calculation (1.3)** - Implement with `s4l_arma_speedup_factor` (conservative default)
5. **Resonance extraction (1.6) ← PRIMARY GOAL** - Detect antenna detuning
6. Power/SAR extraction (1.4, 1.5) - Support frequency-dependent data
7. Integration testing (3.2) - Validate end-to-end workflow
8. **Optimization (Phase 7 - OPTIONAL)** - Test different speedup factors, update defaults

### Key Understandings (RESOLVED)
1. ✅ **Power extraction:** `GetPower()` returns total integrated power (not density)
2. ✅ **Frequency data:** Sim4Life automatically provides continuous frequency spectra via FFT
3. ✅ **Frequency resolution:** Determined by simulation time (Δf = 1/T_sim), NOT manual sampling
4. ✅ **Simulation time:** Frequency resolution dominates (~200 ns) over pulse (~44 ns) and propagation (~5 ns)
5. ✅ **PML boundaries:** 1× propagation time sufficient (waves absorbed, not reflected back)

### Key Risks (UPDATED)
1. **Simulation time uncertainty (MITIGATED BY TUNABLE PARAMETER):**
   - Theoretical: ~200 ns (140 periods) vs. typical ~5-10 ns
   - **Unknown:** Sim4Life's internal processing (ARMA, interpolation, zero-padding)
   - **Risk mitigation:** Start conservative (speedup=1.0), make tunable for later optimization
   - **Benefit:** Implementation guaranteed correct, can optimize after it works
   
2. **Frequency resolution vs bandwidth trade-off:** 
   - Narrow bandwidth (50 MHz): Better resolution, may need multiple runs if shift > 25 MHz
   - Wide bandwidth (150 MHz): Single run coverage, but longer simulation
   - **Mitigation:** Start with 50 MHz (covers ±25 MHz), can adjust in config

3. **Performance impact (MEASURED POST-IMPLEMENTATION):**
   - Conservative default may make simulations 20-40× longer (~200 ns vs ~5 ns)
   - But provides much more information (full frequency response)
   - Optional Phase 7 optimization can reduce this after validation

4. **Implementation correctness:**
   - Conservative defaults guarantee correctness
   - Tunable parameters enable optimization without code changes
   - Phase 7 sensitivity study validates speedup assumptions (optional)

### Success Criteria (UPDATED)
- [ ] Gaussian config runs end-to-end without errors
- [ ] **Resonance frequency extracted accurately from continuous frequency data** ← PRIMARY
- [ ] **Detuning quantified and reported with clear warnings** ← PRIMARY
- [ ] **Frequency response plot generated** ← PRIMARY
- [ ] Simulation time accounts for frequency resolution requirement (~200 ns)
- [ ] Power extraction works correctly across full frequency range
- [ ] SAR extraction works correctly at center frequency
- [ ] Copper→PEC workaround applies correctly for all Gaussian
- [ ] Backward compatibility maintained (Harmonic simulations unchanged)
- [ ] Frequency resolution adequate for narrowband antennas (≤5 MHz)
- [ ] Documentation complete with practical examples

### Next Steps (PRAGMATIC IMPLEMENTATION APPROACH)

**Stage 0: Quick Config Setup (15 minutes)**
1. Phase 0 (Config Design) - Add tunable parameters to `base_config.json`

**Stage 1: Core Infrastructure (18-24 hours)**
2. Phase 1.1 (Source Setup) - Enable Gaussian from config
3. Phase 1.2 (Material Setup) - Copper→PEC for all Gaussian
4. Phase 1.3 (Simulation Time) - Implement with `s4l_arma_speedup_factor` (default: 1.0 = conservative)
5. Phase 1.6 (Resonance Extraction) - **PRIMARY DELIVERABLE** ← Main goal!
6. Phase 1.4/1.5 (Power/SAR) - Verify existing code works with Gaussian

**Stage 2: Testing & Validation (17-23 hours)**
7. Phase 2 (Config Files) - Create test configs
8. Phase 3 (Testing) - Comprehensive validation
   - Free-space: No detuning expected (baseline)
   - Near-field: Detect and quantify detuning
   - Compare with harmonic at detected resonance

**Stage 3: Polish (11-15 hours)**
9. Phase 4 (Documentation) - User guides and API docs
10. Phase 5 (Error Handling) - Edge cases and validation
11. Phase 6 (Performance) - Monitoring and profiling

**Stage 4: Optimization (OPTIONAL, 4-6 hours)**
12. Phase 7 (Sensitivity Study) - Test different `s4l_arma_speedup_factor` values
   - Run with [1.0, 1.5, 2.0, 3.0, 4.0]
   - Measure accuracy vs. sim time tradeoff
   - Update default if speedup is validated

### Practical Antenna Characteristics (For Reference)
From experimental measurements:
- **Antenna bandwidth:** 10-30 MHz (narrowband, Q ≈ 20-40)
- **Maximum detuning:** 50-100 MHz when device near body
- **Required resolution:** ≤5 MHz (at least 2-6 points across antenna bandwidth)
- **Simulation time implication:** ≥200 ns (versus typical 5-10 ns for harmonic)

### Key Formulas (Quick Reference)

**Simulation Time (THREE constraints):**
```
T_sim = max(multiplier · L_bbox/c, L_bbox/c + 2k·σ, 1/Δf_target)
```
Where:
- `σ = 0.94/(π·BW)` (pulse temporal width)
- `k = 3.7` (conservative threshold)
- `Δf_target` = target frequency resolution (typically 5 MHz)

**Typical values for 700 MHz, L_bbox = 0.5 m, BW = 50 MHz:**
- Component 1 (multiplier): ~6 ns
- Component 2 (propagation + pulse): ~46 ns
- Component 3 (resolution): **200 ns ← DOMINATES**

**Frequency Resolution:**
```
Δf = 1 / T_sim
```
- T_sim = 200 ns → Δf = 5 MHz
- T_sim = 500 ns → Δf = 2 MHz (better resolution, longer simulation)

---

## Notes

### Resolved Questions
1. ✅ **Power extraction:** Returns total integrated power (FFT magnitude)
2. ✅ **Frequency data:** Continuous arrays from automatic FFT post-processing
3. ✅ **Resolution:** Set by simulation time, not manual sampling
4. ✅ **Propagation:** 1× sufficient with PML boundaries
5. ✅ **Convergence:** May be unreliable, use explicit time calculation

### Remaining Questions for Implementation
**To be answered during implementation:**
1. Optimal bandwidth for different use cases (50 vs 150 MHz)?
2. Should we implement two-stage detection (wide then narrow)?
3. How to handle cases where resonance is outside excitation bandwidth?
4. Can we extract S11 directly if voltage/current outputs exist?

**To be answered by Phase 7 (Optional Sensitivity Study - AFTER implementation):**
5. ❓ What is the actual minimum T_sim for accurate peak detection?
6. ❓ Does Sim4Life use ARMA, zero-padding, or other advanced processing?
7. ❓ Can we achieve <200 ns simulation times with acceptable accuracy?
8. ❓ What is the optimal `s4l_arma_speedup_factor` value?

### References
- `docs/technical/gaussian_pulse_timing_analysis.md` - Comprehensive mathematical analysis (UPDATED)
- `goliat/setups/source_setup.py` - Current source setup
- `goliat/setups/material_setup.py` - Current material setup  
- `goliat/setups/base_setup.py` - Current time calculation
- `goliat/extraction/power_extractor.py` - Current power extraction (lines 228-243: multi-frequency handling)
- `goliat/extraction/sar_extractor.py` - Current SAR extraction
- `docs/reference/useful_s4l_snippets.md` - Sim4Life API examples (section 7: Results extraction)

