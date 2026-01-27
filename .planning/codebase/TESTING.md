# Testing Patterns

**Analysis Date:** 2026-01-27

## Test Framework

**Runner:**
- Python scripts (no formal framework like pytest)
- Manual validation scripts in `tools/` directory
- No C++ unit test framework configured

**Assertion Library:**
- Manual assertions via `if/else` and print statements
- NumPy comparison functions: `np.any(np.isnan())`, `np.any(np.isinf())`

**Run Commands:**
```bash
python tools/test_dsp.py              # Run DSP validation test
python tools/validate_audio.py        # Run audio comparison validation
python tools/test_zplane_filter.py    # Run Z-plane filter test
```

## Test File Organization

**Location:**
- All test/validation scripts in `tools/` directory (separate from source)
- Reference audio in `validation/` directory
- Output files in `validation/output/` directory

**Naming:**
- Test scripts: `test_*.py` - `test_dsp.py`, `test_zplane_filter.py`
- Validation scripts: `validate_*.py` - `validate_audio.py`, `validate_wav.py`
- Analysis scripts: `analyze_*.py`, `sweep_*.py`, `solve_*.py`
- Reference audio: descriptive names - `bypassed-pinknoise.wav`, `hedzmorph0q100.wav`

**Structure:**
```
tools/
├── test_dsp.py                 # Main DSP validation
├── test_zplane_filter.py       # Z-plane filter test
├── test_allpole.py             # Topology tests
├── test_parallel.py            # Parallel vs cascade tests
├── test_hybrid_topology.py     # Hybrid topology tests
├── validate_audio.py           # Audio comparison harness
├── ripper.py                   # Memory capture tool
└── analyze_*.py                # Analysis utilities

validation/
├── bypassed-pinknoise.wav      # Dry input (pink noise)
├── hedzmorph0q100.wav          # X3 reference: M0 Q100
├── hedzmorph100q100.wav        # X3 reference: M100 Q100
├── hedzmorph100q0.wav          # X3 reference: M100 Q0
└── output/                     # Test output directory
    ├── test_m0q100.wav
    ├── test_m0q100_spectrum.csv
    └── validation_results.json
```

## Test Structure

**Suite Organization:**
```python
#!/usr/bin/env python3
"""
TRENCH DSP Test Script

Tests the formant filter implementation by:
1. Loading bypassed-pinknoise.wav
2. Processing through a Python implementation of the filter
3. Comparing spectral peaks to X3 reference recordings

Usage:
    python tools/test_dsp.py
"""

def main():
    print("=" * 70)
    print("TRENCH DSP Test")
    print("=" * 70)

    # Test configurations
    tests = [
        ("M0_Q100", 0.0, 1.0, ref_m0_q100, [178, 1077, 1701, 2498, 4915]),
        ("M100_Q100", 1.0, 1.0, ref_m100_q100, [221, 2417, 2719]),
        ("M100_Q0", 1.0, 0.0, ref_m100_q0, [215, 2024, 2681, 3047]),
    ]

    all_passed = True
    for name, morph, q, ref_file, expected_peaks in tests:
        # Run test...
        pass

    return 0 if all_passed else 1

if __name__ == "__main__":
    exit(main())
```

**Patterns:**
- Setup: Load reference files, create filter instances
- Execute: Process audio through filter
- Verify: Compare output to reference, check for NaN/Inf
- Report: Print detailed results with pass/fail status

## Mocking

**Framework:** None - tests use real DSP implementations

**Patterns:**
- Python reimplements C++ DSP classes for validation:
  ```python
  class Biquad:
      """Direct Form II Transposed biquad filter"""
      def __init__(self):
          self.b0 = 1.0
          self.b1 = 0.0
          # ...
  ```

**What to Mock:**
- Memory access (for capture tools) uses `pymem` library
- Audio file I/O uses `scipy.io.wavfile` or `soundfile`

**What NOT to Mock:**
- DSP algorithms (must match C++ implementation exactly)
- Reference audio files (golden truth)

## Fixtures and Factories

