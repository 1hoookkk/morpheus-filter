# TRENCH ZPlane Filter Architecture

**Analysis Date:** 2026-01-20

## Overview

TRENCH is the DSP subsystem recreating E-mu's "Talking Hedz" Z-Plane filter from the Emulator X3. The goal is 1:1 behavioral accuracy against reference captures.

**Key Context:** Current implementation uses 5 biquad stages but the H-Chip (14-pole) architecture requires 7 stages. A static 221 Hz body resonance stage was identified in reference audio but is missing from captures.

## Architecture Summary

**Pattern:** Cascaded biquad filter bank with control-rate coefficient interpolation

**Key Characteristics:**
- 5-stage cascade (targeting 7-stage for full H-Chip fidelity)
- 4 bandpass stages + 1 lowpass stage
- Coefficients captured at Q=100% reference, scaled at runtime
- 2D interpolation over Morph x Q dimensions
- Control-rate updates (every 64 samples) with per-sample ramping

## File Structure

**Primary Implementation:**
```
Source/dsp/ZPlaneFilter.h    # Main Trench namespace implementation (477 lines)
```

**Legacy/Alternate (CONFLICTING - needs cleanup):**
```
ZPlaneFilter.h               # Root-level ZPlane namespace (195 lines)
ZPlaneData.h                 # Data structures + biquad computation (127 lines)
ZPlaneLoader.h               # JSON parsing + embedded Talking Hedz (154 lines)
```

**Validation Scripts:**
```
validate_trench.py           # Primary validation with complete Q=0/Q=100 grid
validate_trench_v2.py        # Spec-correct Q scaling formula test
validate_zplane.py           # Older validation (different Q model)
debug_zplane.py              # Coefficient debugging utility
```

**Cartridge Data:**
```
talking_hedz_cartridge.json  # 5 keyframes, Q=100% reference (64 lines)
talking_hedz_complete.json   # Full Cheat Engine captures (142 lines)
talking_hedz_extracted.json  # 17x17x3 grid (WRONG DATA - see GAP-01)
```

## Data Structures

### Stage Data (Captured Coefficients)

```cpp
// Location: Source/dsp/ZPlaneFilter.h:39-43
struct StageRaw {
    float a1;      // Captured a1 coefficient: -2*cos(theta), NOT radius-multiplied
    float radius;  // Pole radius at Q=100% reference (0.94-0.999)
    int   flag;    // Filter type: 1 = EQ/bandpass, 0 = LP/body
};
```

**Critical Formula:** The captured `a1` is normalized (radius=1). At runtime:
```cpp
a1_actual = a1_captured * radius   // PROVEN via Cheat Engine
```

### Biquad Coefficients (Runtime)

```cpp
// Location: Source/dsp/ZPlaneFilter.h:47-51
struct BiquadCoeffs {
    double b0, b1, b2;    // Numerator (zeros)
    double a1, a2;        // Denominator (poles), a0 = 1
};
```

### JSON Cartridge Format

```json
// Location: talking_hedz_cartridge.json
{
  "keyframes": [
    {
      "position": 0.0,    // Morph position 0-1
      "stages": [
        {"a1": -1.974805, "radius": 0.998231, "flag": 1},
        // ... 4 more stages
      ]
    }
  ]
}
```

## Coefficient Computation

### Core Formula (CRITICAL PATH)

```cpp
// Location: Source/dsp/ZPlaneFilter.h:179-205
BiquadCoeffs computeCoeffs(float a1_captured, float radius, int flag) {
    BiquadCoeffs c;

    // CRITICAL: radius multiply
    c.a1 = a1_captured * radius;
    c.a2 = radius * radius;

    if (flag == 1) {
        // Bandpass/EQ numerator: zeros at DC and Nyquist
        const double scale = (1.0 - c.a2) * 0.5;
        c.b0 = scale;
        c.b1 = 0.0;
        c.b2 = -scale;
    } else {
        // Lowpass numerator: zeros at Nyquist only
        double norm = (1.0 + c.a1 + c.a2) * 0.25;
        if (norm <= 0.0) norm = 0.0001;  // Prevent silence at DC
        c.b0 = norm;
        c.b1 = 2.0 * norm;
        c.b2 = norm;
    }
    return c;
}
```

