---
status: investigating
trigger: "Previous debug session incorrectly concluded PARALLEL topology. NotebookLM research confirms CASCADE topology is correct. The 4.0 dB validation error must have another cause - likely the reference file is invalid."
created: 2026-01-18T12:00:00Z
updated: 2026-01-18T16:00:00Z
---

## Current Focus

hypothesis: CONFIRMED - HYBRID topology achieves correct response RANGE but frequency alignment differs from reference.
test: HYBRID (cascade BP stages 0-3, sum LP stage 4 in parallel) with lp_mix=0.1
expecting: Response range matches, but RMS error remains ~13 dB due to frequency mismatch
next_action: Document findings and propose next steps

## Symptoms

expected: CASCADE topology should match E-mu X3 behavior. NotebookLM confirms:
- Advanced Applications Guide: "1 -> 2 -> 3 -> 4 -> 5 -> 6" cascade
- Patent 5,170,369: "cascade form... preferred embodiment, parallel has many disadvantages"
- Proteus X Manual: "sections are cascaded"
- Q=0% does NOT produce flat response - only "No Filter" or "Null Cube" does

actual: CASCADE implementation produces 27+ dB error against reference file hedz - m100q0.wav. Previous session incorrectly switched to PARALLEL which reduced error to 4.0 dB, but this contradicts ALL E-mu documentation.

errors: 27+ dB error with correct CASCADE topology vs reference file

reproduction: Run validation comparing CASCADE implementation against hedz - m100q0.wav

timeline: Previous debug session made incorrect conclusion. Reverting to CASCADE and investigating reference file validity.

## Eliminated

- hypothesis: Reference file is Null Cube or flat/bypass
  evidence: CORRECTED analysis shows 34.6 dB range (MODERATE filtering), peaks at 221 Hz, 2019 Hz, 2686 Hz - this IS filtered audio, not flat/bypass
  timestamp: 2026-01-18T12:30:00Z

- hypothesis: Reference file is invalid/unusable
  evidence: File IS valid Talking Hedz capture. Previous "0.0 dB range" finding was WRONG - FFT was computed on silent portion (samples 0-8191 are zeros, signal starts at sample 8528)
  timestamp: 2026-01-18T12:30:00Z

## Evidence

- timestamp: 2026-01-18T15:00:00Z
  checked: Multiple topology approaches for M=100%, Q=0%
  found: |
    KEY FINDING: HYBRID topology achieves correct response RANGE but wrong frequency alignment.

    Approaches tested:
    1. Pure CASCADE with bandpass formula: 80-100+ dB range (too much)
    2. Peaking EQ formula: 15-84 dB range (varies with Q blend)
    3. HYBRID (cascade BP + parallel LP): 34.2 dB range with lp_mix=0.1

    HYBRID with lp_mix=0.1 gives:
    - Response range: 34.2 dB (reference: 34.6 dB) - MATCHES!
    - RMS Error: 12.99 dB (still above 6 dB tolerance)
    - Per-band: we boost 300-3000 Hz (+15 dB), attenuate bass (-8 dB) and high (-11 dB)

    The frequency mismatch suggests either:
    - Reference was captured at different morph position
    - Our formant frequencies are shifted vs X3

    Reference has peaks at ~221 Hz, 2019 Hz, 2686 Hz
    Our M=100% stages: 0 Hz (bypass), 2400 Hz, 2707 Hz, 4733 Hz
    Note: At M=75%, Stage 0 would be ~198 Hz (close to 221 Hz)
  implication: Response shape (range) can be achieved with hybrid topology. Frequency alignment needs investigation.

