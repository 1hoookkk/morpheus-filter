#!/usr/bin/env python3
"""
Mobile-Friendly 4-Corner RMS Validator
Run on Google Colab, Pyto (iOS), or Termux (Android)

Usage:
    python mobile_validate.py

Requires: numpy, scipy
Optional: soundfile (for WAV output)
"""

import numpy as np
from scipy import signal

# =============================================================================
# GOLDEN MASTER KEYFRAMES (from CLAUDE.md)
# =============================================================================

KEYFRAMES = {
    "M0_Q100": {
        "boost": 1.762177,
        "stages": [
            {"a1": -1.974805, "r": 0.998231, "val1": 0.548706, "val2": -0.214841, "val3": 0.283027, "flag": 1},
            {"a1": -1.939721, "r": 0.998292, "val1": 0.548706, "val2":  0.000000, "val3": 0.548704, "flag": 1},
            {"a1": -1.873399, "r": 0.998353, "val1": 0.548706, "val2": -0.960298, "val3": 0.522998, "flag": 1},
            {"a1": -1.524112, "r": 0.992679, "val1": 0.548706, "val2": -0.617493, "val3": 0.548704, "flag": 1},
            {"a1": -1.997652, "r": 0.998292, "val1": 0.0,      "val2":  0.0,      "val3": 0.0,      "flag": 0},
        ]
    },
    "M0_Q0": {
        "boost": 1.765472,
        "stages": [
            {"a1": -1.938511, "r": 0.959007, "val1": 0.561890, "val2": -0.246341, "val3": 0.316166, "flag": 1},
            {"a1": -1.892624, "r": 0.955101, "val1": 0.561890, "val2": -0.579652, "val3": 0.561888, "flag": 1},
            {"a1": -1.853366, "r": 0.993899, "val1": 0.561890, "val2": -0.970202, "val3": 0.531174, "flag": 1},
            {"a1": -1.398666, "r": 0.898483, "val1": 0.561890, "val2": -1.022866, "val3": 0.518018, "flag": 1},
            {"a1": -1.981336, "r": 0.982433, "val1": 0.0,      "val2":  0.0,      "val3": 0.0,      "flag": 0},
        ]
    },
    "M100_Q100": {
        "boost": 1.752869,
        "stages": [
            {"a1": -1.997743, "r": 0.998719, "val1": 0.511475, "val2": -0.415885, "val3": 0.207911, "flag": 1},
            {"a1": -1.881333, "r": 0.998475, "val1": 0.511475, "val2":  0.958517, "val3": 0.511473, "flag": 1},
            {"a1": -1.850007, "r": 0.998353, "val1": 0.511475, "val2": -0.885161, "val3": 0.457553, "flag": 1},
            {"a1": -1.476768, "r": 0.945335, "val1": 0.511475, "val2": -0.864006, "val3": 0.000000, "flag": 1},
            {"a1": -1.939599, "r": 0.998170, "val1": 0.0,      "val2":  0.0,      "val3": 0.0,      "flag": 0},
        ]
    },
    "M100_Q0": {
        "boost": 1.755402,
        "stages": [
            {"a1": -1.983283, "r": 0.984381, "val1": 0.521606, "val2": -0.407823, "val3": 0.244630, "flag": 1},
            {"a1": -1.824333, "r": 0.964867, "val1": 0.521606, "val2":  0.977505, "val3": 0.521605, "flag": 1},
            {"a1": -1.783306, "r": 0.970715, "val1": 0.521606, "val2": -0.885161, "val3": 0.457553, "flag": 1},
            {"a1": -1.344162, "r": 0.875046, "val1": 0.521606, "val2": -0.864006, "val3": 0.000000, "flag": 1},
            {"a1": -1.911181, "r": 0.993167, "val1": 0.0,      "val2":  0.0,      "val3": 0.0,      "flag": 0},
        ]
    },
}

# =============================================================================
# CALIBRATION CONSTANTS (GAIN MAP FIX - Feb 4, 2026)
# =============================================================================

