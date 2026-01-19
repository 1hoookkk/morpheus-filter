---
phase: 01-dsp-engine
plan: 04
type: execute
wave: 3
depends_on: ["01-01", "01-02", "01-03"]
files_modified:
  - Tests/validate_against_reference.py
autonomous: true

must_haves:
  truths:
    - "Validation compares output against reference WAV files"
    - "RMS error is calculated and reported"
    - "Test passes if RMS error < 3dB for both reference files"
    - "Frequency response plots generated for visual verification"
  artifacts:
    - path: "Tests/validate_against_reference.py"
      provides: "Automated accuracy testing against EmulatorX3 captures"
      min_lines: 250
  key_links:
    - from: "validate_against_reference.py"
      to: "ZPlaneEngine (Python port)"
      via: "filter processing"
      pattern: "class.*ZPlaneEngine|process_sample"
    - from: "test output"
      to: "reference WAV"
      via: "RMS comparison"
      pattern: "rms.*error|compare.*reference"
---

<objective>
Create the validation script that tests the DSP engine against EmulatorX3 reference recordings.

Purpose: Prove the implementation is accurate. VAL-01 and VAL-02 require <3dB RMS error against reference files. This script automates that validation.

Output: `Tests/validate_against_reference.py` with automated testing and plots.
</objective>

<context>
@.planning/phases/01-dsp-engine/01-RESEARCH.md (validation approach, code patterns)
@.planning/REQUIREMENTS.md (VAL-01 through VAL-04)
@talking_hedz_extracted.json (grid data format)
</context>

<reference_files>
The following reference files should exist in the project root:
- `hedz - m100q0.wav` - Reference capture at Morph=100%, Q=0%
- `hedz - 5050.wav` - Reference capture at Morph=50%, Q=50%
- `morph 100 q 0.wav` - Alternative naming
- `morph 100 q 100.wav` - Additional reference

If files use different names, the script will search for variants.
</reference_files>

<tasks>

<task type="auto">
  <name>Task 1: Create Python ZPlaneEngine matching C++ implementation</name>
  <files>Tests/validate_against_reference.py</files>
  <action>
Create `Tests/validate_against_reference.py` with a Python implementation that mirrors the C++ engine:

```python
"""
Validate ZPlaneEngine against EmulatorX3 reference recordings.

Tests:
- VAL-01: Output matches "hedz - m100q0.wav" within 3dB RMS error
- VAL-02: Output matches "hedz - 5050.wav" within 3dB RMS error
- VAL-03: Morph sweep produces audible vowel-like formant changes
- VAL-04: Q=0% produces flatter response than Q=100%
"""

import numpy as np
import json
from pathlib import Path

try:
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    print("Warning: matplotlib not available, plots will be skipped")

try:
    import soundfile as sf
    HAS_SOUNDFILE = True
except ImportError:
    try:
        from scipy.io import wavfile
        HAS_SOUNDFILE = False
        HAS_SCIPY_WAV = True
    except ImportError:
        HAS_SOUNDFILE = False
        HAS_SCIPY_WAV = False
        print("Warning: soundfile/scipy not available, WAV loading will fail")


# Constants matching C++ implementation
C5_HZ = 523.251
NUM_STAGES = 7
GRID_SIZE = 17
NUM_VARIANTS = 3


def hz_to_semitone(hz):
    """Convert Hz to semitones relative to C5"""
    if hz <= 0:
        return -120.0
    return 12.0 * np.log2(hz / C5_HZ)


def semitone_to_hz(semitone):
    """Convert semitones to Hz"""
    return C5_HZ * (2.0 ** (semitone / 12.0))


def is_ultrasonic(semitone):
    """Check if frequency is ultrasonic (>20kHz)"""
    return semitone > 63.3  # 12 * log2(20000/523.25)


class GridStageData:
    """Matches C++ GridStageData struct"""
    def __init__(self, freq_semitone=0, radius=0.5, gain_db=0, shape=0):
        self.freq_semitone = freq_semitone
        self.radius = radius
        self.gain_db = gain_db
        self.shape = shape  # 0=LP, 1=EQ


class ZPlaneCartridge:
    """Matches C++ ZPlaneCartridge struct"""
    def __init__(self):
        self.name = ""
        # data[variant][stage][grid_index]
        self.data = [[[GridStageData() for _ in range(GRID_SIZE * GRID_SIZE)]
                      for _ in range(NUM_STAGES)]
                     for _ in range(NUM_VARIANTS)]
        self.is_loaded = False


def load_cartridge(path):
    """Load cartridge from JSON, converting Hz to semitones"""
    cart = ZPlaneCartridge()

    with open(path) as f:
        j = json.load(f)

    cart.name = j.get("name", "Unknown")

    variants = j["variants"]
    assert len(variants) == NUM_VARIANTS, f"Expected 3 variants, got {len(variants)}"

    for vi, variant in enumerate(variants):
        stages = variant["stages"]
        assert len(stages) == NUM_STAGES, f"Expected 7 stages, got {len(stages)}"

        for si, stage in enumerate(stages):
            freqs = stage["freq_17x17"]
            gains = stage["gain_17x17"]
            radii = stage["radius_17x17"]

            assert len(freqs) == GRID_SIZE * GRID_SIZE

            shape_str = stage.get("shape", "lp")
            shape = 1 if shape_str in ("eq", "bp") else 0

            for gi in range(GRID_SIZE * GRID_SIZE):
                cell = cart.data[vi][si][gi]
                cell.freq_semitone = hz_to_semitone(freqs[gi])
                cell.radius = radii[gi]
                cell.gain_db = gains[gi]
                cell.shape = shape

    cart.is_loaded = True
    return cart
```