- timestamp: 2026-01-18T14:00:00Z
  checked: Q scaling formula against captured X3 data from Section 5.1 of spec
  found: |
    CRITICAL FINDING - Q mapping is completely wrong!

    Captured X3 data at Morph 50% (Stage 3):
    - Q=0%: radius=0.886765
    - Q=50%: radius=0.951195
    - Q=100%: radius=0.979504 (reference)

    Back-calculating Q_actual values from r = r_ref^(100/Q):
    - Q knob 0% -> Q_actual = 17.26% (NOT 0.5%!)
    - Q knob 50% -> Q_actual = 41.43% (NOT 50.25%!)
    - Q knob 100% -> Q_actual = 100%

    Current code produces at Q_knob=0%:
    - Q_actual = 0.5 (from linear mapping)
    - s = 100/0.5 = 200
    - r = 0.979504^200 = 0.016 -> clamped to 0.5

    X3 actually uses at Q_knob=0%:
    - Q_actual = 17.26 (from exponential mapping)
    - s = 100/17.26 = 5.8
    - r = 0.979504^5.8 = 0.8867

    The 0.5 vs 0.8867 radius difference is HUGE. With r=0.5, bandpass stages are
    extremely overdamped, causing massive compounded rolloff in cascade topology.
    With r=0.8867, stages have moderate resonance producing ~35 dB range.

    FIX REQUIRED:
    1. Change Q_MIN from 0.5 to 17.0
    2. Use exponential mapping: Q_actual = Q_MIN * (Q_REF/Q_MIN)^q_knob
  implication: This explains the 72.3 dB vs 34.6 dB discrepancy. The bug is in Q mapping, not cascade topology.

- timestamp: 2026-01-18T12:00:00Z
  checked: SESSION_SUMMARY_2026-01-18.md
  found: NotebookLM research CONFIRMS CASCADE topology from multiple E-mu sources (patent, manuals). Also notes reference file "may not be a true IR" with "significant pre-peak energy" and "peak at 13.5% not 0%"
  implication: Previous debug session conclusion (PARALLEL) was wrong. The 4.0 dB error was achieved by fitting to an invalid reference file.

- timestamp: 2026-01-18T12:01:00Z
  checked: Current state of files
  found: ZPLANE_RECREATION_SPEC_X3.md, ZPlaneFilter.h, validate_zplane.py, talking_hedz_cartridge.json all modified to PARALLEL topology with mix_gains
  implication: All files need to be reverted to CASCADE topology

- timestamp: 2026-01-18T12:02:00Z
  checked: Reference files in directory
  found: Multiple hedz files exist: "hedz - m100q0.wav", "hedz - 5050.wav", "hedz - 100100.wav", "hedz - 0 0.wav", "hedz - q 100 m 0.wav"
  implication: Can compare Q=0% file against other captures to see if response characteristics differ as expected

- timestamp: 2026-01-18T12:30:00Z
  checked: Corrected frequency analysis of reference files (analyzing ACTUAL signal, not silent portions)
  found: |
    CRITICAL FINDING: Reference files have SILENCE at start, signal begins mid-file:
    - hedz - m100q0.wav: Signal starts at sample 8528 (13.5%), dB range = 34.6 dB (MODERATE)
    - hedz - 100100.wav: Signal starts at sample 16183 (50.7%), dB range = 55.2 dB (STRONG)
    - hedz - 5050.wav: Signal starts at sample 7349 (60.7%), dB range = 64.9 dB (STRONG)

    This COMPLETELY contradicts previous "flat response" finding which was based on FFT of silent portion!

    Q comparison:
    - Q=0%: 34.6 dB range (LESS resonance) - CORRECT per E-mu docs
    - Q=100%: 55.2 dB range (MORE resonance) - CORRECT per E-mu docs

    The reference file IS VALID. Previous validation failure was due to:
    1. Incorrect FFT analysis (computed on silent samples)
    2. Fitting arbitrary parallel gains to "improve" error
  implication: Must revert to CASCADE topology and fix validation script to properly align signals before comparison

- timestamp: 2026-01-18T13:00:00Z
  checked: CASCADE validation with proper signal alignment
  found: |
    CASCADE validation results (M=100%, Q=0%):
    - Our output: 72.3 dB response range
    - Reference: 34.6 dB response range
    - RMS error: 18.50 dB
    - Per-band analysis shows we're 60+ dB BELOW reference in bass (20-300 Hz)
    - We're 13+ dB ABOVE reference in mid frequencies (1-6 kHz)

    KEY INSIGHT: CASCADE inherently produces steep rolloff from multiplied bandpass filters.
    5 bandpass filters in series each cut bass, compounding the effect.
  implication: Either X3 applies normalization, or some stages are handled differently

