# TRENCH Session Handoff - 2026-01-28

## Current State: Level Stability Achieved

**M0_Q100 Grade: B+** (7.72 dB spectral error, 0.27 dB level error)
**M100_Q100 Grade: B+** (7.17 dB spectral error, 0.30 dB level error)
**Level Stability: A+** (0.00 dB range at endpoints, ~1 dB across sweep)
**Build:** Clean (no warnings)

---

## Ralph Loop Iteration 12: Unified Gains + Level Compensation

### Problem Discovered

Previous iteration (per-stage morph-interpolated gains) created **37+ dB level swings** across the morph range, while X3 only has 0.6 dB variation. This made the plugin unusable.

### Root Cause

M0 and M100 endpoints were optimized independently for spectral shape:
- M0 optimal gains: [78.76, 55.24, 41.88, 70.21] dB
- M100 optimal gains: [60.0, 41.74, 33.05, 38.90] dB

When interpolated, these wildly different values caused unstable output levels.

### Solution: Unified Gains + Linear Compensation

1. **Unified gains** - same for all morph positions
2. **Interpolated offsets** - different for M0 vs M100 to shape spectrum
3. **Linear level compensation** - applied post-filter to match X3 levels

### Optimized Parameters

```cpp
// Unified gains (same for all morph positions)
static constexpr double UNIFIED_GAINS_DB[5] = {
    31.87, 30.91, 33.11, 30.54, 0.0
};

// M0 offsets (Hz)
static constexpr double M0_OFFSETS[5] = {
    140.3, 30.7, 18.4, 23.6, 0.0
};

// M100 offsets (Hz)
static constexpr double M100_OFFSETS[5] = {
    67.4, 138.4, 51.0, 196.9, 0.0
};

// Level compensation formula (applied in processBlock)
double compensationDB = 9.43 - 9.70 * morph;
double compensationLinear = pow(10.0, compensationDB / 20.0);
```

### Results

| Metric | Before (Iter 11) | After (Iter 12) | Target |
|--------|------------------|-----------------|--------|
| Level Range (endpoints) | 37+ dB | **0.00 dB** | 0.57 dB |
| Full Sweep Variation | Unstable | **~1 dB** | ~1 dB |
| M0 Level Error | N/A | **0.27 dB** | <1 dB |
| M100 Level Error | N/A | **0.30 dB** | <1 dB |
| M0 Spectral Error | 5.22 dB | 7.72 dB | <5 dB |
| M100 Spectral Error | 5.89 dB | 7.17 dB | <5 dB |

### Trade-off Analysis

- **Spectral-only optimization:** 5.5 dB error, 37 dB level instability
- **Unified gains + compensation:** 7.4 dB error, 0 dB level instability

Accepted ~2 dB worse spectral error in exchange for stable, usable output levels.

---

## What's Working

- [x] VST3 builds and loads in DAWs
- [x] 7-stage cascade processing
- [x] Polar coefficient decode (a1, r → freq, Q)
- [x] Q scaling (Q_SCALE = 0.08)
- [x] RBJ Peaking EQ for flag=1 stages
- [x] RBJ Lowpass for flag=0 stages
- [x] Morph-interpolated frequency offsets
- [x] Unified per-stage gains
- [x] **Level compensation curve** (NEW!)

---

## Current Error: 7.44 dB average

### Remaining Gap Analysis

To improve from 7.44 dB → 1:1, potential approaches:

1. **Numerator zeros (c1, c2):** NotebookLM revealed transfer function has feedforward zeros:
   ```
   H(z) = c0 * (1 + c1*z^-1 + c2*z^-2) / (1 + a1*z^-1 + a2*z^-2)
   ```
   We're only using denominator (poles). Adding zeros could improve shape.

2. **Memory capture of full coefficients:** Find c0, c1, c2 addresses in X3 and capture complete coefficient sets.

3. **Different topology per stage:** Some stages might use different filter types (bandpass vs peaking).

4. **Q knob interaction:** Current Q_SCALE = 0.08 is constant. X3 might vary this.

---

## Key Files

| File | Purpose |
|------|---------|
| `Source/PluginProcessor.cpp` | Main DSP with unified gains + compensation |
| `tools/verify_unified_solution.py` | Validates current implementation |
| `tools/optimize_unified_gains.py` | Joint optimization for unified gains |
| `tools/test_unified_morph.py` | Tests morph sweep stability |
| `tools/calculate_compensation_curve.py` | Derives compensation formula |
| `validation/*.wav` | X3 reference audio |

---

## Build Commands

```bash
# Build VST3 and Standalone
./build.bat

# Verify current implementation
python tools/verify_unified_solution.py

# Test morph sweep
python tools/test_unified_morph.py
```

---

## Session Summary

**Problem solved:** Fixed 37 dB level instability by using unified gains with linear compensation.

**Trade-off accepted:** Spectral error increased from 5.5 dB to 7.4 dB, but output is now stable and usable.

**Key insight:** Separate endpoint optimization doesn't work for interpolated systems - must optimize for the whole morph range together.

**Next focus:** Investigate numerator zeros (c1, c2) to improve spectral match without sacrificing level stability.

**Build status:** VST3 installed at `C:\Program Files\Common Files\VST3\TRENCH.vst3`