This establishes the data structures and loading. Continue in Task 2.
  </action>
  <verify>
File starts with:
- Constants matching C++ (C5_HZ, NUM_STAGES=7, GRID_SIZE=17, NUM_VARIANTS=3)
- `hz_to_semitone()` and `semitone_to_hz()` functions
- `GridStageData` and `ZPlaneCartridge` classes
- `load_cartridge()` function that converts Hz to semitones
  </verify>
  <done>Python data structures mirror C++ implementation</done>
</task>

<task type="auto">
  <name>Task 2: Implement trilinear interpolation and biquad processing</name>
  <files>Tests/validate_against_reference.py</files>
  <action>
Add the interpolator and filter engine to `validate_against_reference.py`:

```python
class GridInterpolator:
    """Trilinear interpolation matching C++ GridInterpolator"""

    def __init__(self, cartridge):
        self.cart = cartridge

    def interpolate(self, stage_idx, morph, transform, q):
        """Interpolate stage data at given position"""
        if not self.cart.is_loaded:
            return GridStageData()

        # Map 0-1 to grid indices
        gx = morph * (GRID_SIZE - 1)
        gy = transform * (GRID_SIZE - 1)
        gz = q * (NUM_VARIANTS - 1)

        ix = int(np.clip(gx, 0, GRID_SIZE - 2))
        iy = int(np.clip(gy, 0, GRID_SIZE - 2))
        iz = int(np.clip(gz, 0, NUM_VARIANTS - 2))

        fx = gx - ix
        fy = gy - iy
        fz = gz - iz

        def sample(vi, row, col):
            grid_idx = row * GRID_SIZE + col
            return self.cart.data[vi][stage_idx][grid_idx]

        def lerp_stage(a, b, t):
            result = GridStageData()
            result.freq_semitone = a.freq_semitone + (b.freq_semitone - a.freq_semitone) * t
            result.radius = a.radius + (b.radius - a.radius) * t
            result.gain_db = a.gain_db + (b.gain_db - a.gain_db) * t
            result.shape = a.shape  # Shape doesn't interpolate
            return result

        # 8-corner trilinear
        c00 = lerp_stage(sample(iz, iy, ix), sample(iz, iy, ix+1), fx)
        c01 = lerp_stage(sample(iz, iy+1, ix), sample(iz, iy+1, ix+1), fx)
        c0 = lerp_stage(c00, c01, fy)

        c10 = lerp_stage(sample(iz+1, iy, ix), sample(iz+1, iy, ix+1), fx)
        c11 = lerp_stage(sample(iz+1, iy+1, ix), sample(iz+1, iy+1, ix+1), fx)
        c1 = lerp_stage(c10, c11, fy)

        return lerp_stage(c0, c1, fz)

    def interpolate_all_stages(self, morph, transform, q):
        return [self.interpolate(i, morph, transform, q) for i in range(NUM_STAGES)]


def compute_biquad_from_stage(stage, sample_rate):
    """Compute biquad coefficients from stage data"""
    freq_hz = semitone_to_hz(stage.freq_semitone)
    nyquist = sample_rate / 2.0

    # Ultrasonic bypass
    if freq_hz > nyquist * 0.95 or freq_hz > 20000:
        return {'b0': 1.0, 'b1': 0.0, 'b2': 0.0, 'a1': 0.0, 'a2': 0.0, 'bypass': True}

    omega = 2.0 * np.pi * freq_hz / sample_rate
    omega = np.clip(omega, 0.001, 3.1)

    cos_omega = np.cos(omega)
    radius = np.clip(stage.radius, 0.0, 0.9999)

    # Denominator (poles)
    a1 = -2.0 * radius * cos_omega
    a2 = radius * radius

    # Numerator (zeros)
    if stage.shape == 0:  # LP
        dc_gain = 1.0 + a1 + a2
        norm = max(dc_gain / 4.0, 0.0001)
        b0 = norm
        b1 = 2.0 * norm
        b2 = norm
    else:  # EQ/BP
        scale = (1.0 - a2) / 2.0
        gain_linear = 10.0 ** (stage.gain_db / 20.0)
        b0 = scale * gain_linear
        b1 = 0.0
        b2 = -scale * gain_linear

    return {'b0': b0, 'b1': b1, 'b2': b2, 'a1': a1, 'a2': a2, 'bypass': False}


class ZPlaneEngine:
    """7-stage cascade filter matching C++ ZPlaneEngine"""

    def __init__(self, cartridge):
        self.interpolator = GridInterpolator(cartridge)
        self.sample_rate = 44100.0
        self.morph = 0.5
        self.q = 0.5
        self.transform = 0.0

        # Biquad state (z1, z2 per stage)
        self.z1 = [0.0] * NUM_STAGES
        self.z2 = [0.0] * NUM_STAGES
        self.coeffs = [None] * NUM_STAGES

    def set_parameters(self, morph, q, transform=0.0):
        self.morph = np.clip(morph, 0, 1)
        self.q = np.clip(q, 0, 1)
        self.transform = np.clip(transform, 0, 1)
        self._update_coefficients()

    def reset(self):
        self.z1 = [0.0] * NUM_STAGES
        self.z2 = [0.0] * NUM_STAGES

    def _update_coefficients(self):
        stages = self.interpolator.interpolate_all_stages(self.morph, self.transform, self.q)
        self.coeffs = [compute_biquad_from_stage(s, self.sample_rate) for s in stages]

    def process_sample(self, x):
        """Process through 7-stage cascade"""
        signal = x
        for i in range(NUM_STAGES):
            c = self.coeffs[i]
            if c['bypass']:
                continue

            # Direct Form II Transposed
            y = c['b0'] * signal + self.z1[i]
            self.z1[i] = c['b1'] * signal - c['a1'] * y + self.z2[i]
            self.z2[i] = c['b2'] * signal - c['a2'] * y
            signal = y

        return signal

    def process_block(self, block):
        return np.array([self.process_sample(x) for x in block])

    def get_frequency_response(self, num_points=2048):
        """Compute frequency response for plotting"""
        w = np.linspace(0, np.pi, num_points)
        H = np.ones(num_points, dtype=complex)

        for c in self.coeffs:
            if c['bypass']:
                continue
            z = np.exp(1j * w)
            num = c['b0'] + c['b1'] * z**(-1) + c['b2'] * z**(-2)
            den = 1 + c['a1'] * z**(-1) + c['a2'] * z**(-2)
            H *= num / den

        freqs = w * self.sample_rate / (2 * np.pi)
        return freqs, 20 * np.log10(np.abs(H) + 1e-10)
```
  </action>
  <verify>
