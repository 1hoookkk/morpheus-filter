#!/usr/bin/env python3
"""
Fine-tune Q scale and gain around the optimal zone found (Q_scale=0.1, Gain=36dB)
"""

import numpy as np
from scipy.io import wavfile
from scipy.signal import lfilter
from scipy.fft import rfft, rfftfreq
import os

CAPTURES = {
    "M100_Q100": [
        {"a1": -1.996743, "r": 0.998619, "flag": 1},
        {"a1": -1.894098, "r": 0.998437, "flag": 1},
        {"a1": -1.854829, "r": 0.998353, "flag": 1},
        {"a1": -1.495171, "r": 0.963737, "flag": 1},
        {"a1": -1.974292, "r": 0.998195, "flag": 0},
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


def process_filter(signal, stages, sr, gain_db, q_scale):
    x = signal.copy()

    for stage in stages:
        freq = polar_to_freq(stage["a1"], stage["r"], sr)
        original_q = 1.0 / (2.0 * (1.0 - stage["r"]))

        if stage["flag"] == 1:
            effective_q = original_q * q_scale
            effective_q = max(0.5, min(effective_q, 100.0))
            b, a = make_peaking_eq(freq, effective_q, gain_db, sr)
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

    print(f"{'='*70}")
    print("FINE-TUNING AROUND Q_scale=0.1, Gain=36 dB")
    print(f"{'='*70}")

    results = []

    # Fine-grained sweep
    for q_scale in np.arange(0.05, 0.20, 0.01):
        for gain_db in range(28, 46, 2):
            output = process_filter(pink, stages, sr, gain_db, q_scale)

            if np.any(np.isnan(output)) or np.any(np.isinf(output)):
                continue

            _, our_spectrum = compute_spectrum(output, sr)
            error = compare_spectra(ref_spectrum, our_spectrum, ref_freqs)

            results.append((q_scale, gain_db, error))

    # Sort by error
    results.sort(key=lambda x: x[2])

    print(f"\nTOP 20 COMBINATIONS:")
    for q_scale, gain_db, error in results[:20]:
        original_q = 1.0 / (2.0 * (1.0 - 0.998619))
        eff_q = original_q * q_scale
        print(f"  Q_scale={q_scale:.2f} (eff_Q0={eff_q:5.1f})  Gain={gain_db:2d} dB  Error={error:.3f} dB")

    # Best result
    best_q_scale, best_gain, best_error = results[0]
    print(f"\n{'='*70}")
    print(f"OPTIMAL: Q_scale={best_q_scale:.2f}, Gain={best_gain} dB")
    print(f"Error: {best_error:.3f} dB")
    print(f"{'='*70}")

    print("\nEffective Q values at optimal setting:")
    for i, s in enumerate(stages):
        if s["flag"] == 1:
            freq = polar_to_freq(s["a1"], s["r"], sr)
            Q = 1.0 / (2.0 * (1.0 - s["r"]))
            eff_q = Q * best_q_scale
            print(f"  Stage {i}: {freq:.1f} Hz  Q: {Q:.1f} → {eff_q:.1f}")

    # Also test both M0_Q100 and M100_Q100 with optimal params
    print(f"\n{'='*70}")
    print("TESTING OPTIMAL ON BOTH MORPH POSITIONS")
    print(f"{'='*70}")

    # Add M0_Q100 stages
    CAPTURES["M0_Q100"] = [
        {"a1": -1.976510, "r": 0.998242, "flag": 1},
        {"a1": -1.938977, "r": 0.998296, "flag": 1},
        {"a1": -1.872895, "r": 0.998353, "flag": 1},
        {"a1": -1.523842, "r": 0.992409, "flag": 1},
        {"a1": -1.997572, "r": 0.998289, "flag": 0},
    ]

    for case in ["M0_Q100", "M100_Q100"]:
        ref_path = f"validation/hedz{'morph0q100' if case == 'M0_Q100' else 'morph100q100'}.wav"
        if not os.path.exists(ref_path):
            continue

        ref_audio, _ = load_wav(ref_path)
        _, ref_spectrum = compute_spectrum(ref_audio, sr)

        output = process_filter(pink, CAPTURES[case], sr, best_gain, best_q_scale)
        _, our_spectrum = compute_spectrum(output, sr)
        error = compare_spectra(ref_spectrum, our_spectrum, ref_freqs)

        print(f"  {case}: Error = {error:.3f} dB")

    # Save best output
    output = process_filter(pink, stages, sr, best_gain, best_q_scale)
    output_norm = output / (np.max(np.abs(output)) + 1e-10) * 0.9
    wavfile.write('validation/trench_optimal.wav', sr,
                  (output_norm * 32767).astype(np.int16))
    print(f"\nSaved: validation/trench_optimal.wav")

    # Output C++ constants
    print(f"\n{'='*70}")
    print("C++ CONSTANTS TO USE:")
    print(f"{'='*70}")
    print(f"constexpr double Q_SCALE = {best_q_scale:.2f};")
    print(f"constexpr double GAIN_DB = {best_gain:.1f};")
    print(f"\n// In calculatePolarCoeffs:")
    print(f"double Q = 1.0 / (2.0 * (1.0 - radius));")
    print(f"Q = Q * Q_SCALE;  // Scale down extreme Q values")
    print(f"Q = juce::jlimit(0.5, 100.0, Q);")


if __name__ == "__main__":
    main()
