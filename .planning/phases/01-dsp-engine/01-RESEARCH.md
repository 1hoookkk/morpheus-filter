# Phase 1: DSP Engine - Research

**Researched:** 2026-01-19
**Domain:** Z-Plane filter DSP, biquad cascade, coefficient interpolation
**Confidence:** HIGH (patent-verified formulas, empirically captured data)

## Summary

This research investigates the DSP engine requirements for recreating E-mu Z-Plane filters targeting validation against EmulatorX3 reference recordings. The Z-Plane filter is a cascaded biquad architecture (7 stages / 14 poles) with a specialized coefficient encoding scheme (ARMAdillo) that enables musically meaningful interpolation.

The key architectural decision from CONTEXT.md is to **store all coefficients in semitone space relative to C5**. This aligns with E-mu's ARMAdillo patent which specifies that linear interpolation of logarithmically-encoded coefficients produces the desired "Rossum sweep" - logarithmic frequency motion that sounds musical rather than mechanical.

The extracted `talking_hedz_extracted.json` provides complete 17x17x3 grid data (17 Morph positions x 17 Transform positions x 3 Q variants) with 7 stages per cell, giving us full coverage for bilinear interpolation across the filter cube.

**Primary recommendation:** Implement coefficient storage in semitone space with lazy conversion to biquad coefficients at render time. Use the standard cascade topology with stage-specific numerator formulas based on shape type (LP vs EQ).

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| C++ STL | N/A | Core data structures | Zero dependency, portable |
| JUCE (optional) | 7.x | Audio plugin framework | Industry standard for VST/AU/AAX |
| NumPy/SciPy | Latest | Validation scripts | De facto standard for DSP validation |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| nlohmann/json | 3.x | JSON parsing | Loading cartridge files |
| matplotlib | Latest | Response plotting | Validation visualization |
| libsndfile/dr_wav | Latest | WAV I/O | Reference file comparison |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Hand-rolled biquad | JUCE IIR::Filter | JUCE adds framework dependency but provides SIMD optimization |
| Custom JSON parser | RapidJSON | nlohmann is slower but much easier to use |

**Installation:**
```bash
# Python validation environment
pip install numpy scipy matplotlib soundfile

# C++ (header-only libraries)
# nlohmann/json: single header, copy to project
```

## Architecture Patterns

### Recommended Project Structure

```
src/
  ZPlane/
    ZPlaneData.h           # Data structures (SemitoneStageData, MorphCell, Cartridge)
    ZPlaneMath.h           # Conversion functions (Hz<->semitone, biquad computation)
    ZPlaneFilter.h         # Filter engine class
    ZPlaneCartridgeLoader.h # JSON loading
  Validation/
    validate_zplane.py     # Reference comparison
    plot_response.py       # Frequency response visualization
```

### Pattern 1: Semitone-Space Storage

**What:** Store all frequency-related coefficients as semitones relative to C5 (523.25 Hz, MIDI note 72)

**When to use:** All coefficient storage and interpolation

**Why:** E-mu's patent (US 5,170,369) specifies that linear interpolation of logarithmically-encoded coefficients produces logarithmic frequency sweeps. Semitone space IS logarithmic frequency space.

**Conversion formulas:**

```cpp
// Source: MIDI Tuning Standard + Audio EQ Cookbook
constexpr float C5_HZ = 523.251f;       // MIDI note 72
constexpr float SEMITONE_RATIO = 1.0594630943592953f;  // 2^(1/12)

// Hz to semitones relative to C5
inline float hzToSemitone(float hz) {
    if (hz <= 0.0f) return -120.0f;  // Effectively DC
    return 12.0f * std::log2(hz / C5_HZ);
}

// Semitones to Hz
inline float semitoneToHz(float semitone) {
    return C5_HZ * std::pow(2.0f, semitone / 12.0f);
}

// Examples:
//   C5 (523 Hz) -> 0 semitones
//   C6 (1046 Hz) -> +12 semitones
//   C4 (262 Hz) -> -12 semitones
//   A4 (440 Hz) -> -3 semitones
```

### Pattern 2: Lazy Biquad Computation

