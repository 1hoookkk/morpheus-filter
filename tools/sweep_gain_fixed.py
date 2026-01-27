#!/usr/bin/env python3
"""
TRENCH Gain Sweep - FIXED VALIDATION
Finds optimal peaking EQ gain by comparing TIME-DOMAIN levels first,
then spectral shape. Avoids the normalization bug that made bandpass
appear better when it was producing silence.
"""

import numpy as np
from scipy.io import wavfile
from scipy.signal import lfilter
from scipy.fft import rfft, rfftfreq
import os

# =============================================================================
# CAPTURED COEFFICIENTS FROM X3 (Cheat Engine)
# =============================================================================

CAPTURES = {
    "M0_Q100": [
        {"a1": -1.976510, "r": 0.998242, "flag": 1},
        {"a1": -1.938977, "r": 0.998296, "flag": 1},
        {"a1": -1.872895, "r": 0.998353, "flag": 1},
        {"a1": -1.523842, "r": 0.992409, "flag": 1},
        {"a1": -1.997572, "r": 0.998289, "flag": 0},
    ],
    "M100_Q100": [
        {"a1": -1.996743, "r": 0.998619, "flag": 1},
        {"a1": -1.894098, "r": 0.998437, "flag": 1},
        {"a1": -1.854829, "r": 0.998353, "flag": 1},
        {"a1": -1.495171, "r": 0.963737, "flag": 1},
        {"a1": -1.974292, "r": 0.998195, "flag": 0},
    ],
}

REFERENCE_FILES = {
    "M0_Q100": "validation/hedzmorph0q100.wav",
    "M100_Q100": "validation/hedzmorph100q100.wav",
}


def load_wav(path):
    """Load WAV file, convert to float mono."""
    sr, data = wavfile.read(path)
    if data.dtype == np.int16:
        data = data.astype(np.float64) / 32768.0
    elif data.dtype == np.int32:
        data = data.astype(np.float64) / 2147483648.0
    if len(data.shape) > 1:
        data = data[:, 0]
    return data, sr


def polar_to_freq(a1, r, sr=44100):
    """Convert polar coefficients to frequency."""
    cos_theta = -a1 / (2.0 * r)
    cos_theta = np.clip(cos_theta, -1.0, 1.0)
    theta = np.arccos(cos_theta)
    return theta * sr / (2.0 * np.pi)


def make_peaking_eq(a1, r, sr, gain_db):
    """RBJ Peaking EQ at pole frequency."""
    freq = polar_to_freq(a1, r, sr)
    freq = np.clip(freq, 20, sr * 0.49)

    # Q from radius
    Q = 1.0 / (2.0 * (1.0 - r))
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

    b = [b0/a0, b1/a0, b2/a0]
    a = [1.0, a1_coef/a0, a2/a0]
    return b, a


def make_lowpass_rbj(freq, Q, sr):
    """RBJ Lowpass."""
    freq = np.clip(freq, 20, sr * 0.49)
    w0 = 2.0 * np.pi * freq / sr
    alpha = np.sin(w0) / (2.0 * Q)

    b0 = (1.0 - np.cos(w0)) / 2.0
    b1 = 1.0 - np.cos(w0)
    b2 = (1.0 - np.cos(w0)) / 2.0
    a0 = 1.0 + alpha
    a1 = -2.0 * np.cos(w0)
    a2 = 1.0 - alpha

    b = [b0/a0, b1/a0, b2/a0]
    a = [1.0, a1/a0, a2/a0]
    return b, a


def process_filter(signal, stages, sr, gain_db):
    """Process signal through filter stages with given peaking gain."""
    x = signal.copy()

    for stage in stages:
        if stage["flag"] == 1:
            b, a = make_peaking_eq(stage["a1"], stage["r"], sr, gain_db)
        else:
            # Lowpass - decode frequency from polar
            freq = polar_to_freq(stage["a1"], stage["r"], sr)
            b, a = make_lowpass_rbj(freq, 0.707, sr)
        x = lfilter(b, a, x)

    return x


def compute_spectrum(signal, sr, nfft=8192):
    """Compute magnitude spectrum in dB."""
    spectrum = np.abs(rfft(signal, n=nfft))
    freqs = rfftfreq(nfft, 1/sr)
    spectrum_db = 20 * np.log10(spectrum + 1e-10)
    return freqs, spectrum_db


