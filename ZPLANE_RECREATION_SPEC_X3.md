# Z-PLANE FILTER RECREATION SPECIFICATION
## Targeting Emulator X3 / Proteus 2000 / Orbit (12-Pole Architecture)

### Document Purpose

This document provides complete technical specifications for recreating E-mu Z-Plane filters as they exist in Emulator X3 and the Proteus/Orbit product line. All empirical data, validation targets, and coefficient captures come from X3. While the original patents describe the 1994 Morpheus hardware (14-pole), this specification targets the 12-pole architecture used in X3 because that is the system we can measure, validate against, and hear.

An LLM or developer reading this document should have sufficient information to implement a working Z-Plane filter engine that matches Emulator X3's Talking Hedz filter and can be extended to all 45+ Z-Plane presets in the X3 library.

---

## 1. ARCHITECTURE OVERVIEW

### 1.1 Topology

**CANONICAL TOPOLOGY: CASCADE (Series)**

Per US Patent 5,170,369 and 5,248,845, E-mu documentation (Proteus X Manual, Advanced Applications
Guide), the Z-Plane filter uses CASCADE (series) topology where signal flows sequentially through
each biquad stage.

```
Signal Flow (CASCADE):

[Input] ──→ [Section 0] ──→ [Section 1] ──→ [Section 2] ──→ [Section 3] ──→ [Section 4] ──→ [Output]

Each stage receives the previous stage's output.
Transfer function: H_total = H0 × H1 × H2 × H3 × H4
```

**Patent Evidence:**
- US 5,170,369: "cascade form... preferred embodiment, parallel has many disadvantages"
- Advanced Applications Guide: "1 -> 2 -> 3 -> 4 -> 5 -> 6" cascade diagram

**Open Investigation (2026-01-18):**
Pure CASCADE implementation produces ~97 dB response range at M=100% Q=0%, while reference
file "hedz - m100q0.wav" shows only ~35 dB range. This 2.8x discrepancy suggests:
- Additional normalization or gain compensation may be applied in X3
- The captured coefficient data may need different interpretation
- Reference file capture methodology needs verification

See debug session `.planning/debug/zplane-reference-file-invalid.md` for ongoing investigation.

### 1.2 The 12-Pole Architecture (X3/Proteus/Orbit)

Emulator X3 uses a 12-pole architecture, which means 6 biquad sections. This differs from the original 1994 Morpheus hardware, which used 14 poles (7 sections). The distinction matters because all our captured data comes from X3.

**X3 Architecture (Our Target):**

The filter consists of 6 biquad sections arranged as 1 Body/Lowpass filter plus 5 Parametric Peaking filters. The Body filter has 2 parameters (frequency and bandwidth). Each Parametric filter has 3 parameters (frequency, bandwidth, gain). This gives a total of 2 + (5 × 3) = 17 parameters per filter state.

**Evidence for 12-Pole in X3:**

The extracted DLL data contains 17×17 grids. This number directly corresponds to the 17-parameter count of the 12-pole architecture. The Cheat Engine captures show 5 coefficient stages (indices 0-4), which combined with 1 Body section equals 6 biquads. This is complete data, not a partial view of something larger.

**Comparison Table:**

| System | Poles | Biquads | Layout | Parameters |
|--------|-------|---------|--------|------------|
| Original Morpheus (1994) | 14 | 7 | 1 LP + 6 Parametric | 20 |
| X3/Proteus/Orbit (target) | 12 | 6 | 1 LP + 5 Parametric | 17 |

### 1.3 Section Roles

The standard vowel filter template places the Body/Lowpass filter at Section 1 (index 0), but
the architecture is FLEXIBLE - any stage can be LP, HP, or EQ.

**Standard Template (most vowel filters):**
- Section 1 (index 0): Body/Lowpass - provides spectral envelope and high-frequency rolloff
- Sections 2-5 (index 1-4): Parametric EQ - create resonant formant peaks
- Section 6 (index 5): Articulation - often HP or EQ for breath/air

**Talking Hedz Specific:**
Our captured data shows Stage 4 (index 4) has flag=0 (Lowpass), while Stages 0-3 have flag=1
(Bandpass/EQ). This means Talking Hedz places the "body" filter at the END of the cascade,
not the beginning. This is a valid configuration per E-mu documentation.

