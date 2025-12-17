# Dispersion Model Fitting and Material Properties Guide

This guide documents how frequency-dependent material properties (dispersion) work in GOLIAT, including the IT'IS database, Cole-Cole model, cache generation, and Lorentz fitting for FDTD simulations.

## Table of Contents
1. [Overview](#overview)
2. [IT'IS Material Database](#itis-material-database)
3. [Cole-Cole Dispersion Model](#cole-cole-dispersion-model)
4. [Material Properties Cache](#material-properties-cache)
5. [Lorentz Model Fitting for FDTD](#lorentz-model-fitting-for-fdtd)
6. [Sim4Life Python API](#sim4life-python-api)
7. [Complete Workflow](#complete-workflow)

---

## Overview

### When Dispersion is Needed
For multisine FDTD simulations with multiple frequencies (e.g., 700 MHz and 835 MHz), materials need frequency-dependent properties. Simple constant permittivity/conductivity won't work because biological tissues exhibit significant dispersion.

### Key Relationships
```
ε*(ω) = ε'(ω) - jε''(ω)    # Complex permittivity
ε'' = σ / (ω·ε₀)           # Conductivity contribution to imaginary part

Where:
- ε'  = real permittivity (dielectric constant)
- ε'' = imaginary permittivity (loss)
- σ   = conductivity (S/m)
- ω   = 2πf (angular frequency)
- ε₀  = 8.854187817e-12 F/m (vacuum permittivity)
```

### Physical Behavior of Biological Tissues
At RF/microwave frequencies (100 MHz - 10 GHz):
- **ε' decreases** with increasing frequency
- **σ increases** with increasing frequency

This is due to various polarization mechanisms (ionic, dipolar) that cannot follow fast-changing fields.

---

## IT'IS Material Database

### Source: IT'IS Foundation V5.0 Database

The IT'IS Foundation provides a comprehensive database of tissue properties based on Gabriel's 4-Cole-Cole model parameters. We use **data/itis_v5.db** (SQLite format).

### Database Structure

```sql
-- Key tables:
materials (mat_id, name, ver_id)          -- Tissue names
vectors (mat_id, prop_id, vals)           -- Parameter arrays (BLOB)
properties (prop_id, name, unit)          -- Property definitions

-- Gabriel Parameters property ID:
'37f803e4-fc61-4b2b-9a41-39bd6569eb28'
```

### Gabriel Parameters Format

Each tissue has a 14-element float64 array:
```
[ef, del1, tau1, alf1, del2, tau2, alf2, del3, tau3, alf3, del4, tau4, alf4, sigma]

Where:
- ef      = ε∞ (epsilon infinity, high-frequency limit)
- del1-4  = Δε for each Cole-Cole pole
- tau1-4  = relaxation time (units: ps, ns, µs, ms for poles 1-4)
- alf1-4  = α parameter (0 = Debye, >0 = Cole-Cole broadening)
- sigma   = ionic conductivity (S/m)
```

### Tau Unit Conversion

**Critical**: The database uses mixed time units that must be converted to seconds:
```python
tau1_seconds = tau1 * 1e-12  # picoseconds
tau2_seconds = tau2 * 1e-9   # nanoseconds
tau3_seconds = tau3 * 1e-6   # microseconds
tau4_seconds = tau4 * 1e-3   # milliseconds
```

---

## Cole-Cole Dispersion Model

### 4-Cole-Cole Formula

The Gabriel model uses 4 Cole-Cole poles:

```
ε*(ω) = ε∞ + Σₙ [Δεₙ / (1 + (jωτₙ)^(1-αₙ))] + σ/(jωε₀)
```

Where:
- ε∞ = high-frequency permittivity
- Δεₙ = permittivity increment for pole n
- τₙ = relaxation time for pole n
- αₙ = Cole-Cole broadening parameter (0 = pure Debye)
- σ = ionic conductivity

### Python Implementation

```python
import numpy as np

EPS_0 = 8.854187817e-12  # F/m

def cole_cole(f_hz: float, ef: float, poles: list, sigma_ionic: float) -> tuple:
    """
    Calculate eps_r and sigma at frequency f_hz using 4-Cole-Cole model.
    
    Args:
        f_hz: Frequency in Hz
        ef: Epsilon infinity
        poles: List of (delta_eps, tau_seconds, alpha) tuples
        sigma_ionic: Ionic conductivity in S/m
        
    Returns:
        (eps_r, sigma) - real permittivity and total conductivity
    """
    omega = 2 * np.pi * f_hz
    eps_complex = ef + 0j
    
    for delta_eps, tau, alpha in poles:
        if delta_eps != 0 and tau != 0 and alpha < 1:
            eps_complex += delta_eps / (1 + (1j * omega * tau)**(1 - alpha))
    
    # Add ionic conductivity contribution
    eps_complex -= 1j * sigma_ionic / (omega * EPS_0)
    
    eps_r = float(np.real(eps_complex))
    sigma = float(-omega * EPS_0 * np.imag(eps_complex))
    
    return eps_r, sigma
```

### Validated Values

Values computed from IT'IS V5.0 database match Sim4Life GUI exactly:

| Tissue | Frequency | ε_r | σ (S/m) |
|--------|-----------|-----|---------|
| Brain (Grey Matter) | 700 MHz | 53.90 | 0.860 |
| Muscle | 2450 MHz | 52.73 | 1.739 |
| Skin | 835 MHz | 41.76 | 0.845 |
| Fat | 5800 MHz | 9.86 | 0.832 |
| Bone (Cortical) | 450 MHz | 13.04 | 0.096 |

---

## Material Properties Cache

### Purpose

The cache (`data/material_properties_cache.json`) stores precomputed ε_r and σ values at multiple frequencies, avoiding runtime Cole-Cole calculations and enabling fast Lorentz fitting.

### Cache Generation

Generate from IT'IS V5.0 database:

```python
# scripts/generate_material_cache_from_excel.py (or use DB directly)
# Generates: data/material_properties_cache.json

FREQUENCIES_MHZ = [450, 700, 835, 1450, 2140, 2450, 3500, 5200, 5800]
```

### Cache Format

```json
{
  "source": "IT'IS Foundation Database V5.0 (4-Cole-Cole Gabriel model)",
  "generated": "2024-12-14T17:00:00",
  "frequencies_mhz": [450, 700, 835, 1450, 2140, 2450, 3500, 5200, 5800],
  "model": "4-pole Cole-Cole",
  "tissues": {
    "Brain (Grey Matter)": {
      "450": {"eps_r": 56.55, "sigma": 0.7585},
      "700": {"eps_r": 53.90, "sigma": 0.8596},
      ...
    },
    ...
  }
}
```

### Material Name Mapping

Phantom entity names → IT'IS database names via `data/material_name_mapping.json`:

```json
{
  "thelonious": {
    "Brain_grey_matter": "Brain (Grey Matter)",
    "Muscle": "Muscle",
    "SAT": "SAT (Subcutaneous Fat)",
    ...
  },
  "duke": { ... },
  "ella": { ... },
  "eartha": { ... }
}
```

### Cache API

```python
from goliat.dispersion import get_material_properties, load_material_cache

# Load cache (cached in memory after first load)
cache = load_material_cache()

# Get properties at specific frequencies
props = get_material_properties("Brain (Grey Matter)", [700, 835])
# Returns: [{"eps_r": 53.90, "sigma": 0.86}, {"eps_r": 52.28, "sigma": 0.99}]
```

---

## Lorentz Model Fitting for FDTD

### Why Lorentz?

Sim4Life FDTD requires dispersion models in specific formats (Debye, Drude, Lorentz). The **two-pole Lorentz model** is used because:

1. Can model both increasing and decreasing ε' with frequency
2. FDTD-stable when operating below resonance
3. Provides good fit with minimal poles

### Lorentz Formula

```
ε(ω) = ε∞ + Σᵢ [Δεᵢ × ω₀ᵢ² / (ω₀ᵢ² - ω² + jγᵢω)]

Where:
- ε∞    = base permittivity
- Δεᵢ   = static permittivity contribution
- ω₀ᵢ   = resonance angular frequency
- γᵢ    = damping factor
```

### Fitting Implementation

```python
from goliat.dispersion import fit_two_pole_lorentz

# Target frequencies and properties
frequencies_hz = [700e6, 835e6, 2450e6]
eps_r_targets = [53.90, 52.28, 48.46]
sigma_targets = [0.86, 0.99, 2.00]

# Fit two-pole Lorentz model
params = fit_two_pole_lorentz(frequencies_hz, eps_r_targets, sigma_targets)

# params contains:
# - eps_inf: base permittivity
# - sigma_dc: DC conductivity
# - poles: list of PoleFit(delta_eps, f_res_hz, damping_hz)
# - fit_error: RMS error
```

---

## Sim4Life Python API

### Model Types

| Type | Index | Use Case |
|------|-------|----------|
| Debye | 0 | Normal dispersion |
| Drude | 1 | Metallic behavior |
| Lorentz | 2 | Resonance, works for both directions |
| Generic | 3 | Custom/inactive |

### Creating Dispersive Materials

```python
import s4l_v1.simulation.emfdtd as emfdtd
import XMaterials as xm

# Create material with LinearDispersive model
material_settings = emfdtd.MaterialSettings()
material_settings.Name = "Brain (Multisine)"
material_settings.ElectricProps.MaterialModel = (
    material_settings.ElectricProps.MaterialModel.enum.LinearDispersive
)

# Configure dispersion
disp = material_settings.raw.ElectricDispersiveSettings
disp.StartFrequency = 350e6
disp.EndFrequency = 6e9
disp.Permittivity = params.eps_inf
disp.Conductivity = params.sigma_dc

# Create Lorentz poles
poles = []
for pole_fit in params.poles:
    pole = xm.LinearDispersionPole()
    pole.Active = True
    pole.Type = xm.LinearDispersionPole.ePoleType.kLorentz
    pole[xm.LinearDispersionPole.ePoleProperty.kLorentzAmplitude] = 1.0
    pole[xm.LinearDispersionPole.ePoleProperty.kLorentzFrequency] = pole_fit.f_res_hz
    pole[xm.LinearDispersionPole.ePoleProperty.kLorentzStaticPermittivity] = pole_fit.delta_eps
    pole[xm.LinearDispersionPole.ePoleProperty.kLorentzInfinityPermittivity] = 0.0
    pole[xm.LinearDispersionPole.ePoleProperty.kLorentzDamping] = pole_fit.damping_hz
    poles.append(pole)

# CRITICAL: Must assign as list, cannot modify in-place
disp.Poles = poles

# Add to simulation
simulation.Add(material_settings, [entity])
```

### Critical Notes

1. **Poles are immutable tuples** - you cannot modify `disp.Poles[0]`, must create new list
2. **Frequency units are Hz** in the API (not rad/s)
3. **Damping is in Hz** (already divided by 2π)

---

## Complete Workflow

### 1. One-time: Generate Material Cache

```bash
# Option A: From IT'IS V5.0 database (recommended)
python scripts/generate_material_cache_from_db.py

# Option B: From Excel file
python scripts/generate_material_cache_from_excel.py
```

### 2. In GOLIAT Setup (Automatic)

The `MaterialSetup` class automatically handles dispersion for multisine:

```python
# In goliat/setups/material_setup.py
def _assign_phantom_materials_multisine(self):
    cache = load_material_cache()
    
    for material_name, entities in material_groups.items():
        # Get properties at each frequency
        props = get_material_properties(material_name, self.frequencies_mhz, cache)
        
        # Fit Lorentz model
        params = fit_two_pole_lorentz(frequencies_hz, eps_r_list, sigma_list)
        
        # Create and assign dispersive material...
```

### 3. Verification

Check cache values against Sim4Life GUI:
1. Open **IT'IS 4.x Database** in Materials panel
2. Select tissue, set frequency
3. Compare ε_r and σ with cache values

---

## Troubleshooting

### Cache Not Found
```
FileNotFoundError: Material properties cache not found
```
**Solution**: Run cache generation script

### Tissue Not In Cache
```
KeyError: Tissue 'XYZ' not found in material cache
```
**Solution**: Check `material_name_mapping.json` for correct IT'IS name

### High Fit Error
```
WARNING: High fit error (0.05) for 'Muscle'
```
**Solution**: Usually acceptable for <5% error. For higher errors, consider:
- Adding more Lorentz poles
- Narrowing frequency range
- Using database fallback

### Poles Not Visible in GUI
**Cause**: Modified poles in-place instead of creating new objects
**Solution**: Create new `LinearDispersionPole()` objects and assign as list

---

## References

- **IT'IS Foundation**: https://itis.swiss/virtual-population/tissue-properties/database/
- **Gabriel et al.**: "The dielectric properties of biological tissues" Physics in Medicine & Biology (1996)
- **Sim4Life**: Python API reference in `PythonAPIReference/`
