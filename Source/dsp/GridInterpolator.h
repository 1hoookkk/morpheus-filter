#pragma once

#include <array>
#include <string>
#include <cmath>
#include <algorithm>

namespace ZPlane {

//==============================================================================
// Constants
//==============================================================================
constexpr float C5_HZ = 523.251f;           // MIDI note 72 - capture reference
constexpr int NUM_STAGES = 7;               // 7-stage cascade
constexpr int GRID_SIZE = 17;               // 17x17 morph grid
constexpr int NUM_VARIANTS = 3;             // Q variants (0%, 50%, 100%)

//==============================================================================
// Hz/Semitone Conversion Utilities
//
// Semitone space is logarithmic frequency space relative to C5.
// This enables linear interpolation to produce logarithmic frequency sweeps
// (the "Rossum sweep" effect from E-mu patents).
//
// Examples:
//   C5 (523 Hz) -> 0 semitones
//   C6 (1046 Hz) -> +12 semitones
//   C4 (262 Hz) -> -12 semitones
//   A4 (440 Hz) -> -3 semitones
//==============================================================================

// Hz to semitones relative to C5
inline float hzToSemitone(float hz) {
    if (hz <= 0.0f) return -120.0f;  // Effectively DC, maps to inaudible
    return 12.0f * std::log2(hz / C5_HZ);
}

// Semitones to Hz
inline float semitoneToHz(float semitone) {
    return C5_HZ * std::pow(2.0f, semitone / 12.0f);
}

// Check if frequency is ultrasonic (>20kHz, should bypass)
// 20kHz in semitones relative to C5: 12 * log2(20000/523.25) = ~63.3
inline bool isUltrasonic(float semitone) {
    return semitone > 63.3f;
}

//==============================================================================
// GridStageData - Per-stage data at a single grid cell (stored in semitone space)
//==============================================================================
struct GridStageData {
    float freqSemitone;    // Frequency in semitones relative to C5
    float radius;          // Pole radius 0-1
    float gainDb;          // Gain in dB
    int shape;             // 0=LP, 1=EQ (bandpass)
};

//==============================================================================
// ZPlaneCartridge - Complete cartridge with 3 variants x 7 stages x 289 grid cells
//
// Data layout: [variant][stage][gridIndex]
// gridIndex = row * 17 + col (row=transform, col=morph)
//==============================================================================
struct ZPlaneCartridge {
    std::string name;

    // Data layout: [variant][stage][gridIndex]
    // variant: 0=Q0%, 1=Q50%, 2=Q100%
    // stage: 0-6 (7 cascade stages)
    // gridIndex: row * 17 + col where row=transform (0-16), col=morph (0-16)
    std::array<std::array<std::array<GridStageData, GRID_SIZE * GRID_SIZE>, NUM_STAGES>, NUM_VARIANTS> data;

    bool isLoaded = false;
};

//==============================================================================
// GridInterpolator - Trilinear interpolation across Morph x Transform x Q
//
// The 17x17x3 grid requires interpolation in 3 dimensions:
//   Morph (X): 0-1 maps to columns 0-16
//   Transform (Y): 0-1 maps to rows 0-16
//   Q (Z): 0-1 maps to variants 0-2
//
// All interpolation happens in SEMITONE SPACE - this is key to achieving
// the "Rossum sweep" effect where linear interpolation produces logarithmic
// frequency motion.
//==============================================================================
class GridInterpolator {
public:
    // Set the cartridge to interpolate from
    void setCartridge(const ZPlaneCartridge* cart) {
        cartridge = cart;
    }

    // Interpolate stage data at given position
    // morph: 0-1 (X-axis, columns)
    // transform: 0-1 (Y-axis, rows) - typically fixed at 0 for Talking Hedz
    // q: 0-1 (Z-axis, interpolates between 3 variants)
    GridStageData interpolate(int stageIdx, float morph, float transform, float q) const {
        if (!cartridge || !cartridge->isLoaded) {
            return GridStageData{0.0f, 0.5f, 0.0f, 0};
        }

        // Clamp inputs to valid range
        morph = std::clamp(morph, 0.0f, 1.0f);
        transform = std::clamp(transform, 0.0f, 1.0f);
        q = std::clamp(q, 0.0f, 1.0f);

        // Map 0-1 to grid indices
        float gx = morph * (GRID_SIZE - 1);      // 0-16
        float gy = transform * (GRID_SIZE - 1);  // 0-16
        float gz = q * (NUM_VARIANTS - 1);       // 0-2

        // Integer indices (clamped for interpolation base)
        int ix = std::clamp(static_cast<int>(gx), 0, GRID_SIZE - 2);
        int iy = std::clamp(static_cast<int>(gy), 0, GRID_SIZE - 2);
        int iz = std::clamp(static_cast<int>(gz), 0, NUM_VARIANTS - 2);

        // Fractional parts
        float fx = gx - ix;
        float fy = gy - iy;
        float fz = gz - iz;

        // Lambda to sample a grid cell
        auto sample = [&](int vi, int row, int col) -> const GridStageData& {
            int gridIdx = row * GRID_SIZE + col;
            return cartridge->data[vi][stageIdx][gridIdx];
        };

        // Lambda for linear interpolation of stage data (in semitone space)
        auto lerpStage = [](const GridStageData& a, const GridStageData& b, float t) {
            GridStageData result;
            result.freqSemitone = a.freqSemitone + (b.freqSemitone - a.freqSemitone) * t;
            result.radius = a.radius + (b.radius - a.radius) * t;
            result.gainDb = a.gainDb + (b.gainDb - a.gainDb) * t;
            result.shape = a.shape;  // Shape doesn't interpolate (discrete)
            return result;
        };

        //----------------------------------------------------------------------
        // 8-corner trilinear interpolation
        //----------------------------------------------------------------------

        // Bottom face (variant iz)
        GridStageData c00 = lerpStage(sample(iz, iy, ix), sample(iz, iy, ix+1), fx);
        GridStageData c01 = lerpStage(sample(iz, iy+1, ix), sample(iz, iy+1, ix+1), fx);
        GridStageData c0 = lerpStage(c00, c01, fy);

        // Top face (variant iz+1)
        GridStageData c10 = lerpStage(sample(iz+1, iy, ix), sample(iz+1, iy, ix+1), fx);
        GridStageData c11 = lerpStage(sample(iz+1, iy+1, ix), sample(iz+1, iy+1, ix+1), fx);
        GridStageData c1 = lerpStage(c10, c11, fy);

        // Interpolate between variants (Q axis)
        return lerpStage(c0, c1, fz);
    }

    // Convenience: get all 7 stages at once
    std::array<GridStageData, NUM_STAGES> interpolateAllStages(float morph, float transform, float q) const {
        std::array<GridStageData, NUM_STAGES> result;
        for (int i = 0; i < NUM_STAGES; ++i) {
            result[i] = interpolate(i, morph, transform, q);
        }
        return result;
    }

private:
    const ZPlaneCartridge* cartridge = nullptr;
};

} // namespace ZPlane
