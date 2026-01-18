#pragma once

#include <cmath>
#include <algorithm>
#include <array>
#include <vector>
#include <string>

namespace ZPlane {

//==============================================================================
// Stage Data - Raw coefficients from X3 memory capture
// This is PURE DATA - no implementation logic here
//==============================================================================
struct StageData {
    float a1;       // Captured feedback coefficient (already includes radius: -2*R*cos(theta))
    float radius;   // Pole radius (0 to 1)
    int flag;       // 0 = lowpass, 1 = bandpass (captured from X3 memory)
};

//==============================================================================
// Morph Keyframe - One snapshot of all 5 stages at a specific morph position
//==============================================================================
struct MorphKeyframe {
    float position;                     // 0.0 to 1.0
    std::array<StageData, 5> stages;    // 5 stages for X3 12-pole architecture
};

//==============================================================================
// Z-Plane Cartridge - Pure captured data (matches JSON structure)
//==============================================================================
struct ZPlaneCartridge {
    // Metadata
    std::string name;
    std::string source;
    float sampleRate = 44100.0f;

    // Captured keyframes (typically 5: 0%, 25%, 50%, 75%, 100%)
    std::vector<MorphKeyframe> keyframes;
};

//==============================================================================
// Biquad Coefficients - Computed for actual filtering (implementation detail)
//==============================================================================
struct BiquadCoeffs {
    float b0 = 0.0f, b1 = 0.0f, b2 = 0.0f;  // Numerator (zeros)
    float a1 = 0.0f, a2 = 0.0f;              // Denominator (poles)
};

//==============================================================================
// IMPLEMENTATION DETAILS BELOW - These live in code, not JSON
//==============================================================================

// Q Scaling Constants (captured empirically from X3)
// Q_MIN derived from captured data: at Q_knob=0%, Stage 3 radius=0.8867
// Back-calculation: Q_MIN = 100 / (log(r_ref)/log(r_0)) = 100/5.8 = 17.26
constexpr float Q_REF = 100.0f;         // Reference Q level (captured at Q=100%)
constexpr float Q_MIN = 17.0f;          // Minimum effective Q (NOT 0.5! - from X3 captures)
constexpr float RADIUS_FLOOR = 0.5f;    // Minimum radius (safety clamp)
constexpr float RADIUS_CEILING = 0.9999f; // Maximum radius (near instability)

//==============================================================================
// Q Scaling - Reduces radius from Q=100% reference
// Formula derived empirically from X3 Cheat Engine captures
//==============================================================================
inline float applyQToRadius(float r_ref, float Q_new) {
    if (Q_new <= 0.0f) return RADIUS_FLOOR;

    // Exponential scaling: lower Q = smaller radius = broader peaks
    float s = Q_REF / Q_new;
    float r = std::exp(std::log(std::max(r_ref, 1e-12f)) * s);

    // Clamp to valid range, never exceed reference
    return std::clamp(r, RADIUS_FLOOR, std::min(r_ref, RADIUS_CEILING));
}

//==============================================================================
// Compute Biquad Coefficients from captured stage data
// Numerator formula derived from flag byte
// IMPORTANT: We recompute a1 from the clamped angle to maintain stability.
// The ratio swap formula can produce unstable filters when the pole is near DC.
//==============================================================================
inline BiquadCoeffs computeBiquadCoeffs(const StageData& stage, float radiusScaled) {
    BiquadCoeffs c;

    // Extract the angle from captured coefficients
    // a1_captured = -2*R_orig*cos(theta) --> cos(theta) = -a1_captured / (2*R_orig)
    float origRadius = std::max(stage.radius, 1e-12f);  // Prevent division by zero
    float cosTheta = std::clamp(-stage.a1 / (2.0f * origRadius), -1.0f, 1.0f);

    // Reconstruct a1 with new radius (maintains stability for near-DC poles)
    c.a1 = -2.0f * radiusScaled * cosTheta;

    // a2 = radius squared
    c.a2 = radiusScaled * radiusScaled;

    // Numerator depends on flag (derived from captured data)
    if (stage.flag == 1) {
        // Bandpass/Peaking: zeros at DC (z=+1) and Nyquist (z=-1)
        float scale = (1.0f - c.a2) / 2.0f;
        c.b0 = scale;
        c.b1 = 0.0f;
        c.b2 = -scale;
    } else {
        // Lowpass/Body: zeros at Nyquist (z=-1)
        float norm = (1.0f + c.a1 + c.a2) / 4.0f;
        if (norm <= 0.0f) norm = 0.0001f;  // Prevent silence near DC
        c.b0 = norm;
        c.b1 = 2.0f * norm;
        c.b2 = norm;
    }

    return c;
}

//==============================================================================
// Utility: Get frequency in Hz from captured a1 and radius
// Formula: a1 = -2*R*cos(theta), so theta = acos(-a1 / (2*R))
//==============================================================================
inline float getFrequencyHz(float a1, float radius, float sampleRate) {
    float r = std::max(radius, 1e-12f);  // Prevent division by zero
    float cosTheta = std::clamp(-a1 / (2.0f * r), -1.0f, 1.0f);
    float theta = std::acos(cosTheta);
    return theta * sampleRate / (2.0f * 3.14159265359f);
}

} // namespace ZPlane
