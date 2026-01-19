#pragma once

#include "GridInterpolator.h"
#include "../external/json.hpp"

#include <fstream>
#include <stdexcept>

namespace ZPlane {

using json = nlohmann::json;

//==============================================================================
// CartridgeLoader - Load ZPlaneCartridge from JSON, converting Hz to semitones
//
// CRITICAL: Hz values are converted to semitone space on load (not at render
// time). This enables proper logarithmic frequency interpolation per E-mu
// patents - the "Rossum sweep" effect.
//==============================================================================

// Load cartridge from JSON file, converting Hz to semitones on load
inline ZPlaneCartridge loadCartridge(const std::string& path) {
    ZPlaneCartridge cart;

    std::ifstream f(path);
    if (!f.is_open()) {
        throw std::runtime_error("Failed to open cartridge file: " + path);
    }

    json j = json::parse(f);

    cart.name = j.value("name", "Unknown");

    // Validate structure
    const auto& variants = j["variants"];
    if (variants.size() != NUM_VARIANTS) {
        throw std::runtime_error("Expected 3 variants, got " + std::to_string(variants.size()));
    }

    // Parse each variant
    for (size_t vi = 0; vi < NUM_VARIANTS; ++vi) {
        const auto& variant = variants[vi];
        const auto& stages = variant["stages"];

        if (stages.size() != NUM_STAGES) {
            throw std::runtime_error("Expected 7 stages, got " + std::to_string(stages.size()));
        }

        // Parse each stage
        for (size_t si = 0; si < NUM_STAGES; ++si) {
            const auto& stage = stages[si];

            // Get arrays (each has 289 elements = 17x17)
            const auto& freqs = stage["freq_17x17"];
            const auto& gains = stage["gain_17x17"];
            const auto& radii = stage["radius_17x17"];

            if (freqs.size() != GRID_SIZE * GRID_SIZE) {
                throw std::runtime_error("Expected 289 grid cells, got " + std::to_string(freqs.size()));
            }

            // Determine shape from string
            std::string shapeStr = stage.value("shape", "lp");
            int shape = (shapeStr == "eq" || shapeStr == "bp") ? 1 : 0;

            // Parse each grid cell
            for (size_t gi = 0; gi < GRID_SIZE * GRID_SIZE; ++gi) {
                GridStageData& cell = cart.data[vi][si][gi];

                // CRITICAL: Convert Hz to semitones on load
                // This enables proper interpolation per CONTEXT.md
                float freqHz = freqs[gi].get<float>();
                cell.freqSemitone = hzToSemitone(freqHz);

                cell.radius = radii[gi].get<float>();
                cell.gainDb = gains[gi].get<float>();
                cell.shape = shape;
            }
        }
    }

    cart.isLoaded = true;
    return cart;
}

// Convenience: load from default location
inline ZPlaneCartridge loadTalkingHedz() {
    return loadCartridge("talking_hedz_extracted.json");
}

//==============================================================================
// Debug: Print cartridge summary to verify load
//==============================================================================
inline void printCartridgeSummary(const ZPlaneCartridge& cart) {
    if (!cart.isLoaded) {
        printf("Cartridge not loaded\n");
        return;
    }

    printf("Cartridge: %s\n", cart.name.c_str());
    printf("Variants: %d, Stages: %d, Grid: %dx%d\n",
           NUM_VARIANTS, NUM_STAGES, GRID_SIZE, GRID_SIZE);

    // Print first cell of each variant/stage for sanity check
    printf("\nSample data (Morph=0, Transform=0):\n");
    for (int vi = 0; vi < NUM_VARIANTS; ++vi) {
        printf("  Variant %d (Q=%d%%):\n", vi, vi * 50);
        for (int si = 0; si < NUM_STAGES; ++si) {
            const auto& cell = cart.data[vi][si][0];  // Grid index 0 = row 0, col 0
            float freqHz = semitoneToHz(cell.freqSemitone);
            printf("    Stage %d: freq=%.1f Hz (%.1f st), r=%.4f, gain=%.1f dB, shape=%s\n",
                   si, freqHz, cell.freqSemitone, cell.radius, cell.gainDb,
                   cell.shape == 0 ? "LP" : "EQ");
        }
    }

    // Also print Morph=100% for comparison (grid index = 16, last column of row 0)
    printf("\nSample data (Morph=100%%, Transform=0):\n");
    for (int vi = 0; vi < NUM_VARIANTS; ++vi) {
        printf("  Variant %d (Q=%d%%):\n", vi, vi * 50);
        for (int si = 0; si < NUM_STAGES; ++si) {
            const auto& cell = cart.data[vi][si][16];  // Grid index 16 = row 0, col 16
            float freqHz = semitoneToHz(cell.freqSemitone);
            printf("    Stage %d: freq=%.1f Hz (%.1f st), r=%.4f, gain=%.1f dB, shape=%s\n",
                   si, freqHz, cell.freqSemitone, cell.radius, cell.gainDb,
                   cell.shape == 0 ? "LP" : "EQ");
        }
    }
}

} // namespace ZPlane
