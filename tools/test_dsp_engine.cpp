/*
  ==============================================================================

    test_dsp_engine.cpp
    Phase 2 DSP Engine Functional Test Harness

    Validates:
    - DSP-02: 5-stage cascaded biquad filter processes audio
    - DSP-03: Direct Form I topology produces stable output
    - Phase 2 Success Criteria from ROADMAP.md

  ==============================================================================
*/

#include <cstdint>
#include <cmath>
#include <cstdio>
#include <fstream>
#include <iostream>
#include <string>
#include <vector>
#include <chrono>

#include "DSP/ZPlaneFilter.h"

// ==============================================================================
// WAV I/O (16-bit PCM mono)
// ==============================================================================

static std::vector<float> readWavMono16(const std::string& path, int& sampleRateOut)
{
    std::ifstream f(path, std::ios::binary);
    if (!f)
        throw std::runtime_error("Failed to open input WAV: " + path);

    auto readU32 = [&]() -> uint32_t {
        uint32_t v{};
        f.read(reinterpret_cast<char*>(&v), 4);
        return v;
    };
    auto readU16 = [&]() -> uint16_t {
        uint16_t v{};
        f.read(reinterpret_cast<char*>(&v), 2);
        return v;
    };

    char riff[4]{};
    f.read(riff, 4);
    if (std::string(riff, 4) != "RIFF")
        throw std::runtime_error("Not a RIFF file: " + path);
    (void)readU32();
    char wave[4]{};
    f.read(wave, 4);
    if (std::string(wave, 4) != "WAVE")
        throw std::runtime_error("Not a WAVE file: " + path);

    uint16_t audioFormat = 0;
    uint16_t numChannels = 0;
    uint32_t sampleRate = 0;
    uint16_t bitsPerSample = 0;
    std::vector<int16_t> pcm;

    while (f && !f.eof())
    {
        char id[4]{};
        f.read(id, 4);
        if (f.gcount() != 4)
            break;
        const uint32_t size = readU32();
        const std::string chunk(id, 4);

        if (chunk == "fmt ")
        {
            audioFormat = readU16();
            numChannels = readU16();
            sampleRate = readU32();
            (void)readU32(); // byteRate
            (void)readU16(); // blockAlign
            bitsPerSample = readU16();
            if (size > 16)
                f.seekg(static_cast<std::streamoff>(size - 16), std::ios::cur);
        }
        else if (chunk == "data")
        {
            if (audioFormat != 1 || bitsPerSample != 16)
                throw std::runtime_error("Only PCM16 WAV supported for input: " + path);
            const size_t samples = size / sizeof(int16_t);
            pcm.resize(samples);
            f.read(reinterpret_cast<char*>(pcm.data()), static_cast<std::streamsize>(size));
        }
        else
        {
            f.seekg(static_cast<std::streamoff>(size), std::ios::cur);
        }
    }

    if (sampleRate == 0 || numChannels == 0 || pcm.empty())
        throw std::runtime_error("Failed to parse WAV: " + path);

    sampleRateOut = static_cast<int>(sampleRate);

    // Convert to mono float
    std::vector<float> x;
    x.reserve(pcm.size() / numChannels);
    for (size_t i = 0; i + (numChannels - 1) < pcm.size(); i += numChannels)
        x.push_back(static_cast<float>(pcm[i]) / 32768.0f);

    return x;
}

static void writeWavMono16(const std::string& path, const std::vector<float>& x, int sampleRate)
{
    std::ofstream f(path, std::ios::binary);
    if (!f)
        throw std::runtime_error("Failed to open output WAV: " + path);

    const uint16_t numChannels = 1;
    const uint16_t bitsPerSample = 16;
    const uint32_t byteRate = uint32_t(sampleRate) * numChannels * (bitsPerSample / 8);
    const uint16_t blockAlign = numChannels * (bitsPerSample / 8);

    const uint32_t dataSize = uint32_t(x.size() * sizeof(int16_t));
    const uint32_t riffSize = 36 + dataSize;

    f.write("RIFF", 4);
    f.write(reinterpret_cast<const char*>(&riffSize), 4);
    f.write("WAVE", 4);

    f.write("fmt ", 4);
    const uint32_t fmtSize = 16;
    const uint16_t audioFormat = 1;
    f.write(reinterpret_cast<const char*>(&fmtSize), 4);
    f.write(reinterpret_cast<const char*>(&audioFormat), 2);
    f.write(reinterpret_cast<const char*>(&numChannels), 2);
    f.write(reinterpret_cast<const char*>(&sampleRate), 4);
    f.write(reinterpret_cast<const char*>(&byteRate), 4);
    f.write(reinterpret_cast<const char*>(&blockAlign), 2);
    f.write(reinterpret_cast<const char*>(&bitsPerSample), 2);

    f.write("data", 4);
    f.write(reinterpret_cast<const char*>(&dataSize), 4);

    for (float v : x)
    {
        const float clamped = std::fmax(-1.0f, std::fmin(1.0f, v));
        const int16_t s = static_cast<int16_t>(std::lrint(clamped * 32767.0f));
        f.write(reinterpret_cast<const char*>(&s), 2);
    }
}

// ==============================================================================
// MAIN TEST
// ==============================================================================

