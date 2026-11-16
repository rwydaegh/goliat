# GOLIAT verification runs in Sim4Life

These runs verify the simulation setup, the default grid rule and the grid convergence of GOLIAT (SoftwareX paper, Section 3.1).
All numbers in Cases 1–4 were computed by GOLIAT's own setup and extraction code (`FarFieldStudy.run()` →
`PhantomSetup`, `FarFieldSetup`, `MaterialSetup`, `GriddingSetup`, `BoundarySetup`, `SimulationRunner`/
`Sim4LifeAPIStrategy`, `ResultsExtractor` → `PowerExtractor`, `SarExtractor`, `SapdExtractor`). The code ran headless
in oSPARC `simcore/services/comp/s4l-python-runner` 1.2.251 (Sim4Life SDK `s4l_v1` 9.6.0+22584, iSolve run
locally inside the runner, Software/CPU kernel, 8 vCPU). The GOLIAT code is git `7301f24` plus the uncommitted changes
listed in the bundle manifest that `tools/make_bundle.sh` writes (`build/stage/BUNDLE_MANIFEST.txt`, not in the repository). These include the 1 g psSAR option in `sar_extractor.py`.

> **Code version and defaults.** All runs used GOLIAT at git `7301f24` plus the uncommitted files in the manifest.
> In that code `bbox_padding_mm` is 0 and the grid step at 5200/5800 MHz is 1.0 mm. After `7301f24` the defaults are
> `bbox_padding_mm: 20` and 0.7 mm at 5200/5800 MHz, and the two attribute assignments that Sim4Life 9.6 rejects
> (Shim 3) have try/except guards. No run used those files. The closest runs are the padded rows of Case 1
> and the 0.7 mm rows of Case 3 below.

## Layout

| path | content |
|---|---|
| `tools/osparc_job.py` | stdlib oSPARC client (submit/poll/stop/collect) |
| `tools/make_bundle.sh` | packages `goliat/` + `runner/valdriver` into `build/goliat_bundle.zip` |
| `tools/specs.py` | run-spec builders (every override is a normal GOLIAT config key) |
| `tools/analyze.py`, `tools/table.py` | parse logs/results, compare with `goliat/validation/analytic.py` |
| `tools/convergence.py` | convergence table and generalised Richardson extrapolation, written to `case3_convergence/convergence_table.json` |
| `runner/main.py` | runner entrypoint: installs vendored wheels, runs each spec in its own subprocess |
| `runner/valdriver/run_one.py` | per-run driver (phantom build, config, shims, output collection) |
| `case*/…/case.json` | the exact run specs submitted; `…/results.json` = parsed results. The raw downloaded outputs (`…/raw/`) are not in the repository. |

## Shims (everything the driver does that a normal GOLIAT install would not)

1. Phantom: an icosphere (level 6, 40 962 vertices, volume 0.99986 of the true sphere) or a box is written
   as STL, imported into Sim4Life as a `TriangleMesh` named after the IT'IS tissue, and exported to
   `data/phantoms/<phantom>.sab`. GOLIAT's `PhantomSetup` imports that file in the same way as a licensed phantom.
