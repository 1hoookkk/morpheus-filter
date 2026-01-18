#pragma once

#include "ZPlaneData.h"
#include <array>
#include <cmath>

namespace ZPlane {

//==============================================================================
// Biquad Section - Direct Form II Transposed
// Most numerically stable form for high-Q resonant filters
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
// Z-Plane Filter - 5 Biquad CASCADE Topology (Per E-mu Patents & Documentation)
// Topology: CASCADE (series) - signal flows through stages sequentially
// Source: US Patent 5,170,369 and 5,248,845, Proteus X Manual, Advanced Apps Guide
// Note: Previous session incorrectly used PARALLEL due to faulty validation analysis
//==============================================================================
class ZPlaneFilter {
public:
    static constexpr int NUM_STAGES = 5;
    static constexpr float CAPTURED_SAMPLE_RATE = 44100.0f;

    ZPlaneFilter() = default;

    //--------------------------------------------------------------------------
    // Set runtime sample rate (for frequency warping if needed)
    //--------------------------------------------------------------------------
    void setSampleRate(float fs) {
        runtimeSampleRate = fs;
    }

    //--------------------------------------------------------------------------
    // Load cartridge data
    //--------------------------------------------------------------------------
    void setCartridge(const ZPlaneCartridge& cart) {
        cartridge = cart;
        reset();
    }

    //--------------------------------------------------------------------------
    // Reset filter state (clear delay lines)
    //--------------------------------------------------------------------------
    void reset() {
        for (auto& section : sections) {
            section.reset();
        }
    }

    //--------------------------------------------------------------------------
    // Update coefficients for given morph and Q positions
    // morph: 0.0 to 1.0 (EE to AH vowel)
    // q: 0.0 to 1.0 (maps to Q_MIN to Q_REF)
    //--------------------------------------------------------------------------
    void calculateCoefficients(float morph, float q) {
        if (cartridge.keyframes.empty()) return;

        morph = std::clamp(morph, 0.0f, 1.0f);
        q = std::clamp(q, 0.0f, 1.0f);

        // Find bracketing keyframes for interpolation
        const MorphKeyframe* kfA = &cartridge.keyframes.front();
        const MorphKeyframe* kfB = &cartridge.keyframes.back();
        float t = 0.0f;

        for (size_t i = 0; i < cartridge.keyframes.size() - 1; ++i) {
            if (morph >= cartridge.keyframes[i].position &&
                morph <= cartridge.keyframes[i + 1].position) {
                kfA = &cartridge.keyframes[i];
                kfB = &cartridge.keyframes[i + 1];

                float range = kfB->position - kfA->position;
                t = (range > 0.0f) ? (morph - kfA->position) / range : 0.0f;
                break;
            }
        }

        // Convert Q knob (0-1) to actual Q value using EXPONENTIAL mapping
        // Derived from X3 captures: Q_knob=0% -> Q_actual=17, Q_knob=100% -> Q_actual=100
        // This produces logarithmic Q scaling that matches X3 behavior
        float Q_actual = Q_MIN * std::pow(Q_REF / Q_MIN, q);

        // Compute coefficients for each stage
        for (int i = 0; i < NUM_STAGES; ++i) {
            // Interpolate stage data between keyframes
            StageData interpolated;
            interpolated.a1 = lerp(kfA->stages[i].a1, kfB->stages[i].a1, t);
            interpolated.radius = lerp(kfA->stages[i].radius, kfB->stages[i].radius, t);
            interpolated.flag = kfA->stages[i].flag;  // Flag doesn't interpolate

            // Warp a1 for sample rate conversion (if runtime != captured rate)
            interpolated.a1 = warpA1ForSampleRate(interpolated.a1, interpolated.radius);

            // Apply Q scaling to radius
            float radiusScaled = applyQToRadius(interpolated.radius, Q_actual);

            // Compute biquad coefficients
            BiquadCoeffs coeffs = computeBiquadCoeffs(interpolated, radiusScaled);
            sections[i].setCoefficients(coeffs);
        }
    }

    //--------------------------------------------------------------------------
    // Process single sample through CASCADE topology (Per E-mu Patents)
    //--------------------------------------------------------------------------
    float processSample(float input) {
        // CASCADE TOPOLOGY (per US Patent 5,170,369, Proteus X Manual)
        // Signal flows through stages in series: 1 -> 2 -> 3 -> 4 -> 5
        // Each stage's output becomes the next stage's input
        float signal = input;
        for (int i = 0; i < NUM_STAGES; ++i) {
            signal = sections[i].processSample(signal);
        }
        return signal;
    }

    //--------------------------------------------------------------------------
    // Process buffer
    //--------------------------------------------------------------------------
    void processBlock(float* buffer, int numSamples) {
        for (int i = 0; i < numSamples; ++i) {
            buffer[i] = processSample(buffer[i]);
        }
    }

    //--------------------------------------------------------------------------
    // Accessors
    //--------------------------------------------------------------------------
    const BiquadSection& getSection(int index) const {
        return sections[std::clamp(index, 0, NUM_STAGES - 1)];
    }

    const ZPlaneCartridge& getCartridge() const { return cartridge; }

private:
    static float lerp(float a, float b, float t) {
        return a + (b - a) * t;
    }

    //--------------------------------------------------------------------------
    // Warp a1 coefficient for sample rate conversion
    // Uses bilinear transform frequency warping
    //--------------------------------------------------------------------------
    float warpA1ForSampleRate(float a1_captured, float radius) const {
        if (std::abs(runtimeSampleRate - CAPTURED_SAMPLE_RATE) < 1.0f) {
            return a1_captured;  // No warping needed
        }

        // Extract original frequency from captured a1
        float origRadius = std::max(radius, 1e-12f);
        float cosTheta = std::clamp(-a1_captured / (2.0f * origRadius), -1.0f, 1.0f);
        float theta = std::acos(cosTheta);
        float freqHz = theta * CAPTURED_SAMPLE_RATE / (2.0f * 3.14159265359f);

        // Compute new theta for runtime sample rate
        float newTheta = 2.0f * 3.14159265359f * freqHz / runtimeSampleRate;
        newTheta = std::clamp(newTheta, 0.0f, 3.14159265359f);  // Clamp to valid range

        // Reconstruct a1 with new theta
        return -2.0f * origRadius * std::cos(newTheta);
    }

    ZPlaneCartridge cartridge;
    std::array<BiquadSection, NUM_STAGES> sections;
    float runtimeSampleRate = CAPTURED_SAMPLE_RATE;
};

} // namespace ZPlane
