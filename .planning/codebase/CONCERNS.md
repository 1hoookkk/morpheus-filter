# Codebase Concerns

**Analysis Date:** 2026-01-27

## Tech Debt

**TrenchFilter Disabled:**
- Issue: The `TrenchFilter` class is commented out/disabled throughout the codebase "for debugging"
- Files: `Source/PluginProcessor.h` (lines 4, 67-69, 93-94), `Source/PluginProcessor.cpp` (lines 210-212)
- Impact: The clean, dedicated filter implementation is bypassed in favor of inline biquad processing
- Fix approach: Re-enable TrenchFilter once coefficient validation is complete; remove dead code paths

**Multiple Coefficient Systems (Code Complexity):**
- Issue: Three parallel coefficient update paths create branching complexity
- Files: `Source/PluginProcessor.cpp` (lines 347-363, 369-382, 504-518, 524-552)
- Impact: Difficult to maintain; easy to introduce bugs when changing one path
- Fix approach: Consolidate to single polar/v-space system once validated; deprecate legacy presets entirely

**Biquad Topology Contradiction:**
- Issue: CLAUDE.md specifies Direct Form I for stable morphing, but actual implementation uses DF-II Transposed
- Files: `CLAUDE.md` (lines 38-45), `Source/DSP/Biquad.h` (lines 217-226), `Source/PluginProcessor.cpp` (lines 695-699)
- Impact: May cause instability during rapid coefficient morphing; contradicts documented architecture
- Fix approach: Decide on canonical topology; update either spec or code to match

**Hardcoded File Path:**
- Issue: File chooser has hardcoded user-specific path
- Files: `Source/PluginEditor.cpp` (line 142): `juce::File("C:\\Users\\hooki\\do-it")`
- Impact: Will fail or behave unexpectedly for other users
- Fix approach: Use `juce::File::getSpecialLocation()` for user documents or last-used path

**Magic Numbers Scattered:**
- Issue: Undocumented constants throughout DSP code
- Files:
  - `Source/PluginProcessor.cpp`: `0.446` (line 274), `CONTROL_RATE = 128` (line 84)
  - `Source/DSP/TrenchFilter.h`: `0.8f`, `0.2f` (line 107)
  - `Source/DSP/WavCubeLoader.cpp`: `86.4` (line 25), `32.0` (line 17)
- Impact: Hard to understand purpose; easy to misconfigure
- Fix approach: Replace with named constexpr values with documentation

## Known Bugs

**Missing M0_Q0 Keyframe:**
- Symptoms: Interpolation at low morph + low Q positions falls back to scaling M0_Q100 radius
- Files: `Source/DSP/TrenchFilter.h` (lines 172-179)
- Trigger: Set Morph near 0% and Q near 0%
- Workaround: Current code scales radius down by 50%, but this is not validated against X3

**Sample Rate Hardcoded:**
- Symptoms: Filter frequencies will be wrong at sample rates other than 44100 Hz
- Files: `Source/DSP/WavCubeLoader.cpp` (lines 443, 472, 475): hardcoded `44100.0`
- Trigger: Running plugin at 48kHz or 96kHz
- Workaround: None - coefficients will be calculated incorrectly

## Security Considerations

**Memory Reading Tool:**
- Risk: `tools/ripper.py` uses `pymem` to read EmulatorX.exe process memory
- Files: `tools/ripper.py` (lines 57-72)
- Current mitigation: Tool is development-only, not shipped with plugin
- Recommendations: Document legal considerations; ensure tool never ships in release builds

**No Path Validation on File Loading:**
- Risk: File loader accepts any path without sanitization
- Files: `Source/DSP/WavCubeLoader.cpp` (lines 110-120, 179-199)
- Current mitigation: JUCE's file handling provides some protection
- Recommendations: Add explicit path validation; reject paths outside expected directories

## Performance Bottlenecks

**Control Rate Inside Sample Loop:**
- Problem: `updateCoefficients()` called conditionally inside per-sample loop
- Files: `Source/PluginProcessor.cpp` (lines 666-669)
- Cause: Counter checked every sample; coefficient update every 128 samples
- Improvement path: Move coefficient update to block-level processing; use parameter smoothing instead

**Expensive Frequency Response Calculation:**
- Problem: 256 frequency points with full trig calculations at 30 fps
- Files: `Source/PluginProcessor.cpp` (lines 716-802)
- Cause: Complex numbers computed per-point, per-stage (256 x 7 = 1792 calculations)
- Improvement path: Cache coefficients; only recalculate on parameter change; use lookup tables for trig