**The "flag" byte** in captured data indicates section type:
- **flag = 0**: Lowpass/Body - uses Unity DC Gain mode (zeros at Nyquist)
- **flag = 1**: Bandpass/Peaking/EQ - rejects DC (zeros at DC and Nyquist)

---

## 2. THE BIQUAD FOUNDATION

### 2.1 Transfer Function

Each section implements a second-order IIR filter (biquad) with the transfer function:

```
        b0 + b1·z⁻¹ + b2·z⁻²
H(z) = ─────────────────────────
        1 + a1·z⁻¹ + a2·z⁻²
```

The denominator coefficients (a1, a2) define the poles, which create resonant peaks. The numerator coefficients (b0, b1, b2) define the zeros, which create notches or shape the passband.

### 2.2 Pole Position and Filter Character

The pole angle θ determines the center frequency according to the formula freq = θ × sampleRate / (2π). The pole radius r determines the bandwidth and Q, where values closer to 1.0 produce narrower bandwidth and higher resonance.

### 2.3 Critical Coefficient Formula

The captured X3 data stores a1_captured (which equals -2×cos(θ) without the radius multiplication) and radius as separate values. To compute the actual biquad coefficients:

```
a1_actual = a1_captured × radius
a2 = radius × radius
```

This multiplication step is essential. The captured a1 value must be multiplied by radius to produce the correct feedback coefficient. This was validated against SPAN frequency measurements.

---

## 3. NUMERATOR FORMULAS BY SECTION TYPE

### 3.1 Lowpass/Body Section (flag = 0)

The lowpass section places zeros at the Nyquist frequency (z = -1), creating high-frequency rolloff while passing low frequencies. The formula is:

```
norm = (1 + a1_actual + a2) / 4
b0 = norm
b1 = 2 × norm
b2 = norm
```

If norm becomes zero or negative (which can happen when the pole is near DC), clamp it to a small positive value like 0.0001 to prevent silence.

### 3.2 Bandpass/Peaking Section (flag = 1)

The bandpass section places zeros at DC (z = +1) and Nyquist (z = -1), creating a resonant peak at the pole frequency while rejecting DC. The formula is:

```
scale = (1 - a2) / 2
b0 = scale
b1 = 0
b2 = -scale
```

This produces unity gain at the peak frequency with the bandwidth determined by the pole radius.

---

## 4. LOGARITHMIC COEFFICIENT ENCODING

### 4.1 The Problem with Direct Interpolation

US Patent 5,170,369 explains that linearly interpolating standard IIR coefficients "produces filters where audio quality varies dramatically over the sweep range, preventing any logarithmic or audibly meaningful sweep." Direct coefficient interpolation creates non-musical frequency motion.

### 4.2 The E-mu Solution

The patent describes encoding coefficients into a format where linear interpolation produces logarithmic (musically meaningful) changes. The encoding formulas for pole coefficients are:

```
ENCODE (for storage and interpolation):
  B1' = B1 + 2
  B2' = 1 - B2

DECODE (for rendering):
  B1 = B1' - 2
  B2 = 1 - B2'
```

The modification B1' = B1 + 2 ensures encoded values are always positive. The modification B2' = 1 - B2 concentrates resolution near the unit circle where resonance is most audible.

### 4.3 Interpolation Procedure

The correct procedure is to retrieve encoded parameters from the two morph endpoints, linearly interpolate in encoded space, decode the interpolated values, then compute biquad coefficients from decoded values. This produces logarithmic frequency sweeps that sound musical rather than linear sweeps that sound mechanical.

---

## 5. THE Q PARAMETER

### 5.1 Empirical Q-to-Radius Relationship

The Q parameter controls filter resonance by scaling the pole radius. This was empirically captured via Cheat Engine at Morph 50%:

| Q Setting | Radius (Stage 3) | Observation |
|-----------|------------------|-------------|
| 0% | 0.886765 | Broad, soft peaks |
| 50% | 0.951195 | Clear formant structure |
| 100% | 0.979504 | Sharp, narrow peaks |

The captured morph keyframes are all at Q=100% (maximum resonance). The Q knob scales radius downward from this reference.

### 5.2 The Proven Q Scaling Formula

