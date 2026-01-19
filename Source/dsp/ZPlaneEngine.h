#pragma once

#include "GridInterpolator.h"
#include <array>
#include <cmath>
#include <algorithm>

namespace ZPlane {

//==============================================================================
// BiquadCoeffs - Computed filter coefficients (computed at control rate)
//==============================================================================
struct BiquadCoeffs {
    float b0 = 1.0f, b1 = 0.0f, b2 = 0.0f;  // Numerator (zeros)
    float a1 = 0.0f, a2 = 0.0f;              // Denominator (poles)
    bool bypass = false;                      // True if ultrasonic (passthrough)
};

//==============================================================================
// BiquadSection - Direct Form II Transposed
// Most numerically stable for high-Q resonant filters
//==============================================================================
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

//==============================================================================
// Compute biquad coefficients from grid stage data
// Source: US Patent 5,170,369 and Audio EQ Cookbook
//
// Sample rate handling (DSP-07):
// Because we store frequencies in semitones (absolute pitch) and convert to Hz
// at render time, sample rate handling is automatic via the omega calculation:
//   omega = 2 * pi * f / fs
//
// At 44.1kHz: 1kHz -> omega = 0.142
// At 96kHz:   1kHz -> omega = 0.065 (lower, preserves analog frequency)
//==============================================================================
inline BiquadCoeffs computeBiquadFromStage(const GridStageData& stage, float sampleRate) {
    BiquadCoeffs c;

    // Convert semitone to Hz
    float freqHz = semitoneToHz(stage.freqSemitone);

    // Nyquist limit for this sample rate
    float nyquist = sampleRate / 2.0f;

    // Check for ultrasonic - bypass if:
    // 1. Frequency > 95% of Nyquist (too close to aliasing)
    // 2. Frequency > 20kHz (inaudible)
    // This handles both DSP-06 (ultrasonic bypass) and DSP-07 (sample rate warping)
    if (freqHz > nyquist * 0.95f || freqHz > 20000.0f) {
        c.bypass = true;
        c.b0 = 1.0f;
        c.b1 = c.b2 = c.a1 = c.a2 = 0.0f;
        return c;
    }

    // Compute omega (normalized angular frequency)
    // This naturally handles sample rate differences - same Hz value produces
    // different omega at different sample rates, preserving analog frequency
    constexpr float PI = 3.14159265359f;
    float omega = 2.0f * PI * freqHz / sampleRate;

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

//==============================================================================
// ZPlaneEngine - 7-stage cascade filter processor
//
// The Z-Plane filter is a CASCADE of 7 biquad sections. Signal flows
// sequentially through all stages: stage0 -> stage1 -> ... -> stage6
//
// Coefficient update happens at CONTROL RATE (once per block), not per sample.
// This matches the original hardware behavior and saves CPU.
//==============================================================================
class ZPlaneEngine {
public:
    static constexpr float DEFAULT_SAMPLE_RATE = 44100.0f;

    ZPlaneEngine() = default;

    //--------------------------------------------------------------------------
    // Configuration
    //--------------------------------------------------------------------------

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

    //--------------------------------------------------------------------------
    // State management
    //--------------------------------------------------------------------------

    // Reset filter state (clear all delay lines)
    void reset() {
        for (auto& section : sections) {
            section.reset();
        }
    }

    //--------------------------------------------------------------------------
    // Coefficient update (call at control rate)
    //--------------------------------------------------------------------------

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

    //--------------------------------------------------------------------------
    // Audio processing
    //--------------------------------------------------------------------------

    // Process single sample through 7-stage CASCADE
    // Topology: signal flows stage0 -> stage1 -> ... -> stage6
    float processSample(float input) {
        float signal = input;
        for (int i = 0; i < NUM_STAGES; ++i) {
            signal = sections[i].processSample(signal);
        }
        return signal;
    }

    // Process block of samples (in-place)
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

    //--------------------------------------------------------------------------
    // Accessors for debugging and visualization
    //--------------------------------------------------------------------------

    float getMorph() const { return currentMorph; }
    float getQ() const { return currentQ; }
    float getTransform() const { return currentTransform; }
    float getSampleRate() const { return sampleRate; }

    const BiquadSection& getSection(int idx) const {
        return sections[std::clamp(idx, 0, NUM_STAGES - 1)];
    }

    // Get current stage frequencies in Hz (for visualization/debugging)
    // Uses current morph/transform/q parameters to interpolate grid
    std::array<float, NUM_STAGES> getStageFrequencies() const {
        std::array<float, NUM_STAGES> freqs;
        auto stages = interpolator.interpolateAllStages(currentMorph, currentTransform, currentQ);
        for (int i = 0; i < NUM_STAGES; ++i) {
            freqs[i] = semitoneToHz(stages[i].freqSemitone);
        }
        return freqs;
    }

    // Get bypass state for each stage (true = ultrasonic, passthrough)
    std::array<bool, NUM_STAGES> getStageBypassStates() const {
        std::array<bool, NUM_STAGES> bypassed;
        for (int i = 0; i < NUM_STAGES; ++i) {
            bypassed[i] = sections[i].getCoefficients().bypass;
        }
        return bypassed;
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
