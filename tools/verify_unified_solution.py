#!/usr/bin/env python3
"""
Verify the unified gains + compensation solution matches X3.

This tests the exact implementation now in C++:
- Unified gains: [31.87, 30.91, 33.11, 30.54]
- Interpolated offsets
- Linear compensation: comp_dB = 9.43 - 9.70 * morph
"""

import numpy as np
from scipy.io import wavfile
from scipy.signal import lfilter
from scipy.fft import rfft, rfftfreq
import warnings
import os

warnings.filterwarnings('ignore', category=wavfile.WavFileWarning)

SR = 44100

M0_Q100_STAGES = [
    {"a1": -1.974805, "r": 0.998231, "flag": 1.0},
    {"a1": -1.939721, "r": 0.998292, "flag": 1.0},
    {"a1": -1.873399, "r": 0.998353, "flag": 1.0},
    {"a1": -1.524112, "r": 0.992679, "flag": 1.0},
    {"a1": -1.997652, "r": 0.998292, "flag": 0.0},
]

M100_Q100_STAGES = [
    {"a1": -1.996743, "r": 0.998619, "flag": 1.0},
    {"a1": -1.894098, "r": 0.998437, "flag": 1.0},
    {"a1": -1.854829, "r": 0.998353, "flag": 1.0},
    {"a1": -1.495171, "r": 0.963737, "flag": 1.0},
    {"a1": -1.974292, "r": 0.998195, "flag": 0.0},
]

# Match C++ exactly
UNIFIED_GAINS = [31.87, 30.91, 33.11, 30.54, 0.0]
M0_OFFSETS = [140.3, 30.7, 18.4, 23.6, 0.0]
M100_OFFSETS = [67.4, 138.4, 51.0, 196.9, 0.0]

Q_SCALE = 0.08


def load_wav(path):
    sr, data = wavfile.read(path)
    if data.dtype == np.int16:
        data = data.astype(np.float64) / 32768.0
    if len(data.shape) > 1:
        data = data[:, 0]
    return data, sr


def polar_to_freq(a1, r, sr=44100):
    cos_theta = -a1 / (2.0 * r)
    cos_theta = np.clip(cos_theta, -1.0, 1.0)
    theta = np.arccos(cos_theta)
    return theta * sr / (2.0 * np.pi)


def make_peaking_eq(freq, Q, gain_db, sr):
    freq = np.clip(freq, 20, sr * 0.49)
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
    return [b0/a0, b1/a0, b2/a0], [1.0, a1_coef/a0, a2/a0]


def make_lowpass_rbj(freq, Q, sr):
    freq = np.clip(freq, 20, sr * 0.49)
    w0 = 2.0 * np.pi * freq / sr
    alpha = np.sin(w0) / (2.0 * Q)
    b0 = (1.0 - np.cos(w0)) / 2.0
    b1 = 1.0 - np.cos(w0)
    b2 = (1.0 - np.cos(w0)) / 2.0
    a0 = 1.0 + alpha
    a1 = -2.0 * np.cos(w0)
    a2 = 1.0 - alpha
    return [b0/a0, b1/a0, b2/a0], [1.0, a1/a0, a2/a0]


def lerp(a, b, t):
    return a + t * (b - a)


def process_morph_with_compensation(signal, morph, sr):
    """Process matching exact C++ implementation."""
    # Input gain staging (-7 dB)
    x = signal.copy() * 0.446

    for i in range(5):
        # Interpolate coefficients
        a1 = lerp(M0_Q100_STAGES[i]["a1"], M100_Q100_STAGES[i]["a1"], morph)
        r = lerp(M0_Q100_STAGES[i]["r"], M100_Q100_STAGES[i]["r"], morph)
        flag = M0_Q100_STAGES[i]["flag"]

        # Unified gain + interpolated offset
        gain_db = UNIFIED_GAINS[i]
        offset = lerp(M0_OFFSETS[i], M100_OFFSETS[i], morph)

        base_freq = polar_to_freq(a1, r, sr)
        original_q = 1.0 / (2.0 * (1.0 - r))

        if flag > 0.5:
            freq = base_freq + offset
            effective_q = original_q * Q_SCALE
            effective_q = max(0.5, min(effective_q, 100.0))
            b, a = make_peaking_eq(freq, effective_q, gain_db, sr)
        else:
            b, a = make_lowpass_rbj(base_freq, 0.707, sr)

        x = lfilter(b, a, x)

    # Soft saturation
    x = np.tanh(x * 0.5) * 2.0

    # Level compensation (match C++)
    compensation_db = 9.43 - 9.70 * morph
    compensation_linear = 10.0 ** (compensation_db / 20.0)
    x *= compensation_linear

    # Makeup gain (+7 dB)
    x *= 2.24

    return x


def compute_spectrum(signal, sr, nfft=8192):
    spectrum = np.abs(rfft(signal, n=nfft))
    freqs = rfftfreq(nfft, 1/sr)
    spectrum_db = 20 * np.log10(spectrum + 1e-10)
    return freqs, spectrum_db


