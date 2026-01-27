#!/usr/bin/env python3
"""
Test Q REDUCTION hypothesis.

Captured coefficients show Q=362 (extremely narrow spikes).
X3 reference shows broader peaks. Maybe Q knob or internal
scaling reduces the effective Q.
"""

import numpy as np
from scipy.io import wavfile
from scipy.signal import lfilter
from scipy.fft import rfft, rfftfreq
import os

CAPTURES = {
    "M100_Q100": [
        {"a1": -1.996743, "r": 0.998619, "flag": 1},  # Q=362
        {"a1": -1.894098, "r": 0.998437, "flag": 1},  # Q=320
        {"a1": -1.854829, "r": 0.998353, "flag": 1},  # Q=304
        {"a1": -1.495171, "r": 0.963737, "flag": 1},  # Q=14
        {"a1": -1.974292, "r": 0.998195, "flag": 0},  # LP
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
    """RBJ Peaking EQ using frequency and Q directly."""
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
    """Process with Q scaling factor applied to all stages."""
    x = signal.copy()

    for stage in stages:
        freq = polar_to_freq(stage["a1"], stage["r"], sr)
        original_q = 1.0 / (2.0 * (1.0 - stage["r"]))

        if stage["flag"] == 1:
            # Scale Q down
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

    print("ORIGINAL CAPTURED STAGE Q VALUES:")
    for i, s in enumerate(stages):
        freq = polar_to_freq(s["a1"], s["r"], sr)
        Q = 1.0 / (2.0 * (1.0 - s["r"]))
        stype = "Resonator" if s["flag"] == 1 else "Lowpass"
        print(f"  Stage {i}: {freq:.1f} Hz  Q={Q:.1f} ({stype})")

    print(f"\n{'='*70}")
    print("SWEEP: Q SCALE FACTOR (reduces extreme Q values)")
    print(f"{'='*70}")
    print(f"{'Q Scale':<12} {'Gain (dB)':<12} {'Error'}")

    results = []

    # Sweep both Q scale and gain
    for q_scale in [0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0]:
        for gain_db in [6, 12, 18, 24, 30, 36, 42, 48]:
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
        # Calculate effective Q for Stage 0
        original_q = 1.0 / (2.0 * (1.0 - 0.998619))
        eff_q = original_q * q_scale
        print(f"  Q_scale={q_scale:<6} (eff_Q0={eff_q:5.1f})  Gain={gain_db:2d} dB  Error={error:.2f} dB")

    # Best result
    best_q_scale, best_gain, best_error = results[0]
    print(f"\n{'='*70}")
    print(f"BEST: Q_scale={best_q_scale}, Gain={best_gain} dB, Error={best_error:.2f} dB")
    print(f"{'='*70}")

    print("\nEffective Q values at best setting:")
    for i, s in enumerate(stages):
        if s["flag"] == 1:
            freq = polar_to_freq(s["a1"], s["r"], sr)
            Q = 1.0 / (2.0 * (1.0 - s["r"]))
            eff_q = Q * best_q_scale
            print(f"  Stage {i}: {freq:.1f} Hz  Q: {Q:.1f} → {eff_q:.1f}")

    # Save best output
    output = process_filter(pink, stages, sr, best_gain, best_q_scale)
    output_norm = output / (np.max(np.abs(output)) + 1e-10) * 0.9
    wavfile.write('validation/trench_q_scaled.wav', sr,
                  (output_norm * 32767).astype(np.int16))
    print(f"\nSaved: validation/trench_q_scaled.wav")


if __name__ == "__main__":
    main()
