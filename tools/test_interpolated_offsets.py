#!/usr/bin/env python3
"""
Test morph-dependent offset interpolation.
M0: zero offsets, M100: [65, 150, 62, 0]
Interpolate linearly between them.
"""

import numpy as np
from scipy.io import wavfile
from scipy.signal import lfilter
from scipy.fft import rfft, rfftfreq

# Validated captures (5 stages only)
M0_Q100_STAGES = [
    {"a1": -1.976510, "r": 0.998242, "flag": 1},  # 994 Hz
    {"a1": -1.938977, "r": 0.998296, "flag": 1},  # 1690 Hz
    {"a1": -1.872895, "r": 0.998353, "flag": 1},  # 2485 Hz
    {"a1": -1.523842, "r": 0.992409, "flag": 1},  # 4881 Hz
    {"a1": -1.997572, "r": 0.998289, "flag": 0},  # Lowpass
]

M100_Q100_STAGES = [
    {"a1": -1.996743, "r": 0.998619, "flag": 1},  # 156 Hz
    {"a1": -1.894098, "r": 0.998437, "flag": 1},  # 2262 Hz
    {"a1": -1.854829, "r": 0.998353, "flag": 1},  # 2662 Hz
    {"a1": -1.495171, "r": 0.963737, "flag": 1},  # 4793 Hz
    {"a1": -1.974292, "r": 0.998195, "flag": 0},  # Lowpass 1045 Hz
]

# Validated offset endpoints
M0_OFFSETS = [0, 0, 0, 0, 0]
M100_OFFSETS = [65, 150, 62, 0, 0]

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


def interpolate_stages(morph):
    """Interpolate coefficients between M0 and M100."""
    result = []
    for s0, s100 in zip(M0_Q100_STAGES, M100_Q100_STAGES):
        result.append({
            "a1": s0["a1"] + morph * (s100["a1"] - s0["a1"]),
            "r": s0["r"] + morph * (s100["r"] - s0["r"]),
            "flag": s0["flag"],
        })
    return result


def interpolate_offsets(morph):
    """Interpolate frequency offsets with morph."""
    return [
        M0_OFFSETS[i] + morph * (M100_OFFSETS[i] - M0_OFFSETS[i])
        for i in range(len(M0_OFFSETS))
    ]


def process_filter(signal, stages, sr, freq_offsets):
    x = signal.copy()
    for i, stage in enumerate(stages):
        if stage["r"] <= 0 or stage["r"] >= 1:
            continue
        base_freq = polar_to_freq(stage["a1"], stage["r"], sr)
        if stage["flag"] == 1:
            freq = base_freq + freq_offsets[i]
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


def compute_rms(signal):
    return np.sqrt(np.mean(signal**2))


def main():
    pink, sr = load_wav("validation/bypassed-pinknoise.wav")

    print("="*70)
    print("INTERPOLATED OFFSET TEST")
    print("="*70)
    print(f"\nOffset endpoints:")
    print(f"  M0:   {M0_OFFSETS[:4]}")
    print(f"  M100: {M100_OFFSETS[:4]}")

    print(f"\n{'Morph':<8} {'Offsets':<30} {'Output RMS':<12}")
    print("-" * 55)

    morph_values = [0.0, 0.25, 0.5, 0.75, 1.0]
    for morph in morph_values:
        stages = interpolate_stages(morph)
        offsets = interpolate_offsets(morph)

        output = process_filter(pink, stages, sr, offsets)
        rms = compute_rms(output)
        rms_db = 20 * np.log10(rms + 1e-10)

        offset_str = f"[{offsets[0]:.0f}, {offsets[1]:.0f}, {offsets[2]:.0f}, {offsets[3]:.0f}]"
        print(f"{morph*100:5.0f}%   {offset_str:<30} {rms_db:+.1f} dB")

    # Compare with and without offset interpolation
    print(f"\n{'='*70}")
    print("COMPARISON: Fixed M100 Offsets vs Interpolated")
    print(f"{'='*70}")

    print(f"\n{'Morph':<8} {'Fixed M100':<15} {'Interpolated':<15} {'Zero Offset':<15}")
    print("-" * 55)

    for morph in morph_values:
        stages = interpolate_stages(morph)

        # With fixed M100 offsets everywhere
        output = process_filter(pink, stages, sr, M100_OFFSETS)
        rms_fixed = 20 * np.log10(compute_rms(output) + 1e-10)

        # With interpolated offsets
        offsets = interpolate_offsets(morph)
        output = process_filter(pink, stages, sr, offsets)
        rms_interp = 20 * np.log10(compute_rms(output) + 1e-10)

        # With zero offsets
        output = process_filter(pink, stages, sr, [0]*5)
        rms_zero = 20 * np.log10(compute_rms(output) + 1e-10)

        print(f"{morph*100:5.0f}%   {rms_fixed:+.1f} dB        {rms_interp:+.1f} dB        {rms_zero:+.1f} dB")

    # Decode frequencies to show the morph effect
    print(f"\n{'='*70}")
    print("DECODED FREQUENCIES ACROSS MORPH")
    print(f"{'='*70}")

    print(f"\n{'Morph':<8} {'Stage 0':<12} {'Stage 1':<12} {'Stage 2':<12} {'Stage 3':<12}")
    print("-" * 55)

    for morph in morph_values:
        stages = interpolate_stages(morph)
        freqs = [polar_to_freq(s["a1"], s["r"], sr) for s in stages[:4]]
        offsets = interpolate_offsets(morph)
        adjusted = [freqs[i] + offsets[i] for i in range(4)]

        print(f"{morph*100:5.0f}%   {adjusted[0]:8.0f} Hz  {adjusted[1]:8.0f} Hz  {adjusted[2]:8.0f} Hz  {adjusted[3]:8.0f} Hz")

    print(f"\n{'='*70}")
    print("RECOMMENDATION")
    print(f"{'='*70}")
    print("""
Interpolate offsets linearly with morph parameter:

    offset[i] = M0_OFFSET[i] + morph * (M100_OFFSET[i] - M0_OFFSET[i])

This ensures:
- M0 uses zero offsets (best for M0_Q100)
- M100 uses [65, 150, 62, 0] (best for M100_Q100)
- In-between values are smoothly interpolated

C++ implementation:
    static constexpr double M100_OFFSETS[7] = {65, 150, 62, 0, 0, 0, 0};
    double offset = morphParam * M100_OFFSETS[stageIndex];
    freqHz += offset;
""")


if __name__ == "__main__":
    main()
