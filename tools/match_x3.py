#!/usr/bin/env python3
"""
TRENCH X3 Matching Script

Iteratively adjust filter parameters to match X3 reference recordings.
Compares spectrum of our output to X3 captures.
"""

import numpy as np
from scipy.io import wavfile
from scipy.signal import lfilter
from scipy.fft import rfft, rfftfreq
import matplotlib.pyplot as plt
import os

# =============================================================================
# CAPTURED COEFFICIENTS FROM X3 (Cheat Engine)
# Format: a1_polar (stored as -2*r*cos(theta)), radius, flag
# =============================================================================

CAPTURES = {
    "M0_Q100": [
        {"a1": -1.976510, "r": 0.998242, "flag": 1},
        {"a1": -1.938977, "r": 0.998296, "flag": 1},
        {"a1": -1.872895, "r": 0.998353, "flag": 1},
        {"a1": -1.523842, "r": 0.992409, "flag": 1},
        {"a1": -1.997572, "r": 0.998289, "flag": 0},
    ],
    "M100_Q100": [
        {"a1": -1.996743, "r": 0.998619, "flag": 1},
        {"a1": -1.894098, "r": 0.998437, "flag": 1},
        {"a1": -1.854829, "r": 0.998353, "flag": 1},
        {"a1": -1.495171, "r": 0.963737, "flag": 1},
        {"a1": -1.974292, "r": 0.998195, "flag": 0},
    ],
    "M100_Q0": [
        {"a1": -1.986418, "r": 0.987503, "flag": 1},
        {"a1": -1.837391, "r": 0.974537, "flag": 1},
        {"a1": -1.794609, "r": 0.977806, "flag": 1},
        {"a1": -1.362762, "r": 0.883514, "flag": 1},
        {"a1": -1.914935, "r": 0.993960, "flag": 0},
    ],
}

REFERENCE_FILES = {
    "M0_Q100": "validation/hedzmorph0q100.wav",
    "M100_Q100": "validation/hedzmorph100q100.wav",
    "M100_Q0": "validation/hedzmorph100q0.wav",
}


def load_wav(path):
    """Load WAV file, convert to float mono."""
    sr, data = wavfile.read(path)
    if data.dtype == np.int16:
        data = data.astype(np.float64) / 32768.0
    elif data.dtype == np.int32:
        data = data.astype(np.float64) / 2147483648.0
    if len(data.shape) > 1:
        data = data[:, 0]
    return data, sr


def polar_to_freq(a1, r, sr=44100):
    """Convert polar coefficients to frequency."""
    cos_theta = -a1 / (2.0 * r)
    cos_theta = np.clip(cos_theta, -1.0, 1.0)
    theta = np.arccos(cos_theta)
    return theta * sr / (2.0 * np.pi)


# =============================================================================
# FILTER IMPLEMENTATIONS - Try different approaches
# =============================================================================

def make_resonator_v1(a1, r, sr):
    """
    Version 1: Direct bandpass (zeros at DC and Nyquist)
    H(z) = scale * (1 - z^-2) / (1 + a1*z^-1 + a2*z^-2)
    """
    a1_final = a1 * r
    a2 = r * r
    scale = (1.0 - a2) * 0.5
    b = [scale, 0.0, -scale]
    a = [1.0, a1_final, a2]
    return b, a


def make_resonator_v2(a1, r, sr, gain_db=12.0):
    """
    Version 2: Peaking EQ at pole frequency
    Uses RBJ cookbook formula
    """
    freq = polar_to_freq(a1, r, sr)
    freq = np.clip(freq, 20, sr * 0.49)

    # Q from radius
    Q = 1.0 / (2.0 * (1.0 - r))
    Q = np.clip(Q, 0.5, 100.0)

    A = 10.0 ** (gain_db / 40.0)
    w0 = 2.0 * np.pi * freq / sr
    alpha = np.sin(w0) / (2.0 * Q)

    b0 = 1.0 + alpha * A
    b1 = -2.0 * np.cos(w0)
    b2 = 1.0 - alpha * A
    a0 = 1.0 + alpha / A
    a1_coef = -2.0 * np.cos(w0)
    a2 = 1.0 - alpha / A

    b = [b0/a0, b1/a0, b2/a0]
    a = [1.0, a1_coef/a0, a2/a0]
    return b, a