### Q Scaling Formula

```cpp
// Location: Source/dsp/ZPlaneFilter.h:164-172
// Formula: r = r_ref^(Q_ref/Q_new)
float applyQToRadius(float r_ref, float Q_new) {
    if (Q_new <= 0.0f) return 0.5f;

    const float s = Q_REF / Q_new;  // Q_REF = 100.0
    float r = std::exp(std::log(r_ref) * s);

    return clamp(r, 0.5f, min(r_ref, 0.9999f));
}
```

**Q Knob Mapping:** `Q_actual = 0.5 + q_knob * 99.5` (0-1 knob maps to Q=0.5 to Q=100)

### Frequency Extraction

```cpp
// Location: ZPlaneData.h:120-125
// Extract Hz from captured a1 and radius
float getFrequencyHz(float a1, float radius, float sampleRate) {
    float cosTheta = clamp(-a1 / (2.0f * radius), -1.0f, 1.0f);
    float theta = acos(cosTheta);
    return theta * sampleRate / (2 * PI);
}
```

## Processing Architecture

### Cascade Topology

```cpp
// Location: Source/dsp/ZPlaneFilter.h:275-281
// Signal flows through stages sequentially (NOT parallel)
float processSample(float input) {
    double x = input;
    for (int s = 0; s < activeStages; ++s) {
        x = stages[s].process(x);  // Cascade: output->input
    }
    return x;
}
```

### Control-Rate Updates

```cpp
// Location: Source/dsp/ZPlaneFilter.h:266-282
void processBlock(float* data, int numSamples) {
    for (int i = 0; i < numSamples; ++i) {
        // Control-rate update every ctrlInterval samples (default: 64)
        if (sampleCounter >= ctrlInterval) {
            updateControlRate();  // Recompute coefficient targets
            sampleCounter = 0;
        }
        ++sampleCounter;

        // Audio-rate: cascade + coefficient ramping
        // ...
    }
}
```

### Delta-Add Coefficient Ramping

```cpp
// Location: Source/dsp/ZPlaneFilter.h:58-87
struct Ramp {
    double cur, tgt, step;
    int remaining;

    void setTarget(double v, int samples) {
        tgt = v;
        remaining = samples;
        step = (tgt - cur) / samples;
    }

    double tick() {
        if (remaining > 0) {
            cur += step;
            --remaining;
        } else {
            cur = tgt;  // Snap when done
        }
        return cur;
    }
};
```

## Morph Interpolation

### Keyframe Structure

5 keyframes at morph positions: 0%, 25%, 50%, 75%, 100%

```cpp
// Location: Source/dsp/ZPlaneFilter.h:435-460
void updateControlRate() {
    // Map morph (0-1) to keyframe index
    const float xm = morph * 4.0f;  // 5 keys -> 4 intervals
    int mi = floor(xm);
    mi = clamp(mi, 0, 3);
    const float tx = xm - mi;  // Interpolation fraction

    for (int s = 0; s < activeStages; ++s) {
        // Linear interpolation between adjacent keyframes
        const float a1_interp = lerp(raw[mi][s].a1, raw[mi+1][s].a1, tx);
        const float r_ref = lerp(raw[mi][s].radius, raw[mi+1][s].radius, tx);
        const int flag = raw[mi][s].flag;  // Flag doesn't interpolate

        // Apply Q scaling, compute coefficients, set ramp targets
        // ...
    }
}
```

## Validation Approach

### Python Reference Implementation

```python
# Location: validate_trench.py:148-217
class TrenchFilter:
    NUM_STAGES = 5

    def process_sample(self, x):
        y = x
        for i in range(self.NUM_STAGES):
            b0, b1, b2, a1, a2 = self.coeffs[i]
            # Direct Form II Transposed
            out = b0 * y + self.z1[i]
            self.z1[i] = b1 * y - a1 * out + self.z2[i]
            self.z2[i] = b2 * y - a2 * out
            y = out
        return y
```

### Validation Tests