# OLD values (15-19 dB too hot for Q0):
# CAL_M0_Q0     = 0.010
# CAL_M100_Q0   = 0.15

# NEW values (fixed):
CAL_M0_Q0     = 0.0017   # was 0.010 - cut 15.2 dB
CAL_M0_Q100   = 0.53     # unchanged
CAL_M100_Q0   = 0.017    # was 0.15  - cut 18.7 dB
CAL_M100_Q100 = 0.72     # unchanged

SAMPLE_RATE = 44100
NUM_FREQS = 1024

# =============================================================================
# WITCHCRAFT COEFFICIENT FORMULA
# =============================================================================

def build_sos(keyframe, morph, q):
    """Build SOS array from keyframe using Witchcraft formula"""
    stages = keyframe["stages"]
    raw_boost = keyframe["boost"]
    sos = []

    for i, s in enumerate(stages):
        a1_cap = s["a1"]
        r = min(s["r"], 0.9999)
        a2_cap = r * r

        if s["flag"] == 1:
            # Witchcraft numerator formula
            b0 = 1.0 + s["val1"]
            b1 = a1_cap + s["val2"]
            b2 = a2_cap - s["val3"]  # MINUS val3

            # Use captured denominator
            a1_out = a1_cap
            a2_out = a2_cap

            # DC pole normalization
            dc_denom = 1.0 + a1_out + a2_out
            if abs(dc_denom) < 0.01:
                dc_numer = b0 + b1 + b2
                if abs(dc_numer) > 0.001:
                    scale = abs(dc_denom) / abs(dc_numer) * 10.0
                    b0 *= scale
                    b1 *= scale
                    b2 *= scale
        else:
            # Stage 4: ALLPOLE with captured poles (no zeros)
            # This creates near-DC resonance for warmth/body
            # b0=1, b1=0, b2=0 with denominator from captured data
            b0 = 1.0
            b1 = 0.0
            b2 = 0.0
            a1_out = a1_cap
            a2_out = a2_cap

        # SOS format: [b0, b1, b2, 1.0, a1, a2]
        sos.append([b0, b1, b2, 1.0, a1_out, a2_out])

    return np.array(sos), raw_boost


def compute_peak_gain(sos):
    """Compute cascade peak gain (endpoint-excluded grid)"""
    w, h = signal.sosfreqz(sos, worN=NUM_FREQS, fs=SAMPLE_RATE)
    return np.max(np.abs(h))


def apply_normalization(sos, raw_boost, morph, q):
    """Apply peak normalization and calibration"""
    peak_gain = compute_peak_gain(sos)
    peak_with_boost = peak_gain * raw_boost

    current_boost = raw_boost

    # Normalize if peak > 100
    if peak_with_boost > 100.0:
        norm_factor = 10.0 / peak_with_boost
        current_boost *= norm_factor

    # Bilinear interpolation of calibration
    cal_start = CAL_M0_Q0 + q * (CAL_M0_Q100 - CAL_M0_Q0)
    cal_end = CAL_M100_Q0 + q * (CAL_M100_Q100 - CAL_M100_Q0)
    calibration = cal_start + morph * (cal_end - cal_start)

    current_boost *= calibration

    # Apply boost to stage 0
    sos_out = sos.copy()
    sos_out[0, 0] *= current_boost
    sos_out[0, 1] *= current_boost
    sos_out[0, 2] *= current_boost

    return sos_out, current_boost, calibration


# =============================================================================
# PINK NOISE GENERATOR
# =============================================================================

def generate_pink_noise(n_samples, seed=42):
    """Generate pink noise using Voss-McCartney algorithm"""
    np.random.seed(seed)

    # Simple pink noise approximation
    white = np.random.randn(n_samples)

    # Apply -3dB/octave filter (approximation)
    b = [0.049922035, -0.095993537, 0.050612699, -0.004408786]
    a = [1, -2.494956002, 2.017265875, -0.522189400]
    pink = signal.lfilter(b, a, white)

    # Normalize to -20 dBFS RMS
    rms = np.sqrt(np.mean(pink**2))
    target_rms = 10**(-20/20)  # -20 dBFS
    pink = pink * (target_rms / rms)

    return pink