2. Config: the driver writes `data/material_name_mapping.json` (tissue → IT'IS 4.2 material, `skin_group` for SAPD) and
   `configs/validation.json` = `{"extends": "far_field_config.json", …overrides}`. The working directory is the scratch base_dir.
3. Sim4Life 9.6 setattr shim: the 9.6 wrappers raise `AttributeError: Cannot set unknown attribute` when code sets an attribute that does not exist. Older
   SDKs ignored such assignments. GOLIAT at `7301f24` sets two such attributes: `Simulation.Frequency`
   (`goliat/setups/far_field_setup.py:182`, `near_field_setup.py:578`) and `GlobalGridSettings.BoundingBox`
   (`goliat/setups/gridding_setup.py:228`). Neither exists in the 8.2 API reference, so both assignments had no effect in older SDKs. The
   shim ignores both assignments and logs each one (`permissive_setattr_hits` = exactly these two in every run).
   No goliat/ code was changed for these runs. After `7301f24`, both assignments have try/except guards.
4. 8 MB output threshold: GOLIAT uses `goliat/constants.py MIN_H5_FILE_SIZE_BYTES = 8 MB`. It treats a smaller
   `_Output.h5` as a failed run and silently skips extraction ("Run deliverables not found"). Small validation
   grids produce valid outputs below 8 MB, so the driver lowers the threshold to 1 byte (logged in driver_report).
   Three runs of the first sweeps have no extracted results for this reason. They were rerun in later jobs.

Materials: Sim4Life's built-in IT'IS 4.2 database, evaluated by GOLIAT at the run frequency. The values below were read
from GOLIAT's log and are used for the analytic reference: Muscle 2450 MHz εr 52.7295 σ 1.7388 S/m ρ 1090.4;
Muscle 5800 MHz εr 48.4846 σ 4.9616; Skin 10 GHz εr 31.2902 σ 8.0140 ρ 1109 (= Gabriel dry skin).

Normalisation: GOLIAT's plane wave uses the Sim4Life default amplitude, which we take as 1 V/m peak
(S_inc = 1/(2·377) W/m²). The agreement with Mie at the 0.1 % level (below) shows that this is a peak value. With an RMS
amplitude the result would differ by a factor of 2.

## Case 1: far-field normalisation (muscle sphere vs Mie)

Sphere r = 50 mm, 2450 MHz, x-incidence, GOLIAT grid 1.482 mm (actual step 1.471 mm, 11.5 cells/λ in muscle).
The reference is `analytic.sphere_wb_sar` (Mie) with the IT'IS values above. WB-SAR is the Sim4Life "All Regions"
mass-averaged SAR from GOLIAT's `SarExtractor`.

| run | change vs `far_field_config.json` at `7301f24` | WB-SAR err vs Mie |
|---|---|---|
| `p1_sphere50_2450_default` | none (bbox_padding 0) | **+51.3 %** |
| d1/d2 | 20× sim time, −15 / −50 dB | +54.6 % (identical) |
| m3 | bbox_padding 5 mm | −0.11 % |
| m2 | bbox_padding 10 mm | +0.51 % |
| d3 | padding 25 mm, 20× time | +0.90 % |
| d4 / d5 | padding 50 mm, 20× time, PML Low / High | +1.29 % / +1.16 % |
| d6 | padding 50 mm, default time | +1.31 % |
| m1 | bbox 0 but grid padding 25 mm | −1.69 % |

At 5.8 GHz with r = 25 mm and the `7301f24` defaults (padding 0, 1.0 mm), the WB-SAR error is +78 % (`s5800_dx1p0_production_pad0`).

Finding: the far-field normalisation (amplitude to S_inc, power and SAR extraction, mass) is correct to ≈1 %.
The far-field default at `7301f24` is `simulation_parameters.bbox_padding_mm: 0`
(`goliat/config/defaults/far_field_config.json`). With this value the tissue is directly against the UPML, so the
absorbed power is 50–80 % too high for these spheres. Simulation time and termination criterion are not the cause (d1 = d2).
Whole-body phantoms touch the boundary only at the extremities. Whether they have the same bias was not tested.

## Case 3: grid convergence (the default grid rule)

GOLIAT's default grid rule at `7301f24` (both `far_field_config.json` and `near_field_config.json`,
`gridding_parameters.global_gridding_per_frequency`, used as a uniform manual max step):
450–1450 MHz → 2.5 mm, 2140 → 1.694, 2450 → 1.482, 3500 / 5200 / 5800 → 1.0 mm, any other frequency →
`manual_fallback_max_step_mm` (2.0 far-field, 3.0 base). `GriddingSetup` refuses steps above 3 mm. The FR3 configs add
7000 → 0.6, 9000/11000 → 0.5, 13000 → 0.45, 15000 → 0.4, 26000 → 0.3. The rule is a fixed table and does not use a cells-per-
wavelength criterion. At 5.8 GHz it gives 7.4 cells/λ in muscle (IT'IS 4.2 εr 48.5) and ~6 in vitreous (εr ≈ 67 by
Gabriel). Vitreous was not simulated here.

The phantoms are homogeneous muscle spheres in an x-incident plane wave. All other settings are GOLIAT defaults except the bbox padding
(15 mm at 5.8 GHz, 25 mm at 2.45 GHz, to remove the Case-1 bias), 10× sim time at 5.8 GHz, and PML strength
High (see below). WB-SAR is compared with Mie (exact). psSAR10g/1g (IEEE/IEC 62704-1 cubes, GOLIAT
`SarExtractor`, 1 g via `extraction.psSAR_averaging_masses_g: [1, 10]`) have no exact reference. They are
compared with the finest grid. Where the three finest grids give an observed order 0.5 < p < 4, they are also compared with the Richardson value.
Source: `case3_convergence/convergence_table.json` (`tools/convergence.py`).

