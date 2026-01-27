#include "PluginProcessor.h"
#include "PluginEditor.h"
#include "BinaryData.h"
#include <cmath>

//==============================================================================
// TRENCH Audio Processor
// Verified architecture: 7 cascaded biquads (14 poles) with pole-based morphing
// Supports both legacy presets and WAV-loaded E-mu cubes
//==============================================================================

TrenchAudioProcessor::TrenchAudioProcessor()
    : AudioProcessor(BusesProperties()
                    .withInput("Input", juce::AudioChannelSet::stereo(), true)
                    .withOutput("Output", juce::AudioChannelSet::stereo(), true)),
      apvts(*this, nullptr, "Parameters", createParameterLayout())
{
    morphParam = apvts.getRawParameterValue("morph");
    qParam = apvts.getRawParameterValue("q");
    driveParam = apvts.getRawParameterValue("drive");
    mixParam = apvts.getRawParameterValue("mix");
    outputParam = apvts.getRawParameterValue("output");
    bypassParam = apvts.getRawParameterValue("bypass");

    try
    {
        initializePresets();
    }
    catch (const std::exception& e)
    {
        DBG("TRENCH: Failed to initialize presets: " << e.what());
        // Continue with empty presets - plugin will still load
    }
    catch (...)
    {
        DBG("TRENCH: Unknown exception during preset initialization");
        // Continue with empty presets - plugin will still load
    }

    cubesLoaded = false;
}

TrenchAudioProcessor::~TrenchAudioProcessor() {}

juce::AudioProcessorValueTreeState::ParameterLayout TrenchAudioProcessor::createParameterLayout()
{
    std::vector<std::unique_ptr<juce::RangedAudioParameter>> params;

    params.push_back(std::make_unique<juce::AudioParameterFloat>(
        juce::ParameterID("morph", 1), "Morph",
        juce::NormalisableRange<float>(0.0f, 100.0f, 0.1f), 0.0f,
        juce::AudioParameterFloatAttributes().withLabel("%")));

    params.push_back(std::make_unique<juce::AudioParameterFloat>(
        juce::ParameterID("q", 1), "Q",
        juce::NormalisableRange<float>(0.0f, 100.0f, 0.1f), 50.0f,
        juce::AudioParameterFloatAttributes().withLabel("%")));

    params.push_back(std::make_unique<juce::AudioParameterFloat>(
        juce::ParameterID("drive", 1), "Drive",
        juce::NormalisableRange<float>(0.0f, 100.0f, 0.1f), 0.0f,
        juce::AudioParameterFloatAttributes().withLabel("%")));

    params.push_back(std::make_unique<juce::AudioParameterFloat>(
        juce::ParameterID("mix", 1), "Mix",
        juce::NormalisableRange<float>(0.0f, 100.0f, 0.1f), 100.0f,
        juce::AudioParameterFloatAttributes().withLabel("%")));

    params.push_back(std::make_unique<juce::AudioParameterFloat>(
        juce::ParameterID("output", 1), "Output",
        juce::NormalisableRange<float>(-24.0f, 24.0f, 0.1f), 0.0f,
        juce::AudioParameterFloatAttributes().withLabel("dB")));

    params.push_back(std::make_unique<juce::AudioParameterBool>(
        juce::ParameterID("bypass", 1), "Bypass", false));

    return { params.begin(), params.end() };
}

//==============================================================================
// SEMITONE CONVERSION (Required for musical interpolation)
//==============================================================================

static double hzToSemi(double hz)
{
    return 12.0 * std::log2(hz / 440.0) + 69.0;  // A440 = semitone 69
}

static double semiToHz(double semi)
{
    return 440.0 * std::pow(2.0, (semi - 69.0) / 12.0);
}

//==============================================================================
// VALIDATED X3 POLAR PRESET DATA
// Format: a1_polar, radius, flag (1=BP, 0=LP)
// Captured from Emulator X3 using Cheat Engine - FFT validated 2025-01-24
//==============================================================================