**What:** Store semitone values, compute biquad coefficients only at control rate

**When to use:** Coefficient updates (every 32-128 samples, not per-sample)

```cpp
struct SemitoneStageData {
    float freqSemitone;    // Stored: frequency in semitones relative to C5
    float radius;          // Stored: pole radius 0-1 (already logarithmic-ish)
    float gainDb;          // Stored: gain in dB (already logarithmic)
    int shape;             // 0=LP, 1=EQ, 2=HP (does not interpolate)
};

// At render time (per control block):
void updateBiquadFromSemitone(const SemitoneStageData& data, float sampleRate) {
    float freqHz = semitoneToHz(data.freqSemitone);
    float omega = 2.0f * M_PI * freqHz / sampleRate;

    // Clamp to valid range (Nyquist limit)
    omega = std::min(omega, 3.1f);  // Just under pi

    // Compute biquad...
}
```

### Pattern 3: Trilinear Grid Interpolation

**What:** The 17x17x3 grid requires interpolation in 3 dimensions: Morph (X), Transform (Y), Q (Z)

**When to use:** Any parameter update

```cpp
struct GridPosition {
    float morph;      // 0-1, maps to columns 0-16
    float transform;  // 0-1, maps to rows 0-16
    float q;          // 0-1, maps to variants 0-2
};

// Trilinear interpolation
SemitoneStageData interpolateGrid(const Cartridge& cart, int stageIdx, GridPosition pos) {
    // Map 0-1 to grid indices
    float gx = pos.morph * 16.0f;
    float gy = pos.transform * 16.0f;
    float gz = pos.q * 2.0f;  // 3 variants -> indices 0,1,2

    int ix = (int)gx;
    int iy = (int)gy;
    int iz = (int)gz;

    float fx = gx - ix;
    float fy = gy - iy;
    float fz = gz - iz;

    // Clamp to valid range
    ix = std::clamp(ix, 0, 15);
    iy = std::clamp(iy, 0, 15);
    iz = std::clamp(iz, 0, 1);

    // 8-point trilinear interpolation
    // ... (standard trilinear formula)
}
```

### Pattern 4: Stage-Specific Numerator Formulas

**What:** Different biquad numerator formulas for LP vs EQ stages

**When to use:** Biquad coefficient computation

```cpp
// Source: US Patent 5,170,369, Audio EQ Cookbook
void computeBiquadCoeffs(float freqHz, float radius, float gainDb, int shape,
                         float sampleRate, BiquadCoeffs& out) {
    float omega = 2.0f * M_PI * freqHz / sampleRate;
    omega = std::clamp(omega, 0.001f, 3.1f);

    float cosOmega = std::cos(omega);
    float sinOmega = std::sin(omega);

    // Denominator (poles) - same for all shapes
    out.a1 = -2.0f * radius * cosOmega;
    out.a2 = radius * radius;

    // Numerator (zeros) - depends on shape
    if (shape == 0) {
        // LOWPASS: zeros at Nyquist (z = -1)
        // Unity DC gain normalization
        float norm = (1.0f + out.a1 + out.a2) / 4.0f;
        norm = std::max(norm, 0.0001f);
        out.b0 = norm;
        out.b1 = 2.0f * norm;
        out.b2 = norm;
    }
    else if (shape == 1) {
        // EQ/BANDPASS: zeros at DC (z = +1) and Nyquist (z = -1)
        // Unity peak gain normalization
        float scale = (1.0f - out.a2) / 2.0f;

        // Apply gain boost/cut (in dB)
        float gainLinear = std::pow(10.0f, gainDb / 20.0f);
        out.b0 = scale * gainLinear;
        out.b1 = 0.0f;
        out.b2 = -scale * gainLinear;
    }
    else if (shape == 2) {
        // HIGHPASS: zeros at DC (z = +1)
        // Unity Nyquist gain normalization
        float norm = (1.0f - out.a1 + out.a2) / 4.0f;
        norm = std::max(norm, 0.0001f);
        out.b0 = norm;
        out.b1 = -2.0f * norm;
        out.b2 = norm;
    }
}
```

