# FR1 Auto-Induced SAR Pipeline Plan

## Overview

Add auto-induced worst-case SAR extraction at 700 MHz and 3500 MHz (5G FR1, sub-6 GHz).
These frequencies are cheap to simulate (coarse grids), so no bbox reduction or phantom
slicing is needed. SAR is volumetric (unlike SAPD which is surface-based), so we do
full-volume field combination and whole-body SAR extraction.

## Key Design Decisions

### Why it differs from FR3 (SAPD) pipeline

| Aspect | FR3 (7-15 GHz, SAPD) | FR1 (700/3500 MHz, SAR) |
|---|---|---|
| Grid step | 0.4-0.6 mm | 2.5 / 1.0 mm |
| Full-body voxels | ~1 billion | ~22M / ~350M |
| Field combination | Sliced cube around focus | Full volume (chunked) |
| Extraction metric | SAPD (surface, localized) | SAR 10g (volumetric, anywhere) |
| Needs H-field? | Yes (Poynting vector) | No (SAR only uses E) |
| Phantom reduction | Height limits, bbox cuts | None needed |

### Simulation setup

- 4 azimuthal directions (θ=90°, φ=90°/150°/210°/270°) × 1 polarization (theta)
- Same as FR3, NOT the 6×2=12 environmental setup from far_field_config.json
- `do_extract: false` — no per-sim SAR, only auto-induced combined
- `record_h_field: false` — SAR only needs E-field, cuts H5 storage in half

## Implementation Status

### ✅ DONE — Config files (3 new)

- [x] `configs/far_field_FR1_auto_induced_base.json` — base config with 4 azimuthal dirs,
  1 pol (theta), SAR metric, E-field only, no per-sim extraction
- [x] `configs/far_field_FR1_auto_induced_700MHz.json` — extends base, `frequencies_mhz: [700]`
- [x] `configs/far_field_FR1_auto_induced_3500MHz.json` — extends base, `frequencies_mhz: [3500]`

### ✅ DONE — Code changes (`goliat/extraction/auto_induced_processor.py`)

- [x] **`process()`** — reads `extraction_metric` and `full_volume_combination` from config,
  dispatches to `_extract_sar()` or `_extract_sapd()`, uses generic metric keys for
  logging, correlation export, worst-case finding, and return dict
- [x] **`_combine_fields_for_candidate()`** — new `full_volume` and `field_types` params;
  branches to `combine_fields_chunked` (full volume) vs `combine_fields_sliced` (cube)
- [x] **`_extract_sar()`** — NEW method (~155 lines). Uses `SarStatisticsEvaluator` for
  whole-body + peak 10g SAR, `AverageSarFieldEvaluator` for peak location details.
  No skin mesh, no slicing, no `ModelToGridFilter` — much simpler than SAPD.
- [x] **`_find_worst_case()`** — now accepts generic `metric_key` parameter
- [x] Syntax verified with `ast.parse()` ✓

### ✅ NOT changed (reused as-is, no modifications needed)

- `focus_optimizer.py` — frequency-agnostic focus search
- `field_combiner.py` — `combine_fields_chunked` already existed for full-volume
- `far_field_study.py` — auto-induced orchestration unchanged
- `sar_extractor.py` — reference for SAR API calls, not directly used

### ⬜ TODO — Future / runtime validation

- [ ] Run the pipeline on actual Sim4Life with a test phantom to validate
- [ ] Verify `combine_fields_chunked` handles E-only H5 files correctly (template has no H-field)
- [ ] Consider deleting combined H5s after SAR extraction to save disk (currently all 20 kept)
- [ ] Verify gridding parameters produce expected grid sizes at 700/3500 MHz

## Pipeline Flow (SAR mode)

```
1. Run 4 environmental sims (4 dirs × 1 pol) per phantom×freq
   └─ Each produces an _Output.h5 with E-field data (no H-field)

2. Focus search (find_focus_and_compute_weights)
   └─ Find top-20 air hotspot candidates with optimal phase weights
   └─ Reuses existing focus_optimizer.py unchanged

3. For each candidate:
   a. combine_fields_chunked (FULL volume, E-field only)
      └─ Writes combined_candidateN_Output.h5
   b. _extract_sar from combined H5
      └─ SarStatisticsEvaluator → peak SAR 10g, whole-body SAR
      └─ AverageSarFieldEvaluator → peak location details

4. Find worst case across all 20 candidates (highest peak SAR 10g)

5. Export proxy_sar_correlation.csv + auto_induced_summary.json
```

## Storage Estimates

| Freq | Grid | E-field per H5 | 20 candidates |
|---|---|---|---|
| 700 MHz | ~200×150×700 | ~250 MB | ~5 GB |
| 3500 MHz | ~500×350×1700 | ~3.5 GB | ~70 GB |

No H-field stored (halved vs SAPD). Combined H5s can be deleted after extraction
if disk space is a concern (future optimization).
