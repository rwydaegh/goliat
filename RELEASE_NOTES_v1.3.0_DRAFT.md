# GOLIAT v1.3.0 Release Notes (DRAFT)

**Changes since v1.2.3** | ~102 commits | ~40k insertions, ~12k deletions

---

## 🚀 Major New Features

### Multi-Sine Excitation for Far-Field Studies
Simulate multiple frequencies in a single FDTD run, extracting per-frequency SAR results via DFT.

**Config syntax:**
```json
"frequencies_mhz": ["700+2450", 5800]
```

- `"700+2450"` runs both frequencies in one simulation (multi-sine)
- `5800` runs as a single-frequency harmonic simulation (legacy behavior)

**Sub-changes (obscured but important):**
- Custom `UserDefined` excitation expression using sum of cosines
- `ExtractedFrequencies` set on field sensor for DFT extraction
- Simulation time extended for beat period requirement (`T_beat = 1/GCD(f1, f2)`)
- Bandwidth filter explicitly disabled (`ApplyFilter=False`) to allow all frequency components
- Material dispersion fitting via Lorentz model (new `goliat/dispersion/` module)
- `scipy` added as dependency for dispersion fitting optimization

**Docs status:** ✅ Configuration.md updated, ✅ Technical docs exist (3 files), ❌ NOT in feature list

---

### Antenna Detuning Feature (Harmonic Near-Field)
Apply calibrated frequency shifts to account for body loading effects on resonance.

**How it works:**
1. Run calibration sims (Gaussian excitation) to detect resonance shift
2. Store detuning values in config (e.g., `"700": -15` means 15 MHz lower)
3. Harmonic sims automatically apply the detuning offset

**Sub-changes (obscured):**
- Detuning config files for various offsets (`detuning_-10.json`, `detuning_0.json`, etc.)
- `write_during_calibration` flag to suppress warnings during calibration runs
- Integration with resonance extraction from Gaussian results

**Docs status:** ✅ Technical design doc exists, ❌ NOT in feature list, ❌ NOT in user guide

---

### AI Assistant Improvements
Refactored and enhanced the `goliat ai` command.

**New capabilities:**
- Animated thinking spinner (TTY-aware)
- `--simple` and `--complex` flags to force model selection
- Markdown formatting for AI responses
- Detailed cost breakdown with token usage
- Classification time display
- Modular architecture (split into `embedding_indexer`, `query_processor`, `cost_tracker`, `chat_handler`)
- All magic numbers moved to centralized `config.py`

**Docs status:** ✅ Documented in user guide, ✅ In feature list, ❌ New flags not documented

---

### Gaussian Near-Field Support
Use Gaussian pulses for frequency-domain analysis (antenna characterization, detuning detection).

**Key additions:**
- `excitation_type: "Gaussian"` config option
- Custom Gaussian waveform support (`gaussian_pulse_k` parameter)
- `ResonanceExtractor` for detecting antenna resonance
- Bandwidth and frequency resolution config parameters

**Sub-changes (obscured):**
- Custom `UserDefined` waveforms when `k != 5`
- Material setup adjustments for Gaussian excitation
- Power extraction updates for frequency-domain results

**Docs status:** ✅ Technical doc exists, ✅ In feature list (simulation parameters section), ❌ No tutorial

---

## 🔧 Infrastructure & Refactoring

### Simulation Runner Strategy Pattern
Complete refactor of `simulation_runner.py` using Strategy pattern.

**New modules:**
- `goliat/runners/execution_strategy.py` (abstract base)
- `goliat/runners/isolve_manual_strategy.py` (local iSolve)
- `goliat/runners/osparc_direct_strategy.py` (cloud)
- `goliat/runners/sim4life_api_strategy.py` (Sim4Life API)
- `goliat/runners/isolve_process_manager.py`
- `goliat/runners/keep_awake_handler.py`
- `goliat/runners/retry_handler.py`
- `goliat/runners/post_simulation_handler.py`

**Result:** `simulation_runner.py` reduced from ~620 to ~245 lines

**Docs status:** ❌ NOT documented anywhere

---

### Technical Debt Reduction (Phase 1 & 2)
Systematic refactoring across multiple modules.

**Files touched:** `base_study.py`, `project_manager.py`, various setups

**Docs status:** ❌ No user-facing changes, internal only

---

### Plots Module Refactoring
Split `plots.py` into focused modules and reduced `plotter.py` complexity.

**Docs status:** ❌ Internal refactoring, no user impact

---

## 📊 Analysis Enhancements

