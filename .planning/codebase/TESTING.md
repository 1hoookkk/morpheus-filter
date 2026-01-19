# Testing Patterns

**Analysis Date:** 2026-01-20

## Test Framework

**C++:**
- No formal test framework (no Google Test, Catch2, etc.)
- Simple `main()` functions with assertions and manual verification
- Compiles to standalone executables

**Python:**
- No formal test framework (no pytest, unittest)
- Validation scripts with manual assertions and print-based reporting
- Dependencies: `numpy`, `scipy`, `matplotlib` (optional)

**Run Commands:**
```bash
# C++ test (Windows)
cd C:/Users/hooki/yup/Tests
g++ -std=c++17 -I../Source test_cartridge_load.cpp -o test_load.exe
./test_load.exe

# Python validation
python Tests/validate_against_reference.py
```

## Test File Organization

**Location:**
- C++ tests: `Tests/` directory
- Python validation: `Tests/` directory for production, root for development

**Naming:**
- C++ test files: `test_*.cpp` prefix
- Python validators: `validate_*.py` prefix

**Structure:**
```
Tests/
  test_cartridge_load.cpp      # C++ cartridge loading test
  test_load.exe                # Compiled test binary
  validate_against_reference.py # Python reference validation suite
```

**Development Scripts (root, gitignored):**
```
validate_zplane.py             # Ad-hoc Z-plane validation
validate_trench.py             # Trench filter validation v1
validate_trench_v2.py          # Trench filter validation v2
debug_*.py                     # Debug/exploration scripts
```

## Test Structure

**C++ Test Pattern:**
```cpp
#include "../Source/dsp/CartridgeLoader.h"
#include <iostream>

int main() {
    try {
        // Setup
        std::cout << "Loading cartridge from talking_hedz_extracted.json...\n";
        ZPlane::ZPlaneCartridge cart = ZPlane::loadCartridge("talking_hedz_extracted.json");

        // Verification
        const auto& cell = cart.data[0][0][0];
        float freqHz = ZPlane::semitoneToHz(cell.freqSemitone);

        // Assertion with pass/fail output
        if (freqHz > 3500 && freqHz < 3700) {
            std::cout << "  PASS: Frequency in expected range (3500-3700 Hz)\n";
        } else {
            std::cout << "  FAIL: Frequency outside expected range\n";
            return 1;
        }

        std::cout << "\n=== ALL TESTS PASSED ===\n";
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "Error: " << e.what() << std::endl;
        return 1;
    }
}
```

**Python Validation Pattern:**
```python
def test_reference_comparison(cart_path, base_path, ref_name, morph, q, transform=0.0):
    """Compare engine output against reference file (VAL-01, VAL-02)."""
    print(f"\n{'='*60}")
    print(f"TEST: {ref_name} (Morph={morph*100:.0f}%, Q={q*100:.0f}%)")
    print('='*60)

    # Load reference audio
    ref_path = find_reference_file(base_path, ref_name)
    if ref_path is None:
        print(f"  SKIP: Reference file not found: {ref_name}")
        return None

    ref_audio, sr = load_wav(ref_path)

    # Create engine and generate our response
    cart = load_cartridge(cart_path)
    engine = ZPlaneEngine(cart)
    engine.set_parameters(morph, q, transform)

    # Generate impulse response
    impulse = np.zeros(len(ref_audio))
    impulse[0] = 1.0
    our_response = engine.process_block(impulse)

    # Calculate RMS error
    rms_error = calculate_rms_error_db(ref_audio, our_response)

    # Pass/fail criteria
    print(f"\n  Results:")
    print(f"    RMS Error: {rms_error:.1f} dB")
    print(f"    Target: < 3.0 dB")

    if rms_error < 3.0:
        print(f"    STATUS: PASS")
        return True
    else:
        print(f"    STATUS: FAIL")
        return False
```

## Validation Test IDs

Tests use structured IDs for traceability:

| Test ID | Description | File |
|---------|-------------|------|
| VAL-01 | Output matches "hedz - m100q0.wav" within 3dB RMS | `Tests/validate_against_reference.py` |
| VAL-02 | Output matches "hedz - 5050.wav" within 3dB RMS | `Tests/validate_against_reference.py` |
| VAL-03 | Morph sweep produces audible vowel-like formant changes | `Tests/validate_against_reference.py` |
| VAL-04 | Q=0% produces flatter response than Q=100% | `Tests/validate_against_reference.py` |

## Mocking

**No mocking framework used.**

**Pattern for optional dependencies:**
```python
try:
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    print("Warning: matplotlib not available, plots will be skipped")

# Usage
def plot_responses():
    if not HAS_MATPLOTLIB:
        print("matplotlib not available - skipping plots")
        return
    # ... plotting code ...
```

