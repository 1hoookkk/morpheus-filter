# Coding Conventions

**Analysis Date:** 2026-01-20

## Naming Patterns

**Files:**
- C++ headers: PascalCase with `.h` extension (`ZPlaneFilter.h`, `ZPlaneData.h`, `CartridgeLoader.h`)
- Python scripts: snake_case with `.py` extension (`validate_trench.py`, `regenerate_cartridge.py`)
- Lua scripts: snake_case with `.lua` extension (`ce_capture_grid.lua`)
- Test files: `test_` prefix for C++ (`test_cartridge_load.cpp`), `validate_` prefix for Python validators

**Functions/Methods:**
- C++: camelCase (`processBlock`, `setMorph`, `applyQToRadius`, `computeCoeffs`)
- Python: snake_case (`process_sample`, `set_parameters`, `apply_q_to_radius`, `load_cartridge`)

**Variables:**
- C++: camelCase for locals (`sampleCounter`, `ctrlInterval`, `rampLength`)
- C++: single letters acceptable for short-lived math variables (`x`, `y`, `r`, `s`, `tx`)
- Python: snake_case (`sample_rate`, `morph_idx`, `ref_peaks`)

**Constants:**
- C++: SCREAMING_SNAKE_CASE (`MAX_STAGES`, `Q_REF`, `DEFAULT_CTRL_INTERVAL`)
- Python: SCREAMING_SNAKE_CASE (`SAMPLE_RATE`, `NUM_STAGES`, `GRID_SIZE`, `TUNING_FACTOR`)

**Types/Classes/Structs:**
- C++: PascalCase (`ZPlaneFilter`, `HChipStage`, `BiquadCoeffs`, `StageRaw`, `Ramp`)
- Python: PascalCase (`ZPlaneEngine`, `GridInterpolator`, `GridStageData`, `ZPlaneCartridge`)

**Namespaces:**
- C++: PascalCase (`namespace Trench`, `namespace ZPlane`)

## Code Style

**Formatting:**
- No explicit formatter config detected
- Indentation: 4 spaces (observed in both C++ and Python)
- Opening braces: same line for functions/control flow in C++
- Max line length: ~100 characters observed

**Linting:**
- No explicit linter config (no `.eslintrc`, `.pylintrc`, etc.)
- Code follows consistent style through convention

## Import Organization

**C++ Headers:**
1. Standard library (`<cmath>`, `<algorithm>`, `<array>`)
2. External libraries (`"../external/json.hpp"`)
3. Project headers (same directory)

**Python:**
1. Standard library (`json`, `pathlib`)
2. Third-party (`numpy`, `scipy`, `matplotlib`)
3. Local modules (rare - most scripts are self-contained)

**Example from `Tests/validate_against_reference.py`:**
```python
import numpy as np
import json
from pathlib import Path

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
```

**Path Aliases:**
- None detected - use relative paths in C++ (`"../external/json.hpp"`)

## Error Handling

**C++ Patterns:**
- Clamping values to valid ranges rather than throwing:
```cpp
inline float clampf(float x, float lo, float hi) {
    return (x < lo) ? lo : ((x > hi) ? hi : x);
}

// Usage: prevent division by zero
float origRadius = std::max(stage.radius, 1e-12f);
```

- Default/fallback values for edge cases:
```cpp
if (norm <= 0.0) norm = 0.0001;  // Prevent silence near DC
```

**Python Patterns:**
- Try/except for optional dependencies with feature flags:
```python
try:
    import soundfile as sf
    HAS_SOUNDFILE = True
except ImportError:
    HAS_SOUNDFILE = False
```

- Assertions for data validation:
```python
assert len(variants) == NUM_VARIANTS, f"Expected 3 variants, got {len(variants)}"
```

- Main entry points wrapped in try/except:
```cpp
int main() {
    try {
        // ... code ...
    } catch (const std::exception& e) {
        std::cerr << "Error: " << e.what() << std::endl;
        return 1;
    }
}
```