int main()
{
    try
    {
        std::cout << "========================================\n";
        std::cout << "TRENCH DSP Engine Functional Test\n";
        std::cout << "Phase 2 Requirements Validation\n";
        std::cout << "========================================\n\n";

        // 1. Load pink noise input
        std::cout << "Loading pink noise input...\n";
        int sampleRate = 0;
        std::vector<float> input = readWavMono16("validation/bypassed-pinknoise.wav", sampleRate);

        std::cout << "  Sample rate: " << sampleRate << " Hz\n";
        std::cout << "  Duration: " << input.size() / double(sampleRate) << " seconds\n";
        std::cout << "  Samples: " << input.size() << "\n\n";

        // 2. Create filter at M0_Q100 (resonant "Ah" vowel)
        std::cout << "Initializing ZPlaneFilter at M0_Q100 (resonant 'Ah' vowel)...\n";
        ZPlaneFilter filter;
        filter.prepare(double(sampleRate));
        filter.setDebugOscillator(false);
        filter.setParameters(0.0, 1.0);  // M0_Q100
        std::cout << "  Filter ready\n\n";

        // 3. Process through filter
        std::cout << "Processing " << input.size() << " samples through 5-stage biquad cascade...\n";
        std::vector<float> output;
        output.reserve(input.size());

        auto startTime = std::chrono::high_resolution_clock::now();

        for (size_t i = 0; i < input.size(); i++)
        {
            const double out = filter.processSample(double(input[i]));

            // Verify output is finite
            if (!std::isfinite(out))
            {
                throw std::runtime_error("Non-finite output at sample " + std::to_string(i));
            }

            output.push_back(static_cast<float>(out));
        }

        auto endTime = std::chrono::high_resolution_clock::now();
        auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(endTime - startTime);

        std::cout << "  Processing complete\n\n";

        // 4. Measure RMS levels
        std::cout << "Computing RMS levels...\n";
        double inputRMS = 0.0, outputRMS = 0.0;
        for (size_t i = 0; i < input.size(); i++)
        {
            inputRMS += double(input[i]) * double(input[i]);
            outputRMS += double(output[i]) * double(output[i]);
        }
        inputRMS = std::sqrt(inputRMS / input.size());
        outputRMS = std::sqrt(outputRMS / output.size());

        double inputDb = 20.0 * std::log10(inputRMS);
        double outputDb = 20.0 * std::log10(outputRMS);

        std::cout << "  Input RMS:  " << inputRMS << " (" << inputDb << " dB)\n";
        std::cout << "  Output RMS: " << outputRMS << " (" << outputDb << " dB)\n";
        std::cout << "  Delta: " << (outputDb - inputDb) << " dB\n\n";

        // 5. Performance metrics
        double audioDuration = double(input.size()) / double(sampleRate);
        double processingTime = double(duration.count()) / 1000.0;
        double realtimeFactor = audioDuration / processingTime;

        std::cout << "Performance:\n";
        std::cout << "  Audio duration: " << audioDuration << " seconds\n";
        std::cout << "  Processing time: " << processingTime << " seconds\n";
        std::cout << "  Realtime factor: " << realtimeFactor << "x\n";
        std::cout << "  (Target: >20x for headroom)\n\n";

        // 6. Save output
        writeWavMono16("tools/test_dsp_output.wav", output, sampleRate);
        std::cout << "Output saved: tools/test_dsp_output.wav\n\n";

        // 7. Automated verification
        std::cout << "========================================\n";
        std::cout << "AUTOMATED VERIFICATION\n";
        std::cout << "========================================\n";

        bool allPassed = true;

        // Test 1: Output is non-zero (filter is processing)
        if (std::abs(outputRMS) < 0.001)
        {
            std::cout << "FAIL: Output RMS too quiet - filter may not be processing\n";
            allPassed = false;
        }
        else
        {
            std::cout << "PASS: Output RMS is non-zero (filter is processing)\n";
        }

        // Test 2: Output differs from input (spectrum is modified)
        double rmsDifference = std::abs(outputRMS - inputRMS);
        if (rmsDifference < 0.01)
        {
            std::cout << "FAIL: Output matches input - filter may be bypassed\n";
            allPassed = false;
        }
        else
        {
            std::cout << "PASS: Output differs from input (filter is modifying spectrum)\n";
        }

        // Test 3: Processing is efficient
        if (realtimeFactor < 20.0)
        {
            std::cout << "WARN: Processing slower than 20x realtime (may impact performance)\n";
            // Not a failure, just a warning
        }
        else
        {
            std::cout << "PASS: Processing is efficient (>20x realtime)\n";
        }

        // Test 4: No NaN/Inf in output
        bool hasNonFinite = false;
        for (float v : output)
        {
            if (!std::isfinite(v))
            {
                hasNonFinite = true;
                break;
            }
        }
        if (hasNonFinite)
        {
            std::cout << "FAIL: Output contains NaN or Inf values\n";
            allPassed = false;
        }
        else
        {
            std::cout << "PASS: All output samples are finite\n";
        }

        std::cout << "\n========================================\n";
        std::cout << "RESULT: " << (allPassed ? "ALL TESTS PASSED" : "SOME TESTS FAILED") << "\n";
        std::cout << "========================================\n\n";

        std::cout << "Next steps:\n";
        std::cout << "1. Listen to tools/test_dsp_output.wav\n";
        std::cout << "2. Verify it sounds filtered (not raw pink noise)\n";
        std::cout << "3. Should have 'Ah' vowel formant character\n";

        return allPassed ? 0 : 1;
    }
    catch (const std::exception& e)
    {
        std::cerr << "\nERROR: " << e.what() << "\n";
        return 1;
    }
}
