#!/usr/bin/env python3
"""
TRENCH Validation Harness (Phase 0)

Compares DSP output against X3 reference recordings.

Usage:
    python validate_audio.py [--config CONFIG] [--output OUTPUT_DIR]

Reports:
    - Mean spectral error (100-8000 Hz)
    - Max spectral error (100-8000 Hz)
    - RMS delta (dB)
    - Writes output WAV for inspection
"""

import numpy as np
import soundfile as sf
import argparse
import os
from dataclasses import dataclass
from typing import List, Tuple, Optional
import json


# =============================================================================
# BIQUAD DSP (Direct Form II Transposed)
# =============================================================================

@dataclass
class BiquadCoeffs:
    """Biquad coefficients in patent form: H(z) = c0*(1+c1*z^-1+c2*z^-2)/(1+a1*z^-1+a2*z^-2)"""
    c0: float = 1.0
    c1: float = 0.0
    c2: float = 0.0
    a1: float = 0.0
    a2: float = 0.0

    def to_direct(self) -> Tuple[float, float, float, float, float]:
        """Convert to direct form: b0, b1, b2, a1, a2"""
        return (self.c0, self.c0 * self.c1, self.c0 * self.c2, self.a1, self.a2)


class BiquadState:
    """Per-channel biquad state"""
    def __init__(self):
        self.z1 = 0.0
        self.z2 = 0.0

    def reset(self):
        self.z1 = 0.0
        self.z2 = 0.0


def process_biquad(x: float, coeffs: BiquadCoeffs, state: BiquadState) -> float:
    """Process single sample through biquad (Direct Form II Transposed)"""
    b0, b1, b2, a1, a2 = coeffs.to_direct()

    y = b0 * x + state.z1
    state.z1 = b1 * x - a1 * y + state.z2
    state.z2 = b2 * x - a2 * y

    return y


def saturate_emu(x: float) -> float:
    """E-mu H-chip style saturation"""
    if x > 4.0:
        x = 4.0 + np.tanh(x - 4.0)
    elif x < -4.0:
        x = -4.0 + np.tanh(x + 4.0)
    return np.clip(x, -100.0, 100.0)


def process_cascade(samples: np.ndarray, coeffs_list: List[BiquadCoeffs],
                    use_saturation: bool = True) -> np.ndarray:
    """Process audio through cascade of biquads"""
    output = np.zeros_like(samples)
    states = [BiquadState() for _ in coeffs_list]

    for i, x in enumerate(samples):
        y = float(x)
        for stage_idx, (coeffs, state) in enumerate(zip(coeffs_list, states)):
            y = process_biquad(y, coeffs, state)
            if use_saturation:
                y = saturate_emu(y)
        output[i] = y

    return output


# =============================================================================
# COEFFICIENT GENERATION (Patent Form)
# =============================================================================

@dataclass
class StageCapture:
    """Captured stage data from X3"""
    a1: float
    radius: float
    flag: int

    @property
    def a2(self) -> float:
        return self.radius * self.radius

    @property
    def freq_hz(self) -> float:
        """Derive frequency from a1 and radius (at 44100 Hz)"""
        cos_theta = -self.a1 / (2.0 * self.radius) if self.radius > 0 else 0
        cos_theta = np.clip(cos_theta, -1.0, 1.0)
        theta = np.arccos(cos_theta)
        return theta * 44100.0 / (2.0 * np.pi)

    @property
    def Q(self) -> float:
        """Derive Q from radius"""
        if self.radius >= 1.0:
            return 1000.0
        return self.radius / (2.0 * (1.0 - self.radius))


# Zero topology modes for experimentation
ZERO_MODE = 'allpole'  # Options: 'allpole', 'bandpass', 'matched', 'parametric', 'constpeak', 'widepole'
Q_SCALE = 1.0  # Multiply Q by this factor (< 1 widens bandwidth)


