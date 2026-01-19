---
phase: 01-dsp-engine
plan: 03
type: execute
wave: 2
depends_on: ["01-01"]
files_modified:
  - Source/dsp/ZPlaneEngine.h
autonomous: true

must_haves:
  truths:
    - "7-stage cascade topology processes signal sequentially"
    - "Biquad coefficients computed from semitone data at control rate"
    - "Ultrasonic frequencies (>20kHz) bypass filter stage"
    - "Sample rate warping works for 48kHz and 96kHz"
  artifacts:
    - path: "Source/dsp/ZPlaneEngine.h"
      provides: "7-stage cascade filter processor"
      exports: ["ZPlane::ZPlaneEngine", "ZPlane::BiquadSection"]
      min_lines: 250
  key_links:
    - from: "ZPlaneEngine.process"
      to: "BiquadSection cascade"
      via: "sequential signal flow"
      pattern: "for.*NUM_STAGES.*processSample"
    - from: "calculateCoefficients"
      to: "GridInterpolator"
      via: "interpolateAllStages call"
      pattern: "interpolator.*interpolate"
    - from: "semitone data"
      to: "biquad coefficients"
      via: "semitoneToHz conversion"
      pattern: "semitoneToHz.*freqSemitone"
---

<objective>
Create the 7-stage cascade filter engine that processes audio using grid-interpolated coefficients.

Purpose: This is the core DSP - the filter that produces the Z-Plane sound. It must convert semitone grid data to biquad coefficients and process audio through a 7-stage cascade.

Output: `Source/dsp/ZPlaneEngine.h` with the complete filter processor.
</objective>

<context>
@.planning/phases/01-dsp-engine/01-CONTEXT.md (cascade topology, semitone storage)
@.planning/phases/01-dsp-engine/01-RESEARCH.md (biquad formulas, pitfalls)
@Source/dsp/GridInterpolator.h (data structures and interpolation)
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create biquad section and coefficient computation</name>
  <files>Source/dsp/ZPlaneEngine.h</files>
  <action>
Create `Source/dsp/ZPlaneEngine.h` with biquad processing:

```cpp
#pragma once

#include "GridInterpolator.h"
#include <array>
#include <cmath>

namespace ZPlane {

// Biquad coefficients (computed at control rate)
struct BiquadCoeffs {
    float b0 = 1.0f, b1 = 0.0f, b2 = 0.0f;  // Numerator (zeros)
    float a1 = 0.0f, a2 = 0.0f;              // Denominator (poles)
    bool bypass = false;                      // True if ultrasonic (passthrough)
};

// Biquad section - Direct Form II Transposed
// Most numerically stable for high-Q resonant filters
class BiquadSection {
public:
    void setCoefficients(const BiquadCoeffs& c) {
        coeffs = c;
    }

    void reset() {
        z1 = 0.0f;
        z2 = 0.0f;
    }

    float processSample(float x) {
        if (coeffs.bypass) {
            return x;  // Ultrasonic stage - passthrough
        }

        // Direct Form II Transposed
        float y = coeffs.b0 * x + z1;
        z1 = coeffs.b1 * x - coeffs.a1 * y + z2;
        z2 = coeffs.b2 * x - coeffs.a2 * y;
        return y;
    }

    const BiquadCoeffs& getCoefficients() const { return coeffs; }

private:
    BiquadCoeffs coeffs;
    float z1 = 0.0f;
    float z2 = 0.0f;
};

// Compute biquad coefficients from grid stage data
// Source: US Patent 5,170,369 and Audio EQ Cookbook
inline BiquadCoeffs computeBiquadFromStage(const GridStageData& stage, float sampleRate) {
    BiquadCoeffs c;

    // Convert semitone to Hz
    float freqHz = semitoneToHz(stage.freqSemitone);

    // Check for ultrasonic - bypass if >20kHz (DSP-06)
    if (freqHz > 20000.0f || isUltrasonic(stage.freqSemitone)) {
        c.bypass = true;
        c.b0 = 1.0f;
        c.b1 = c.b2 = c.a1 = c.a2 = 0.0f;
        return c;
    }

    // Compute omega (normalized angular frequency)
    float omega = 2.0f * 3.14159265359f * freqHz / sampleRate;

    // Clamp to valid range (must be < pi for stability)
    omega = std::clamp(omega, 0.001f, 3.1f);

    float cosOmega = std::cos(omega);
    float radius = std::clamp(stage.radius, 0.0f, 0.9999f);

    // Denominator (poles) - same for all filter types
    c.a1 = -2.0f * radius * cosOmega;
    c.a2 = radius * radius;

    // Numerator (zeros) - depends on shape
    if (stage.shape == 0) {
        // LOWPASS (LP): zeros at Nyquist (z = -1)
        // Unity DC gain normalization
        float dcGain = 1.0f + c.a1 + c.a2;
        float norm = dcGain / 4.0f;
        norm = std::max(norm, 0.0001f);  // Prevent silence near DC (Pitfall 2)

        c.b0 = norm;
        c.b1 = 2.0f * norm;
        c.b2 = norm;
    }
    else {
        // EQ/BANDPASS: zeros at DC (z = +1) and Nyquist (z = -1)
        // Unity peak gain at resonance
        float scale = (1.0f - c.a2) / 2.0f;

        // Apply gain boost/cut from grid data
        float gainLinear = std::pow(10.0f, stage.gainDb / 20.0f);

        c.b0 = scale * gainLinear;
        c.b1 = 0.0f;
        c.b2 = -scale * gainLinear;
    }

    c.bypass = false;
    return c;
}

} // namespace ZPlane
```

