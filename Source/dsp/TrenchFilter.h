#pragma once

#include "Biquad.h"
#include <array>
#include <cmath>

namespace Trench {

/**
 * TRENCH Z-Plane Formant Filter
 *
 * A 5-stage series cascade implementing E-mu Z-Plane morphing filter:
 * - Stages 0-3: PEAKING EQ resonators (flag=1) - boost at formant, unity elsewhere
 * - Stage 4: Lowpass filter for body/warmth (flag=0)
 *
 * Coefficients reverse-engineered from Emulator X3 "Talking Hedz" preset
 * via Cheat Engine memory capture, validated against audio references.
 *
 * CRITICAL TOPOLOGY NOTE:
 * For series cascade, stages MUST use Peaking EQ (not Bandpass).
 * Bandpass zeros at DC/Nyquist cause signal cancellation when cascaded.
 * Peaking EQ passes signal at unity gain away from resonance, allowing
 * multiple formant peaks to coexist in the output.
 */

constexpr int NUM_STAGES = 5;

// Captured coefficients from TalkingHedz.json
struct StageCoeffs {
    float a1;
    float radius;
    float flag;
};

// M0_Q100: Morph=0%, Q=100% ("Ah" vowel, full resonance)
constexpr std::array<StageCoeffs, NUM_STAGES> M0_Q100 = {{
    {-1.976510f, 0.998242f, 1.0f},  // Stage 0: 994 Hz resonator
    {-1.938977f, 0.998296f, 1.0f},  // Stage 1: 1690 Hz resonator
    {-1.872895f, 0.998353f, 1.0f},  // Stage 2: 2485 Hz resonator
    {-1.523842f, 0.992409f, 1.0f},  // Stage 3: 4881 Hz resonator
    {-1.997572f, 0.998289f, 0.0f}   // Stage 4: Lowpass (DC body)
}};

// M100_Q100: Morph=100%, Q=100% ("Ee" vowel, full resonance)
constexpr std::array<StageCoeffs, NUM_STAGES> M100_Q100 = {{
    {-1.996743f, 0.998619f, 1.0f},  // Stage 0: 156 Hz resonator
    {-1.894098f, 0.998437f, 1.0f},  // Stage 1: 2262 Hz resonator
    {-1.854829f, 0.998353f, 1.0f},  // Stage 2: 2662 Hz resonator
    {-1.495171f, 0.963737f, 1.0f},  // Stage 3: 4793 Hz resonator
    {-1.974292f, 0.998195f, 0.0f}   // Stage 4: 1045 Hz lowpass
}};

// M100_Q0: Morph=100%, Q=0% ("Ee" vowel, minimal resonance)
constexpr std::array<StageCoeffs, NUM_STAGES> M100_Q0 = {{
    {-1.986418f, 0.987503f, 1.0f},  // Stage 0: wider bandwidth
    {-1.837391f, 0.974537f, 1.0f},  // Stage 1: 2388 Hz
    {-1.794609f, 0.977806f, 1.0f},  // Stage 2: 2868 Hz
    {-1.362762f, 0.883514f, 1.0f},  // Stage 3: 4843 Hz
    {-1.914935f, 0.993960f, 0.0f}   // Stage 4: 1908 Hz lowpass
}};

class TrenchFilter {
public:
    TrenchFilter() {
        reset();
    }

    /**
     * Prepare the filter for playback
     */
    void prepare(float newSampleRate) {
        sampleRate = newSampleRate;
        updateCoefficients();
    }

    /**
     * Reset filter state (clear all delay lines)
     */
    void reset() {
        for (auto& stage : stages) {
            stage.reset();
        }
        phantomZ1 = 0.0f;
    }

    /**
     * Set morph position (0.0 = "Ah", 1.0 = "Ee")
     */
    void setMorph(float newMorph) {
        morph = std::fmax(0.0f, std::fmin(1.0f, newMorph));
        updateCoefficients();
    }

    /**
     * Set Q (resonance) parameter (0.0 = wide, 1.0 = narrow)
     */
    void setQ(float newQ) {
        qParam = std::fmax(0.0f, std::fmin(1.0f, newQ));
        updateCoefficients();
    }

    float getMorph() const { return morph; }
    float getQ() const { return qParam; }

    /**
     * Process a single sample through the cascade
     */
    float process(float input) {
        // Phantom 1-pole lowpass (anti-aliasing, ~20kHz)
        float x = input * 0.8f + phantomZ1 * 0.2f;
        phantomZ1 = x;

        // 5-stage cascade
        for (int i = 0; i < NUM_STAGES; ++i) {
            x = stages[i].process(x);
        }

        return x;
    }

    /**
     * Process a block of samples
     */
    void processBlock(float* buffer, int numSamples) {
        for (int i = 0; i < numSamples; ++i) {
            buffer[i] = process(buffer[i]);
        }
    }

    void processBlock(const float* input, float* output, int numSamples) {
        for (int i = 0; i < numSamples; ++i) {
            output[i] = process(input[i]);
        }
    }

private:
    /**
     * Linear interpolation
     */
    static float lerp(float a, float b, float t) {
        return a + t * (b - a);
    }

    /**
     * Interpolate between two coefficient sets
     */
    static StageCoeffs lerpCoeffs(const StageCoeffs& a, const StageCoeffs& b, float t) {
        return {
            lerp(a.a1, b.a1, t),
            lerp(a.radius, b.radius, t),
            a.flag  // Flag doesn't interpolate (stage type is fixed)
        };
    }

    /**
     * Update all filter coefficients based on current morph and Q
     *
     * Interpolation strategy:
     * - At Q=1.0: interpolate between M0_Q100 and M100_Q100 based on morph
     * - At Q=0.0: interpolate between M0_Q100 and M100_Q0 based on morph
     * - In between: blend the Q=1 and Q=0 results
     *
     * Note: This is simplified 2D interpolation. Full E-mu uses 3D cube
     * with trilinear interpolation on encoded v1/v2 values.
     */
    void updateCoefficients() {
        if (sampleRate <= 0.0f) return;

        for (int i = 0; i < NUM_STAGES; ++i) {
            // Q=1 path: M0_Q100 -> M100_Q100
            StageCoeffs highQ = lerpCoeffs(M0_Q100[i], M100_Q100[i], morph);

            // Q=0 path: M0_Q100 -> M100_Q0
            // Note: We don't have M0_Q0, so we scale radius from M0_Q100
            StageCoeffs lowQ;
            if (morph < 0.01f) {
                // At morph=0, scale radius down for lower Q
                lowQ = M0_Q100[i];
                lowQ.radius = lerp(0.9f, M0_Q100[i].radius, 0.5f);
            } else {
                lowQ = lerpCoeffs(M0_Q100[i], M100_Q0[i], morph);
            }

            // Blend between high Q and low Q based on qParam
            StageCoeffs final = lerpCoeffs(lowQ, highQ, qParam);

            // Apply to biquad using Z-Plane formulas (peaking EQ for flag=1)
            stages[i].setZPlaneStage(final.a1, final.radius, final.flag, sampleRate);
        }
    }

    // Filter stages
    std::array<Biquad, NUM_STAGES> stages;

    // Phantom 1-pole lowpass state
    float phantomZ1 = 0.0f;

    // Parameters
    float morph = 0.0f;
    float qParam = 1.0f;
    float sampleRate = 44100.0f;
};

} // namespace Trench