def make_resonator_v3(a1, r, sr):
    """
    Version 3: All-pole (just denominator, unity numerator)
    H(z) = gain / (1 + a1*z^-1 + a2*z^-2)
    """
    a1_final = a1 * r
    a2 = r * r
    # Normalize for unity DC gain
    dc_gain = 1.0 / (1.0 + a1_final + a2)
    b = [dc_gain, 0.0, 0.0]
    a = [1.0, a1_final, a2]
    return b, a


def make_resonator_v4(a1, r, sr):
    """
    Version 4: Constant peak gain resonator
    Peak gain = 1, bandwidth controlled by r
    """
    a1_final = a1 * r
    a2 = r * r
    # Peak gain normalization
    # At resonance, |H(e^jw)| should be constant
    # For bandpass: peak_gain = (1-r^2) / (1-r)^2 ???
    # Simpler: just use (1-r) as the scale
    scale = 1.0 - r
    b = [scale, 0.0, -scale]
    a = [1.0, a1_final, a2]
    return b, a


def make_lowpass(a1, r, sr):
    """Lowpass biquad."""
    a1_final = a1 * r
    a2 = r * r
    # Unity DC gain
    norm = (1.0 + a1_final + a2) / 4.0
    b = [norm, 2*norm, norm]
    a = [1.0, a1_final, a2]
    return b, a


def process_filter(signal, stages, sr, resonator_fn, lp_cutoff_override=None):
    """Process signal through filter stages."""
    x = signal.copy()

    for stage in stages:
        if stage["flag"] == 1:
            b, a = resonator_fn(stage["a1"], stage["r"], sr)
        else:
            if lp_cutoff_override:
                # Override lowpass with fixed cutoff
                w0 = 2.0 * np.pi * lp_cutoff_override / sr
                Q = 0.707
                alpha = np.sin(w0) / (2.0 * Q)
                b0 = (1.0 - np.cos(w0)) / 2.0
                b1 = 1.0 - np.cos(w0)
                b2 = (1.0 - np.cos(w0)) / 2.0
                a0 = 1.0 + alpha
                a1 = -2.0 * np.cos(w0)
                a2 = 1.0 - alpha
                b = [b0/a0, b1/a0, b2/a0]
                a = [1.0, a1/a0, a2/a0]
            else:
                b, a = make_lowpass(stage["a1"], stage["r"], sr)
        x = lfilter(b, a, x)

    return x


def compute_spectrum(signal, sr, nfft=8192):
    """Compute magnitude spectrum."""
    spectrum = np.abs(rfft(signal, n=nfft))
    freqs = rfftfreq(nfft, 1/sr)
    # Convert to dB
    spectrum_db = 20 * np.log10(spectrum + 1e-10)
    return freqs, spectrum_db


def compare_spectra(ref_spectrum, our_spectrum, freqs, freq_range=(50, 6000)):
    """Compare two spectra, return RMS error in dB."""
    mask = (freqs >= freq_range[0]) & (freqs <= freq_range[1])
    ref = ref_spectrum[mask]
    our = our_spectrum[mask]

    # Normalize both to same RMS
    ref_rms = np.sqrt(np.mean(ref**2))
    our_rms = np.sqrt(np.mean(our**2))
    our_normalized = our * (ref_rms / our_rms) if our_rms > 0 else our

    error = ref - our_normalized
    rms_error = np.sqrt(np.mean(error**2))

    return rms_error, error


