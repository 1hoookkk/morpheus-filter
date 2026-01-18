#pragma once

#include "ZPlaneData.h"
#include <juce_core/juce_core.h>

namespace ZPlane {

//==============================================================================
// Z-Plane Loader - Parses cartridge JSON into ZPlaneCartridge
// JSON contains ONLY captured data (a1, radius, flag per stage per keyframe)
//==============================================================================
class ZPlaneLoader {
public:
    //--------------------------------------------------------------------------
    // Load cartridge from JSON file
    //--------------------------------------------------------------------------
    static bool loadFromFile(const juce::File& file, ZPlaneCartridge& cartridge) {
        if (!file.existsAsFile())
            return false;

        auto jsonText = file.loadFileAsString();
        return loadFromString(jsonText, cartridge);
    }

    //--------------------------------------------------------------------------
    // Load cartridge from JSON string
    //--------------------------------------------------------------------------
    static bool loadFromString(const juce::String& jsonText, ZPlaneCartridge& cartridge) {
        auto json = juce::JSON::parse(jsonText);
        if (!json.isObject())
            return false;

        return parseCartridge(json, cartridge);
    }

private:
    //--------------------------------------------------------------------------
    // Parse root cartridge object
    //--------------------------------------------------------------------------
    static bool parseCartridge(const juce::var& json, ZPlaneCartridge& cartridge) {
        // Parse metadata
        auto meta = json.getProperty("meta", juce::var());
        if (meta.isObject()) {
            cartridge.name = meta.getProperty("name", "Unknown").toString().toStdString();
            cartridge.source = meta.getProperty("source", "").toString().toStdString();
            cartridge.sampleRate = static_cast<float>(meta.getProperty("sample_rate", 44100.0));
        }

        // Parse keyframes array
        auto keyframes = json.getProperty("keyframes", juce::var());
        if (!keyframes.isArray())
            return false;

        cartridge.keyframes.clear();
        for (int k = 0; k < keyframes.size(); ++k) {
            MorphKeyframe kf;
            if (parseKeyframe(keyframes[k], kf)) {
                cartridge.keyframes.push_back(kf);
            }
        }

        return !cartridge.keyframes.empty();
    }

    //--------------------------------------------------------------------------
    // Parse single keyframe
    //--------------------------------------------------------------------------
    static bool parseKeyframe(const juce::var& json, MorphKeyframe& kf) {
        // Zero-initialize to prevent undefined behavior if JSON has fewer stages
        kf = MorphKeyframe{};
        kf.position = static_cast<float>(json.getProperty("position", 0.0));

        auto stages = json.getProperty("stages", juce::var());
        if (!stages.isArray())
            return false;

        for (int i = 0; i < std::min(5, stages.size()); ++i) {
            kf.stages[i] = parseStage(stages[i]);
        }

        return true;
    }

    //--------------------------------------------------------------------------
    // Parse single stage (pure captured data: a1, radius, flag)
    //--------------------------------------------------------------------------
    static StageData parseStage(const juce::var& json) {
        StageData stage;
        stage.a1 = static_cast<float>(json.getProperty("a1", 0.0));
        stage.radius = static_cast<float>(json.getProperty("radius", 0.9));
        stage.flag = static_cast<int>(json.getProperty("flag", 1));
        return stage;
    }
};

//==============================================================================
// Embedded Talking Hedz Data - Fallback if JSON not available
// SOURCE OF TRUTH: talking_hedz_cartridge.json (X3 Cheat Engine capture)
//==============================================================================
inline ZPlaneCartridge getTalkingHedzCartridge() {
    ZPlaneCartridge cart;
    cart.name = "Talking Hedz";
    cart.source = "X3 Cheat Engine Capture";
    cart.sampleRate = 44100.0f;

    // Morph 0% (EE vowel)
    cart.keyframes.push_back({0.0f, {{
        {-1.974805f, 0.998231f, 1},  // Stage 0: bandpass ~1035 Hz
        {-1.939721f, 0.998292f, 1},  // Stage 1: bandpass ~1679 Hz
        {-1.873399f, 0.998353f, 1},  // Stage 2: bandpass ~2480 Hz
        {-1.524112f, 0.992679f, 1},  // Stage 3: bandpass ~4882 Hz
        {-1.997652f, 0.998292f, 0}   // Stage 4: lowpass ~DC
    }}});

    // Morph 25%
    cart.keyframes.push_back({0.25f, {{
        {-1.987616f, 0.998353f, 1},
        {-1.928071f, 0.998338f, 1},
        {-1.867585f, 0.998353f, 1},
        {-1.518988f, 0.987555f, 1},
        {-1.996355f, 0.998261f, 0}
    }}});

    // Morph 50% (crossover point)
    cart.keyframes.push_back({0.5f, {{
        {-1.993596f, 0.998475f, 1},
        {-1.912492f, 0.998383f, 1},
        {-1.861726f, 0.998353f, 1},
        {-1.510937f, 0.979504f, 1},
        {-1.992010f, 0.998231f, 0}
    }}});

    // Morph 75%
    cart.keyframes.push_back({0.75f, {{
        {-1.996402f, 0.998597f, 1},
        {-1.896912f, 0.998429f, 1},
        {-1.855866f, 0.998353f, 1},
        {-1.499229f, 0.967796f, 1},
        {-1.978928f, 0.998200f, 0}
    }}});

    // Morph 100% (AH vowel)
    cart.keyframes.push_back({1.0f, {{
        {-1.997743f, 0.998719f, 1},  // Stage 0: bandpass ~DC
        {-1.881333f, 0.998475f, 1},  // Stage 1: bandpass ~2400 Hz
        {-1.850007f, 0.998353f, 1},  // Stage 2: bandpass ~2707 Hz
        {-1.476768f, 0.945335f, 1},  // Stage 3: bandpass ~4733 Hz
        {-1.939599f, 0.998170f, 0}   // Stage 4: lowpass ~1677 Hz
    }}});

    return cart;
}

} // namespace ZPlane