**5.8 GHz, r = 25 mm**

| dx (mm) | cells/λ | WB-SAR vs Mie | psSAR10g vs 0.35 mm | psSAR1g vs 0.35 mm | psSAR1g vs Richardson |
|---|---|---|---|---|---|
| 1.379 | 5.4 | −8.61 % | −12.82 % | −12.21 % | −13.73 % |
| **1.000 (default)** | **7.4** | **−2.26 %** | **−6.42 %** | **−5.01 %** | **−6.66 %** |
| 0.696 | 10.7 | +0.35 % | −1.94 % | −2.25 % | −3.94 % |
| 0.500 | 14.8 | +1.03 % | −0.98 % | −0.94 % | −2.66 % |
| 0.349 | 21.2 | +1.16 % | 0 | 0 | −1.73 % |

Observed order (three finest grids): WB-SAR p = 5.0, psSAR1g p = 1.19, psSAR10g p = 0.17. The extrapolated WB-SAR is +1.19 % above Mie. This residual offset is
attributed to the 15 mm air gap and the PML. With p = 0.17, psSAR10g is
not in the asymptotic range. Its converged value may be a further ~1–3 % above the 0.35 mm value.

**2.45 GHz, r = 50 mm**

| dx (mm) | cells/λ | WB-SAR vs Mie | psSAR10g vs 0.7 mm | psSAR1g vs 0.7 mm | psSAR1g vs Richardson |
|---|---|---|---|---|---|
| 2.500 | 6.7 | −2.26 % | −1.54 % | −21.77 % | −23.65 % |
| **1.471 (default)** | **11.5** | **+0.94 %** | **−1.86 %** | **−7.25 %** | **−9.49 %** |
| 1.000 | 16.9 | +1.23 % | −0.48 % | −2.32 % | −4.67 % |
| 0.698 | 24.2 | +1.08 % | 0 | 0 | −2.41 % |

psSAR1g order p = 1.84 (1.47/1.0/0.7 mm). psSAR10g order p = 2.61 (extrapolated value +0.3 % above the 0.7 mm value).

The PML strength changes the results on fine grids. With GOLIAT's default `UpmlCpml` strength Low, the same grid series are
non-monotone at the finest grid (5.8 GHz 0.35 mm: WB −0.68 %, psSAR10g −2.6 % vs High; 2.45 GHz 0.7 mm:
WB −2.09 % vs +1.08 % with High, and +3.39 % with Low + 50 mm padding). PML Low changed results by about 0.1 % at
1.47 mm (d4 vs d5). Hypothesis (consistent with these runs, not proven): the PML has a
fixed number of cells, so on fine grids it is physically thin and reflects. The effect of the reflected wave
on the sphere depends on the air gap.

Grid alignment: a translation of the sphere by (0.37, 0.29, 0.11) mm gave bit-identical results because GOLIAT
aligns the grid to the phantom bbox. The sensitivity to the position of the sphere within a grid cell was therefore not measured.

## Case 2: APD at 10 and 30 GHz (skin slab vs (1−|Γ|²)·S_inc)

The phantom is a slab of IT'IS 4.2 "Skin" (εr 31.29, σ 8.014 at 10 GHz and εr 15.51, σ 27.10 at 30 GHz, equal to Gabriel dry skin).
The plane wave is at normal incidence (−z). APD is from GOLIAT's `SapdExtractor` (Sim4Life `GenericSAPDEvaluator`, 4 cm², 10 mm threshold). The
`sapd_field` 4 cm²-averaged APD map is in `skin_apd.npz`. The analytic APD is T = 0.4888 (10 GHz) and 0.5418 (30 GHz)
per W/m² of incident power density. `sapd_slicing_side_length_mm` and `sapd_mesh_slicing_side_length_mm` were set to 400 mm so that the slab
centre is inside GOLIAT's slice.

