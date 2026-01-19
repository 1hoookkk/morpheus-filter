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
//==============================================================================
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

} // namespace ZPlane
