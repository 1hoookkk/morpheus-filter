#!/usr/bin/env python3
"""
Comprehensive validation suite for TRENCH Z-Plane filter.
Tests all reference positions and reports overall accuracy.
"""

import numpy as np
from scipy.io import wavfile
from scipy.signal import lfilter
from scipy.fft import rfft, rfftfreq
import os

# Validated coefficient captures
CAPTURES = {
    "M0_Q100": {
        "stages": [
            {"a1": -1.976510, "r": 0.998242, "flag": 1},
            {"a1": -1.938977, "r": 0.998296, "flag": 1},
            {"a1": -1.872895, "r": 0.998353, "flag": 1},
            {"a1": -1.523842, "r": 0.992409, "flag": 1},
            {"a1": -1.997572, "r": 0.998289, "flag": 0},
        ],
        "morph": 0.0,
        "ref_file": "validation/hedzmorph0q100.wav",
    },
    "M100_Q100": {
        "stages": [
            {"a1": -1.996743, "r": 0.998619, "flag": 1},
            {"a1": -1.894098, "r": 0.998437, "flag": 1},
            {"a1": -1.854829, "r": 0.998353, "flag": 1},
            {"a1": -1.495171, "r": 0.963737, "flag": 1},
            {"a1": -1.974292, "r": 0.998195, "flag": 0},
        ],
        "morph": 1.0,
        "ref_file": "validation/hedzmorph100q100.wav",
    },
    "M100_Q0": {
        "stages": [
            {"a1": -1.986418, "r": 0.987503, "flag": 1},
            {"a1": -1.837391, "r": 0.974537, "flag": 1},
            {"a1": -1.794609, "r": 0.977806, "flag": 1},
            {"a1": -1.362762, "r": 0.883514, "flag": 1},
            {"a1": -1.914935, "r": 0.993960, "flag": 0},
        ],
        "morph": 1.0,
        "ref_file": "validation/hedzmorph100q0.wav",
    },
}

# Validated DSP parameters
Q_SCALE = 0.08
GAIN_DB = 34.0
M100_OFFSETS = [65.0, 150.0, 62.0, 0.0, 0.0]


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


def process_filter(signal, stages, sr, morph):
    """Process signal with morph-interpolated frequency offsets."""
    x = signal.copy()
    for i, stage in enumerate(stages):
        if stage["r"] <= 0 or stage["r"] >= 1:
            continue
        base_freq = polar_to_freq(stage["a1"], stage["r"], sr)

        if stage["flag"] == 1:
            # Apply morph-interpolated frequency offset
            offset = morph * M100_OFFSETS[i] if i < len(M100_OFFSETS) else 0.0
            freq = base_freq + offset
            original_q = 1.0 / (2.0 * (1.0 - stage["r"]))
            effective_q = max(0.5, min(original_q * Q_SCALE, 100.0))
            b, a = make_peaking_eq(freq, effective_q, GAIN_DB, sr)
        else:
            base_freq = max(base_freq, 20)
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


def find_peaks(freqs, spectrum, min_height=0, min_freq=50, max_freq=8000):
    """Find spectral peaks in frequency range."""
    from scipy.signal import find_peaks as scipy_find_peaks
    mask = (freqs >= min_freq) & (freqs <= max_freq)
    masked_freqs = freqs[mask]
    masked_spec = spectrum[mask]
    peaks_idx, props = scipy_find_peaks(masked_spec, height=min_height, prominence=3)
    return [(masked_freqs[i], masked_spec[i]) for i in peaks_idx[:6]]


