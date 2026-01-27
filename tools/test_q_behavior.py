#!/usr/bin/env python3
"""
Test Q knob behavior across the range.
Verify that Q=0% produces flat response and Q=100% produces sharp peaks.
"""

import numpy as np
from scipy.io import wavfile
from scipy.signal import lfilter, find_peaks
from scipy.fft import rfft, rfftfreq

# M50 keyframe (morph=50%) - Stage 0 at ~407 Hz, more reasonable for testing
M50_STAGES = [
    {"a1": -1.993596, "r": 0.998475, "flag": 1},  # ~407 Hz
    {"a1": -1.912492, "r": 0.998383, "flag": 1},
    {"a1": -1.861726, "r": 0.998353, "flag": 1},
    {"a1": -1.510937, "r": 0.979504, "flag": 1},
    {"a1": -1.992010, "r": 0.998231, "flag": 0},
    {"a1": -1.991170, "r": 0.988775, "flag": 0},
    {"a1": -2.0, "r": 0.5, "flag": 0},
]

# Use M50 for testing
TEST_STAGES = M50_STAGES

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


def apply_q_to_radius(r_ref, q_normalized):
    """Apply Q knob scaling to radius."""
    # Q knob 0-1 maps to Q 0.5% - 100%
    Q_REF = 100.0
    Q_new = 0.5 + q_normalized * 99.5

    if Q_new <= 0.0:
        return 0.5
    if r_ref <= 0.0 or r_ref >= 1.0:
        return r_ref

    # Exponential scaling: r = r_ref^(Q_ref / Q_new)
    r = np.exp(np.log(r_ref) * (Q_REF / Q_new))

    # Clamp to valid range
    return np.clip(r, 0.3, r_ref)


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


def process_filter(signal, stages, sr, q_knob):
    """Process signal with Q knob applied."""
    x = signal.copy()

    for i, stage in enumerate(stages):
        if stage["r"] <= 0 or stage["r"] >= 1:
            continue  # Skip invalid stages

        # IMPORTANT: Decode frequency from ORIGINAL radius (before Q scaling)
        # This matches the C++ implementation
        base_freq = polar_to_freq(stage["a1"], stage["r"], sr)

        # Apply Q knob to radius for Q calculation only
        r_scaled = apply_q_to_radius(stage["r"], q_knob)

        if stage["flag"] == 1:
            original_q = 1.0 / (2.0 * (1.0 - r_scaled))
            effective_q = max(0.5, min(original_q * Q_SCALE, 100.0))  # Clamp to [0.5, 100]
            base_freq = max(base_freq, 20)  # Ensure minimum frequency
            b, a = make_peaking_eq(base_freq, effective_q, GAIN_DB, sr)
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


def measure_peak_width(freqs, spectrum_db, peak_freq, threshold_db=-3):
    """Measure bandwidth at threshold below peak."""
    # Find the peak
    peak_idx = np.argmin(np.abs(freqs - peak_freq))
    peak_db = spectrum_db[peak_idx]

    # Find left edge (go backward until below threshold)
    left_idx = peak_idx
    for i in range(peak_idx, 0, -1):
        if spectrum_db[i] < peak_db + threshold_db:
            left_idx = i
            break

    # Find right edge (go forward until below threshold)
    right_idx = peak_idx
    for i in range(peak_idx, len(spectrum_db)):
        if spectrum_db[i] < peak_db + threshold_db:
            right_idx = i
            break

    return freqs[right_idx] - freqs[left_idx]


def main():
    pink, sr = load_wav("validation/bypassed-pinknoise.wav")

    print("="*70)
    print("Q KNOB BEHAVIOR TEST")
    print("="*70)
    print(f"\nUsing Q_SCALE={Q_SCALE}, GAIN_DB={GAIN_DB}")
    print(f"Testing at Morph=50% (Stage 0 at ~407 Hz)")

    # Get reference peak frequency
    ref_freq = polar_to_freq(TEST_STAGES[0]["a1"], TEST_STAGES[0]["r"], sr)
    print(f"Stage 0 decoded frequency: {ref_freq:.1f} Hz")

    print(f"\n{'Q Knob':<10} {'Effective Q':<15} {'Peak (dB)':<12} {'BW (Hz)':<10} {'RMS (dB)':<10}")
    print("-" * 60)

    q_values = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]

    results = []
    for q_knob in q_values:
        output = process_filter(pink, TEST_STAGES, sr, q_knob)
        freqs, spec = compute_spectrum(output, sr)

        # Find actual peak near expected frequency
        mask = (freqs >= 50) & (freqs <= 500)
        peak_idx = np.argmax(spec[mask])
        actual_peak_freq = freqs[mask][peak_idx]
        peak_db = spec[mask][peak_idx]

        # Measure bandwidth
        bandwidth = measure_peak_width(freqs, spec, actual_peak_freq)

        # Compute output RMS
        rms = np.sqrt(np.mean(output**2))
        rms_db = 20 * np.log10(rms + 1e-10)

        # Effective Q estimate (from radius after scaling) - with clamping like C++ code
        r_scaled = apply_q_to_radius(TEST_STAGES[0]["r"], q_knob)
        original_q = 1.0 / (2.0 * (1.0 - r_scaled))
        effective_q = max(0.5, min(original_q * Q_SCALE, 100.0))

        results.append({
            'q_knob': q_knob,
            'effective_q': effective_q,
            'peak_db': peak_db,
            'bandwidth': bandwidth,
            'rms_db': rms_db,
        })

        print(f"{q_knob*100:5.0f}%     {effective_q:8.2f}        {peak_db:+6.1f}       {bandwidth:6.0f}      {rms_db:+.1f}")

    # Analysis
    print(f"\n{'='*70}")
    print("ANALYSIS")
    print(f"{'='*70}")

    q0 = results[0]
    q100 = results[-1]

    print(f"\nQ=0% vs Q=100% comparison:")
    print(f"  Effective Q: {q0['effective_q']:.1f} → {q100['effective_q']:.1f}")
    print(f"  Peak level:  {q0['peak_db']:+.1f} → {q100['peak_db']:+.1f} dB ({q100['peak_db']-q0['peak_db']:+.1f} dB change)")
    print(f"  Bandwidth:   {q0['bandwidth']:.0f} → {q100['bandwidth']:.0f} Hz ({(1-q100['bandwidth']/q0['bandwidth'])*100:.0f}% narrower)")
    print(f"  Output RMS:  {q0['rms_db']:+.1f} → {q100['rms_db']:+.1f} dB")

    # Check if behavior is correct
    print(f"\n{'='*70}")
    print("VALIDATION")
    print(f"{'='*70}")

    issues = []

    if q100['peak_db'] < q0['peak_db']:
        issues.append("Peak should be HIGHER at Q=100%, not lower")

    if q100['bandwidth'] > q0['bandwidth']:
        issues.append("Bandwidth should be NARROWER at Q=100%, not wider")

    if q100['effective_q'] < q0['effective_q'] * 5:
        issues.append("Q should increase significantly from Q=0% to Q=100%")

    if issues:
        print("\nISSUES FOUND:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("\nAll checks PASSED:")
        print("  - Peak increases with Q knob")
        print("  - Bandwidth narrows with Q knob")
        print("  - Effective Q scales correctly")


if __name__ == "__main__":
    main()