def make_peaking_coeffs(stage: StageCapture, gain_db: float = 12.0) -> BiquadCoeffs:
    """
    Create flag=1 stage coefficients.

    Supports multiple zero topologies for experimentation:
    - allpole: No zeros, DC normalized. H = (1+a1+a2) / D(z)
    - bandpass: Zeros at DC and Nyquist. H = k*(1-z^-2) / D(z)
    - matched: Zeros at same angle, reduced radius. H = k*N(z) / D(z)
    - parametric: RBJ cookbook peaking EQ
    """
    r = min(stage.radius, 0.9999)
    a1 = stage.a1
    a2 = r * r

    # Edge case: near-DC pole (identity)
    cos_w = -a1 / (2.0 * r) if r > 0 else 1.0
    if cos_w > 0.9999 or cos_w < -0.9999:
        return BiquadCoeffs(c0=1.0, c1=0.0, c2=0.0, a1=0.0, a2=0.0)

    cos_w = np.clip(cos_w, -1.0, 1.0)
    sin_w = np.sqrt(1.0 - cos_w * cos_w)

    if ZERO_MODE == 'allpole':
        # All-pole: DC normalized
        dc_norm = 1.0 + a1 + a2
        if abs(dc_norm) < 0.001:
            return BiquadCoeffs(c0=1.0, c1=0.0, c2=0.0, a1=0.0, a2=0.0)
        return BiquadCoeffs(c0=dc_norm, c1=0.0, c2=0.0, a1=a1, a2=a2)

    elif ZERO_MODE == 'bandpass':
        # Bandpass: zeros at DC and Nyquist
        # H = scale * (1 - z^-2) / D(z)
        # Normalize so peak gain = 1
        scale = (1.0 - a2) * 0.5
        return BiquadCoeffs(c0=scale, c1=0.0, c2=-1.0, a1=a1, a2=a2)

    elif ZERO_MODE == 'matched':
        # Matched zeros: same angle as poles, radius = r^2 (squared)
        # This creates a gentler peak than all-pole
        r_z = r * r  # Zero radius = pole radius squared
        c1 = -2.0 * r_z * cos_w
        c2 = r_z * r_z
        # Normalize for unity DC
        num_dc = 1.0 + c1 + c2
        den_dc = 1.0 + a1 + a2
        c0 = den_dc / num_dc if abs(num_dc) > 0.001 else 1.0
        return BiquadCoeffs(c0=c0, c1=c1, c2=c2, a1=a1, a2=a2)

    elif ZERO_MODE == 'parametric':
        # RBJ cookbook peaking EQ
        Q = stage.Q
        if Q < 0.1:
            Q = 0.1
        A = 10.0 ** (gain_db / 40.0)
        alpha = sin_w / (2.0 * Q)

        b0 = 1.0 + alpha * A
        b1 = -2.0 * cos_w
        b2 = 1.0 - alpha * A
        a0 = 1.0 + alpha / A
        a1_out = -2.0 * cos_w
        a2_out = 1.0 - alpha / A

        # Normalize
        b0 /= a0; b1 /= a0; b2 /= a0
        a1_out /= a0; a2_out /= a0

        c0 = b0
        c1 = b1 / b0 if abs(b0) > 1e-10 else 0.0
        c2 = b2 / b0 if abs(b0) > 1e-10 else 0.0
        return BiquadCoeffs(c0=c0, c1=c1, c2=c2, a1=a1_out, a2=a2_out)

    elif ZERO_MODE == 'constpeak':
        # Constant peak height resonator
        # Peak gain = gain_db regardless of Q
        # c0 = G * (1-r) where G = 10^(gain_db/20)
        # This gives peak = c0 / (1-r) = G
        G = 10.0 ** (gain_db / 20.0)
        c0 = G * (1.0 - r)
        return BiquadCoeffs(c0=c0, c1=0.0, c2=0.0, a1=a1, a2=a2)

    elif ZERO_MODE == 'widepole':
        # Widened all-pole: reduce radius to widen bandwidth
        # Keep same pole angle (frequency), reduce r by Q_SCALE
        # New r' creates wider peak with lower height
        r_new = 1.0 - (1.0 - r) / Q_SCALE  # Q_SCALE < 1 makes r smaller (wider)
        r_new = max(0.5, min(r_new, 0.999))

        # Recalculate a1 for new radius (same angle)
        a1_new = -2.0 * r_new * cos_w
        a2_new = r_new * r_new

        # DC normalize
        dc_norm = 1.0 + a1_new + a2_new
        if dc_norm < 0.01:
            return BiquadCoeffs(c0=1.0, c1=0.0, c2=0.0, a1=0.0, a2=0.0)

        return BiquadCoeffs(c0=dc_norm, c1=0.0, c2=0.0, a1=a1_new, a2=a2_new)

    else:
        # Default: all-pole
        dc_norm = 1.0 + a1 + a2
        return BiquadCoeffs(c0=dc_norm, c1=0.0, c2=0.0, a1=a1, a2=a2)