| run | slab (mm) | cells/λ skin | centre APD (10×10 mm² around centre) vs T | GOLIAT peak SAPD vs T |
|---|---|---|---|---|
| slab10G_N6 / N10 / N15 / N20 | 80×80×15 | 6/10/15/20 | −19.6 / −8.2 / −7.1 / −8.1 % | −3.1 / +45.6 / +14.1 / +7.8 % |
| big10G_N10 | 200×200×6 | 10 | +10.4 % (ripple ±5 % within r < 60 mm) | +20.9 % (max at slab edge) |
| slab30G_N6 / N10 / N15 | 40×40×8 | 6/10/15 | −15.6 / +1.7 / +4.9 % | −7.3 / +8.9 / +19.1 % |
| big30G_N10 | 100×100×3 | 10 | −12.6 % (flat to ±0.1 %) | −7.5 % |

Finding: GOLIAT's APD extraction gives the right magnitude at 10 and 30 GHz. At ≈10 cells/λ
the centre APD differs from the analytic value by −13 % to +10 % across runs with similar geometry.
The reported peak SAPD is an edge effect of the finite slab (the peak is at the slab edge). A possible cause of the run-to-run
differences is the position of the slab surface relative to the grid nodes (`big30G_N10`: surface exactly on a
node, −12.6 %, `slab30G_N10`: 0.28 cell off, +1.7 %). This hypothesis was not tested separately. Grid convergence was not shown:
the 200×200×6 mm slab at 15 cells/λ (`big10G_N15`) did not finish within the job time limit. `peak_sapd_location_m` is null because the location is not
parsed from the Sim4Life 9.6 evaluator output.

## Case 4: IEEE 1528 dipole over a flat phantom

A script builds and places the dipole. GOLIAT's antenna import and its placement relative to phantom landmarks are not used. `runner/valdriver/run_dipole.py`
runs `NearFieldStudy.run()` with four patches. The dipole (two PEC cylinders, d = 3.6 mm, 1 mm gap, `Feed`
polyline, axis parallel to the liquid surface at distance s) replaces `PlacementSetup.place_antenna`.
The simulation box (phantom + 20 mm laterally/below, dipole + 50 mm above) replaces `_create_simulation_bbox`.
The head/trunk boxes are skipped. Constants for the liquid (ρ 1000) and the shell (2 mm, εr 4, σ 0, ρ 1 kg/m³ so it adds no mass)
replace the IT'IS lookup. All other steps are GOLIAT's own code: solver settings, simulation time and termination, PEC from
`antenna_config.materials`, `GriddingSetup` (global per-frequency step + manual arm grid [1.0, 0.4, 0.4] mm +
automatic feed grid), `BoundarySetup`, `SourceSetup` (harmonic edge source + edge sensor), voxelisation, run,
`ResultsExtractor` (near-field input power, 1 g/10 g psSAR) and `NearFieldAnalysisStrategy.get_normalization_factor`
with `target_power_mW: 1000`, which scales the results to 1 W net input power.

IEEE 1528 parameters used (not checked against the
text of the standard): 835 MHz (L 161.0 mm, s 15 mm, εr 41.5, σ 0.90), 1900 MHz (L 68.0, s 10,
εr 40.0, σ 1.40), 2450 MHz (L 51.5, s 10, εr 39.2, σ 1.80). Targets per 1 W: 9.56/6.22, 39.7/20.5, 52.4/24.0 W/kg
(1 g/10 g). The liquid size, 360×240×150 mm (835) and 240×160×100 mm (1900/2450), was chosen for these runs.

| run | global step (mm) | MCells | P_in (W, raw) | psSAR1g per W (target) | err | psSAR10g per W (target) | err | power balance |
|---|---|---|---|---|---|---|---|---|
| d835_g2p5 (GOLIAT default) | 2.5 | 4.1 | 2.493e-3 | 9.69 (9.56) | +1.4 % | 6.24 (6.22) | +0.4 % | 97.2 % |
| d835_g1p6 | 1.6 | 10.0 | 2.498e-3 | 9.67 | +1.2 % | 6.26 | +0.6 % | 98.0 % |
| d1900_g1p694 (default step for 2140 MHz) | 1.694 | 3.3 | 2.476e-3 | 39.76 (39.7) | +0.1 % | 20.40 (20.5) | −0.5 % | 96.4 % |
| d1900_g1p0 | 1.0 | 11.6 | 2.470e-3 | 42.56 | +7.2 % | 21.85 | +6.6 % | 98.7 % |
| d2450_g1p482 (GOLIAT default) | 1.482 | 4.4 | 2.464e-3 | 55.13 (52.4) | +5.2 % | 24.99 (24.0) | +4.1 % | 96.1 % |
| d2450_g1p0 | 1.0 | 11.6 | 2.464e-3 | 57.09 | +8.9 % | 26.00 | +8.3 % | 98.2 % |