| Test | Script | Purpose |
|------|--------|---------|
| Coefficient formula | `validate_trench.py:test_coefficient_formula()` | Verify `a1 * radius` |
| DC rejection | `validate_trench.py:test_dc_rejection()` | Confirm cascade topology |
| Reference match | `validate_trench.py:test_against_reference()` | Compare vs `hedz - m100q0.wav` |
| Q scaling | `validate_trench_v2.py:test_q_scaling()` | Verify exponential formula |

### Reference Files

| File | Parameters | Use |
|------|------------|-----|
| `hedz - m100q0.wav` | Morph=100%, Q=0% | Primary validation target |
| `morph 100 q 100.wav` | Morph=100%, Q=100% | Sharp resonance test |
| `bypassed in x3.wav` | Bypass | Flat reference |

## Known Issues

### GAP-01: Wrong Data Source (CRITICAL)

**Status:** Blocks validation
**Impact:** `talking_hedz_extracted.json` frequencies are 6x wrong

**Evidence:**
- Cheat Engine raw capture: Stage 0 at M=100% Q=100% = 217 Hz
- Extracted JSON: Same position = 1371 Hz (WRONG)
- Reference audio confirms 218 Hz

**Fix Required:** Regenerate from `talking_hedz_complete.json` using:
1. Hz decode: `freq = arccos(-a1/(2*r)) * sr / (2*pi)`
2. 7.4 semitone tuning correction
3. Grid interpolation

### 5-Stage vs 7-Stage Architecture

**Status:** Design limitation
**Impact:** Missing formant stages

**Background:**
- H-Chip supports up to 6 or 7 stages (14-pole)
- Current captures show only 5 active stages
- Reference audio has peak at ~221 Hz not present in captured stages
- This 221 Hz appears to be a static body resonance

**Investigation Needed:**
- Capture additional stages from X3 memory
- Determine if 221 Hz is Stage 6 or a fixed body model

### Duplicate Header Files

**Files:**
- `ZPlaneFilter.h` (root) vs `Source/dsp/ZPlaneFilter.h`
- Different namespaces: `ZPlane` vs `Trench`

**Resolution:** Consolidate to `Source/dsp/` with single `Trench` namespace

## Stage Characteristics (Captured Data)

### Morph=100%, Q=100% (Reference Point)

| Stage | Type | a1_captured | Radius | Freq (Hz) | Notes |
|-------|------|-------------|--------|-----------|-------|
| 0 | BP | -1.997743 | 0.998719 | ~217 | F1 formant |
| 1 | BP | -1.881333 | 0.998475 | ~2400 | F2 formant |
| 2 | BP | -1.850007 | 0.998353 | ~2707 | F3 formant |
| 3 | BP | -1.476768 | 0.945335 | ~4733 | High formant |
| 4 | LP | -1.939599 | 0.998170 | ~1677 | Body/rolloff |

### Q Effect on Radius

| Q Knob | Q Actual | Typical Radius |
|--------|----------|----------------|
| 0% | 0.5 | 0.87-0.97 (broad) |
| 50% | 50 | 0.96-0.99 |
| 100% | 100 | 0.94-0.999 (sharp) |

## Usage Example

```cpp
#include "Source/dsp/ZPlaneFilter.h"

Trench::ZPlaneFilter filter;
filter.prepare(44100.0, 64);  // Sample rate, control interval

// Set parameters (0-1 range)
filter.setMorph(0.75f);  // 75% morph position
filter.setQ(0.5f);        // 50% Q

// Process audio
float buffer[512];
// ... fill buffer with input ...
filter.processBlock(buffer, 512);
```

## Related Documentation

| Document | Path | Content |
|----------|------|---------|
| Requirements | `.planning/REQUIREMENTS.md` | DSP-01 through DSP-08 |
| UAT Status | `.planning/phases/01-dsp-engine/01-UAT.md` | GAP-01 tracking |
| Data Fix Plan | `.planning/phases/01-dsp-engine/05-data-fix-PLAN.md` | Cartridge regeneration |
| Debug Resolution | `.planning/debug/resolved/zplane-topology-contradiction.md` | CASCADE vs PARALLEL |

---

*TRENCH analysis: 2026-01-20*
