# Multisine Dispersion Integration - Walkthrough

## Summary

Implemented frequency-dependent material dispersion for multisine FDTD simulations. When running multisine (e.g., 700+2450 MHz), materials now get fitted Lorentz dispersion models that accurately reproduce permittivity and conductivity at all excitation frequencies.

### Data Source

Material properties are computed from the **IT'IS Foundation V5.0 Database** using the **Gabriel 4-Cole-Cole model**. This provides accurate, frequency-dependent dielectric properties validated against Sim4Life GUI values.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    IT'IS V5.0 Database                          │
│              (data/itis_v5.db)                  │
│                                                                 │
│  Contains Gabriel 4-Cole-Cole parameters for 250+ tissues      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│            scripts/generate_material_cache_from_db.py           │
│                                                                 │
│  • Reads Gabriel parameters (ef, del, tau, alf, sigma)         │
│  • Computes ε_r and σ at 9 frequencies (450-5800 MHz)          │
│  • Outputs JSON cache                                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              data/material_properties_cache.json                │
│                                                                 │
│  {                                                              │
│    "tissues": {                                                 │
│      "Brain (Grey Matter)": {                                   │
│        "700": {"eps_r": 53.90, "sigma": 0.86},                 │
│        "2450": {"eps_r": 48.46, "sigma": 2.00}, ...            │
│      }, ...                                                     │
│    }                                                            │
│  }                                                              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              goliat/dispersion/material_cache.py                │
│                                                                 │
│  get_material_properties("Brain (Grey Matter)", [700, 2450])   │
│  → [{"eps_r": 53.90, "sigma": 0.86}, ...]                      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              goliat/dispersion/lorentz_fitter.py                │
│                                                                 │
│  fit_two_pole_lorentz(frequencies_hz, eps_r_list, sigma_list)  │
│  → LorentzParams(eps_inf, sigma_dc, poles, fit_error)          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│           goliat/setups/material_setup.py                       │
│                                                                 │
│  _assign_phantom_materials_multisine()                          │
│  • Creates LinearDispersive materials in Sim4Life              │
│  • Assigns Lorentz poles to disp.Poles                         │
└─────────────────────────────────────────────────────────────────┘
```

---

## Files Created

### Dispersion Package

| File | Purpose |
|------|---------|
| `goliat/dispersion/__init__.py` | Package init, exports public API |
| `goliat/dispersion/lorentz_fitter.py` | Two-pole Lorentz model fitting using scipy optimization |
| `goliat/dispersion/material_cache.py` | JSON cache loading for precomputed material properties |

### Scripts

| File | Purpose |
|------|---------|
| `scripts/generate_material_cache_from_db.py` | Generate cache from IT'IS V5.0 database (recommended) |
| `scripts/generate_material_cache_from_excel.py` | Alternative: generate from Excel file |
| `scripts/generate_material_cache.py` | Legacy: run in Sim4Life (has API limitations) |

### Data Files

| File | Purpose |
|------|---------|
| `data/material_properties_cache.json` | Precomputed ε_r and σ at 9 frequencies for 111 tissues |
| `data/material_name_mapping.json` | Maps phantom entity names → IT'IS tissue names |
| `data/itis_v5.db` | Source SQLite database with Gabriel parameters |

### Tests

| File | Purpose |
|------|---------|
| `tests/dispersion/test_lorentz_fitter.py` | Unit tests for fitting (6 tests, all passing) |

---

## Files Modified

### material_setup.py

Added multisine support:
- New `frequencies_mhz` parameter in `__init__`
- `is_multisine` flag detection
- `_assign_phantom_materials_multisine()` method

```python
def __init__(
    self,
    config: "Config",
    simulation,
    antenna,
    phantom_name: str,
    verbose_logger: "Logger",
    progress_logger: "Logger",
    free_space: bool = False,
    frequencies_mhz: list[int] | None = None,  # NEW
):
    self.frequencies_mhz = frequencies_mhz
    self.is_multisine = frequencies_mhz is not None and len(frequencies_mhz) > 1
