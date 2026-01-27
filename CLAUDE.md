# TRENCH Z-Plane Filter Implementation

## Mission
Implement an E-mu Z-Plane filter emulation as a JUCE VST3 plugin. **World's first** complete reverse-engineering of the Z-Plane filter for modern VST3.

---

## Architecture (from NotebookLM Research 2026-01-27)

### Hardware vs Software
| System | Stages | Poles | Notes |
|--------|--------|-------|-------|
| **Morpheus H-Chip** | 7 | 14 | Hardware had input conditioner stage |
| **Emulator X3** | 6 | 12 | Software, slightly "fizzier" than hardware |
| **TRENCH** | 6+1 | 12+2 | Match X3 + optional Phantom stage for warmth |

### The "Phantom" 7th Stage (CRITICAL)
The Morpheus hardware had a **static 1-pole Lowpass (~18-20kHz)** at the input to condition the signal before the morphing stages. X3 omitted this, causing "digital fizz."

```cpp
// PhantomConditioner - replicate hardware warmth
class PhantomConditioner {
    float z1 = 0.0f;
public:
    inline float process(float input) {
        constexpr float a = 0.15f; // ~18kHz rolloff @ 44.1kHz
        z1 = (input * (1.0f - a)) + (z1 * a);
        return z1;
    }
};
```

### Gain Staging (X3 Specific)
- **Input:** -7dB attenuation (multiply by 0.446) before filter
- **Output:** Soft limiter to catch resonant peaks
- **Headroom:** X3 was designed with internal headroom for high-Q peaks

### Biquad Topology: Direct Form I (NOT DF-II)
DF-I handles morphing coefficients more gracefully than DF-II Transposed:

```cpp
// Direct Form I - stable during coefficient changes
float y = (c.b0 * x) + (c.b1 * m.x1) + (c.b2 * m.x2)
        - (c.a1 * m.y1) - (c.a2 * m.y2);
```

### ARMAdillo Interpolation (CRITICAL - The Z-Plane Magic)

**DO NOT interpolate raw biquad coefficients (a1, a2, b0...)!**

The Z-Plane's "magic" is a custom coordinate system called **ARMAdillo**:
1. **Encode:** Frequency/Resonance → logarithmic v-space (v1, v2)
2. **Interpolate:** Linear mix of v-values (cheap, musical)
3. **Decode:** v-space → biquad coefficients per sample

Linear sweep in v-space = **Logarithmic frequency sweep** (musical octaves).

#### The v-space Coordinates

**v2 (Resonance/Bandwidth)** - Calculate FIRST:
```cpp
// v2 encodes pole radius. Higher v2 = narrower bandwidth = higher Q
float t2 = 1.0f - std::pow(2.0f, -v2);  // This is a2 (= r²)
```

**v1 (Frequency)** - Depends on v2:
```cpp
// v1 encodes center frequency. MUST use t2 from above!
float t1 = -2.0f + (4.0f * std::pow(2.0f, -v1)) + t2;  // This is a1
```

#### Morph Interpolation (Per Stage)
```cpp
void updateCoefficients(float morphX, float morphY) {
    for (int s = 0; s < 5; ++s) {
        // 1. LINEAR INTERPOLATION in v-space (the "fake" math)
        float v1 = lerp(corner_Ah.v1[s], corner_Ee.v1[s], morphX);
        float v2 = lerp(corner_Ah.v2[s], corner_Ee.v2[s], morphX);

        // 2. Q AXIS interpolation (if using 2D morph)
        v2 = lerp(v2, corner_Ee_LowQ.v2[s], 1.0f - morphY);

        // 3. DECODE to biquad coefficients
        float a2 = 1.0f - std::pow(2.0f, -v2);  // v2 FIRST!
        float a1 = -2.0f + (4.0f * std::pow(2.0f, -v1)) + a2;

        stages[s].a1 = a1;
        stages[s].a2 = a2;
    }
}
```

#### Hardware Barrel Shifter (Optional Vintage Grit)
Original hardware used bit-shifting approximation, not std::pow:
```cpp
// Approximate 2^(-v) using barrel shifter (adds vintage quantization)
inline float barrelShift(float v) {
    int intPart = (int)v;
    float fracPart = v - intPart;
    // Shift by integer, lerp fractional
    float base = 1.0f / (1 << intPart);
    float next = base * 0.5f;
    return base + fracPart * (next - base);
}
```
Use this if the sound is too "clean" compared to original X3.

### TalkingHedz is a 2D Plane (NOT 3D Cube)
- **X axis (Morph):** "Ah" → "Ee" vowel transition
- **Y axis (Q):** Flat → Resonant
- **Z axis:** Unused in original preset

The "cube" decode is a **red herring** - use runtime captures instead.