**Test Data:**
```python
# Captured coefficients from TalkingHedz.json (validated ground truth)
M0_Q100 = [
    {"a1": -1.976510, "r": 0.998242, "flag": 1.0},  # 994 Hz
    {"a1": -1.938977, "r": 0.998296, "flag": 1.0},  # 1690 Hz
    {"a1": -1.872895, "r": 0.998353, "flag": 1.0},  # 2485 Hz
    {"a1": -1.523842, "r": 0.992409, "flag": 1.0},  # 4881 Hz
    {"a1": -1.997572, "r": 0.998289, "flag": 0.0},  # Lowpass
]

M100_Q100 = [
    {"a1": -1.996743, "r": 0.998619, "flag": 1.0},  # 156 Hz
    # ...
]
```

**Location:**
- Inline in test scripts (no separate fixtures directory)
- Reference data in `CLAUDE.md` as source of truth
- Audio fixtures in `validation/` directory

## Coverage

**Requirements:** None enforced

**Current Coverage:**
- DSP stability: Checks for NaN/Inf in output
- Spectral accuracy: Compares FFT peaks to reference
- Level matching: RMS delta within tolerance

**View Coverage:**
- No coverage tool configured
- Manual inspection of test output

## Test Types

**Unit Tests:**
- Not formally structured as unit tests
- Individual Python scripts test specific DSP components
- Example: `test_allpole.py` tests all-pole filter topology

**Integration Tests:**
- Full processing chain tests in `validate_audio.py`
- Loads dry audio -> processes through cascade -> compares to reference

**E2E Tests:**
- Plugin must be built and tested manually in DAW
- No automated E2E testing framework

## Common Patterns

**Async Testing:**
Not applicable (synchronous processing)

**Error Testing:**
```python
# Check for NaN/Inf
if np.any(np.isnan(output)):
    print("  ERROR: Output contains NaN!")
    all_passed = False
    continue
if np.any(np.isinf(output)):
    print("  ERROR: Output contains Inf!")
    all_passed = False
    continue
```

**Spectral Comparison:**
```python
def compute_spectral_error(test_samples, ref_samples, sample_rate,
                           freq_lo=100.0, freq_hi=8000.0):
    """Compute spectral error between test and reference."""
    freqs_t, spec_t = compute_spectrum_db(test_samples[:n], sample_rate)
    freqs_r, spec_r = compute_spectrum_db(ref_samples[:n], sample_rate)

    mask = (freqs_t >= freq_lo) & (freqs_t <= freq_hi)
    error_db = np.abs(spec_t - spec_r)

    mean_error = np.mean(error_db[mask])
    max_error = np.max(error_db[mask])

    return mean_error, max_error, freqs_t, error_db
```

**Pass/Fail Criteria:**
```python
# From validate_audio.py
passed = result['mean_spectral_error_db'] < 3.0 and abs(result['rms_delta_db']) < 1.0
print(f"PASS: {passed}")
```

## Validation Workflow

**Audio Comparison Harness:**
1. Load dry input (`bypassed-pinknoise.wav`)
2. Process through DSP cascade
3. Compare to X3 reference recording
4. Report metrics:
   - Mean spectral error (100-8000 Hz)
   - Max spectral error
   - RMS delta (dB)

**Success Criteria:**
- Mean spectral error < 3.0 dB
- RMS delta < 1.0 dB
- No NaN or Inf in output

**Output Artifacts:**
- Processed WAV file for manual inspection
- Spectrum CSV for detailed analysis
- JSON results file with all metrics

## Command-Line Interface

**Standard Pattern:**
```python
def main():
    parser = argparse.ArgumentParser(description='TRENCH Audio Validation Harness')
    parser.add_argument('--validation-dir', default='validation')
    parser.add_argument('--output-dir', default='validation/output')
    parser.add_argument('--gain-db', type=float, default=12.0)
    parser.add_argument('--test', choices=['m0q100', 'm100q100', 'both'], default='both')
    parser.add_argument('--zero-mode', choices=['allpole', 'bandpass', 'matched', 'parametric'])

    args = parser.parse_args()
    # ...
```

## Missing Test Infrastructure

**Gaps:**
- No C++ unit test framework (Catch2, GoogleTest)
- No CI/CD pipeline for automated testing
- No code coverage reporting
- No automated plugin testing (DAW integration)
- No performance benchmarks

**Recommended Additions:**
1. Add Catch2 or GoogleTest for C++ unit tests
2. Create CMake target for running tests
3. Add GitHub Actions workflow for CI
4. Consider JUCE's unit test framework

---

*Testing analysis: 2026-01-27*
