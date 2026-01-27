# Technology Stack

**Analysis Date:** 2026-01-27

## Languages

**Primary:**
- C++17 - Plugin DSP engine, JUCE framework code (`Source/`)
- Python 3.10+ - Reverse engineering tools, validation scripts (`tools/`)

**Secondary:**
- Lua - Cheat Engine memory capture scripts (`tools/ce_full_capture.lua`)
- CMake - Build configuration (`CMakeLists.txt`)

## Runtime

**Environment:**
- Windows 10/11 (primary development target)
- VST3/AU host applications (DAWs)

**Package Manager:**
- CMake FetchContent - C++ dependencies (JUCE)
- pip - Python dependencies (no requirements.txt, install manually)

**Lockfile:** Not present - dependencies fetched at build time

## Frameworks

**Core:**
- JUCE 8.0.1 - Audio plugin framework (fetched via CMake)
  - `juce::juce_audio_utils` - Audio utilities
  - `juce::juce_audio_processors` - Plugin architecture
  - `juce::juce_dsp` - DSP primitives
  - `juce::juce_gui_basics` - GUI components

**Testing:**
- Manual validation via Python scripts (`tools/validate_audio.py`)
- No C++ unit test framework currently

**Build/Dev:**
- CMake 4.0+ - Build system
- Visual Studio 2022 - Windows compiler/IDE
- MSVC toolchain - C++ compilation

## Key Dependencies

**C++ (JUCE modules):**
- `juce_audio_processors` - Plugin host interface (VST3, AU, Standalone)
- `juce_dsp` - DSP math and filtering primitives
- `juce_gui_basics` - UI rendering and components
- `juce_audio_utils` - Audio file handling

**Python (analysis tools):**
- `numpy` - Numerical computing, array ops
- `scipy` - Signal processing (`scipy.signal`, `scipy.io.wavfile`, `scipy.fft`)
- `matplotlib` - Visualization and plotting
- `soundfile` - WAV file I/O (alternative to scipy.io.wavfile)
- `pymem` - Windows process memory reading (for EmulatorX capture)

## Configuration

**Environment:**
- No `.env` files - configuration via code constants
- Memory addresses hardcoded in capture scripts (change per session)

**Build:**
- `CMakeLists.txt` - Main build configuration
- `build.bat` - Windows quick build script
- CMake generator: Visual Studio 17 2022

**Plugin Configuration:**
```cmake
FORMATS VST3 AU Standalone
COMPANY_NAME "Trench Audio"
BUNDLE_ID "com.trenchaudio.trench"
```

## Platform Requirements

**Development:**
- Windows 10/11 with Visual Studio 2022
- CMake 3.22+ (using 4.0)
- Python 3.10+ for tooling
- Emulator X3 (optional, for coefficient capture)
- Cheat Engine (optional, for memory analysis)

**Production:**
- VST3 host (any Windows DAW)
- AU host (macOS, untested)
- Standalone mode available

## Build Commands

```bash
# Configure and build (first time)
mkdir build && cd build
cmake .. -G "Visual Studio 17 2022"
cmake --build . --config Release

# Quick build (subsequent)
build.bat release

# Run standalone
build.bat release run
```

## Output Artifacts

- `build/TRENCH_artefacts/Release/VST3/TRENCH.vst3` - VST3 plugin
- `build/TRENCH_artefacts/Release/Standalone/TRENCH.exe` - Standalone app
- `build/TRENCH_artefacts/Release/TRENCH_SharedCode.lib` - Static library

## Binary Data

Embedded via `juce_add_binary_data`:
- `Source/Data/wav_decoded.bin` - Pre-decoded filter coefficient ROM
- `Source/Data/morpheus_zplane_library.json` - Filter library metadata

---

*Stack analysis: 2026-01-27*
