/*
  ==============================================================================

    ZPlaneFilter.cpp
    Project TRENCH - Validated Z-Plane Filter Implementation

    This implementation matches the VALIDATED render_trench.cpp exactly.
    All formulas and coefficients are from Golden Master captures (Jan 28, 2026).

  ==============================================================================
*/

#include "ZPlaneFilter.h"

// ==============================================================================
// GOLDEN MASTER DATA (from CLAUDE.md 2026-01-28)
// ==============================================================================

const ZPlaneFilter::Keyframe ZPlaneFilter::M0_Q100 = {
    {
        {-1.974805, 0.998231, 0.548706, -0.214841, 0.283027, false},  // S0: 1035 Hz
        {-1.939721, 0.998292, 0.548706,  0.000000, 0.548704, false},  // S1: 1679 Hz
        {-1.873399, 0.998353, 0.548706, -0.960298, 0.522998, false},  // S2: 2480 Hz
        {-1.524112, 0.992679, 0.548706, -0.617493, 0.548704, false},  // S3: 4882 Hz
        {-1.997652, 0.998292, 0.0, 0.0, 0.0, true}                    // S4: Lowpass
    },
    1.762177
};

const ZPlaneFilter::Keyframe ZPlaneFilter::M0_Q0 = {
    {
        {-1.938511, 0.959007, 0.561890, -0.246341, 0.316166, false},
        {-1.892624, 0.955101, 0.561890, -0.579652, 0.561888, false},
        {-1.853366, 0.993899, 0.561890, -0.970202, 0.531174, false},
        {-1.398666, 0.898483, 0.561890, -1.022866, 0.518018, false},
        {-1.981336, 0.982433, 0.0, 0.0, 0.0, true}
    },
    1.765472
};

const ZPlaneFilter::Keyframe ZPlaneFilter::M100_Q100 = {
    {
        {-1.997743, 0.998719, 0.511475, -0.415885, 0.207911, false},
        {-1.881333, 0.998475, 0.511475,  0.958517, 0.511473, false},
        {-1.850007, 0.998353, 0.511475, -0.885161, 0.457553, false},
        {-1.476768, 0.945335, 0.511475, -0.864006, 0.000000, false},
        {-1.939599, 0.998170, 0.0, 0.0, 0.0, true}
    },
    1.752869
};

const ZPlaneFilter::Keyframe ZPlaneFilter::M100_Q0 = {
    {
        {-1.983283, 0.984381, 0.521606, -0.407823, 0.244630, false},
        {-1.824333, 0.964867, 0.521606,  0.977505, 0.521605, false},
        {-1.783306, 0.970715, 0.521606, -0.885161, 0.457553, false},
        {-1.344162, 0.875046, 0.521606, -0.864006, 0.000000, false},
        {-1.911181, 0.993167, 0.0, 0.0, 0.0, true}
    },
    1.755402
};

// ==============================================================================
// CONSTRUCTOR / DESTRUCTOR
// ==============================================================================

ZPlaneFilter::ZPlaneFilter()
{
}

// ==============================================================================
// PUBLIC METHODS
// ==============================================================================

void ZPlaneFilter::prepare(double newSampleRate)
{
    sampleRate = newSampleRate;
    reset();
    updateCoefficients(0.0, 1.0);  // Initialize to M0_Q100
}

void ZPlaneFilter::reset()
{
    for (int i = 0; i < 5; i++) {
        stages[i].reset();
    }
}

void ZPlaneFilter::setParameters(double morphPosition, double qPosition)
{
    updateCoefficients(morphPosition, qPosition);
}

void ZPlaneFilter::setDebugOscillator(bool enabled)
{
    debugOscEnabled = enabled;
    if (enabled)
    {
        oscPhase = 0.0;
        oscIncrement = 179.0 / sampleRate;  // F3 = 179 Hz (matches X3 reference)
    }
}

double ZPlaneFilter::processSample(double input)
{
    // Boost is baked into stage 0 coefficients (updateCoefficients)
    double out = input;

    // CASCADE 5 stages with soft clipping
    for (int i = 0; i < 5; i++) {
        out = stages[i].process(out);
        out = std::clamp(out, -10.0, 10.0);  // Prevent explosion
    }

    // Final safety clipping
    out = std::clamp(out, -1.0, 1.0);

    return out;
}

