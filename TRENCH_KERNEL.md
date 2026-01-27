# TRENCH_KERNEL: Validated Z-Plane Architecture
**TARGET:** Emulator X3 (Software Implementation)
**VERSION:** 3.0 (2026-01-26)
**STATUS:** Validated against live Cheat Engine captures + audio FFT

---

## 1. Confirmed Constants (Talking Hedz)

| Constant | Value | Validation Method |
|----------|-------|-------------------|
| **STAGES** | 5 | CE capture at 0x0056E450, 12-byte spacing |
| **POLES** | 10 | 5 stages × 2 poles each |
| **TOPOLOGY** | Cascade (series) | Previous session: notch depth test |
| **STAGE_SIZE** | 12 bytes | [a1: float][r: float][flag: float] |

**UNVALIDATED (from docs, needs testing):**
| Constant | Claimed Value | Source |
|----------|---------------|--------|
| Q_SCALE | 0.057826 | NotebookLM / old docs |
| CUBE_SIZE | 333 bytes | Calculated from WAV decode |
| CUBE_COUNT | 289 | Calculated from WAV decode |

---

## 2. Memory Layout (Runtime)

**Per-Stage (12 bytes):**
```
Offset 0x00: float32 a1     // Frequency coefficient (-2.0 to 0.0)
Offset 0x04: float32 r      // Radius (0.0 to 1.0, typically 0.88-0.999)
Offset 0x08: float32 flag   // 1.0 = resonator, 0.0 = lowpass
```

**Stage Array (60 bytes total):**
```
Base + 0x00: Stage 0
Base + 0x0C: Stage 1
Base + 0x18: Stage 2
Base + 0x24: Stage 3
Base + 0x30: Stage 4
```

Note: Base address shifts on X3 restart. Found at 0x0056E450 this session.

---

## 3. Coefficient Decode (PROVEN)

```cpp
// Frequency from a1 and radius
float cos_theta = -a1 / (2.0f * r);
float theta = acosf(fmaxf(-1.0f, fminf(1.0f, cos_theta)));
float freq_hz = theta * sampleRate / (2.0f * M_PI);

// a2 from radius (standard biquad)
float a2 = r * r;

// Q from radius (for analysis only)
float Q = r / (2.0f * (1.0f - r));
```

---

## 4. Stage Types (PROVEN)

**flag = 1.0: Resonator Stage**
- Creates a peak at freq_hz
- Must be unity gain away from resonance (NOT pure bandpass)
- Numerator formula: TBD (the main unknown)

**flag = 0.0: Lowpass Stage**
- Provides low-frequency body
- Does not create sharp spectral peak
- Standard lowpass biquad numerator:
  ```cpp
  float a2 = r * r;
  float b0 = (1.0f + a1 + a2) / 4.0f;
  float b1 = 2.0f * b0;
  float b2 = b0;
  ```

---

## 5. Validated Captures (Ground Truth)

### M0_Q100 (Morph=0%, Q=100%)
```
S0: a1=-1.976510  r=0.998242  flag=1.0  ->  994 Hz
S1: a1=-1.938977  r=0.998296  flag=1.0  -> 1690 Hz
S2: a1=-1.872895  r=0.998353  flag=1.0  -> 2485 Hz
S3: a1=-1.523842  r=0.992409  flag=1.0  -> 4881 Hz
S4: a1=-1.997572  r=0.998289  flag=0.0  ->   DC
```
**Audio peaks:** 178, 1077, 1701, 2498, 4915 Hz
**Match quality:** Within 8% for all resonator stages

### M100_Q100 (Morph=100%, Q=100%)
```
S0: a1=-1.996743  r=0.998619  flag=1.0  ->  156 Hz
S1: a1=-1.894098  r=0.998437  flag=1.0  -> 2262 Hz
S2: a1=-1.854829  r=0.998353  flag=1.0  -> 2662 Hz
S3: a1=-1.495171  r=0.963737  flag=1.0  -> 4793 Hz
S4: a1=-1.974292  r=0.998195  flag=0.0  -> 1045 Hz
```
**Audio peaks:** 221, 2417, 2719, 10148 Hz

### M100_Q0 (Morph=100%, Q=0%)
```
S0: a1=-1.986418  r=0.987503  flag=1.0  ->   DC
S1: a1=-1.837391  r=0.974537  flag=1.0  -> 2388 Hz
S2: a1=-1.794609  r=0.977806  flag=1.0  -> 2868 Hz
S3: a1=-1.362762  r=0.883514  flag=1.0  -> 4843 Hz
S4: a1=-1.914935  r=0.993960  flag=0.0  -> 1908 Hz
```
**Audio peaks:** 215, 2024, 2681, 3047 Hz

---

## 6. Q Knob Behavior (PROVEN)

Q knob scales radius uniformly across all stages:

| Stage | r @ Q100 | r @ Q0 | Δ |
|-------|----------|--------|---|
| S0 | 0.998619 | 0.987503 | -0.011 |
| S1 | 0.998437 | 0.974537 | -0.024 |
| S2 | 0.998353 | 0.977806 | -0.021 |
| S3 | 0.963737 | 0.883514 | -0.080 |
| S4 | 0.998195 | 0.993960 | -0.004 |

Higher Q = higher radius = sharper resonance.

---

## 7. Cube Architecture (FROM DOCS - NEEDS VALIDATION)

**Morpheus Cube WAV:**
- File: cubes_v1.01vc_170120.wav
- Size: 96,500 bytes decoded
- Structure: 263-byte header + 289 × 333-byte cubes

**Per Cube:**
- 8 corners (3 axes: Morph, Freq, Transform)
- 7 stages per corner (but X3 may only use 5?)
- Parameters encoded in ARMAdillo v-domain

**ARMAdillo Decode (from patent, UNVALIDATED):**
```
t2 = 1 - 2^(-v_res)           // Approximates radius²
t1 = -2 + 4×2^(-v_freq) + 2^(-v_res)  // Approximates a1
```

**Validation approach:** Decode a cube, compare to CE capture at same position.

---

## 8. Interpolation (FROM DOCS - NEEDS VALIDATION)

**Rule:** Do NOT interpolate a1/a2 directly (causes pitch wobble).

**ARMAdillo approach:**
1. Store parameters in v-domain (log frequency, log resonance)
2. Interpolate v-values linearly during morph
3. Convert interpolated v to coefficients

**Control rate:** Update coefficients every 16-32 samples (not per-sample).

---

## 9. Saturation (FROM DOCS)

```cpp
inline float saturate(float x) {
    if (x > 4.0f) return 4.0f + tanhf(x - 4.0f);
    if (x < -4.0f) return -4.0f + tanhf(x + 4.0f);
    return x;
}
```

---

## 10. Open Questions

1. **Numerator for flag=1 stages** — Must be unity away from resonance. Formula unknown.
2. **Cube decode validation** — Do decoded cubes match CE captures?
3. **Stage count per filter** — Is it always 5, or does it vary by preset?
4. **The 10148 Hz peak** — Appears in M100_Q100 audio, not predicted by captures. Source unknown.
5. **Q_SCALE value** — 0.057826 claimed but unvalidated.

---

## 11. Implementation Phases

### Phase 1: DSP Engine (Current)
- Hardcode Talking Hedz coefficients
- Validate against audio references
- Solve numerator formula

### Phase 2: Cube Decoder
- Decode cube WAV to raw bytes
- Parse cube structure
- Validate against CE captures (ground truth)

### Phase 3: Full Plugin
- Load any cube from library
- Real-time morph interpolation
- Q scaling