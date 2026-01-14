# Auto-Induced Exposure Research Plan

**Document**: Scientific approach for MaMIMO beamforming worst-case SAPD study  
**Date**: January 2026  
**Status**: Planning phase

---

## 1. Research Questions

### Primary Questions

1. **Distribution**: What is the distribution of induced SAPD when MaMIMO beamforming focuses at arbitrary points near the human body?
   - Is it normal, log-normal, heavy-tailed?
   - What is the range (min to max)?
   - How does it vary across body regions?

2. **Worst-Case**: What is the maximum achievable SAPD under ideal beamforming conditions?
   - Where on the body does it occur?
   - How does it compare to regulatory limits (IEC 62209-3)?
   - How much margin exists?

3. **Proxy Validity**: How well does our fast proxy metric predict actual SAPD?
   - What is the correlation coefficient?
   - Are there systematic biases?
   - Is selecting by proxy sufficient to find the true worst-case?

### Secondary Questions

4. **Frequency Dependence**: How does worst-case SAPD scale with frequency (450 MHz → 5.8 GHz)?

5. **Antenna Configuration**: How does the number of directions/polarizations affect the result?

6. **Body Type Variation**: How do results differ across phantoms (child vs adult, male vs female)?

7. **Focus Distance**: How does SAPD change with distance from skin (10mm vs 50mm)?

---

## 2. Current Tool Capabilities

### What We Have

| Component | Status | Performance |
|-----------|--------|-------------|
| E-field simulation (Sim4Life) | ✅ Working | ~2h per direction |
| Skin/Air voxel extraction | ✅ Working | 1.7s |
| Binary dilation (shell finding) | ✅ Working | 51s for 25mm shell |
| Field caching | ✅ Working | 5GB RAM, 5s load |
| MRT phase optimization | ✅ Working | Per-point at focus |
| Hotspot scoring | ✅ Working | **646 samples/sec** |
| Field combination | ✅ Working | 2s per candidate |
| SAPD extraction (Sim4Life) | ✅ Working | 10s per candidate |
| Focus point markers | ✅ Working | Saved in .smash |

### Key Parameters (Current Config)

```json
{
    "n_samples": 10000,        // Number of random focus points scored
    "top_n": 5,                // Candidates for SAPD extraction
    "shell_size_mm": 25,       // Max distance from skin
    "cube_size_mm": 50,        // Scoring cube size
    "random_seed": 42          // Reproducibility
}
```

### Performance Summary

| Phase | Time | Notes |
|-------|------|-------|
| Voxel extraction | 2s | Fixed |
| Dilation | 51s | Scales with shell_size² |
| Field loading | 5s | Fixed per run |
| **Scoring 10K points** | **15s** | 646/sec, highly scalable |
| Combine fields (5 candidates) | 10s | 2s each |
| SAPD extraction (5 candidates) | 50s | 10s each |
| **Total** | **~2.5 min** | For 10K samples, 5 candidates |

---

## 3. Critical Features To Add

### Priority 1: Data Export (for analysis)

- [ ] **Save all proxy scores** to CSV: `[idx, x_mm, y_mm, z_mm, proxy_score]`
- [ ] **Save proxy-SAPD pairs** for correlation analysis
- [ ] **Export score histogram** as data file

### Priority 2: Improved Candidate Selection

- [ ] **Percentile-based selection**: Sample from top 5% (not just top-N)
- [ ] **Diversity constraint**: Min distance between candidates (e.g., 50mm)
- [ ] **Body region stratification**: Ensure head, torso, limbs all represented

### Priority 3: Uniform Spatial Sampling

- [ ] **Grid-based sampling**: Divide body into 3D grid, sample from each cell
- [ ] **Surface-based sampling**: Sample along skin surface at regular intervals
- [ ] **Farthest Point Sampling (FPS)**: Maximize spatial coverage

### Priority 4: Analysis Automation

- [ ] **Correlation plot**: Scatter proxy vs SAPD with regression line
- [ ] **Histogram generation**: Distribution of all 10K scores
- [ ] **Body heatmap**: 3D visualization of hotspot locations
- [ ] **Summary statistics**: Table with min/max/mean/std per body region

---

## 4. Parameters to Explore

### Numerical Experiments