**No SIMD Optimization:**
- Problem: 7-stage biquad cascade processes samples serially
- Files: `Source/PluginProcessor.cpp` (lines 689-700)
- Cause: Single-sample DF-II Transposed implementation
- Improvement path: Use JUCE's `dsp::IIR::Filter` with SIMD or process in blocks per stage

## Fragile Areas

**Cube Decode Format Ambiguity:**
- Files: `Source/DSP/WavCubeLoader.h` (lines 25-28), `Source/DSP/WavCubeLoader.cpp` (lines 24-26)
- Why fragile: Comments acknowledge confusion about frequency scaling (86.4 vs 43.2)
- Safe modification: Always validate against known reference frequencies (TalkingHedz: 994, 1690, 2485 Hz)
- Test coverage: Manual Python scripts only; no automated regression tests

**Memory Address Volatility:**
- Files: `CLAUDE.md` (line 150), `tools/ripper.py` (line 33)
- Why fragile: E-mu X3 coefficient base address shifts on every restart
- Safe modification: Always verify address via Cheat Engine before capture session
- Test coverage: Manual verification only

**WAV Frame Decoding:**
- Files: `Source/DSP/WavCubeLoader.cpp` (lines 49-99)
- Why fragile: Hardcoded frame patterns; any change in source file format will silently fail
- Safe modification: Prefer binary or JSON loading over WAV parsing
- Test coverage: None - relies on matching exact byte patterns

## Scaling Limits

**Preset Storage:**
- Current capacity: 3 presets hardcoded (TalkingHedz, MeatyGizmo, RadioCraze)
- Limit: Memory scales linearly with presets; 289 cubes would require significant RAM for full library
- Scaling path: Load cubes on-demand from embedded binary; unload unused cubes

**Morph Keyframes:**
- Current capacity: 5 keyframes per preset (0%, 25%, 50%, 75%, 100%)
- Limit: Linear interpolation adequate for formant filters; may need more for complex filters
- Scaling path: Support variable keyframe counts per preset

## Dependencies at Risk

**JUCE Version:**
- Risk: Pinned to JUCE 8.0.1; newer versions may break API
- Files: `CMakeLists.txt` (line 9)
- Impact: Cannot take advantage of future JUCE improvements without testing
- Migration plan: Bump version quarterly; test build before committing

**pymem (Development Tool):**
- Risk: Windows-only Python library for memory reading; no macOS/Linux equivalent
- Files: `tools/ripper.py` (lines 22-27)
- Impact: Coefficient capture only works on Windows
- Migration plan: Pre-capture all needed presets; ship as embedded data

## Missing Critical Features

**v-space Interpolation Not Implemented:**
- Problem: CLAUDE.md documents ARMAdillo v-space as "the magic" but code interpolates raw a1/radius
- Files: `CLAUDE.md` (lines 47-91), `Source/PluginProcessor.cpp` (lines 428-433)
- Blocks: Musical morphing quality; coefficients may pitch-wobble without v-space

**Only TalkingHedz Captured:**
- Problem: Only one preset has validated X3 coefficient captures
- Files: `TalkingHedz.json`, polar presets in `Source/PluginProcessor.cpp`
- Blocks: Product cannot ship with single preset; need 10-15 essential filters

**No 2D Morph Support:**
- Problem: TalkingHedz is documented as 2D (Morph + Q axes) but Q axis interpolation is incomplete
- Files: `Source/DSP/TrenchFilter.h` (lines 163-186)
- Blocks: Full range of filter expressiveness

## Test Coverage Gaps

**No C++ Unit Tests:**
- What's not tested: Biquad coefficient calculation, interpolation logic, file loading
- Files: All `Source/DSP/*.h`, `Source/DSP/*.cpp`
- Risk: Regression bugs during refactoring will go unnoticed
- Priority: High - DSP correctness is critical

**Python Scripts Are Validation, Not Tests:**
- What's not tested: Automated pass/fail; CI integration
- Files: `tools/test_*.py` (20+ files)
- Risk: Scripts require manual interpretation; easy to miss regressions
- Priority: Medium - convert to pytest with assertions

**No Audio Output Regression Tests:**
- What's not tested: Processed audio matches reference within tolerance
- Files: `validation/*.wav` (reference files exist but no automation)
- Risk: Filter character could drift without detection
- Priority: High - core product quality

**GUI Not Tested:**
- What's not tested: Component layout, parameter response, state persistence
- Files: `Source/PluginEditor.cpp`, `Source/GUI/*.h`
- Risk: UI bugs in different hosts/platforms
- Priority: Low - manual testing adequate for MVP

---

*Concerns audit: 2026-01-27*