### Excel Generation
Automatic Excel file generation during analysis workflow.

**Usage:**
```bash
goliat analyze --config <config>  # Now generates .xlsx files
```

**Docs status:** ❌ NOT in feature list, ❌ NOT documented

---

### Unified Stats Command
Merged `stats` and `parse-log` CLI commands into single `goliat stats` command.

**Behavior:**
- Single `.log` file → parses to JSON
- Directory → generates visualizations from all `verbose.log` files

**Docs status:** ❌ NOT in CLI documentation

---

### Analysis GUI Component
New GUI component for analysis progress tracking.

**Docs status:** ❌ NOT documented

---

### UGent vs CNR Comparison Tool
Tool for comparing results between research groups.

**Docs status:** ⚠️ Screenshot in README, ❌ No documentation

---

## 🌐 Cloud & Monitoring

### Web Dashboard Improvements
Multiple fixes for real-time web monitoring.

**Key changes:**
- Screenshot streaming (1 FPS, JPEG compression)
- Message ordering with timestamps and sequence numbers
- Smart batching to adapt to network latency
- Adaptive timeouts to prevent freeze on exit
- Serialized log requests to prevent race conditions

**Sub-fix (obscured):** NTP time for plot timestamps (bypasses VM clock issues)

**Docs status:** ✅ Web dashboard documented, ❌ NTP detail not documented

---

### Cloud Setup Improvements
Better error handling and UX for cloud VM setup.

**Changes:**
- OpenVPN verification before launch
- Working directory fixes when run as administrator
- Parallel launch of license installer and Git Bash
- NVIDIA GPU driver validation

**Docs status:** ✅ Cloud setup docs updated

---

## 🐛 Bug Fixes

### Critical Fixes
| Fix | Description |
|-----|-------------|
| Subgridding contamination | Created separate `Automatic (Subgrid)` grid settings to prevent all components getting subgridded |
| Antenna fallback | Auto-fallback to nearest frequency antenna file when exact match not found |
| Setup timestamp preservation | Preserve setup_timestamp when setup is skipped (caching) |
| Unicode on old Windows | Replace ✓/✗/⚠ with ASCII equivalents for Windows console compatibility |

### Other Fixes
- `scipy` added to dependencies (was missing, broke dispersion fitter tests)
- `openpyxl` added for Excel generation
- Various type errors and missing config key handling
- Power balance calculation improvements
- Bbox expansion for low-frequency whole_body simulations

---

## 📝 Documentation Updates

### Added/Updated
- Configuration guide: multi-sine frequency format
- Analysis documentation expanded (user and developer guides)
- Capita selecta gallery with nested collapsible sections
- AI assistant capabilities advertised

### Technical Docs Added
- `multi_sine_excitation_analysis.md`
- `multi_sine_grouping_math.md`
- `multisine_dispersion_walkthrough.md`
- `detuning_feature_design.md`
- `dispersion_model_guide.md`

---

## ⚠️ Gaps in Documentation (ACTION REQUIRED)

### Feature List (`docs/reference/full_features_list.md`)

**Missing features that MUST be added:**

1. **Multi-sine excitation** - No mention at all
2. **Antenna detuning** - No mention at all
3. **Material dispersion fitting** - No mention (new `goliat/dispersion/` module)
4. **Excel generation** - No mention
5. **Antenna fallback to nearest frequency** - No mention
6. **NTP time for GUI timestamps** - No mention
7. **`goliat stats` unified command** - No mention
8. **Keep-awake functionality** - No mention
9. **Subgridding isolation fix** - No mention
10. **Environment variables** - Missing:
    - `GOLIAT_SKIP_IF_EXISTS`
    - `GOLIAT_AUTO_CLEANUP`

### User Guide Gaps

1. **Detuning workflow** - No user-facing documentation
2. **Multi-sine usage** - Only in configuration.md, no tutorial
3. **Excel export** - Not mentioned
4. **Stats command** - Not in CLI reference

### Configuration Guide Gaps

1. **`detuning_enabled`** - Not documented
2. **`keep_awake`** - Not documented
3. **`gaussian_pulse_k`** - Mentioned but sparse

---

## 📋 Pre-Release Checklist

- [ ] Update `full_features_list.md` with all missing features
- [ ] Add detuning section to user guide
- [ ] Document new environment variables
- [ ] Add `goliat stats` to CLI reference
- [ ] Document Excel generation in analysis section
- [ ] Update version number in `pyproject.toml`
- [ ] Update version in README citation block
- [ ] Create GitHub release with notes
- [ ] Publish to PyPI
