---
status: testing
phase: 01-dsp-engine
source: [01-01-SUMMARY.md, 01-02-SUMMARY.md, 01-03-SUMMARY.md, 01-04-SUMMARY.md]
started: 2026-01-19T07:20:00Z
updated: 2026-01-19T07:20:00Z
---

## Current Test

number: 1
name: Validation script runs
expected: |
  Run `python Tests/validate_against_reference.py` from project root.
  Script should execute without Python errors and print test results.
awaiting: user response

## Tests

### 1. Validation script runs
expected: Run `python Tests/validate_against_reference.py` - script executes without Python errors, prints test results
result: PASS (script runs, but formant frequencies completely wrong)

### 2. VAL-01 passes (m100q0 reference)
expected: Output shows "VAL-01: PASS" for Morph=100%, Q=0% reference comparison
result: SKIPPED (blocked by GAP-01 - formants 4 octaves wrong)

### 3. VAL-02 passes (5050 reference)
expected: Output shows "VAL-02: PASS" for Morph=50%, Q=50% reference comparison
result: SKIPPED (blocked by GAP-01)

### 4. VAL-03 passes (formant changes)
expected: Output shows "VAL-03: PASS" with morph sweep producing >10 semitones range
result: SKIPPED (blocked by GAP-01 - wrong frequencies)

### 5. VAL-04 passes (Q behavior)
expected: Output shows "VAL-04: PASS" with Q=0% response range smaller than Q=100%
result: SKIPPED (blocked by GAP-01)

### 6. Frequency response plots generated
expected: File `validation_plots.png` exists in project root after running validation
result: SKIPPED (blocked by GAP-01 - plots would show wrong frequencies)

## Summary

total: 6
passed: 1
issues: 1
pending: 0
skipped: 5
blocked_by: GAP-01 (wrong data source - all remaining tests invalid until fixed)

## Gaps

### GAP-01: Wrong data source (CRITICAL)
severity: critical
discovered: Test 1
description: |
  `talking_hedz_extracted.json` contains incorrect frequency data — likely from DLL extraction with RGB contamination.

  **Evidence:**
  - Raw Cheat Engine capture (`talking_hedz_complete.json`): Q=100% M=100% Stage 0 = a1=-1.997743 → **217.5 Hz** (after 7.4 semitone correction)
  - Current JSON (`talking_hedz_extracted.json`): Q=100% M=100% Stage 0 = **1371.3 Hz** (6x wrong!)
  - Reference IR shows F1 at **218 Hz** — matches Cheat Engine, not extracted JSON

  **Root cause:** The 17x17x3 grid was generated from wrong source data, not the validated Cheat Engine captures.

  **Fix required:** Regenerate `talking_hedz_extracted.json` from raw a1/r coefficients in `talking_hedz_complete.json`, applying:
  1. Proper Hz decoding: `freq = arccos(-a1/(2*r)) * sr / (2*pi)`
  2. 7.4 semitone tuning correction: `freq_corrected = freq * 2^(-7.4/12)`
  3. Grid interpolation for full 17x17 coverage (complete.json only has sparse morph points)