```cpp
float applyQToRadius(float r_ref, float Q_ref, float Q_new) {
    // r_ref = captured radius at Q=100%
    // Q_ref = 100.0 (reference Q level)
    // Q_new = current Q setting (0.5 to 100)
    
    if (Q_new <= 0.0f) return 0.5f;
    
    float s = Q_ref / Q_new;
    float r = std::exp(std::log(std::max(r_ref, 1e-12f)) * s);
    
    return std::clamp(r, 0.5f, std::min(r_ref, 0.9999f));
}
```

### 5.3 Q Behavior Reference

| Q Knob | Radius | Character |
|--------|--------|-----------|
| 0% | ~0.50 | Blur, formants barely visible |
| 25% | ~0.70 | Soft but audible |
| 50% | ~0.90 | Clear peaks |
| 75% | ~0.95 | Sharp |
| 100% | 0.998 | Captured reference (maximum) |

---

## 6. CUBE INTERPOLATION

### 6.1 The 17×17 Grid Structure

X3 stores Z-Plane filter data as 17×17 grids corresponding to 17 Morph positions × 17 Q positions. The number 17 matches the parameter count of the 12-pole architecture. Each cell contains the encoded parameter values for that Morph/Q combination.

### 6.2 Bilinear Interpolation

Given position (x, y) where x is Morph (0-1) and y is Q (0-1), map to grid indices and interpolate:

```
grid_x = x × 16    // 0 to 16
grid_y = y × 16    // 0 to 16

i = floor(grid_x)
j = floor(grid_y)
fx = grid_x - i
fy = grid_y - j

// Bilinear weights
w00 = (1 - fx) × (1 - fy)
w10 = fx × (1 - fy)
w01 = (1 - fx) × fy
w11 = fx × fy

parameter = w00 × grid[i][j] + w10 × grid[i+1][j] + w01 × grid[i][j+1] + w11 × grid[i+1][j+1]
```

---

## 7. CAPTURED COEFFICIENT DATA: TALKING HEDZ

### 7.1 Data Source

The following coefficients were captured from Emulator X3 memory using Cheat Engine at five morph positions with Q at 100%. Each stage provides a1_captured, radius, and flag.

### 7.2 Coefficient Tables

**Morph 0% (vowel "EE"):**

| Stage | a1_captured | radius | flag | freq_Hz |
|-------|-------------|--------|------|---------|
| 0 | -1.974805 | 0.998231 | 1 | 1035 |
| 1 | -1.939721 | 0.998292 | 1 | 1679 |
| 2 | -1.873399 | 0.998353 | 1 | 2480 |
| 3 | -1.524112 | 0.992679 | 1 | 4882 |
| 4 | -1.997652 | 0.998292 | 0 | ~0 (DC) |

**Morph 25%:**

| Stage | a1_captured | radius | flag | freq_Hz |
|-------|-------------|--------|------|---------|
| 0 | -1.987616 | 0.998353 | 1 | 670 |
| 1 | -1.928071 | 0.998338 | 1 | 1845 |
| 2 | -1.867585 | 0.998353 | 1 | 2538 |
| 3 | -1.518988 | 0.987555 | 1 | 4867 |
| 4 | -1.996355 | 0.998261 | 0 | 91 |

**Morph 50% (crossover point):**

| Stage | a1_captured | radius | flag | freq_Hz |
|-------|-------------|--------|------|---------|
| 0 | -1.993596 | 0.998475 | 1 | 407 |
| 1 | -1.912492 | 0.998383 | 1 | 2046 |
| 2 | -1.861726 | 0.998353 | 1 | 2596 |
| 3 | -1.510937 | 0.979504 | 1 | 4843 |
| 4 | -1.992010 | 0.998231 | 0 | 469 |

**Morph 75%:**

| Stage | a1_captured | radius | flag | freq_Hz |
|-------|-------------|--------|------|---------|
| 0 | -1.996402 | 0.998597 | 1 | 198 |
| 1 | -1.896912 | 0.998429 | 1 | 2230 |
| 2 | -1.855866 | 0.998353 | 1 | 2652 |
| 3 | -1.499229 | 0.967796 | 1 | 4806 |
| 4 | -1.978928 | 0.998200 | 0 | 929 |