def spectral_error_normalized(ref_spectrum, our_spectrum, freqs, freq_range=(50, 6000)):
    mask = (freqs >= freq_range[0]) & (freqs <= freq_range[1])
    ref = ref_spectrum[mask]
    our = our_spectrum[mask]
    ref_mean = np.mean(ref)
    our_mean = np.mean(our)
    our_shifted = our + (ref_mean - our_mean)
    error = ref - our_shifted
    return np.sqrt(np.mean(error**2))


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    pink_path = os.path.join(script_dir, "..", "validation", "bypassed-pinknoise.wav")
    m0_ref_path = os.path.join(script_dir, "..", "validation", "hedzmorph0q100.wav")
    m100_ref_path = os.path.join(script_dir, "..", "validation", "hedzmorph100q100.wav")

    pink, sr = load_wav(pink_path)
    m0_ref, _ = load_wav(m0_ref_path)
    m100_ref, _ = load_wav(m100_ref_path)

    m0_ref_rms = 20 * np.log10(np.sqrt(np.mean(m0_ref**2)) + 1e-10)
    m100_ref_rms = 20 * np.log10(np.sqrt(np.mean(m100_ref**2)) + 1e-10)

    m0_ref_freqs, m0_ref_spec = compute_spectrum(m0_ref, sr)
    _, m100_ref_spec = compute_spectrum(m100_ref, sr)

    print("=" * 70)
    print("UNIFIED GAINS + COMPENSATION VERIFICATION")
    print("=" * 70)
    print(f"\nX3 Reference Levels:")
    print(f"  M0_Q100:   {m0_ref_rms:+.2f} dB")
    print(f"  M100_Q100: {m100_ref_rms:+.2f} dB")
    print(f"  Range: {abs(m0_ref_rms - m100_ref_rms):.2f} dB")

    print("\n" + "-" * 70)
    print("ENDPOINT TESTS (with compensation)")
    print("-" * 70)

    # Test M0
    m0_out = process_morph_with_compensation(pink, 0.0, sr)
    m0_rms = 20 * np.log10(np.sqrt(np.mean(m0_out**2)) + 1e-10)
    _, m0_spec = compute_spectrum(m0_out, sr)
    m0_err = spectral_error_normalized(m0_ref_spec, m0_spec, m0_ref_freqs)

    print(f"\nM0_Q100 (morph=0%):")
    print(f"  Level:          {m0_rms:+.2f} dB (target: {m0_ref_rms:+.2f} dB, error: {m0_rms - m0_ref_rms:+.2f} dB)")
    print(f"  Spectral error: {m0_err:.2f} dB")

    # Test M100
    m100_out = process_morph_with_compensation(pink, 1.0, sr)
    m100_rms = 20 * np.log10(np.sqrt(np.mean(m100_out**2)) + 1e-10)
    _, m100_spec = compute_spectrum(m100_out, sr)
    m100_err = spectral_error_normalized(m100_ref_spec, m100_spec, m0_ref_freqs)

    print(f"\nM100_Q100 (morph=100%):")
    print(f"  Level:          {m100_rms:+.2f} dB (target: {m100_ref_rms:+.2f} dB, error: {m100_rms - m100_ref_rms:+.2f} dB)")
    print(f"  Spectral error: {m100_err:.2f} dB")

    print("\n" + "-" * 70)
    print("FULL MORPH SWEEP (with compensation)")
    print("-" * 70)
    print("\nMorph   | Level      | Level Error | Compensation")
    print("-" * 60)

    target_avg = (m0_ref_rms + m100_ref_rms) / 2

    for morph in np.linspace(0, 1, 11):
        out = process_morph_with_compensation(pink, morph, sr)
        rms = 20 * np.log10(np.sqrt(np.mean(out**2)) + 1e-10)
        level_err = rms - target_avg
        comp_db = 9.43 - 9.70 * morph
        print(f"  {int(morph*100):3d}%  | {rms:+7.2f} dB | {level_err:+7.2f} dB  | {comp_db:+.2f} dB applied")

    print("-" * 60)

    # Calculate final metrics
    level_range = abs(m0_rms - m100_rms)
    avg_spectral_err = (m0_err + m100_err) / 2

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"\nLevel Range: {level_range:.2f} dB (X3: 0.57 dB) {'✓' if level_range < 2.0 else '✗'}")
    print(f"M0 Level Error: {abs(m0_rms - m0_ref_rms):.2f} dB {'✓' if abs(m0_rms - m0_ref_rms) < 3.0 else '✗'}")
    print(f"M100 Level Error: {abs(m100_rms - m100_ref_rms):.2f} dB {'✓' if abs(m100_rms - m100_ref_rms) < 3.0 else '✗'}")
    print(f"Average Spectral Error: {avg_spectral_err:.2f} dB")

    if level_range < 2.0 and avg_spectral_err < 8.0:
        print("\n✓ SOLUTION VALID - Level stability achieved with reasonable spectral match")
    else:
        print("\n✗ NEEDS IMPROVEMENT")


if __name__ == "__main__":
    main()
