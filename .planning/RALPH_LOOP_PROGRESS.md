# TRENCH Ralph Loop Progress

## Iteration 1 Summary

### Parallel Audit Findings

1. **DSP Implementation vs Spec**
   - Biquad uses DF-II Transposed (spec says DF-I) - acceptable tradeoff
   - Was using RBJ peaking EQ, but CLAUDE.md says "DO NOT use RBJ cookbook"
   - Missing Phantom stage and gain staging

2. **Python Spectral Test Results**
   - v1_bandpass / v4_constpeak: **14.84 dB** RMS error (BEST)
   - v2_peaking (RBJ): 17-19 dB error (WORSE)
   - This proved the peaking EQ "fix" was actually making things worse!

3. **Parameter Flow** - Verified working correctly
   - morphParam and qParam ARE being read
   - updateCoefficientsFromPolar() IS being called
   - Coefficients ARE being applied
   - No bugs in the control flow

4. **178 Hz Mystery**
   - M0_Q100 has NO resonator near 178 Hz (lowest is 994 Hz)
   - The 178 Hz peak likely comes from cascade interaction or lowpass body
   - M100_Q100 Stage 0 at 156 Hz DOES explain its low peak

### Changes Made

1. **Reverted flag=1 to constant peak gain bandpass** (PluginProcessor.cpp:492-518)
   ```cpp
   double a1_final = a1_polar * radius;
   double scale = 1.0 - radius;
   c.b0 = scale; c.b1 = 0.0; c.b2 = -scale;
   ```

2. **Added gain staging** (PluginProcessor.cpp:737-766)
   - -7dB input attenuation (0.446)
   - Post-filter soft saturation
   - +7dB makeup gain

3. **Fixed lowpass formula** - Now multiplies a1 by radius for consistency

4. **Updated Biquad.h** - setZPlaneResonator uses constant peak gain formula

### Build Status
- VST3: SUCCESS (installed to Program Files)
- Standalone: LOCKED (process running)

### Validation Results
| Configuration | RMS Error |
|---------------|-----------|
| M100_Q100 + v4_constpeak | 14.84 dB |
| M0_Q100 + v4_constpeak | 15.47 dB |
| M100_Q100 + v2_peaking | 17.06 dB |

### Next Steps (Iteration 2)
1. Test the built VST3 in a DAW to hear the difference
2. Consider per-sample coefficient smoothing to reduce zipper noise
3. Investigate whether a low-frequency "body" stage is needed for M0_Q100
4. Compare FFT output of C++ plugin vs Python test vs X3 reference

### Key Insight
**The E-mu Z-Plane uses constant peak gain bandpass resonators, NOT parametric/peaking EQ.** This is the "E-mu character" - tight formant peaks with zeros at DC and Nyquist.