void ZPlaneFilter::processBlock(juce::AudioBuffer<float>& buffer)
{
    int numChannels = buffer.getNumChannels();
    int numSamples = buffer.getNumSamples();

    for (int channel = 0; channel < numChannels; ++channel)
    {
        auto* channelData = buffer.getWritePointer(channel);

        for (int sample = 0; sample < numSamples; ++sample)
        {
            double input;

            // Generate F3 sawtooth if debug oscillator enabled
            if (debugOscEnabled)
            {
                // Sawtooth wave: -1 to +1
                input = (2.0 * oscPhase) - 1.0;
                input *= 0.5;  // Scale to ±0.5 (-6 dB pad)

                oscPhase += oscIncrement;
                if (oscPhase >= 1.0) oscPhase -= 1.0;
            }
            else
            {
                input = (double)channelData[sample];
            }

            double output = processSample(input);

            channelData[sample] = (float)output;
        }
    }
}

// ==============================================================================
// PRIVATE METHODS
// ==============================================================================

double ZPlaneFilter::lerp(double a, double b, double t)
{
    return a + t * (b - a);
}

ZPlaneFilter::StageData ZPlaneFilter::interpolateStage(const StageData& A, const StageData& B, double t, double sampleRate)
{
    // CLAUDE.md spec: "Interpolate ALL values linearly"
    // Direct linear interpolation of captured values (NOT polar space)
    double radius = lerp(A.radius, B.radius, t);

    // CRITICAL: Clamp radius to prevent instability
    radius = std::clamp(radius, 0.0, MAX_RADIUS);

    return {
        lerp(A.a1, B.a1, t),
        radius,
        lerp(A.val1, B.val1, t),
        lerp(A.val2, B.val2, t),
        lerp(A.val3, B.val3, t),
        A.isLowpass
    };
}