def make_lowpass_coeffs(stage: StageCapture) -> BiquadCoeffs:
    """
    Create flag=0 stage coefficients.

    UNKNOWN: Testing DC-normalized all-pole (same as flag=1).
    Near-DC poles or unstable configurations treated as bypass.
    If widepole mode, apply same Q scaling.
    """
    r = min(stage.radius, 0.9999)
    a1 = stage.a1
    a2 = r * r

    # Derive cos_w for edge case detection
    cos_w = -a1 / (2.0 * r) if r > 0 else 1.0

    # Edge case: near-DC pole - treat as bypass
    if cos_w > 0.9999 or cos_w < -0.9999:
        return BiquadCoeffs(c0=1.0, c1=0.0, c2=0.0, a1=0.0, a2=0.0)

    cos_w = np.clip(cos_w, -1.0, 1.0)

    if ZERO_MODE == 'widepole' and Q_SCALE != 1.0:
        # Apply same widening as flag=1 stages
        r_new = 1.0 - (1.0 - r) / Q_SCALE
        r_new = max(0.5, min(r_new, 0.999))
        a1 = -2.0 * r_new * cos_w
        a2 = r_new * r_new

    # DC normalization factor
    dc_norm = 1.0 + a1 + a2

    if dc_norm < 0.01:
        return BiquadCoeffs(c0=1.0, c1=0.0, c2=0.0, a1=0.0, a2=0.0)

    return BiquadCoeffs(c0=dc_norm, c1=0.0, c2=0.0, a1=a1, a2=a2)


def make_coeffs_from_capture(stage: StageCapture, gain_db: float = 12.0) -> BiquadCoeffs:
    """Generate coefficients based on flag"""
    if stage.flag == 1:
        return make_peaking_coeffs(stage, gain_db)
    else:
        return make_lowpass_coeffs(stage)


# =============================================================================
# CAPTURED PRESETS (from CLAUDE.md)
# =============================================================================

# M0_Q100 - Morph 0%, Q 100%
M0_Q100_STAGES = [
    StageCapture(a1=-1.974805, radius=0.998231, flag=1),  # S0: 1035 Hz
    StageCapture(a1=-1.939721, radius=0.998292, flag=1),  # S1: 1679 Hz
    StageCapture(a1=-1.873399, radius=0.998353, flag=1),  # S2: 2480 Hz
    StageCapture(a1=-1.524112, radius=0.992679, flag=1),  # S3: 4882 Hz
    StageCapture(a1=-1.997652, radius=0.998292, flag=0),  # S4: ~DC
]

# M100_Q100 - Morph 100%, Q 100%
M100_Q100_STAGES = [
    StageCapture(a1=-1.997743, radius=0.998719, flag=1),  # S0: ~0 Hz
    StageCapture(a1=-1.881333, radius=0.998475, flag=1),  # S1: 2400 Hz
    StageCapture(a1=-1.850007, radius=0.998353, flag=1),  # S2: 2707 Hz
    StageCapture(a1=-1.476768, radius=0.945335, flag=1),  # S3: 4733 Hz
    StageCapture(a1=-1.939599, radius=0.998170, flag=0),  # S4: 1677 Hz
]


# =============================================================================
# AUDIO I/O
# =============================================================================

def load_wav(path: str) -> Tuple[np.ndarray, int]:
    """Load WAV file, return (samples as float32 -1..1, sample_rate)"""
    samples, sample_rate = sf.read(path, dtype='float32')

    # Convert stereo to mono if needed
    if len(samples.shape) > 1:
        samples = samples.mean(axis=1)

    return samples, sample_rate


def save_wav(path: str, samples: np.ndarray, sample_rate: int = 44100):
    """Save float32 samples as 32-bit float WAV"""
    sf.write(path, samples.astype(np.float32), sample_rate, subtype='FLOAT')


# =============================================================================
# ANALYSIS
# =============================================================================

def compute_rms_db(samples: np.ndarray) -> float:
    """Compute RMS in dB"""
    rms = np.sqrt(np.mean(samples ** 2))
    if rms < 1e-10:
        return -200.0
    return 20.0 * np.log10(rms)


def compute_spectrum_db(samples: np.ndarray, sample_rate: int,
                        fft_size: int = 8192) -> Tuple[np.ndarray, np.ndarray]:
    """Compute magnitude spectrum in dB, returns (freqs, magnitude_db)"""
    # Window and FFT
    n = min(len(samples), fft_size)
    windowed = samples[:n] * np.hanning(n)

    spectrum = np.fft.rfft(windowed, n=fft_size)
    magnitude = np.abs(spectrum)

    # Convert to dB
    magnitude_db = 20.0 * np.log10(magnitude + 1e-10)

    # Frequency bins
    freqs = np.fft.rfftfreq(fft_size, 1.0 / sample_rate)

    return freqs, magnitude_db