```

### far_field_setup.py

Passes frequency list to MaterialSetup:

```python
material_setup = MaterialSetup(
    self.config,
    sim,
    self.antenna,
    self.phantom_name,
    self.verbose_logger,
    self.progress_logger,
    free_space=False,
    frequencies_mhz=self.frequency_mhz if self.is_multisine else None,  # NEW
)
```

---

## Material Cache Details

### Source: IT'IS V5.0 Database

The cache is generated from **data/itis_v5.db** using the Gabriel 4-Cole-Cole model:

```
ε*(ω) = ε∞ + Σₙ [Δεₙ / (1 + (jωτₙ)^(1-αₙ))] + σ/(jωε₀)
```

### Gabriel Parameter Format (14 floats)

```
[ef, del1, tau1_ps, alf1, del2, tau2_ns, alf2, del3, tau3_us, alf3, del4, tau4_ms, alf4, sigma]
```

### Frequencies Covered

```python
FREQUENCIES_MHZ = [450, 700, 835, 1450, 2140, 2450, 3500, 5200, 5800]
```

### Validated Against Sim4Life GUI

| Tissue | Frequency | Cache ε_r | Cache σ | S4L GUI | Match |
|--------|-----------|-----------|---------|---------|-------|
| Brain (Grey Matter) | 700 MHz | 53.90 | 0.860 | ✓ | ✅ |
| Muscle | 2450 MHz | 52.73 | 1.739 | ✓ | ✅ |
| Skin | 835 MHz | 41.76 | 0.845 | ✓ | ✅ |
| Fat | 5800 MHz | 9.86 | 0.832 | ✓ | ✅ |
| Bone (Cortical) | 450 MHz | 13.04 | 0.096 | ✓ | ✅ |

### Material Name Mapping

Entity names from phantoms map to IT'IS names via `data/material_name_mapping.json`:

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

All 4 phantoms verified: **303 total mappings**, all present in cache.

---

## Test Results

```
tests/dispersion/test_lorentz_fitter.py::TestFitTwoPoleLorentz::test_basic_two_frequency_fit PASSED
tests/dispersion/test_lorentz_fitter.py::TestFitTwoPoleLorentz::test_fit_validation_passes PASSED  
tests/dispersion/test_lorentz_fitter.py::TestFitTwoPoleLorentz::test_three_frequency_fit PASSED
tests/dispersion/test_lorentz_fitter.py::TestFitTwoPoleLorentz::test_invalid_input_length_mismatch PASSED
tests/dispersion/test_lorentz_fitter.py::TestFitTwoPoleLorentz::test_invalid_input_too_few_points PASSED
tests/dispersion/test_lorentz_fitter.py::TestLorentzParams::test_dataclass_fields PASSED

6 passed in 105.81s
```

---

## Usage

### 1. Generate Material Cache (One-time)

**Recommended: From IT'IS V5.0 Database**

```bash
python scripts/generate_material_cache_from_db.py
```

This creates `data/material_properties_cache.json` with ε_r and σ for all tissues at all standard frequencies.

### 2. Run Multisine Simulation

```bash
python -m goliat run configs/far_field_multisine.json
```

The config should have multiple frequencies:
```json
{
  "frequencies_mhz": [700, 2450]
}
```

### 3. Verify in Sim4Life

After simulation setup, verify:
- Materials show **"LinearDispersive"** model type
- Dispersion Viewer shows **2 active Lorentz poles** per tissue
- SAR results match harmonic reference runs

---

## Fallback Behavior

If a material is not found in the cache:

1. **Warning logged**: `'{material_name}' not in cache, using database fallback`
2. **Database linking used**: Standard IT'IS 4.2 database material assigned
3. **If database fails**: Second warning logged, material skipped

This ensures simulations can still run even with incomplete cache.

---

## Troubleshooting

### Cache Not Found
```
FileNotFoundError: Material properties cache not found at .../material_properties_cache.json
```
**Solution**: Run `python scripts/generate_material_cache_from_db.py`

### Tissue Not In Cache
```
KeyError: Tissue 'XYZ' not found in material cache
```
**Solution**: 
- Check `data/material_name_mapping.json` for correct IT'IS name
- Verify tissue exists in IT'IS V5.0 database

### High Fit Error
```
WARNING: High fit error (0.05) for 'Muscle'
```
**Note**: Errors <5% are generally acceptable. Higher errors may indicate:
- Extreme dispersion behavior
- Consider using database fallback for that tissue

### Database File Missing
```
sqlite3.OperationalError: unable to open database file
```
**Solution**: Ensure `data/itis_v5.db` is in project root

---

## References

- **IT'IS Foundation**: https://itis.swiss/virtual-population/tissue-properties/database/
- **Gabriel et al.**: "The dielectric properties of biological tissues" Physics in Medicine & Biology (1996)
- **Technical guide**: `docs/technical/dispersion_model_guide.md`