void ZPlaneFilter::updateCoefficients(double morph, double q)
{
    morph = std::clamp(morph, 0.0, 1.0);
    q = std::clamp(q, 0.0, 1.0);

    // Interpolate boost factor (will normalize later based on freq response)
    double boostStart = lerp(M0_Q0.boost, M0_Q100.boost, q);
    double boostEnd = lerp(M100_Q0.boost, M100_Q100.boost, q);
    double rawBoost = lerp(boostStart, boostEnd, morph);

    // 4-corner bilinear interpolation
    for (int i = 0; i < 5; i++)
    {
        // Interpolate along Q axis first
        StageData start = interpolateStage(M0_Q0.stages[i], M0_Q100.stages[i], q, sampleRate);
        StageData end = interpolateStage(M100_Q0.stages[i], M100_Q100.stages[i], q, sampleRate);

        // Then along Morph axis
        StageData curr = interpolateStage(start, end, morph, sampleRate);

        // Calculate biquad coefficients
        double r = std::min(curr.radius, MAX_RADIUS);
        double a2 = r * r;

        // ==============================================================
        // STABILITY CHECK (from Python golden_master_talkinghedz.py)
        // ==============================================================
        // For biquad stability, need |a1| < 1 + a2
        // Clamp a1 to just inside stability boundary
        double stabilityLimit = 1.0 + a2 - 0.001;
        double a1 = curr.a1;
        if (std::abs(a1) > stabilityLimit) {
            a1 = (a1 < 0) ? -stabilityLimit : stabilityLimit;
        }

        // ==============================================================
        // FLAG LOGIC: Two distinct mathematical models
        // ==============================================================
        // Common variables:
        // - a1: interpolated from morph tables (clamped -1.999 to 1.999)
        // - a2: radius² (pole magnitude)

        // ==============================================================
        // UNIFIED WITCHCRAFT FORMULA (ALL STAGES)
        // ==============================================================
        // Stage 4 has val1=val2=val3=0.0, which gives:
        //   b0 = 1.0 + 0.0 = 1.0
        //   b1 = a1 + 0.0 = a1
        //   b2 = a2 - 0.0 = a2
        // This creates a minimum-phase allpass, NOT a lowpass!
        //
        // Hypothesis: ALL stages use the same formula, Stage 4 just has
        // zero offsets which happens to produce allpass behavior.

        if (curr.isLowpass) {
            // ==============================================================
            // LOWPASS STAGE (flag = 0) - RBJ 15kHz Lowpass
            // ==============================================================
            // From golden_master_talking_hedz.py (WORKS!)
            // Uses standard RBJ lowpass at 15kHz, NOT the captured pole positions
            constexpr double freq_lp = 15000.0;
            constexpr double PI = 3.14159265358979323846;
            double omega = 2.0 * PI * freq_lp / sampleRate;
            constexpr double Q_lp = 0.707;
            double alpha = std::sin(omega) / (2.0 * Q_lp);

            double b0_lp = (1.0 - std::cos(omega)) / 2.0;
            double b1_lp = 1.0 - std::cos(omega);
            double b2_lp = (1.0 - std::cos(omega)) / 2.0;
            double a0_lp = 1.0 + alpha;
            double a1_lp = -2.0 * std::cos(omega);
            double a2_lp = 1.0 - alpha;

            // Note: Lowpass uses its own a1_lp, not the clamped a1
            stages[i].b0 = b0_lp / a0_lp;
            stages[i].b1 = b1_lp / a0_lp;
            stages[i].b2 = b2_lp / a0_lp;
            stages[i].a1 = a1_lp / a0_lp;
            stages[i].a2 = a2_lp / a0_lp;

        } else {
            // ==============================================================
            // WITCHCRAFT FORMULA + DC POLE NORMALIZATION
            // ==============================================================
            // From golden_master_talkinghedz.py (WORKING IMPLEMENTATION)

            double b0 = 1.0 + curr.val1;
            double b1 = a1 + curr.val2;  // Use clamped a1
            double b2 = a2 - curr.val3;  // MINUS val3!

            // CRITICAL: DC Pole Normalization (missing from previous implementation!)
            // When pole is near DC (a1 ≈ -2, a2 ≈ 1), scale numerator to prevent explosion
            double dc_denom = 1.0 + a1 + a2;  // Use clamped a1
            if (std::abs(dc_denom) < 0.01) {
                // DC pole detected - normalize to prevent extreme gain
                double dc_numer = b0 + b1 + b2;
                if (std::abs(dc_numer) > 0.001) {
                    double scale = std::abs(dc_denom) / std::abs(dc_numer) * 10.0;
                    b0 *= scale;
                    b1 *= scale;
                    b2 *= scale;
                }
            }

            // DON'T apply boost yet - will normalize after computing cascade response
            stages[i].b0 = b0;
            stages[i].b1 = b1;
            stages[i].b2 = b2;
            stages[i].a1 = a1;  // Use clamped a1
            stages[i].a2 = a2;
        }
    }

    // ==============================================================
    // FREQUENCY-DOMAIN GAIN NORMALIZATION
    // ==============================================================
    // Compute cascade peak gain and normalize boost if needed
    // This matches Python: max_gain = np.max(np.abs(h)) * total_gain
    double peakGain = computeCascadePeakGain();
    double maxGainWithBoost = peakGain * rawBoost;

    currentBoost = rawBoost;
    if (maxGainWithBoost > 100.0) {
        // Normalize to target ~10-20 linear (~20 dB)
        double normFactor = 10.0 / maxGainWithBoost;
        currentBoost *= normFactor;
    }

    // Apply normalized boost to FIRST stage numerator
    stages[0].b0 *= currentBoost;
    stages[0].b1 *= currentBoost;
    stages[0].b2 *= currentBoost;

    // Debug: Print coefficients for M100 corners
    if (std::abs(morph - 1.0) < 0.01) {
        static bool printed_q1 = false;
        static bool printed_q0 = false;

        if (std::abs(q - 1.0) < 0.01 && !printed_q1) {
            printf("\nC++ M100_Q100 coefficients (AFTER boost):\n");
            for (int i = 0; i < 5; i++) {
                printf("  S%d: b=[%9.6f, %9.6f, %9.6f]  a=[1.0, %9.6f, %9.6f]\n",
                       i, stages[i].b0, stages[i].b1, stages[i].b2,
                       stages[i].a1, stages[i].a2);
            }
            printed_q1 = true;
        }

        if (std::abs(q - 0.0) < 0.01 && !printed_q0) {
            printf("\nC++ M100_Q0 coefficients (AFTER boost):\n");
            for (int i = 0; i < 5; i++) {
                printf("  S%d: b=[%9.6f, %9.6f, %9.6f]  a=[1.0, %9.6f, %9.6f]\n",
                       i, stages[i].b0, stages[i].b1, stages[i].b2,
                       stages[i].a1, stages[i].a2);
            }
            printed_q0 = true;
        }
    }
}