def compute_spectral_error(test_samples: np.ndarray, ref_samples: np.ndarray,
                           sample_rate: int, freq_lo: float = 100.0,
                           freq_hi: float = 8000.0) -> Tuple[float, float, np.ndarray, np.ndarray]:
    """
    Compute spectral error between test and reference.

    Returns: (mean_error_db, max_error_db, freqs, error_db)
    """
    # Use same length
    n = min(len(test_samples), len(ref_samples))

    freqs_t, spec_t = compute_spectrum_db(test_samples[:n], sample_rate)
    freqs_r, spec_r = compute_spectrum_db(ref_samples[:n], sample_rate)

    # Find frequency range indices
    mask = (freqs_t >= freq_lo) & (freqs_t <= freq_hi)

    # Compute error in the range
    error_db = np.abs(spec_t - spec_r)
    error_in_range = error_db[mask]

    mean_error = np.mean(error_in_range)
    max_error = np.max(error_in_range)

    return mean_error, max_error, freqs_t, error_db


def analyze_comparison(test_path: str, ref_path: str,
                       freq_lo: float = 100.0, freq_hi: float = 8000.0) -> dict:
    """
    Full comparison analysis between test and reference WAV files.
    """
    test_samples, test_sr = load_wav(test_path)
    ref_samples, ref_sr = load_wav(ref_path)

    if test_sr != ref_sr:
        raise ValueError(f"Sample rate mismatch: {test_sr} vs {ref_sr}")

    # RMS
    test_rms = compute_rms_db(test_samples)
    ref_rms = compute_rms_db(ref_samples)
    rms_delta = test_rms - ref_rms

    # Spectral error
    mean_err, max_err, freqs, error = compute_spectral_error(
        test_samples, ref_samples, test_sr, freq_lo, freq_hi
    )

    return {
        'test_rms_db': test_rms,
        'ref_rms_db': ref_rms,
        'rms_delta_db': rms_delta,
        'mean_spectral_error_db': mean_err,
        'max_spectral_error_db': max_err,
        'sample_rate': test_sr,
        'test_length': len(test_samples),
        'ref_length': len(ref_samples),
    }


# =============================================================================
# MAIN VALIDATION WORKFLOW
# =============================================================================

def run_validation(dry_path: str, ref_path: str, output_path: str,
                   stages: List[StageCapture], gain_db: float = 12.0,
                   use_saturation: bool = True, global_gain_db: float = 0.0) -> dict:
    """
    Run full validation:
    1. Load dry audio
    2. Process through DSP cascade
    3. Compare to reference
    4. Save output
    5. Return metrics
    """
    # Load dry input
    dry_samples, sample_rate = load_wav(dry_path)
    print(f"Loaded dry: {len(dry_samples)} samples @ {sample_rate} Hz")
    print(f"Dry RMS: {compute_rms_db(dry_samples):.1f} dB")

    # Generate coefficients
    coeffs_list = [make_coeffs_from_capture(s, gain_db) for s in stages]

    # Print stage info
    print("\nStage Configuration:")
    for i, (stage, coeffs) in enumerate(zip(stages, coeffs_list)):
        print(f"  S{i}: freq={stage.freq_hz:.0f}Hz Q={stage.Q:.1f} flag={stage.flag}")
        print(f"       c0={coeffs.c0:.6f} c1={coeffs.c1:.6f} c2={coeffs.c2:.6f}")
        print(f"       a1={coeffs.a1:.6f} a2={coeffs.a2:.6f}")

    # Process
    print("\nProcessing...")
    output_samples = process_cascade(dry_samples, coeffs_list, use_saturation)

    # Apply global gain adjustment
    if global_gain_db != 0.0:
        global_gain = 10.0 ** (global_gain_db / 20.0)
        output_samples = output_samples * global_gain
        print(f"Applied global gain: {global_gain_db:+.1f} dB")

    output_rms = compute_rms_db(output_samples)
    print(f"Output RMS: {output_rms:.1f} dB")

    # Save output
    save_wav(output_path, output_samples, sample_rate)
    print(f"Saved: {output_path}")

    # Compare to reference
    print("\nComparing to reference...")
    result = analyze_comparison(output_path, ref_path)

    # Save spectral comparison data
    ref_samples, ref_sr = load_wav(ref_path)
    n = min(len(output_samples), len(ref_samples))
    freqs, out_spec = compute_spectrum_db(output_samples[:n], sample_rate)
    _, ref_spec = compute_spectrum_db(ref_samples[:n], sample_rate)

    # Save to CSV for analysis
    spec_path = output_path.replace('.wav', '_spectrum.csv')
    with open(spec_path, 'w') as f:
        f.write("freq_hz,output_db,ref_db,error_db\n")
        for i, freq in enumerate(freqs):
            if 20 <= freq <= 20000:
                f.write(f"{freq:.1f},{out_spec[i]:.2f},{ref_spec[i]:.2f},{abs(out_spec[i]-ref_spec[i]):.2f}\n")
    print(f"Spectrum saved: {spec_path}")

    print(f"\n{'='*50}")
    print(f"VALIDATION RESULT")
    print(f"{'='*50}")
    print(f"Reference RMS:        {result['ref_rms_db']:.1f} dB")
    print(f"Output RMS:           {result['test_rms_db']:.1f} dB")
    print(f"RMS Delta:            {result['rms_delta_db']:+.1f} dB")
    print(f"Mean Spectral Error:  {result['mean_spectral_error_db']:.1f} dB (100-8000 Hz)")
    print(f"Max Spectral Error:   {result['max_spectral_error_db']:.1f} dB")
    print(f"{'='*50}")

    # Pass/Fail
    passed = result['mean_spectral_error_db'] < 3.0 and abs(result['rms_delta_db']) < 1.0
    print(f"PASS: {passed}")

    return result


