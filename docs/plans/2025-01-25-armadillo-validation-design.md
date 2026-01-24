# ARMAdillo Coefficient Validation Design

**Date:** 2025-01-25
**Project:** TRENCH Z-Plane Filter
**Phase:** Validation-First Implementation

---

## 1. Overview

### Goal
Validate that we can correctly decode the 289 Morpheus cubes from `wav_decoded.bin` before writing any C++ filter code.

### Approach
- Clean rewrite (not patching existing broken code)
- Python for analysis/validation, C++ for production
- Validate against known preset frequencies before building filter engine

### Success Criteria
- C043 VowelSpace frequencies match phonetic formant targets (±50Hz)
- Decoded frequencies produce sensible values (20Hz-20kHz range)
- No obviously wrong values (0Hz, negative radius, R > 1)

---

## 2. Pipeline Architecture

```
cubes_v1.01vc_170120.wav
        │
        ▼
[WAV Frame Decoder] ← existing, sanity check only
        │
        ▼
wav_decoded.bin (96,500 bytes)
        │
        ▼
[ARMAdillo Decoder] ← NEW (exponential formulas)
        │
        ▼
morpheus_cubes_validated.json
        │
        ▼
[Validation Checks]
   • C043 VowelSpace formants
   • Talking Hedz reference (~2417Hz stage 0)
```

---

## 3. Deliverables

| File | Purpose |
|------|---------|
| `tools/validate_wav.py` | Sanity check WAV frame patterns |
| `tools/decode_cubes.py` | ARMAdillo decode → JSON export |
| `tools/verify_cubes.py` | Check known presets against expected values |
| `Source/Data/morpheus_cubes_validated.json` | Production data for C++ |

---

## 4. ARMAdillo Decoding Specification

### 4.1 The Problem
Previous implementation used fabricated linear formula `Hz = byte × 86.4`.
The patent specifies **exponential/logarithmic** encoding.

### 4.2 Patent Formulas (US 5,170,369A)

**Resonance (t2 / a2):**
```
t2 = 1 - 2^(-v2)
```
Where t2 = R² (pole radius squared)

**Frequency (t1 / a1):**
```
t1 = -2 + 4·2^(-v1) + 2^(-v2)
```
Where t1 = -2R·cos(θ)

### 4.3 Byte Format Hypotheses

**Hypothesis A: Linear Scaling**
```python
v1 = (byte1 / 255.0) * SCALE
v2 = (byte2 / 255.0) * SCALE
```

**Hypothesis B: Block Floating Point (Packed)**
```
Format: [S][sh2][sh1][sh0][d3][d2][d1][d0]
- S: Sign bit
- sh: Shift/exponent (3 bits)
- d: Mantissa (4 bits)

v = sign * (mantissa << shift) * SCALE_CONSTANT
```

### 4.4 Decode Implementation

```python
def decode_byte_linear(byte, scale):
    return (byte / 255.0) * scale

def decode_byte_packed(byte, scale):
    sign = -1 if (byte >> 7) & 1 else 1
    exp = (byte >> 4) & 0x07
    mantissa = byte & 0x0F
    return sign * (mantissa << exp) * (scale * 0.001)

def decode_stage(b1, b2, scale, mode='linear', sample_rate=44100):
    decode = decode_byte_linear if mode == 'linear' else decode_byte_packed
    v1, v2 = decode(b1, scale), decode(b2, scale)

    # Patent exponential formulas
    t2 = 1.0 - 2.0**(-max(v2, 0.001))
    t1 = -2.0 + 4.0 * 2.0**(-v1) + 2.0**(-v2)

    # Extract physical parameters
    R = math.sqrt(max(t2, 0.0001))
    cos_theta = max(-1, min(1, t1 / (-2.0 * R)))
    theta = math.acos(cos_theta)
    freq_hz = theta * sample_rate / (2 * math.pi)

    return {
        'a1': t1,
        'a2': t2,
        'R': R,
        'freq_hz': freq_hz,
        'v1': v1,
        'v2': v2
    }
```

---

## 5. Validation Targets

### 5.1 C043 VowelSpace Formants

**Vowel /i/ (as in "beet"):**
- F1: ~270 Hz
- F2: ~2290 Hz
- F3: ~3010 Hz

**Vowel /a/ (as in "father"):**
- F1: ~730 Hz
- F2: ~1090 Hz
- F3: ~2440 Hz

### 5.2 Talking Hedz Reference (M100% Q100%)

