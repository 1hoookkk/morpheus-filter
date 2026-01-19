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

} // namespace ZPlane