The arm grid is [1.0, 0.4, 0.4] mm in all runs. The per-W values are GOLIAT's raw psSAR times the `NearFieldAnalysisStrategy`
factor (1 W / P_in). These runs also test the 1 g psSAR extraction of near-field studies in Sim4Life
(`peak_sar_1g_W_kg`, `peak_sar_details_1g`).

Finding: GOLIAT's near-field source, input-power normalisation and 1 g/10 g psSAR extraction reproduce the IEEE 1528
targets within −0.5…+5.2 % at the default grids. On the finer global grid, the 1900 and 2450 MHz results are further from the
targets (+7…+9 %), so the agreement at the default grids is not grid-converged. The results are probably sensitive to
sub-millimetre changes of the effective dipole–liquid distance and of the feed-gap model on the staircased grid
(SAR scales roughly with 1/s²). This is a hypothesis that was not tested separately. A coarser run at 1900 MHz with a 3 mm grid and a 120×80×40 mm liquid gave 37.4 / 19.2 W/kg
(−5.8 / −6.3 %, files in `case4_dipole/probe`).

## Case 5: Li et al. 2026 intercomparison (ViP Ella, licensed Sim4Life 9.2, GPU)

A dipole and a 4×4 dipole array were simulated at 10 and 30 GHz, at d = 10, 15 and 20 mm in front of the left cheek of ViP Ella,
with 10 mW input power. The sAPD over 1 cm² and 4 cm² from GOLIAT's `SapdExtractor` is compared with the
inter-lab mean ± SD in Li et al. 2026 (PMB 71 01NT02), Table 3 (pooled over their Alvar and VHP heads). In the table below, z = (GOLIAT value − Li mean) / Li SD.

The oSPARC runner used for the other cases could not decrypt ViP Ella. The licence is not part of the
`.sab` file, and the imported group was empty (`case5_li/probe`, `probe2`, `probe3`).
Therefore, Case 5 ran on a Windows 10 virtual machine
with one RTX A6000 GPU:
- Sim4Life 9.2.1.19976 with a SPEAG FlexNet licence (`MODEL_ELLA`, `CUDA_TOKEN`).
- GOLIAT installed from the working tree into the Python that ships with Sim4Life.
- Per-run files: specs in `windows_vm/specs/`, reports and logs in `case5_li/vm92/out/<run>/`.
- Comparison: `tools/case5_table.py` writes `case5_li/results.json`.

Setup (`runner/valdriver/run_head.py`, `run_head_win.py`):
- GOLIAT `NearFieldStudy` (phantom load, materials with the Ella IT'IS mapping, gridding, PML High,
  voxelisation, iSolve with the CUDA kernel (`manual_isolve: true`), power/SAR/SAPD extraction).
- Scripted PEC dipole(s), L = 0.45 λ, r = 0.5 mm. The 4×4 array uses λ/2 pitch with all feeds driven.
- Antenna centre halfway along GOLIAT's by_cheek ear-to-lips line, mirrored to the left side, at d from
  Skin (`GetEntityPointDistance`). The cheek is curved, so the dipole tips are ≈ 1.6 mm closer to the skin than d
  (at d = 15 mm the minimum metal-to-skin distance is 13.4 mm). Li et al. do not state which point their d refers to.
- Uniform grid of 0.5 mm (10 GHz) or 0.25 mm (30 GHz), as in Li. Cropped domain with ≥ 20 mm air padding.
- sAPD over 4 cm² from GOLIAT and over 1 cm² from a second run of the same evaluator. Results are scaled linearly to 10 mW input power.
- 12/12 runs completed, about 8 min each (FDTD ≈ 440 MCells/s on the A6000). Power balance 95.6–98.9 %.