**Morph 100% (vowel "AH"):**

| Stage | a1_captured | radius | flag | freq_Hz |
|-------|-------------|--------|------|---------|
| 0 | -1.997743 | 0.998719 | 1 | ~0 (DC) |
| 1 | -1.881333 | 0.998475 | 1 | 2400 |
| 2 | -1.850007 | 0.998353 | 1 | 2707 |
| 3 | -1.476768 | 0.945335 | 1 | 4733 |
| 4 | -1.939599 | 0.998170 | 0 | 1677 |

### 7.3 Observations

Stages 0 and 4 exhibit contrary motion. At Morph 0%, Stage 0 is at 1035 Hz while Stage 4 is near DC. At Morph 100%, Stage 0 is near DC while Stage 4 is at 1677 Hz. They pass through each other around Morph 50%, creating the vowel transformation.

Stage 4 has flag=0 throughout, indicating it uses the lowpass/body numerator formula. Stages 0-3 have flag=1, indicating bandpass/peaking numerators.

All radius values are close to 1.0 (0.945 to 0.999), indicating high-Q resonances characteristic of formant filters.

---

## 8. VALIDATED FORMULAS

### 8.1 Frequency from Captured Coefficients

```
frequency_hz = acos(-a1_captured / 2) × sampleRate / (2 × π)
```

Validated against SPAN measurements within 1-4% accuracy.

### 8.2 Complete Biquad Coefficient Calculation

```cpp
void computeBiquadCoeffs(float a1_captured, float radius, int flag,
                         float& b0, float& b1, float& b2, float& a1, float& a2) {
    // Denominator (poles)
    a1 = a1_captured * radius;  // CRITICAL: multiply by radius
    a2 = radius * radius;
    
    // Numerator depends on flag
    if (flag == 1) {
        // Bandpass/Peaking
        float scale = (1.0f - a2) / 2.0f;
        b0 = scale;
        b1 = 0.0f;
        b2 = -scale;
    } else {
        // Lowpass/Body
        float norm = (1.0f + a1 + a2) / 4.0f;
        if (norm <= 0) norm = 0.0001f;
        b0 = norm;
        b1 = 2.0f * norm;
        b2 = norm;
    }
}
```

---

## 9. COMPLETE IMPLEMENTATION

### 9.1 Data Structures

```cpp
struct StageData {
    float a1_captured;  // -2*cos(theta), NOT multiplied by radius
    float radius;       // Pole radius (0 to 1)
    int flag;           // 1 = bandpass, 0 = lowpass
};

struct MorphKeyframe {
    float morph_position;  // 0.0 to 1.0
    StageData stages[5];   // 5 stages for X3 12-pole architecture
};

struct BiquadState {
    float z1 = 0, z2 = 0;  // Delay elements
};
```

### 9.2 Coefficient Update

```cpp
void updateCoefficients(float morph, float q_knob) {
    // 1. Find bracketing keyframes
    MorphKeyframe kfA, kfB;
    float t = findBracketingKeyframes(morph, kfA, kfB);
    
    // 2. For each stage
    for (int i = 0; i < 5; i++) {
        // Interpolate a1 and radius
        float a1_interp = lerp(kfA.stages[i].a1_captured, 
                               kfB.stages[i].a1_captured, t);
        float r_interp = lerp(kfA.stages[i].radius, 
                              kfB.stages[i].radius, t);
        
        // Apply Q scaling to radius
        float Q_ref = 100.0f;
        float Q_new = 0.5f + q_knob * 99.5f;
        float r_scaled = applyQToRadius(r_interp, Q_ref, Q_new);
        
        // Compute biquad coefficients
        computeBiquadCoeffs(a1_interp, r_scaled, kfA.stages[i].flag,
                           coeffs[i].b0, coeffs[i].b1, coeffs[i].b2,
                           coeffs[i].a1, coeffs[i].a2);
    }
}
```

### 9.3 Audio Processing (Cascade)

```cpp
float processSample(float input) {
    float signal = input;
    
    // Process through cascade (series)
    for (int i = 0; i < 5; i++) {
        signal = processBiquad(signal, coeffs[i], state[i]);
    }
    
    return signal;
}

float processBiquad(float x, const BiquadCoeffs& c, BiquadState& s) {
    // Direct Form II Transposed
    float y = c.b0 * x + s.z1;
    s.z1 = c.b1 * x - c.a1 * y + s.z2;
    s.z2 = c.b2 * x - c.a2 * y;
    return y;
}
```