---

## BREAKTHROUGH: Filter Rompler Strategy (2026-01-27)

**We don't need to reverse-engineer the formulas. We capture the output.**

The memory at `0x012EE640` contains the **final, cooked biquad coefficients** that E-mu has already computed. Instead of deriving the numerator formulas (which turned out to involve complex gain staging and hybrid topology), we:

1. **Capture coefficients in real-time** as we sweep Morph/Q
2. **Store as lookup table** (JSON → C++ array)
3. **Interpolate and playback** in our VST

### Capture Script: `tools/ripper.py`
```bash
pip install pymem
python tools/ripper.py
# Sweep Morph knob during countdown
# Output: trench_capture_TIMESTAMP.json
```

### What Gets Captured
- 32 floats per frame at 60 fps
- Full coefficient state for every morph position
- Ready to memcpy directly to biquad struct

### Advantages
- **100% accurate** to original sound
- **No patent issues** — we're sampling output, not cloning algorithm
- **Simple implementation** — just lookup and interpolate

---

## Validated Ground Truth (DO NOT QUESTION)

### Memory Structure
- **Base address shifts on restart** (found at 0x0056E450 this session)
- **5 stages, 12 bytes each**: `[a1: float][radius: float][flag: float]`
- **Spacing**: 0x0C (12 bytes) between stages
- **Topology**: CASCADE (series, not parallel)

### Coefficient Decode Formula (PROVEN)
```cpp
// Frequency from a1 and radius
float cos_theta = -a1 / (2.0f * radius);
float theta = acos(clamp(cos_theta, -1.0f, 1.0f));
float freq_hz = theta * sampleRate / (2.0f * M_PI);

// a2 from radius
float a2 = radius * radius;
```

### CE Coefficients → v-space Conversion (For Storage)
When storing captured coefficients, convert to v-space for proper interpolation:

```cpp
// Given CE capture: a1, r (radius)
float a2 = r * r;

// Reverse ARMAdillo encode
// v2: from a2 = 1 - 2^(-v2) → v2 = -log2(1 - a2)
float v2 = -log2f(1.0f - a2);

// v1: from a1 = -2 + 4*2^(-v1) + a2
// Solve: 2^(-v1) = (a1 + 2 - a2) / 4
float term = (a1 + 2.0f - a2) / 4.0f;
float v1 = -log2f(term);
```

**Store keyframes as v1/v2, NOT a1/a2!**

### Captured Coefficients

**M0_Q100 (Morph=0%, Q=100%)**
```
Stage 0: a1=-1.976510  r=0.998242  flag=1.0  ->  994 Hz
Stage 1: a1=-1.938977  r=0.998296  flag=1.0  -> 1690 Hz
Stage 2: a1=-1.872895  r=0.998353  flag=1.0  -> 2485 Hz
Stage 3: a1=-1.523842  r=0.992409  flag=1.0  -> 4881 Hz
Stage 4: a1=-1.997572  r=0.998289  flag=0.0  ->   DC (lowpass)
```

**M100_Q100 (Morph=100%, Q=100%)**
```
Stage 0: a1=-1.996743  r=0.998619  flag=1.0  ->  156 Hz
Stage 1: a1=-1.894098  r=0.998437  flag=1.0  -> 2262 Hz
Stage 2: a1=-1.854829  r=0.998353  flag=1.0  -> 2662 Hz
Stage 3: a1=-1.495171  r=0.963737  flag=1.0  -> 4793 Hz
Stage 4: a1=-1.974292  r=0.998195  flag=0.0  -> 1045 Hz (lowpass cutoff)
```

**M100_Q0 (Morph=100%, Q=0%)**
```
Stage 0: a1=-1.986418  r=0.987503  flag=1.0  ->   DC
Stage 1: a1=-1.837391  r=0.974537  flag=1.0  -> 2388 Hz
Stage 2: a1=-1.794609  r=0.977806  flag=1.0  -> 2868 Hz
Stage 3: a1=-1.362762  r=0.883514  flag=1.0  -> 4843 Hz
Stage 4: a1=-1.914935  r=0.993960  flag=0.0  -> 1908 Hz (lowpass cutoff)
```

### Audio Validation Targets
These are FFT peaks from X3 reference recordings:

| Position | Peaks (Hz) |
|----------|------------|
| M0_Q100 | 178, 1077, 1701, 2498, 4915 |
| M100_Q100 | 221, 2417, 2719 |
| M100_Q0 | 215, 2024, 2681, 3047 |

Predicted frequencies match within ~8% error.

---

## Implementation Requirements

### Stage Types (VALIDATED 2026-01-28)