def compare_spectra_fixed(ref_spectrum, our_spectrum, freqs, freq_range=(50, 6000)):
    """
    FIXED comparison - match levels in time domain first via offset,
    not by normalizing spectra which hides when signal is killed.
    """
    mask = (freqs >= freq_range[0]) & (freqs <= freq_range[1])
    ref = ref_spectrum[mask]
    our = our_spectrum[mask]

    # Match mean level (offset) rather than RMS (which hides silence)
    ref_mean = np.mean(ref)
    our_mean = np.mean(our)
    offset = ref_mean - our_mean
    our_shifted = our + offset

    error = ref - our_shifted
    rms_error = np.sqrt(np.mean(error**2))

    return rms_error, offset


def time_domain_rms(signal):
    """Compute time-domain RMS."""
    return np.sqrt(np.mean(signal**2))


def main():
    # Load pink noise input
    pink_path = "validation/bypassed-pinknoise.wav"
    if not os.path.exists(pink_path):
        print(f"ERROR: {pink_path} not found")
        return

    pink, sr = load_wav(pink_path)
    print(f"Loaded pink noise: {len(pink)} samples, {sr} Hz")
    print(f"Input RMS: {time_domain_rms(pink):.6f}\n")

    # Test case
    case = "M100_Q100"
    stages = CAPTURES[case]

    # Load reference
    ref_path = REFERENCE_FILES[case]
    if not os.path.exists(ref_path):
        print(f"ERROR: Reference not found: {ref_path}")
        return

    ref_audio, _ = load_wav(ref_path)
    ref_rms = time_domain_rms(ref_audio)
    ref_freqs, ref_spectrum = compute_spectrum(ref_audio, sr)

    print(f"Reference {case}")
    print(f"  Time-domain RMS: {ref_rms:.6f}")
    print(f"  Spectrum mean (50-6kHz): {np.mean(ref_spectrum[(ref_freqs >= 50) & (ref_freqs <= 6000)]):.1f} dB")

    # Extended gain sweep
    print(f"\n{'='*60}")
    print(f"GAIN SWEEP - Peaking EQ")
    print(f"{'='*60}")
    print(f"{'Gain (dB)':<12} {'Output RMS':<15} {'Spectral Error':<15} {'Level Offset'}")
    print(f"{'-'*60}")

    results = []

    for gain_db in range(0, 72, 3):  # 0 to 69 dB in 3dB steps
        output = process_filter(pink, stages, sr, gain_db)

        if np.any(np.isnan(output)) or np.any(np.isinf(output)):
            print(f"{gain_db:<12} UNSTABLE")
            continue

        out_rms = time_domain_rms(output)
        _, out_spectrum = compute_spectrum(output, sr)

        spectral_error, offset = compare_spectra_fixed(ref_spectrum, out_spectrum, ref_freqs)

        print(f"{gain_db:<12} {out_rms:<15.6f} {spectral_error:<15.2f} {offset:+.1f} dB")
        results.append((gain_db, out_rms, spectral_error, offset))

    # Find best
    if results:
        results.sort(key=lambda x: x[2])  # Sort by spectral error
        best_gain, best_rms, best_error, best_offset = results[0]

        print(f"\n{'='*60}")
        print(f"OPTIMAL GAIN: {best_gain} dB")
        print(f"  Spectral Error: {best_error:.2f} dB")
        print(f"  Output RMS: {best_rms:.6f}")
        print(f"  Level Offset: {best_offset:+.1f} dB")
        print(f"{'='*60}")

        # Save optimal output
        output = process_filter(pink, stages, sr, best_gain)
        output_norm = output / (np.max(np.abs(output)) + 1e-10) * 0.9
        wavfile.write(f'validation/trench_{case.lower()}_optimal.wav', sr,
                      (output_norm * 32767).astype(np.int16))
        print(f"\nSaved: validation/trench_{case.lower()}_optimal.wav (gain={best_gain}dB)")

        # Also show plateau behavior
        print(f"\nError vs Gain (looking for plateau):")
        for gain_db, _, err, _ in sorted(results, key=lambda x: x[0]):
            bar = "#" * int(50 - err)
            print(f"  {gain_db:2d} dB: {err:5.2f} {bar}")


if __name__ == "__main__":
    main()