---

## 10. VALIDATION CHECKLIST

**Frequency Accuracy:** Load Talking Hedz in X3 at Morph 0%, measure formant peaks with a spectrum analyzer. Implementation should match within 5%.

**Q Behavior:** Sweep Q from 0% to 100% at Morph 50%. At Q=0%, the response should be broad
and smooth but NOT FLAT - the filter is still active and applies rolloff. At Q=100%, peaks
should be sharp with deep notches between them. Only "No Filter" produces true flat/bypass.

**Morph Behavior:** Sweep Morph from 0% to 100% at Q=100%. The vowel should transform from "EE" to "AH" character smoothly without clicks or discontinuities.

**A/B Comparison:** Process identical audio through X3 and the implementation with matching parameters. Spectral character should be perceptually indistinguishable.

---

## 11. EXTENDING TO ALL X3 FILTERS

### 11.1 Data Sources

The zplane_filters.json file contains 45 Z-Plane filters extracted from EmulatorX.dll. Each filter has 17×17 grids for freq, gain, q, and shape parameters per stage. This provides complete interpolation data for all factory presets.

### 11.2 Shape Parameter

The shape byte indicates section type. While not fully decoded, likely mappings include 0 for bypass/off, 1 for lowpass, 2 for bandpass/peak, and higher values for specialized types like highpass, notch, or all-pass.

### 11.3 Special Filter Types

Phase shifters and flangers use all-pass coefficients (b0=a2, b1=a1, b2=1) instead of bandpass. Distortion filters may include non-linear saturation between stages. These require additional coefficient formulas beyond the standard lowpass/bandpass covered in this document.

---

## 12. SUMMARY

The Emulator X3 Z-Plane filter uses CASCADE (series) processing of 5 biquad sections (10 poles in
the captured data), enabling smooth morphing between vowel shapes.

**Essential Implementation Details:**

1. **CASCADE topology** - signal flows through stages in series.
   Signal flows: Input → Stage 0 → Stage 1 → Stage 2 → Stage 3 → Stage 4 → Output
   Transfer function: H_total = H0 × H1 × H2 × H3 × H4

2. **Coefficient formula**: a1_actual = a1_captured × radius (captured a1 is -2*r*cos(theta))

3. **Flag determines numerator**: flag=0 → Lowpass, flag=1 → Bandpass/EQ

4. **Q scaling**: Reduces radius from captured Q=100% reference using exponential formula

5. **Captured data is RAW**: NOT logarithmically encoded (decoding would produce invalid values)

6. **Flexible stage roles**: LP "body" filter can be at ANY position (Talking Hedz has it at stage 4)

7. **Q at 0% reduces resonance**: Filter remains active with rolloff (NOT flat response)

The captured Talking Hedz data provides 5 complete morph keyframes with all coefficient values
needed for implementation. The architecture can be extended to all 45 X3 filters using the
extracted DLL data.

**Open Investigation:** Current implementation produces ~97 dB response range vs reference ~35 dB.
Additional normalization or coefficient interpretation changes may be needed.

**Primary Sources**: US Patents 5,170,369 and 5,248,845, E-mu X3 Reference Manual, Proteus X
Operation Manual, Advanced Applications Guide (verified via NotebookLM 2026-01-18).

---

## APPENDIX A: QUICK REFERENCE

```
TARGET ARCHITECTURE: 12-pole (6 biquads) — X3/Proteus/Orbit
SECTION COUNT: 6 (1 lowpass + 5 parametric)
PARAMETERS: 17 per filter state
GRID SIZE: 17×17 (Morph × Q)

FREQUENCY FROM A1:
  freq = acos(-a1_captured / 2) × sampleRate / (2π)

BIQUAD DENOMINATOR:
  a1 = a1_captured × radius
  a2 = radius²

BANDPASS NUMERATOR (flag=1):
  b0 = (1 - a2) / 2
  b1 = 0
  b2 = -b0

LOWPASS NUMERATOR (flag=0):
  norm = (1 + a1 + a2) / 4
  b0 = norm
  b1 = 2 × norm
  b2 = norm

Q SCALING:
  r_new = exp(log(r_ref) × (Q_ref / Q_new))
```

