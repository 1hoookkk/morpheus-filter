# Technology Stack

**Analysis Date:** 2026-01-20

## Languages

**Primary:**
- C++17 - DSP engine implementation (`Source/dsp/ZPlaneFilter.h`)

**Secondary:**
- Python 3.10 - Analysis, validation, data regeneration scripts
- Lua - Cheat Engine coefficient extraction scripts

## Runtime

**Environment:**
- Windows (development platform)
- Python 3.10.11 for validation/analysis scripts

**Package Manager:**
- No C++ package manager (header-only dependencies)
- Python: pip (packages installed globally/per-project)

**Lockfile:**
- None detected

## Frameworks

**Core (Phase 1 - Current):**
- Header-only C++ DSP implementation
- No framework dependencies

**Core (Phase 2 - Planned):**
- JUCE 8.0.10 - Audio plugin framework for VST3 wrapper
- CMake - Build system

**Testing:**
- Python validation scripts (no formal test framework)
- Manual reference file comparison

**Build/Dev:**
- g++/MSVC for C++ compilation
- Python interpreter for scripts

## Key Dependencies

**C++ Critical:**
- `nlohmann/json` 3.11.3 - JSON cartridge parsing
  - Location: `Source/external/json.hpp`
  - Single-header library, vendored

**C++ Standard Library Only:**
- `<cmath>` - Mathematical functions (cos, sin, log, exp, pow)
- `<array>` - Fixed-size arrays for coefficient storage
- `<algorithm>` - clamp, min, max

**Python Critical:**
- `numpy` - Numerical arrays, FFT, signal processing
- `scipy` - WAV I/O (`scipy.io.wavfile`), interpolation (`scipy.interpolate`), signal processing (`scipy.signal`)
- `matplotlib` - Frequency response plots, validation visualization

**Python Optional:**
- `soundfile` - Alternative WAV loading (fallback to scipy)

## Configuration

**Environment:**
- No environment variables required
- All paths relative to project root

**Build (Phase 2 - Planned):**
- `CMakeLists.txt` - JUCE CMake configuration
- Platform: VST3 primary, AU secondary

**Sample Rate:**
- Default: 44100 Hz (capture reference rate)
- Supported: 44.1kHz, 48kHz, 96kHz with bilinear transform warping

## Data Files

**Primary Data Source:**
- `talking_hedz_extracted.json` (374KB) - Complete 17x17x3 grid cartridge
  - 3 Q variants x 7 stages x 289 grid cells
  - Frequencies stored in Hz (converted to semitones on load)

**Raw Captures:**
- `talking_hedz_complete.json` - Raw Cheat Engine a1/radius coefficients
- `talking_hedz_cartridge.json` - Intermediate format

**Reference Audio:**
- `hedz - m100q0.wav` - Reference impulse response (Morph=100%, Q=0%)
- `hedz - 5050.wav` - Reference impulse response (Morph=50%, Q=50%)
- `impulse.wav` - Source impulse for filter testing

## Platform Requirements

**Development:**
- Windows 10/11 (current development platform)
- Python 3.10+
- C++17 compatible compiler (MSVC, g++, clang)

**Production (Phase 2):**
- VST3 host (Ableton Live, Reaper, FL Studio)
- Windows/macOS (via JUCE cross-compilation)

## DSP Implementation Details

**Architecture:**
- Header-only implementation for easy integration
- Namespace: `Trench`
- Main class: `ZPlaneFilter`

**Key Constants:**
```cpp
constexpr int MAX_STAGES = 6;           // H-Chip maximum
constexpr int HEDZ_STAGES = 5;          // Talking Hedz uses 5
constexpr int NUM_MORPH_KEYS = 5;       // Keyframe positions
constexpr float Q_REF = 100.0f;         // Reference Q level
constexpr int DEFAULT_CTRL_INTERVAL = 64; // Control rate
```

**Filter Topology:**
- 7-stage biquad cascade (5 active for Talking Hedz)
- Direct Form II Transposed implementation
- Delta-add coefficient ramping (H-Chip style)

**Critical Formulas:**
```cpp
// Coefficient computation
a1_actual = a1_captured * radius;
a2 = radius^2;

// Q scaling
r = r_ref^(Q_ref/Q_new);

// Numerators
// EQ/BP: scale = (1-a2)/2, [b0,b1,b2] = [scale, 0, -scale]
// LP:    norm = (1+a1+a2)/4, [b0,b1,b2] = [norm, 2*norm, norm]
```

---

*Stack analysis: 2026-01-20*