| Parameter | Values to Test | Hypothesis |
|-----------|----------------|------------|
| `shell_size_mm` | 10, 25, 50, 100 | Closer focus → higher SAPD? |
| `n_samples` | 1K, 10K, 100K | Convergence of max SAPD |
| `cube_size_mm` | 25, 50, 100 | Larger cube → smoother scores |
| `top_n` | 5, 10, 20, 50 | Diversity vs computation |
| Frequency | 450, 2450, 5800 MHz | Wavelength effects |
| Phantom | Duke, Ella, Thelonious, Eartha | Body variation |
| Directions | 4, 6, 12 | Array size effects |

### Sensitivity Analysis

1. **Random seed variation**: Run with seeds 1-10, compare max SAPD
2. **Sample size convergence**: Plot max(proxy) vs n_samples
3. **Shell size sweep**: SAPD vs distance from skin

---

## 5. Proposed Experimental Protocol

### Phase 1: Methodology Validation (Current)

**Goal**: Verify proxy-SAPD correlation

1. Run with current settings (10K samples, 25mm shell)
2. Select 20 candidates from top 5% with diversity constraint
3. Extract SAPD for all 20
4. Compute correlation coefficient R²
5. If R² > 0.8: proceed; else: investigate bias

### Phase 2: Distribution Characterization

**Goal**: Understand proxy score distribution

1. Run 100K samples (conservative for near-exhaustive search)
2. Save all scores to CSV
3. Generate:
   - Histogram with percentile markers
   - Q-Q plot (normality test)
   - Body region breakdown

### Phase 3: Worst-Case Identification

**Goal**: Find and validate maximum SAPD

1. From 100K samples, select top 50 with diversity
2. Extract SAPD for all 50
3. Report:
   - Maximum SAPD value
   - Location (body region)
   - Comparison to IEC limits

### Phase 4: Multi-Parameter Study

**Goal**: Comprehensive results for paper

| Run | Phantom | Frequency | Directions | Expected Time |
|-----|---------|-----------|------------|---------------|
| 1 | Thelonious | 2450 MHz | 4 | 3 min |
| 2 | Thelonious | 2450 MHz | 6 | 4 min |
| 3 | Thelonious | 5800 MHz | 6 | 4 min |
| 4 | Duke | 2450 MHz | 6 | 4 min |
| 5 | Ella | 2450 MHz | 6 | 4 min |
| ... | ... | ... | ... | ... |

---

## 6. Key Metrics for Paper

### Tables

1. **Worst-case SAPD by phantom/frequency**
   | Phantom | 450 MHz | 2450 MHz | 5800 MHz | IEC Limit |
   |---------|---------|----------|----------|-----------|
   | Duke    | X W/m²  | Y W/m²   | Z W/m²   | 20 W/m²   |
   | Ella    | ...     | ...      | ...      | ...       |

2. **Proxy-SAPD correlation by configuration**
   | Configuration | R² | Slope | Bias |
   |---------------|-----|-------|------|

### Figures

1. **Score distribution histogram** (all 10K/100K samples)
2. **Proxy vs SAPD scatter plot** with regression
3. **Body heatmap** showing hotspot probabilities
4. **Convergence plot**: max SAPD vs sample size
5. **Distance analysis**: SAPD vs focus-to-skin distance

---

## 7. Open Questions / Decisions Needed

### Scientific

1. **How many samples are "enough"?** 
   - 10K gives good coverage, 100K near-exhaustive
   - Need convergence analysis

2. **What percentile threshold for candidate selection?**
   - Top 5% = 500 candidates from 10K
   - Too many for SAPD extraction, need subsampling

3. **How to define "diversity"?**
   - Minimum distance in mm?
   - One per body region?

4. **Is E_z the right phase reference?**
   - Currently using E_z only
   - Could use full |E| or specific polarization

### Technical

5. **Storage for 100K samples?**
   - ~10 MB CSV, negligible

6. **Parallel SAPD extraction?**
   - Currently sequential, could parallelize on cluster

7. **Mesh quality issues?**
   - Many "Failed to cover cut loop" warnings
   - May need mesh preprocessing

---

## 8. Next Steps (Immediate)

1. [ ] **Implement CSV export** of all proxy scores
2. [ ] **Add percentile selection** with diversity constraint
3. [ ] **Run validation experiment**: 20 diverse candidates, check correlation
4. [ ] **Create analysis notebook** for histogram/correlation plots
5. [ ] **Document findings** in this file

---

## 9. References

- IEC 62209-3: SAR/SAPD measurement standards
- ITU-T K.52: Guidance on EMF exposure
- Sim4Life SAPD evaluator documentation
- GOLIAT project technical documentation

---

*Last updated: 2026-01-11*
