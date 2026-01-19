# Codebase Concerns

**Analysis Date:** 2026-01-20

## Tech Debt

**GAP-01: Wrong Data Source (CRITICAL):**
- Issue: `talking_hedz_extracted.json` contains incorrect frequency data - likely from DLL extraction with RGB contamination
- Files: `C:\Users\hooki\yup\talking_hedz_extracted.json`
- Impact: ALL validation tests invalid. Formant frequencies are ~6x wrong (1371 Hz vs expected 217 Hz)
- Evidence: Raw Cheat Engine capture shows 217 Hz; extracted JSON shows 1371 Hz; reference IR confirms 218 Hz
- Fix approach: Regenerate from `talking_hedz_complete.json` raw a1/r coefficients applying:
  1. Proper Hz decoding: `freq = arccos(-a1/(2*r)) * sr / (2*pi)`
  2. 7.4 semitone tuning correction
  3. Grid interpolation for full 17x17 coverage
- Tracked in: `.planning/phases/01-dsp-engine/01-UAT.md`

**Duplicate/Conflicting Header Files:**
- Issue: Two different filter implementations exist with conflicting namespaces and approaches
- Files:
  - `C:\Users\hooki\yup\ZPlaneFilter.h` (195 lines, `ZPlane` namespace, older)
  - `C:\Users\hooki\yup\ZPlaneData.h` (127 lines, `ZPlane` namespace)
  - `C:\Users\hooki\yup\Source\dsp\ZPlaneFilter.h` (477 lines, `Trench` namespace, newer)
- Impact: Confusion about which implementation is authoritative; test file may reference wrong version
- Fix approach: Remove root-level headers or consolidate into `Source/dsp/` with single namespace

**Deleted Files Not Committed:**
- Issue: Three critical DSP files deleted but change not committed
- Files (deleted from working tree):
  - `Source/dsp/CartridgeLoader.h`
  - `Source/dsp/GridInterpolator.h`
  - `Source/dsp/ZPlaneEngine.h`
- Impact: `Tests/test_cartridge_load.cpp` includes `CartridgeLoader.h` - build will fail
- Fix approach: Either restore files or update test to use current implementation

**Python/C++ Implementation Drift:**
- Issue: Python validation code has experimental HYBRID topology; C++ has CASCADE topology
- Files:
  - `C:\Users\hooki\yup\validate_zplane.py` (HYBRID experiments, modified)
  - `C:\Users\hooki\yup\Source\dsp\ZPlaneFilter.h` (CASCADE topology)
- Impact: Python cannot validate C++ behavior if they use different algorithms
- Fix approach: After resolving GAP-01, unify on single topology approach

**Orphan Analysis Scripts:**
- Issue: 15+ Python scripts in root directory from debugging/analysis phases
- Files (root level):
  - `analyze_reference.py`, `analyze_reference_corrected.py`, `analyze_reference_deep.py`
  - `debug_coefficients.py`, `debug_zplane.py`, `debug_impulse.py`, `debug_m100q0.py`
  - `validate_zplane.py`, `validate_grid_engine.py`, `validate_trench.py`, `validate_trench_v2.py`
  - `compare_fft.py`, `log_encode_captures.py`, `analyze_cartridge.py`
- Impact: Cluttered root directory; unclear which scripts are current vs obsolete
- Fix approach: Move to `Scripts/` or `Tests/archive/`; document purpose of retained scripts

## Known Bugs

**None currently tracked** - GAP-01 blocks proper testing

## Security Considerations

**Reverse Engineering Tools Present:**
- Risk: Lua scripts for Cheat Engine memory capture could raise legal concerns
- Files: `C:\Users\hooki\yup\ce_capture_grid.lua`, `C:\Users\hooki\yup\x3_dump.lua`
- Current mitigation: Files used for legitimate coefficient extraction, not distribution
- Recommendations: Consider moving to separate extraction repo; document purpose

**No Credential Exposure:**
- No `.env` files, API keys, or credentials detected
- Current mitigation: N/A - clean state

## Performance Bottlenecks

**None identified** - DSP code is header-only with inline processing; performance profiling not yet performed

## Fragile Areas