Key implementation notes from RESEARCH.md:
- Direct Form II Transposed is most stable for high-Q
- LP normalization: `(1 + a1 + a2) / 4` - clamp to prevent silence (Pitfall 2)
- EQ/BP: zeros at DC and Nyquist for bandpass response
- Ultrasonic bypass prevents artifacts from impossible frequencies (DSP-06)
  </action>
  <verify>
File contains:
- `BiquadCoeffs` struct with bypass flag
- `BiquadSection` class with DFII-T implementation
- `computeBiquadFromStage()` with LP and EQ numerator formulas
- Ultrasonic check (>20kHz) sets bypass=true
  </verify>
  <done>Biquad computation implemented with LP/EQ formulas and ultrasonic bypass</done>
</task>

<task type="auto">
  <name>Task 2: Implement 7-stage cascade engine</name>
  <files>Source/dsp/ZPlaneEngine.h</files>
  <action>
Add the main ZPlaneEngine class to `ZPlaneEngine.h`:

```cpp
namespace ZPlane {

class ZPlaneEngine {
public:
    static constexpr float DEFAULT_SAMPLE_RATE = 44100.0f;

    ZPlaneEngine() = default;

    // Set sample rate (for coefficient computation)
    void setSampleRate(float fs) {
        sampleRate = fs;
        coefficientsValid = false;
    }

    // Set cartridge and interpolator
    void setCartridge(const ZPlaneCartridge* cart) {
        interpolator.setCartridge(cart);
        coefficientsValid = false;
    }

    // Set filter parameters
    // morph: 0-1 (Morph knob)
    // q: 0-1 (Q knob, interpolates between 3 variants)
    // transform: 0-1 (Transform parameter, typically 0 for Talking Hedz)
    void setParameters(float morph, float q, float transform = 0.0f) {
        if (morph != currentMorph || q != currentQ || transform != currentTransform) {
            currentMorph = std::clamp(morph, 0.0f, 1.0f);
            currentQ = std::clamp(q, 0.0f, 1.0f);
            currentTransform = std::clamp(transform, 0.0f, 1.0f);
            coefficientsValid = false;
        }
    }

    // Reset filter state (clear all delay lines)
    void reset() {
        for (auto& section : sections) {
            section.reset();
        }
    }

    // Update coefficients from current parameters
    // Call this at control rate (every 32-128 samples), NOT per sample
    void updateCoefficients() {
        if (coefficientsValid) return;

        // Get interpolated stage data for all 7 stages
        auto stages = interpolator.interpolateAllStages(currentMorph, currentTransform, currentQ);

        // Compute biquad coefficients for each stage
        for (int i = 0; i < NUM_STAGES; ++i) {
            BiquadCoeffs coeffs = computeBiquadFromStage(stages[i], sampleRate);
            sections[i].setCoefficients(coeffs);
        }

        coefficientsValid = true;
    }

    // Process single sample through 7-stage CASCADE
    // Topology: signal flows stage0 -> stage1 -> ... -> stage6
    float processSample(float input) {
        float signal = input;
        for (int i = 0; i < NUM_STAGES; ++i) {
            signal = sections[i].processSample(signal);
        }
        return signal;
    }

    // Process block of samples
    void processBlock(float* buffer, int numSamples) {
        // Update coefficients once per block (control rate)
        updateCoefficients();

        for (int i = 0; i < numSamples; ++i) {
            buffer[i] = processSample(buffer[i]);
        }
    }

    // Process block with separate input/output buffers
    void processBlock(const float* input, float* output, int numSamples) {
        updateCoefficients();

        for (int i = 0; i < numSamples; ++i) {
            output[i] = processSample(input[i]);
        }
    }

    // Accessors for debugging
    float getMorph() const { return currentMorph; }
    float getQ() const { return currentQ; }
    float getTransform() const { return currentTransform; }
    const BiquadSection& getSection(int idx) const {
        return sections[std::clamp(idx, 0, NUM_STAGES - 1)];
    }

private:
    GridInterpolator interpolator;
    std::array<BiquadSection, NUM_STAGES> sections;

    float sampleRate = DEFAULT_SAMPLE_RATE;
    float currentMorph = 0.5f;
    float currentQ = 0.5f;
    float currentTransform = 0.0f;
    bool coefficientsValid = false;
};

} // namespace ZPlane
```