**What to Mock:**
- Not applicable (no mocking framework)

**What NOT to Mock:**
- Reference audio files (real captured data from Emulator X3)
- DSP algorithms (need actual computation for validation)

## Fixtures and Factories

**Reference Audio Files:**
- Location: Project root (`C:/Users/hooki/yup/`)
- Format: WAV files captured from Emulator X3
- Naming: `hedz - {morph}{q}.wav` (e.g., `hedz - m100q0.wav`)
- Gitignored (binary audio files)

**Cartridge Data:**
- Location: `talking_hedz_extracted.json`
- Format: JSON with 3 variants x 7 stages x 289 grid cells
- Generated by: `Scripts/regenerate_cartridge.py`

**Test Data Loading:**
```python
def load_wav(path):
    """Load WAV file, return (samples, sample_rate)."""
    if HAS_SOUNDFILE:
        data, sr = sf.read(str(path))
        return data.astype(np.float32), sr
    elif HAS_SCIPY_WAV:
        sr, data = wavfile.read(str(path))
        if data.dtype == np.int16:
            data = data.astype(np.float32) / 32768.0
        return data, sr

def find_reference_file(base_path, pattern):
    """Find reference file with various naming conventions."""
    candidates = [
        base_path / pattern,
        base_path / pattern.replace(" - ", " "),
        base_path / pattern.replace(" - ", "_"),
    ]
    for c in candidates:
        if c.exists():
            return c
    return None
```

## Coverage

**Requirements:** None enforced (no coverage tooling)

**Implicit Coverage via Validation:**
- DSP algorithms validated against reference captures
- Parameter ranges tested (morph 0-100%, Q 0-100%)
- Edge cases: DC poles, ultrasonic frequencies

## Test Types

**Validation Tests (Primary):**
- Compare DSP output against reference audio from Emulator X3
- Pass/fail based on RMS error threshold (typically 3dB)
- Frequency response comparison via FFT

**Smoke Tests:**
- Cartridge loading succeeds
- Round-trip conversion accuracy
- All grid cells populated

**Visual Verification:**
- Frequency response plots saved as PNG
- Manual inspection of formant peaks

## Common Patterns

**Impulse Response Testing:**
```python
# Generate impulse
impulse = np.zeros(num_samples)
impulse[0] = 1.0

# Process through filter
response = filter.process_block(impulse)

# Analyze via FFT
fft_result = np.fft.rfft(response)
freqs = np.fft.rfftfreq(len(response), 1/sample_rate)
mag_db = 20 * np.log10(np.abs(fft_result) + 1e-10)
```

**RMS Error Calculation:**
```python
def calculate_rms_error_db(ref, test):
    """Calculate RMS error in dB between two signals."""
    min_len = min(len(ref), len(test))
    ref = ref[:min_len]
    test = test[:min_len]

    diff = ref - test
    rms_diff = np.sqrt(np.mean(diff ** 2))
    rms_ref = np.sqrt(np.mean(ref ** 2))

    if rms_ref < 1e-10:
        return float('inf')

    return 20 * np.log10(rms_diff / rms_ref)
```

**Peak Detection:**
```python
from scipy.signal import find_peaks

peaks, _ = find_peaks(magnitude_db, height=-20)
for p in peaks[:5]:
    print(f"  {freqs[p]:.0f} Hz: {magnitude_db[p]:.1f} dB")
```

**Test Result Aggregation:**
```python
def main():
    results = []

    # Run tests
    results.append(("VAL-01", test_reference_comparison(...)))
    results.append(("VAL-02", test_reference_comparison(...)))
    results.append(("VAL-03", test_morph_sweep(...)))
    results.append(("VAL-04", test_q_behavior(...)))

    # Summary
    passed = sum(1 for _, r in results if r)
    total = len(results)

    for name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"  {name}: {status}")

    print(f"\n  Total: {passed}/{total} tests passed")
    return 0 if passed == total else 1
```

## Writing New Tests

**For C++ functionality:**
1. Create `Tests/test_<feature>.cpp`
2. Include necessary headers from `Source/`
3. Use try/catch with return codes
4. Print PASS/FAIL for each assertion
5. Compile with: `g++ -std=c++17 -I../Source test_<feature>.cpp -o test_<feature>.exe`

**For Python validation:**
1. Create function `test_<feature>(...)` returning bool
2. Print structured output with test name header
3. Use numerical thresholds for pass/fail
4. Add to results list in `main()`
5. Generate plots if useful for debugging

**Pass/Fail Criteria:**
- RMS error < 3dB for audio comparison
- Frequency within semitone tolerance for formant matching
- Boolean assertions for structural validation

---

*Testing analysis: 2026-01-20*
