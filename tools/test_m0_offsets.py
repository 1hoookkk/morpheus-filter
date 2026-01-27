#!/usr/bin/env python3
"""
Test frequency offsets on M0_Q100 (morph=0%, Q=100%).
Check if the same offsets calibrated for M100_Q100 work here.
"""

import numpy as np
from scipy.io import wavfile
from scipy.signal import lfilter
from scipy.fft import rfft, rfftfreq

# M0_Q100 captured coefficients
M0_Q100_STAGES = [
    {"a1": -1.976510, "r": 0.998242, "flag": 1},  # Stage 0
    {"a1": -1.938977, "r": 0.998296, "flag": 1},  # Stage 1
    {"a1": -1.872895, "r": 0.998353, "flag": 1},  # Stage 2
    {"a1": -1.523842, "r": 0.992409, "flag": 1},  # Stage 3
    {"a1": -1.997572, "r": 0.998289, "flag": 0},  # Stage 4 (LP)
]

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


def process_filter_with_offsets(signal, stages, sr, freq_offsets):
    """Process with per-stage frequency offsets."""
    x = signal.copy()

    for i, stage in enumerate(stages):
        base_freq = polar_to_freq(stage["a1"], stage["r"], sr)
        original_q = 1.0 / (2.0 * (1.0 - stage["r"]))

        if stage["flag"] == 1:
            freq = base_freq + freq_offsets[i]
            effective_q = original_q * Q_SCALE
            effective_q = max(0.5, min(effective_q, 100.0))
            b, a = make_peaking_eq(freq, effective_q, GAIN_DB, sr)
        else:
            b, a = make_lowpass_rbj(base_freq, 0.707, sr)
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
    ref_audio, _ = load_wav("validation/hedzmorph0q100.wav")  # M0_Q100 reference
    ref_freqs, ref_spectrum = compute_spectrum(ref_audio, sr)

    stages = M0_Q100_STAGES

    print("M0_Q100 STAGE FREQUENCIES (decoded):")
    for i, stage in enumerate(stages):
        freq = polar_to_freq(stage["a1"], stage["r"], sr)
        q = 1.0 / (2.0 * (1.0 - stage["r"]))
        typ = "Peaking" if stage["flag"] == 1 else "Lowpass"
        print(f"  Stage {i}: {freq:7.1f} Hz  Q={q:6.1f}  ({typ})")

    # Find X3 reference peaks for comparison
    from scipy.signal import find_peaks
    peaks_idx, _ = find_peaks(ref_spectrum, height=-10, prominence=5)
    print(f"\nX3 Reference Peaks (M0_Q100):")
    for idx in peaks_idx:
        f = ref_freqs[idx]
        if 50 <= f <= 8000:
            print(f"  {f:7.1f} Hz  ({ref_spectrum[idx]:+.1f} dB)")

    # Baseline (no offset)
    print(f"\n{'='*70}")
    output = process_filter_with_offsets(pink, stages, sr, [0, 0, 0, 0, 0])
    _, our_spec = compute_spectrum(output, sr)
    error_baseline = compare_spectra(ref_spectrum, our_spec, ref_freqs)
    print(f"Baseline (no offset): {error_baseline:.3f} dB")

    # Test with M100_Q100 offsets (may not work for M0)
    m100_offsets = [65, 150, 62, 0, 0]
    output = process_filter_with_offsets(pink, stages, sr, m100_offsets)
    _, our_spec = compute_spectrum(output, sr)
    error_m100 = compare_spectra(ref_spectrum, our_spec, ref_freqs)
    print(f"M100 offsets [+65, +150, +62, 0]: {error_m100:.3f} dB")

    # Grid search for M0-specific offsets
    print(f"\n{'='*70}")
    print("GRID SEARCH FOR M0_Q100 OPTIMAL OFFSETS")
    print(f"{'='*70}")

    results = []
    # M0_Q100 has different peak structure than M100
    # Stage 0: ~994 Hz, Stage 1: ~1690 Hz, Stage 2: ~2485 Hz
    for o0 in [0, 50, 100, 150, 200]:
        for o1 in [0, 50, 100, 150, 200]:
            for o2 in [0, 50, 100, 150]:
                offsets = [o0, o1, o2, 0, 0]
                output = process_filter_with_offsets(pink, stages, sr, offsets)
                if np.any(np.isnan(output)) or np.any(np.isinf(output)):
                    continue
                _, our_spec = compute_spectrum(output, sr)
                error = compare_spectra(ref_spectrum, our_spec, ref_freqs)
                results.append((offsets, error))

    results.sort(key=lambda x: x[1])

    print(f"\nTOP 10 OFFSET COMBINATIONS FOR M0_Q100:")
    for offsets, error in results[:10]:
        print(f"  {offsets}: {error:.3f} dB")

    best_offsets, best_error = results[0]
    print(f"\n{'='*70}")
    print(f"BEST OFFSETS FOR M0_Q100:")
    print(f"{'='*70}")
    print(f"  Stage 0: +{best_offsets[0]} Hz")
    print(f"  Stage 1: +{best_offsets[1]} Hz")
    print(f"  Stage 2: +{best_offsets[2]} Hz")
    print(f"  Stage 3: +{best_offsets[3]} Hz")
    print(f"  Error: {best_error:.3f} dB")

    print(f"\nComparison:")
    print(f"  Baseline (no offset):  {error_baseline:.3f} dB")
    print(f"  M100 offsets:          {error_m100:.3f} dB")
    print(f"  Optimal M0 offsets:    {best_error:.3f} dB")
    print(f"  Improvement vs baseline: {error_baseline - best_error:.3f} dB")


if __name__ == "__main__":
    main()