File contains:
- `GridInterpolator` class with `interpolate()` and `interpolate_all_stages()`
- `compute_biquad_from_stage()` function with LP/EQ numerator formulas
- `ZPlaneEngine` class with `process_sample()` cascade loop
- `get_frequency_response()` for plotting
  </verify>
  <done>Python filter engine matches C++ implementation</done>
</task>

<task type="auto">
  <name>Task 3: Implement validation tests and main entry point</name>
  <files>Tests/validate_against_reference.py</files>
  <action>
Add the validation functions and main entry point:

```python
def load_wav(path):
    """Load WAV file, return (samples, sample_rate)"""
    if HAS_SOUNDFILE:
        data, sr = sf.read(path)
        return data.astype(np.float32), sr
    elif HAS_SCIPY_WAV:
        sr, data = wavfile.read(path)
        if data.dtype == np.int16:
            data = data.astype(np.float32) / 32768.0
        elif data.dtype == np.int32:
            data = data.astype(np.float32) / 2147483648.0
        return data, sr
    else:
        raise RuntimeError("No WAV loading library available")


def find_reference_file(pattern):
    """Find reference file with various naming conventions"""
    base = Path(__file__).parent.parent
    candidates = [
        base / pattern,
        base / pattern.replace(" - ", " "),
        base / pattern.replace(" - ", "_"),
        base / pattern.lower(),
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def calculate_rms_error_db(ref, test):
    """Calculate RMS error in dB between two signals"""
    # Align lengths
    min_len = min(len(ref), len(test))
    ref = ref[:min_len]
    test = test[:min_len]

    # RMS of difference
    diff = ref - test
    rms_diff = np.sqrt(np.mean(diff ** 2))

    # RMS of reference (for normalization)
    rms_ref = np.sqrt(np.mean(ref ** 2))

    if rms_ref < 1e-10:
        return float('inf')

    # Error in dB
    return 20 * np.log10(rms_diff / rms_ref)


def test_reference_comparison(cart_path, ref_name, morph, q, transform=0.0):
    """Compare engine output against reference file"""
    print(f"\n{'='*60}")
    print(f"TEST: {ref_name} (Morph={morph*100:.0f}%, Q={q*100:.0f}%)")
    print('='*60)

    # Find reference file
    ref_path = find_reference_file(ref_name)
    if ref_path is None:
        print(f"  SKIP: Reference file not found: {ref_name}")
        return None

    # Load reference
    ref_audio, sr = load_wav(ref_path)
    if len(ref_audio.shape) > 1:
        ref_audio = ref_audio[:, 0]  # Take first channel

    print(f"  Reference: {ref_path.name}")
    print(f"  Sample rate: {sr} Hz")
    print(f"  Duration: {len(ref_audio)/sr:.2f} s")

    # Load cartridge and create engine
    cart = load_cartridge(cart_path)
    engine = ZPlaneEngine(cart)
    engine.sample_rate = sr
    engine.set_parameters(morph, q, transform)
    engine.reset()

    # Generate impulse response (assuming reference is impulse response)
    impulse = np.zeros(len(ref_audio))
    impulse[0] = 1.0

    our_response = engine.process_block(impulse)

    # Skip initial samples (reference may have pre-delay)
    # Find where reference signal starts
    threshold = np.max(np.abs(ref_audio)) * 0.01
    start_idx = np.argmax(np.abs(ref_audio) > threshold)
    start_idx = max(0, start_idx - 10)

    ref_trimmed = ref_audio[start_idx:]
    our_trimmed = our_response[start_idx:]

    # Calculate RMS error
    rms_error = calculate_rms_error_db(ref_trimmed, our_trimmed)

    print(f"\n  Results:")
    print(f"    RMS Error: {rms_error:.1f} dB")
    print(f"    Target: < 3.0 dB")

    if rms_error < 3.0:
        print(f"    STATUS: PASS")
        return True
    else:
        print(f"    STATUS: FAIL")
        return False


def test_q_behavior(cart_path):
    """VAL-04: Verify Q=0% produces flatter response than Q=100%"""
    print(f"\n{'='*60}")
    print("TEST: Q Behavior (VAL-04)")
    print('='*60)

    cart = load_cartridge(cart_path)
    engine = ZPlaneEngine(cart)

    morph = 1.0  # Full morph

    # Get response at Q=0% and Q=100%
    engine.set_parameters(morph, 0.0)
    freqs_q0, mag_q0 = engine.get_frequency_response()

    engine.set_parameters(morph, 1.0)
    freqs_q100, mag_q100 = engine.get_frequency_response()

    # Calculate peak-to-valley ratio (indicator of "peakiness")
    # Higher ratio = more resonant peaks
    q0_range = np.max(mag_q0) - np.min(mag_q0)
    q100_range = np.max(mag_q100) - np.min(mag_q100)

    print(f"\n  Morph = 100%:")
    print(f"    Q=0%:   Response range = {q0_range:.1f} dB")
    print(f"    Q=100%: Response range = {q100_range:.1f} dB")

    if q0_range < q100_range:
        print(f"    STATUS: PASS (Q=0% is flatter)")
        return True
    else:
        print(f"    STATUS: FAIL (Q=0% should be flatter than Q=100%)")
        return False


def plot_frequency_responses(cart_path, output_path="validation_plots.png"):
    """Generate frequency response plots for visual verification"""
    if not HAS_MATPLOTLIB:
        print("Matplotlib not available, skipping plots")
        return

    cart = load_cartridge(cart_path)
    engine = ZPlaneEngine(cart)

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    # Plot 1: Q sweep at Morph=100%
    ax = axes[0, 0]
    ax.set_title("Q Sweep (Morph=100%)")
    for q in [0.0, 0.25, 0.5, 0.75, 1.0]:
        engine.set_parameters(1.0, q)
        freqs, mag = engine.get_frequency_response()
        ax.semilogx(freqs, mag, label=f"Q={q*100:.0f}%")
    ax.set_xlabel("Frequency (Hz)")
    ax.set_ylabel("Magnitude (dB)")
    ax.set_xlim(20, 20000)
    ax.set_ylim(-60, 30)
    ax.legend()
    ax.grid(True)

    # Plot 2: Morph sweep at Q=100%
    ax = axes[0, 1]
    ax.set_title("Morph Sweep (Q=100%)")
    for morph in [0.0, 0.25, 0.5, 0.75, 1.0]:
        engine.set_parameters(morph, 1.0)
        freqs, mag = engine.get_frequency_response()
        ax.semilogx(freqs, mag, label=f"Morph={morph*100:.0f}%")
    ax.set_xlabel("Frequency (Hz)")
    ax.set_ylabel("Magnitude (dB)")
    ax.set_xlim(20, 20000)
    ax.set_ylim(-60, 30)
    ax.legend()
    ax.grid(True)

    # Plot 3: Morph sweep at Q=0%
    ax = axes[1, 0]
    ax.set_title("Morph Sweep (Q=0%)")
    for morph in [0.0, 0.25, 0.5, 0.75, 1.0]:
        engine.set_parameters(morph, 0.0)
        freqs, mag = engine.get_frequency_response()
        ax.semilogx(freqs, mag, label=f"Morph={morph*100:.0f}%")
    ax.set_xlabel("Frequency (Hz)")
    ax.set_ylabel("Magnitude (dB)")
    ax.set_xlim(20, 20000)
    ax.set_ylim(-60, 30)
    ax.legend()
    ax.grid(True)

    # Plot 4: Reference comparison (if available)
    ax = axes[1, 1]
    ax.set_title("Stage Frequencies at Morph=100%")
    for q, style in [(0.0, '--'), (0.5, '-.'), (1.0, '-')]:
        engine.set_parameters(1.0, q)
        stages = engine.interpolator.interpolate_all_stages(1.0, 0.0, q)
        freqs = [semitone_to_hz(s.freq_semitone) for s in stages]
        ax.bar([i + q*0.25 for i in range(NUM_STAGES)], freqs,
               width=0.25, label=f"Q={q*100:.0f}%", alpha=0.7)
    ax.set_xlabel("Stage")
    ax.set_ylabel("Frequency (Hz)")
    ax.set_yscale('log')
    ax.legend()
    ax.grid(True)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    print(f"\nSaved: {output_path}")


def main():
    """Main validation entry point"""
    print("="*60)
    print("Z-Plane DSP Engine Validation")
    print("Testing against EmulatorX3 reference captures")
    print("="*60)

    # Find cartridge
    base = Path(__file__).parent.parent
    cart_path = base / "talking_hedz_extracted.json"

    if not cart_path.exists():
        print(f"ERROR: Cartridge not found: {cart_path}")
        return 1

    print(f"\nCartridge: {cart_path}")

    results = []

    # VAL-01: Reference match (m100q0)
    r = test_reference_comparison(cart_path, "hedz - m100q0.wav", 1.0, 0.0)
    if r is not None:
        results.append(("VAL-01", r))

    # VAL-02: Reference match (5050)
    r = test_reference_comparison(cart_path, "hedz - 5050.wav", 0.5, 0.5)
    if r is not None:
        results.append(("VAL-02", r))

    # VAL-04: Q behavior
    r = test_q_behavior(cart_path)
    results.append(("VAL-04", r))

    # Generate plots (VAL-03 visual verification)
    print(f"\n{'='*60}")
    print("Generating frequency response plots (VAL-03)...")
    print('='*60)
    plot_frequency_responses(cart_path)

    # Summary
    print(f"\n{'='*60}")
    print("VALIDATION SUMMARY")
    print('='*60)

    passed = sum(1 for _, r in results if r)
    total = len(results)

    for name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"  {name}: {status}")

    print(f"\n  Total: {passed}/{total} tests passed")

    if passed == total:
        print("\n  OVERALL: SUCCESS")
        return 0
    else:
        print("\n  OVERALL: FAILURE - Review failed tests")
        return 1


if __name__ == "__main__":
    exit(main())
```
  </action>
  <verify>
