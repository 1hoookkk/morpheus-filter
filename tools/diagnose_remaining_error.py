#!/usr/bin/env python3
"""
Diagnose where the remaining ~8.8 dB spectral error comes from.
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

Q_SCALE = 0.08
GAIN_DB = 34.0


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


def process_filter(signal, stages, sr):
    x = signal.copy()

    for stage in stages:
        freq = polar_to_freq(stage["a1"], stage["r"], sr)
        original_q = 1.0 / (2.0 * (1.0 - stage["r"]))

        if stage["flag"] == 1:
            effective_q = original_q * Q_SCALE
            effective_q = max(0.5, min(effective_q, 100.0))
            b, a = make_peaking_eq(freq, effective_q, GAIN_DB, sr)
        else:
            b, a = make_lowpass_rbj(freq, 0.707, sr)
        x = lfilter(b, a, x)

    return x


def compute_spectrum(signal, sr, nfft=8192):
    spectrum = np.abs(rfft(signal, n=nfft))
    freqs = rfftfreq(nfft, 1/sr)
    spectrum_db = 20 * np.log10(spectrum + 1e-10)
    return freqs, spectrum_db


def main():
    pink, sr = load_wav("validation/bypassed-pinknoise.wav")
    ref_audio, _ = load_wav("validation/hedzmorph100q100.wav")

    stages = CAPTURES["M100_Q100"]
    output = process_filter(pink, stages, sr)

    ref_freqs, ref_spectrum = compute_spectrum(ref_audio, sr)
    _, our_spectrum = compute_spectrum(output, sr)

    # Level-align
    mask = (ref_freqs >= 50) & (ref_freqs <= 6000)
    ref_mean = np.mean(ref_spectrum[mask])
    our_mean = np.mean(our_spectrum[mask])
    our_aligned = our_spectrum + (ref_mean - our_mean)

    error = ref_spectrum - our_aligned

    print(f"Level offset applied: {ref_mean - our_mean:.1f} dB")
    print(f"Overall RMS error: {np.sqrt(np.mean(error[mask]**2)):.2f} dB")

    # Analyze error by frequency band
    print(f"\n{'='*70}")
    print("ERROR BY FREQUENCY BAND")
    print(f"{'='*70}")

    bands = [
        ("Sub-bass", 50, 100),
        ("Bass", 100, 200),
        ("Low-mid", 200, 500),
        ("Mid", 500, 1000),
        ("High-mid", 1000, 2000),
        ("Upper-mid", 2000, 3000),
        ("Presence", 3000, 4000),
        ("Brilliance", 4000, 6000),
        ("Air", 6000, 8000),
    ]

    for name, lo, hi in bands:
        band_mask = (ref_freqs >= lo) & (ref_freqs <= hi)
        if np.any(band_mask):
            band_error = error[band_mask]
            rms = np.sqrt(np.mean(band_error**2))
            mean_err = np.mean(band_error)
            max_err = np.max(np.abs(band_error))
            print(f"{name:<12} ({lo:4d}-{hi:4d} Hz): RMS={rms:5.2f} dB, Mean={mean_err:+5.2f} dB, Max={max_err:5.2f} dB")

    # Find specific frequencies with largest errors
    print(f"\n{'='*70}")
    print("FREQUENCIES WITH LARGEST ABSOLUTE ERRORS")
    print(f"{'='*70}")

    abs_error = np.abs(error)
    sorted_idx = np.argsort(abs_error)[::-1]

    print(f"{'Freq':<10} {'Ref (dB)':<12} {'Ours (dB)':<12} {'Error'}")
    for idx in sorted_idx[:30]:
        f = ref_freqs[idx]
        if 50 <= f <= 8000:
            print(f"{f:8.1f}   {ref_spectrum[idx]:8.1f}     {our_aligned[idx]:8.1f}     {error[idx]:+6.1f}")

    # Look for systematic patterns
    print(f"\n{'='*70}")
    print("SYSTEMATIC PATTERNS")
    print(f"{'='*70}")

    # Are we too loud or too quiet at our formant frequencies?
    formant_freqs = [156.3, 2261.6, 2661.8, 4793.4]
    print("\nAt our formant frequencies:")
    for f in formant_freqs:
        idx = np.argmin(np.abs(ref_freqs - f))
        actual_f = ref_freqs[idx]
        print(f"  {f:.0f} Hz: Ref={ref_spectrum[idx]:.1f} dB, Ours={our_aligned[idx]:.1f} dB, Err={error[idx]:+.1f} dB")

    # Where does X3 have peaks?
    print("\nX3 reference peak frequencies (>-10 dB):")
    peak_mask = ref_spectrum > -10
    peak_freqs = ref_freqs[peak_mask & (ref_freqs >= 50) & (ref_freqs <= 8000)]
    peak_mags = ref_spectrum[peak_mask & (ref_freqs >= 50) & (ref_freqs <= 8000)]

    # Group into ranges
    if len(peak_freqs) > 0:
        # Find local maxima
        from scipy.signal import find_peaks
        peaks_idx, _ = find_peaks(ref_spectrum, height=-10, prominence=5)
        for idx in peaks_idx:
            f = ref_freqs[idx]
            if 50 <= f <= 8000:
                our_val = our_aligned[idx]
                ref_val = ref_spectrum[idx]
                print(f"  {f:6.0f} Hz: Ref={ref_val:+5.1f} dB, Ours={our_val:+5.1f} dB, Err={error[idx]:+5.1f} dB")

    # Correlation analysis
    print(f"\n{'='*70}")
    print("CORRELATION ANALYSIS")
    print(f"{'='*70}")

    corr = np.corrcoef(ref_spectrum[mask], our_aligned[mask])[0, 1]
    print(f"Correlation coefficient: {corr:.4f}")

    # What percentage of frequencies have error < 5 dB?
    low_err_mask = np.abs(error[mask]) < 5.0
    pct_low_err = 100.0 * np.sum(low_err_mask) / np.sum(mask)
    print(f"Frequencies with <5 dB error: {pct_low_err:.1f}%")

    high_err_mask = np.abs(error[mask]) > 10.0
    pct_high_err = 100.0 * np.sum(high_err_mask) / np.sum(mask)
    print(f"Frequencies with >10 dB error: {pct_high_err:.1f}%")


if __name__ == "__main__":
    main()
