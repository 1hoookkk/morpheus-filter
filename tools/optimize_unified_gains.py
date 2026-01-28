#!/usr/bin/env python3
"""
Find a SINGLE set of per-stage gains that works well at BOTH M0 and M100.

This avoids the wild level swings from interpolating between very different gains.
The idea: one set of gains, different offsets per morph, plus output compensation.
"""

import numpy as np
from scipy.io import wavfile
from scipy.signal import lfilter
from scipy.fft import rfft, rfftfreq
from scipy.optimize import differential_evolution
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

Q_SCALE = 0.08

PINK_NOISE = None
M0_REF_SPECTRUM = None
M100_REF_SPECTRUM = None
REF_FREQS = None
M0_REF_RMS = None
M100_REF_RMS = None


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


def process_filter(signal, stages, sr, gains, offsets):
    x = signal.copy()
    for i, stage in enumerate(stages):
        base_freq = polar_to_freq(stage["a1"], stage["r"], sr)
        original_q = 1.0 / (2.0 * (1.0 - stage["r"]))
        if stage["flag"] > 0.5:
            freq = base_freq + offsets[i]
            effective_q = original_q * Q_SCALE
            effective_q = max(0.5, min(effective_q, 100.0))
            b, a = make_peaking_eq(freq, effective_q, gains[i], sr)
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


def objective_function(params):
    """
    Optimize UNIFIED gains (same for M0 and M100) plus separate offsets.
    params = [g0, g1, g2, g3,  # unified gains
              m0_off0, m0_off1, m0_off2, m0_off3,  # M0 offsets
              m100_off0, m100_off1, m100_off2, m100_off3]  # M100 offsets
    """
    global PINK_NOISE, M0_REF_SPECTRUM, M100_REF_SPECTRUM, REF_FREQS
    global M0_REF_RMS, M100_REF_RMS

    gains = list(params[:4]) + [0.0]
    m0_offsets = list(params[4:8]) + [0.0]
    m100_offsets = list(params[8:12]) + [0.0]

    # Process M0
    m0_out = process_filter(PINK_NOISE, M0_Q100_STAGES, SR, gains, m0_offsets)
    if np.any(np.isnan(m0_out)) or np.any(np.isinf(m0_out)):
        return 200.0

    # Process M100
    m100_out = process_filter(PINK_NOISE, M100_Q100_STAGES, SR, gains, m100_offsets)
    if np.any(np.isnan(m100_out)) or np.any(np.isinf(m100_out)):
        return 200.0

    # Spectral errors
    _, m0_spec = compute_spectrum(m0_out, SR)
    _, m100_spec = compute_spectrum(m100_out, SR)
    m0_spectral_err = spectral_error_normalized(M0_REF_SPECTRUM, m0_spec, REF_FREQS)
    m100_spectral_err = spectral_error_normalized(M100_REF_SPECTRUM, m100_spec, REF_FREQS)

    # Level errors
    m0_rms = 20 * np.log10(np.sqrt(np.mean(m0_out**2)) + 1e-10)
    m100_rms = 20 * np.log10(np.sqrt(np.mean(m100_out**2)) + 1e-10)
    m0_level_err = abs(m0_rms - M0_REF_RMS)
    m100_level_err = abs(m100_rms - M100_REF_RMS)

    # Combined objective: spectral + level
    spectral_weight = 1.0
    level_weight = 0.5  # Less weight on level since we'll compensate anyway

    return (spectral_weight * (m0_spectral_err + m100_spectral_err) +
            level_weight * (m0_level_err + m100_level_err))


