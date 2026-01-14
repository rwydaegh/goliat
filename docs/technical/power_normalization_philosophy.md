# Power Normalization in Computational Dosimetry: A Critical Analysis

## The Problem

In computational dosimetry, we wish to compare electromagnetic exposure from different sources:

1. **Near-field sources** (mobile phones, wearable devices): A physical antenna fed with measurable input power (e.g., 1 W)
2. **Far-field sources** (environmental exposure, base stations): Represented as plane waves with a specified electric field strength (e.g., 1 V/m)

The challenge: **How do we normalize results to enable meaningful comparison?**

---

## Near-Field: A Clear Definition

For near-field sources, "normalized to 1 W" has an unambiguous physical meaning:

- The source (antenna) is fed with P_in = 1 W of input power
- The simulation computes SAR distribution in the phantom
- Results scale linearly with input power (SAR ∝ P_in)

This is well-defined because there exists a physical port where power is injected.

---

## Far-Field: The Philosophical Challenge

For a plane wave, there is no "source" in the conventional sense. The electromagnetic field simply exists:

$$\vec{E}(\vec{r}, t) = E_0 \hat{e} \cos(\omega t - \vec{k} \cdot \vec{r})$$

Where E₀ is the field amplitude (e.g., 1 V/m), and the wave fills all of space uniformly.

**The question becomes: What does "1 W" mean for a plane wave?**

### The Poynting Vector and Power Density

The time-averaged power density (Poynting vector magnitude) for a plane wave is:

$$S = \frac{E_0^2}{2\eta_0} \quad \text{[W/m²]}$$

Where η₀ = 377 Ω is the impedance of free space.

For E₀ = 1 V/m:
$$S = \frac{1}{2 \times 377} = 1.326 \text{ mW/m²}$$

**Power density is a well-defined, direction-independent quantity.** But it's in W/m², not W.

### Converting to Watts: The Area Problem

To get from W/m² to W, we need to multiply by an area:

$$P = S \times A$$

**But which area?**

---

## Possible Definitions of "1 W" for Plane Waves

### Option 1: Power through the phantom's cross-section

$$P = S \times A_{\text{phantom}}$$

**Problem:** The phantom's cross-sectional area depends on the direction of incidence:
- Front view (wave from front): A ≈ 0.5 m²
- Side view (wave from side): A ≈ 0.25 m²
- Top view (wave from above): A ≈ 0.2 m²

This makes "1 W" direction-dependent, which is conceptually problematic for a normalization constant—but is actually **correct physics** for power balance (see below).

### Option 2: Power through the simulation bounding box

$$P = S \times A_{\text{bbox}}$$

This is what some implementations use. However, **this approach is fundamentally flawed**, as demonstrated by the following proof by contradiction:

#### Proof by Contradiction: The Simulation Box is Irrelevant

Consider a plane wave simulation at 1 V/m with a human phantom:

1. **Observation**: The SAR distribution and total absorbed power in the phantom depend only on the incident field and phantom properties—not on the computational domain size.

2. **Suppose** we define "input power" as P = S × A_bbox (power flowing through the bounding box).

3. **Then**: By making the simulation box arbitrarily large (say, 100× larger), the "input power" increases by a factor of 100.

4. **But**: The SAR in the phantom remains exactly the same—the phantom doesn't know or care how big the computational domain is.

5. **Contradiction**: A normalization metric that can be made arbitrarily large without changing the quantity it's supposed to normalize (SAR) is physically meaningless.

**Conclusion**: The simulation bounding box is a computational convenience with no physical significance for power accounting. Any normalization based on bbox area is arbitrary and should be rejected.

### Option 3: Power density normalization (1 W/m² = "1 W")

Define "1 W" to mean **1 W/m² power density**, corresponding to:

$$E_0 = \sqrt{2 \eta_0} = 27.46 \text{ V/m}$$

**Advantages:**
- Direction-independent ✓
- No arbitrary area choices ✓
- Well-defined physical meaning ✓
- **Passes the bbox test**: Power density is independent of simulation domain size ✓

**The power actually intercepted by the body** is then:

$$P_{\text{intercepted}} = S \times A_{\text{body}}(\theta, \phi)$$

Where A_body depends on the body's cross-section as seen from the direction of incidence. This direction-dependence is **real physics**, not an artifact—a wave from the front genuinely deposits more power into the body than the same power density from the side.