def main():
    # Load pink noise input
    pink_path = "validation/bypassed-pinknoise.wav"
    if not os.path.exists(pink_path):
        print(f"ERROR: {pink_path} not found")
        return

    pink, sr = load_wav(pink_path)
    print(f"Loaded pink noise: {len(pink)} samples, {sr} Hz")

    # Test each capture position
    test_cases = ["M0_Q100", "M100_Q100"]

    # Different resonator implementations to try
    resonator_versions = [
        ("v1_bandpass", make_resonator_v1),
        ("v2_peaking", lambda a1, r, sr: make_resonator_v2(a1, r, sr, gain_db=12.0)),
        ("v2_peaking_6dB", lambda a1, r, sr: make_resonator_v2(a1, r, sr, gain_db=6.0)),
        ("v2_peaking_18dB", lambda a1, r, sr: make_resonator_v2(a1, r, sr, gain_db=18.0)),
        ("v3_allpole", make_resonator_v3),
        ("v4_constpeak", make_resonator_v4),
    ]

    results = []

    for case in test_cases:
        print(f"\n{'='*60}")
        print(f"Testing: {case}")
        print(f"{'='*60}")

        # Load reference
        ref_path = REFERENCE_FILES[case]
        if not os.path.exists(ref_path):
            print(f"  Reference not found: {ref_path}")
            continue

        ref_audio, _ = load_wav(ref_path)
        ref_freqs, ref_spectrum = compute_spectrum(ref_audio, sr)

        stages = CAPTURES[case]

        # Print stage frequencies
        print("\nStage frequencies:")
        for i, s in enumerate(stages):
            freq = polar_to_freq(s["a1"], s["r"], sr)
            stype = "Resonator" if s["flag"] == 1 else "Lowpass"
            print(f"  {i}: {freq:.1f} Hz ({stype})")

        print("\nTesting resonator implementations:")

        for name, resonator_fn in resonator_versions:
            # Try with LP bypass (20kHz)
            output = process_filter(pink, stages, sr, resonator_fn, lp_cutoff_override=20000)

            if np.any(np.isnan(output)) or np.any(np.isinf(output)):
                print(f"  {name}: UNSTABLE (NaN/Inf)")
                continue

            _, our_spectrum = compute_spectrum(output, sr)
            rms_error, _ = compare_spectra(ref_spectrum, our_spectrum, ref_freqs)

            print(f"  {name}: RMS error = {rms_error:.2f} dB")
            results.append((case, name, rms_error))

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY - Best implementations by RMS error")
    print(f"{'='*60}")

    results.sort(key=lambda x: x[2])
    for case, name, error in results[:10]:
        print(f"  {case} + {name}: {error:.2f} dB")

    # Plot comparison for best result
    if results:
        best_case, best_impl, _ = results[0]

        print(f"\nGenerating comparison plot for: {best_case} + {best_impl}")

        ref_audio, _ = load_wav(REFERENCE_FILES[best_case])
        ref_freqs, ref_spectrum = compute_spectrum(ref_audio, sr)

        # Find the resonator function
        for name, fn in resonator_versions:
            if name == best_impl:
                output = process_filter(pink, CAPTURES[best_case], sr, fn, lp_cutoff_override=20000)
                break

        _, our_spectrum = compute_spectrum(output, sr)

        # Normalize
        mask = (ref_freqs >= 50) & (ref_freqs <= 6000)
        ref_rms = np.sqrt(np.mean(ref_spectrum[mask]**2))
        our_rms = np.sqrt(np.mean(our_spectrum[mask]**2))
        our_spectrum_norm = our_spectrum + (ref_rms - our_rms)

        plt.figure(figsize=(12, 6))
        plt.semilogx(ref_freqs, ref_spectrum, label='X3 Reference', alpha=0.8)
        plt.semilogx(ref_freqs, our_spectrum_norm, label=f'TRENCH ({best_impl})', alpha=0.8)
        plt.xlim(50, 8000)
        plt.ylim(-60, 80)
        plt.xlabel('Frequency (Hz)')
        plt.ylabel('Magnitude (dB)')
        plt.title(f'{best_case} Spectrum Comparison')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.savefig('validation/spectrum_comparison.png', dpi=150)
        print("Saved: validation/spectrum_comparison.png")

        # Save our output
        output_norm = output / (np.max(np.abs(output)) + 1e-10) * 0.9
        wavfile.write(f'validation/trench_{best_case.lower()}.wav', sr,
                      (output_norm * 32767).astype(np.int16))
        print(f"Saved: validation/trench_{best_case.lower()}.wav")


if __name__ == "__main__":
    main()
