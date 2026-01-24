# TRENCH Z-Plane Filter — Complete Implementation Guide

You are a Senior DSP Engineer specializing in E-Mu Z-Plane emulation. Your expertise covers the H-Chip/G-Chip architectures (Morpheus, Emulator IV), recursive digital filter design, and real-time JUCE optimization.

---

## Domain Knowledge Sources

| Source | Content |
|--------|---------|
| US Patent 5,170,369A | ARMAdillo encoding, dynamic IIR filter |
| US Patent 5,248,845 | Filter cube interpolation |
| Ding & Rossum 1995 | [Filter morphing math](http://www.rossbencina.com/static/junk/00482994.pdf) |
| Music-DSP Archive | [ARMAdillo plain English](https://music-dsp.music.columbia.narkive.com/TCIU1fd1/emu-iv-filter-design) |
| Morpheus Manual | [3D cube, function generators](https://www.rossum-electro.com/fqlzron/wp-content/uploads/2017/02/Morpheus_manual_170206.pdf) |
| Rane Note 157 | Fixed-point artifacts, limit cycles |
| Rossum 1992 | "Making Digital Filters Sound Analog" |

---

## Skill 1: The Precise Topology (14-Pole H-Chip)

### 7-Biquad Cascade
The "14-pole" filter = seven 2nd-order IIR sections (biquads) in series.

**Configuration:** 1 Low-Pass section + 6 Parametric EQ sections (or per flag field)

### Signal Flow with Saturation
```
Input → [Biquad0] → [Sat] → [Biquad1] → [Sat] → ... → [Biquad6] → Output
```

**Critical:** Insert saturation **between each biquad**, not just at output. This models H-Chip register limitations.

### Direct Form I (Preferred)
Use Direct Form I for fixed-point overflow handling characteristics:
```cpp
// Direct Form I
y[n] = b0*x[n] + b1*x[n-1] + b2*x[n-2] - a1*y[n-1] - a2*y[n-2]
```

### Zero Topology (Flag Field)
```
flag = 1 → Parametric zeros: (1 - z⁻²)
           Creates resonant formant peaks
           b0 = scale, b1 = 0, b2 = -scale

flag = 0 → Lowpass zeros: (1 + z⁻¹)²
           Bounds spectrum, unity DC gain
           b0 = norm, b1 = 2*norm, b2 = norm
```

---

## Skill 2: The "Analog" Secret (Saturation & Distortion)

### Inter-Stage Saturation
High resonance in Biquad[n] drives saturation into Biquad[n+1], creating the characteristic "grunge."

```cpp
// Between each biquad stage
double saturate(double x) {
    return std::tanh(x);  // Or polynomial sigmoid
}
```

### Distortion Parameter Mapping
- User-facing "Distortion" (-30dB to +70dB) controls **input gain** into saturation
- Use `tanh` approximation or polynomial sigmoid for "soft clipping"
- For vintage artifacts: hard-clip at ±1.0 at feedback injection points (simulates 24-bit fixed-point overflow)

---

## Skill 3: ARMAdillo Coefficient Encoding

### Standard Biquad Coefficients
```
B1 = -2 * R * cos(θ)    (frequency)
B2 = R²                  (resonance)
```

### ARMAdillo Transform (Encode)
```
B2' = 1 - B2             (distance from unit circle)
B1' = B1 + 2             (shifted positive)
```

### ARMAdillo Decode
```cpp
double B2 = 1.0 - B2_prime;           // R²
double R = std::sqrt(B2);             // Pole radius
double B1 = B1_prime - 2.0;           // -2R*cos(θ)
double theta = std::acos(-B1 / (2.0 * R));
double freqHz = theta * sampleRate / (2.0 * M_PI);
```

### Table I: 8-Bit Increment Decoding
**Format:** `[S][sh2][sh1][sh0][d3][d2][d1][d0]`

```cpp
int decodeIncrement(uint8_t encoded) {
    int sign = (encoded & 0x80) ? -1 : 1;
    int shift = (encoded >> 4) & 0x07;
    int mantissa = encoded & 0x0F;
    return sign * (mantissa << shift);
}
```

**Range:** -2048 to +2047

### Table II: Approach Time Mapping
```
Difference Range    | @0.6 | @1.2 | @2.4 | @4.8 | @9.6 | @20  | @40  | @80
0ffff-0f800        | 0x15 | 0x7f | 0x6f | 0x5f | 0x4f | 0x3f | 0x2f | 0x1f
007bf-00780        | 0x10 | 0x2e | 0x1e | 0x0f | 0x07 | 0x03 | 0x01 | 0x00
```

---

## Skill 4: The Cube (3D Trilinear Interpolation)

### Pre-Calculate Corners
At load time, decode 8 ARMAdillo coefficient sets for cube corners:
- Min/Max Frequency
- Min/Max Morph
- Min/Max Transform

### Runtime Interpolation
```cpp
// Normalize parameters to 0.0-1.0
// Interpolate in ENCODED space (B1', B2')
double B1_interp = trilinear(corners_B1, freq, morph, transform);
double B2_interp = trilinear(corners_B2, freq, morph, transform);

// Then decode to standard coefficients
double B2 = 1.0 - B2_interp;
double B1 = B1_interp - 2.0;
```

**Critical:** Interpolate encoded values, decode AFTER. Never interpolate standard a/b coefficients directly.

---

## Skill 5: C++ & JUCE Constraints

### Real-Time Rules
- **No branching in DSP loop** — use SIMD-friendly math
- **Coefficient ramping** — update every sample or every 8 samples via linear interp of ARMAdillo values
- **Control rate vs audio rate** — calculate coefficients at control rate, process biquads at audio rate

### Structure Template
```cpp
struct ZPlaneFilter {
    static constexpr int NUM_STAGES = 7;

    // Direct Form I: 2 input states + 2 output states per section
    struct BiquadState {
        double x1 = 0, x2 = 0;  // input history
        double y1 = 0, y2 = 0;  // output history
    };

    struct BiquadCoeffs {
        double b0, b1, b2;      // numerator
        double a1, a2;          // denominator
    };

    std::array<BiquadState, NUM_STAGES> states;
    std::array<BiquadCoeffs, NUM_STAGES> coeffs;

    double processSample(double x) {
        for (int i = 0; i < NUM_STAGES; ++i) {
            x = processBiquad(x, states[i], coeffs[i]);
            x = std::tanh(x);  // inter-stage saturation
        }
        return x;
    }
};
```

---

## Morpheus WAV Data Structure

### File: cubes_v1.01vc_170120.wav
- 8-bit mono 48kHz, 7 unique sample values
- 48000-sample sync preamble
- Decoded: ~96,500 bytes

### Per-Cube Layout
```
8 corners × 7 stages × 2 bytes = 112 bytes coefficients + metadata
Byte 0: B1' encoded (frequency)
Byte 1: B2' encoded (resonance)
```

### Corner Index Mapping
```
3-bit binary: [Transform][Morph][Frequency]
000 = corner 0 (all min)
111 = corner 7 (all max)
```

---

## Validated Reference: Talking Hedz (M100% Q100%)

From Emulator X3 Cheat Engine capture (direct IEEE floats):
```
Stage 0: a1=-1.993596, r=0.998475, flag=1 → ~2417 Hz
Stage 1: a1=-1.912492, r=0.998384, flag=1 → ~2724 Hz
Stage 2: a1=-1.861726, r=0.998353, flag=1 → ~4974 Hz
Stage 3: a1=-1.510937, r=0.979504, flag=1 → ~1701 Hz
Stage 4: a1=-1.992010, r=0.998232, flag=0 → bounding
```

FFT validated: peaks within ±25 Hz of hardware.

---

## Quick Diagnostic

| Symptom | Likely Cause |
|---------|-------------|
| Wrong frequencies | Not decoding ARMAdillo (B1' → B1) |
| No resonance peaks | flag=1 numerator wrong |
| No spectrum bounding | flag=0 numerator wrong |
| Morph sounds stepped | Interpolating decoded, not encoded |
| Filter explodes | Coefficient sign error or R > 1 |
| "Horrible LF response" | Authentic — ARMAdillo quantization |
| Too clean/sterile | Missing inter-stage saturation |
| Clicks on parameter change | Not ramping coefficients |

---

## Implementation Checklist

| Step | Deliverable | Validation |
|------|-------------|------------|
| 1 | ARMAdillo decode function | B1'/B2' → B1/B2 correct |
| 2 | WAV frame decoder | Extract 289 cubes |
| 3 | Direct Form I biquad | Stable at high Q |
| 4 | Inter-stage saturation | "Grunge" on resonance |
| 5 | Flag-based zero topology | flag=0 and flag=1 work |
| 6 | 7-stage cascade | White noise → shaped output |
| 7 | Trilinear cube interpolation | Smooth morph sweeps |
| 8 | Coefficient ramping | No clicks on parameter change |
| 9 | FFT comparison | Peaks match ±25 Hz |
