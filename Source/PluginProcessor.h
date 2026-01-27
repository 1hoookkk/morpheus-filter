#pragma once
#include <JuceHeader.h>
#include "DSP/WavCubeLoader.h"
// #include "DSP/TrenchFilter.h"  // Temporarily disabled for debugging

//==============================================================================
// TRENCH Audio Processor
// Verified architecture: 7 cascaded biquads (14-pole) with pole-based morphing
// Supports both legacy presets and WAV-loaded E-mu cubes
//==============================================================================

class TrenchAudioProcessor : public juce::AudioProcessor
{
public:
    TrenchAudioProcessor();
    ~TrenchAudioProcessor() override;

    void prepareToPlay(double sampleRate, int samplesPerBlock) override;
    void releaseResources() override;
    void processBlock(juce::AudioBuffer<float>&, juce::MidiBuffer&) override;

    juce::AudioProcessorEditor* createEditor() override;
    bool hasEditor() const override { return true; }

    const juce::String getName() const override { return JucePlugin_Name; }
    bool acceptsMidi() const override { return false; }
    bool producesMidi() const override { return false; }
    bool isMidiEffect() const override { return false; }
    double getTailLengthSeconds() const override { return 0.0; }

    int getNumPrograms() override { return 1; }
    int getCurrentProgram() override { return 0; }
    void setCurrentProgram(int) override {}
    const juce::String getProgramName(int) override { return {}; }
    void changeProgramName(int, const juce::String&) override {}

    void getStateInformation(juce::MemoryBlock& destData) override;
    void setStateInformation(const void* data, int sizeInBytes) override;

    // Parameter access
    juce::AudioProcessorValueTreeState& getAPVTS() { return apvts; }

    // Get current frequency response for display (256 points, in dB)
    std::vector<float> getFrequencyResponse() const;

    //==========================================================================
    // Preset / Cube Management
    //==========================================================================
    int getCurrentPresetIndex() const { return currentPresetIndex; }
    void setPresetIndex(int index);
    juce::StringArray getPresetNames() const;

    // Cube Loading (binary preferred, WAV fallback)
    bool loadCubesFromBinary(const juce::File& binFile);
    bool loadCubesFromBinary(const juce::String& path);
    bool loadCubesFromWav(const juce::File& wavFile);
    bool loadCubesFromWav(const juce::String& path);
    bool areCubesLoaded() const { return cubesLoaded; }
    int getNumCubes() const { return cubeLoader.getNumCubes(); }
    void setCubeIndex(int index);
    int getCurrentCubeIndex() const { return currentCubeIndex; }
    juce::StringArray getCubeNames() const { return cubeLoader.getCubeNames(); }

    // WAV file path for persistence
    juce::String getWavFilePath() const { return wavFilePath; }

    // Filter mode toggle (Compose vs Cube) - disabled for debugging
    // void setUseComposedFilter(bool use) { useComposedFilter = use; }
    // bool isUsingComposedFilter() const { return useComposedFilter; }

private:
    juce::AudioProcessorValueTreeState apvts;
    juce::AudioProcessorValueTreeState::ParameterLayout createParameterLayout();

    // Parameters
    std::atomic<float>* morphParam = nullptr;
    std::atomic<float>* qParam = nullptr;
    std::atomic<float>* driveParam = nullptr;
    std::atomic<float>* mixParam = nullptr;
    std::atomic<float>* outputParam = nullptr;
    std::atomic<float>* bypassParam = nullptr;
    std::atomic<float>* testParam = nullptr;

    // Test tone generator
    juce::Random noiseGen;
    double testPhase = 0.0;

    // DSP constants
    static constexpr int CONTROL_RATE = 128;  // Update coefficients every N samples

    // DSP state
    double currentSampleRate = 48000.0;
    int currentPresetIndex = 0;
    int currentCubeIndex = 0;
    int controlCounter = 0;

    // TrenchFilter instances (Compose mode - clean formant filtering)
    // Trench::TrenchFilter trenchFilterL;  // Temporarily disabled
    // Trench::TrenchFilter trenchFilterR;  // Temporarily disabled
    bool useComposedFilter = false;  // Disabled - uses cube mode

