#pragma once

#include <cmath>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

namespace Trench {

/**
 * Biquad filter using Direct Form II Transposed
 *
 * Transfer function: H(z) = (b0 + b1*z^-1 + b2*z^-2) / (1 + a1*z^-1 + a2*z^-2)
 *
 * DF-II Transposed is preferred for floating-point because:
 * - Better numerical behavior
 * - Lower noise/distortion
 * - Requires only 2 delay elements
 */
class Biquad {
public:
    Biquad() { reset(); }

    /**
     * Reset filter state (clear delay line)
     */
    void reset() {
        z1 = 0.0f;
        z2 = 0.0f;
    }

    /**
     * Set coefficients directly (already normalized by a0)
     */
    void setCoefficients(float _b0, float _b1, float _b2, float _a1, float _a2) {
        b0 = _b0;
        b1 = _b1;
        b2 = _b2;
        a1 = _a1;
        a2 = _a2;
    }

    /**
     * Configure as parametric/peaking EQ
     *
     * @param freq   Center frequency (Hz)
     * @param Q      Quality factor (higher = narrower)
     * @param gainDb Gain at center frequency (dB)
     * @param sampleRate Sample rate (Hz)
     */
    void setParametric(float freq, float Q, float gainDb, float sampleRate) {
        // Clamp frequency to valid range
        freq = std::fmax(20.0f, std::fmin(freq, sampleRate * 0.49f));
        Q = std::fmax(0.1f, Q);

        float A = std::sqrt(std::pow(10.0f, gainDb / 20.0f));
        float w0 = 2.0f * static_cast<float>(M_PI) * freq / sampleRate;
        float sinW0 = std::sin(w0);
        float cosW0 = std::cos(w0);
        float alpha = sinW0 / (2.0f * Q);

        float b0_raw = 1.0f + alpha * A;
        float b1_raw = -2.0f * cosW0;
        float b2_raw = 1.0f - alpha * A;
        float a0_raw = 1.0f + alpha / A;
        float a1_raw = -2.0f * cosW0;
        float a2_raw = 1.0f - alpha / A;

        // Normalize by a0
        float invA0 = 1.0f / a0_raw;
        b0 = b0_raw * invA0;
        b1 = b1_raw * invA0;
        b2 = b2_raw * invA0;
        a1 = a1_raw * invA0;
        a2 = a2_raw * invA0;
    }

    /**
     * Configure as lowpass filter
     *
     * @param freq   Cutoff frequency (Hz)
     * @param Q      Quality factor (0.707 = Butterworth)
     * @param sampleRate Sample rate (Hz)
     */
    void setLowpass(float freq, float Q, float sampleRate) {
        // Clamp frequency to valid range
        freq = std::fmax(20.0f, std::fmin(freq, sampleRate * 0.49f));
        Q = std::fmax(0.1f, Q);

        float w0 = 2.0f * static_cast<float>(M_PI) * freq / sampleRate;
        float sinW0 = std::sin(w0);
        float cosW0 = std::cos(w0);
        float alpha = sinW0 / (2.0f * Q);

        float b0_raw = (1.0f - cosW0) / 2.0f;
        float b1_raw = 1.0f - cosW0;
        float b2_raw = (1.0f - cosW0) / 2.0f;
        float a0_raw = 1.0f + alpha;
        float a1_raw = -2.0f * cosW0;
        float a2_raw = 1.0f - alpha;

        // Normalize by a0
        float invA0 = 1.0f / a0_raw;
        b0 = b0_raw * invA0;
        b1 = b1_raw * invA0;
        b2 = b2_raw * invA0;
        a1 = a1_raw * invA0;
        a2 = a2_raw * invA0;
    }

    /**
     * Configure as highpass filter
     *
     * @param freq   Cutoff frequency (Hz)
     * @param Q      Quality factor (0.707 = Butterworth)
     * @param sampleRate Sample rate (Hz)
     */
    void setHighpass(float freq, float Q, float sampleRate) {
        freq = std::fmax(20.0f, std::fmin(freq, sampleRate * 0.49f));
        Q = std::fmax(0.1f, Q);

        float w0 = 2.0f * static_cast<float>(M_PI) * freq / sampleRate;
        float sinW0 = std::sin(w0);
        float cosW0 = std::cos(w0);
        float alpha = sinW0 / (2.0f * Q);

        float b0_raw = (1.0f + cosW0) / 2.0f;
        float b1_raw = -(1.0f + cosW0);
        float b2_raw = (1.0f + cosW0) / 2.0f;
        float a0_raw = 1.0f + alpha;
        float a1_raw = -2.0f * cosW0;
        float a2_raw = 1.0f - alpha;

        float invA0 = 1.0f / a0_raw;
        b0 = b0_raw * invA0;
        b1 = b1_raw * invA0;
        b2 = b2_raw * invA0;
        a1 = a1_raw * invA0;
        a2 = a2_raw * invA0;
    }

