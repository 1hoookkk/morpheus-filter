---
phase: 01-dsp-engine
plan: 02
type: execute
wave: 2
depends_on: ["01-01"]
files_modified:
  - Source/dsp/CartridgeLoader.h
autonomous: true

must_haves:
  truths:
    - "Cartridge loader parses talking_hedz_extracted.json successfully"
    - "Hz values from JSON are converted to semitones on load"
    - "All 3 variants x 7 stages x 289 cells are populated"
  artifacts:
    - path: "Source/dsp/CartridgeLoader.h"
      provides: "JSON parsing for cartridge files"
      exports: ["ZPlane::loadCartridge"]
      min_lines: 80
  key_links:
    - from: "loadCartridge function"
      to: "ZPlaneCartridge struct"
      via: "populates data array"
      pattern: "cart\\.data\\[.*\\]\\[.*\\]\\[.*\\]"
    - from: "JSON freq_17x17"
      to: "GridStageData.freqSemitone"
      via: "hzToSemitone conversion"
      pattern: "hzToSemitone.*freq"
---

<objective>
Create the JSON cartridge loader that parses `talking_hedz_extracted.json` and populates ZPlaneCartridge.

Purpose: Bridge between the extracted JSON data and the runtime grid structures. Critical to convert Hz values to semitone space on load (not at render time).

Output: `Source/dsp/CartridgeLoader.h` with `loadCartridge()` function.
</objective>

<context>
@.planning/phases/01-dsp-engine/01-RESEARCH.md (JSON structure in Appendix B)
@Source/dsp/GridInterpolator.h (data structures to populate)
@talking_hedz_extracted.json (actual data format)
</context>

<tasks>

<task type="auto">
  <name>Task 1: Set up nlohmann/json dependency</name>
  <files>Source/dsp/CartridgeLoader.h</files>
  <action>
First, download nlohmann/json single header to the project.

Create directory if needed: `Source/external/`

Download the single-header version:
```bash
mkdir -p Source/external
curl -o Source/external/json.hpp https://raw.githubusercontent.com/nlohmann/json/v3.11.3/single_include/nlohmann/json.hpp
```

If curl is not available, the executor should download manually from:
https://github.com/nlohmann/json/releases/download/v3.11.3/json.hpp

Place at: `Source/external/json.hpp`

Note: This is a ~25KB single-header library, industry standard for C++ JSON parsing.
  </action>
  <verify>
File exists at `Source/external/json.hpp` and contains nlohmann json library (check for "nlohmann" in first 50 lines)
  </verify>
  <done>nlohmann/json header available for include</done>
</task>

<task type="auto">
  <name>Task 2: Create cartridge loader with Hz-to-semitone conversion</name>
  <files>Source/dsp/CartridgeLoader.h</files>
  <action>
Create `Source/dsp/CartridgeLoader.h`:

```cpp
#pragma once

#include "GridInterpolator.h"
#include "../external/json.hpp"

#include <fstream>
#include <stdexcept>

namespace ZPlane {

using json = nlohmann::json;

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

} // namespace ZPlane
```

Key implementation notes:
- Include path assumes `Source/external/json.hpp` relative to `Source/dsp/`
- Hz-to-semitone conversion happens ONCE at load time (not per frame)
- Shape string "lp" -> 0, "eq" or "bp" -> 1
- Validate array sizes to catch format mismatches early
- Use `.value()` for optional fields with defaults
  </action>
  <verify>
CartridgeLoader.h exists with:
- `loadCartridge(path)` function
- `#include "../external/json.hpp"`
- `hzToSemitone()` call for frequency conversion
- Loops over 3 variants, 7 stages, 289 cells
  </verify>
  <done>JSON loader parses cartridge and converts to semitone space</done>
</task>

<task type="auto">
  <name>Task 3: Verify cartridge loading with test output</name>
  <files>Source/dsp/CartridgeLoader.h</files>
  <action>
Add a debug/test function to CartridgeLoader.h that can verify the load:

```cpp
namespace ZPlane {

// Debug: Print cartridge summary to verify load
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
```

Also create a minimal test file `Tests/test_cartridge_load.cpp`:

```cpp
#include "../Source/dsp/CartridgeLoader.h"
#include <iostream>

int main() {
    try {
        ZPlane::ZPlaneCartridge cart = ZPlane::loadCartridge("talking_hedz_extracted.json");
        ZPlane::printCartridgeSummary(cart);

        // Verify some expected values
        // At Morph=0 (col 0), variant 0, stage 0: freq should be ~3607 Hz
        const auto& cell = cart.data[0][0][0];
        float freqHz = ZPlane::semitoneToHz(cell.freqSemitone);
        std::cout << "\nVerification:\n";
        std::cout << "  V0 S0 M0: freq=" << freqHz << " Hz (expected ~3607)\n";

        if (freqHz > 3500 && freqHz < 3700) {
            std::cout << "  PASS: Frequency in expected range\n";
        } else {
            std::cout << "  FAIL: Frequency outside expected range\n";
            return 1;
        }

        return 0;
    } catch (const std::exception& e) {
        std::cerr << "Error: " << e.what() << std::endl;
        return 1;
    }
}
```

Compile and run to verify:
```bash
# Windows (MSVC)
cl /EHsc /std:c++17 /I. Tests/test_cartridge_load.cpp /Fe:test_load.exe
./test_load.exe

# Or with g++
g++ -std=c++17 -I. Tests/test_cartridge_load.cpp -o test_load
./test_load
```
  </action>
  <verify>
1. Test file compiles without errors
2. Running test_load outputs cartridge summary
3. Stage 0 variant 0 at Morph=0 shows frequency ~3607 Hz (matching JSON first value)
4. No exceptions thrown during load
  </verify>
  <done>Cartridge loads correctly with verified Hz-to-semitone conversion</done>
</task>

</tasks>

<verification>
1. `Source/external/json.hpp` exists (nlohmann/json library)
2. `Source/dsp/CartridgeLoader.h` exists with `loadCartridge()` function
3. Test compilation: `g++ -std=c++17 Tests/test_cartridge_load.cpp` succeeds
4. Test execution: `./test_load` prints cartridge data and exits 0
5. Frequency values match JSON source after semitone round-trip
</verification>

<success_criteria>
- nlohmann/json integrated without build issues
- loadCartridge() parses all 3 variants x 7 stages x 289 cells
- Hz values converted to semitones on load (not at render time)
- Error handling for missing files and format mismatches
- Test program verifies load against known JSON values
</success_criteria>

<output>
After completion, create `.planning/phases/01-dsp-engine/01-02-SUMMARY.md`
</output>
