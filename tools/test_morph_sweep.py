#!/usr/bin/env python3
"""
Test spectral error across the full morph range (0-100%).
Verify that Q_SCALE=0.08 and GAIN_DB=34 work well everywhere.
"""

import numpy as np
from scipy.io import wavfile
from scipy.signal import lfilter
from scipy.fft import rfft, rfftfreq

# Preset keyframes from PluginProcessor.cpp (Talking Hedz)
TALKING_HEDZ = {
    0.0: [
        {"a1": -1.974805, "r": 0.998231, "flag": 1},
        {"a1": -1.939721, "r": 0.998292, "flag": 1},
        {"a1": -1.873399, "r": 0.998353, "flag": 1},
        {"a1": -1.524112, "r": 0.992679, "flag": 1},
        {"a1": -1.997652, "r": 0.998292, "flag": 0},
        {"a1": -1.992054, "r": 0.982433, "flag": 0},
        {"a1": -2.0, "r": 0.5, "flag": 0},
    ],
    0.25: [
        {"a1": -1.987616, "r": 0.998353, "flag": 1},
        {"a1": -1.928071, "r": 0.998338, "flag": 1},
        {"a1": -1.867585, "r": 0.998353, "flag": 1},
        {"a1": -1.518988, "r": 0.987555, "flag": 1},
        {"a1": -1.996355, "r": 0.998261, "flag": 0},
        {"a1": -1.992689, "r": 0.986090, "flag": 0},
        {"a1": -2.0, "r": 0.5, "flag": 0},
    ],
    0.5: [
        {"a1": -1.993596, "r": 0.998475, "flag": 1},
        {"a1": -1.912492, "r": 0.998383, "flag": 1},
        {"a1": -1.861726, "r": 0.998353, "flag": 1},
        {"a1": -1.510937, "r": 0.979504, "flag": 1},
        {"a1": -1.992010, "r": 0.998231, "flag": 0},
        {"a1": -1.991170, "r": 0.988775, "flag": 0},
        {"a1": -2.0, "r": 0.5, "flag": 0},
    ],
    0.75: [
        {"a1": -1.996402, "r": 0.998597, "flag": 1},
        {"a1": -1.896912, "r": 0.998429, "flag": 1},
        {"a1": -1.855866, "r": 0.998353, "flag": 1},
        {"a1": -1.499229, "r": 0.967796, "flag": 1},
        {"a1": -1.978928, "r": 0.998200, "flag": 0},
        {"a1": -1.984614, "r": 0.991461, "flag": 0},
        {"a1": -2.0, "r": 0.5, "flag": 0},
    ],
    1.0: [
        {"a1": -1.997743, "r": 0.998719, "flag": 1},
        {"a1": -1.881333, "r": 0.998475, "flag": 1},
        {"a1": -1.850007, "r": 0.998353, "flag": 1},
        {"a1": -1.476768, "r": 0.945335, "flag": 1},
        {"a1": -1.939599, "r": 0.998170, "flag": 0},
        {"a1": -1.962060, "r": 0.993167, "flag": 0},
        {"a1": -2.0, "r": 0.5, "flag": 0},
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


def interpolate_stages(morph, preset=TALKING_HEDZ):
    """Interpolate between keyframes."""
    keys = sorted(preset.keys())

    # Find surrounding keyframes
    lo_key = keys[0]
    hi_key = keys[-1]
    for i in range(len(keys) - 1):
        if keys[i] <= morph <= keys[i+1]:
            lo_key = keys[i]
            hi_key = keys[i+1]
            break

    lo_stages = preset[lo_key]
    hi_stages = preset[hi_key]

    t = (morph - lo_key) / (hi_key - lo_key) if hi_key != lo_key else 0

    # Linear interpolation of a1 and r
    result = []
    for lo, hi in zip(lo_stages, hi_stages):
        result.append({
            "a1": lo["a1"] + t * (hi["a1"] - lo["a1"]),
            "r": lo["r"] + t * (hi["r"] - lo["r"]),
            "flag": lo["flag"],  # Don't interpolate flag
        })
    return result


def process_filter(signal, stages, sr):
    """Process signal through filter cascade."""
    x = signal.copy()

    for i, stage in enumerate(stages):
        if stage["r"] <= 0 or stage["r"] >= 1:
            continue  # Skip invalid stages

        base_freq = polar_to_freq(stage["a1"], stage["r"], sr)

        if stage["flag"] == 1:
            original_q = 1.0 / (2.0 * (1.0 - stage["r"]))
            effective_q = max(0.5, min(original_q * Q_SCALE, 100.0))
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


def compute_rms(signal):
    return np.sqrt(np.mean(signal**2))


def main():
    pink, sr = load_wav("validation/bypassed-pinknoise.wav")

    print("="*70)
    print("MORPH SWEEP TEST (Talking Hedz preset)")
    print("="*70)
    print(f"\nUsing Q_SCALE={Q_SCALE}, GAIN_DB={GAIN_DB}")
    print(f"\n{'Morph':<8} {'Stage 0 Hz':<12} {'Stage 1 Hz':<12} {'Stage 2 Hz':<12} {'Stage 3 Hz':<12} {'Output RMS':<12}")
    print("-" * 70)

    morph_values = [0.0, 0.125, 0.25, 0.375, 0.5, 0.625, 0.75, 0.875, 1.0]

    for morph in morph_values:
        stages = interpolate_stages(morph)

        # Get decoded frequencies for display
        freqs = []
        for stage in stages[:4]:  # First 4 peaking stages
            if stage["flag"] == 1:
                f = polar_to_freq(stage["a1"], stage["r"], sr)
                freqs.append(f)
            else:
                freqs.append(0)

        # Process and compute output RMS
        output = process_filter(pink, stages, sr)
        out_rms = compute_rms(output)
        out_db = 20 * np.log10(out_rms + 1e-10)

        print(f"{morph*100:5.1f}%   {freqs[0]:8.1f} Hz   {freqs[1]:8.1f} Hz   {freqs[2]:8.1f} Hz   {freqs[3]:8.1f} Hz   {out_db:+.1f} dB")

    # Detailed analysis at keyframes
    print(f"\n{'='*70}")
    print("KEYFRAME ANALYSIS")
    print(f"{'='*70}")

    for morph_key in sorted(TALKING_HEDZ.keys()):
        stages = TALKING_HEDZ[morph_key]
        output = process_filter(pink, stages, sr)

        freqs, spec = compute_spectrum(output, sr)
        out_rms = compute_rms(output)
        out_db = 20 * np.log10(out_rms + 1e-10)

        print(f"\nMorph {morph_key*100:.0f}%:")
        print(f"  Output RMS: {out_db:+.1f} dB")

        # Find spectral peaks
        from scipy.signal import find_peaks
        peaks_idx, props = find_peaks(spec, height=0, prominence=5)
        print(f"  Spectral peaks (>0dB):")
        for idx in peaks_idx[:5]:  # Top 5 peaks
            f = freqs[idx]
            if 50 <= f <= 8000:
                print(f"    {f:6.0f} Hz: {spec[idx]:+.1f} dB")

    # Output level consistency check
    print(f"\n{'='*70}")
    print("OUTPUT LEVEL CONSISTENCY")
    print(f"{'='*70}")

    levels = []
    for morph in np.linspace(0, 1, 21):
        stages = interpolate_stages(morph)
        output = process_filter(pink, stages, sr)
        out_rms = compute_rms(output)
        levels.append(20 * np.log10(out_rms + 1e-10))

    print(f"Output level range: {min(levels):.1f} dB to {max(levels):.1f} dB")
    print(f"Level variation: {max(levels) - min(levels):.1f} dB")
    print(f"Average level: {np.mean(levels):.1f} dB")

    if max(levels) - min(levels) > 6:
        print("\nWARNING: Large level variation across morph range!")
        print("May need gain compensation or different parameter tuning.")
    else:
        print("\nLevel variation acceptable for formant filter.")


if __name__ == "__main__":
    main()
