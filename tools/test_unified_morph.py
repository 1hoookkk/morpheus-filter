#!/usr/bin/env python3
"""
Test full morph sweep with unified gains and interpolated offsets.
"""

import numpy as np
from scipy.io import wavfile
from scipy.signal import lfilter
from scipy.fft import rfft, rfftfreq
import warnings
import os

warnings.filterwarnings('ignore', category=wavfile.WavFileWarning)

SR = 44100

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

# Unified gains (same for all morph positions)
UNIFIED_GAINS = [31.87, 30.91, 33.11, 30.54, 0.0]

# Separate offsets for endpoints
M0_OFFSETS = [140.3, 30.7, 18.4, 23.6, 0.0]
M100_OFFSETS = [67.4, 138.4, 51.0, 196.9, 0.0]

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
    x = signal.copy()

    for i in range(5):
        # Interpolate stage coefficients
        a1 = lerp(M0_Q100_STAGES[i]["a1"], M100_Q100_STAGES[i]["a1"], morph)
        r = lerp(M0_Q100_STAGES[i]["r"], M100_Q100_STAGES[i]["r"], morph)
        flag = M0_Q100_STAGES[i]["flag"]

        # Interpolate offsets (unified gains)
        offset = lerp(M0_OFFSETS[i], M100_OFFSETS[i], morph)
        gain_db = UNIFIED_GAINS[i]

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


def compute_spectrum(signal, sr, nfft=8192):
    spectrum = np.abs(rfft(signal, n=nfft))
    freqs = rfftfreq(nfft, 1/sr)
    spectrum_db = 20 * np.log10(spectrum + 1e-10)
    return freqs, spectrum_db


def spectral_error_normalized(ref_spectrum, our_spectrum, freqs, freq_range=(50, 6000)):
    mask = (freqs >= freq_range[0]) & (freqs <= freq_range[1])
    ref = ref_spectrum[mask]
    our = our_spectrum[mask]
    ref_mean = np.mean(ref)
    our_mean = np.mean(our)
    our_shifted = our + (ref_mean - our_mean)
    error = ref - our_shifted
    return np.sqrt(np.mean(error**2))


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    pink_path = os.path.join(script_dir, "..", "validation", "bypassed-pinknoise.wav")
    m0_ref_path = os.path.join(script_dir, "..", "validation", "hedzmorph0q100.wav")
    m100_ref_path = os.path.join(script_dir, "..", "validation", "hedzmorph100q100.wav")

    pink, sr = load_wav(pink_path)
    m0_ref, _ = load_wav(m0_ref_path)
    m100_ref, _ = load_wav(m100_ref_path)

    m0_ref_rms = 20 * np.log10(np.sqrt(np.mean(m0_ref**2)) + 1e-10)
    m100_ref_rms = 20 * np.log10(np.sqrt(np.mean(m100_ref**2)) + 1e-10)
    target_level = (m0_ref_rms + m100_ref_rms) / 2

    m0_ref_freqs, m0_ref_spec = compute_spectrum(m0_ref, sr)
    _, m100_ref_spec = compute_spectrum(m100_ref, sr)

    print("UNIFIED GAINS MORPH SWEEP TEST")
    print("=" * 60)
    print(f"Target level (X3 average): {target_level:+.2f} dB")
    print(f"Unified gains: {UNIFIED_GAINS[:4]}")
    print()

    morph_positions = np.linspace(0, 1, 11)
    levels = []
    compensation = []

    print("Morph   | Output   | Compensation | Spectral Error")
    print("-" * 60)

    for morph in morph_positions:
        out = process_morph(pink, morph, sr)
        rms = 20 * np.log10(np.sqrt(np.mean(out**2)) + 1e-10)
        comp = target_level - rms
        levels.append(rms)
        compensation.append(comp)

        # Calculate spectral error at endpoints
        _, out_spec = compute_spectrum(out, sr)
        if morph < 0.1:
            spec_err = spectral_error_normalized(m0_ref_spec, out_spec, m0_ref_freqs)
        elif morph > 0.9:
            spec_err = spectral_error_normalized(m100_ref_spec, out_spec, m0_ref_freqs)
        else:
            spec_err = float('nan')

        print(f"  {int(morph*100):3d}%  | {rms:+7.2f} dB | {comp:+7.2f} dB   | {spec_err:.2f} dB")

    print("-" * 60)
    print(f"Level range: {max(levels) - min(levels):.2f} dB")
    print(f"Compensation range: {max(compensation) - min(compensation):.2f} dB")

    # Fit linear compensation
    slope = (compensation[-1] - compensation[0]) / 1.0
    intercept = compensation[0]

    print("\n" + "=" * 60)
    print("COMPENSATION CURVE")
    print("=" * 60)
    print(f"\nLinear approximation: comp_dB = {intercept:.2f} + morph * {slope:.2f}")

    # Check linear fit error
    max_err = 0
    for i, morph in enumerate(morph_positions):
        linear = intercept + morph * slope
        err = abs(linear - compensation[i])
        if err > max_err:
            max_err = err
    print(f"Max linear fit error: {max_err:.2f} dB")

    # C++ code
    print("\n// Compensation formula")
    print(f"double compensationDB = {intercept:.2f} + morph * ({slope:.2f});")
    print("double compensationLinear = pow(10.0, compensationDB / 20.0);")
    print("// Apply: output *= compensationLinear;")


if __name__ == "__main__":
    main()
