# Architecture

**Analysis Date:** 2026-01-20

## Pattern Overview

**Overall:** Domain-Driven DSP Engine with Data-Driven Cartridge System

**Key Characteristics:**
- Header-only C++ DSP implementation in `Trench` and `ZPlane` namespaces
- Data-driven design: filter behavior defined by JSON cartridge files
- Python validation/analysis tooling alongside C++ implementation
- Phase-based development with completed DSP engine (Phase 1)

## Layers

**Data Layer:**
- Purpose: Define filter coefficient data structures and cartridge format
- Location: `Source/dsp/ZPlaneData.h`, `ZPlaneData.h` (root)
- Contains: `StageData`, `MorphKeyframe`, `ZPlaneCartridge`, `BiquadCoeffs` structs
- Depends on: Standard library only
- Used by: Loader, Filter Engine

**Loader Layer:**
- Purpose: Parse JSON cartridge files into runtime data structures
- Location: `ZPlaneLoader.h` (root), `Source/dsp/CartridgeLoader.h` (deleted/in-progress)
- Contains: `ZPlaneLoader` class, `getTalkingHedzCartridge()` fallback function
- Depends on: Data Layer, JUCE JSON (or nlohmann/json)
- Used by: Filter Engine initialization

**DSP Engine Layer:**
- Purpose: Real-time audio processing using cascaded biquad filters
- Location: `Source/dsp/ZPlaneFilter.h` (Trench namespace), `ZPlaneFilter.h` (ZPlane namespace, root)
- Contains: `ZPlaneFilter`, `HChipStage`, `BiquadSection`, `Ramp` classes
- Depends on: Data Layer
- Used by: (Future) Plugin Processor

**Validation Layer:**
- Purpose: Verify DSP accuracy against EmulatorX3 reference recordings
- Location: Root directory Python scripts, `Tests/`
- Contains: Python implementations mirroring C++ DSP, FFT analysis, plotting
- Depends on: NumPy, SciPy, Matplotlib
- Used by: Development/testing workflow

## Data Flow

**Cartridge Loading:**

1. JSON file read from disk (`talking_hedz_cartridge.json` or `talking_hedz_extracted.json`)
2. `ZPlaneLoader::loadFromFile()` parses JSON into `ZPlaneCartridge` struct
3. Cartridge contains `keyframes[]` array, each with `position` and `stages[5]`
4. Each stage has `a1`, `radius`, `flag` coefficients captured from EmulatorX3

**Coefficient Computation (per control tick):**

1. User sets `morph` (0-1) and `q` (0-1) parameters
2. Find bracketing morph keyframes and compute interpolation factor `t`
3. For each of 5 stages:
   - Interpolate `a1` and `radius` between keyframes
   - Apply Q scaling: `r_scaled = r_ref^(Q_ref/Q_new)`
   - Compute biquad coefficients using flag-dependent numerator formulas
4. Set coefficient targets for ramped smoothing

**Audio Processing (per sample):**

1. Check if control interval elapsed, update coefficient targets
2. For each biquad stage, tick coefficient ramps (delta-add smoothing)
3. Process sample through 5-stage cascade using Direct Form II Transposed
4. Output = cascaded filter result

**State Management:**
- Filter state: `z1`, `z2` delay elements per stage
- Coefficient ramps: `cur`, `tgt`, `step`, `remaining` per coefficient
- Parameters: `morph`, `qKnob` normalized 0-1 values

## Key Abstractions

**ZPlaneFilter (main class):**
- Purpose: Complete Z-Plane filter implementation with H-Chip emulation
- Examples: `Source/dsp/ZPlaneFilter.h` (Trench namespace)
- Pattern: Control-rate coefficient generation + audio-rate delta-add ramping

**HChipStage (biquad with smoothing):**
- Purpose: Single biquad section with per-coefficient ramping
- Examples: `Source/dsp/ZPlaneFilter.h` lines 92-145
- Pattern: Ramp objects for b0, b1, b2, a1, a2 + DF2T processing

**StageRaw / StageData (coefficient data):**
- Purpose: Raw captured coefficients from EmulatorX3 memory
- Examples: `Source/dsp/ZPlaneFilter.h` lines 39-43, `ZPlaneData.h` lines 15-19
- Pattern: {a1, radius, flag} tuple per stage per keyframe

**BiquadCoeffs (computed coefficients):**
- Purpose: Actual biquad filter coefficients after Q scaling and numerator computation
- Examples: `Source/dsp/ZPlaneFilter.h` lines 48-51
- Pattern: {b0, b1, b2, a1, a2} for Direct Form II

## Entry Points

**C++ Filter Usage:**
- Location: `Source/dsp/ZPlaneFilter.h`
- Triggers: Plugin processBlock (future Phase 2)
- Responsibilities: `prepare()` -> `setMorph()/setQ()` -> `processBlock()`

**C++ Cartridge Loading:**
- Location: `ZPlaneLoader.h`, `Source/dsp/CartridgeLoader.h`
- Triggers: Plugin initialization, preset changes
- Responsibilities: Parse JSON, populate ZPlaneCartridge struct

**Python Validation:**
- Location: `validate_trench_v2.py`, `validate_zplane.py`
- Triggers: Manual execution during development
- Responsibilities: Compare C++ implementation against reference WAV files

**C++ Test Harness:**
- Location: `Tests/test_cartridge_load.cpp`
- Triggers: Build and run during development
- Responsibilities: Verify cartridge loading and data integrity

## Error Handling

**Strategy:** Defensive clamping with sensible defaults

**Patterns:**
- Parameter clamping: `morph = clampf(m, 0.0f, 1.0f)`
- Radius bounds: `clamp(r, 0.5f, 0.9999f)` to prevent instability
- Division safety: `std::max(r_ref, 1e-12f)` before log operations
- Numerator safety: `if (norm <= 0) norm = 0.0001f` to prevent silence

## Cross-Cutting Concerns

**Logging:** Debug builds use `std::printf()` in `debugPrint()` / `debugPrintForMorphQ()` methods, controlled by `JUCE_DEBUG` / `_DEBUG` / `NDEBUG` macros.

**Validation:** Python scripts generate PNG plots and compare FFT spectra. Reference WAV files (`hedz - m100q0.wav`, etc.) serve as ground truth.

**Authentication:** Not applicable (offline audio plugin).

## Critical Formulas

**Coefficient Multiplication (proven formula):**
```cpp
a1_actual = a1_captured * radius
a2 = radius * radius
```

**Q Scaling (radius reduction):**
```cpp
r_scaled = exp(log(r_ref) * (Q_ref / Q_new))
// Q_new = 0.5 + q_knob * 99.5  (maps 0-1 to 0.5-100)
```

**Bandpass Numerator (flag=1):**
```cpp
scale = (1.0 - a2) / 2.0
b0 = scale, b1 = 0, b2 = -scale
```

**Lowpass Numerator (flag=0):**
```cpp
norm = (1.0 + a1 + a2) / 4.0
b0 = norm, b1 = 2*norm, b2 = norm
```

---

*Architecture analysis: 2026-01-20*