def main():
    # Check if files exist
    pink_path = "validation/bypassed-pinknoise.wav"
    if not os.path.exists(pink_path):
        print(f"ERROR: {pink_path} not found!")
        print("Run from the project root directory.")
        return

    pink, sr = load_wav(pink_path)

    print("="*70)
    print("TRENCH COMPREHENSIVE VALIDATION")
    print("="*70)
    print(f"\nDSP Parameters:")
    print(f"  Q_SCALE = {Q_SCALE}")
    print(f"  GAIN_DB = {GAIN_DB}")
    print(f"  M100_OFFSETS = {M100_OFFSETS[:4]}")
    print(f"  Morph-interpolated offsets: YES")

    results = []

    for name, capture in CAPTURES.items():
        ref_path = capture["ref_file"]
        if not os.path.exists(ref_path):
            print(f"\nWARNING: {ref_path} not found, skipping {name}")
            continue

        print(f"\n{'='*70}")
        print(f"Testing: {name}")
        print(f"{'='*70}")

        ref_audio, _ = load_wav(ref_path)
        ref_freqs, ref_spectrum = compute_spectrum(ref_audio, sr)

        # Process with our implementation
        output = process_filter(pink, capture["stages"], sr, capture["morph"])
        _, our_spectrum = compute_spectrum(output, sr)

        # Calculate error
        error = compare_spectra(ref_spectrum, our_spectrum, ref_freqs)

        # Find peaks in reference
        ref_peaks = find_peaks(ref_freqs, ref_spectrum)
        our_peaks = find_peaks(ref_freqs, our_spectrum)

        print(f"\nReference peaks:")
        for f, db in ref_peaks:
            print(f"  {f:6.0f} Hz: {db:+.1f} dB")

        print(f"\nOur peaks:")
        for f, db in our_peaks:
            print(f"  {f:6.0f} Hz: {db:+.1f} dB")

        print(f"\nSpectral RMS Error: {error:.3f} dB")

        results.append({
            "name": name,
            "error": error,
            "morph": capture["morph"],
        })

    # Summary
    print(f"\n{'='*70}")
    print("VALIDATION SUMMARY")
    print(f"{'='*70}")

    print(f"\n{'Position':<15} {'Error (dB)':<15} {'Status'}")
    print("-" * 45)

    total_error = 0
    passed = 0
    for r in results:
        status = "PASS" if r["error"] < 10.0 else "NEEDS WORK"
        if r["error"] < 10.0:
            passed += 1
        print(f"{r['name']:<15} {r['error']:<15.3f} {status}")
        total_error += r["error"]

    avg_error = total_error / len(results) if results else 0
    print("-" * 45)
    print(f"{'Average':<15} {avg_error:<15.3f}")
    print(f"\nPassed: {passed}/{len(results)}")

    # Grade overall
    if avg_error < 7.0:
        grade = "A - Excellent match"
    elif avg_error < 8.5:
        grade = "B - Good match"
    elif avg_error < 10.0:
        grade = "C - Acceptable"
    elif avg_error < 12.0:
        grade = "D - Needs improvement"
    else:
        grade = "F - Significant issues"

    print(f"\nOverall Grade: {grade}")

    # Grade for high-Q only (typical use case)
    high_q_results = [r for r in results if "Q0" not in r["name"]]
    if high_q_results:
        high_q_avg = sum(r["error"] for r in high_q_results) / len(high_q_results)
        if high_q_avg < 7.0:
            high_q_grade = "A - Excellent"
        elif high_q_avg < 8.0:
            high_q_grade = "B - Good"
        elif high_q_avg < 9.0:
            high_q_grade = "C - Acceptable"
        else:
            high_q_grade = "D - Needs work"
        print(f"High-Q Grade: {high_q_grade} (avg {high_q_avg:.2f} dB, typical use case)")

    # Recommendations
    print(f"\n{'='*70}")
    print("RECOMMENDATIONS")
    print(f"{'='*70}")

    if avg_error < 8.5:
        print("""
The implementation is producing good spectral matches to X3 reference audio.

Next steps:
1. Listen test in DAW - perceptual quality may be even closer than metrics suggest
2. Capture additional presets (Meaty Gizmo, Radio Craze)
3. Fine-tune saturation curve if needed
""")
    else:
        print("""
There is room for improvement in the spectral match.

Consider:
1. Reviewing the Q_SCALE and GAIN_DB parameters
2. Investigating the lowpass stage contribution
3. Analyzing the saturation curve
4. Checking if additional frequency offsets are needed
""")


if __name__ == "__main__":
    main()
