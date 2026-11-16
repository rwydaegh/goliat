# Linking simulations to mmWave measurements

`goliat.postprocessing.measurement_link` compares a GOLIAT/Sim4Life field map with a measured or reconstructed field map on a plane in front of a device. It uses the incident power density (IPD) assessment steps of IEC/IEEE 63195-1 (measurement) and 63195-2 (computation). The module is pure NumPy/SciPy and does not need Sim4Life.

## Pipeline

```python
from goliat.postprocessing import measurement_link as ml

meas = ml.load_field_map("scan_30GHz.csv")                 # probe scan, tangential E
sim = ml.from_sim4life_output("run_Output.h5", z=meas.z, frequency_hz=30e9,
                              xlim=(-0.05, 0.05), ylim=(-0.05, 0.05))

meas_full = ml.reconstruct_fields(meas)                    # Ez and H by PWS
fine = ml.spectral_upsample(meas_full, 4)                  # band-limited step refinement
pd = ml.assess_pd(fine, areas_m2=(1e-4, 4e-4))             # sPDn / sPDtot maps + peaks
res = ml.compare_fields(meas, sim, register=True)          # shift, errors, calibration
print(res.as_dict())
```

| Step | Function | Notes |
|---|---|---|
| Container | `PlanarField` | `x`, `y` (m), plane `z`, `frequency_hz`, `E[ix, iy, 3]`, optional `H`. A missing Ez is NaN. The defaults are peak phasors and `exp(+jwt)`. The options `amplitude="rms"` and `time_convention="-jwt"` are also available. `phase_valid=False` marks magnitude-only maps. |
| Resampling | `PlanarField.resample`, `common_grid`, `spectral_upsample` | Linear or cubic interpolation of the real and imaginary parts, or exact band-limited interpolation through the plane-wave spectrum (PWS). |
| PWS | `angular_spectrum`, `propagate`, `reconstruct_fields` | The tangential E is transformed by an FFT with zero padding. Each plane wave is propagated with `exp(-j kz dz)`, where `Im kz <= 0` so evanescent waves decay. Ez is computed from `k·E = 0` and H from `H = k × E / (ω μ0)`. Options: `k_max_factor` (k-space low-pass in units of k0) and `taper` (raised-cosine roll-off). Back-propagation raises an error unless a filter is set. Pass `keep_padding=True` to keep the field that spreads beyond the scan. |
| Power density | `poynting`, `spatial_average_pd`, `assess_pd`, `total_power` | `sPDn = (1/A)∫Re(S)·n dA` and `sPDtot = (1/A)‖∫Re(S) dA‖` over an axis-aligned square of area `A`, centred on every sample whose square fits in the map. Partial cells are weighted exactly. A warning is logged if the step exceeds min(1 mm, λ/10). |
| Comparison | `register_translation`, `calibration_factor`, `compare_fields` | Registration is a masked normalised cross-correlation of \|E_t\| with sub-sample refinement. Calibration is a least-squares scale factor, complex or magnitude-only. The metrics are the relative L2 error of \|E\|, the mean relative error of \|E\| (MRE, Yi et al. 2026, Eq. 7), the weighted RMS phase error after removal of the global phase, the complex relative L2 error, and the relative psPDn error for each averaging area. `Calibration.power_factor` rescales simulated PD/SAR to the measured level. |

## File layouts

- A CSV file has optional `# key = value` lines (`frequency_hz`, `z`, `length_unit` = m|mm|cm, `amplitude`, `time_convention`, `phase_valid`), then a header and one row per sample. Required columns are `x, y, Ex_re, Ex_im, Ey_re, Ey_im`. Optional columns are `Ez_*` and `Hx_*..Hz_*`. Rows may come in any order but must cover a full rectangular grid.
- An NPZ file has `x`, `y`, `E` (`Nx×Ny×2|3`, complex), optional `H`, the scalars `z` and `frequency_hz`, and optional strings.
- An HDF5 file has the datasets `x`, `y`, `E`, optional `H` (complex, or real with a trailing `[re, im]` axis) inside `group`. The attributes are `z`, `frequency_hz` and the optional keys listed for CSV.

The matching writers are `save_csv`, `save_npz` and `save_hdf5`.

## Sim4Life adapter

`from_sim4life_output` reads the "Overall Field" group of `*_Output.h5` through `goliat.extraction.field_reader`. It reads only the two z-slices around the requested plane and averages the Yee-staggered components to the x-y cell centres at the nearest node plane. The co-located H is an approximation. For a compliance assessment of PD, recompute H from the tangential E with `reconstruct_fields`. The adapter is tested on a synthetic file with the layout described in `field_reader`. It is not yet tested on a real Sim4Life export.

## Validation (tests/test_postprocessing_measurement_link.py)

The reference fields are closed-form: a Hertzian dipole and oblique plane waves at 30 GHz.

- The tangential E of the dipole is sampled on z = λ/2 with a λ/10 step over a 50 cm scan and propagated forward to z = 2λ. The relative error on the central 6 cm is 0.92 % for E, 1.2 % for Ez and 0.92 % for H. The error is set by scan truncation. The E error is 2.7 % with a 30 cm scan and 0.48 % with an 80 cm scan.
- Reconstruction on the same plane at z = λ has E and H errors of 0.34 %. psPDn over 1 and 4 cm² agrees with the exact-field value to better than 0.01 %.
- Back-propagation from 3λ to 1.5λ with `k_max_factor=1` and `taper=0.05` has a 0.5 % error against the band-limited exact field.
- For a plane wave, `|S| = |E|²/(2η0)` and `S_z = cosθ |S|` hold to machine precision, including when H is reconstructed from the tangential E.
- The power through the plane is conserved between two planes, to 1e-10 in the spectral integral and to 1e-3 in the spatial integral. It matches the exact-field integral over the scan within 0.5 % and is 98.7 % of the analytic half-space power P_rad/2.
- Registration recovers integer and sub-sample shifts to within 0.1 mm. Calibration recovers a complex gain of 0.73·e^{0.4j} under 0.2 % noise. The psPD error after calibration is 0.3 %.

## Limitations

- Only planar scans are handled. There is no conformal or cylindrical PWS and no probe compensation, so the scan must be probe-compensated before loading.
- PWS needs phase, so a magnitude-only map is assessed with the plane-wave estimate `|E|²/(2η0)`, which is biased in the reactive near field. Amplitude probes and image-based super-resolution of \|E\| give such maps. Phase retrieval from two planes is not implemented.
- Accuracy is limited by scan aperture truncation and by sampling. Use a step of λ/2 or finer for the propagating spectrum, and finer still close to the source.
- Back-propagation recovers only the band passed by the filter. Evanescent content lost at the measurement plane cannot be restored.
- Averaging squares are aligned with the grid axes. Rotated squares and curved evaluation surfaces are not supported.

## Using super-resolution reconstructions

Methods such as EFGraGAN (Yi, Li & Wu, *Front. Inf. Technol. Electron. Eng.* 2026) upsample a probe-array scan with a coarse step (about 8 mm) to the 0.5–1 mm grid required by IEC/IEEE 63195. Load their output as a `PlanarField` on the fine grid and pass it to `assess_pd` and `compare_fields`. Complex outputs are processed with full PWS. Magnitude-only outputs are flagged `phase_valid=False` and assessed with the plane-wave estimate. `spectral_upsample` gives the physics-based baseline that a learned reconstruction should beat. A GOLIAT simulation on the same plane is the high-resolution reference.
