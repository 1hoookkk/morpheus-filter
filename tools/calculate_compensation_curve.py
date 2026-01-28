#!/usr/bin/env python3
"""
Calculate the exact output level compensation curve needed
when using interpolated optimized gains.

This uses the M0 and M100 optimized gains and interpolates between them,
then calculates what compensation is needed at each morph position to
match the X3 reference levels.
"""

import numpy as np
from scipy.io import wavfile
from scipy.signal import lfilter
import warnings
import os

warnings.filterwarnings('ignore', category=wavfile.WavFileWarning)

SR = 44100

# Optimized gains from joint optimization
M0_GAINS = [78.76, 55.24, 41.88, 70.21, 0.0]
M100_GAINS = [60.0, 41.74, 33.05, 38.90, 0.0]

M0_OFFSETS = [41.3, 19.3, 18.2, 27.2, 0.0]
M100_OFFSETS = [65.8, 149.8, 58.7, 200.0, 0.0]

# Captured coefficients
M0_Q100_STAGES = [
    {"a1": -1.974805, "r": 0.998231, "flag": 1.0},
    {"a1": -1.939721, "r": 0.998292, "flag": 1.0},
    {"a1": -1.873399, "r": 0.998353, "flag": 1.0},
    {"a1": -1.524112, "r": 0.992679, "flag": 1.0},
    {"a1": -1.997652, "r": 0.998292, "flag": 0.0},
]

M100_Q100_STAGES = [
    {"a1": -1.996743, "r": 0.998619, "flag": 1.0},
    {"a1": -1.894098, "r": 0.998437, "flag": 1.0},
    {"a1": -1.854829, "r": 0.998353, "flag": 1.0},
    {"a1": -1.495171, "r": 0.963737, "flag": 1.0},
    {"a1": -1.974292, "r": 0.998195, "flag": 0.0},
]

Q_SCALE = 0.08


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


def lerp(a, b, t):
    return a + t * (b - a)


def process_morph(signal, morph, sr):
    """Process with interpolated optimized gains and offsets."""
    x = signal.copy()

    for i in range(5):
        # Interpolate coefficients
        a1 = lerp(M0_Q100_STAGES[i]["a1"], M100_Q100_STAGES[i]["a1"], morph)
        r = lerp(M0_Q100_STAGES[i]["r"], M100_Q100_STAGES[i]["r"], morph)
        flag = M0_Q100_STAGES[i]["flag"]

        # Interpolate gains and offsets
        gain_db = lerp(M0_GAINS[i], M100_GAINS[i], morph)
        offset = lerp(M0_OFFSETS[i], M100_OFFSETS[i], morph)

        base_freq = polar_to_freq(a1, r, sr)
        original_q = 1.0 / (2.0 * (1.0 - r))

        if flag > 0.5:
            freq = base_freq + offset
            effective_q = original_q * Q_SCALE
            effective_q = max(0.5, min(effective_q, 100.0))
            b, a = make_peaking_eq(freq, effective_q, gain_db, sr)
        else:
            b, a = make_lowpass_rbj(base_freq, 0.707, sr)

        x = lfilter(b, a, x)

    return x


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    pink_path = os.path.join(script_dir, "..", "validation", "bypassed-pinknoise.wav")
    m0_ref_path = os.path.join(script_dir, "..", "validation", "hedzmorph0q100.wav")
    m100_ref_path = os.path.join(script_dir, "..", "validation", "hedzmorph100q100.wav")

    pink, sr = load_wav(pink_path)
    m0_ref, _ = load_wav(m0_ref_path)
    m100_ref, _ = load_wav(m100_ref_path)

    # X3 reference levels
    m0_ref_rms = 20 * np.log10(np.sqrt(np.mean(m0_ref**2)) + 1e-10)
    m100_ref_rms = 20 * np.log10(np.sqrt(np.mean(m100_ref**2)) + 1e-10)

    print("X3 Reference Levels:")
    print(f"  M0_Q100:   {m0_ref_rms:+.2f} dB")
    print(f"  M100_Q100: {m100_ref_rms:+.2f} dB")
    print(f"  Range: {abs(m0_ref_rms - m100_ref_rms):.2f} dB")

    # Calculate our output levels at each morph position
    print("\n" + "=" * 60)
    print("OUTPUT LEVELS WITH INTERPOLATED OPTIMIZED GAINS")
    print("=" * 60)

    morph_positions = np.linspace(0, 1, 21)  # 5% increments
    our_levels = []

    for morph in morph_positions:
        out = process_morph(pink, morph, sr)
        rms = 20 * np.log10(np.sqrt(np.mean(out**2)) + 1e-10)
        our_levels.append(rms)
        print(f"  Morph {int(morph*100):3d}%: {rms:+.2f} dB")

    # Calculate compensation needed to match X3
    # X3 level is approximately constant at average of M0 and M100
    target_level = (m0_ref_rms + m100_ref_rms) / 2

    print(f"\nTarget level (X3 average): {target_level:+.2f} dB")
    print("\n" + "=" * 60)
    print("COMPENSATION CURVE (to match X3)")
    print("=" * 60)

    compensation = []
    for i, morph in enumerate(morph_positions):
        comp = target_level - our_levels[i]
        compensation.append(comp)
        print(f"  Morph {int(morph*100):3d}%: {comp:+.2f} dB compensation")

    # Output C++ code
    print("\n" + "=" * 60)
    print("C++ COMPENSATION TABLE")
    print("=" * 60)

    print("\n// Compensation curve (21 points, 5% increments)")
    print("// Apply as: output *= pow(10.0, compensation[morphIndex] / 20.0)")
    print("static constexpr double MORPH_COMPENSATION_DB[21] = {")
    for i, comp in enumerate(compensation):
        comma = "," if i < len(compensation) - 1 else ""
        print(f"    {comp:+.2f}{comma}  // {int(morph_positions[i]*100)}%")
    print("};")

    # Also output a simpler linear approximation
    print("\n// Or use linear approximation:")
    slope = (compensation[-1] - compensation[0]) / 1.0
    intercept = compensation[0]
    print(f"// compensation_dB = {intercept:.2f} + morph * {slope:.2f}")

    # Test linear approximation error
    max_linear_error = 0
    for i, morph in enumerate(morph_positions):
        linear_comp = intercept + morph * slope
        error = abs(linear_comp - compensation[i])
        if error > max_linear_error:
            max_linear_error = error
    print(f"// Max linear approximation error: {max_linear_error:.2f} dB")

    # Verify compensation works
    print("\n" + "=" * 60)
    print("VERIFICATION (after compensation)")
    print("=" * 60)

    for i, morph in enumerate(morph_positions):
        compensated_level = our_levels[i] + compensation[i]
        error = compensated_level - target_level
        if i % 4 == 0:  # Print every 20%
            print(f"  Morph {int(morph*100):3d}%: {compensated_level:+.2f} dB (error: {error:+.2f} dB)")


if __name__ == "__main__":
    main()
