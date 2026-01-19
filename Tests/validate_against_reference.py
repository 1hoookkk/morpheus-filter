"""
Validate ZPlaneEngine against EmulatorX3 reference recordings.

Tests:
- VAL-01: Output matches "hedz - m100q0.wav" within 3dB RMS error
- VAL-02: Output matches "hedz - 5050.wav" within 3dB RMS error
- VAL-03: Morph sweep produces audible vowel-like formant changes
- VAL-04: Q=0% produces flatter response than Q=100%

This Python implementation mirrors the C++ ZPlaneEngine exactly,
enabling accurate validation against EmulatorX3 reference captures.
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
    HAS_SOUNDFILE = False
    try:
        from scipy.io import wavfile
        HAS_SCIPY_WAV = True
    except ImportError:
        HAS_SCIPY_WAV = False
        print("Warning: soundfile/scipy not available, WAV loading may fail")


# =============================================================================
# Constants matching C++ implementation (from GridInterpolator.h)
# =============================================================================
C5_HZ = 523.251           # MIDI note 72 - capture reference
NUM_STAGES = 7            # 7-stage cascade
GRID_SIZE = 17            # 17x17 morph grid
NUM_VARIANTS = 3          # Q variants (0%, 50%, 100%)


# =============================================================================
# Hz/Semitone Conversion Utilities (matching C++ implementation)
# =============================================================================

def hz_to_semitone(hz):
    """Convert Hz to semitones relative to C5.

    Semitone space is logarithmic frequency space relative to C5.
    This enables linear interpolation to produce logarithmic frequency sweeps
    (the "Rossum sweep" effect from E-mu patents).

    Examples:
      C5 (523 Hz) -> 0 semitones
      C6 (1046 Hz) -> +12 semitones
      C4 (262 Hz) -> -12 semitones
      A4 (440 Hz) -> -3 semitones
    """
    if hz <= 0:
        return -120.0  # Effectively DC, maps to inaudible
    return 12.0 * np.log2(hz / C5_HZ)


def semitone_to_hz(semitone):
    """Convert semitones to Hz."""
    return C5_HZ * (2.0 ** (semitone / 12.0))


def is_ultrasonic(semitone):
    """Check if frequency is ultrasonic (>20kHz, should bypass).

    20kHz in semitones relative to C5: 12 * log2(20000/523.25) = ~63.3
    """
    return semitone > 63.3


# =============================================================================
# GridStageData - Per-stage data at a single grid cell
# Matches C++ GridStageData struct
# =============================================================================
class GridStageData:
    """Per-stage data at a single grid cell (stored in semitone space)."""

    def __init__(self, freq_semitone=0.0, radius=0.5, gain_db=0.0, shape=0):
        self.freq_semitone = freq_semitone  # Frequency in semitones relative to C5
        self.radius = radius                 # Pole radius 0-1
        self.gain_db = gain_db              # Gain in dB
        self.shape = shape                   # 0=LP, 1=EQ (bandpass)


# =============================================================================
# ZPlaneCartridge - Complete cartridge with 3 variants x 7 stages x 289 grid cells
# Matches C++ ZPlaneCartridge struct
# =============================================================================
class ZPlaneCartridge:
    """Complete cartridge with 3 variants x 7 stages x 289 grid cells.

    Data layout: [variant][stage][gridIndex]
    gridIndex = row * 17 + col (row=transform, col=morph)
    """

    def __init__(self):
        self.name = ""
        # Data layout: [variant][stage][gridIndex]
        # variant: 0=Q0%, 1=Q50%, 2=Q100%
        # stage: 0-6 (7 cascade stages)
        # gridIndex: row * 17 + col where row=transform (0-16), col=morph (0-16)
        self.data = [[[GridStageData() for _ in range(GRID_SIZE * GRID_SIZE)]
                      for _ in range(NUM_STAGES)]
                     for _ in range(NUM_VARIANTS)]
        self.is_loaded = False


def load_cartridge(path):
    """Load cartridge from JSON, converting Hz to semitones.

    CRITICAL: Hz values are converted to semitone space on load (not at render
    time). This enables proper logarithmic frequency interpolation per E-mu
    patents - the "Rossum sweep" effect.
    """
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

            assert len(freqs) == GRID_SIZE * GRID_SIZE, f"Expected 289 grid cells, got {len(freqs)}"

            # Determine shape from string
            shape_str = stage.get("shape", "lp")
            shape = 1 if shape_str in ("eq", "bp") else 0

            for gi in range(GRID_SIZE * GRID_SIZE):
                cell = cart.data[vi][si][gi]
                # CRITICAL: Convert Hz to semitones on load
                cell.freq_semitone = hz_to_semitone(freqs[gi])
                cell.radius = radii[gi]
                cell.gain_db = gains[gi]
                cell.shape = shape

    cart.is_loaded = True
    return cart


# =============================================================================
# GridInterpolator - Trilinear interpolation across Morph x Transform x Q
# Matches C++ GridInterpolator class
#
# The 17x17x3 grid requires interpolation in 3 dimensions:
#   Morph (X): 0-1 maps to columns 0-16
#   Transform (Y): 0-1 maps to rows 0-16
#   Q (Z): 0-1 maps to variants 0-2
#
# All interpolation happens in SEMITONE SPACE - this is key to achieving
# the "Rossum sweep" effect where linear interpolation produces logarithmic
# frequency motion.
# =============================================================================
class GridInterpolator:
    """Trilinear interpolation matching C++ GridInterpolator."""

    def __init__(self, cartridge):
        self.cart = cartridge

    def interpolate(self, stage_idx, morph, transform, q):
        """Interpolate stage data at given position.

        Args:
            stage_idx: Stage index 0-6
            morph: 0-1 (X-axis, columns)
            transform: 0-1 (Y-axis, rows) - typically fixed at 0 for Talking Hedz
            q: 0-1 (Z-axis, interpolates between 3 variants)

        Returns:
            GridStageData: Interpolated stage parameters
        """
        if not self.cart or not self.cart.is_loaded:
            return GridStageData()

        # Clamp inputs to valid range
        morph = np.clip(morph, 0.0, 1.0)
        transform = np.clip(transform, 0.0, 1.0)
        q = np.clip(q, 0.0, 1.0)

        # Map 0-1 to grid indices
        gx = morph * (GRID_SIZE - 1)       # 0-16
        gy = transform * (GRID_SIZE - 1)   # 0-16
        gz = q * (NUM_VARIANTS - 1)        # 0-2

        # Integer indices (clamped for interpolation base)
        ix = int(np.clip(gx, 0, GRID_SIZE - 2))
        iy = int(np.clip(gy, 0, GRID_SIZE - 2))
        iz = int(np.clip(gz, 0, NUM_VARIANTS - 2))

        # Fractional parts
        fx = gx - ix
        fy = gy - iy
        fz = gz - iz

        def sample(vi, row, col):
            """Sample a grid cell."""
            grid_idx = row * GRID_SIZE + col
            return self.cart.data[vi][stage_idx][grid_idx]

        def lerp_stage(a, b, t):
            """Linear interpolation of stage data (in semitone space)."""
            result = GridStageData()
            result.freq_semitone = a.freq_semitone + (b.freq_semitone - a.freq_semitone) * t
            result.radius = a.radius + (b.radius - a.radius) * t
            result.gain_db = a.gain_db + (b.gain_db - a.gain_db) * t
            result.shape = a.shape  # Shape doesn't interpolate (discrete)
            return result

        # 8-corner trilinear interpolation
        # Bottom face (variant iz)
        c00 = lerp_stage(sample(iz, iy, ix), sample(iz, iy, ix+1), fx)
        c01 = lerp_stage(sample(iz, iy+1, ix), sample(iz, iy+1, ix+1), fx)
        c0 = lerp_stage(c00, c01, fy)

        # Top face (variant iz+1)
        c10 = lerp_stage(sample(iz+1, iy, ix), sample(iz+1, iy, ix+1), fx)
        c11 = lerp_stage(sample(iz+1, iy+1, ix), sample(iz+1, iy+1, ix+1), fx)
        c1 = lerp_stage(c10, c11, fy)

        # Interpolate between variants (Q axis)
        return lerp_stage(c0, c1, fz)

    def interpolate_all_stages(self, morph, transform, q):
        """Convenience: get all 7 stages at once."""
        return [self.interpolate(i, morph, transform, q) for i in range(NUM_STAGES)]


# =============================================================================
# Compute biquad coefficients from grid stage data
# Matches C++ computeBiquadFromStage function
# Source: US Patent 5,170,369 and Audio EQ Cookbook
# =============================================================================
def compute_biquad_from_stage(stage, sample_rate):
    """Compute biquad coefficients from stage data.

    Sample rate handling (DSP-07):
    Because we store frequencies in semitones (absolute pitch) and convert to Hz
    at render time, sample rate handling is automatic via the omega calculation:
      omega = 2 * pi * f / fs

    At 44.1kHz: 1kHz -> omega = 0.142
    At 96kHz:   1kHz -> omega = 0.065 (lower, preserves analog frequency)
    """
    # Convert semitone to Hz
    freq_hz = semitone_to_hz(stage.freq_semitone)

    # Nyquist limit for this sample rate
    nyquist = sample_rate / 2.0

    # Check for ultrasonic - bypass if:
    # 1. Frequency > 95% of Nyquist (too close to aliasing)
    # 2. Frequency > 20kHz (inaudible)
    # This handles both DSP-06 (ultrasonic bypass) and DSP-07 (sample rate warping)
    if freq_hz > nyquist * 0.95 or freq_hz > 20000.0:
        return {'b0': 1.0, 'b1': 0.0, 'b2': 0.0, 'a1': 0.0, 'a2': 0.0, 'bypass': True}

    # Compute omega (normalized angular frequency)
    omega = 2.0 * np.pi * freq_hz / sample_rate

    # Clamp to valid range (must be < pi for stability)
    omega = np.clip(omega, 0.001, 3.1)

    cos_omega = np.cos(omega)
    radius = np.clip(stage.radius, 0.0, 0.9999)

    # Denominator (poles) - same for all filter types
    a1 = -2.0 * radius * cos_omega
    a2 = radius * radius

    # Numerator (zeros) - depends on shape
    if stage.shape == 0:
        # LOWPASS (LP): zeros at Nyquist (z = -1)
        # Unity DC gain normalization
        dc_gain = 1.0 + a1 + a2
        norm = dc_gain / 4.0
        norm = max(norm, 0.0001)  # Prevent silence near DC (Pitfall 2)

        b0 = norm
        b1 = 2.0 * norm
        b2 = norm
    else:
        # EQ/BANDPASS: zeros at DC (z = +1) and Nyquist (z = -1)
        # Unity peak gain at resonance
        scale = (1.0 - a2) / 2.0

        # Apply gain boost/cut from grid data
        gain_linear = 10.0 ** (stage.gain_db / 20.0)

        b0 = scale * gain_linear
        b1 = 0.0
        b2 = -scale * gain_linear

    return {'b0': b0, 'b1': b1, 'b2': b2, 'a1': a1, 'a2': a2, 'bypass': False}


# =============================================================================
# ZPlaneEngine - 7-stage cascade filter processor
# Matches C++ ZPlaneEngine class
#
# The Z-Plane filter is a CASCADE of 7 biquad sections. Signal flows
# sequentially through all stages: stage0 -> stage1 -> ... -> stage6
# =============================================================================
class ZPlaneEngine:
    """7-stage cascade filter matching C++ ZPlaneEngine."""

    DEFAULT_SAMPLE_RATE = 44100.0

    def __init__(self, cartridge):
        self.interpolator = GridInterpolator(cartridge)
        self.sample_rate = self.DEFAULT_SAMPLE_RATE
        self.morph = 0.5
        self.q = 0.5
        self.transform = 0.0

        # Biquad state (z1, z2 per stage) - Direct Form II Transposed
        self.z1 = [0.0] * NUM_STAGES
        self.z2 = [0.0] * NUM_STAGES
        self.coeffs = [None] * NUM_STAGES

        # Initial coefficient computation
        self._update_coefficients()

    def set_parameters(self, morph, q, transform=0.0):
        """Set filter parameters.

        Args:
            morph: 0-1 (Morph knob)
            q: 0-1 (Q knob, interpolates between 3 variants)
            transform: 0-1 (Transform parameter, typically 0 for Talking Hedz)
        """
        self.morph = np.clip(morph, 0, 1)
        self.q = np.clip(q, 0, 1)
        self.transform = np.clip(transform, 0, 1)
        self._update_coefficients()

    def reset(self):
        """Reset filter state (clear all delay lines)."""
        self.z1 = [0.0] * NUM_STAGES
        self.z2 = [0.0] * NUM_STAGES

    def _update_coefficients(self):
        """Update coefficients from current parameters."""
        stages = self.interpolator.interpolate_all_stages(self.morph, self.transform, self.q)
        self.coeffs = [compute_biquad_from_stage(s, self.sample_rate) for s in stages]

    def process_sample(self, x):
        """Process single sample through 7-stage CASCADE.

        Topology: signal flows stage0 -> stage1 -> ... -> stage6
        """
        signal = x
        for i in range(NUM_STAGES):
            c = self.coeffs[i]
            if c['bypass']:
                continue  # Ultrasonic stage - passthrough

            # Direct Form II Transposed
            y = c['b0'] * signal + self.z1[i]
            self.z1[i] = c['b1'] * signal - c['a1'] * y + self.z2[i]
            self.z2[i] = c['b2'] * signal - c['a2'] * y
            signal = y

        return signal

    def process_block(self, block):
        """Process block of samples."""
        return np.array([self.process_sample(x) for x in block])

    def get_frequency_response(self, num_points=2048):
        """Compute frequency response for plotting.

        Returns:
            freqs: Frequency axis in Hz
            mag_db: Magnitude response in dB
        """
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

    def get_stage_frequencies(self):
        """Get current stage frequencies in Hz (for visualization/debugging)."""
        stages = self.interpolator.interpolate_all_stages(self.morph, self.transform, self.q)
        return [semitone_to_hz(s.freq_semitone) for s in stages]

    def get_stage_bypass_states(self):
        """Get bypass state for each stage (True = ultrasonic, passthrough)."""
        return [c['bypass'] for c in self.coeffs]


# =============================================================================
# WAV File Loading
# =============================================================================

def load_wav(path):
    """Load WAV file, return (samples, sample_rate)."""
    # Convert Path to string for soundfile compatibility
    path_str = str(path)
    if HAS_SOUNDFILE:
        data, sr = sf.read(path_str)
        return data.astype(np.float32), sr
    elif HAS_SCIPY_WAV:
        sr, data = wavfile.read(path_str)
        if data.dtype == np.int16:
            data = data.astype(np.float32) / 32768.0
        elif data.dtype == np.int32:
            data = data.astype(np.float32) / 2147483648.0
        return data, sr
    else:
        raise RuntimeError("No WAV loading library available (install soundfile or scipy)")


def find_reference_file(base_path, pattern):
    """Find reference file with various naming conventions."""
    candidates = [
        base_path / pattern,
        base_path / pattern.replace(" - ", " "),
        base_path / pattern.replace(" - ", "_"),
        base_path / pattern.lower(),
        base_path / pattern.replace(" - ", "-"),
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


# =============================================================================
# Validation Functions
# =============================================================================

def calculate_rms_error_db(ref, test):
    """Calculate RMS error in dB between two signals.

    Returns the ratio of RMS(difference) to RMS(reference) in dB.
    Lower is better. 0 dB = identical signals.
    """
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

    # Error in dB (ratio of error to reference)
    return 20 * np.log10(rms_diff / rms_ref)


def analyze_impulse_response(audio, sample_rate, label=""):
    """Analyze impulse response characteristics."""
    # Find peak
    peak_idx = np.argmax(np.abs(audio))
    peak_val = audio[peak_idx]

    # Find -60dB decay point
    threshold = np.abs(peak_val) * 0.001  # -60dB
    decay_idx = len(audio) - 1
    for i in range(peak_idx, len(audio)):
        if np.abs(audio[i]) < threshold:
            decay_idx = i
            break

    decay_time_ms = (decay_idx - peak_idx) / sample_rate * 1000

    # Compute spectrum
    fft = np.fft.rfft(audio)
    freqs = np.fft.rfftfreq(len(audio), 1/sample_rate)
    mag_db = 20 * np.log10(np.abs(fft) + 1e-10)

    # Find formant peaks (local maxima in spectrum, 200-8000 Hz range)
    formant_range = (freqs >= 200) & (freqs <= 8000)
    formant_freqs = freqs[formant_range]
    formant_mag = mag_db[formant_range]

    # Simple peak detection
    peaks = []
    for i in range(1, len(formant_mag) - 1):
        if formant_mag[i] > formant_mag[i-1] and formant_mag[i] > formant_mag[i+1]:
            if formant_mag[i] > np.max(formant_mag) - 20:  # Within 20dB of max
                peaks.append((formant_freqs[i], formant_mag[i]))

    print(f"  {label} Analysis:")
    print(f"    Peak at sample {peak_idx}, value {peak_val:.4f}")
    print(f"    Decay time (-60dB): {decay_time_ms:.1f} ms")
    print(f"    Formant peaks: {len(peaks)}")
    for i, (f, m) in enumerate(peaks[:5]):  # Show top 5 peaks
        print(f"      F{i+1}: {f:.0f} Hz ({m:.1f} dB)")

    return peaks


def test_reference_comparison(cart_path, base_path, ref_name, morph, q, transform=0.0):
    """Compare engine output against reference file (VAL-01, VAL-02).

    This compares the impulse response of our filter to a captured
    impulse response from EmulatorX3.
    """
    print(f"\n{'='*60}")
    print(f"TEST: {ref_name} (Morph={morph*100:.0f}%, Q={q*100:.0f}%)")
    print('='*60)

    # Find reference file
    ref_path = find_reference_file(base_path, ref_name)
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
    print(f"  RMS level: {20*np.log10(np.sqrt(np.mean(ref_audio**2)) + 1e-10):.1f} dB")

    # Analyze reference
    ref_peaks = analyze_impulse_response(ref_audio, sr, "Reference")

    # Load cartridge and create engine
    cart = load_cartridge(cart_path)
    engine = ZPlaneEngine(cart)
    engine.sample_rate = sr
    engine.set_parameters(morph, q, transform)
    engine.reset()

    # Generate impulse response
    impulse = np.zeros(len(ref_audio))
    impulse[0] = 1.0

    our_response = engine.process_block(impulse)

    # Analyze our response
    our_peaks = analyze_impulse_response(our_response, sr, "Our engine")

    # Compare formant frequencies (more meaningful than RMS for filter validation)
    print(f"\n  Formant Comparison:")
    if len(ref_peaks) > 0 and len(our_peaks) > 0:
        for i, ((rf, rm), (of, om)) in enumerate(zip(ref_peaks[:3], our_peaks[:3])):
            diff_cents = 1200 * np.log2(of / rf) if rf > 0 else 0
            diff_semitones = diff_cents / 100
            print(f"    F{i+1}: Ref={rf:.0f}Hz, Ours={of:.0f}Hz, Diff={diff_semitones:+.1f} semitones")

    # Calculate RMS error
    # Skip initial samples - find where reference signal starts
    threshold = np.max(np.abs(ref_audio)) * 0.01
    start_idx = np.argmax(np.abs(ref_audio) > threshold)
    start_idx = max(0, start_idx - 10)

    ref_trimmed = ref_audio[start_idx:]
    our_trimmed = our_response[start_idx:]

    rms_error = calculate_rms_error_db(ref_trimmed, our_trimmed)

    print(f"\n  Results:")
    print(f"    RMS Error: {rms_error:.1f} dB")
    print(f"    Target: < 3.0 dB")

    if rms_error < 3.0:
        print(f"    STATUS: PASS")
        return True
    else:
        print(f"    STATUS: FAIL (see formant analysis above for potential tuning offset)")
        # Note about potential 7.4 semitone offset
        if len(ref_peaks) > 0 and len(our_peaks) > 0:
            avg_diff = np.mean([1200 * np.log2(o[0] / r[0]) / 100
                               for r, o in zip(ref_peaks[:3], our_peaks[:3])
                               if r[0] > 0])
            if abs(avg_diff) > 5:
                print(f"    NOTE: Average formant offset is {avg_diff:+.1f} semitones")
                print(f"          This may indicate a tuning calibration issue.")
        return False


def test_q_behavior(cart_path):
    """VAL-04: Verify Q=0% produces flatter response than Q=100%.

    At Q=0%, resonant stages are pushed to ultrasonic frequencies (bypassed),
    so the response should be relatively flat.

    At Q=100%, stages are at audible formant frequencies with high Q,
    producing pronounced resonant peaks.
    """
    print(f"\n{'='*60}")
    print("TEST: Q Behavior (VAL-04)")
    print('='*60)

    cart = load_cartridge(cart_path)
    engine = ZPlaneEngine(cart)

    morph = 1.0  # Full morph

    # Get response at Q=0%
    engine.set_parameters(morph, 0.0)
    freqs_q0, mag_q0 = engine.get_frequency_response()
    bypass_q0 = engine.get_stage_bypass_states()
    stage_freqs_q0 = engine.get_stage_frequencies()

    print(f"\n  Q=0% Configuration:")
    print(f"    Bypassed stages: {sum(bypass_q0)}/7")
    for i, (f, b) in enumerate(zip(stage_freqs_q0, bypass_q0)):
        status = "BYPASSED" if b else f"{f:.0f} Hz"
        print(f"      Stage {i}: {status}")

    # Get response at Q=100%
    engine.set_parameters(morph, 1.0)
    freqs_q100, mag_q100 = engine.get_frequency_response()
    bypass_q100 = engine.get_stage_bypass_states()
    stage_freqs_q100 = engine.get_stage_frequencies()

    print(f"\n  Q=100% Configuration:")
    print(f"    Bypassed stages: {sum(bypass_q100)}/7")
    for i, (f, b) in enumerate(zip(stage_freqs_q100, bypass_q100)):
        status = "BYPASSED" if b else f"{f:.0f} Hz"
        print(f"      Stage {i}: {status}")

    # Calculate peak-to-valley ratio (indicator of "peakiness")
    # Measure in audible range only (100Hz - 10kHz)
    audible_mask = (freqs_q0 >= 100) & (freqs_q0 <= 10000)
    q0_audible = mag_q0[audible_mask]
    q100_audible = mag_q100[audible_mask]

    q0_range = np.max(q0_audible) - np.min(q0_audible)
    q100_range = np.max(q100_audible) - np.min(q100_audible)

    print(f"\n  Frequency Response (100Hz-10kHz):")
    print(f"    Q=0%:   Response range = {q0_range:.1f} dB")
    print(f"    Q=100%: Response range = {q100_range:.1f} dB")

    # Q=0% should have smaller range (flatter) because stages are bypassed
    if q0_range < q100_range:
        print(f"    STATUS: PASS (Q=0% is flatter, as expected with ultrasonic bypass)")
        return True
    else:
        print(f"    STATUS: FAIL (Q=0% should be flatter than Q=100%)")
        print(f"    Note: Check that ultrasonic frequencies are being bypassed correctly")
        return False


def test_morph_sweep(cart_path):
    """VAL-03: Verify morph sweep produces formant changes.

    The morph parameter should produce vowel-like formant shifts across the grid.
    """
    print(f"\n{'='*60}")
    print("TEST: Morph Sweep (VAL-03)")
    print('='*60)

    cart = load_cartridge(cart_path)
    engine = ZPlaneEngine(cart)

    q = 1.0  # Full Q for maximum formant visibility

    print(f"\n  Stage frequencies at different morph positions (Q=100%):")

    morph_positions = [0.0, 0.25, 0.5, 0.75, 1.0]
    all_freqs = []

    for morph in morph_positions:
        engine.set_parameters(morph, q)
        freqs = engine.get_stage_frequencies()
        all_freqs.append(freqs)
        print(f"    Morph={morph*100:3.0f}%: " + ", ".join(f"{f:5.0f}" for f in freqs[:4]) + " Hz ...")

    # Check that frequencies change significantly across morph
    freq_array = np.array(all_freqs)
    stage_ranges = []
    for stage in range(NUM_STAGES):
        stage_freqs = freq_array[:, stage]
        # Calculate range in semitones
        if np.min(stage_freqs) > 0:
            range_semitones = 12 * np.log2(np.max(stage_freqs) / np.min(stage_freqs))
            stage_ranges.append(range_semitones)

    avg_range = np.mean(stage_ranges) if stage_ranges else 0
    print(f"\n  Average frequency range across morph: {avg_range:.1f} semitones")

    # Morph should produce at least 6 semitones (half octave) of formant movement
    if avg_range >= 6:
        print(f"    STATUS: PASS (morph produces significant formant changes)")
        return True
    else:
        print(f"    STATUS: FAIL (morph should produce >= 6 semitones of formant change)")
        return False


def plot_frequency_responses(cart_path, output_path):
    """Generate frequency response plots for visual verification."""
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

    # Plot 4: Stage frequencies at Morph=100% for each Q
    ax = axes[1, 1]
    ax.set_title("Stage Frequencies at Morph=100%")
    bar_width = 0.25
    x = np.arange(NUM_STAGES)

    for i, q in enumerate([0.0, 0.5, 1.0]):
        engine.set_parameters(1.0, q)
        freqs = engine.get_stage_frequencies()
        bypass = engine.get_stage_bypass_states()
        # Mark bypassed stages with a different color
        colors = ['lightblue' if b else ['tab:blue', 'tab:orange', 'tab:green'][i] for b in bypass]
        bars = ax.bar(x + i*bar_width, freqs, bar_width, label=f"Q={q*100:.0f}%", alpha=0.7)
        for bar, b in zip(bars, bypass):
            if b:
                bar.set_hatch('///')

    ax.set_xlabel("Stage")
    ax.set_ylabel("Frequency (Hz)")
    ax.set_yscale('log')
    ax.set_xticks(x + bar_width)
    ax.set_xticklabels([f"S{i}" for i in range(NUM_STAGES)])
    ax.legend()
    ax.grid(True, axis='y')
    ax.axhline(y=20000, color='red', linestyle='--', label='20kHz (ultrasonic)')

    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    print(f"Saved: {output_path}")


def print_cartridge_info(cart):
    """Print detailed cartridge information for debugging."""
    print(f"\nCartridge Information:")
    print(f"  Name: {cart.name}")
    print(f"  Loaded: {cart.is_loaded}")

    print(f"\n  Sample data at Morph=0%, Transform=0%:")
    for vi in range(NUM_VARIANTS):
        q_label = vi * 50
        print(f"    Variant {vi} (Q={q_label}%):")
        for si in range(NUM_STAGES):
            cell = cart.data[vi][si][0]  # Grid index 0
            freq_hz = semitone_to_hz(cell.freq_semitone)
            ultrasonic = "ULTRA" if freq_hz > 20000 else ""
            print(f"      Stage {si}: {freq_hz:8.1f} Hz ({cell.freq_semitone:+6.1f} st), "
                  f"r={cell.radius:.4f}, gain={cell.gain_db:+5.1f} dB, "
                  f"shape={'LP' if cell.shape == 0 else 'EQ'} {ultrasonic}")

    print(f"\n  Sample data at Morph=100%, Transform=0%:")
    for vi in range(NUM_VARIANTS):
        q_label = vi * 50
        print(f"    Variant {vi} (Q={q_label}%):")
        for si in range(NUM_STAGES):
            cell = cart.data[vi][si][16]  # Grid index 16 (col=16, row=0)
            freq_hz = semitone_to_hz(cell.freq_semitone)
            ultrasonic = "ULTRA" if freq_hz > 20000 else ""
            print(f"      Stage {si}: {freq_hz:8.1f} Hz ({cell.freq_semitone:+6.1f} st), "
                  f"r={cell.radius:.4f}, gain={cell.gain_db:+5.1f} dB, "
                  f"shape={'LP' if cell.shape == 0 else 'EQ'} {ultrasonic}")


# =============================================================================
# Main Entry Point
# =============================================================================

def main():
    """Main validation entry point."""
    print("="*60)
    print("Z-Plane DSP Engine Validation")
    print("Testing against EmulatorX3 reference captures")
    print("="*60)

    # Find paths
    script_dir = Path(__file__).parent
    base_path = script_dir.parent  # Project root
    cart_path = base_path / "talking_hedz_extracted.json"

    if not cart_path.exists():
        print(f"ERROR: Cartridge not found: {cart_path}")
        return 1

    print(f"\nCartridge: {cart_path}")

    # Load and print cartridge info
    cart = load_cartridge(cart_path)
    print_cartridge_info(cart)

    results = []

    # VAL-01: Reference match (m100q0)
    r = test_reference_comparison(cart_path, base_path, "hedz - m100q0.wav", 1.0, 0.0)
    if r is not None:
        results.append(("VAL-01", r))

    # VAL-02: Reference match (5050)
    r = test_reference_comparison(cart_path, base_path, "hedz - 5050.wav", 0.5, 0.5)
    if r is not None:
        results.append(("VAL-02", r))

    # VAL-03: Morph sweep produces formant changes
    r = test_morph_sweep(cart_path)
    results.append(("VAL-03", r))

    # VAL-04: Q behavior
    r = test_q_behavior(cart_path)
    results.append(("VAL-04", r))

    # Generate plots (visual verification)
    print(f"\n{'='*60}")
    print("Generating frequency response plots...")
    print('='*60)
    plot_path = base_path / "validation_plots.png"
    plot_frequency_responses(cart_path, plot_path)

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
        print("\n  OVERALL: FAILURE - Review failed tests above")
        print("  Note: If VAL-01/VAL-02 fail with formant offset, this may indicate")
        print("        a tuning calibration issue (reference C5 = 523.25 Hz = MIDI 72)")
        return 1


if __name__ == "__main__":
    exit(main())