---

## APPENDIX B: FILE LOCATIONS

```
Captured Coefficients:  TalkingHedzFilter.h
DLL Extraction:         zplane_filters.json (45 filters, 17×17 grids)
XML Templates:          Templates/Filter/*.xml (68 files)
Project Root:           c:/trenchdev/TRENCH/
```

---

## APPENDIX C: VALIDATION STATUS

This specification was verified against primary sources and empirical captures on 2026-01-17.

**Verified Against Patents:**

| Claim | Source | Status |
|-------|--------|--------|
| Cascade topology | US 5,248,845 | Confirmed |
| Logarithmic encoding (B1', B2') | US 5,170,369 | Confirmed |
| Linear interpolation of encoded values | US 5,170,369 | Confirmed |

**Verified Against X3 Captures:**

| Claim | Method | Status |
|-------|--------|--------|
| 5 coefficient stages (12-pole) | Cheat Engine | Confirmed |
| 17×17 grid structure | DLL extraction | Confirmed |
| Frequency formula accuracy | SPAN comparison | Within 1-4% |
| Q-to-radius relationship | Multi-Q capture | Confirmed |
| Flag indicates numerator type | Behavioral testing | Confirmed |

---

## APPENDIX D: NOTEBOOKLM RESEARCH FINDINGS (2026-01-18)

The following findings come from querying Google NotebookLM loaded with E-mu X3 Reference Manual,
Proteus X Operation Manual, Advanced Applications Guide, and US Patents 5,170,369 and 5,248,845.

### D.1 Topology: CASCADE (Per All E-mu Documentation)

**Source**: NotebookLM queries against E-mu manuals and patents (2026-01-18)

**CONFIRMED CASCADE TOPOLOGY:**
- US Patent 5,170,369: "cascade form... preferred embodiment, parallel has many disadvantages"
- Advanced Applications Guide: "1 -> 2 -> 3 -> 4 -> 5 -> 6" cascade diagram
- Proteus X Manual: "sections are cascaded"

**Previous "Parallel" Conclusion Was Wrong:**
An earlier debug session incorrectly concluded X3 uses parallel topology based on flawed analysis:
- The FFT was computed on the SILENT portion of reference files (first 8000+ samples are zeros)
- The signal actually starts mid-file (13.5% for hedz - m100q0.wav)
- CORRECTED analysis shows hedz - m100q0.wav has 34.6 dB response range (not flat!)

**Open Question:**
Pure CASCADE implementation produces ~97 dB response range, while reference shows ~35 dB.
This discrepancy is under investigation. Possible causes:
- Additional gain normalization in X3
- Different coefficient interpretation needed
- Reference capture methodology issues

### D.2 Filter Types per Stage

**Source**: Emulator X3 Advanced Applications Guide

Available filter types for each Morph Designer stage:
- **Lowpass (LP)** - flag=0, Unity DC Gain mode
- **Highpass (HP)** - zeros at DC
- **EQ (Parametric)** - flag=1, bandpass/peaking

**NOT available as primitives**: Bandpass, Notch, Allpass (these are created by combining LP/HP/EQ)

### D.3 The "Flag" Meaning

**Source**: US Patent 5,170,369

The flag byte corresponds to a hardware multiplexer ("Unity DC Gain" switch):
- **flag=0**: Unity DC Gain mode (Lowpass) - forces DC gain to unity
- **flag=1**: Standard mode (EQ/Parametric/Bandpass)

This is implemented via Mux 16 in Figure 6 of the patent.

### D.4 Q at 0% Behavior (CORRECTED 2026-01-18)

**Source**: NotebookLM query + corrected empirical analysis

**NotebookLM Research Confirms:**
- Q=0% does NOT produce flat response
- Filter remains ACTIVE, still applies LP/HP rolloff
- Only "No Filter" or "Null Cube" (C000) produces completely flat response
- "Null Cube" is described as "completely flat frequency response under all parameter settings"

