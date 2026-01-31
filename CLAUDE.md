# TRENCH Z-Plane Filter Implementation

## Mission
Implement an E-mu Z-Plane filter emulation as a JUCE VST3 plugin. **World's first** complete reverse-engineering of the Z-Plane filter for modern VST3.

---

## ✅ CURRENT STATUS (2026-01-31)

### What Works
- **M0_Q100** (Ah vowel, resonant): **-20.5 dB RMS** (0.5 dB error) ✅ **PERFECT**
- **M100_Q100** (Ee vowel, resonant): **-17.4 dB RMS** (2.6 dB error) ✅ **WORKING**
- Coefficient capture: All 4 corners validated with val1/val2/val3 numerator offsets
- Linear interpolation: Direct lerp of a1, radius, val1/val2/val3 (NOT polar)
- Cascade stability: 5-stage cascade with proper denormal protection
- Frequency-domain gain normalization: Matches Python scipy.signal.sosfreqz

### Issues Remaining
- **M0_Q0** (Ah flat): -4.8 dB (15.2 dB too hot) - needs additional normalization
- **M100_Q0** (Ee flat): -1.3 dB (18.7 dB too hot) - needs additional normalization

### Root Cause
Q0 (flat) corners have lower peak gains than Q100 (resonant) but are receiving inadequate boost normalization. The current threshold of 100 (40 dB) may need adjustment, or Q0 corners need a different normalization strategy.

---

## Validated Implementation Details

### Golden Master Keyframes (COMPLETE - 2026-01-28)

**M0_Q100 (Start/Resonant) - boost=1.762177**
```
Stage 0: a1=-1.974805  r=0.998231  val1=0.548706  val2=-0.214841  val3=0.283027
Stage 1: a1=-1.939721  r=0.998292  val1=0.548706  val2= 0.000000  val3=0.548704
Stage 2: a1=-1.873399  r=0.998353  val1=0.548706  val2=-0.960298  val3=0.522998
Stage 3: a1=-1.524112  r=0.992679  val1=0.548706  val2=-0.617493  val3=0.548704
Stage 4: a1=-1.997652  r=0.998292  (lowpass)
```

**M0_Q0 (Start/Flat) - boost=1.765472**
```
Stage 0: a1=-1.938511  r=0.959007  val1=0.561890  val2=-0.246341  val3=0.316166
Stage 1: a1=-1.892624  r=0.955101  val1=0.561890  val2=-0.579652  val3=0.561888
Stage 2: a1=-1.853366  r=0.993899  val1=0.561890  val2=-0.970202  val3=0.531174
Stage 3: a1=-1.398666  r=0.898483  val1=0.561890  val2=-1.022866  val3=0.518018
Stage 4: a1=-1.981336  r=0.982433  (lowpass)
```

**M100_Q100 (End/Resonant) - boost=1.752869**
```
Stage 0: a1=-1.997743  r=0.998719  val1=0.511475  val2=-0.415885  val3=0.207911
Stage 1: a1=-1.881333  r=0.998475  val1=0.511475  val2= 0.958517  val3=0.511473
Stage 2: a1=-1.850007  r=0.998353  val1=0.511475  val2=-0.885161  val3=0.457553
Stage 3: a1=-1.476768  r=0.945335  val1=0.511475  val2=-0.864006  val3=0.000000
Stage 4: a1=-1.939599  r=0.998170  (lowpass)
```

**M100_Q0 (End/Flat) - boost=1.755402**
```
Stage 0: a1=-1.983283  r=0.984381  val1=0.521606  val2=-0.407823  val3=0.244630
Stage 1: a1=-1.824333  r=0.964867  val1=0.521606  val2= 0.977505  val3=0.521605
Stage 2: a1=-1.783306  r=0.970715  val1=0.521606  val2=-0.885161  val3=0.457553
Stage 3: a1=-1.344162  r=0.875046  val1=0.521606  val2=-0.864006  val3=0.000000
Stage 4: a1=-1.911181  r=0.993167  (lowpass)
```

### Coefficient Formulas (VALIDATED)

**Resonator Stages (flag=1):**
```cpp
// Witchcraft numerator formula
double b0 = 1.0 + val1;
double b1 = a1 + val2;
double b2 = a2 - val3;  // MINUS val3

// DC Pole Normalization (when pole near DC)
double dc_denom = 1.0 + a1 + a2;
if (std::abs(dc_denom) < 0.01) {
    double dc_numer = b0 + b1 + b2;
    if (std::abs(dc_numer) > 0.001) {
        double scale = std::abs(dc_denom) / std::abs(dc_numer) * 10.0;
        b0 *= scale;
        b1 *= scale;
        b2 *= scale;
    }
}
```