---

## What Does the Literature Do?

Reviewing computational dosimetry literature reveals inconsistent conventions:

### Near-field studies
- Typically report SAR "normalized to 1 W input power" (unambiguous)
- Sometimes "normalized to 1 W radiated power" (slightly different)

### Far-field/plane wave studies
- **Some report SAR per (V/m)²**: Implicitly normalizing to electric field
- **Some report SAR at 1 W/m²**: Power density normalization
- **Some report SAR at reference levels**: E.g., ICNIRP limits (10 W/m² for general public)
- **Few explicitly define what "1 W" means** for plane waves

This lack of standardization is a genuine problem in the field.

---

## Critical Analysis: Why 1 W/m² Is the Correct Choice

### The Physical Argument

For plane wave exposure, power density S (W/m²) is the intrinsic property of the incident field:
- It is direction-independent
- It is what EMF probes measure
- It does not depend on any arbitrary computational choices

The power intercepted by the body, P = S × A_body, is then determined by:
- The incident power density (property of the field)
- The body's absorption cross-section (property of the body + viewing angle)

Both of these are **physically meaningful** quantities. Neither depends on the simulation box.

### Comparison with Near-Field Is Meaningful

| Exposure Scenario | "1 W" Definition | Power Available to Body |
|-------------------|------------------|-------------------------|
| Phone at 1 W input | 1 W to antenna terminals | ~0.3–0.5 W (coupling efficiency ~30–50%) |
| Plane wave at 1 W/m² | 1 W through each m² | ~0.5 W (front view, A ≈ 0.5 m²) |
| Plane wave at 1 W/m² | 1 W through each m² | ~0.25 W (side view, A ≈ 0.25 m²) |

The comparison is **physically meaningful**: both scenarios deliver similar orders of magnitude of power to the body. The differences in SAR distribution reflect genuine differences in the exposure physics.

### Direction-Dependence Is a Feature, Not a Bug

The fact that a wave from the front produces different SAR than the same power density from the side is **correct physics**. The body presents different cross-sections to different directions, and this affects how much power is intercepted and where it is deposited.

This is exactly what dosimetry should capture.

---

## An Alternative Perspective: Total Absorbed Power

Rather than normalizing to input power (which has different meanings), we could normalize to **total absorbed power in the body**:

$$P_{\text{abs}} = \int_V \sigma |E|^2 \, dV$$

This is what the body actually "experiences" and is directly related to whole-body SAR:

$$\text{WB-SAR} = \frac{P_{\text{abs}}}{M_{\text{body}}}$$

However, this requires running the simulation first to determine P_abs, making it less useful for a priori normalization. It remains valuable as a post-hoc comparison metric.

---

## Final Recommendation

Based on the analysis above, we adopt the following convention:

### For far-field (plane wave) simulations:
- Simulate at E = 1 V/m incident field (power density S = 1.326 mW/m²)
- Normalize SAR to **1 W/m² incident power density** by scaling by factor 754
- This corresponds to E = 27.46 V/m
- Report as "SAR at 1 W/m² incident power density"

### For comparison with near-field (1 W input):
- The comparison is valid and physically meaningful
- Near-field "1 W" and far-field "1 W/m²" both result in comparable power levels reaching the body
- Differences in spatial SAR distribution reflect genuine differences in exposure mechanisms

---

## Suggested Text for Scientific Publications

> *"Far-field exposure simulations were performed using plane wave illumination. Results are normalized to an incident power density of 1 W/m², corresponding to an electric field amplitude of 27.5 V/m in free space. This normalization was chosen because power density is an intrinsic, direction-independent property of the incident field that does not depend on the arbitrary size of the computational domain—a critical requirement for physical consistency. The power intercepted by the body scales with its absorption cross-section, which naturally depends on the direction of incidence; this direction-dependence represents genuine dosimetric differences rather than normalization artifacts. SAR values scale quadratically with field strength (SAR ∝ E²), enabling straightforward translation to any exposure level. For comparison with near-field sources (normalized to 1 W input power), we note that at 1 W/m², a human body of approximately 0.5 m² frontal cross-section intercepts roughly 0.5 W—comparable to the power coupled from a 1 W phone antenna—suggesting that these normalization conventions yield meaningful inter-scenario comparisons."*

---

## The Power Balance Problem

### Near-Field Power Balance

For near-field simulations, power balance is well-defined:

$$\text{Balance} = \frac{P_{\text{absorbed}} + P_{\text{radiated}} + P_{\text{losses}}}{P_{\text{input}}} \times 100\%$$

Where P_input is the power fed to the antenna—a single, unambiguous number.

### Far-Field Power Balance: A Conceptual Mismatch

For far-field plane wave exposure, "power balance" is problematic:

- **P_absorbed**: Well-defined (computed by integrating σ|E|² over the phantom volume)
- **P_input**: **Undefined!** There is no "input" for a plane wave that extends to infinity

If we use the bbox-based "input power" (which we've proven arbitrary), the resulting power balance percentage is meaningless—it can be made arbitrarily small by enlarging the simulation domain.

### The Ideal Solution: Phantom Cross-Section

The **only physically meaningful** definition of "input power" for far-field is:

$$P_{\text{input}}(\theta, \phi) = S \times A_{\text{phantom}}(\theta, \phi)$$

Where A_phantom(θ, φ) is the **projected cross-sectional area** of the phantom as seen from the direction of incidence.

This is the "shadow area" of the phantom illuminated by the plane wave.

**With this definition:**
- Power balance becomes **absorption efficiency**: what fraction of intercepted power is absorbed
- The metric is **direction-dependent** (correctly reflecting physics)
- It is **independent of simulation domain size** ✓
- It enables **meaningful comparison** with near-field efficiency

### Computing Phantom Cross-Section

The phantom cross-section can be computed by:
1. Projecting the phantom surface mesh onto a plane perpendicular to the propagation direction k̂
2. Computing the area of the resulting 2D projection (convex hull or exact boundary)

For standard directions:
- **Front/back (±y)**: Project onto XZ plane → ~0.4–0.6 m² (adult)
- **Side (±x)**: Project onto YZ plane → ~0.2–0.35 m²
- **Top/bottom (±z)**: Project onto XY plane → ~0.15–0.25 m²

For arbitrary angles, the cross-section varies smoothly between these extremes.

### Current Implementation Status

**As of this writing:** The phantom cross-section is not yet computed automatically. Power balance for far-field uses the bbox-based approximation, which should be interpreted with caution.

**Future improvement:** Implement automatic phantom cross-section calculation for each direction, enabling physically meaningful power balance and absorption efficiency metrics.

---

## Conclusion

The normalization question for far-field dosimetry has a clear answer: **normalize to power density (W/m²)**.

This choice is justified by:
1. **Physical consistency**: Power density is intrinsic to the field, independent of computational domain
2. **Proof by contradiction**: Bbox-based power is arbitrary and can be made infinite without changing SAR
3. **Measurement correspondence**: Power density is what EMF probes measure
4. **Valid comparison**: Resulting power levels are comparable to near-field scenarios
5. **Direction-dependence is correct physics**: Body cross-section variations are real dosimetric effects

**Our convention:** Normalize far-field SAR to 1 W/m² (equivalently, E = 27.46 V/m). For simulations at E = 1 V/m, multiply SAR by 754.

**For power balance:** The ideal metric is absorption efficiency using phantom cross-section, but this requires computing the projected area for each direction—a future enhancement.

---

## Appendix A: Conversion Formulas

| Quantity | Symbol | Value at E = 1 V/m |
|----------|--------|-------------------|
| Electric field | E₀ | 1 V/m |
| Power density | S | 1.326 mW/m² |
| Scaling to 1 W/m² | — | × 754 |
| E-field for 1 W/m² | E₀ | 27.46 V/m |
| E-field for 10 W/m² (ICNIRP GP) | E₀ | 61.4 V/m |

**Scaling SAR from 1 V/m simulation to 1 W/m² normalization:**
$$\text{SAR}_{1\text{W/m}^2} = \text{SAR}_{1\text{V/m}} \times 754$$

**Scaling to arbitrary incident field E:**
$$\text{SAR}(E) = \text{SAR}_{1\text{V/m}} \times E^2$$

---

## Appendix B: Typical Phantom Cross-Sections

| Direction | Projection Plane | Typical Adult Area |
|-----------|------------------|-------------------|
| Front/back (±y) | XZ | 0.4–0.6 m² |
| Side (±x) | YZ | 0.2–0.35 m² |
| Top/bottom (±z) | XY | 0.15–0.25 m² |

These values are approximate and vary with phantom model, posture, and anatomical proportions.
