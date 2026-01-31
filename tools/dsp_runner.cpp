#include <cstdint>
#include <cmath>
#include <cstdio>
#include <fstream>
#include <iostream>
#include <string>
#include <vector>

#include "DSP/ZPlaneFilter.h"

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

static std::vector<float> generateSaw(double freqHz, int sampleRate, int numSamples, float amp)
{
    std::vector<float> x;
    x.resize(static_cast<size_t>(numSamples));

    double phase = 0.0;
    const double inc = freqHz / double(sampleRate);

    for (int i = 0; i < numSamples; ++i)
    {
        const double saw = (2.0 * phase) - 1.0;
        x[static_cast<size_t>(i)] = static_cast<float>(saw * double(amp));
        phase += inc;
        if (phase >= 1.0)
            phase -= 1.0;
    }

    return x;
}

static std::vector<float> processCorner(double morph, double q, int sampleRate, const std::vector<float>& input)
{
    ZPlaneFilter f;
    f.prepare(double(sampleRate));
    f.setDebugOscillator(false);
    f.setParameters(morph, q);

    // AUDIT: Dump coefficients to JSON for comparison with Python
    static bool firstRun = true;
    if (firstRun) {
        std::remove("tools/coeff_dump.json");  // Clear file on first run
        firstRun = false;
    }
    f.dumpCoefficientsJSON("tools/coeff_dump.json", morph, q);

    std::vector<float> y;
    y.resize(input.size());

    double peak = 0.0;
    for (size_t i = 0; i < input.size(); ++i)
    {
        const double out = f.processSample(double(input[i]));
        if (!std::isfinite(out))
            throw std::runtime_error("Non-finite output at sample " + std::to_string(i));
        peak = std::max(peak, std::abs(out));
        y[i] = static_cast<float>(out);
    }

    // AUTO-NORMALIZATION: DISABLED FOR AUDIT - Print when it would trigger
    if (peak > 0.99)
    {
        std::cout << "  [AUDIT] Auto-norm would trigger: peak=" << peak << " (NOT APPLIED)\n";
        // const double g = 0.9 / peak;
        // for (auto& v : y)
        //     v = static_cast<float>(double(v) * g);
    }

    return y;
}

int main()
{
    try
    {
        int sampleRate = 0;
        std::vector<float> input;
        try
        {
            input = readWavMono16("validation/bypassed-pinknoise.wav", sampleRate);
            writeWavMono16("tools/output_input.wav", input, sampleRate);
        }
        catch (...)
        {
            sampleRate = 44100;
            constexpr int seconds = 3;
            const int numSamples = sampleRate * seconds;
            input = generateSaw(179.0, sampleRate, numSamples, 0.5f);
            writeWavMono16("tools/output_input.wav", input, sampleRate);
        }

        struct Corner { const char* name; double morph; double q; };
        const Corner corners[] = {
            {"M0_Q100", 0.0, 1.0},
            {"M0_Q0", 0.0, 0.0},
            {"M100_Q100", 1.0, 1.0},
            {"M100_Q0", 1.0, 0.0},
        };

        for (const auto& c : corners)
        {
            std::cout << "Rendering " << c.name << " (morph=" << c.morph << ", q=" << c.q << ")...\n";
            const auto out = processCorner(c.morph, c.q, sampleRate, input);
            writeWavMono16(std::string("tools/output_") + c.name + ".wav", out, sampleRate);
        }

        std::cout << "Done.\n";
        return 0;
    }
    catch (const std::exception& e)
    {
        std::cerr << "dsp_runner failed: " << e.what() << "\n";
        return 1;
    }
}