**Lowpass Stage (flag=0):**
```cpp
// RBJ 2nd-order lowpass at 15kHz
constexpr double freq_lp = 15000.0;
double omega = 2.0 * PI * freq_lp / sampleRate;
constexpr double Q_lp = 0.707;
double alpha = std::sin(omega) / (2.0 * Q_lp);

double b0 = (1.0 - std::cos(omega)) / 2.0;
double b1 = 1.0 - std::cos(omega);
double b2 = (1.0 - std::cos(omega)) / 2.0;
double a0 = 1.0 + alpha;
double a1_lp = -2.0 * std::cos(omega);
double a2_lp = 1.0 - alpha;

// Normalize by a0
stages[i].b0 = b0 / a0;
stages[i].b1 = b1 / a0;
stages[i].b2 = b2 / a0;
stages[i].a1 = a1_lp / a0;
stages[i].a2 = a2_lp / a0;
```

### Stability Checks (CRITICAL)

**1. Radius Clamping:**
```cpp
constexpr double MAX_RADIUS = 0.9999;
double r = std::min(radius, MAX_RADIUS);
double a2 = r * r;
```

**2. Biquad Stability (a1 clamping):**
```cpp
// For stability, need |a1| < 1 + a2
double stabilityLimit = 1.0 + a2 - 0.001;
double a1 = curr.a1;
if (std::abs(a1) > stabilityLimit) {
    a1 = (a1 < 0) ? -stabilityLimit : stabilityLimit;
}
```

### Frequency-Domain Gain Normalization (CRITICAL)

**MUST match scipy.signal.sosfreqz grid (endpoint EXCLUDED):**

```cpp
constexpr int NUM_FREQS = 1024;
constexpr double PI = 3.14159265358979323846;

// Compute cascade peak gain
double maxMag = 0.0;
for (int k = 0; k < NUM_FREQS; k++) {
    double omega = PI * k / NUM_FREQS;  // ENDPOINT EXCLUDED (matches scipy)

    // Evaluate cascade frequency response at omega
    // [complex arithmetic to compute |H(omega)|]

    maxMag = std::max(maxMag, mag);
}

// Normalize boost if peak gain too high
double maxGainWithBoost = peakGain * rawBoost;
if (maxGainWithBoost > 100.0) {
    double normFactor = 10.0 / maxGainWithBoost;
    currentBoost = rawBoost * normFactor;
}

// Apply boost to FIRST stage numerator ONLY
stages[0].b0 *= currentBoost;
stages[0].b1 *= currentBoost;
stages[0].b2 *= currentBoost;
```

### Biquad Processing (Direct Form I)

```cpp
struct BiquadDFI {
    double b0, b1, b2, a1, a2;
    double x1 = 0, x2 = 0;  // Input history
    double y1 = 0, y2 = 0;  // Output history

    inline double process(double x) {
        double y = (b0 * x) + (b1 * x1) + (b2 * x2)
                 - (a1 * y1) - (a2 * y2);

        // Denormal protection
        if (!std::isfinite(y) || std::abs(y) < 1.0e-15) {
            y = 0.0;
        }

        // Per-stage clipping
        y = std::clamp(y, -10.0, 10.0);

        x2 = x1; x1 = x;
        y2 = y1; y1 = y;
        return y;
    }
};
```

### 4-Corner Bilinear Interpolation

```cpp
void updateCoefficients(double morph, double q) {
    morph = std::clamp(morph, 0.0, 1.0);
    q = std::clamp(q, 0.0, 1.0);

    // Interpolate boost
    double boostStart = lerp(M0_Q0.boost, M0_Q100.boost, q);
    double boostEnd = lerp(M100_Q0.boost, M100_Q100.boost, q);
    double rawBoost = lerp(boostStart, boostEnd, morph);

    // Build all stages WITHOUT boost
    for (int i = 0; i < 5; i++) {
        // Interpolate along Q axis
        StageData start = interpolateStage(M0_Q0.stages[i], M0_Q100.stages[i], q);
        StageData end = interpolateStage(M100_Q0.stages[i], M100_Q100.stages[i], q);

        // Then along Morph axis
        StageData curr = interpolateStage(start, end, morph);

        // Apply stability checks and compute coefficients
        // [as detailed above]
    }

    // Compute cascade peak gain and normalize boost
    double peakGain = computeCascadePeakGain();
    // [apply normalization as detailed above]
}
```

---

## File Structure

