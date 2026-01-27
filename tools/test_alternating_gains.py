#!/usr/bin/env python3
"""
Test ALTERNATING GAINS hypothesis from TRENCH spec:
"6 cascaded peaking EQ biquads with alternating +/- gains"

This means stages should alternate between BOOST and CUT:
Stage 0: +12 dB (peak)
Stage 1: -12 dB (notch)
Stage 2: +12 dB (peak)
Stage 3: -12 dB (notch)
Stage 4: Lowpass
"""

import numpy as np
from scipy.io import wavfile
from scipy.signal import lfilter
from scipy.fft import rfft, rfftfreq
import os

CAPTURES = {
    "M100_Q100": [
        {"a1": -1.996743, "r": 0.998619, "flag": 1},  # Stage 0
        {"a1": -1.894098, "r": 0.998437, "flag": 1},  # Stage 1
        {"a1": -1.854829, "r": 0.998353, "flag": 1},  # Stage 2
        {"a1": -1.495171, "r": 0.963737, "flag": 1},  # Stage 3
        {"a1": -1.974292, "r": 0.998195, "flag": 0},  # Stage 4 - Lowpass
    ],
}


def load_wav(path):
    sr, data = wavfile.read(path)
    if data.dtype == np.int16:
        data = data.astype(np.float64) / 32768.0
    elif data.dtype == np.int32:
        data = data.astype(np.float64) / 2147483648.0
    if len(data.shape) > 1:
        data = data[:, 0]
    return data, sr


def polar_to_freq(a1, r, sr=44100):
    cos_theta = -a1 / (2.0 * r)
    cos_theta = np.clip(cos_theta, -1.0, 1.0)
    theta = np.arccos(cos_theta)
    return theta * sr / (2.0 * np.pi)


def make_peaking_eq(a1, r, sr, gain_db):
    """RBJ Peaking EQ - works for both boost (+) and cut (-)."""
    freq = polar_to_freq(a1, r, sr)
    freq = np.clip(freq, 20, sr * 0.49)

    Q = 1.0 / (2.0 * (1.0 - r))
    Q = np.clip(Q, 0.5, 100.0)

    A = 10.0 ** (gain_db / 40.0)
    w0 = 2.0 * np.pi * freq / sr
    alpha = np.sin(w0) / (2.0 * Q)

    if gain_db >= 0:  # Boost
        b0 = 1.0 + alpha * A
        b1 = -2.0 * np.cos(w0)
        b2 = 1.0 - alpha * A
        a0 = 1.0 + alpha / A
        a1_coef = -2.0 * np.cos(w0)
        a2 = 1.0 - alpha / A
    else:  # Cut
        b0 = 1.0 + alpha / A
        b1 = -2.0 * np.cos(w0)
        b2 = 1.0 - alpha / A
        a0 = 1.0 + alpha * A
        a1_coef = -2.0 * np.cos(w0)
        a2 = 1.0 - alpha * A

    b = [b0/a0, b1/a0, b2/a0]
    a = [1.0, a1_coef/a0, a2/a0]
    return b, a


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

    b = [b0/a0, b1/a0, b2/a0]
    a = [1.0, a1/a0, a2/a0]
    return b, a


def process_filter_with_gains(signal, stages, sr, gains):
    """Process with per-stage gain list."""
    x = signal.copy()

    for i, stage in enumerate(stages):
        if stage["flag"] == 1:
            b, a = make_peaking_eq(stage["a1"], stage["r"], sr, gains[i])
        else:
            freq = polar_to_freq(stage["a1"], stage["r"], sr)
            b, a = make_lowpass_rbj(freq, 0.707, sr)
        x = lfilter(b, a, x)

    return x


def compute_spectrum(signal, sr, nfft=8192):
    spectrum = np.abs(rfft(signal, n=nfft))
    freqs = rfftfreq(nfft, 1/sr)
    spectrum_db = 20 * np.log10(spectrum + 1e-10)
    return freqs, spectrum_db


def compare_spectra(ref_spectrum, our_spectrum, freqs, freq_range=(50, 6000)):
    mask = (freqs >= freq_range[0]) & (freqs <= freq_range[1])
    ref = ref_spectrum[mask]
    our = our_spectrum[mask]

    # Level-match via offset
    ref_mean = np.mean(ref)
    our_mean = np.mean(our)
    our_shifted = our + (ref_mean - our_mean)

    error = ref - our_shifted
    return np.sqrt(np.mean(error**2))