    // Biquad cascade (7 stages = 14 poles) - legacy/cube mode
    static constexpr int NUM_STAGES = 7;

    struct BiquadState
    {
        double z1 = 0.0, z2 = 0.0;
    };
    std::array<BiquadState, NUM_STAGES> biquadStatesL;
    std::array<BiquadState, NUM_STAGES> biquadStatesR;

    // Biquad coefficients (normalized)
    struct BiquadCoeffs
    {
        double b0 = 1.0, b1 = 0.0, b2 = 0.0;
        double a1 = 0.0, a2 = 0.0;
    };
    std::array<BiquadCoeffs, NUM_STAGES> currentCoeffs;

    //==========================================================================
    // WAV Cube Loader (E-mu Morpheus format)
    //==========================================================================
    WavCubeLoader cubeLoader;
    bool cubesLoaded = false;
    juce::String wavFilePath;

    //==========================================================================
    // POLAR STAGE DATA (validated X3 captures)
    // a1 = -2*r*cos(theta)  <-- radius IS included (final biquad coefficient)
    // r = pole radius (for Q calculation and resonator frequency decode)
    // flag = 1:Peaking EQ, 0:Lowpass
    //==========================================================================
    struct PolarStageParams
    {
        double a1 = -2.0;   // -2*r*cos(theta) - final biquad a1 coefficient
        double r = 0.5;     // Pole radius (for freq decode: cos(theta) = -a1/(2*r))
        int flag = 1;       // 1 = peaking EQ (formant resonator), 0 = lowpass
    };

    struct PolarMorphPoint
    {
        double morph = 0.0;
        std::array<PolarStageParams, NUM_STAGES> stages;
    };

    struct PolarPreset
    {
        juce::String name;
        std::vector<PolarMorphPoint> morphPoints;
    };

    std::vector<PolarPreset> polarPresets;

    //==========================================================================
    // LEGACY POLE-BASED STAGE DATA (from WAV cubes - no flag)
    // a1 = -2*r*cos(theta), r = pole radius
    //==========================================================================
    struct PoleParams
    {
        double a1 = -2.0;   // -2*r*cos(theta)
        double r = 0.5;     // Pole radius
    };

    struct PoleMorphPoint
    {
        double morph = 0.0;
        std::array<PoleParams, NUM_STAGES> stages;
    };

    //==========================================================================
    // LEGACY STAGE DATA (hand-crafted presets)
    // freq in semitones, Q, gain in dB
    //==========================================================================
    enum class StageType { Peaking, Lowpass };

    struct StageParams
    {
        double freqSemi = 69.0;  // A440
        double q = 1.0;
        double gainDB = 0.0;
        StageType type = StageType::Peaking;
    };

    struct MorphPoint
    {
        double morph = 0.0;
        std::array<StageParams, NUM_STAGES> stages;
    };

    struct Preset
    {
        juce::String name;
        std::vector<MorphPoint> morphPoints;
    };

    std::vector<Preset> presets;
    void initializePresets();

    //==========================================================================
    // DSP Helpers
    //==========================================================================
    void updateCoefficients();
    void updateCoefficientsFromPolar();   // NEW: Validated polar presets
    void updateCoefficientsFromCube();    // WAV cube data
    void updateCoefficientsFromLegacy();  // Hand-crafted presets (deprecated)

    // Polar preset interpolation (validated X3 data)
    std::array<PolarStageParams, NUM_STAGES> interpolatePolarStages(double morphValue) const;
    BiquadCoeffs calculatePolarCoeffs(double a1_polar, double r, int flag) const;
    double applyQToRadius(double r_ref, double qNormalized) const;

    // Legacy preset interpolation (deprecated)
    std::array<StageParams, NUM_STAGES> interpolateStages(double morphValue) const;
    BiquadCoeffs calculatePeakingCoeffs(double freqHz, double Q, double gainDB) const;
    BiquadCoeffs calculateLowpassCoeffs(double freqHz, double Q) const;

    // Pole-based interpolation (for WAV cubes)
    std::array<PoleParams, NUM_STAGES> interpolatePoleStages(double morphValue) const;
    BiquadCoeffs calculatePoleCoeffs(double a1, double r, double qOffset) const;

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(TrenchAudioProcessor)
};