void TrenchAudioProcessor::initializePresets()
{
    // =========================================================================
    // TALKING HEDZ - 1:1 X3 Recreation
    // Validated against impulse response FFT: peaks within 25 Hz
    // =========================================================================
    PolarPreset talkingHedz;
    talkingHedz.name = "Talking Hedz";
    talkingHedz.morphPoints = {
        // Morph 0%
        { 0.0, {{
            { -1.974805, 0.998231, 1 },
            { -1.939721, 0.998292, 1 },
            { -1.873399, 0.998353, 1 },
            { -1.524112, 0.992679, 1 },
            { -1.997652, 0.998292, 0 },
            { -1.992054, 0.982433, 0 },
            { -2.0, 0.5, 0 }  // Stage 7: bypass
        }} },
        // Morph 25%
        { 0.25, {{
            { -1.987616, 0.998353, 1 },
            { -1.928071, 0.998338, 1 },
            { -1.867585, 0.998353, 1 },
            { -1.518988, 0.987555, 1 },
            { -1.996355, 0.998261, 0 },
            { -1.992689, 0.986090, 0 },
            { -2.0, 0.5, 0 }  // Stage 7: bypass
        }} },
        // Morph 50% - Primary validation point
        { 0.5, {{
            { -1.993596, 0.998475, 1 },
            { -1.912492, 0.998383, 1 },
            { -1.861726, 0.998353, 1 },
            { -1.510937, 0.979504, 1 },
            { -1.992010, 0.998231, 0 },
            { -1.991170, 0.988775, 0 },
            { -2.0, 0.5, 0 }  // Stage 7: bypass
        }} },
        // Morph 75%
        { 0.75, {{
            { -1.996402, 0.998597, 1 },
            { -1.896912, 0.998429, 1 },
            { -1.855866, 0.998353, 1 },
            { -1.499229, 0.967796, 1 },
            { -1.978928, 0.998200, 0 },
            { -1.984614, 0.991461, 0 },
            { -2.0, 0.5, 0 }  // Stage 7: bypass
        }} },
        // Morph 100%
        { 1.0, {{
            { -1.997743, 0.998719, 1 },
            { -1.881333, 0.998475, 1 },
            { -1.850007, 0.998353, 1 },
            { -1.476768, 0.945335, 1 },
            { -1.939599, 0.998170, 0 },
            { -1.962060, 0.993167, 0 },
            { -2.0, 0.5, 0 }  // Stage 7: bypass
        }} }
    };
    polarPresets.push_back(talkingHedz);

    // =========================================================================
    // MEATY GIZMO - Aggressive resonant character
    // =========================================================================
    PolarPreset meatyGizmo;
    meatyGizmo.name = "Meaty Gizmo";
    meatyGizmo.morphPoints = {
        { 0.0, {{
            { -1.960, 0.990, 1 },
            { -1.900, 0.985, 1 },
            { -1.820, 0.980, 1 },
            { -1.600, 0.970, 1 },
            { -1.990, 0.995, 0 },
            { -1.985, 0.980, 0 },
            { -2.0, 0.5, 0 }  // Stage 7: bypass
        }} },
        { 1.0, {{
            { -1.990, 0.995, 1 },
            { -1.950, 0.992, 1 },
            { -1.880, 0.988, 1 },
            { -1.700, 0.960, 1 },
            { -1.970, 0.998, 0 },
            { -1.950, 0.990, 0 },
            { -2.0, 0.5, 0 }  // Stage 7: bypass
        }} }
    };
    polarPresets.push_back(meatyGizmo);

    // =========================================================================
    // RADIO CRAZE - Bandpass/telephone character
    // =========================================================================
    PolarPreset radioCraze;
    radioCraze.name = "Radio Craze";
    radioCraze.morphPoints = {
        { 0.0, {{
            { -1.940, 0.997, 1 },
            { -1.850, 0.996, 1 },
            { -1.720, 0.995, 1 },
            { -1.500, 0.990, 1 },
            { -1.995, 0.998, 0 },
            { -1.990, 0.985, 0 },
            { -2.0, 0.5, 0 }  // Stage 7: bypass
        }} },
        { 1.0, {{
            { -1.985, 0.998, 1 },
            { -1.920, 0.997, 1 },
            { -1.800, 0.996, 1 },
            { -1.580, 0.985, 1 },
            { -1.980, 0.999, 0 },
            { -1.960, 0.992, 0 },
            { -2.0, 0.5, 0 }  // Stage 7: bypass
        }} }
    };
    polarPresets.push_back(radioCraze);
}