Critical implementation notes:
- CASCADE TOPOLOGY (DSP-05): Signal flows through all 7 stages in series
- Coefficient update at CONTROL RATE (not per sample) per RESEARCH.md
- `coefficientsValid` flag prevents redundant recomputation
- Parameters are 0-1 normalized (matches JUCE parameter conventions)
  </action>
  <verify>
ZPlaneEngine class contains:
- 7 BiquadSections (`std::array<BiquadSection, NUM_STAGES>`)
- `setParameters(morph, q, transform)` method
- `updateCoefficients()` with `interpolateAllStages` call
- `processSample()` with cascade loop (stage 0 to 6)
- `processBlock()` calling `updateCoefficients()` once per block
  </verify>
  <done>7-stage cascade engine processes audio with parameter-driven interpolation</done>
</task>

<task type="auto">
  <name>Task 3: Add sample rate warping support</name>
  <files>Source/dsp/ZPlaneEngine.h</files>
  <action>
Update `computeBiquadFromStage()` to handle sample rate warping (DSP-07).

The key insight from RESEARCH.md: Because we store frequencies in semitones (absolute pitch) and convert to Hz at render time, sample rate handling is largely automatic via the omega calculation: `omega = 2 * pi * f / fs`.

However, we need to ensure frequencies near Nyquist are handled correctly:

```cpp
// Update the computeBiquadFromStage function:
inline BiquadCoeffs computeBiquadFromStage(const GridStageData& stage, float sampleRate) {
    BiquadCoeffs c;

    // Convert semitone to Hz
    float freqHz = semitoneToHz(stage.freqSemitone);

    // Nyquist limit for this sample rate
    float nyquist = sampleRate / 2.0f;

    // Check for ultrasonic - bypass if frequency > Nyquist or > 20kHz (DSP-06)
    if (freqHz > nyquist * 0.95f || freqHz > 20000.0f) {
        c.bypass = true;
        c.b0 = 1.0f;
        c.b1 = c.b2 = c.a1 = c.a2 = 0.0f;
        return c;
    }

    // Compute omega (normalized angular frequency)
    // This naturally handles sample rate differences:
    // - At 44.1kHz: 1kHz -> omega = 0.142
    // - At 96kHz: 1kHz -> omega = 0.065 (lower, preserves analog frequency)
    float omega = 2.0f * 3.14159265359f * freqHz / sampleRate;

    // Safety clamp: omega must be < pi for stability
    omega = std::clamp(omega, 0.001f, 3.1f);

    // ... rest of function unchanged ...
}
```

Also add a helper to ZPlaneEngine for getting stage info (useful for debugging and visualization):

```cpp
// Add to ZPlaneEngine class:

// Get current stage frequencies (for visualization/debugging)
std::array<float, NUM_STAGES> getStageFrequencies() const {
    std::array<float, NUM_STAGES> freqs;
    auto stages = interpolator.interpolateAllStages(currentMorph, currentTransform, currentQ);
    for (int i = 0; i < NUM_STAGES; ++i) {
        freqs[i] = semitoneToHz(stages[i].freqSemitone);
    }
    return freqs;
}

// Get bypass state for each stage
std::array<bool, NUM_STAGES> getStageBypassStates() const {
    std::array<bool, NUM_STAGES> bypassed;
    for (int i = 0; i < NUM_STAGES; ++i) {
        bypassed[i] = sections[i].getCoefficients().bypass;
    }
    return bypassed;
}
```
  </action>
  <verify>
1. `computeBiquadFromStage` includes Nyquist check (`freqHz > nyquist * 0.95f`)
2. omega computation uses runtime `sampleRate` parameter
3. `getStageFrequencies()` helper method exists
4. Bypass logic triggers for both >20kHz and >Nyquist cases
  </verify>
  <done>Sample rate warping works for 44.1kHz, 48kHz, and 96kHz</done>
</task>

</tasks>

<verification>
1. File structure: `Source/dsp/ZPlaneEngine.h` exists with ~300 lines
2. Stage count: `NUM_STAGES` = 7 (not 5 like old implementation)
3. Cascade topology: `processSample` loops through stages sequentially
4. Coefficient update: `updateCoefficients` calls `interpolateAllStages`
5. Ultrasonic bypass: Frequencies >20kHz or >Nyquist set `bypass = true`
6. Sample rate: omega calculation uses runtime sample rate
</verification>

<success_criteria>
- ZPlaneEngine.h compiles without errors
- 7 stages in cascade (not 5)
- Biquad coefficients computed from semitone data via `computeBiquadFromStage`
- LP and EQ numerator formulas correct per RESEARCH.md
- Ultrasonic stages bypass (passthrough) per DSP-06
- Sample rate parameter affects omega calculation per DSP-07
- Coefficient update happens at control rate (once per block)
</success_criteria>

<output>
After completion, create `.planning/phases/01-dsp-engine/01-03-SUMMARY.md`
</output>