### Anti-Patterns to Avoid

- **Linear frequency interpolation:** NEVER interpolate frequencies in Hz - always in semitone space
- **Per-sample coefficient update:** Compute coefficients at control rate (32-128 samples), not audio rate
- **Ignoring ultrasonic frequencies:** Stages with freq > Nyquist/2 should pass signal unchanged
- **Forgetting gain normalization:** Each stage type needs appropriate normalization to prevent clipping

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JSON parsing | Custom parser | nlohmann/json | Edge cases, unicode, escaping |
| WAV file I/O | Raw file reading | libsndfile or dr_wav | Format variations, endianness |
| FFT for validation | DFT implementation | numpy.fft or FFTW | Numerical precision, performance |
| log2/pow2 | Naive implementation | std::log2/std::pow | Precision, platform optimization |

**Key insight:** The DSP core (biquad cascade, coefficient computation) IS hand-rolled because E-mu's specific formulas aren't available in standard libraries. But all infrastructure (file I/O, JSON, validation math) should use proven libraries.

## Common Pitfalls

### Pitfall 1: Linear Coefficient Interpolation

**What goes wrong:** Interpolating raw biquad coefficients (a1, a2) produces warped frequency trajectories and gain spikes
**Why it happens:** Biquad coefficients have non-linear relationship to perceptual frequency
**How to avoid:** Always interpolate in semitone space, convert to biquad at render time
**Warning signs:** Formant sweeps sound "mechanical" or have audible clicks

### Pitfall 2: Unstable Filters Near DC

**What goes wrong:** Poles very close to z=1 (low frequency, high radius) cause instability or silence
**Why it happens:** Lowpass normalization formula `(1 + a1 + a2)/4` approaches zero as pole approaches DC
**How to avoid:** Clamp normalization factor to minimum (e.g., 0.0001), clamp omega to minimum 0.001
**Warning signs:** Output goes to zero, NaN, or infinity

### Pitfall 3: Sample Rate Mismatch

**What goes wrong:** Filter sounds different at 48kHz vs 44.1kHz - formants shift higher
**Why it happens:** Captured coefficients are relative to 44.1kHz; angle-to-Hz conversion is sample-rate dependent
**How to avoid:** Store frequencies in absolute Hz (or semitones), recompute omega at runtime sample rate
**Warning signs:** A/B comparison between sample rates shows frequency shift

### Pitfall 4: Q Parameter Misunderstanding

**What goes wrong:** Q=0% produces flat response instead of broad formants
**Why it happens:** Confusion between "low Q = bypass" vs "low Q = broad peaks"
**How to avoid:** Q scales pole radius: low Q = smaller radius = broader peaks (NOT bypass)
**Warning signs:** Q sweep sounds like wet/dry mix instead of bandwidth change

### Pitfall 5: Grid Index Off-by-One

**What goes wrong:** Morph=100% produces wrong vowel
**Why it happens:** 17 grid points means indices 0-16, not 0-17; interpolation needs clamping
**How to avoid:** Use `std::clamp(index, 0, 15)` for base index, separate handling for endpoints
**Warning signs:** Extreme morph values sound wrong or cause crashes

### Pitfall 6: Gain Accumulation in Cascade

**What goes wrong:** Output clips or is too quiet
**Why it happens:** 7 stages in cascade multiply gains; each EQ boost compounds
**How to avoid:** Apply per-stage gains from grid data; consider automatic gain compensation
**Warning signs:** Output dynamic range doesn't match reference files

## Code Examples

### Complete Biquad Processing (Direct Form II Transposed)

```cpp
// Source: Industry standard, most numerically stable for high-Q filters
struct BiquadState {
    float z1 = 0.0f;
    float z2 = 0.0f;
};

inline float processBiquad(float input, const BiquadCoeffs& c, BiquadState& s) {
    float output = c.b0 * input + s.z1;
    s.z1 = c.b1 * input - c.a1 * output + s.z2;
    s.z2 = c.b2 * input - c.a2 * output;
    return output;
}
```

### Semitone Grid Cell Structure

