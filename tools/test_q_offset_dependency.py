#!/usr/bin/env python3
"""
Test if frequency offsets depend on Q knob setting.
If offsets change with Q, we need 2D interpolation (morph, Q).
"""

import numpy as np
from scipy.io import wavfile
from scipy.signal import lfilter
from scipy.fft import rfft, rfftfreq

# Validated M100 captures at different Q levels
M100_Q100_STAGES = [
    {"a1": -1.996743, "r": 0.998619, "flag": 1},  # 156 Hz
    {"a1": -1.894098, "r": 0.998437, "flag": 1},  # 2262 Hz
    {"a1": -1.854829, "r": 0.998353, "flag": 1},  # 2662 Hz
    {"a1": -1.495171, "r": 0.963737, "flag": 1},  # 4793 Hz
    {"a1": -1.974292, "r": 0.998195, "flag": 0},  # Lowpass 1045 Hz
]

M100_Q0_STAGES = [
    {"a1": -1.986418, "r": 0.987503, "flag": 1},  # ~DC (clamped)
    {"a1": -1.837391, "r": 0.974537, "flag": 1},  # 2388 Hz
    {"a1": -1.794609, "r": 0.977806, "flag": 1},  # 2868 Hz
    {"a1": -1.362762, "r": 0.883514, "flag": 1},  # 4843 Hz
    {"a1": -1.914935, "r": 0.993960, "flag": 0},  # Lowpass 1908 Hz
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


def process_filter(signal, stages, sr, freq_offsets):
    x = signal.copy()
    for i, stage in enumerate(stages):
        if stage["r"] <= 0 or stage["r"] >= 1:
            continue
        base_freq = polar_to_freq(stage["a1"], stage["r"], sr)
        if stage["flag"] == 1:
            freq = base_freq + freq_offsets[i] if i < len(freq_offsets) else base_freq
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


def find_optimal_offsets(pink, stages, sr, ref_spectrum, ref_freqs):
    """Find optimal offsets for given stages."""
    best_error = float('inf')
    best_offsets = [0, 0, 0, 0, 0]

    for o0 in [0, 50, 65, 100, 150, 200]:
        for o1 in [0, 50, 100, 150, 200]:
            for o2 in [0, 50, 62, 100]:
                offsets = [o0, o1, o2, 0, 0]
                output = process_filter(pink, stages, sr, offsets)
                if np.any(np.isnan(output)) or np.any(np.isinf(output)):
                    continue
                _, our_spec = compute_spectrum(output, sr)
                error = compare_spectra(ref_spectrum, our_spec, ref_freqs)
                if error < best_error:
                    best_error = error
                    best_offsets = offsets.copy()

    return best_offsets[:3], best_error


def main():
    pink, sr = load_wav("validation/bypassed-pinknoise.wav")

    # Load both Q levels
    ref_q100, _ = load_wav("validation/hedzmorph100q100.wav")
    ref_q0, _ = load_wav("validation/hedzmorph100q0.wav")

    ref_freqs, ref_q100_spec = compute_spectrum(ref_q100, sr)
    _, ref_q0_spec = compute_spectrum(ref_q0, sr)

    print("="*70)
    print("Q-DEPENDENCY OF FREQUENCY OFFSETS")
    print("="*70)
    print(f"\nUsing Q_SCALE={Q_SCALE}, GAIN_DB={GAIN_DB}")

    # Test M100_Q100
    print(f"\n{'='*70}")
    print("M100_Q100")
    print(f"{'='*70}")

    decoded_freqs = [polar_to_freq(s["a1"], s["r"], sr) for s in M100_Q100_STAGES[:4]]
    print(f"Decoded frequencies: {[f'{f:.0f} Hz' for f in decoded_freqs]}")

    # Baseline
    output = process_filter(pink, M100_Q100_STAGES, sr, [0]*5)
    _, our_spec = compute_spectrum(output, sr)
    baseline = compare_spectra(ref_q100_spec, our_spec, ref_freqs)
    print(f"Baseline: {baseline:.3f} dB")

    # With validated offsets
    output = process_filter(pink, M100_Q100_STAGES, sr, [65, 150, 62, 0, 0])
    _, our_spec = compute_spectrum(output, sr)
    with_offsets = compare_spectra(ref_q100_spec, our_spec, ref_freqs)
    print(f"With [65, 150, 62, 0]: {with_offsets:.3f} dB")

    # Find optimal
    best_offsets_q100, best_error_q100 = find_optimal_offsets(
        pink, M100_Q100_STAGES, sr, ref_q100_spec, ref_freqs
    )
    print(f"Optimal offsets: {best_offsets_q100} → {best_error_q100:.3f} dB")

    # Test M100_Q0
    print(f"\n{'='*70}")
    print("M100_Q0")
    print(f"{'='*70}")

    decoded_freqs = [polar_to_freq(s["a1"], s["r"], sr) for s in M100_Q0_STAGES[:4]]
    print(f"Decoded frequencies: {[f'{f:.0f} Hz' for f in decoded_freqs]}")

    # Baseline
    output = process_filter(pink, M100_Q0_STAGES, sr, [0]*5)
    _, our_spec = compute_spectrum(output, sr)
    baseline = compare_spectra(ref_q0_spec, our_spec, ref_freqs)
    print(f"Baseline: {baseline:.3f} dB")

    # With Q100 offsets
    output = process_filter(pink, M100_Q0_STAGES, sr, [65, 150, 62, 0, 0])
    _, our_spec = compute_spectrum(output, sr)
    with_q100_offsets = compare_spectra(ref_q0_spec, our_spec, ref_freqs)
    print(f"With Q100 offsets [65, 150, 62, 0]: {with_q100_offsets:.3f} dB")

    # Find optimal for Q0
    best_offsets_q0, best_error_q0 = find_optimal_offsets(
        pink, M100_Q0_STAGES, sr, ref_q0_spec, ref_freqs
    )
    print(f"Optimal offsets: {best_offsets_q0} → {best_error_q0:.3f} dB")

    # Analysis
    print(f"\n{'='*70}")
    print("ANALYSIS: Does Q affect optimal offsets?")
    print(f"{'='*70}")

    print(f"\n{'Setting':<15} {'Optimal Offsets':<25} {'Error':<10}")
    print("-" * 50)
    print(f"{'M100_Q100':<15} {str(best_offsets_q100):<25} {best_error_q100:.3f} dB")
    print(f"{'M100_Q0':<15} {str(best_offsets_q0):<25} {best_error_q0:.3f} dB")

    # Check if offsets differ significantly
    if best_offsets_q100 == best_offsets_q0:
        print("\nOFFSETS ARE THE SAME - No Q dependency!")
        print("→ Use same offsets for all Q values")
    else:
        print("\nOFFSETS DIFFER - Q affects optimal offsets!")
        print("→ Consider interpolating offsets with Q as well as morph")
        print(f"   Stage 0: Q100={best_offsets_q100[0]}, Q0={best_offsets_q0[0]}")
        print(f"   Stage 1: Q100={best_offsets_q100[1]}, Q0={best_offsets_q0[1]}")
        print(f"   Stage 2: Q100={best_offsets_q100[2]}, Q0={best_offsets_q0[2]}")


if __name__ == "__main__":
    main()