def main():
    pink, sr = load_wav("validation/bypassed-pinknoise.wav")
    ref_audio, _ = load_wav("validation/hedzmorph100q100.wav")
    ref_freqs, ref_spectrum = compute_spectrum(ref_audio, sr)

    stages = CAPTURES["M100_Q100"]

    print("Stage frequencies:")
    for i, s in enumerate(stages):
        freq = polar_to_freq(s["a1"], s["r"], sr)
        stype = "Resonator" if s["flag"] == 1 else "Lowpass"
        print(f"  Stage {i}: {freq:.1f} Hz ({stype})")

    print(f"\n{'='*70}")
    print("TESTING ALTERNATING GAIN PATTERNS")
    print(f"{'='*70}")

    # Test various alternating patterns
    test_patterns = [
        # (name, [gains for stages 0-3, stage 4 is LP])
        ("All +12", [12, 12, 12, 12]),
        ("All +24", [24, 24, 24, 24]),
        ("All +36", [36, 36, 36, 36]),
        ("All +48", [48, 48, 48, 48]),
        ("All +60", [60, 60, 60, 60]),

        # Alternating patterns
        ("Alternating +12/-12", [12, -12, 12, -12]),
        ("Alternating +18/-12", [18, -12, 18, -12]),
        ("Alternating +24/-12", [24, -12, 24, -12]),
        ("Alternating +24/-18", [24, -18, 24, -18]),
        ("Alternating +36/-18", [36, -18, 36, -18]),
        ("Alternating +36/-24", [36, -24, 36, -24]),

        # Progressive patterns (decreasing boost)
        ("Progressive +36,+24,+18,+12", [36, 24, 18, 12]),
        ("Progressive +48,+36,+24,+12", [48, 36, 24, 12]),

        # Alternating with higher magnitudes
        ("Alt +48/-24", [48, -24, 48, -24]),
        ("Alt +60/-30", [60, -30, 60, -30]),

        # Decreasing alternating
        ("Alt +36/-12,+24/-6", [36, -12, 24, -6]),
        ("Alt +48/-18,+36/-12", [48, -18, 36, -12]),

        # Formant-style (strong first, weaker later)
        ("Formant +48,+36,+24,+12", [48, 36, 24, 12]),
        ("Formant +60,-30,+48,-24", [60, -30, 48, -24]),

        # What if only some stages are active?
        ("+60 on S0, 0 on rest", [60, 0, 0, 0]),
        ("+60 on S0,S2, 0 on S1,S3", [60, 0, 60, 0]),
        ("+48 on S0,S2, -24 on S1,S3", [48, -24, 48, -24]),
    ]

    results = []

    for name, gains in test_patterns:
        output = process_filter_with_gains(pink, stages, sr, gains)

        if np.any(np.isnan(output)) or np.any(np.isinf(output)):
            print(f"{name:<35} UNSTABLE")
            continue

        _, our_spectrum = compute_spectrum(output, sr)
        error = compare_spectra(ref_spectrum, our_spectrum, ref_freqs)

        print(f"{name:<35} Error: {error:.2f} dB")
        results.append((name, gains, error))

    # Find best
    results.sort(key=lambda x: x[2])
    print(f"\n{'='*70}")
    print("TOP 5 PATTERNS")
    print(f"{'='*70}")
    for name, gains, error in results[:5]:
        print(f"  {error:.2f} dB: {name} {gains}")

    # Detailed analysis of best
    best_name, best_gains, best_error = results[0]
    print(f"\n{'='*70}")
    print(f"BEST: {best_name}")
    print(f"Gains: {best_gains}")
    print(f"Spectral Error: {best_error:.2f} dB")
    print(f"{'='*70}")

    # Save best output
    output = process_filter_with_gains(pink, stages, sr, best_gains)
    out_rms = np.sqrt(np.mean(output**2))
    ref_rms = np.sqrt(np.mean(ref_audio**2))
    print(f"\nOutput RMS: {out_rms:.6f}, Reference RMS: {ref_rms:.6f}")

    output_norm = output / (np.max(np.abs(output)) + 1e-10) * 0.9
    wavfile.write('validation/trench_best_pattern.wav', sr,
                  (output_norm * 32767).astype(np.int16))
    print(f"Saved: validation/trench_best_pattern.wav")


if __name__ == "__main__":
    main()