# =============================================================================
# PROCESS AND MEASURE
# =============================================================================

def biquad_dfi(x, b0, b1, b2, a1, a2):
    """Direct Form I biquad (matches C++ BiquadDFI)"""
    n = len(x)
    y = np.zeros(n)
    x1, x2 = 0.0, 0.0
    y1, y2 = 0.0, 0.0

    for i in range(n):
        out = b0 * x[i] + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2

        # Denormal protection (matches C++)
        if not np.isfinite(out) or abs(out) < 1e-15:
            out = 0.0

        x2, x1 = x1, x[i]
        y2, y1 = y1, out
        y[i] = out

    return y


def process_cascade_with_clipping(sos, x):
    """Process through cascade with per-stage clipping (matches C++)"""
    out = x.copy()
    for i in range(len(sos)):
        b0, b1, b2, _, a1, a2 = sos[i]
        out = biquad_dfi(out, b0, b1, b2, a1, a2)
        # Per-stage clipping (C++ uses ±10.0)
        out = np.clip(out, -10.0, 10.0)
    # Final output clipping
    out = np.clip(out, -1.0, 1.0)
    return out


def process_corner(corner_name, morph, q):
    """Process a corner and return RMS in dB"""
    keyframe = KEYFRAMES[corner_name]

    # Build SOS
    sos, raw_boost = build_sos(keyframe, morph, q)

    # Apply normalization
    sos_norm, final_boost, calibration = apply_normalization(sos, raw_boost, morph, q)

    # Generate pink noise (3 seconds)
    n_samples = SAMPLE_RATE * 3
    pink = generate_pink_noise(n_samples)

    # Process through filter with per-stage clipping (matches C++)
    output = process_cascade_with_clipping(sos_norm, pink)

    # Compute RMS
    rms = np.sqrt(np.mean(output**2))
    rms_db = 20 * np.log10(rms + 1e-10)

    return rms_db, final_boost, calibration


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 60)
    print("MOBILE 4-CORNER RMS VALIDATOR")
    print("GAIN MAP FIX - Feb 4, 2026")
    print("=" * 60)
    print()
    print("Calibration Constants:")
    print(f"  CAL_M0_Q0     = {CAL_M0_Q0}")
    print(f"  CAL_M0_Q100   = {CAL_M0_Q100}")
    print(f"  CAL_M100_Q0   = {CAL_M100_Q0}")
    print(f"  CAL_M100_Q100 = {CAL_M100_Q100}")
    print()

    corners = [
        ("M0_Q100",   0.0, 1.0),
        ("M0_Q0",     0.0, 0.0),
        ("M100_Q100", 1.0, 1.0),
        ("M100_Q0",   1.0, 0.0),
    ]

    target_db = -20.0

    print(f"{'Corner':<12} {'RMS (dB)':>10} {'Target':>10} {'Error':>10} {'Boost':>10} {'Cal':>8} {'Status':>8}")
    print("-" * 80)

    all_pass = True
    for name, morph, q in corners:
        rms_db, boost, cal = process_corner(name, morph, q)
        error = rms_db - target_db
        status = "✓ PASS" if abs(error) <= 3.0 else "✗ FAIL"
        if abs(error) > 3.0:
            all_pass = False

        print(f"{name:<12} {rms_db:>10.1f} {target_db:>10.1f} {error:>+10.1f} {boost:>10.6f} {cal:>8.4f} {status:>8}")

    print("-" * 80)
    print(f"Overall: {'ALL PASS ✓' if all_pass else 'SOME FAILED ✗'}")
    print()
    print("Target: -20 dB RMS, ±3 dB tolerance")


if __name__ == "__main__":
    main()