Script has:
- `load_wav()` function with soundfile/scipy fallback
- `calculate_rms_error_db()` function
- `test_reference_comparison()` for VAL-01, VAL-02
- `test_q_behavior()` for VAL-04
- `plot_frequency_responses()` for VAL-03 visual verification
- `main()` entry point that runs all tests
- Exit code 0 on success, 1 on failure
  </verify>
  <done>Validation script tests all VAL requirements and generates plots</done>
</task>

</tasks>

<verification>
Run the validation script:
```bash
cd C:/Users/hooki/yup
python Tests/validate_against_reference.py
```

Expected output:
1. VAL-01 test runs (may skip if reference file missing)
2. VAL-02 test runs (may skip if reference file missing)
3. VAL-04 test runs and passes (Q=0% flatter than Q=100%)
4. Plots saved to `validation_plots.png`
5. Summary shows pass/fail for each test

Success indicators:
- Script runs without Python errors
- VAL-04 passes (Q behavior correct)
- Plots generated showing formant peaks
- If reference files exist, RMS error reported (target <3dB)
</verification>

<success_criteria>
- validate_against_reference.py runs without errors
- Python ZPlaneEngine matches C++ implementation logic
- RMS error calculation works correctly
- Q behavior test (VAL-04) passes
- Frequency response plots generated
- Reference file comparison reports meaningful RMS error
- Script exits 0 when all available tests pass
</success_criteria>

<output>
After completion, create `.planning/phases/01-dsp-engine/01-04-SUMMARY.md`
</output>
