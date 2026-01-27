#!/usr/bin/env python3
"""
Analyze optimal frequency offsets across the full morph range.
Discover if offsets follow a predictable pattern for interpolation.
"""

import numpy as np
from scipy.io import wavfile
from scipy.signal import lfilter
from scipy.fft import rfft, rfftfreq

# Preset keyframes from captured CE data
TALKING_HEDZ = {
    0.0: [
        # Using validated M0_Q100 capture
        {"a1": -1.976510, "r": 0.998242, "flag": 1},  # 994 Hz
        {"a1": -1.938977, "r": 0.998296, "flag": 1},  # 1690 Hz
        {"a1": -1.872895, "r": 0.998353, "flag": 1},  # 2485 Hz
        {"a1": -1.523842, "r": 0.992409, "flag": 1},  # 4881 Hz
        {"a1": -1.997572, "r": 0.998289, "flag": 0},  # Lowpass
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
        # Using validated M100_Q100 capture (NOT from TalkingHedz_Complete.json)
        {"a1": -1.996743, "r": 0.998619, "flag": 1},  # 156 Hz, not DC!
        {"a1": -1.894098, "r": 0.998437, "flag": 1},  # 2262 Hz
        {"a1": -1.854829, "r": 0.998353, "flag": 1},  # 2662 Hz
        {"a1": -1.495171, "r": 0.963737, "flag": 1},  # 4793 Hz
        {"a1": -1.974292, "r": 0.998195, "flag": 0},  # Lowpass 1045 Hz
        {"a1": -1.962060, "r": 0.993167, "flag": 0},
        {"a1": -2.0, "r": 0.5, "flag": 0},
    ],
}

# Validated DSP parameters
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

    result = []
    for lo, hi in zip(lo_stages, hi_stages):
        result.append({
            "a1": lo["a1"] + t * (hi["a1"] - lo["a1"]),
            "r": lo["r"] + t * (hi["r"] - lo["r"]),
            "flag": lo["flag"],
        })
    return result


def process_filter_with_offsets(signal, stages, sr, freq_offsets):
    """Process signal with per-stage frequency offsets."""
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


def compare_spectra(ref_spectrum, our_spectrum, freqs, freq_range=(50, 6000)):
    mask = (freqs >= freq_range[0]) & (freqs <= freq_range[1])
    ref = ref_spectrum[mask]
    our = our_spectrum[mask]
    ref_mean = np.mean(ref)
    our_mean = np.mean(our)
    our_shifted = our + (ref_mean - our_mean)
    error = ref - our_shifted
    return np.sqrt(np.mean(error**2))


def find_optimal_offsets_coarse(pink, stages, sr, ref_spectrum, ref_freqs):
    """Coarse search for optimal offsets at this morph position."""
    best_error = float('inf')
    best_offsets = [0, 0, 0, 0, 0, 0, 0]

    # Only search first 3 stages (flag=1 resonators)
    for o0 in [0, 50, 100, 150, 200]:
        for o1 in [0, 50, 100, 150, 200]:
            for o2 in [0, 50, 100]:
                offsets = [o0, o1, o2, 0, 0, 0, 0]
                output = process_filter_with_offsets(pink, stages, sr, offsets)
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

    # We only have X3 references at M0 and M100
    refs = {
        0.0: "validation/hedzmorph0q100.wav",
        1.0: "validation/hedzmorph100q100.wav",
    }

    print("="*70)
    print("MORPH-DEPENDENT OFFSET ANALYSIS")
    print("="*70)
    print(f"\nUsing Q_SCALE={Q_SCALE}, GAIN_DB={GAIN_DB}")

    results = {}

    for morph_pos, ref_path in refs.items():
        ref_audio, _ = load_wav(ref_path)
        ref_freqs, ref_spectrum = compute_spectrum(ref_audio, sr)

        stages = interpolate_stages(morph_pos)

        # Get decoded frequencies
        decoded_freqs = []
        for i, stage in enumerate(stages[:4]):
            if stage["flag"] == 1:
                f = polar_to_freq(stage["a1"], stage["r"], sr)
                decoded_freqs.append(f)
            else:
                decoded_freqs.append(0)

        print(f"\n{'='*70}")
        print(f"MORPH = {morph_pos*100:.0f}%")
        print(f"{'='*70}")
        print(f"Decoded frequencies: {[f'{f:.0f} Hz' for f in decoded_freqs]}")

        # Baseline (no offsets)
        output = process_filter_with_offsets(pink, stages, sr, [0]*7)
        _, our_spec = compute_spectrum(output, sr)
        baseline_error = compare_spectra(ref_spectrum, our_spec, ref_freqs)
        print(f"Baseline error (no offsets): {baseline_error:.3f} dB")

        # Find optimal offsets
        best_offsets, best_error = find_optimal_offsets_coarse(
            pink, stages, sr, ref_spectrum, ref_freqs
        )
        print(f"Best offsets: {best_offsets}")
        print(f"Best error: {best_error:.3f} dB")
        print(f"Improvement: {baseline_error - best_error:.3f} dB")

        results[morph_pos] = {
            "decoded_freqs": decoded_freqs,
            "baseline_error": baseline_error,
            "best_offsets": best_offsets,
            "best_error": best_error,
        }

    # Analysis
    print(f"\n{'='*70}")
    print("OFFSET PATTERN ANALYSIS")
    print(f"{'='*70}")

    m0 = results[0.0]
    m100 = results[1.0]

    print(f"\n{'Stage':<8} {'M0 Offset':<12} {'M100 Offset':<12} {'Difference':<12}")
    print("-" * 50)
    for i in range(3):
        o0 = m0["best_offsets"][i]
        o100 = m100["best_offsets"][i]
        print(f"{i:<8} {o0:<12} {o100:<12} {o100-o0:<12}")

    # Check if offsets are proportional to frequency
    print(f"\n{'='*70}")
    print("OFFSET AS PERCENTAGE OF FREQUENCY")
    print(f"{'='*70}")

    for morph_pos, r in results.items():
        print(f"\nMorph {morph_pos*100:.0f}%:")
        for i in range(3):
            if r["decoded_freqs"][i] > 0:
                pct = 100 * r["best_offsets"][i] / r["decoded_freqs"][i]
                print(f"  Stage {i}: {r['best_offsets'][i]:+} Hz / {r['decoded_freqs'][i]:.0f} Hz = {pct:.1f}%")

    # Recommendations
    print(f"\n{'='*70}")
    print("RECOMMENDATIONS")
    print(f"{'='*70}")

    # Check if M0 needs any offsets
    if m0["best_error"] - m0["baseline_error"] > -0.3:
        print("\nM0: Offsets provide < 0.3 dB improvement")
        print("    Recommendation: Use zero offsets for M0")

    # Check if offsets should be interpolated
    if m100["best_offsets"] != m0["best_offsets"]:
        print("\nOffsets differ between M0 and M100:")
        print("    Option 1: Interpolate offsets linearly with morph")
        print("    Option 2: Use M100 offsets only when morph > 0.5")
        print("    Option 3: Create offset lookup table per keyframe")


if __name__ == "__main__":
    main()
