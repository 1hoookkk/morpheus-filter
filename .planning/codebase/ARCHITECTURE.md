# Architecture

**Analysis Date:** 2026-01-27

## Pattern Overview

**Overall:** JUCE Audio Plugin (Processor-Editor MVC)

**Key Characteristics:**
- Standard JUCE plugin pattern with `AudioProcessor` (model/controller) and `AudioProcessorEditor` (view)
- DSP processing embedded in processor with control-rate coefficient updates
- Parameter state management via `AudioProcessorValueTreeState` (APVTS)
- 7-stage cascaded biquad filter architecture (14 poles) for Z-Plane emulation
- Multiple coefficient data sources (polar presets, WAV cubes, legacy presets)

## Layers

**Plugin Core (Entry Points):**
- Purpose: JUCE plugin lifecycle, DAW integration
- Location: `Source/PluginProcessor.cpp`, `Source/PluginProcessor.h`
- Contains: Audio processing, parameter management, state persistence
- Depends on: DSP layer, JUCE framework
- Used by: DAW host

**DSP Layer:**
- Purpose: Filter coefficient loading and decoding
- Location: `Source/DSP/`
- Contains: `WavCubeLoader` (cube data parsing), biquad coefficient calculation
- Depends on: Data layer (embedded binaries)
- Used by: Plugin Core

**GUI Layer:**
- Purpose: User interface rendering and interaction
- Location: `Source/GUI/`
- Contains: Custom LookAndFeel, slider/knob components, LCD display
- Depends on: Plugin Core (via APVTS attachments)
- Used by: Plugin Editor

**Data Layer:**
- Purpose: Static embedded data for filter presets
- Location: `Source/Data/`
- Contains: Cube names, pre-decoded binary data, JSON libraries
- Depends on: Nothing (static)
- Used by: DSP layer

## Data Flow

**Audio Processing Chain:**

1. DAW calls `processBlock()` with audio buffer
2. Control-rate update (every 128 samples): recalculate biquad coefficients
3. Per-sample: apply drive saturation (optional)
4. Per-sample: cascade through 7 biquad stages (Direct Form II Transposed)
5. Apply wet/dry mix and output gain
6. Return processed buffer to DAW

**Coefficient Update Flow:**

1. Read morph/Q parameters from APVTS
2. Route to appropriate source:
   - Cubes loaded? -> `updateCoefficientsFromCube()`
   - Polar presets? -> `updateCoefficientsFromPolar()`
   - Legacy? -> `updateCoefficientsFromLegacy()`
3. Interpolate between keyframes based on morph value
4. Apply Q scaling to pole radius
5. Calculate biquad coefficients (b0, b1, b2, a1, a2)
6. Store in `currentCoeffs[]` array for audio processing

**State Management:**
- Parameters: morph, q, drive, mix, output, bypass
- State persistence: XML serialization via `getStateInformation()`/`setStateInformation()`
- Preset/cube selection stored in state tree

## Key Abstractions

**BiquadCoeffs:**
- Purpose: Single biquad stage coefficient set
- Examples: `Source/PluginProcessor.h` (lines 108-112)
- Pattern: POD struct with b0, b1, b2, a1, a2

**PolarStageParams:**
- Purpose: E-mu-style polar representation (a1, radius, flag)
- Examples: `Source/PluginProcessor.h` (lines 126-131)
- Pattern: Pre-validated X3 capture data format

**WavCubeLoader::Cube:**
- Purpose: Complete filter preset with morph interpolation points
- Examples: `Source/DSP/WavCubeLoader.h` (lines 62-74)
- Pattern: Container with name, index, and vector of MorphPoints

**MorphPoint:**
- Purpose: Snapshot of all 7 stages at a particular morph position
- Examples: `Source/DSP/WavCubeLoader.h` (lines 55-59)
- Pattern: Array of PoleStage structs with morph position

## Entry Points

**Plugin Instantiation:**
- Location: `Source/PluginProcessor.cpp` (line 952-955)
- Triggers: DAW loads plugin
- Responsibilities: Creates `TrenchAudioProcessor` instance

**Audio Processing:**
- Location: `Source/PluginProcessor.cpp::processBlock()` (lines 640-710)
- Triggers: DAW audio callback
- Responsibilities: Process audio through 7-stage biquad cascade

**Editor Creation:**
- Location: `Source/PluginProcessor.cpp::createEditor()` (lines 947-950)
- Triggers: DAW opens plugin UI
- Responsibilities: Creates `TrenchAudioProcessorEditor` instance

**Cube Loading:**
- Location: `Source/PluginProcessor.cpp::loadCubesFromWav()` (lines 874-896)
- Triggers: User selects cube file
- Responsibilities: Parse WAV/binary data into cube structures

## Error Handling

**Strategy:** Defensive defaults with DBG logging

**Patterns:**
- Invalid cube index: Return bypass defaults (a1=-2, r=0.5)
- File load failure: Return false, set `lastError` string
- Coefficient bounds: Clamp radius to 0.9999 for stability
- Denormal protection: Zero samples below 1e-20 threshold

## Cross-Cutting Concerns

**Logging:** JUCE `DBG()` macro for debug builds only

**Validation:**
- Coefficient clamping for filter stability
- Sample rate stored in processor for coefficient calculation
- Bounds checking on array indices

**Threading:**
- Audio thread: `processBlock()` - no allocations, no locks
- Message thread: UI updates, file loading
- Control rate: Coefficient updates every 128 samples to reduce CPU

---

*Architecture analysis: 2026-01-27*