//==============================================================================
void TrenchAudioProcessor::prepareToPlay(double sampleRate, int samplesPerBlock)
{
    juce::ignoreUnused(samplesPerBlock);
    currentSampleRate = sampleRate;
    controlCounter = 0;

    // TrenchFilter disabled for debugging
    // trenchFilterL.prepare(static_cast<float>(sampleRate));
    // trenchFilterR.prepare(static_cast<float>(sampleRate));

    // Reset biquad states
    for (auto& state : biquadStatesL)
        state = BiquadState{};
    for (auto& state : biquadStatesR)
        state = BiquadState{};

    updateCoefficients();
}

void TrenchAudioProcessor::releaseResources() {}

//==============================================================================
// INTERPOLATION - All in semitone space for musical sweeps
//==============================================================================

std::array<TrenchAudioProcessor::StageParams, TrenchAudioProcessor::NUM_STAGES>
TrenchAudioProcessor::interpolateStages(double morphValue) const
{
    if (presets.empty() || currentPresetIndex >= (int)presets.size())
        return {};

    const auto& points = presets[currentPresetIndex].morphPoints;
    if (points.empty())
        return {};

    // Find surrounding morph keyframes
    size_t lo = 0, hi = points.size() - 1;
    for (size_t i = 0; i < points.size() - 1; ++i)
    {
        if (morphValue >= points[i].morph && morphValue <= points[i + 1].morph)
        {
            lo = i;
            hi = i + 1;
            break;
        }
    }

    const auto& loPoint = points[lo];
    const auto& hiPoint = points[hi];

    double range = hiPoint.morph - loPoint.morph;
    double t = range > 0.0 ? (morphValue - loPoint.morph) / range : 0.0;

    // Linear interpolation - frequencies in semitones, Q and gain direct
    std::array<StageParams, NUM_STAGES> result;
    for (int i = 0; i < NUM_STAGES; ++i)
    {
        // Interpolate semitones (critical for musical sweep)
        result[i].freqSemi = loPoint.stages[i].freqSemi +
                             t * (hiPoint.stages[i].freqSemi - loPoint.stages[i].freqSemi);
        result[i].q = loPoint.stages[i].q + t * (hiPoint.stages[i].q - loPoint.stages[i].q);
        result[i].gainDB = loPoint.stages[i].gainDB +
                           t * (hiPoint.stages[i].gainDB - loPoint.stages[i].gainDB);
        result[i].type = loPoint.stages[i].type;
    }

    return result;
}

//==============================================================================
// COEFFICIENT CALCULATION - Verified formulas from Audio EQ Cookbook
//==============================================================================

TrenchAudioProcessor::BiquadCoeffs
TrenchAudioProcessor::calculatePeakingCoeffs(double freqHz, double Q, double gainDB) const
{
    BiquadCoeffs c;

    double A = std::pow(10.0, gainDB / 40.0);  // Amplitude factor
    double omega = 2.0 * juce::MathConstants<double>::pi * freqHz / currentSampleRate;
    double sinW = std::sin(omega);
    double cosW = std::cos(omega);
    double alpha = sinW / (2.0 * Q);

    double a0;
    if (gainDB >= 0.0)
    {
        // BOOST: creates resonant peak
        c.b0 = 1.0 + alpha * A;
        c.b1 = -2.0 * cosW;
        c.b2 = 1.0 - alpha * A;
        a0   = 1.0 + alpha / A;
        c.a1 = -2.0 * cosW;
        c.a2 = 1.0 - alpha / A;
    }
    else
    {
        // CUT: creates notch
        c.b0 = 1.0 + alpha / A;
        c.b1 = -2.0 * cosW;
        c.b2 = 1.0 - alpha / A;
        a0   = 1.0 + alpha * A;
        c.a1 = -2.0 * cosW;
        c.a2 = 1.0 - alpha * A;
    }

    // Normalize by a0
    c.b0 /= a0;
    c.b1 /= a0;
    c.b2 /= a0;
    c.a1 /= a0;
    c.a2 /= a0;

    return c;
}

