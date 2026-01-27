#!/usr/bin/env python3
"""
Test FREQUENCY OFFSET hypothesis.

The X3 reference has peaks at different frequencies than our captured
coefficients predict. Test if applying a frequency offset improves match.
"""

import numpy as np
from scipy.io import wavfile
from scipy.signal import lfilter
from scipy.fft import rfft, rfftfreq
import os

CAPTURES = {
    "M100_Q100": [
        {"a1": -1.996743, "r": 0.998619, "flag": 1},  # Decoded: 156 Hz, X3 peak: 221 Hz
        {"a1": -1.894098, "r": 0.998437, "flag": 1},  # Decoded: 2262 Hz, X3 peak: 2412 Hz
        {"a1": -1.854829, "r": 0.998353, "flag": 1},  # Decoded: 2662 Hz, X3 peak: 2724 Hz
        {"a1": -1.495171, "r": 0.963737, "flag": 1},  # Decoded: 4793 Hz
        {"a1": -1.974292, "r": 0.998195, "flag": 0},  # LP: 1045 Hz
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
    ref_audio, _ = load_wav("validation/hedzmorph100q100.wav")
    ref_freqs, ref_spectrum = compute_spectrum(ref_audio, sr)

    stages = CAPTURES["M100_Q100"]

    print("CAPTURED vs X3 PEAKS:")
    print(f"  Stage 0: 156 Hz (captured) vs 221 Hz (X3 peak) → +65 Hz offset")
    print(f"  Stage 1: 2262 Hz (captured) vs 2412 Hz (X3 peak) → +150 Hz offset")
    print(f"  Stage 2: 2662 Hz (captured) vs 2724 Hz (X3 peak) → +62 Hz offset")
    print(f"  Stage 3: 4793 Hz (captured) vs ? Hz → unknown")

    # Baseline (no offset)
    output = process_filter_with_offsets(pink, stages, sr, [0, 0, 0, 0])
    _, our_spec = compute_spectrum(output, sr)
    error_baseline = compare_spectra(ref_spectrum, our_spec, ref_freqs)
    print(f"\nBaseline (no offset): {error_baseline:.3f} dB")

    # Test with observed offsets
    observed_offsets = [65, 150, 62, 0]
    output = process_filter_with_offsets(pink, stages, sr, observed_offsets)
    _, our_spec = compute_spectrum(output, sr)
    error_observed = compare_spectra(ref_spectrum, our_spec, ref_freqs)
    print(f"Observed offsets [+65, +150, +62, 0]: {error_observed:.3f} dB")

    # Test uniform offset
    print(f"\n{'='*70}")
    print("UNIFORM FREQUENCY OFFSET SWEEP")
    print(f"{'='*70}")

    results = []
    for offset in range(-100, 201, 20):
        offsets = [offset, offset, offset, offset]
        output = process_filter_with_offsets(pink, stages, sr, offsets)
        _, our_spec = compute_spectrum(output, sr)
        error = compare_spectra(ref_spectrum, our_spec, ref_freqs)
        results.append((offset, error))
        print(f"  Offset {offset:+4d} Hz: {error:.3f} dB")

    # Find best uniform offset
    results.sort(key=lambda x: x[1])
    best_offset, best_error = results[0]
    print(f"\nBest uniform offset: {best_offset:+d} Hz → {best_error:.3f} dB")

    # Test percentage-based offset (proportional to frequency)
    print(f"\n{'='*70}")
    print("PERCENTAGE-BASED FREQUENCY OFFSET")
    print(f"{'='*70}")

    base_freqs = [156, 2262, 2662, 4793]

    for pct in [0, 5, 10, 15, 20, 25, 30, 40, 50]:
        offsets = [int(f * pct / 100) for f in base_freqs]
        output = process_filter_with_offsets(pink, stages, sr, offsets)
        _, our_spec = compute_spectrum(output, sr)
        error = compare_spectra(ref_spectrum, our_spec, ref_freqs)
        print(f"  +{pct}% offset {offsets}: {error:.3f} dB")

    # Grid search for per-stage optimization
    print(f"\n{'='*70}")
    print("PER-STAGE FREQUENCY OFFSET GRID SEARCH")
    print(f"{'='*70}")

    # Test variations around observed offsets
    results = []
    for o0 in [0, 40, 65, 80, 100]:
        for o1 in [0, 100, 150, 180, 200]:
            for o2 in [0, 40, 62, 80, 100]:
                offsets = [o0, o1, o2, 0]
                output = process_filter_with_offsets(pink, stages, sr, offsets)
                if np.any(np.isnan(output)) or np.any(np.isinf(output)):
                    continue
                _, our_spec = compute_spectrum(output, sr)
                error = compare_spectra(ref_spectrum, our_spec, ref_freqs)
                results.append((offsets, error))

    results.sort(key=lambda x: x[1])

    print(f"\nTOP 10 OFFSET COMBINATIONS:")
    for offsets, error in results[:10]:
        print(f"  {offsets}: {error:.3f} dB")

    # Best result
    best_offsets, best_error = results[0]
    print(f"\n{'='*70}")
    print(f"BEST FREQUENCY OFFSETS:")
    print(f"{'='*70}")
    print(f"  Stage 0: +{best_offsets[0]} Hz")
    print(f"  Stage 1: +{best_offsets[1]} Hz")
    print(f"  Stage 2: +{best_offsets[2]} Hz")
    print(f"  Stage 3: +{best_offsets[3]} Hz")
    print(f"  Error: {best_error:.3f} dB")

    # Compare to baseline
    print(f"\nImprovement: {error_baseline - best_error:.3f} dB better than baseline")


if __name__ == "__main__":
    main()