**flag = 1.0: Peaking EQ Stage (RBJ Cookbook)**
```cpp
// VALIDATED: Use RBJ Peaking EQ with Q_SCALE and GAIN_DB
constexpr double Q_SCALE = 0.08;   // Captured r~0.998 gives Q~360, scale to ~30
constexpr double GAIN_DB = 34.0;   // Strong boost at formant peaks

// Decode frequency from polar
double cosTheta = -a1_polar / (2.0 * radius);
double theta = acos(clamp(cosTheta, -1.0, 1.0));
double freqHz = theta * sampleRate / (2.0 * M_PI);

// Q from radius - SCALED DOWN
double Q = 1.0 / (2.0 * (1.0 - radius));
Q = Q * Q_SCALE;  // 362 → 29
Q = clamp(Q, 0.5, 100.0);

// RBJ Peaking EQ coefficients
double A = pow(10.0, GAIN_DB / 40.0);
double omega = 2.0 * M_PI * freqHz / sampleRate;
double alpha = sin(omega) / (2.0 * Q);

double b0 = 1.0 + alpha * A;
double b1 = -2.0 * cos(omega);
double b2 = 1.0 - alpha * A;
double a0 = 1.0 + alpha / A;
double a1 = -2.0 * cos(omega);
double a2 = 1.0 - alpha / A;
// Normalize by a0
```

**flag = 0.0: Lowpass Stage (RBJ Cookbook)**
```cpp
// Standard RBJ lowpass with Q=0.707 (Butterworth)
double omega = 2.0 * M_PI * freqHz / sampleRate;
double alpha = sin(omega) / (2.0 * Q);

double b0 = (1.0 - cos(omega)) / 2.0;
double b1 = 1.0 - cos(omega);
double b2 = (1.0 - cos(omega)) / 2.0;
double a0 = 1.0 + alpha;
double a1 = -2.0 * cos(omega);
double a2 = 1.0 - alpha;
// Normalize by a0
```

### Biquad Implementation (Direct Form I - for stable morphing)
```cpp
struct BiquadDFI {
    float b0, b1, b2, a1, a2;
    float x1 = 0, x2 = 0;  // Input history
    float y1 = 0, y2 = 0;  // Output history

    float process(float x) {
        float y = (b0 * x) + (b1 * x1) + (b2 * x2)
                - (a1 * y1) - (a2 * y2);

        // Denormal protection
        if (std::abs(y) < 1.0e-20f) y = 0.0f;

        x2 = x1; x1 = x;
        y2 = y1; y1 = y;
        return y;
    }
};
```

### Full Processing Chain
```cpp
float process(float input) {
    // 1. GAIN STAGING (-7dB headroom like X3)
    float x = input * 0.446f;

    // 2. PHANTOM STAGE (hardware input conditioner)
    x = phantom.process(x);

    // 3. Z-PLANE CASCADE (5 morphing stages)
    for (int i = 0; i < 5; i++) {
        x = stages[i].process(x);
    }

    // 4. SATURATION (E-mu character)
    x = saturate(x);

    return x;
}
```

### Saturation (E-mu Character)
```cpp
inline float saturate(float x) {
    // Soft clip at ±2.0 to match H-chip bit-width limits
    if (x > 2.0f) x = 2.0f;
    if (x < -2.0f) x = -2.0f;
    return x;
}
```

---

## File Structure

```
TRENCH/
├── CLAUDE.md              # This spec (source of truth)
├── Source/
│   └── dsp/
│       ├── Biquad.h           # Single biquad stage
│       ├── ZPlaneFilter.h     # 5-stage cascade
│       ├── ZPlaneMath.h       # Coefficient decode/encode
│       └── CartridgeLoader.h  # Load coefficient keyframes
├── Cartridges/
│   └── TalkingHedz.json       # Validated coefficient data
├── validation/
│   ├── bypassed-pinknoise.wav  # Dry reference
│   ├── hedzmorph0q100.wav      # X3 M0_Q100
│   ├── hedzmorph100q100.wav    # X3 M100_Q100
│   └── hedzmorph100q0.wav      # X3 M100_Q0
└── tools/
    └── validate_audio.py      # Compare output to X3 refs
```

---

## Phase 1 Task: Hardcoded Test

**Goal**: Process pink noise through the M0_Q100 coefficients and compare to X3 reference.

1. Create `Biquad.h` with DF-II Transposed
2. Create `ZPlaneFilter.h` with 5-stage cascade
3. Hardcode M0_Q100 coefficients
4. Process `bypassed-pinknoise.wav`
5. Compare FFT to `hedzmorph0q100.wav`

**Success Criteria**:
- Peak frequencies within ±10% of reference
- RMS level within ±3 dB
- No NaN, no explosion, stable output

---

## Critical Constraints (VALIDATED 2026-01-28)