**Q Scaling Formula:**
- Files:
  - `C:\Users\hooki\yup\Source\dsp\ZPlaneFilter.h` (lines 162-172)
  - `C:\Users\hooki\yup\ZPlaneData.h` (lines 54-75)
- Why fragile: Multiple formula attempts documented in debug sessions:
  - Original exponential: `r = r_ref^(Q_ref/Q_new)` with Q_MIN=0.5 (too aggressive)
  - Corrected exponential: Q_MIN=17 (from X3 captures)
  - Linear alternative: `r = floor + (r_ref - floor) * q`
- History: Debug session `.planning/debug/zplane-reference-file-invalid.md` shows extensive experimentation
- Safe modification: Any Q formula change requires re-running all validation tests
- Test coverage: Currently blocked by GAP-01; needs dedicated unit tests

**Filter Topology:**
- Files: `C:\Users\hooki\yup\Source\dsp\ZPlaneFilter.h` (CASCADE processing loop)
- Why fragile: Previous debug session incorrectly concluded PARALLEL topology
- History: NotebookLM research confirmed CASCADE is correct per E-mu patents
- Safe modification: Do NOT change to PARALLEL without E-mu documentation evidence
- Test coverage: Topology correctness depends on reference match (blocked by GAP-01)

**Coefficient Formula (a1 multiply):**
- Files: `C:\Users\hooki\yup\Source\dsp\ZPlaneFilter.h` (lines 179-205)
- Why fragile: Critical that `a1_actual = a1_captured * radius` - documented in spec
- Safe modification: Formula verified via Cheat Engine captures; do not change
- Test coverage: Covered by cartridge load test indirectly

## Scaling Limits

**Not applicable** - Offline audio plugin with fixed 7-stage architecture

## Dependencies at Risk

**nlohmann/json (vendored):**
- Risk: Single-header file vendored at `Source/external/json.hpp` - version 3.11.3
- Impact: No automatic security updates
- Migration plan: Monitor nlohmann/json releases; manual update if needed

## Missing Critical Features

**Data Regeneration Pipeline:**
- Problem: No automated way to regenerate `talking_hedz_extracted.json` from source captures
- Blocks: GAP-01 resolution requires manual coefficient processing
- Files needed: Script to process `talking_hedz_complete.json` with proper formulas

**C++ Validation Test:**
- Problem: No C++ test validates actual filter output matches reference audio
- Blocks: Cannot verify C++ implementation without Python dependency
- Files needed: C++ equivalent of `Tests/validate_against_reference.py`

## Test Coverage Gaps

**DSP Processing Untested:**
- What's not tested: Actual filter audio output, biquad correctness, cascade behavior
- Files: `C:\Users\hooki\yup\Source\dsp\ZPlaneFilter.h` (main DSP code)
- Risk: Filter could be silently broken without reference comparison
- Priority: HIGH (blocked by GAP-01)

**Interpolation Untested:**
- What's not tested: Trilinear grid interpolation, morph boundary cases
- Files: Deleted `GridInterpolator.h` or equivalent
- Risk: Edge case interpolation bugs (morph=0, morph=1, Q=0, Q=1)
- Priority: MEDIUM

**Sample Rate Warping Untested:**
- What's not tested: `warpA1ForSampleRate()` function at 48kHz/96kHz
- Files: `C:\Users\hooki\yup\ZPlaneFilter.h` (lines 171-188)
- Risk: Filter sounds wrong at non-44.1kHz rates
- Priority: LOW (Phase 2 concern)

**Only Cartridge Load Test Exists:**
- What's tested: JSON parsing, Hz/semitone round-trip, cell population
- Files: `C:\Users\hooki\yup\Tests\test_cartridge_load.cpp`
- Coverage: ~10% of DSP functionality
- Priority: HIGH - need filter output tests

## Investigation Items (from STATE.md)

**Formant Frequency Offset:**
- Observation: Formant frequencies differ between reference captures and DSP output
- Tracked for: Phase 3 (Accuracy)
- Possible causes:
  1. Reference not captured at C5 pitch
  2. Different tuning reference
  3. Processed audio vs impulse response
- Recommendation: Capture new reference at known C5 pitch for direct comparison

---

*Concerns audit: 2026-01-20*
