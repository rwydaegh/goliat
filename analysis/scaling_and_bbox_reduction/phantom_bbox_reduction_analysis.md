# Phantom Bounding Box Reduction for High-Frequency Far-Field Simulations

## Problem

FDTD cell counts scale cubically with frequency. At constant cells-per-wavelength, doubling the frequency increases the cell count by 8×. For whole-body far-field simulations:

- **5.8 GHz**: ~2.2 billion cells (manageable)
- **10 GHz**: ~11 billion cells (exceeds GPU memory)
- **15 GHz**: ~37 billion cells (impractical)

## Solution

Automatically reduce the phantom bounding box from the bottom (keeping the head) for frequencies above a reference threshold. The reduction follows cubic frequency scaling:

```
height_factor = (reference_freq / current_freq)³
```

This maintains roughly constant cell count across frequencies.

## Implementation

Configuration in `gridding_parameters.phantom_bbox_reduction`:

```json
{
    "auto_reduce_bbox": true,
    "reference_frequency_mhz": 9000,
    "use_symmetry_reduction": true,
    "height_limit_per_frequency_mm": {}
}
```

- **reference_frequency_mhz**: The highest frequency where full-body simulation fits in memory. Frequencies at or below this get no reduction.
- **use_symmetry_reduction**: When `true`, cuts the bounding box in half along the x-axis at x=0, keeping only the positive x (right) side. This exploits the approximate left-right symmetry of human phantoms, reducing cell count by ~50%.
- **height_limit_per_frequency_mm**: Optional manual overrides per frequency.

A 20% minimum floor ensures at least the head remains in the simulation.

## Scaling Analysis

### Reference: 5.8 GHz

| Freq (GHz) | Factor | Height (Thelonious) | Anatomy |
|------------|--------|---------------------|---------|
| 7          | 0.569  | 683 mm | Head → upper thighs |
| 8          | 0.381  | 457 mm | Head → waist |
| 9          | 0.268  | 321 mm | Head → shoulders |
| 10         | 0.195  | 234 mm | Head + neck |
| 11         | 0.147  | 176 mm | Head only |
| 12         | 0.113  | 135 mm | Head only |
| 15         | 0.058  | 69 mm  | Scalp only (floor kicks in → 240mm) |

With a 5.8 GHz reference, the reduction is aggressive. The 20% floor becomes necessary above 10 GHz.

### Reference: 9 GHz (Recommended)

| Freq (GHz) | Factor | Height (Thelonious) | Anatomy |
|------------|--------|---------------------|---------|
| 7–9        | 1.000  | 1200 mm | Full body (no reduction) |
| 10         | 0.729  | 875 mm  | Upper body + thighs |
| 11         | 0.548  | 657 mm  | Upper body + thighs |
| 12         | 0.422  | 506 mm  | Head + torso |
| 13         | 0.332  | 398 mm  | Head + shoulders |
| 14         | 0.266  | 319 mm  | Head + shoulders |
| 15         | 0.216  | 259 mm  | Head + shoulders |

A 9 GHz reference provides more gradual reduction. At 15 GHz, the simulation still includes head + shoulders without hitting the floor.

## Recommendation

Use `reference_frequency_mhz: 9000` for high-frequency studies. This:
- Keeps full body up to 9 GHz
- Provides meaningful body coverage at 15 GHz
- Avoids the 20% floor for most frequencies
- Maintains ~constant cell count across the 10–15 GHz range

## Files

- **Implementation**: `goliat/setups/far_field_setup.py` (`_get_phantom_height_limit_mm`, `_calculate_auto_height_limit`, `_create_or_get_simulation_bbox`)
- **Test config**: `configs/test_phantom_bbox_reduction.json`
- **Production config**: `configs/far_field_config_high_freq.json`