    /**
     * Configure as bypass (unity gain, no filtering)
     */
    void setBypass() {
        b0 = 1.0f;
        b1 = 0.0f;
        b2 = 0.0f;
        a1 = 0.0f;
        a2 = 0.0f;
    }

    //=========================================================================
    // E-mu Z-Plane Filter Methods (from reverse engineering)
    //=========================================================================

    /**
     * Configure as E-mu Z-Plane CONSTANT PEAK GAIN resonator
     *
     * This is the authentic E-mu formula from the Z-Plane architecture:
     * - Zeros at DC (z=1) and Nyquist (z=-1) create bandpass character
     * - Peak gain normalized to ~1.0 regardless of Q/radius
     * - Matches X3 spectral character (validated: 14.84 dB RMS error)
     *
     * Note: In a series cascade, narrow bandpass stages will attenuate
     * frequencies outside their passband. This is the intended E-mu
     * behavior - the formant character comes from this attenuation.
     *
     * @param _a1         Feedback coefficient: -2*r*cos(theta) from capture
     * @param radius      Pole radius (Q control - closer to 1.0 = higher Q)
     */
    void setZPlaneResonator(float _a1, float radius) {
        // Denominator: poles at r*e^(±jθ)
        // Note: multiply captured a1 by radius for final biquad coefficient
        float a1_final = _a1 * radius;
        float _a2 = radius * radius;

        // Numerator: zeros at DC and Nyquist for bandpass character
        // Scale factor normalizes peak gain to ~1.0
        float scale = 1.0f - radius;  // Constant peak gain

        b0 = scale;
        b1 = 0.0f;
        b2 = -scale;
        a1 = a1_final;
        a2 = _a2;
    }

    /**
     * Configure as E-mu Z-Plane lowpass (unity DC gain)
     *
     * Standard 2-pole lowpass with two zeros at Nyquist (z=-1)
     * Provides 12 dB/octave rolloff and "body" for the filter
     *
     * @param _a1    Feedback coefficient (captured from E-mu)
     * @param radius Pole radius
     */
    void setZPlaneLowpass(float _a1, float radius) {
        // Match Python formula: multiply captured a1 by radius
        float a1_final = _a1 * radius;
        float _a2 = radius * radius;

        // Unity DC gain normalization
        float norm = (1.0f + a1_final + _a2) * 0.25f;

        b0 = norm;
        b1 = 2.0f * norm;
        b2 = norm;
        a1 = a1_final;
        a2 = _a2;
    }

    /**
     * Configure from E-mu captured coefficients with automatic type selection
     *
     * @param _a1        Feedback coefficient (-2*r*cos(theta) from capture)
     * @param radius     Pole radius
     * @param flag       Stage type: > 0.5 = resonator (bandpass), < 0.5 = lowpass
     */
    void setZPlaneStage(float _a1, float radius, float flag) {
        if (flag > 0.5f) {
            setZPlaneResonator(_a1, radius);
        } else {
            setZPlaneLowpass(_a1, radius);
        }
    }

    // Overload with sampleRate for API compatibility (sampleRate ignored)
    void setZPlaneStage(float _a1, float radius, float flag, float /*sampleRate*/) {
        setZPlaneStage(_a1, radius, flag);
    }

    /**
     * Process a single sample
     * Direct Form II Transposed:
     *   y[n] = b0*x[n] + z1
     *   z1   = b1*x[n] - a1*y[n] + z2
     *   z2   = b2*x[n] - a2*y[n]
     */
    float process(float input) {
        float output = b0 * input + z1;
        z1 = b1 * input - a1 * output + z2;
        z2 = b2 * input - a2 * output;
        return output;
    }

    // Coefficient accessors (for debugging/visualization)
    float getB0() const { return b0; }
    float getB1() const { return b1; }
    float getB2() const { return b2; }
    float getA1() const { return a1; }
    float getA2() const { return a2; }

private:
    // Coefficients (normalized, a0 = 1)
    float b0 = 1.0f;
    float b1 = 0.0f;
    float b2 = 0.0f;
    float a1 = 0.0f;
    float a2 = 0.0f;

    // State (delay line)
    float z1 = 0.0f;
    float z2 = 0.0f;
};

} // namespace Trench