| run | sAPD 1 cm² (W/m²) | Li Table 3 | z | sAPD 4 cm² (W/m²) | Li Table 3 | z |
|---|---|---|---|---|---|---|
| dip 10 GHz 10 mm | 3.91 | 3.09 ± 0.85 | +0.97 | 2.57 | 1.87 ± 0.47 | +1.49 |
| dip 10 GHz 15 mm | 2.59 | 2.01 ± 0.52 | +1.12 | 2.06 | 1.48 ± 0.35 | +1.64 |
| dip 10 GHz 20 mm | 1.64 | 1.29 ± 0.35 | +1.00 | 1.41 | 1.04 ± 0.25 | +1.49 |
| dip 30 GHz 10 mm | 5.14 | 4.15 ± 0.75 | +1.32 | 3.22 | 2.37 ± 0.40 | +2.12 |
| dip 30 GHz 15 mm | 2.61 | 2.14 ± 0.41 | +1.14 | 2.00 | 1.55 ± 0.25 | +1.81 |
| dip 30 GHz 20 mm | 1.48 | 1.27 ± 0.24 | +0.89 | 1.29 | 1.03 ± 0.18 | +1.45 |
| arr 10 GHz 10 mm | 1.55 | 0.96 ± 0.37 | +1.61 | 1.09 | 0.72 ± 0.29 | +1.27 |
| arr 10 GHz 15 mm | 1.74 | 1.61 ± 0.54 | +0.24 | 1.55 | 1.31 ± 0.39 | +0.62 |
| arr 10 GHz 20 mm | 2.03 | 1.48 ± 0.61 | +0.90 | 1.74 | 1.25 ± 0.48 | +1.03 |
| arr 30 GHz 10 mm | 13.59 | 12.42 ± 2.85 | +0.41 | 6.86 | 5.97 ± 1.45 | +0.62 |
| arr 30 GHz 15 mm | 13.02 | 11.59 ± 2.89 | +0.50 | 6.13 | 5.17 ± 1.25 | +0.77 |
| arr 30 GHz 20 mm | 11.10 | 9.71 ± 2.53 | +0.55 | 5.62 | 4.57 ± 1.17 | +0.89 |

Results:
- 23 of 24 values are within 2 inter-lab SD. The exception is the dipole at 30 GHz and 10 mm over 4 cm², at +2.1 SD.
- Every value is above the Li mean: the dipole by +17…+39 % (1 cm²: +17…+29 %, 4 cm²: +25…+39 %) and the array by +8…+62 % (largest at
  10 GHz and 10 mm, where the inter-lab SD is ±39 %).
- The qualitative pattern matches Li:
  - dipole sAPD falls with d
  - at 30 GHz the array gives 2.6–7.5× the dipole sAPD over 1 cm²
  - at 10 GHz the array sAPD is below the dipole sAPD at 10 mm and above it at 20 mm.
- The geometry is not the same as in Li: Ella is a third head (Li used Alvar
  and VHP-Female). The face shape and the distance convention can each give a uniform
  positive offset. These runs cannot separate that offset from a bias in GOLIAT or Sim4Life.

Observations on GOLIAT with Sim4Life 9.2 and the licensed phantom:
- `model.AllEntities()` returns all tissue meshes. The oSPARC 9.6 runner returned only top-level entities
  because the phantom stayed encrypted there, so GOLIAT's entity handling is not the cause.
- `manual_isolve: false` (the `Sim4LifeAPIStrategy`) fails in a headless Windows service session with "No
  connection available to submit jobs". `manual_isolve: true` (the shipped default) works.
- The driver finds the antenna position by repeated steps of (distance − d), with `GetEntityPointDistance` on the full Ella skin.
  This placement code is in the validation driver and is not part of GOLIAT.

## oSPARC jobs