TrenchAudioProcessor::BiquadCoeffs
TrenchAudioProcessor::calculateLowpassCoeffs(double freqHz, double Q) const
{
    BiquadCoeffs c;

    double omega = 2.0 * juce::MathConstants<double>::pi * freqHz / currentSampleRate;
    double sinW = std::sin(omega);
    double cosW = std::cos(omega);
    double alpha = sinW / (2.0 * Q);

    c.b0 = (1.0 - cosW) / 2.0;
    c.b1 = 1.0 - cosW;
    c.b2 = (1.0 - cosW) / 2.0;
    double a0 = 1.0 + alpha;
    c.a1 = -2.0 * cosW;
    c.a2 = 1.0 - alpha;

    // Normalize
    c.b0 /= a0;
    c.b1 /= a0;
    c.b2 /= a0;
    c.a1 /= a0;
    c.a2 /= a0;

    return c;
}

void TrenchAudioProcessor::updateCoefficients()
{
    // Route to appropriate coefficient calculation based on mode
    if (cubesLoaded && currentCubeIndex >= 0)
    {
        updateCoefficientsFromCube();
    }
    else if (!polarPresets.empty() && currentPresetIndex < (int)polarPresets.size())
    {
        // Use validated polar presets (1:1 X3 recreation)
        updateCoefficientsFromPolar();
    }
    else
    {
        updateCoefficientsFromLegacy();
    }
}

//==============================================================================
// POLAR PRESET COEFFICIENT UPDATE (Validated X3 data)
//==============================================================================

void TrenchAudioProcessor::updateCoefficientsFromPolar()
{
    double morphNorm = morphParam->load() / 100.0;
    double qKnobNorm = qParam->load() / 100.0;

    auto polarStages = interpolatePolarStages(morphNorm);

    for (int i = 0; i < NUM_STAGES; ++i)
    {
        // Apply Q scaling to radius
        double r_scaled = applyQToRadius(polarStages[i].r, qKnobNorm);
        currentCoeffs[i] = calculatePolarCoeffs(polarStages[i].a1, r_scaled, polarStages[i].flag);
    }
}

//==============================================================================
// POLAR INTERPOLATION (Linear in polar space)
//==============================================================================

std::array<TrenchAudioProcessor::PolarStageParams, TrenchAudioProcessor::NUM_STAGES>
TrenchAudioProcessor::interpolatePolarStages(double morphValue) const
{
    std::array<PolarStageParams, NUM_STAGES> result;

    if (polarPresets.empty() || currentPresetIndex >= (int)polarPresets.size())
    {
        // Return bypass defaults
        for (auto& p : result)
        {
            p.a1 = -2.0;
            p.r = 0.5;
            p.flag = 1;
        }
        return result;
    }

    const auto& points = polarPresets[currentPresetIndex].morphPoints;
    if (points.empty())
        return result;

    // Find surrounding morph keyframes
    size_t lo = 0, hi = points.size() - 1;
    for (size_t i = 0; i < points.size() - 1; ++i)
    {
        if (morphValue >= points[i].morph && morphValue <= points[i + 1].morph)
        {
            lo = i;
            hi = i + 1;
            break;
        }
    }

    const auto& loPoint = points[lo];
    const auto& hiPoint = points[hi];

    double range = hiPoint.morph - loPoint.morph;
    double t = range > 0.0 ? (morphValue - loPoint.morph) / range : 0.0;

    // Linear interpolation of a1_polar and radius SEPARATELY
    for (int i = 0; i < NUM_STAGES; ++i)
    {
        result[i].a1 = loPoint.stages[i].a1 + t * (hiPoint.stages[i].a1 - loPoint.stages[i].a1);
        result[i].r = loPoint.stages[i].r + t * (hiPoint.stages[i].r - loPoint.stages[i].r);
        result[i].flag = loPoint.stages[i].flag;  // Flag doesn't interpolate
    }

    return result;
}

//==============================================================================
// Q SCALING (Exponential radius adjustment)
// r_new = r_ref^(Q_ref / Q_new)
//==============================================================================

double TrenchAudioProcessor::applyQToRadius(double r_ref, double qNormalized) const
{
    // Q knob 0-1 maps to Q 0.5% - 100%
    constexpr double Q_REF = 100.0;
    double Q_new = 0.5 + qNormalized * 99.5;

    if (Q_new <= 0.0) return 0.5;
    if (r_ref <= 0.0 || r_ref >= 1.0) return r_ref;

    // Exponential scaling
    double r = std::exp(std::log(r_ref) * (Q_REF / Q_new));

    // Clamp to valid range (don't exceed reference)
    return juce::jlimit(0.3, r_ref, r);
}