def main():
    parser = argparse.ArgumentParser(description='TRENCH Audio Validation Harness')
    parser.add_argument('--validation-dir', default='validation',
                        help='Directory containing validation WAVs')
    parser.add_argument('--output-dir', default='validation/output',
                        help='Directory for output WAVs')
    parser.add_argument('--gain-db', type=float, default=12.0,
                        help='Peaking gain in dB (baseline: 12)')
    parser.add_argument('--global-gain-db', type=float, default=0.0,
                        help='Global output gain adjustment in dB')
    parser.add_argument('--no-saturation', action='store_true',
                        help='Disable E-mu saturation')
    parser.add_argument('--test', choices=['m0q100', 'm100q100', 'both'], default='both',
                        help='Which test to run')
    parser.add_argument('--zero-mode', choices=['allpole', 'bandpass', 'matched', 'parametric', 'constpeak', 'widepole'],
                        default='allpole', help='Zero topology mode')
    parser.add_argument('--q-scale', type=float, default=1.0,
                        help='Q scaling factor for widepole mode (< 1 widens bandwidth)')

    args = parser.parse_args()

    # Set global zero mode and Q scale
    global ZERO_MODE, Q_SCALE
    ZERO_MODE = args.zero_mode
    Q_SCALE = args.q_scale
    print(f"Zero topology mode: {ZERO_MODE}")
    if ZERO_MODE == 'widepole':
        print(f"Q scale: {Q_SCALE}")

    # Resolve paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(script_dir)

    val_dir = os.path.join(project_dir, args.validation_dir)
    out_dir = os.path.join(project_dir, args.output_dir)
    os.makedirs(out_dir, exist_ok=True)

    dry_path = os.path.join(val_dir, 'bypassed-pinknoise.wav')

    results = {}

    if args.test in ['m0q100', 'both']:
        print("\n" + "="*60)
        print("TEST: M0_Q100 (Morph 0%, Q 100%)")
        print("="*60)

        ref_path = os.path.join(val_dir, 'hedzmorph0q100.wav')
        out_path = os.path.join(out_dir, 'test_m0q100.wav')

        results['m0q100'] = run_validation(
            dry_path, ref_path, out_path,
            M0_Q100_STAGES, args.gain_db,
            not args.no_saturation, args.global_gain_db
        )

    if args.test in ['m100q100', 'both']:
        print("\n" + "="*60)
        print("TEST: M100_Q100 (Morph 100%, Q 100%)")
        print("="*60)

        ref_path = os.path.join(val_dir, 'hedzmorph100q100.wav')
        out_path = os.path.join(out_dir, 'test_m100q100.wav')

        results['m100q100'] = run_validation(
            dry_path, ref_path, out_path,
            M100_Q100_STAGES, args.gain_db,
            not args.no_saturation, args.global_gain_db
        )

    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    for name, r in results.items():
        status = "PASS" if r['mean_spectral_error_db'] < 3.0 and abs(r['rms_delta_db']) < 1.0 else "FAIL"
        print(f"{name}: Mean={r['mean_spectral_error_db']:.1f}dB RMS_delta={r['rms_delta_db']:+.1f}dB [{status}]")

    # Save results as JSON
    results_path = os.path.join(out_dir, 'validation_results.json')
    with open(results_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to: {results_path}")


if __name__ == '__main__':
    main()