```cpp
// Matches JSON structure for each stage within a grid cell
struct GridStageData {
    float freqSemitone;  // Converted from freq_17x17 Hz values
    float radius;        // From radius_17x17 (already 0-1)
    float gainDb;        // From gain_17x17 (already in dB-ish units)
    int shape;           // 0=LP, 1=EQ (from "shape" field)
};

// Complete cartridge structure
struct ZPlaneCartridge {
    std::string name;
    int numStages = 7;
    int gridSize = 17;   // 17x17 grid
    int numVariants = 3; // Q variants

    // Data: variants[3][stages[7]][grid[17*17]]
    std::vector<std::vector<std::vector<GridStageData>>> data;
};
```

### Sample Rate Warping

```cpp
// Source: Bilinear transform frequency warping
// Captured at 44.1kHz, runtime may be 48kHz or 96kHz
constexpr float CAPTURE_SAMPLE_RATE = 44100.0f;

float warpFrequencyForSampleRate(float freqHz, float runtimeSampleRate) {
    if (std::abs(runtimeSampleRate - CAPTURE_SAMPLE_RATE) < 1.0f) {
        return freqHz;  // No warping needed
    }

    // The frequency is already in Hz (or converted from semitones)
    // Just clamp to Nyquist of runtime rate
    float nyquist = runtimeSampleRate / 2.0f;
    return std::min(freqHz, nyquist * 0.95f);
}

// Note: Because we store in semitones and convert to Hz at runtime,
// sample rate handling is automatic - omega = 2*pi*f/fs handles it
```

### Q-to-Radius Scaling (Empirically Derived)

```cpp
// Source: Cheat Engine captures from X3 at multiple Q settings
// Q knob interpolates between 3 variants (indices 0, 1, 2)
// Variant 0 = Q 0% (broad), Variant 1 = Q 50%, Variant 2 = Q 100% (sharp)

// The grid already contains pre-baked radius values for each Q level
// So Q interpolation is just trilinear interpolation across Z axis

// If you need to scale radius dynamically (legacy approach):
float applyQScaling(float radiusRef, float qKnob) {
    // qKnob: 0-1 (0% to 100%)
    // radiusRef: captured at Q=100%

    constexpr float Q_REF = 100.0f;
    constexpr float Q_MIN = 17.0f;   // Empirically derived from X3
    constexpr float RADIUS_FLOOR = 0.5f;

    float qActual = Q_MIN + qKnob * (Q_REF - Q_MIN);
    float scale = Q_REF / qActual;
    float r = std::exp(std::log(radiusRef) * scale);

    return std::clamp(r, RADIUS_FLOOR, radiusRef);
}
```

### Loading JSON Grid Data