//==============================================================================
// POLAR TO BIQUAD COEFFICIENT CALCULATION
// Uses flag to determine numerator type:
//   flag=1: Bandpass (zeros at DC and Nyquist)
//   flag=0: Lowpass (unity DC gain)
//==============================================================================

TrenchAudioProcessor::BiquadCoeffs
TrenchAudioProcessor::calculatePolarCoeffs(double a1_polar, double r, int flag) const
{
    BiquadCoeffs c;

    // Clamp radius for stability
    double radius = std::min(r, 0.9999);

    // NOW multiply a1 by radius (critical step!)
    c.a1 = a1_polar * radius;
    c.a2 = radius * radius;

    if (flag == 1)
    {
        // BANDPASS: zeros at DC (z=1) and Nyquist (z=-1)
        // H(z) numerator = (1 - z^-2) scaled
        double scale = (1.0 - c.a2) * 0.5;
        c.b0 = scale;
        c.b1 = 0.0;
        c.b2 = -scale;
    }
    else
    {
        // LOWPASS: unity DC gain
        // H(z) numerator = (1 + z^-1)^2 scaled
        double norm = (1.0 + c.a1 + c.a2) * 0.25;
        c.b0 = norm;
        c.b1 = 2.0 * norm;
        c.b2 = norm;
    }

    return c;
}

//==============================================================================
// CUBE-BASED COEFFICIENT UPDATE (from WAV data)
//==============================================================================

void TrenchAudioProcessor::updateCoefficientsFromCube()
{
    double morphNorm = morphParam->load() / 100.0;
    double qKnobNorm = qParam->load() / 100.0;

    // Q offset affects pole radius (higher Q = tighter bandwidth = higher r)
    double qOffset = qKnobNorm * 0.1;  // Subtle radius adjustment

    auto poleStages = interpolatePoleStages(morphNorm);

    for (int i = 0; i < NUM_STAGES; ++i)
    {
        currentCoeffs[i] = calculatePoleCoeffs(poleStages[i].a1, poleStages[i].r, qOffset);
    }
}

//==============================================================================
// LEGACY COEFFICIENT UPDATE (hand-crafted presets)
//==============================================================================

void TrenchAudioProcessor::updateCoefficientsFromLegacy()
{
    double morphNorm = morphParam->load() / 100.0;
    double qKnobNorm = qParam->load() / 100.0;

    // Q knob ADDS to all stage Q values (additive, not multiplicative)
    double qOffset = qKnobNorm * 10.0;  // 0-10 range addition

    auto stages = interpolateStages(morphNorm);

    for (int i = 0; i < NUM_STAGES; ++i)
    {
        // Convert semitones to Hz AFTER interpolation (critical!)
        double freqHz = semiToHz(stages[i].freqSemi);
        freqHz = juce::jlimit(20.0, 20000.0, freqHz);

        // Apply additive Q offset
        double effectiveQ = std::max(0.5, stages[i].q + qOffset);

        if (stages[i].type == StageType::Lowpass)
        {
            currentCoeffs[i] = calculateLowpassCoeffs(freqHz, effectiveQ);
        }
        else
        {
            currentCoeffs[i] = calculatePeakingCoeffs(freqHz, effectiveQ, stages[i].gainDB);
        }
    }
}

//==============================================================================
// POLE-BASED INTERPOLATION (for WAV cubes)
//==============================================================================

