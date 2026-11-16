# Analytic reference solutions

`goliat.validation` has license-free reference solutions (NumPy/SciPy only) for checking the
normalization, material assignment, and averaging of solver output. The formulas are from
textbooks. The tests in `tests/test_validation_analytic.py` check them against known limiting cases.

All quantities are in SI units. Materials are given as real `eps_r` and total conductivity `sigma` (S/m).
Fields are peak phasors, so `S_inc = |E0|^2 / (2 eta)` and local SAR is `sigma |E|^2 / (2 rho)`.
Complex fields use the `exp(-i w t)` convention: conjugate them for `exp(+j w t)`.

## Functions and valid ranges

| Function | Returns | Valid range / notes |
|---|---|---|
| `mie_sphere(a, f, eps_r, sigma)` | `MieResult` (`q_ext`, `q_sca`, `q_abs`, `c_abs`, ...) | Size parameter `x = k a` from 1e-4 to about 1e4 (cost O(x)). Agrees with miepython to 1e-9. |
| `sphere_absorbed_power(..., s_inc)` / `sphere_wb_sar(..., density, s_inc)` | W, W/kg | Same as above |
| `sphere_internal_field(a, f, eps_r, sigma, points, s_inc)` | complex E (N,3), V/m | Field inside the sphere only. The incident field is x-polarized and travels along +z, with the sphere at the origin. Uses scaled Bessel functions, so heavy loss is fine. Keep `x` below about 200. |
| `sphere_local_sar(...)` | W/kg at points | |
| `multilayer_response(layers, substrate, f, angle_deg, "TE"/"TM", s_inc=...)` | `MultilayerResult` | Any number of lossy layers over a half-space, any thickness. Reflection recursion, so there is no overflow. |
| `MultilayerResult.reflectance/transmittance/absorbed` | power fractions of `S_inc cos(theta)` | These sum to 1 |
| `MultilayerResult.apd` | W/m^2 entering the first layer | Equals `(1-R) S_inc cos(theta)` |
| `MultilayerResult.sar_profile(z)`, `.power_density(z)`, `.e_field_sq(z)` | depth profiles | `z` is measured from the body surface |
| `fresnel_halfspace(...)`, `halfspace_apd(...)` | Gamma and `1-|Gamma|^2`, APD | Closed form |
| `tissue_properties(name, f)`, `cole_cole(params, f)` | `(eps_r, sigma)` | Gabriel et al. 1996c 4-pole Cole-Cole. Tissues: `skin_dry`, `skin_wet`, `muscle`, `fat` (not infiltrated), `blood`. The fits cover 10 Hz to 20 GHz. Above 20 GHz the values are extrapolated. |
| `peak_spatial_average_apd(apd, dx, dy, area=4e-4)` | peak, location, map | Planar uniform grid, axis-aligned squares, fractional edge cells |
| `mass_averaged_sar(sar, density, voxel_size, mass=0.01)` | peak, map, cube sides | Use `mass=0.001` for 1 g. See the limitations below. |

`mass_averaged_sar` does not implement the full IEC/IEEE 62704-1 algorithm. Each cube is
centered on a tissue voxel and grows until it encloses the target mass, with partial voxels weighted
by volume. There is no limit on the air fraction and no re-centering of cubes at the surface. Air and
the space beyond the grid add volume but no mass, so near-surface values differ from 62704-1. The function is
O(N) and is meant for small benchmark grids (up to about 1e6 voxels).

## Reference values

These use Gabriel parameters, with `S_inc = 1 W/m^2` in vacuum.

- Muscle sphere, `a = 0.1 m`, 900 MHz (`eps_r = 55.03`, `sigma = 0.943 S/m`, `x = 1.886`):
  `Q_abs = 0.8519`, `P_abs = 26.76 mW`, and whole-body SAR at 1090 kg/m^3 is `5.862e-3 W/kg`.
- Dry-skin half-space at normal incidence: transmittance `T = 0.4888` at 10 GHz (`31.29`, `8.01 S/m`) and
  `T = 0.5418` at 30 GHz (`15.51`, `27.10 S/m`). APD is `T * S_inc`.

## Example

```python
from goliat.validation import Layer, multilayer_response, sphere_wb_sar, tissue_properties

eps, sig = tissue_properties("muscle", 900e6)
print(sphere_wb_sar(0.1, 900e6, eps, sig, density=1090, s_inc=1.0))  # W/kg

f = 30e9
skin, fat, muscle = (Layer(t, *tissue_properties(n, f)) for t, n in [(1.5e-3, "skin_dry"), (4e-3, "fat"), (0, "muscle")])
res = multilayer_response([skin, fat], muscle, f, angle_deg=0, polarization="TE", s_inc=10.0)
print(res.apd, res.reflectance, res.absorbed, res.sar_profile([0.0, 0.5e-3]))
```