| label | job id | state | credits (runtime × 7 cr/h, runner SMALL) |
|---|---|---|---|
| probe1_sphere2450_default | `5b4972fe-2da1-4614-bd61-1a2a7d047cd3` | SUCCESS | 0.419 |
| probe2_sphere2450_default | `47626902-8ee5-420d-8ed2-864b469e9927` | SUCCESS | 0.052 |
| probe3_sphere2450_default | `fdba6d5b-fe5d-4a8f-a7c5-3e9b520c98dc` | SUCCESS | 0.056 |
| probe4_sphere2450_default | `c418c866-ffd5-4a76-aaec-fee0cda04b9a` | SUCCESS | 0.067 |
| case1_diag_matrix_2450 | `0a770566-2dde-4706-b1ca-a087af565760` | SUCCESS | 0.028 |
| case1_diag_matrix_2450_retry | `620ccc46-0fd6-4276-8bec-2beb758c13c7` | SUCCESS | 1.676 |
| case3_sweep5800 | `2e365758-b090-42e8-aede-1af73247f28a` | SUCCESS | 2.158 |
| case3_sweep2450_mech | `2a765eb2-63f7-4499-9b59-8742f7d57aca` | SUCCESS | 0.958 |
| case2_slab_sweep | `f12d42f3-2cb7-4dda-8342-b34ee4426a64` | SUCCESS | 3.121 |
| case2_slab_large | `1eb10dce-8f4f-4fdc-a907-1db10f8a24c6` | ABORTED | 6.609 |
| case3_pmltest | `4387af79-35b7-425d-b6b0-f15faa57f886` | SUCCESS | 3.62 |
| case3_followA | `da38051a-24b7-4509-9e06-a0089702995c` | SUCCESS | 3.473 |
| case3_followB | `23821e6c-f7d9-412f-ad39-4cc296df267d` | SUCCESS | 0.934 |
| case3_pmlhigh_ladders | `48fc16df-aaf9-40ff-adca-4f675c57f41e` | SUCCESS | 1.437 |
| case2_slab_large_v2 | `c4c32803-0a52-4919-8253-9f2ca365fac7` | SUCCESS | 5.869 |
| case4_probe1900 | `9306021b-4445-43e7-89e4-9b098c2d4f40` | SUCCESS | 0.408 |
| case4_dipole_full | `302fd010-aecf-4ca6-98f5-eceebce30a4f` | SUCCESS | 5.912 |

The 17 jobs in the table used 36.80 cr in total (runtime × rate).

`case1_diag_matrix_2450` found no `case.json` and ran nothing. `case2_slab_large` was stopped at its
time limit before it wrote outputs. Both were resubmitted (`case1_diag_matrix_2450_retry`, `case2_slab_large_v2`).


## Summary of results

Shown by the runs:
- The far-field normalisation (plane wave of 1 V/m peak, S_inc = 1/(2η0), GOLIAT power and SAR extraction,
  ×754 rounding = 0.07 %) gives WB-SAR within ≈ 1 % of Mie when the phantom does not touch the PML.
- With `bbox_padding_mm: 0` (the far-field default at commit `7301f24`) the sphere WB-SAR is +51 % (2.45 GHz) and +78 %
  (5.8 GHz) too high.
- At 5.8 GHz the 1.0 mm grid (the default at `7301f24`, 7.4 cells/λ in muscle) underestimates psSAR10g by 6.4 % and psSAR1g by
  5.0 % (6.7 % vs Richardson) and WB-SAR by 2.3 %. With 0.7 mm (≈ 10.7 cells/λ, the "10 cells per wavelength"
  rule) all three are within ≈ 2 % of the finest grid (psSAR1g −3.9 % vs Richardson). The ±5 % FDTD
  tolerance is therefore met at ≥ 10 cells/λ. At 1.0 mm (7.4 cells/λ) the psSAR errors are slightly above it.
- At 2.45 GHz the default 1.482 mm (11.5 cells/λ) is fine for WB-SAR (+0.9 %) and psSAR10g (−1.9 %) but
  psSAR1g is −7.3 % (−9.5 % vs Richardson). psSAR1g needs a step of ≈ 1.0 mm.
- With PML strength Low (the default), results on sub-millimetre grids differ by 2–3 % from PML High.
- APD at 10 and 30 GHz has the right magnitude, with ±13 % scatter at 10 cells/λ. Convergence was not shown.
- Near field (scripted dipole placement, GOLIAT source/normalisation/extraction): IEEE 1528 1 g/10 g targets
  reproduced within −0.5…+5.2 % at default grids (835/1900/2450 MHz), +7…+9 % on 1.0 mm grids at 1900/2450 MHz.
- Face intercomparison (ViP Ella, Sim4Life 9.2): all 24 sAPD values are above the inter-lab means of Li et al. 2026
  (+8…+62 %, 1.1 SD on average, 2.1 SD at most).

Not tested: cells per wavelength in vitreous humour in anatomical models, the zero-padding bias
in whole-body phantoms, and GOLIAT's own phone-antenna import and placement (Case 4 used scripted placement).
Hypotheses only: the PML-thickness explanation (Case 3) and the grid-alignment explanation for APD (Case 2).
