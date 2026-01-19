---
phase: 01-dsp-engine
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - Source/dsp/GridInterpolator.h
autonomous: true

must_haves:
  truths:
    - "Grid data stores frequencies in semitone space relative to C5"
    - "Trilinear interpolation across Morph x Transform x Q dimensions works"
    - "Hz/semitone conversion produces correct values"
  artifacts:
    - path: "Source/dsp/GridInterpolator.h"
      provides: "17x17x3 grid data structures and trilinear interpolation"
      exports: ["ZPlane::GridStageData", "ZPlane::ZPlaneCartridge", "ZPlane::GridInterpolator"]
      min_lines: 200
  key_links:
    - from: "GridInterpolator"
      to: "ZPlaneCartridge data"
      via: "trilinear lookup"
      pattern: "interpolateGrid.*morph.*transform.*q"
---

<objective>
Create the grid-based data structures and trilinear interpolation for the Z-Plane filter.

Purpose: This is the foundation that all other DSP components depend on. The semitone-space storage is critical for achieving the "Rossum sweep" effect where linear interpolation produces logarithmic frequency motion.

Output: `Source/dsp/GridInterpolator.h` containing data structures, Hz/semitone conversion, and trilinear interpolation.
</objective>

<context>
@.planning/phases/01-dsp-engine/01-CONTEXT.md
@.planning/phases/01-dsp-engine/01-RESEARCH.md
@talking_hedz_extracted.json (reference for data format)
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create grid data structures with semitone storage</name>
  <files>Source/dsp/GridInterpolator.h</files>
  <action>
Create `Source/dsp/GridInterpolator.h` with the following data structures:

```cpp
namespace ZPlane {

// Constants
constexpr float C5_HZ = 523.251f;           // MIDI note 72 - capture reference
constexpr int NUM_STAGES = 7;               // 7-stage cascade
constexpr int GRID_SIZE = 17;               // 17x17 morph grid
constexpr int NUM_VARIANTS = 3;             // Q variants (0%, 50%, 100%)

// Per-stage data at a single grid cell (stored in semitone space)
struct GridStageData {
    float freqSemitone;    // Frequency in semitones relative to C5
    float radius;          // Pole radius 0-1
    float gainDb;          // Gain in dB
    int shape;             // 0=LP, 1=EQ (bandpass)
};

// Complete cartridge with 3 variants x 7 stages x 289 grid cells
struct ZPlaneCartridge {
    std::string name;

    // Data layout: [variant][stage][gridIndex]
    // gridIndex = row * 17 + col (row=transform, col=morph)
    std::array<std::array<std::array<GridStageData, GRID_SIZE * GRID_SIZE>, NUM_STAGES>, NUM_VARIANTS> data;

    bool isLoaded = false;
};

} // namespace ZPlane
```

Key requirements:
- Use `std::array` for fixed-size grid (compile-time known)
- Store frequencies in semitones (NOT Hz) - this is critical per CONTEXT.md
- Shape field uses int (0=LP, 1=EQ) for fast comparison
- Include `isLoaded` flag to detect uninitialized cartridge
  </action>
  <verify>
File exists at `Source/dsp/GridInterpolator.h` and contains:
- `GridStageData` struct with freqSemitone field
- `ZPlaneCartridge` struct with 3D array
- Constants for NUM_STAGES=7, GRID_SIZE=17, NUM_VARIANTS=3
  </verify>
  <done>Data structures compile and represent 17x17x3 grid with semitone storage</done>
</task>

<task type="auto">
  <name>Task 2: Add Hz/semitone conversion utilities</name>
  <files>Source/dsp/GridInterpolator.h</files>
  <action>
Add conversion functions to `GridInterpolator.h`:

```cpp
namespace ZPlane {

// Hz to semitones relative to C5
// C5 (523 Hz) -> 0 semitones
// C6 (1046 Hz) -> +12 semitones
// A4 (440 Hz) -> -3 semitones
inline float hzToSemitone(float hz) {
    if (hz <= 0.0f) return -120.0f;  // Effectively DC, maps to inaudible
    return 12.0f * std::log2(hz / C5_HZ);
}

// Semitones to Hz
inline float semitoneToHz(float semitone) {
    return C5_HZ * std::pow(2.0f, semitone / 12.0f);
}

// Check if frequency is ultrasonic (>20kHz, should bypass)
inline bool isUltrasonic(float semitone) {
    // 20kHz in semitones relative to C5: 12 * log2(20000/523.25) = ~63.3
    return semitone > 63.3f;
}

} // namespace ZPlane
```

