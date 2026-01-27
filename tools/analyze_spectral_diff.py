#!/usr/bin/env python3
"""
Analyze the spectral difference between our filter and X3 reference.
What frequencies are we getting wrong?
"""

import numpy as np
from scipy.io import wavfile
from scipy.signal import lfilter, find_peaks
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


def make_peaking_eq(a1, r, sr, gain_db):
    freq = polar_to_freq(a1, r, sr)
    freq = np.clip(freq, 20, sr * 0.49)
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


def process_filter(signal, stages, sr, gain_db):
    x = signal.copy()
    for stage in stages:
        if stage["flag"] == 1:
            b, a = make_peaking_eq(stage["a1"], stage["r"], sr, gain_db)
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


def find_spectral_peaks(freqs, spectrum_db, freq_range=(50, 8000), prominence=3, height=-30):
    """Find peaks in spectrum."""
    mask = (freqs >= freq_range[0]) & (freqs <= freq_range[1])
    sub_freqs = freqs[mask]
    sub_spec = spectrum_db[mask]

    peaks, props = find_peaks(sub_spec, prominence=prominence, height=height)
    return sub_freqs[peaks], sub_spec[peaks]


def main():
    pink, sr = load_wav("validation/bypassed-pinknoise.wav")
    ref_audio, _ = load_wav("validation/hedzmorph100q100.wav")

    stages = CAPTURES["M100_Q100"]

    print("CAPTURED STAGE FREQUENCIES:")
    for i, s in enumerate(stages):
        freq = polar_to_freq(s["a1"], s["r"], sr)
        Q = 1.0 / (2.0 * (1.0 - s["r"]))
        stype = "Resonator" if s["flag"] == 1 else "Lowpass"
        print(f"  Stage {i}: {freq:.1f} Hz  Q={Q:.1f} ({stype})")

    # Compute spectra
    ref_freqs, ref_spectrum = compute_spectrum(ref_audio, sr)
    _, our_60db = compute_spectrum(process_filter(pink, stages, sr, 60), sr)
    _, our_12db = compute_spectrum(process_filter(pink, stages, sr, 12), sr)
    _, pink_spectrum = compute_spectrum(pink, sr)

    # Find peaks
    ref_peak_freqs, ref_peak_mags = find_spectral_peaks(ref_freqs, ref_spectrum)
    our_peak_freqs, our_peak_mags = find_spectral_peaks(ref_freqs, our_60db)

    print(f"\n{'='*70}")
    print("X3 REFERENCE PEAKS:")
    print(f"{'='*70}")
    for f, m in zip(ref_peak_freqs, ref_peak_mags):
        print(f"  {f:7.1f} Hz : {m:+6.1f} dB")

    print(f"\n{'='*70}")
    print("OUR OUTPUT PEAKS (60 dB gain):")
    print(f"{'='*70}")
    for f, m in zip(our_peak_freqs, our_peak_mags):
        print(f"  {f:7.1f} Hz : {m:+6.1f} dB")

    # Compare at specific frequencies
    print(f"\n{'='*70}")
    print("FREQUENCY-BY-FREQUENCY COMPARISON")
    print(f"{'='*70}")
    print(f"{'Freq':<10} {'Pink':<10} {'X3 Ref':<10} {'Our 60dB':<10} {'Our 12dB':<10} {'Diff(60)':<10}")

    test_freqs = [100, 156, 200, 500, 1000, 1500, 2000, 2262, 2500, 2662, 3000, 4000, 4793, 5000, 6000]

    for f in test_freqs:
        idx = np.argmin(np.abs(ref_freqs - f))
        actual_f = ref_freqs[idx]
        pink_val = pink_spectrum[idx]
        ref_val = ref_spectrum[idx]
        our_60_val = our_60db[idx]
        our_12_val = our_12db[idx]
        diff = ref_val - our_60_val

        marker = ""
        if abs(diff) > 5:
            marker = "<-- LARGE DIFF"

        print(f"{actual_f:<10.1f} {pink_val:<10.1f} {ref_val:<10.1f} {our_60_val:<10.1f} {our_12_val:<10.1f} {diff:+6.1f} {marker}")

    # Compute overall shape difference
    mask = (ref_freqs >= 50) & (ref_freqs <= 6000)
    ref_sub = ref_spectrum[mask]
    our_sub = our_60db[mask]

    # Level-align
    ref_mean = np.mean(ref_sub)
    our_mean = np.mean(our_sub)
    our_aligned = our_sub + (ref_mean - our_mean)

    error = ref_sub - our_aligned
    rms_error = np.sqrt(np.mean(error**2))

    print(f"\n{'='*70}")
    print(f"OVERALL SPECTRAL SHAPE ERROR: {rms_error:.2f} dB (level-aligned)")
    print(f"X3 Mean: {ref_mean:.1f} dB, Our Mean: {our_mean:.1f} dB")
    print(f"Level Offset: {ref_mean - our_mean:.1f} dB")
    print(f"{'='*70}")

    # Where are the biggest errors?
    print(f"\n{'='*70}")
    print("LARGEST ERRORS BY FREQUENCY:")
    print(f"{'='*70}")
    freq_sub = ref_freqs[mask]
    error_abs = np.abs(error)
    sorted_idx = np.argsort(error_abs)[::-1][:20]

    for idx in sorted_idx:
        f = freq_sub[idx]
        e = error[idx]
        print(f"  {f:7.1f} Hz : {e:+6.1f} dB error")


if __name__ == "__main__":
    main()
