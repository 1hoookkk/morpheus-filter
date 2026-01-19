#include "../Source/dsp/CartridgeLoader.h"
#include <iostream>

int main() {
    try {
        std::cout << "Loading cartridge from talking_hedz_extracted.json...\n";
        ZPlane::ZPlaneCartridge cart = ZPlane::loadCartridge("talking_hedz_extracted.json");

        std::cout << "\n=== Cartridge Summary ===\n";
        ZPlane::printCartridgeSummary(cart);

        // Verify some expected values
        // At Morph=0 (col 0), variant 0, stage 0: freq should be ~3607 Hz
        const auto& cell = cart.data[0][0][0];
        float freqHz = ZPlane::semitoneToHz(cell.freqSemitone);

        std::cout << "\n=== Verification ===\n";
        std::cout << "  V0 S0 M0: freq=" << freqHz << " Hz (expected ~3607)\n";
        std::cout << "  Semitone value: " << cell.freqSemitone << " st\n";

        if (freqHz > 3500 && freqHz < 3700) {
            std::cout << "  PASS: Frequency in expected range (3500-3700 Hz)\n";
        } else {
            std::cout << "  FAIL: Frequency outside expected range\n";
            return 1;
        }

        // Verify round-trip conversion
        float expectedHz = 3607.3f;
        float semitone = ZPlane::hzToSemitone(expectedHz);
        float roundtripHz = ZPlane::semitoneToHz(semitone);
        float error = std::abs(roundtripHz - expectedHz);

        std::cout << "\n=== Round-trip Conversion Test ===\n";
        std::cout << "  Original: " << expectedHz << " Hz\n";
        std::cout << "  -> Semitone: " << semitone << " st\n";
        std::cout << "  -> Back to Hz: " << roundtripHz << " Hz\n";
        std::cout << "  Error: " << error << " Hz\n";

        if (error < 0.01f) {
            std::cout << "  PASS: Round-trip error < 0.01 Hz\n";
        } else {
            std::cout << "  FAIL: Round-trip error too large\n";
            return 1;
        }

        // Verify all variants/stages/cells are populated
        int totalCells = 0;
        int validCells = 0;
        for (int v = 0; v < ZPlane::NUM_VARIANTS; ++v) {
            for (int s = 0; s < ZPlane::NUM_STAGES; ++s) {
                for (int g = 0; g < ZPlane::GRID_SIZE * ZPlane::GRID_SIZE; ++g) {
                    totalCells++;
                    const auto& c = cart.data[v][s][g];
                    // Valid if frequency is not zero and radius is in range
                    if (c.freqSemitone != 0.0f || c.radius > 0.0f) {
                        validCells++;
                    }
                }
            }
        }

        std::cout << "\n=== Coverage Test ===\n";
        std::cout << "  Total cells: " << totalCells << "\n";
        std::cout << "  Valid cells: " << validCells << "\n";
        std::cout << "  Expected: " << (3 * 7 * 289) << " (3 variants x 7 stages x 289 grid)\n";

        if (validCells == 3 * 7 * 289) {
            std::cout << "  PASS: All cells populated\n";
        } else {
            std::cout << "  FAIL: Missing cells\n";
            return 1;
        }

        std::cout << "\n=== ALL TESTS PASSED ===\n";
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "Error: " << e.what() << std::endl;
        return 1;
    }
}
