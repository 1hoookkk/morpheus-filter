# Codebase Structure

**Analysis Date:** 2026-01-27

## Directory Layout

```
TRENCH/
├── Source/                    # Plugin source code
│   ├── DSP/                   # Digital signal processing
│   ├── GUI/                   # User interface components
│   ├── Data/                  # Static embedded data
│   ├── PluginProcessor.cpp    # Main audio processor
│   ├── PluginProcessor.h      # Processor header
│   ├── PluginEditor.cpp       # Plugin UI implementation
│   └── PluginEditor.h         # Editor header
├── tools/                     # Python analysis/capture tools
├── validation/                # Reference audio and test outputs
│   └── output/                # Generated test files
├── build/                     # CMake build output (generated)
├── .planning/                 # GSD planning documents
│   └── codebase/              # Architecture documentation
├── CMakeLists.txt             # Build configuration
├── CLAUDE.md                  # Project specification
└── *.json                     # Coefficient capture data
```

## Directory Purposes

**Source/:**
- Purpose: All C++ plugin source code
- Contains: Plugin entry points, processors, editors
- Key files: `PluginProcessor.cpp`, `PluginEditor.cpp`

**Source/DSP/:**
- Purpose: Digital signal processing components
- Contains: Cube loader, filter implementations
- Key files: `WavCubeLoader.h`, `WavCubeLoader.cpp`

**Source/GUI/:**
- Purpose: Custom UI components and styling
- Contains: LookAndFeel, sliders, knobs, displays
- Key files: `TrenchLookAndFeel.h`, `LCDDisplay.h`, `TrenchSlider.h`

**Source/Data/:**
- Purpose: Static embedded binary data
- Contains: Cube names, decoded WAV data, JSON libraries
- Key files: `CubeNames.h`, `wav_decoded.bin`, `morpheus_zplane_library.json`

**tools/:**
- Purpose: Python scripts for reverse engineering and validation
- Contains: Memory rippers, coefficient analyzers, audio validators
- Key files: `ripper.py`, `validate_audio.py`, `decode_cubes.py`

**validation/:**
- Purpose: Reference audio files and test outputs
- Contains: X3 reference recordings, generated test WAVs, analysis images
- Key files: `bypassed-pinknoise.wav`, `hedzmorph*.wav`

## Key File Locations

**Entry Points:**
- `Source/PluginProcessor.cpp`: Audio processing entry, `createPluginFilter()` factory
- `Source/PluginEditor.cpp`: UI entry, timer-based display updates

**Configuration:**
- `CMakeLists.txt`: JUCE plugin build configuration
- `CLAUDE.md`: Project specification and implementation notes

**Core Logic:**
- `Source/PluginProcessor.cpp`: Biquad cascade, coefficient interpolation (lines 347-634)
- `Source/DSP/WavCubeLoader.cpp`: ARMAdillo decoding, cube parsing (lines 9-42)

**Testing:**
- `validation/`: Reference WAV files for A/B comparison
- `tools/validate_audio.py`: FFT comparison against X3 reference

**Binary Data:**
- `Source/Data/wav_decoded.bin`: Pre-decoded E-mu cube data (96,500 bytes)
- `Source/Data/morpheus_zplane_library.json`: JSON cube library (~1.4MB)

## Naming Conventions

**Files:**
- `PascalCase.cpp/.h`: C++ source files
- `snake_case.py`: Python tools
- `lowercase-dashes.wav`: Audio files

**Classes:**
- `TrenchAudioProcessor`: Main processor class
- `TrenchAudioProcessorEditor`: Editor class
- `TrenchLookAndFeel`: Custom styling
- `WavCubeLoader`: Cube data loader

**Parameters:**
- Lowercase: `morph`, `q`, `drive`, `mix`, `output`, `bypass`

**Constants:**
- `SCREAMING_SNAKE`: `NUM_STAGES`, `CONTROL_RATE`, `EXPECTED_CUBES`

## Where to Add New Code

**New DSP Feature:**
- Primary code: `Source/DSP/`
- Header: Create `Source/DSP/NewFeature.h`
- Implementation: Create `Source/DSP/NewFeature.cpp`
- Include in: `Source/PluginProcessor.h`
- Add to CMakeLists.txt `target_sources()`

**New GUI Component:**
- Primary code: `Source/GUI/`
- Header-only OK for simple components
- Follow `TrenchSlider.h` pattern (Component with embedded Slider)
- Include in: `Source/PluginEditor.h`

**New Parameter:**
1. Add to `createParameterLayout()` in `PluginProcessor.cpp` (lines 31-64)
2. Add `std::atomic<float>*` member in `PluginProcessor.h`
3. Initialize pointer in constructor
4. Add UI control in `PluginEditor.cpp`
5. Add attachment in editor constructor

**New Preset Data:**
- Polar format: Add to `initializePresets()` in `PluginProcessor.cpp` (lines 86-201)
- JSON format: Add to `Source/Data/` and update CMakeLists.txt binary data

**New Python Tool:**
- Location: `tools/`
- Pattern: `tool_name.py` with argparse CLI
- Output to: `validation/` for test artifacts

## Special Directories

**build/:**
- Purpose: CMake build output, JUCE fetched source
- Generated: Yes (by CMake)
- Committed: No (in .gitignore)

**build/_deps/juce-src/:**
- Purpose: JUCE framework source (FetchContent)
- Generated: Yes (by CMake FetchContent)
- Committed: No

**validation/output/:**
- Purpose: Test-generated files
- Generated: Yes (by validation scripts)
- Committed: Partial (results files)

**Source/Data/:**
- Purpose: Embedded binary resources
- Generated: No (committed data)
- Committed: Yes
- Note: `wav_decoded.bin` is 96KB pre-decoded cube data

## Build Artifacts

**VST3 Plugin:**
- Location: `build/TRENCH_artefacts/Release/VST3/TRENCH.vst3/`
- Auto-copied to system VST3 folder (COPY_PLUGIN_AFTER_BUILD)

**Standalone:**
- Location: `build/TRENCH_artefacts/Release/Standalone/`

---

*Structure analysis: 2026-01-27*