std::array<TrenchAudioProcessor::PoleParams, TrenchAudioProcessor::NUM_STAGES>
TrenchAudioProcessor::interpolatePoleStages(double morphValue) const
{
    std::array<PoleParams, NUM_STAGES> result;

    const WavCubeLoader::Cube* cube = cubeLoader.getCube(currentCubeIndex);
    if (cube == nullptr || cube->morphPoints.empty())
    {
        // Return bypass defaults
        for (auto& p : result)
        {
            p.a1 = -2.0;
            p.r = 0.5;
        }
        return result;
    }

    const auto& points = cube->morphPoints;

    // Find surrounding morph keyframes
    size_t lo = 0, hi = points.size() - 1;
    for (size_t i = 0; i < points.size() - 1; ++i)
    {
        if (morphValue >= points[i].morph && morphValue <= points[i + 1].morph)
        {
            lo = i;
            hi = i + 1;
            break;
        }
    }

    const auto& loPoint = points[lo];
    const auto& hiPoint = points[hi];

    double range = hiPoint.morph - loPoint.morph;
    double t = range > 0.0 ? (morphValue - loPoint.morph) / range : 0.0;

    // Linear interpolation of pole parameters
    // a1 is already in cos domain, r is radius - both interpolate linearly
    for (int i = 0; i < NUM_STAGES; ++i)
    {
        result[i].a1 = loPoint.stages[i].a1 + t * (hiPoint.stages[i].a1 - loPoint.stages[i].a1);
        result[i].r = loPoint.stages[i].r + t * (hiPoint.stages[i].r - loPoint.stages[i].r);
    }

    return result;
}

//==============================================================================
// POLE-TO-BIQUAD COEFFICIENT CALCULATION
// Converts polar representation (a1, r) to full biquad coefficients
//==============================================================================

TrenchAudioProcessor::BiquadCoeffs
TrenchAudioProcessor::calculatePoleCoeffs(double a1, double r, double qOffset) const
{
    BiquadCoeffs c;

    // Apply Q offset to radius (higher Q = higher r = narrower bandwidth)
    double effectiveR = juce::jlimit(0.5, 0.9999, r + qOffset);

    // Denominator coefficients from pole placement
    // For conjugate poles at r*e^(±jθ): a1 = -2r*cos(θ), a2 = r²
    c.a1 = a1 * effectiveR / r;  // Scale a1 with new radius
    c.a2 = effectiveR * effectiveR;

    // Numerator: Resonator configuration
    // H(z) = (1-r) / (1 + a1*z^-1 + a2*z^-2)
    // This creates a peak at the pole frequency
    double gain = 1.0 - effectiveR;  // Normalize gain

    c.b0 = gain;
    c.b1 = 0.0;
    c.b2 = 0.0;

    return c;
}

//==============================================================================
// PROCESSING - 7-stage cascade (14 poles) with control rate limiting
//==============================================================================

void TrenchAudioProcessor::processBlock(juce::AudioBuffer<float>& buffer,
                                         juce::MidiBuffer& midiMessages)
{
    juce::ScopedNoDenormals noDenormals;
    juce::ignoreUnused(midiMessages);

    const int numChannels = buffer.getNumChannels();
    const int numSamples = buffer.getNumSamples();

    // Get parameter values
    const bool bypassed = bypassParam->load() > 0.5f;
    const float driveAmount = driveParam->load() / 100.0f;  // 0-1
    const float mixAmount = mixParam->load() / 100.0f;      // 0-1
    const float outputGain = std::pow(10.0f, outputParam->load() / 20.0f);  // dB to linear

    // If bypassed, just apply output gain and return
    if (bypassed)
    {
        buffer.applyGain(outputGain);
        return;
    }

    // Process using biquad cascade (cube/polar mode)
    for (int s = 0; s < numSamples; ++s)
    {
        // Control rate: update coefficients every 128 samples
        if (++controlCounter >= CONTROL_RATE)
        {
            controlCounter = 0;
            updateCoefficients();
        }

        // Process each channel
        for (int ch = 0; ch < numChannels; ++ch)
        {
            auto* channelData = buffer.getWritePointer(ch);
            auto& states = (ch == 0) ? biquadStatesL : biquadStatesR;

            double dry = channelData[s];
            double x = dry;

            // Apply drive (soft saturation before filter)
            if (driveAmount > 0.0f)
            {
                double driveGain = 1.0 + driveAmount * 15.0;  // Up to 16x gain
                x *= driveGain;
                x = std::tanh(x);  // Soft clip
            }

            // 7-stage cascade (14-pole Z-Plane filter)
            for (int stage = 0; stage < NUM_STAGES; ++stage)
            {
                const auto& c = currentCoeffs[stage];
                auto& st = states[stage];

                // Transposed Direct Form II
                double y = c.b0 * x + st.z1;
                st.z1 = c.b1 * x - c.a1 * y + st.z2;
                st.z2 = c.b2 * x - c.a2 * y;
                x = y;
            }

            // Wet/dry mix
            double wet = x;
            double mixed = dry * (1.0 - mixAmount) + wet * mixAmount;

            // Output gain
            channelData[s] = static_cast<float>(mixed * outputGain);
        }
    }
}