- timestamp: 2026-01-18T13:01:00Z
  checked: Coefficient interpretation analysis
  found: |
    Tested two interpretations of captured a1 data:
    1. a1 WITHOUT radius: Stage frequencies = 333, 2400, 2707, 4733, 1677 Hz
    2. a1 WITH radius: Stage frequencies = 37, 2400, 2707, 4733, 1677 Hz

    Interpretation 2 matches spec table better (Stage 0 at ~37 Hz vs "~0 Hz").
    The "ratio swap" coefficient formula is correct for preserving frequency.

    Both interpretations produce ~97 dB CASCADE response range.
  implication: Coefficient formula is likely correct. The issue is CASCADE vs reference discrepancy.

- timestamp: 2026-01-18T13:02:00Z
  checked: Files reverted to CASCADE topology
  found: |
    Reverted:
    - ZPlaneFilter.h: Now uses CASCADE processSample()
    - validate_zplane.py: Now uses process_cascade() with signal alignment
    - talking_hedz_cartridge.json: Removed mix_gains, topology="cascade"
    - ZPLANE_RECREATION_SPEC_X3.md: Updated to CASCADE per E-mu docs
  implication: Code is now correct per documentation. Discrepancy remains open investigation.

## Resolution

root_cause: |
  CONFIRMED - Multiple issues identified:

  1. Q SCALING FORMULA: Original formula with Q_MIN=0.5 was too aggressive
     - Exponential formula r=r_ref^(100/Q) crushed radius to floor at Q=0%
     - Linear formula r_floor+(r_ref-r_floor)*q with floor_ratio=0.905 is better
     - Stability fix needed: recompute a1 from clamped angle (not ratio swap)

  2. NUMERATOR FORMULA: Bandpass formula (zeros at DC) causes bass rejection
     - Peaking EQ formula with gain_factor scaling preserves bass
     - At low Q, reduce peak height but keep frequency shaping

  3. TOPOLOGY: Pure CASCADE creates excessive dynamic range (80+ dB)
     - HYBRID topology (cascade BP + parallel LP) achieves correct range
     - lp_mix=0.1 gives 34.2 dB range (reference: 34.6 dB)

  4. FREQUENCY MISMATCH: Our formants don't match reference
     - Reference has peaks at ~221, 2019, 2686 Hz
     - Our M=100% has peaks at 0 (bypass), 2400, 2707 Hz
     - Either reference was captured at different morph, or coefficients differ

  REMAINING ISSUE: RMS error ~13 dB (target <6 dB) due to frequency mismatch

  ORIGINAL HYPOTHESIS "reference file is invalid": DISPROVED
  - Reference IS valid, shows 34.6 dB filtering at Q=0%
  - The issue is our implementation, not the reference

fix: |
  IMPLEMENTED in validate_zplane.py:
  1. Q scaling: linear radius interpolation with floor_ratio=0.905
  2. Numerator: peaking EQ formula with gain_factor scaling
  3. Topology: HYBRID (cascade BP 0-3, sum LP 4 in parallel with lp_mix=0.1)
  4. Stability: recompute a1 from clamped angle (prevents DC instability)

  RESULTS:
  - Response range: 34.2 dB (reference: 34.6 dB) - MATCHES within 0.4 dB
  - RMS error: 12.99 dB (target: <6 dB) - frequency mismatch

  NOT YET PORTED TO C++:
  - ZPlaneData.h still has Q_MIN=17 and exponential formula
  - ZPlaneFilter.h still has pure cascade topology
  - Need to update C++ with HYBRID approach after frequency issue resolved

verification: |
  HYBRID validation at M=100%, Q=0%:
  - Response range: 34.2 dB (reference: 34.6 dB) - 0.4 dB MATCH
  - RMS Error: 12.99 dB (target: <6 dB) - FREQUENCY MISMATCH
  - Per-band: +15 dB mid (300-3000 Hz), -8 dB bass, -11 dB high
  - Formants at 2400, 2707 Hz vs reference's 2019, 2686 Hz

files_changed:
  - C:\Users\hooki\yup\ZPlaneData.h (Q_MIN=17, stability fix)
  - C:\Users\hooki\yup\ZPlaneFilter.h (exponential Q mapping)
  - C:\Users\hooki\yup\validate_zplane.py (HYBRID topology, peaking EQ formula)

next_steps: |
  1. Investigate frequency mismatch - why formants at 2400 Hz vs 2019 Hz
  2. Consider if reference was captured at different morph position
  3. Try recapturing coefficients from X3 to verify accuracy
  4. Once frequency issue resolved, port HYBRID topology to C++