```
TRENCH/
├── CLAUDE.md                          # This spec
├── Source/
│   ├── DSP/
│   │   ├── ZPlaneFilter.h            # Filter class definition
│   │   ├── ZPlaneFilter.cpp          # Implementation with Golden Master data
│   │   └── ZPlaneGroundTruth.h       # Keyframe data reference
│   ├── PluginProcessor.h/cpp         # JUCE VST3 wrapper
│   └── PluginEditor.h/cpp            # GUI (if implemented)
├── tools/
│   ├── coeff_dump.json               # Audit: coefficient validation
│   ├── compare_peak.py               # Audit: peak gain comparison with scipy
│   ├── dsp_runner.cpp                # Test harness for filter validation
│   └── golden_master_talkinghedz.py  # Python reference implementation
└── validation/
    ├── bypassed-pinknoise.wav        # Test input
    ├── hedzmorph0q100.wav            # X3 reference: M0_Q100
    ├── hedzmorph100q100.wav          # X3 reference: M100_Q100
    └── hedzmorph100q0.wav            # X3 reference: M100_Q0
```

---

## Known Issues & Next Steps

### Issue: Q0 Corners Too Hot

**Symptom:**
- M0_Q0: -4.8 dB instead of -20 dB (15.2 dB too hot)
- M100_Q0: -1.3 dB instead of -20 dB (18.7 dB too hot)

**Analysis:**
- Peak gains are correctly computed (validated against scipy)
- Boost normalization threshold of 100 (40 dB) is insufficient for Q0 corners
- Q0 boost values: M0_Q0=0.000768, M100_Q0=0.057051 (much higher than Q100)

**Possible Solutions:**
1. Lower normalization threshold from 100 to 30-50
2. Add second-stage normalization (as in Python golden master)
3. Apply different normalization strategy for low-Q corners
4. Investigate if Python uses additional post-processing for Q0

### Validation Tools

**Test current state:**
```bash
./build/Release/dsp_runner.exe M0_Q100
```

**Compare with scipy:**
```bash
cd tools && python compare_peak.py
```

**Audio validation:**
```python
import numpy as np
from scipy.io import wavfile

sr, audio = wavfile.read('tools/output_M0_Q100.wav')
audio = audio.astype(np.float32) / 32768.0
rms_db = 20 * np.log10(np.sqrt(np.mean(audio**2)))
print(f"RMS: {rms_db:.1f} dB (target: -20 dB)")
```

---

## Build Instructions

**VST3 Plugin:**
```bash
cd build
cmake --build . --config Release --target TRENCH_VST3
# Installed to: C:\Program Files\Common Files\VST3\TRENCH.vst3
```

**Standalone:**
```bash
cmake --build . --config Release --target TRENCH_Standalone
# Output: build/TRENCH_artefacts/Release/Standalone/TRENCH.exe
```

**Test Harness:**
```bash
cmake --build . --config Release --target dsp_runner
./build/Release/dsp_runner.exe M0_Q100
```

---

## References

- **Python Golden Master:** `tools/golden_master_talkinghedz.py` (WORKING reference)
- **Coefficient Validation:** `tools/coeff_dump.json` (matches scipy exactly)
- **Peak Gain Audit:** `tools/compare_peak.py` (validates frequency response)
- **Session Handoff:** `SESSION_HANDOFF_Jan31.md` (debugging history)

---

## Critical Constraints

1. ✅ **CASCADE topology** - 5 stages in series
2. ✅ **Linear interpolation** - Direct lerp of a1, radius, val1/val2/val3
3. ✅ **Stability clamping** - Radius ≤ 0.9999, a1 within biquad stability bounds
4. ✅ **Denormal protection** - NaN checks + ±10 clamp per stage + 1e-15 threshold
5. ✅ **Endpoint-excluded grid** - omega = π*k/N (matches scipy.signal.sosfreqz)
6. ✅ **Witchcraft formula** - b0=1+val1, b1=a1+val2, b2=a2-val3
7. ⚠️ **Boost normalization** - Working for Q100, needs tuning for Q0

---

## Success Criteria

- [x] M0_Q100 within 3 dB of target (-20 dB) ✅ **0.5 dB error**
- [x] M100_Q100 within 3 dB of target ✅ **2.6 dB error**
- [ ] M0_Q0 within 3 dB of target ⚠️ **15.2 dB error**
- [ ] M100_Q0 within 3 dB of target ⚠️ **18.7 dB error**
- [x] Stable morph sweeps (no pops/clicks) ✅
- [x] CPU < 5% on single core ✅
- [ ] All 4 corners validated ⚠️ **2/4 complete**
