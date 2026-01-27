# Coding Conventions

**Analysis Date:** 2026-01-27

## Naming Patterns

**Files:**
- C++ source: `PascalCase.cpp` - e.g., `PluginProcessor.cpp`, `WavCubeLoader.cpp`
- C++ headers: `PascalCase.h` - e.g., `PluginProcessor.h`, `TrenchLookAndFeel.h`
- Python scripts: `snake_case.py` - e.g., `validate_audio.py`, `test_dsp.py`
- Data files: `snake_case.json` or `snake_case.bin`

**C++ Classes:**
- PascalCase: `TrenchAudioProcessor`, `WavCubeLoader`, `BiquadState`
- GUI components: `TrenchSlider`, `TrenchKnob`, `LCDDisplay`, `PresetSelector`
- JUCE convention: Processor class named `{Plugin}AudioProcessor`, Editor named `{Plugin}AudioProcessorEditor`

**C++ Functions:**
- camelCase for member functions: `prepareToPlay()`, `processBlock()`, `updateCoefficients()`
- Static functions: camelCase - `hzToSemi()`, `semiToHz()`
- Getters: `get*()` pattern - `getAPVTS()`, `getFrequencyResponse()`, `getValue()`
- Setters: `set*()` pattern - `setPresetIndex()`, `setMorph()`, `setValue()`
- Boolean getters: `is*()` or `are*()` - `areCubesLoaded()`, `isValid()`

**C++ Variables:**
- Member variables: camelCase without prefix - `currentSampleRate`, `morphParam`, `cubesLoaded`
- Private members: no underscore prefix (JUCE style)
- Constants: `UPPER_SNAKE_CASE` - `CONTROL_RATE`, `NUM_STAGES`, `EXPECTED_CUBES`
- Template parameters: single uppercase letter or PascalCase

**Python Functions:**
- snake_case: `load_wav()`, `compute_spectrum()`, `process_biquad()`
- Test functions: `main()` entry point pattern

**Python Variables:**
- snake_case: `sample_rate`, `morph_param`, `output_samples`
- Constants: `UPPER_SNAKE_CASE` - `M0_Q100_STAGES`, `ZERO_MODE`

## Code Style

**Formatting:**
- No explicit formatter configured (manual formatting)
- 4-space indentation for C++
- 4-space indentation for Python
- Opening braces on same line for C++ (`void foo() {`)
- Max ~100 character line width

**Linting:**
- No explicit linter configured
- JUCE recommended warning flags enabled via CMake:
  ```cmake
  juce::juce_recommended_warning_flags
  ```

**C++ Patterns:**
- Use `constexpr` for compile-time constants
- Use `static constexpr` for class constants:
  ```cpp
  static constexpr int NUM_STAGES = 7;
  static constexpr int CONTROL_RATE = 128;
  ```
- Prefer `std::array` over C-style arrays
- Use `std::vector` for dynamic collections
- Use `std::unique_ptr` for owned pointers

## Import Organization

**C++ Headers:**
1. Own header first (for .cpp files): `#include "PluginProcessor.h"`
2. Project headers: `#include "DSP/WavCubeLoader.h"`
3. JUCE headers: `#include <JuceHeader.h>`
4. Standard library: `#include <cmath>`, `#include <vector>`

**Python Imports:**
1. Standard library: `import os`, `import sys`, `import json`, `import time`
2. Third-party: `import numpy as np`, `from scipy.io import wavfile`
3. Local modules (rare)

**Path Aliases (CMake):**
```cmake
target_include_directories(TRENCH PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/Source)
```
Use `"DSP/WavCubeLoader.h"` not `"../../DSP/WavCubeLoader.h"`

## Error Handling

**C++ Patterns:**
- Return `bool` for success/failure: `loadFromWav()` returns `true`/`false`
- Store error message in member: `lastError` string, accessed via `getLastError()`
- Use `DBG()` macro for debug output (JUCE pattern)
- Check validity before use: `if (cube == nullptr)` guards
- Clamp values to valid ranges: `juce::jlimit()`, `std::min()`, `std::max()`

```cpp
bool WavCubeLoader::loadFromWav(const juce::File& wavFile)
{
    cubes.clear();
    lastError.clear();

    if (!wavFile.existsAsFile())
    {
        lastError = "File not found: " + wavFile.getFullPathName();
        return false;
    }
    // ...
}
```