//==============================================================================
// FREQUENCY RESPONSE - For LCD display
//==============================================================================

std::vector<float> TrenchAudioProcessor::getFrequencyResponse() const
{
    const int numPoints = 256;
    std::vector<float> response(numPoints);

    double morphNorm = morphParam->load() / 100.0;
    double qKnobNorm = qParam->load() / 100.0;

    // Calculate coefficients for display based on current mode
    std::array<BiquadCoeffs, NUM_STAGES> coeffs;

    if (cubesLoaded && currentCubeIndex >= 0)
    {
        // Pole-based mode (WAV cubes)
        double qOffset = qKnobNorm * 0.1;
        auto poleStages = interpolatePoleStages(morphNorm);

        for (int i = 0; i < NUM_STAGES; ++i)
        {
            coeffs[i] = calculatePoleCoeffs(poleStages[i].a1, poleStages[i].r, qOffset);
        }
    }
    else if (!polarPresets.empty() && currentPresetIndex < (int)polarPresets.size())
    {
        // Validated polar presets (1:1 X3 recreation)
        auto polarStages = interpolatePolarStages(morphNorm);

        for (int i = 0; i < NUM_STAGES; ++i)
        {
            double r_scaled = applyQToRadius(polarStages[i].r, qKnobNorm);
            coeffs[i] = calculatePolarCoeffs(polarStages[i].a1, r_scaled, polarStages[i].flag);
        }
    }
    else
    {
        // Legacy mode (hand-crafted presets)
        double qOffset = qKnobNorm * 10.0;
        auto stages = interpolateStages(morphNorm);

        for (int i = 0; i < NUM_STAGES; ++i)
        {
            double freqHz = juce::jlimit(20.0, 20000.0, semiToHz(stages[i].freqSemi));
            double effectiveQ = std::max(0.5, stages[i].q + qOffset);

            if (stages[i].type == StageType::Lowpass)
                coeffs[i] = calculateLowpassCoeffs(freqHz, effectiveQ);
            else
                coeffs[i] = calculatePeakingCoeffs(freqHz, effectiveQ, stages[i].gainDB);
        }
    }

    // Calculate magnitude response
    for (int i = 0; i < numPoints; ++i)
    {
        double t = i / (double)(numPoints - 1);
        double freqHz = 20.0 * std::pow(1000.0, t);  // 20Hz to 20kHz log

        double omega = 2.0 * juce::MathConstants<double>::pi * freqHz / currentSampleRate;
        double cosW = std::cos(omega);
        double cos2W = std::cos(2.0 * omega);
        double sinW = std::sin(omega);
        double sin2W = std::sin(2.0 * omega);

        double magnitude = 1.0;

        // Cascade: multiply magnitudes
        for (int stage = 0; stage < NUM_STAGES; ++stage)
        {
            const auto& c = coeffs[stage];

            double numReal = c.b0 + c.b1 * cosW + c.b2 * cos2W;
            double numImag = -c.b1 * sinW - c.b2 * sin2W;
            double denReal = 1.0 + c.a1 * cosW + c.a2 * cos2W;
            double denImag = -c.a1 * sinW - c.a2 * sin2W;

            double numMag = std::sqrt(numReal * numReal + numImag * numImag);
            double denMag = std::sqrt(denReal * denReal + denImag * denImag);

            magnitude *= (denMag > 0.0) ? (numMag / denMag) : 0.0;
        }

        double dB = 20.0 * std::log10(std::max(magnitude, 0.0001));
        response[i] = static_cast<float>(juce::jlimit(-36.0, 24.0, dB));
    }

    return response;
}

//==============================================================================
juce::StringArray TrenchAudioProcessor::getPresetNames() const
{
    // If cubes are loaded, return cube names; otherwise polar presets
    if (cubesLoaded)
    {
        return cubeLoader.getCubeNames();
    }

    juce::StringArray names;
    for (const auto& preset : polarPresets)
        names.add(preset.name);
    return names;
}