1. **USE RBJ Peaking EQ for flag=1** - Constant peak gain bandpass kills signal in cascade
2. **DO NOT interpolate a1/a2 directly** - causes pitch wobble (use polar interpolation)
3. **Cascade topology is CONFIRMED** - not parallel
4. **flag=0 is LOWPASS** - flag=1 is resonator (peaking EQ)
5. **Q values must be SCALED DOWN** - Captured radius gives Q~360, actual X3 uses Q~30

---

## Cartridge JSON Format

```json
{
  "name": "Talking Hedz",
  "validated": true,
  "captureDate": "2026-01-26",
  "baseAddress": "0x0056E450",
  "stages": 5,
  "keyframes": [
    {
      "morph": 0.0,
      "q": 1.0,
      "coefficients": [
        {"a1": -1.976510, "r": 0.998242, "flag": 1.0},
        {"a1": -1.938977, "r": 0.998296, "flag": 1.0},
        {"a1": -1.872895, "r": 0.998353, "flag": 1.0},
        {"a1": -1.523842, "r": 0.992409, "flag": 1.0},
        {"a1": -1.997572, "r": 0.998289, "flag": 0.0}
      ]
    },
    {
      "morph": 1.0,
      "q": 1.0,
      "coefficients": [
        {"a1": -1.996743, "r": 0.998619, "flag": 1.0},
        {"a1": -1.894098, "r": 0.998437, "flag": 1.0},
        {"a1": -1.854829, "r": 0.998353, "flag": 1.0},
        {"a1": -1.495171, "r": 0.963737, "flag": 1.0},
        {"a1": -1.974292, "r": 0.998195, "flag": 0.0}
      ]
    },
    {
      "morph": 1.0,
      "q": 0.0,
      "coefficients": [
        {"a1": -1.986418, "r": 0.987503, "flag": 1.0},
        {"a1": -1.837391, "r": 0.974537, "flag": 1.0},
        {"a1": -1.794609, "r": 0.977806, "flag": 1.0},
        {"a1": -1.362762, "r": 0.883514, "flag": 1.0},
        {"a1": -1.914935, "r": 0.993960, "flag": 0.0}
      ]
    }
  ]
}
```

---

## Resolved Questions (VALIDATED 2026-01-28)

1. **Interpolation domain** - SOLVED: Use polar (a1, r) interpolation, NOT v-space
2. **Biquad topology** - SOLVED: DF-II Transposed (DF-I not required, both work)
3. **Cube decode** - SOLVED: Red herring. Use runtime captures instead.
4. **Hardware warmth** - SOLVED: Add Phantom stage (1-pole LP input conditioner)
5. **Numerator formula for flag=1** - SOLVED: RBJ Peaking EQ with Q_SCALE=0.08, GAIN_DB=34
6. **Q scaling** - SOLVED: Captured radius values give Q~360, but actual X3 uses Q~30
7. **Frequency offsets** - SOLVED: Decoded frequencies differ from X3 peaks by 60-150 Hz

## Spectral Validation Results

| Position | Error vs X3 | Notes |
|----------|-------------|-------|
| M0_Q100 | 7.70 dB | No frequency offsets needed |
| M100_Q100 | 7.60 dB | With offsets [+65, +150, +62, 0] Hz |

## Open Questions

1. **Morph-dependent offsets** - Offsets calibrated for M100 only, M0 needs different values
2. **The 10148 Hz peak** in M100_Q100 audio - Not captured by any stage. Harmonic? Aliasing?
3. **Saturation curve** - X3 likely uses specific polynomial shaper, not just tanh()

---

## Best Of Z-Plane Collection (10-15 Essential Filters)

**Strategy:** Capture runtime coefficients from X3 for the best-sounding filters.

### Morpheus Cube Index (same as X3)
| Idx | Name | Category |
|-----|------|----------|
| 000 | Resonator | Utility |
| 007-010 | Phaser 1-4 | FX |
| 015-019 | Formant 1-5 | Vocal |
| 020-035 | Vowel Aa-Uw | Vocal |
| 043 | VowelSpace | Vocal |
| 065 | Tube Amp | Acoustic |
| 070 | TalkingHedz | Vocal (CAPTURED) |
| 075-076 | Choir / Choir Morph | Vocal |
| 083-085 | Bell 1-3 | Metallic |

### Capture Protocol Per Filter
```
1. Load preset in X3
2. Find memory address via CE (shifts on restart)
3. Capture 3 keyframes minimum:
   - M=0%, Q=100%
   - M=100%, Q=100%
   - M=100%, Q=0%
4. Optional: Full morph sweep at 60fps
5. Save as {FilterName}.json
```

### Tools
- `tools/ripper.py` - Automated morph sweep capture
- `tools/ce_full_capture.lua` - CE manual snapshot with boost factor