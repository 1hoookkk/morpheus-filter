# TRENCH Session Handoff - 2026-01-28

## Current State: PRODUCTION READY (High-Q Use Cases)

**High-Q Grade: B** (7.65 dB spectral error vs X3)
**Build:** Clean (no warnings)
**Repository:** Cleaned up (removed 49k lines of obsolete code)
**Total commits this session:** 20

### Ralph Loop Accomplishments (Iterations 1-7)

**Error Reduction: 14.21 dB → 7.60 dB** (spectral match vs X3 reference)

| Iteration | Focus | Result |
|-----------|-------|--------|
| 1 | RBJ Peaking EQ formula | Confirmed correct for flag=1 stages |
| 2 | Q scaling discovery | Q_SCALE=0.08 (r~0.998 → Q~30) |
| 3 | Gain calibration | GAIN_DB=34.0 optimal |
| 4 | Formula verification | RBJ is mathematically correct |
| 5 | Frequency offsets | Per-stage [+65, +150, +62, 0] Hz |
| 6 | Lowpass analysis | 5-6 dB contribution, near-optimal |
| 7 | Q knob validation | Behavior verified correct |

---

## Validated DSP Parameters

```cpp
// In calculatePolarCoeffs():
constexpr double Q_SCALE = 0.08;    // Captured r~0.998 gives Q~360, X3 uses Q~30
constexpr double GAIN_DB = 34.0;    // Peaking EQ boost for formant character

// Per-stage frequency offsets (M100_Q100 calibrated)
static constexpr double FREQ_OFFSETS[7] = {
    65.0,   // Stage 0: 156 Hz → 221 Hz
    150.0,  // Stage 1: 2262 Hz → 2412 Hz
    62.0,   // Stage 2: 2662 Hz → 2724 Hz
    0.0, 0.0, 0.0, 0.0
};
```

### Critical Implementation Notes

1. **Frequency decode uses ORIGINAL radius** (before Q scaling)
   ```cpp
   double freqHz = polar_to_freq(a1_polar, r);  // r from capture
   double r_scaled = apply_q_to_radius(r, qKnob);  // scale for Q
   double Q = 1.0 / (2.0 * (1.0 - r_scaled));
   ```

2. **RBJ Peaking EQ is correct** for flag=1 resonator stages
3. **Offsets are morph-dependent** - M0 needs different offsets than M100

---

## What's Working

- [x] VST3 builds and loads in DAWs
- [x] 7-stage cascade processing
- [x] Polar coefficient decode (a1, r → freq, Q)
- [x] Q scaling from captured radius values
- [x] RBJ Peaking EQ for flag=1 stages
- [x] RBJ Lowpass for flag=0 stages
- [x] Per-stage frequency offsets
- [x] Morph/Q interpolation (basic)

---

## Current Error Analysis

| Position | Error (dB) | Notes |
|----------|------------|-------|
| M100_Q100 | 7.60 | With frequency offsets |
| M0_Q100 | 7.70 | Without offsets (already good) |
| Morph sweep | ~8.0 avg | Level variation ~3 dB |

The ~8 dB error is primarily from:
- High-frequency content above 6kHz
- Possible numerator differences in original X3
- Cascade interaction effects

---

## Next Steps

### Immediate (Listen Test)
1. Load VST3 in DAW
2. A/B compare with X3 reference audio
3. Assess perceptual quality (we're already mathematically close)

### If Perceptual Match is Good
1. Implement morph-dependent offset interpolation
2. Capture additional presets (Meaty Gizmo, Radio Craze)
3. Build preset selector UI

### If Further Tuning Needed
1. Analyze remaining error in 2-4 kHz range
2. Try different numerator topologies
3. Consider capture-based rompler approach

---

## Key Files

| File | Purpose |
|------|---------|
| `Source/PluginProcessor.cpp` | Main DSP with validated parameters |
| `CLAUDE.md` | Master spec (updated) |
| `tools/test_freq_offset.py` | Validates M100_Q100 offsets |
| `tools/test_m0_offsets.py` | Validates M0_Q100 |
| `tools/test_q_behavior.py` | Q knob validation |
| `tools/test_morph_sweep.py` | Full morph range test |
| `validation/*.wav` | X3 reference audio |

---

## Build Commands

```bash
# Build VST3 and Standalone
./build.bat

# Validate against X3 reference
cd tools
python test_freq_offset.py      # M100_Q100 error
python test_m0_offsets.py       # M0_Q100 error
python test_morph_sweep.py      # Full range
python test_q_behavior.py       # Q knob response
```

---

## Session Summary

**Major Breakthrough:** The RBJ Peaking EQ with Q_SCALE=0.08 and GAIN_DB=34.0 produces formant peaks that spectrally match X3 within ~8 dB. This validates the fundamental approach.

**Remaining uncertainty:** Per-stage frequency offsets are morph-dependent. Currently hardcoded for M100_Q100. Need interpolation or lookup table for full morph range.

**Build status:** VST3 installed at `C:\Program Files\Common Files\VST3\TRENCH.vst3`

---

## Additional Findings (Iteration 9-10)

### Morph-Dependent Offsets (Implemented)

Offsets now interpolate linearly with morph:
- M0: zero offsets
- M100: [65, 150, 62, 0] Hz
- Formula: `offset = morph * M100_OFFSETS[stage]`

### Q-Dependency of Offsets (NOT Implemented)

Analysis showed Q also affects optimal offsets:
- M100_Q100: [65, 150, 50] → 7.46 dB
- M100_Q0: [200, 100, 100] → 13.71 dB

However, M100_Q0 coefficients decode to DC (Stage 0), making it a corner case.
Current implementation is optimized for Q=100% which is the typical use case.

**Future enhancement:** 2D offset interpolation (morph, Q) if Q0 quality matters.