void TrenchAudioProcessor::setPresetIndex(int index)
{
    if (cubesLoaded)
    {
        setCubeIndex(index);
    }
    else if (index >= 0 && index < (int)polarPresets.size())
    {
        currentPresetIndex = index;
        updateCoefficients();
    }
}

//==============================================================================
// CUBE LOADING (Binary preferred - this is the decoded data)
//==============================================================================

bool TrenchAudioProcessor::loadCubesFromBinary(const juce::String& path)
{
    return loadCubesFromBinary(juce::File(path));
}

bool TrenchAudioProcessor::loadCubesFromBinary(const juce::File& binFile)
{
    if (cubeLoader.loadFromBinary(binFile))
    {
        cubesLoaded = true;
        wavFilePath = binFile.getFullPathName();
        currentCubeIndex = 0;

        DBG("TRENCH: Loaded " << cubeLoader.getNumCubes() << " cubes from " << binFile.getFileName());

        // Reset biquad states
        for (auto& state : biquadStatesL)
            state = BiquadState{};
        for (auto& state : biquadStatesR)
            state = BiquadState{};

        updateCoefficients();
        return true;
    }

    DBG("TRENCH: Failed to load binary: " << cubeLoader.getLastError());
    return false;
}

//==============================================================================
// WAV CUBE LOADING (fallback - may not decode correctly)
//==============================================================================

bool TrenchAudioProcessor::loadCubesFromWav(const juce::String& path)
{
    return loadCubesFromWav(juce::File(path));
}

bool TrenchAudioProcessor::loadCubesFromWav(const juce::File& wavFile)
{
    if (cubeLoader.loadFromWav(wavFile))
    {
        cubesLoaded = true;
        wavFilePath = wavFile.getFullPathName();
        currentCubeIndex = 0;

        DBG("TRENCH: Loaded " << cubeLoader.getNumCubes() << " cubes from " << wavFile.getFileName());

        // Reset biquad states when loading new cubes
        for (auto& state : biquadStatesL)
            state = BiquadState{};
        for (auto& state : biquadStatesR)
            state = BiquadState{};

        updateCoefficients();
        return true;
    }

    DBG("TRENCH: Failed to load cubes: " << cubeLoader.getLastError());
    return false;
}

void TrenchAudioProcessor::setCubeIndex(int index)
{
    if (cubesLoaded && index >= 0 && index < cubeLoader.getNumCubes())
    {
        currentCubeIndex = index;
        updateCoefficients();
    }
}

//==============================================================================
void TrenchAudioProcessor::getStateInformation(juce::MemoryBlock& destData)
{
    auto state = apvts.copyState();
    state.setProperty("presetIndex", currentPresetIndex, nullptr);
    state.setProperty("cubeIndex", currentCubeIndex, nullptr);
    state.setProperty("wavFilePath", wavFilePath, nullptr);
    state.setProperty("cubesLoaded", cubesLoaded, nullptr);
    std::unique_ptr<juce::XmlElement> xml(state.createXml());
    copyXmlToBinary(*xml, destData);
}

void TrenchAudioProcessor::setStateInformation(const void* data, int sizeInBytes)
{
    std::unique_ptr<juce::XmlElement> xml(getXmlFromBinary(data, sizeInBytes));
    if (xml != nullptr && xml->hasTagName(apvts.state.getType()))
    {
        auto state = juce::ValueTree::fromXml(*xml);
        apvts.replaceState(state);

        currentPresetIndex = state.getProperty("presetIndex", 0);
        currentCubeIndex = state.getProperty("cubeIndex", 0);

        // Restore WAV file if it was loaded
        juce::String savedPath = state.getProperty("wavFilePath", "").toString();
        if (savedPath.isNotEmpty() && state.getProperty("cubesLoaded", false))
        {
            juce::File wavFile(savedPath);
            if (wavFile.existsAsFile())
            {
                loadCubesFromWav(wavFile);
                currentCubeIndex = state.getProperty("cubeIndex", 0);
            }
        }

        updateCoefficients();
    }
}

//==============================================================================
juce::AudioProcessorEditor* TrenchAudioProcessor::createEditor()
{
    return new TrenchAudioProcessorEditor(*this);
}

juce::AudioProcessor* JUCE_CALLTYPE createPluginFilter()
{
    return new TrenchAudioProcessor();
}
