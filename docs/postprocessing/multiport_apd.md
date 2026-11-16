# Worst-case APD for multi-port antennas

`goliat.postprocessing.multiport_apd` computes the maximized peak
spatial-average absorbed power density (mpsAPD) of a multi-antenna device.
It takes the per-port fields from simulations where each port is excited on
its own, then finds the largest area-averaged APD over every averaging
position and every allowed excitation. It is pure NumPy/SciPy and does not
need Sim4Life.

## Method

By superposition, the APD at a
point is a Hermitian form `a^H Q(r) a` of the port excitations `a` (shape `(N,)`). Averaging is linear, so each averaging
area `c` has its own matrix `Q_A(c)`, the area mean of `Q(r)`. The module has a builder for each of the two APD
definitions in Wu, Chen & Li (IEEE AWPL 2024, doi:10.1109/LAWP.2024.3421367,
eqs. 1, 2 and 8):

| Definition | Builder | Per-point matrix |
|---|---|---|
| Surface, `½Re(E×H*)·n` (`n` points into the body) | `point_matrices_surface(E, H, normals)` | `(G+Gᴴ)/4`, with `G_kl=(E_l×H_k*)·n` |
| Volumetric, `∫σ|E|²/2 dz` (= `∫SAR·ρ dz`) | `point_matrices_volumetric(E_cols, sigma, dz)` | `Σ σ dz/2 · E_i*·E_j` |

GOLIAT's APD extraction calls Sim4Life's `GenericSAPDEvaluator`
(surface Poynting flux, 4 cm²), so the surface definition is the one that
matches it.

## Averaging areas

* `area_matrices_grid(Q_grid, x, y, area_m2)` works on a planar uniform grid.
  It uses an axis-aligned square with exact fractional weights for edge
  cells and keeps only squares that fit entirely inside the grid.
* `area_matrices_surface(Q, points, normals, areas, area_m2, shape=...)`
  works on curved surfaces such as a skin mesh. `surface_from_mesh` gives
  vertex normals and areas.
  * `"disc"`: points within Euclidean distance `sqrt(A/π)` of the centre.
  * `"square"`: points whose projection on the tangent plane falls inside a
    `√A × √A` square, within `depth_tol` of that plane. Set
    `n_orientations` to try several square rotations.

  For both shapes, the function excludes points whose normal faces away from the centre normal
  (`min_normal_cos`). It drops areas that cover less than `min_coverage`
  (default 0.9) of the nominal area. The function uses Euclidean distances and no
  geodesic distances.

## Worst case

| Function | Constraint | Method and result |
|---|---|---|
| `worst_case_total_power(am, power)` | `‖a‖²=P` | exact: `P·λ_max`. The eigenvector is the worst excitation |
| `worst_case_power_caps(am, power, port_caps)` | `‖a‖²=P`, `|a_i|²≤c_i` (paper eq. 7) | monotone generalized power method with multi-start. Returns a feasible lower bound |
| `worst_case_phase_only(am, power)` | `|a_i|²=P/N` | coordinate ascent on phases (closed form per port) with multi-start |
| `worst_case_phase_exhaustive(am, power, n_levels)` | quantized phases | exhaustive over `n_levels^(N-1)` beams |
| `evaluate_codebook(am, codebook)` | user beams `(K,N)` | per-beam psAPD and the `(K,C)` map |

All constrained results have `upper_bound = P·max λ_max`. Each solver visits the areas
in order of decreasing bound and skips each area whose bound is not above
the best value found so far. This pruning is exact and is off when `return_map=True`.
Pass `init_excitations=codebook` to guarantee the result is at
least as large as every codebook entry.

## Example

```python
from goliat.postprocessing import multiport_apd as mp

pts, nrm, area = mp.surface_from_mesh(verts, faces, interior_point=head_centre)
f = mp.sample_port_fields_at_points(port_h5_paths, pts)          # {"E","H"}: (N, M, 3)
Q = mp.point_matrices_surface(f["E"], f["H"], nrm)
am = mp.area_matrices_surface(Q, pts, nrm, area, area_m2=4e-4, shape="square")
tp = mp.worst_case_total_power(am, power=10e-3)                  # fields per 1 W port input
cap = mp.worst_case_power_caps(am, power=10e-3, port_caps=5e-3)  # setting of the paper's Fig. 5
po = mp.worst_case_phase_only(am, power=10e-3)
print(tp.value, cap.value, po.value, po.excitation, am.centers[po.area_index])
```

## Notes and limitations

* Fields must be per-port with unit excitation and the other ports
  terminated, so mutual coupling is already in each port's field. `power`
  is the incident power in the units of that normalization, not the accepted
  power.
* `sample_port_fields_at_points` samples the nearest voxel. The normal
  component of E is discontinuous at the skin, so sample just inside the
  tissue.
* Wu et al. use an SDR/SDP (CVX) for the
  excitations and PSO for a continuous averaging-area position on a
  conformally mapped mSAM surface. This module searches every discrete
  centre, because the batched eigen-decompositions are cheap. It solves
  the total-power case exactly. For the per-port-cap and phase-only
  cases, it uses local ascent instead of an SDP. There is no rank-one
  extraction and no certificate beyond the eigenvalue upper bound.
* The module is not validated against the mSAM / 28 GHz 2×2-patch results of Wu et al. This validation
  needs their per-port field data, or a GOLIAT re-simulation of the
  same setup.
