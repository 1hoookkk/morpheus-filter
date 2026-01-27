#!/usr/bin/env python3
"""
Analyze the lowpass stage contribution to spectral error.
Check if the decoded lowpass cutoff matches X3's actual rolloff.
"""

import numpy as np
from scipy.io import wavfile
from scipy.signal import lfilter, find_peaks
from scipy.fft import rfft, rfftfreq

# Captured coefficients with lowpass stage
M100_Q100_STAGES = [
    {"a1": -1.996743, "r": 0.998619, "flag": 1},
    {"a1": -1.894098, "r": 0.998437, "flag": 1},
    {"a1": -1.854829, "r": 0.998353, "flag": 1},
    {"a1": -1.495171, "r": 0.963737, "flag": 1},
    {"a1": -1.974292, "r": 0.998195, "flag": 0},  # LOWPASS
]

M0_Q100_STAGES = [
    {"a1": -1.976510, "r": 0.998242, "flag": 1},
    {"a1": -1.938977, "r": 0.998296, "flag": 1},
    {"a1": -1.872895, "r": 0.998353, "flag": 1},
    {"a1": -1.523842, "r": 0.992409, "flag": 1},
    {"a1": -1.997572, "r": 0.998289, "flag": 0},  # LOWPASS
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


def process_without_lowpass(signal, stages, sr, freq_offsets):
    """Process resonator stages only (skip lowpass)."""
    x = signal.copy()
    for i, stage in enumerate(stages):
        if stage["flag"] != 1:  # Skip lowpass
            continue
        base_freq = polar_to_freq(stage["a1"], stage["r"], sr)
        freq = base_freq + freq_offsets[i]
        original_q = 1.0 / (2.0 * (1.0 - stage["r"]))
        effective_q = max(0.5, min(original_q * Q_SCALE, 100.0))
        b, a = make_peaking_eq(freq, effective_q, GAIN_DB, sr)
        x = lfilter(b, a, x)
    return x


def process_with_lowpass(signal, stages, sr, freq_offsets, lp_cutoff=None):
    """Process all stages including lowpass."""
    x = signal.copy()
    for i, stage in enumerate(stages):
        base_freq = polar_to_freq(stage["a1"], stage["r"], sr)
        if stage["flag"] == 1:
            freq = base_freq + freq_offsets[i]
            original_q = 1.0 / (2.0 * (1.0 - stage["r"]))
            effective_q = max(0.5, min(original_q * Q_SCALE, 100.0))
            b, a = make_peaking_eq(freq, effective_q, GAIN_DB, sr)
        else:
            # Lowpass - use override cutoff if provided
            freq = lp_cutoff if lp_cutoff else base_freq
            freq = max(freq, 20)  # Minimum 20 Hz
            b, a = make_lowpass_rbj(freq, 0.707, sr)
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


def estimate_rolloff(freqs, spectrum_db):
    """Find the -3dB rolloff point from peak."""
    max_db = np.max(spectrum_db)
    target_db = max_db - 3.0

    # Find high frequency where it drops below -3dB
    high_mask = freqs > 1000  # Look above 1kHz
    high_freqs = freqs[high_mask]
    high_spec = spectrum_db[high_mask]

    # Find first frequency where it's consistently below target
    for i in range(len(high_freqs) - 10):
        if np.all(high_spec[i:i+10] < target_db):
            return high_freqs[i]
    return None


def main():
    pink, sr = load_wav("validation/bypassed-pinknoise.wav")

    # Load both references
    ref_m100, _ = load_wav("validation/hedzmorph100q100.wav")
    ref_m0, _ = load_wav("validation/hedzmorph0q100.wav")

    ref_freqs, ref_m100_spec = compute_spectrum(ref_m100, sr)
    _, ref_m0_spec = compute_spectrum(ref_m0, sr)

    # Analyze X3 reference rolloff
    print("="*70)
    print("X3 REFERENCE HIGH-FREQUENCY ANALYSIS")
    print("="*70)

    # Find approximate -3dB rolloff
    m100_rolloff = estimate_rolloff(ref_freqs, ref_m100_spec)
    m0_rolloff = estimate_rolloff(ref_freqs, ref_m0_spec)

    print(f"\nM100_Q100 estimated -3dB rolloff: {m100_rolloff:.0f} Hz" if m100_rolloff else "N/A")
    print(f"M0_Q100 estimated -3dB rolloff: {m0_rolloff:.0f} Hz" if m0_rolloff else "N/A")

    # Compare decoded lowpass cutoffs
    lp_m100 = polar_to_freq(M100_Q100_STAGES[4]["a1"], M100_Q100_STAGES[4]["r"], sr)
    lp_m0 = polar_to_freq(M0_Q100_STAGES[4]["a1"], M0_Q100_STAGES[4]["r"], sr)

    print(f"\nDecoded lowpass cutoffs:")
    print(f"  M100_Q100: {lp_m100:.1f} Hz")
    print(f"  M0_Q100: {lp_m0:.1f} Hz")

    # Test M100_Q100 with different lowpass settings
    print(f"\n{'='*70}")
    print("M100_Q100: LOWPASS CUTOFF SWEEP")
    print(f"{'='*70}")

    freq_offsets = [65, 150, 62, 0, 0]  # M100 calibrated offsets

    # Without lowpass
    output_no_lp = process_without_lowpass(pink, M100_Q100_STAGES, sr, freq_offsets)
    _, our_spec = compute_spectrum(output_no_lp, sr)
    error_no_lp = compare_spectra(ref_m100_spec, our_spec, ref_freqs)
    print(f"No lowpass stage: {error_no_lp:.3f} dB")

    # With decoded cutoff
    output = process_with_lowpass(pink, M100_Q100_STAGES, sr, freq_offsets)
    _, our_spec = compute_spectrum(output, sr)
    error_decoded = compare_spectra(ref_m100_spec, our_spec, ref_freqs)
    print(f"Decoded cutoff ({lp_m100:.0f} Hz): {error_decoded:.3f} dB")

    # Sweep different cutoffs
    print(f"\nLowpass cutoff sweep:")
    results = []
    for cutoff in [500, 750, 1000, 1500, 2000, 2500, 3000, 4000, 5000, 6000, 8000, 10000, 15000, 20000]:
        output = process_with_lowpass(pink, M100_Q100_STAGES, sr, freq_offsets, lp_cutoff=cutoff)
        _, our_spec = compute_spectrum(output, sr)
        error = compare_spectra(ref_m100_spec, our_spec, ref_freqs)
        results.append((cutoff, error))
        print(f"  {cutoff:5d} Hz: {error:.3f} dB")

    results.sort(key=lambda x: x[1])
    best_cutoff, best_error = results[0]
    print(f"\nBest lowpass cutoff: {best_cutoff} Hz → {best_error:.3f} dB")

    # Test M0_Q100
    print(f"\n{'='*70}")
    print("M0_Q100: LOWPASS CUTOFF SWEEP")
    print(f"{'='*70}")

    freq_offsets_m0 = [0, 0, 0, 0, 0]  # M0 needs no offsets

    # Without lowpass
    output_no_lp = process_without_lowpass(pink, M0_Q100_STAGES, sr, freq_offsets_m0)
    _, our_spec = compute_spectrum(output_no_lp, sr)
    error_no_lp = compare_spectra(ref_m0_spec, our_spec, ref_freqs)
    print(f"No lowpass stage: {error_no_lp:.3f} dB")

    # With decoded cutoff (very low/DC)
    output = process_with_lowpass(pink, M0_Q100_STAGES, sr, freq_offsets_m0)
    _, our_spec = compute_spectrum(output, sr)
    error_decoded = compare_spectra(ref_m0_spec, our_spec, ref_freqs)
    print(f"Decoded cutoff ({lp_m0:.0f} Hz): {error_decoded:.3f} dB")

    # Sweep different cutoffs
    print(f"\nLowpass cutoff sweep:")
    results = []
    for cutoff in [500, 750, 1000, 1500, 2000, 2500, 3000, 4000, 5000, 6000, 8000, 10000, 15000, 20000]:
        output = process_with_lowpass(pink, M0_Q100_STAGES, sr, freq_offsets_m0, lp_cutoff=cutoff)
        _, our_spec = compute_spectrum(output, sr)
        error = compare_spectra(ref_m0_spec, our_spec, ref_freqs)
        results.append((cutoff, error))
        print(f"  {cutoff:5d} Hz: {error:.3f} dB")

    results.sort(key=lambda x: x[1])
    best_cutoff, best_error = results[0]
    print(f"\nBest lowpass cutoff: {best_cutoff} Hz → {best_error:.3f} dB")

    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    print("""
The lowpass stage may be contributing to error if:
1. Decoded cutoff doesn't match actual X3 rolloff
2. X3 uses a different filter type (e.g., higher order, shelving)
3. There's additional post-filter rolloff we're not modeling

If bypassing the lowpass helps or changing cutoff helps significantly,
we should investigate the lowpass stage parameters more closely.
""")


if __name__ == "__main__":
    main()
