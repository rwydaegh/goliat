# Power Normalization in Computational Dosimetry

## The Problem

In computational dosimetry, we compare electromagnetic exposure from:

1. **Near-field sources** (mobile phones): Antenna fed with measurable input power (e.g., 1 W)
2. **Far-field sources** (environmental exposure): Plane waves with specified electric field strength (e.g., 1 V/m)

**The challenge**: How do we normalize results to enable meaningful comparison?

---

## The Core Insight

For a plane wave, there is no "source" — the field exists uniformly in space. "1 W" has no direct meaning.

The time-averaged power density (Poynting vector magnitude) is:

$$S = \frac{E_0^2}{2\eta_0}$$

Where η₀ = 377 Ω. For E₀ = 1 V/m: S = 1.326 mW/m².

---

## Why Bounding Box Power is Meaningless

Some implementations calculate "input power" as P = S × A_bbox (power through the simulation bounding box).

### Proof by Contradiction

1. SAR depends only on the incident field and phantom — not on the computational domain size.
2. If we define P_input = S × A_bbox, then enlarging the bbox 10× increases P_input 10×.
3. But SAR stays exactly the same.
4. **Contradiction**: A normalization metric that can be made arbitrarily large without changing SAR is physically meaningless.

**Conclusion**: The simulation bounding box is a computational convenience with no physical significance for power accounting.

**Note**: Sim4Life does not provide an "EM Input Power(f)" output for plane wave sources, unlike for antenna (port) sources. This is not an oversight — it reflects the conceptual difficulty of defining "input power" for a plane wave that extends to infinity. The burden of defining a meaningful metric falls on the user.

---

## The Correct Normalization: Power Density (1 W/m²)

We define **"1 W" for far-field** to mean **1 W/m² power density**.

### Why This Works

1. **Intrinsic to the field**: Power density is a property of the incident wave, not an artifact of computation
2. **Direction-independent**: Same S regardless of propagation direction
3. **Measurable**: Exactly what EMF probes (NARDA, etc.) measure
4. **Standard in literature**: ICNIRP reference levels are defined in terms of power density
5. **Reproducible**: No dependence on mesh quality, bbox size, or phantom model

### The Math

At E = 1 V/m, S = 1.326 mW/m². To normalize to 1 W/m²:

$$E_{\text{ref}} = \sqrt{2 \eta_0} = 27.46 \text{ V/m}$$

Since SAR ∝ E², the scaling factor from 1 V/m simulation to 1 W/m² is:

$$\text{Scale factor} = (27.46)^2 = 754$$

---

## Comparison with Near-Field

| Exposure | "1 W" Definition | Power Reaching Body |
|----------|------------------|---------------------|
| Phone at 1 W input | 1 W to antenna | ~0.3–0.5 W (30–50% coupling) |
| Plane wave at 1 W/m² | 1 W per m² | ~0.5 W (frontal area ~0.5 m²) |

Both deliver comparable power to the body — the comparison is physically meaningful.

---

## What About Phantom Cross-Section?

We have pre-computed the projected cross-sectional area A(θ,φ) for all phantoms (see `data/phantom_skins/README.md`). This enables computing the **actual power intercepted** by the body:

$$P_{\text{intercepted}} = S \times A_{\text{phantom}}(\theta, \phi)$$

### Why Not Use This for Normalization?

While physically meaningful, using phantom cross-section for SAR normalization has problems:

1. **Poor reproducibility**: Different phantoms, meshes, and algorithms give different areas
2. **Arbitrary choices**: Convex hull vs exact boundary? Which mesh resolution?
3. **Not standard**: Literature uses 1 W/m², not "1 W per phantom cross-section"
4. **Direction-dependent**: Same "1 W" would mean different things for different directions

### Correct Use of Cross-Section Data

The phantom cross-section is valuable for **analysis**, not normalization:

- **Absorption efficiency**: η = P_absorbed / P_intercepted (what fraction of intercepted power is absorbed?)
- **Worst-case direction**: Which angle maximizes/minimizes exposure for a given power density?
- **Phantom comparison**: Comparing effective target areas across body models

This data is stored in `data/phantom_skins/{phantom}/cross_section_pattern.pkl`.

---

## Power Balance for Far-Field

### The Conceptual Issue

Power balance = (P_absorbed + P_radiated) / P_input × 100%

For near-field, P_input is unambiguous (power to antenna). For far-field, there's no discrete "input" — the plane wave extends infinitely.

### Understanding Sim4Life's RadPower

When Sim4Life reports `RadPower` in the power balance, it computes the **total Poynting flux through the simulation boundaries**. For a plane wave incident on a phantom:

- Power enters through one face of the bounding box
- Some power is absorbed by the phantom → `DielLoss`
- The remaining power exits through all faces → `RadPower`

Crucially, `RadPower` includes both:
1. **Scattered power**: Power redirected by the phantom
2. **Transmitted power**: The portion of the plane wave that missed the phantom and passed straight through

This is why `RadPower` is closely related to the bounding box size, not just the phantom.

---

### Two Approaches for P_input

GOLIAT supports two configurable methods for defining "input power" in far-field power balance. Configure via:

```json
{
    "power_balance": {
        "input_method": "bounding_box"  // or "phantom_cross_section"
    }
}
```

#### 1. Bounding Box Method (Default)

$$P_{\text{input}} = S \times A_{\text{bbox}}(\theta, \phi)$$

Uses the projected cross-sectional area of the simulation bounding box as seen from the incident direction.

**Advantages:**
- **Consistent with Sim4Life**: `RadPower + DielLoss ≈ S × A_bbox`, so balance ≈ 100%
- **Sanity check**: Deviations from 100% indicate numerical issues

**Disadvantages:**
- **Domain-dependent**: Larger bbox → larger P_input (but same SAR)
- **No physical meaning**: Just verifies FDTD energy conservation

**For non-orthogonal directions**: The projected bbox area is computed as:
$$A_{\text{projected}} = |n_x| A_{yz} + |n_y| A_{xz} + |n_z| A_{xy}$$
where $\hat{n} = (\sin\theta\cos\phi, \sin\theta\sin\phi, \cos\theta)$ is the incident direction.

#### 2. Phantom Cross-Section Method

$$P_{\text{input}} = S \times A_{\text{phantom}}(\theta, \phi)$$

Uses the pre-computed projected cross-sectional area of the phantom from `data/phantom_skins/`.

**Advantages:**
- **Physically meaningful**: Represents actual power intercepted by the body
- **Domain-independent**: Same value regardless of simulation bbox size
- **Enables absorption efficiency**: Balance shows what fraction of intercepted power is accounted for

**Disadvantages:**
- **Balance >> 100%**: Expected! `RadPower` includes power that bypassed the phantom
- **Not a sanity check**: Can't detect numerical errors from balance alone

### Interpreting the Balance

| Method | Expected Balance | Interpretation |
|--------|-----------------|----------------|
| `bounding_box` | ~100% | Energy conservation verified; values ≠ 100% suggest issues |
| `phantom_cross_section` | 150–300% | Normal; extra power is plane wave that missed the phantom |

---

## Implementation Summary

### In GOLIAT

1. **Simulations run at E = 1 V/m** (standard Sim4Life plane wave)
2. **Analysis scales by 754** (`far_field_strategy.get_normalization_factor()` returns 754.0)
3. **Results reported as "SAR at 1 W/m² incident power density"**
4. **Power balance uses configurable method** (default: `bounding_box`)

### Configuration

```json
// In far_field_config.json
{
    "power_balance": {
        "input_method": "bounding_box"  // Options: "bounding_box", "phantom_cross_section"
    }
}
```

### Output Fields

The extraction writes these fields to `sar_results.json`:
- `input_power_W`: Computed input power at 1 V/m
- `power_balance_input_method`: Which method was used
- `cross_section_m2`: The area value used
- `cross_section_source`: Description of the source (e.g., "bbox_x_pos", "phantom_duke")

### Conversion Formulas

| Quantity | Value at 1 V/m | Value at 1 W/m² |
|----------|----------------|-----------------|
| Electric field E₀ | 1 V/m | 27.46 V/m |
| Power density S | 1.326 mW/m² | 1 W/m² |
| SAR | SAR₁ᵥ/ₘ | SAR₁ᵥ/ₘ × 754 |

**Scaling to arbitrary field E:**
$$\text{SAR}(E) = \text{SAR}_{1\text{W/m}^2} \times S = \text{SAR}_{1\text{V/m}} \times E^2$$

---

## Suggested Text for Publications

> *"Far-field exposure simulations were performed using plane wave illumination. Results are normalized to an incident power density of 1 W/m², corresponding to an electric field amplitude of 27.5 V/m in free space. This normalization was chosen because power density is an intrinsic, measurable property of the incident field that does not depend on computational domain size or phantom-specific geometry — ensuring reproducibility across studies. SAR values scale quadratically with field strength (SAR ∝ E²), enabling straightforward translation to any exposure level."*

---

## Further Reading

- `data/phantom_skins/README.md` — Pre-computed phantom cross-section data
- `docs/technical/skin_mesh_pipeline.md` — How phantom outer surfaces were extracted and processed