## Logging

**Framework:** `std::printf` (C++), `print()` (Python) - no logging framework

**Patterns:**
- Debug output via printf in debug builds only:
```cpp
#if defined(JUCE_DEBUG) || defined(_DEBUG) || !defined(NDEBUG)
    void debugPrint() const {
        std::printf("=== ZPlaneFilter Debug ===\n");
        // ...
    }
#endif
```

- Python validation scripts use structured print output:
```python
print(f"\n{'='*60}")
print(f"TEST: {ref_name} (Morph={morph*100:.0f}%, Q={q*100:.0f}%)")
print('='*60)
```

## Comments

**When to Comment:**
- File-level documentation blocks explaining purpose and critical formulas
- Section separators using `//==============================================================================`
- Inline comments for critical/non-obvious formulas

**C++ Documentation Style:**
```cpp
/**
 * TRENCH Z-PLANE FILTER ENGINE - H-CHIP EMULATION
 *
 * 1:1 behavioral clone of E-mu Emulator X3 "Talking Hedz" Z-Plane filter.
 * Emulates Rossum H-Chip architecture:
 *   - Control-rate: coefficient target generation
 *   - Audio-rate: delta-add ramping + DF2T MAC only
 *
 * CRITICAL FORMULAS (from Cheat Engine captures):
 *   a1_actual = a1_captured * radius
 *   a2 = radius^2
 *   Q scaling: r = r_ref^(Q_ref/Q_new)
 */
```

**Python Docstrings:**
```python
def hz_to_semitone(hz):
    """Convert Hz to semitones relative to C5.

    Semitone space is logarithmic frequency space relative to C5.
    This enables linear interpolation to produce logarithmic frequency sweeps
    (the "Rossum sweep" effect from E-mu patents).

    Examples:
      C5 (523 Hz) -> 0 semitones
      C6 (1046 Hz) -> +12 semitones
    """
```

## Function Design

**Size:** Functions generally kept small (10-50 lines). Complex logic split into helpers.

**Parameters:**
- C++: Pass primitives by value, structs by const reference
- Return by value (no output parameters)

**Example:**
```cpp
inline BiquadCoeffs computeCoeffs(float a1_captured, float radius, int flag) {
    BiquadCoeffs c;
    // ... compute ...
    return c;
}
```

**Return Values:**
- Structs for multiple related values (`BiquadCoeffs`, `GridStageData`)
- Primitives for single values
- `std::array` for fixed-size collections

## Module Design

**C++ Header-Only:**
- All DSP code is header-only (`.h` files with inline implementations)
- No separate `.cpp` files for core DSP logic
- Enables easy inclusion and compiler optimization

**Exports:**
- Classes and structs at namespace scope
- `inline` functions for utilities
- No `extern` declarations

**Python Scripts:**
- Self-contained scripts with `if __name__ == "__main__":` guards
- Classes defined within scripts (not separate modules)
- Shared logic duplicated across scripts (no shared module)

## DSP-Specific Conventions

**Coefficient Naming:**
- `b0, b1, b2`: numerator (zeros)
- `a1, a2`: denominator (poles, note `a0 = 1` implicit)
- `z1, z2`: filter state (delay line)

**Processing Functions:**
- `processSample(float x)`: single sample
- `processBlock(float* data, int numSamples)`: block processing
- `reset()`: clear state

**Parameter Setting:**
- `setMorph(float m)`: expects 0-1 range
- `setQ(float q)`: expects 0-1 range
- Internal clamping to valid ranges

**Critical Formula Comments:**
- Label formulas as `CRITICAL:` when they are core to algorithm correctness:
```cpp
// CRITICAL: a1_actual = a1_captured * radius (proven formula)
c.a1 = a1_cap * r;
```

---

*Convention analysis: 2026-01-20*