**Python Patterns:**
- Return value indicates success: `return 0` for success, `return 1` for failure
- Use `try/except` for external operations (file I/O, memory access)
- Print error messages to stdout with `[ERROR]` prefix
- Check for NaN/Inf in DSP output:
  ```python
  if np.any(np.isnan(output)) or np.any(np.isinf(output)):
      print("ERROR: Output contains NaN/Inf!")
  ```

## Logging

**Framework:** JUCE `DBG()` macro for C++, `print()` for Python

**C++ Patterns:**
- Use `DBG()` for debug output (stripped in release builds):
  ```cpp
  DBG("TRENCH: Loaded " << cubeLoader.getNumCubes() << " cubes from " << binFile.getFileName());
  ```

**Python Patterns:**
- Print progress with `=` separators and section headers:
  ```python
  print("=" * 70)
  print("TRENCH DSP Test")
  print("=" * 70)
  ```
- Use `f-strings` for formatted output
- Prefix status messages: `[TRENCH]`, `[ERROR]`, `[ACTION]`, `[GO!]`

## Comments

**When to Comment:**
- Section headers with `//===...===` dividers (JUCE style)
- Complex DSP formulas with formula explanation
- Validation sources: "Validated against X3", "From CLAUDE.md"
- Capture date and source for magic numbers

**Section Headers:**
```cpp
//==============================================================================
// COEFFICIENT CALCULATION - Verified formulas from Audio EQ Cookbook
//==============================================================================
```

**Formula Documentation:**
```cpp
// a1 = -2 * r * cos(theta)
// This is the direct biquad coefficient for pole placement
double theta = decodeTheta(freqByte, sampleRate);
return -2.0 * radius * std::cos(theta);
```

**JSDoc/TSDoc:** Not used (C++/Python codebase)

**Python Docstrings:**
- Triple-quoted docstrings at module and function level
- Include Usage section for command-line scripts
- Document parameters inline:
  ```python
  def compute_spectrum(data, sample_rate, nfft=8192):
      """Compute magnitude spectrum in dB"""
  ```

## Function Design

**Size:**
- Keep functions focused on single responsibility
- DSP functions: typically 10-50 lines
- Processing functions: may be longer with clear section comments

**Parameters:**
- Use default parameters for optional values: `nfft=8192`
- Pass large objects by const reference in C++: `const juce::File&`
- Avoid more than 5-6 parameters

**Return Values:**
- Single return type preferred
- Use structs for multiple return values in C++:
  ```cpp
  struct BiquadCoeffs {
      double b0, b1, b2, a1, a2;
  };
  ```
- Use tuples in Python: `return freqs, magnitude_db`

## Module Design

**Exports:**
- One class per header file (JUCE convention)
- Header guards: `#pragma once`

**Barrel Files:** Not used (explicit includes)

**Directory Structure:**
- `Source/` - Main plugin code
- `Source/DSP/` - Digital signal processing components
- `Source/GUI/` - UI components
- `Source/Data/` - Static data (cube names, embedded resources)
- `tools/` - Python validation and analysis scripts

## Struct/Class Patterns

**Nested Types:**
- Use nested structs for closely related data:
  ```cpp
  class WavCubeLoader {
  public:
      struct PoleStage { ... };
      struct MorphPoint { ... };
      struct Cube { ... };
  };
  ```

**JUCE Macros:**
- End all Component classes with:
  ```cpp
  JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(ClassName)
  ```

**Initialization:**
- Use in-class member initialization:
  ```cpp
  double currentSampleRate = 48000.0;
  int currentPresetIndex = 0;
  bool cubesLoaded = false;
  ```

## DSP-Specific Conventions

**Sample Processing:**
- Use `double` for coefficients and state
- Use `float` for audio buffers (JUCE convention)
- Process sample-by-sample with clear loop:
  ```cpp
  for (int s = 0; s < numSamples; ++s) {
      // process
  }
  ```

**Coefficient Names:**
- Standard biquad: `b0, b1, b2, a1, a2` (normalized, a0=1)
- Pole representation: `a1` (frequency), `r` (radius), `flag` (type)
- State variables: `z1, z2` (Direct Form II delays)

**Magic Numbers:**
- Document source and validation:
  ```cpp
  // Validated against VowelSpace formants (F1=778Hz, F2=2074Hz)
  return static_cast<double>(byte) * 86.4;
  ```

---

*Convention analysis: 2026-01-27*