Include necessary headers at top of file:
```cpp
#pragma once
#include <array>
#include <string>
#include <cmath>
#include <algorithm>
```

Test values to verify:
- hzToSemitone(523.251f) should return ~0.0
- hzToSemitone(1046.5f) should return ~12.0
- semitoneToHz(0.0f) should return ~523.25
- semitoneToHz(12.0f) should return ~1046.5
  </action>
  <verify>
Conversion functions present and return expected values when mentally traced:
- `hzToSemitone(523.251f)` = 12 * log2(1) = 0
- `semitoneToHz(12.0f)` = 523.251 * 2^1 = 1046.5
  </verify>
  <done>Hz/semitone conversions implemented with correct C5 reference</done>
</task>

<task type="auto">
  <name>Task 3: Implement trilinear grid interpolation</name>
  <files>Source/dsp/GridInterpolator.h</files>
  <action>
Add the GridInterpolator class:

```cpp
namespace ZPlane {

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

        // Map 0-1 to grid indices
        float gx = morph * (GRID_SIZE - 1);      // 0-16
        float gy = transform * (GRID_SIZE - 1);  // 0-16
        float gz = q * (NUM_VARIANTS - 1);       // 0-2

        // Integer indices (clamped)
        int ix = std::clamp(static_cast<int>(gx), 0, GRID_SIZE - 2);
        int iy = std::clamp(static_cast<int>(gy), 0, GRID_SIZE - 2);
        int iz = std::clamp(static_cast<int>(gz), 0, NUM_VARIANTS - 2);

        // Fractional parts
        float fx = gx - ix;
        float fy = gy - iy;
        float fz = gz - iz;

        // 8-corner trilinear interpolation
        // c000 = variant[iz], row[iy], col[ix]
        auto sample = [&](int vi, int row, int col) -> const GridStageData& {
            int gridIdx = row * GRID_SIZE + col;
            return cartridge->data[vi][stageIdx][gridIdx];
        };

        // Interpolate along X (morph)
        auto lerpStage = [](const GridStageData& a, const GridStageData& b, float t) {
            GridStageData result;
            result.freqSemitone = a.freqSemitone + (b.freqSemitone - a.freqSemitone) * t;
            result.radius = a.radius + (b.radius - a.radius) * t;
            result.gainDb = a.gainDb + (b.gainDb - a.gainDb) * t;
            result.shape = a.shape;  // Shape doesn't interpolate
            return result;
        };

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
```

Critical implementation notes:
- Grid index formula: `row * 17 + col` where row=transform, col=morph
- Clamp indices to valid range (0 to GRID_SIZE-2 for interpolation base)
- Shape field does NOT interpolate (discrete, take from first corner)
- All interpolation happens in SEMITONE SPACE - this is key to the Rossum sweep
  </action>
  <verify>
GridInterpolator class present with:
- `interpolate(stageIdx, morph, transform, q)` method
- `interpolateAllStages(morph, transform, q)` method
- Trilinear interpolation using 8 corners
- Grid index calculation: row * GRID_SIZE + col
  </verify>
  <done>Trilinear interpolation works across Morph x Transform x Q dimensions in semitone space</done>
</task>

</tasks>

<verification>
1. File structure: `Source/dsp/GridInterpolator.h` exists with ~200+ lines
2. Compilation: Create minimal test file that includes GridInterpolator.h and compiles
3. Data layout: Constants match requirements (7 stages, 17x17 grid, 3 variants)
4. Semitone storage: `GridStageData.freqSemitone` field exists (not `freqHz`)
5. Interpolation: `GridInterpolator::interpolate()` uses semitone values throughout
</verification>

<success_criteria>
- GridInterpolator.h compiles without errors
- Data structures can represent the full 17x17x3 x 7-stage grid
- Hz/semitone conversions are mathematically correct
- Trilinear interpolation samples all 8 corners correctly
- Shape field preserved (not interpolated) during blending
</success_criteria>

<output>
After completion, create `.planning/phases/01-dsp-engine/01-01-SUMMARY.md`
</output>