From Emulator X3 Cheat Engine capture:
```
Stage 0: a1=-1.993596, r=0.998475 → ~2417 Hz
Stage 1: a1=-1.912492, r=0.998384 → ~2724 Hz
Stage 2: a1=-1.861726, r=0.998353 → ~4974 Hz
Stage 3: a1=-1.510937, r=0.979504 → ~1701 Hz
Stage 4: a1=-1.992010, r=0.998232 → bounding
```

### 5.3 Scale Factor Determination

Sweep SCALE from 4.0 to 16.0:
1. For each scale, decode C043 corner 0
2. Check if F1 frequency ≈ 270Hz or 730Hz
3. Cross-validate F2, F3 against targets
4. Winner = (format, scale) that minimizes error

---

## 6. Binary Data Structure

### 6.1 File Layout
```
wav_decoded.bin (96,500 bytes)
├── Header: ~500 bytes
└── Cubes: 289 × ~332 bytes each
```

### 6.2 Per-Cube Layout
```
8 corners × 7 stages × 2 bytes = 112 bytes coefficients
+ metadata padding
```

### 6.3 Per-Stage (2 bytes)
```
Byte 0: v1 encoded (frequency parameter)
Byte 1: v2 encoded (resonance parameter)
```

### 6.4 Corner Index Mapping
```
3-bit binary: [Transform][Morph][Frequency]
000 = corner 0 (all min)
111 = corner 7 (all max)
```

---

## 7. JSON Output Schema

```json
{
  "format": "TRENCH Validated Morpheus Cubes",
  "decode_params": {
    "mode": "linear|packed",
    "scale": 8.0,
    "sample_rate": 44100
  },
  "cubes": [
    {
      "index": 0,
      "name": "Null Cube",
      "corners": [
        {
          "corner_index": 0,
          "stages": [
            {
              "stage": 0,
              "raw_bytes": [123, 200],
              "v1": 3.86,
              "v2": 6.27,
              "a1": -1.95,
              "a2": 0.98,
              "R": 0.99,
              "freq_hz": 1200.5,
              "flag": 1
            }
          ]
        }
      ]
    }
  ]
}
```

---

## 8. C++ Filter Architecture (Post-Validation)

### 8.1 Topology
7 cascaded biquads, Direct Form I, inter-stage saturation.

```
Input → [Biquad0] → [Sat] → [Biquad1] → [Sat] → ... → [Biquad6] → Output
```

### 8.2 Saturation (Two-Stage)

```cpp
// 1. Soft clip the sum (analog grit)
double sum = b0*x + b1*x1 + b2*x2 - a1*y1 - a2*y2;
if (sum > 4.0) sum = 4.0 + std::tanh(sum - 4.0);
if (sum < -4.0) sum = -4.0 + std::tanh(sum + 4.0);

// 2. Hard watchdog clamp (safety)
sum = std::clamp(sum, -100.0, 100.0);

// 3. Update state with saturated value
y2 = y1;
y1 = sum;
```

### 8.3 Zero Topology (Flag Field)
```cpp
if (flag == 1) {
    // Parametric zeros: (1 - z^-2)
    b0 = scale; b1 = 0; b2 = -scale;
} else {
    // Lowpass zeros: (1 + z^-1)^2
    b0 = norm; b1 = 2*norm; b2 = norm;
}
```

### 8.4 Interpolation
Trilinear interpolation in ARMAdillo domain (v1, v2), then decode to standard coefficients.

---

## 9. Implementation Order

| Step | Task | Validation |
|------|------|------------|
| 1 | `tools/validate_wav.py` | Confirm frame patterns |
| 2 | `tools/decode_cubes.py` | Export JSON with scale sweep |
| 3 | `tools/verify_cubes.py` | Check VowelSpace frequencies |
| 4 | Determine winning (mode, scale) | F1 within ±50Hz |
| 5 | Generate `morpheus_cubes_validated.json` | All 289 cubes |
| 6 | Update skill with confirmed parameters | Document findings |
| 7 | Rewrite C++ loader to use validated JSON | Clean implementation |

---

## 10. Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Neither byte format works | Try additional formats (signed, different bit layouts) |
| Scale doesn't converge | Check if bytes need preprocessing (bit reversal, etc.) |
| VowelSpace cube not at expected index | Search all 289 cubes for formant-like frequencies |
| Flag field location unknown | Analyze metadata bytes for patterns |

---

## Appendix: Reference Sources

- US Patent 5,170,369A — ARMAdillo encoding
- US Patent 5,248,845 — Filter cube interpolation
- Ding & Rossum 1995 — Filter morphing math
- Morpheus Manual — Cube structure, function generators
- Rane Note 157 — Fixed-point artifacts