def main():
    global PINK_NOISE, M0_REF_SPECTRUM, M100_REF_SPECTRUM, REF_FREQS
    global M0_REF_RMS, M100_REF_RMS

    script_dir = os.path.dirname(os.path.abspath(__file__))
    pink_path = os.path.join(script_dir, "..", "validation", "bypassed-pinknoise.wav")
    m0_ref_path = os.path.join(script_dir, "..", "validation", "hedzmorph0q100.wav")
    m100_ref_path = os.path.join(script_dir, "..", "validation", "hedzmorph100q100.wav")

    print("Loading files...")
    PINK_NOISE, sr = load_wav(pink_path)
    m0_ref, _ = load_wav(m0_ref_path)
    m100_ref, _ = load_wav(m100_ref_path)

    REF_FREQS, M0_REF_SPECTRUM = compute_spectrum(m0_ref, sr)
    _, M100_REF_SPECTRUM = compute_spectrum(m100_ref, sr)

    M0_REF_RMS = 20 * np.log10(np.sqrt(np.mean(m0_ref**2)) + 1e-10)
    M100_REF_RMS = 20 * np.log10(np.sqrt(np.mean(m100_ref**2)) + 1e-10)

    print(f"Target M0 level: {M0_REF_RMS:+.1f} dB")
    print(f"Target M100 level: {M100_REF_RMS:+.1f} dB")

    # Optimization bounds
    # 4 unified gains + 4 M0 offsets + 4 M100 offsets = 12 parameters
    bounds = [
        (20.0, 80.0), (20.0, 80.0), (20.0, 80.0), (20.0, 80.0),  # gains
        (-100.0, 200.0), (-100.0, 200.0), (-100.0, 200.0), (-100.0, 200.0),  # M0 offsets
        (-100.0, 200.0), (-100.0, 200.0), (-100.0, 200.0), (-100.0, 200.0),  # M100 offsets
    ]

    print("\nOptimizing unified gains with separate offsets...")
    result = differential_evolution(
        objective_function, bounds,
        maxiter=150, workers=1, seed=42, polish=True, tol=0.005, disp=True
    )

    gains = list(result.x[:4]) + [0.0]
    m0_offsets = list(result.x[4:8]) + [0.0]
    m100_offsets = list(result.x[8:12]) + [0.0]

    # Evaluate results
    m0_out = process_filter(PINK_NOISE, M0_Q100_STAGES, sr, gains, m0_offsets)
    m100_out = process_filter(PINK_NOISE, M100_Q100_STAGES, sr, gains, m100_offsets)

    _, m0_spec = compute_spectrum(m0_out, sr)
    _, m100_spec = compute_spectrum(m100_out, sr)

    m0_err = spectral_error_normalized(M0_REF_SPECTRUM, m0_spec, REF_FREQS)
    m100_err = spectral_error_normalized(M100_REF_SPECTRUM, m100_spec, REF_FREQS)

    m0_rms = 20 * np.log10(np.sqrt(np.mean(m0_out**2)) + 1e-10)
    m100_rms = 20 * np.log10(np.sqrt(np.mean(m100_out**2)) + 1e-10)

    print("\n" + "=" * 60)
    print("UNIFIED GAINS OPTIMIZATION RESULTS")
    print("=" * 60)

    print("\nUnified gains (same for M0 and M100):")
    for i, g in enumerate(gains[:4]):
        m0_freq = polar_to_freq(M0_Q100_STAGES[i]["a1"], M0_Q100_STAGES[i]["r"])
        m100_freq = polar_to_freq(M100_Q100_STAGES[i]["a1"], M100_Q100_STAGES[i]["r"])
        print(f"  Stage {i}: {g:6.2f} dB (M0: {m0_freq:.0f} Hz, M100: {m100_freq:.0f} Hz)")

    print("\nM0 offsets (Hz):")
    for i, o in enumerate(m0_offsets[:4]):
        print(f"  Stage {i}: {o:+7.2f} Hz")

    print("\nM100 offsets (Hz):")
    for i, o in enumerate(m100_offsets[:4]):
        print(f"  Stage {i}: {o:+7.2f} Hz")

    print(f"\nM0 spectral error: {m0_err:.2f} dB")
    print(f"M100 spectral error: {m100_err:.2f} dB")
    print(f"Average spectral error: {(m0_err + m100_err) / 2:.2f} dB")

    print(f"\nM0 level: {m0_rms:+.1f} dB (target: {M0_REF_RMS:+.1f} dB, error: {m0_rms - M0_REF_RMS:+.1f} dB)")
    print(f"M100 level: {m100_rms:+.1f} dB (target: {M100_REF_RMS:+.1f} dB, error: {m100_rms - M100_REF_RMS:+.1f} dB)")
    print(f"Level range: {abs(m0_rms - m100_rms):.1f} dB (X3 range: 0.6 dB)")

    # C++ output
    print("\n" + "=" * 60)
    print("C++ CODE")
    print("=" * 60)

    print("\n// Unified gains (same for all morph positions)")
    print("static constexpr double UNIFIED_GAINS_DB[5] = {")
    for g in gains:
        print(f"    {g:.2f},")
    print("};")

    print("\n// M0 offsets")
    print("static constexpr double M0_OFFSETS[5] = {")
    for o in m0_offsets:
        print(f"    {o:.1f},")
    print("};")

    print("\n// M100 offsets")
    print("static constexpr double M100_OFFSETS[5] = {")
    for o in m100_offsets:
        print(f"    {o:.1f},")
    print("};")


if __name__ == "__main__":
    main()