double ZPlaneFilter::computeCascadePeakGain() const
{
    // Evaluate cascade frequency response at 1024 frequency points
    // Returns the maximum magnitude |H(f)|
    // CRITICAL: Must use 1024 to match Python sosfreqz (catches sharp resonances)
    constexpr int NUM_FREQS = 1024;
    constexpr double PI = 3.14159265358979323846;
    double maxMag = 0.0;
    int maxK = 0;

    for (int k = 0; k < NUM_FREQS; k++)
    {
        // Frequency from DC to Nyquist
        // CRITICAL: Match scipy.signal.sosfreqz grid (ENDPOINT EXCLUDED)
        double omega = PI * k / NUM_FREQS;

        // e^(-jω) = cos(ω) - j×sin(ω)
        double cosW = std::cos(omega);
        double sinW = std::sin(omega);

        // Cascade all 5 stages
        double realTotal = 1.0;
        double imagTotal = 0.0;

        for (int i = 0; i < 5; i++)
        {
            const BiquadDFI& stage = stages[i];

            // Numerator: b0 + b1×z^-1 + b2×z^-2
            // z^-1 = cos(ω) - j×sin(ω)
            // z^-2 = cos(2ω) - j×sin(2ω)
            double cos2W = std::cos(2.0 * omega);
            double sin2W = std::sin(2.0 * omega);

            double numReal = stage.b0 + stage.b1 * cosW + stage.b2 * cos2W;
            double numImag = -stage.b1 * sinW - stage.b2 * sin2W;

            // Denominator: 1 + a1×z^-1 + a2×z^-2
            double denReal = 1.0 + stage.a1 * cosW + stage.a2 * cos2W;
            double denImag = -stage.a1 * sinW - stage.a2 * sin2W;

            // H_stage = numerator / denominator (complex division)
            double denMag2 = denReal * denReal + denImag * denImag;
            double stageReal = (numReal * denReal + numImag * denImag) / denMag2;
            double stageImag = (numImag * denReal - numReal * denImag) / denMag2;

            // Multiply into cascade: H_total *= H_stage
            double newReal = realTotal * stageReal - imagTotal * stageImag;
            double newImag = realTotal * stageImag + imagTotal * stageReal;
            realTotal = newReal;
            imagTotal = newImag;
        }

        // Magnitude of cascade at this frequency
        double mag = std::sqrt(realTotal * realTotal + imagTotal * imagTotal);
        if (mag > maxMag) {
            maxMag = mag;
            maxK = k;
        }
    }

    // Debug: Print peak bin, omega, and frequency
    static int callCount = 0;
    if (callCount < 10) {
        double peakOmega = PI * maxK / NUM_FREQS;  // Matches scipy: ENDPOINT EXCLUDED
        double peakFreqHz = peakOmega * sampleRate / (2.0 * PI);
        printf("    [C++ Peak: k=%d, ω=%.10f rad/sample, f=%.1f Hz, mag=%.1f]\n",
               maxK, peakOmega, peakFreqHz, maxMag);
        printf("    [C++ Grid: NUM_FREQS=%d, endpoint=%s]\n",
               NUM_FREQS, "EXCLUDED (omega = pi*k/N) - matches scipy");
        callCount++;
    }

    return maxMag;
}

void ZPlaneFilter::dumpCoefficientsJSON(const char* filename, double morph, double q) const
{
    FILE* f = fopen(filename, "a");  // Append mode for multiple corners
    if (!f) return;

    // Determine corner name
    const char* cornerName = "unknown";
    if (std::abs(morph - 0.0) < 0.01 && std::abs(q - 0.0) < 0.01) cornerName = "M0_Q0";
    else if (std::abs(morph - 0.0) < 0.01 && std::abs(q - 1.0) < 0.01) cornerName = "M0_Q100";
    else if (std::abs(morph - 1.0) < 0.01 && std::abs(q - 0.0) < 0.01) cornerName = "M100_Q0";
    else if (std::abs(morph - 1.0) < 0.01 && std::abs(q - 1.0) < 0.01) cornerName = "M100_Q100";

    fprintf(f, "{\n");
    fprintf(f, "  \"corner\": \"%s\",\n", cornerName);
    fprintf(f, "  \"morph\": %.1f,\n", morph);
    fprintf(f, "  \"q\": %.1f,\n", q);
    fprintf(f, "  \"rawBoost\": %.9f,\n", currentBoost);  // This is the FINAL boost after normalization
    fprintf(f, "  \"stageCount\": 5,\n");
    fprintf(f, "  \"stages\": [\n");

    for (int i = 0; i < 5; i++) {
        fprintf(f, "    {\"b0\": %.9f, \"b1\": %.9f, \"b2\": %.9f, \"a0\": 1.0, \"a1\": %.9f, \"a2\": %.9f}%s\n",
                stages[i].b0, stages[i].b1, stages[i].b2,
                stages[i].a1, stages[i].a2,
                (i < 4) ? "," : "");
    }

    fprintf(f, "  ],\n");
    fprintf(f, "  \"processSampleEquation\": \"y = (b0*x + b1*x1 + b2*x2) - (a1*y1 + a2*y2)\"\n");
    fprintf(f, "},\n");

    fclose(f);
}