```cpp
// Source: nlohmann/json library
#include <nlohmann/json.hpp>

ZPlaneCartridge loadCartridge(const std::string& path) {
    std::ifstream f(path);
    nlohmann::json j = nlohmann::json::parse(f);

    ZPlaneCartridge cart;
    cart.name = j["name"];

    // 3 variants
    for (const auto& variant : j["variants"]) {
        std::vector<std::vector<GridStageData>> stages;

        // 7 stages per variant
        for (const auto& stage : variant["stages"]) {
            std::vector<GridStageData> grid;

            const auto& freqs = stage["freq_17x17"];
            const auto& gains = stage["gain_17x17"];
            const auto& radii = stage["radius_17x17"];
            std::string shape = stage["shape"];

            // 17*17 = 289 cells
            for (size_t i = 0; i < 289; i++) {
                GridStageData cell;
                cell.freqSemitone = hzToSemitone(freqs[i].get<float>());
                cell.radius = radii[i].get<float>();
                cell.gainDb = gains[i].get<float>();  // Already dB-ish
                cell.shape = (shape == "lp") ? 0 : 1;
                grid.push_back(cell);
            }
            stages.push_back(grid);
        }
        cart.data.push_back(stages);
    }

    return cart;
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| ARMAdillo bit-shifting | Floating-point semitones | Post-hardware era | Simpler code, same results |
| 8-bit coefficients | 32-bit float | When FPUs became fast | Better precision, no encoding needed |
| Per-sample coeff update | Control-rate update | Always | Massive CPU savings |
| Parallel topology | Cascade topology | N/A (always cascade) | Correct per E-mu patents |

**Deprecated/outdated:**
- The "flag" byte interpretation in old captures: Now we have explicit "shape" field
- B1'/B2' encoding: Only needed for hardware; software uses direct float storage

## Open Questions

1. **Gain Interpretation**
   - What we know: Grid has gain_17x17 values ranging ~55-75
   - What's unclear: Are these raw gain factors, dB, or E-mu's internal format?
   - Recommendation: Treat as dB initially; validate against reference files

2. **Transform Parameter Usage**
   - What we know: Grid is 17x17 for Morph x Transform
   - What's unclear: How should Transform parameter map to Y-axis?
   - Recommendation: Implement as second morph dimension; may not be used for basic validation

3. **Reference File Frequency Mismatch**
   - What we know: Reference peaks at 221, 2019, 2686 Hz vs computed 2400, 2707 Hz
   - What's unclear: Source of ~200 Hz discrepancy
   - Recommendation: Verify reference capture settings; may be different filter preset

## Sources

### Primary (HIGH confidence)

- [US Patent 5,170,369](https://patents.google.com/patent/US5170369A/en) - E-mu coefficient encoding, cascade topology, B1'/B2' formulas
- [Audio EQ Cookbook](https://webaudio.github.io/Audio-EQ-Cookbook/audio-eq-cookbook.html) - Standard biquad coefficient formulas
- ZPLANE_RECREATION_SPEC_X3.md - Empirically captured X3 coefficients

### Secondary (MEDIUM confidence)

- [MIDI Tuning Standard](https://en.wikipedia.org/wiki/MIDI_tuning_standard) - Frequency-to-note conversion formula
- [Symbolic Sound Kyma Wiki](https://archive.symbolicsound.com/cgi-bin/bin/view/How/CreateEMUZ) - ARMAdillo algorithm description
- [Gearspace Forum](https://gearspace.com/board/electronic-music-instruments-and-electronic-music-production/1113702-emu-z-plane-filters-quot-emu-sound-quot-2.html) - Community Z-Plane implementation discussions

### Tertiary (LOW confidence - needs validation)

- Gain_17x17 interpretation - Assumed dB but unverified
- Transform axis behavior - Assumed standard Y-axis morph

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Industry standard libraries
- Architecture patterns: HIGH - Patent-verified formulas, empirical captures
- Pitfalls: HIGH - Documented in debug sessions and spec

**Research date:** 2026-01-19
**Valid until:** 2026-02-19 (30 days - stable domain, unlikely to change)

---

## Appendix A: E-mu Coefficient Encoding Reference

From US Patent 5,170,369:

```
ENCODE (for storage/interpolation):
  B1' = B1 + 2      (ensures positive values)
  B2' = 1 - B2      (concentrates resolution near unit circle)

DECODE (for rendering):
  B1 = B1' - 2
  B2 = 1 - B2'

Linear interpolation formula:
  C(x) = Ca + x(Cb - Ca)    where x = 0 to 1
```

**Modern equivalent:** Store frequency as semitones (logarithmic), interpolate linearly, convert to Hz only at render time. This achieves the same "logarithmic sweep" effect without the complexity of B1'/B2' encoding.

## Appendix B: Data Format Reference

The `talking_hedz_extracted.json` structure:

```json
{
  "name": "Talking Hedz",
  "format": "universal_3variant_grid",
  "variants": [
    {
      "id": 0,                    // Q variant (0=0%, 1=50%, 2=100%)
      "stages": [
        {
          "stage": 0,             // Stage index (0-6)
          "shape": "lp",          // "lp" or "eq"
          "freq_17x17": [...],    // 289 frequency values in Hz
          "gain_17x17": [...],    // 289 gain values
          "radius_17x17": [...]   // 289 radius values (0-1)
        },
        // ... stages 1-6
      ]
    },
    // ... variants 1-2
  ]
}
```

Grid indexing: `grid[row * 17 + col]` where row = transform (0-16), col = morph (0-16)
