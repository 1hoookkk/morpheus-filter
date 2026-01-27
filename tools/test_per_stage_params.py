#!/usr/bin/env python3
"""
Test PER-STAGE parameter optimization.

Observation: Stage 3 has Q=14 (low) vs Stages 0-2 have Q=300+ (high)
This might indicate different stages need different treatment.
"""

import numpy as np
from scipy.io import wavfile
from scipy.signal import lfilter
from scipy.fft import rfft, rfftfreq
import os
from itertools import product

CAPTURES = {
    "M100_Q100": [
        {"a1": -1.996743, "r": 0.998619, "flag": 1},  # Q=362, 156 Hz
        {"a1": -1.894098, "r": 0.998437, "flag": 1},  # Q=320, 2262 Hz
        {"a1": -1.854829, "r": 0.998353, "flag": 1},  # Q=304, 2662 Hz
        {"a1": -1.495171, "r": 0.963737, "flag": 1},  # Q=14,  4793 Hz  <-- MUCH LOWER Q!
        {"a1": -1.974292, "r": 0.998195, "flag": 0},  # LP,    1045 Hz
    ],
}


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


def process_filter_per_stage(signal, stages, sr, q_scales, gains):
    """Process with per-stage Q scale and gain."""
    x = signal.copy()

    for i, stage in enumerate(stages):
        freq = polar_to_freq(stage["a1"], stage["r"], sr)
        original_q = 1.0 / (2.0 * (1.0 - stage["r"]))

        if stage["flag"] == 1:
            # Per-stage parameters
            effective_q = original_q * q_scales[i]
            effective_q = max(0.5, min(effective_q, 100.0))
            b, a = make_peaking_eq(freq, effective_q, gains[i], sr)
        else:
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

    print("ORIGINAL STAGE DATA:")
    for i, s in enumerate(stages):
        freq = polar_to_freq(s["a1"], s["r"], sr)
        Q = 1.0 / (2.0 * (1.0 - s["r"]))
        stype = "Resonator" if s["flag"] == 1 else "Lowpass"
        print(f"  Stage {i}: {freq:.1f} Hz  Q={Q:.1f} ({stype})")

    # First test: uniform vs adaptive
    print(f"\n{'='*70}")
    print("TEST 1: Uniform Q_scale=0.08 vs Stage 3 unchanged")
    print(f"{'='*70}")

    # Baseline: uniform 0.08
    q_scales_uniform = [0.08, 0.08, 0.08, 0.08]
    gains_uniform = [34, 34, 34, 34]

    output = process_filter_per_stage(pink, stages, sr, q_scales_uniform, gains_uniform)
    _, our_spec = compute_spectrum(output, sr)
    error_uniform = compare_spectra(ref_spectrum, our_spec, ref_freqs)
    print(f"Uniform Q_scale=0.08: {error_uniform:.3f} dB")

    # Stage 3 has Q=14 originally - maybe don't scale it as much?
    # Original: 14 * 0.08 = 1.1 (very low)
    # What if we use full Q for stage 3?
    q_scales_adaptive = [0.08, 0.08, 0.08, 1.0]  # Keep Stage 3 at original Q
    output = process_filter_per_stage(pink, stages, sr, q_scales_adaptive, gains_uniform)
    _, our_spec = compute_spectrum(output, sr)
    error_adaptive = compare_spectra(ref_spectrum, our_spec, ref_freqs)
    print(f"Stage 3 at Q=14 (no scale): {error_adaptive:.3f} dB")

    # What if stage 3 needs LOWER gain since it already has lower Q?
    q_scales_adaptive2 = [0.08, 0.08, 0.08, 0.5]
    gains_adaptive = [34, 34, 34, 24]
    output = process_filter_per_stage(pink, stages, sr, q_scales_adaptive2, gains_adaptive)
    _, our_spec = compute_spectrum(output, sr)
    error_adaptive2 = compare_spectra(ref_spectrum, our_spec, ref_freqs)
    print(f"Stage 3: Q_scale=0.5, Gain=24: {error_adaptive2:.3f} dB")

    # Grid search for per-stage optimization
    print(f"\n{'='*70}")
    print("GRID SEARCH: Optimizing per-stage parameters")
    print(f"{'='*70}")

    results = []

    # Test different combinations
    # Stages 0-2 are high-Q, Stage 3 is low-Q
    q_options_highQ = [0.05, 0.08, 0.1, 0.15]
    q_options_lowQ = [0.3, 0.5, 0.8, 1.0]
    gain_options = [24, 30, 34, 40]

    # Reduce search space - use same for high-Q stages
    for q_highQ in q_options_highQ:
        for q_lowQ in q_options_lowQ:
            for g_main in gain_options:
                for g_s3 in [g_main - 10, g_main, g_main + 6]:
                    q_scales = [q_highQ, q_highQ, q_highQ, q_lowQ]
                    gains = [g_main, g_main, g_main, g_s3]

                    output = process_filter_per_stage(pink, stages, sr, q_scales, gains)
                    if np.any(np.isnan(output)) or np.any(np.isinf(output)):
                        continue

                    _, our_spec = compute_spectrum(output, sr)
                    error = compare_spectra(ref_spectrum, our_spec, ref_freqs)

                    results.append({
                        'q_highQ': q_highQ,
                        'q_lowQ': q_lowQ,
                        'g_main': g_main,
                        'g_s3': g_s3,
                        'error': error
                    })

    # Sort and show best
    results.sort(key=lambda x: x['error'])

    print(f"\nTOP 10 CONFIGURATIONS:")
    print(f"{'Q_highQ':<10} {'Q_lowQ':<10} {'G_main':<10} {'G_s3':<10} {'Error'}")
    for r in results[:10]:
        print(f"{r['q_highQ']:<10.2f} {r['q_lowQ']:<10.2f} {r['g_main']:<10} {r['g_s3']:<10} {r['error']:.3f} dB")

    # Best result
    best = results[0]
    print(f"\n{'='*70}")
    print(f"BEST PER-STAGE CONFIGURATION:")
    print(f"{'='*70}")
    print(f"Stages 0-2: Q_scale={best['q_highQ']:.2f}, Gain={best['g_main']} dB")
    print(f"Stage 3:    Q_scale={best['q_lowQ']:.2f}, Gain={best['g_s3']} dB")
    print(f"Error: {best['error']:.3f} dB")

    # Compare to uniform
    print(f"\nComparison to uniform Q_scale=0.08:")
    print(f"  Uniform:   {error_uniform:.3f} dB")
    print(f"  Per-stage: {best['error']:.3f} dB")
    print(f"  Improvement: {error_uniform - best['error']:.3f} dB")


if __name__ == "__main__":
    main()