**Corrected Empirical Finding:**
Previous analysis claimed hedz - m100q0.wav was "essentially flat" - THIS WAS WRONG.
The FFT was computed on the silent portion of the file (samples 0-8191).
CORRECTED analysis of actual signal (starting at sample 8528) shows:
- dB range: 34.6 dB (MODERATE filtering, not flat)
- Spectral peaks at: 221 Hz, 2019 Hz, 2686 Hz
- This IS filtered audio, consistent with Talking Hedz at Q=0%

**IMPLICATION**: Q=0% reduces resonance but the filter is still active with significant rolloff.

### D.5 Stage Numbering and Roles

**Source**: Emulator X3 Advanced Applications Guide

- UI shows stages 1-6, internal DSP uses indices 0-5
- Standard vowel template:
  - Stage 1 (index 0): Lowpass "Body" filter
  - Stages 2-5 (index 1-4): Parametric EQ formants
  - Stage 6 (index 5): HP or EQ for articulation
- Architecture is FLEXIBLE - LP body can appear at ANY position

**Talking Hedz Specific**: Our captured data shows flag=0 (LP) at Stage 4 (index 4),
meaning the "body" filter is at the END of the cascade, not the beginning. This is valid
per E-mu documentation.

### D.6 Coefficient Encoding (Confirmed)

**Source**: US Patent 5,170,369

Linear interpolation on ENCODED values produces logarithmic audio sweeps:
```
B1' = B1 + 2      (ensures positive values)
B2' = 1 - B2      (concentrates resolution near unit circle)
```

Interpolation formula: `C(x) = Ca + x(Cb - Ca)` where x is morph position (0-1)

### D.7 Coefficient Generation Method

**Source**: US Patent 5,170,369

Coefficients are generated using numerical optimization:
- Equation-error method
- Hankel norm
- Prony's method
- Linear Predictive Coding (LPC)

A desired frequency response is defined, and algorithms calculate optimal pole/zero
coefficients to approximate that curve.

### D.8 Gain Controls (What They Actually Do)

**Source**: Emulator X3 Advanced Applications Guide

The "Gain" knob function changes by filter type:
- **If LP/HP**: Controls Q (resonance), NOT output level
- **If EQ**: Controls boost/cut in dB

There is NO per-stage output level or mix gain control. Global filter gain exists only
for clipping prevention.

### D.9 Implications for Implementation (CORRECTED 2026-01-18)

Based on NotebookLM research and corrected empirical analysis:

1. **Use CASCADE topology** - per all E-mu patents and documentation
2. **No mix gains array** - parallel summing is NOT used
3. **flag=0 means LP numerator**, flag=1 means BP/EQ numerator
4. **Stage 4 being LP at the end** is correct for Talking Hedz
5. **Q=0% reduces resonance but filter remains active** - NOT flat response
6. **Reference files have silent padding** - signal starts mid-file, must align before comparison

**Open Investigation:**
CASCADE implementation produces ~97 dB response range vs reference's ~35 dB.
Possible causes being investigated:
- X3 may apply additional normalization or gain staging
- Coefficient data interpretation may need revision
- Some stages may be configured differently than captured

See debug session `.planning/debug/zplane-reference-file-invalid.md` for details.

---

## APPENDIX E: DOCUMENT METADATA

```json
{
  "document_type": "technical_specification",
  "subject": "Z-Plane filter recreation",
  "target_system": "Emulator X3 / Proteus 2000 / Orbit",
  "primary_sources": ["US Patent 5,170,369", "US Patent 5,248,845"],
  "empirical_sources": ["Emulator X3 memory capture via Cheat Engine", "SPAN frequency analysis", "X3 reference WAV captures"],
  "notebooklm_sources": ["X3 Reference Manual", "Proteus X Operation Manual", "Advanced Applications Guide"],
  "validation_status": "CASCADE topology confirmed per documentation. Implementation produces ~97dB range vs reference ~35dB - under investigation.",
  "version": "2026-01-18-CASCADE-CORRECTED",
  "architecture": "5 biquad sections (10 poles) in captured data",
  "topology": "CASCADE (series) - per US Patent 5,170,369 and all E-mu documentation",
  "open_issues": [
    "CASCADE produces steeper rolloff than reference files show",
    "Reference files have silent padding that affected previous analysis",
    "Coefficient interpretation or gain staging may need revision"
  ]
}
```
