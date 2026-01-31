#!/usr/bin/env python3
"""
Peak Gain Audit Script
Loads C++ coefficient dump and compares peak gain computation with Python's scipy.signal.sosfreqz
"""
import json
import numpy as np
from scipy import signal

def load_cpp_coeffs(filename):
    """Load coefficient dump from C++ dsp_runner"""
    with open(filename, 'r') as f:
        content = f.read()

    # Remove trailing comma and wrap in array
    content = content.rstrip().rstrip(',')
    data = json.loads('[' + content + ']')

    return data

def compute_peak_gain(sos_data, worN=1024, sr=44100):
    """Compute peak gain using scipy.signal.sosfreqz"""
    # Convert to numpy SOS array format
    sos = np.array([
        [s['b0'], s['b1'], s['b2'], s['a0'], s['a1'], s['a2']]
        for s in sos_data
    ])

    # Compute frequency response
    w, h = signal.sosfreqz(sos, worN=worN, fs=sr)

    # Find peak
    peak_mag = np.max(np.abs(h))
    peak_idx = np.argmax(np.abs(h))
    peak_omega = w[peak_idx]  # This is in radians/sample when fs is not specified
    peak_freq_hz = peak_omega  # When fs=sr is given, w is already in Hz

    # Get omega in radians/sample for comparison with C++
    # When fs is specified, sosfreqz returns frequencies in Hz, so convert back to omega
    omega_rad = peak_omega * 2 * np.pi / sr if sr else peak_omega

    return peak_mag, peak_freq_hz, peak_idx, omega_rad

def main():
    print("="*80)
    print("PEAK GAIN AUDIT - C++ vs Python scipy.signal.sosfreqz")
    print("="*80)

    # First, check scipy's omega grid endpoint behavior
    print("\nSciPy Omega Grid Analysis:")
    print("-" * 80)
    worN = 1024
    w_test, _ = signal.sosfreqz(np.array([[1,0,0,1,0,0]]), worN=worN)
    print(f"  worN = {worN}")
    print(f"  w[0]   = {w_test[0]:.10f} rad/sample")
    print(f"  w[-1]  = {w_test[-1]:.10f} rad/sample")
    print(f"  π      = {np.pi:.10f}")
    print(f"  w[-1] == π? {np.isclose(w_test[-1], np.pi)}")
    if np.isclose(w_test[-1], np.pi):
        print("  → ENDPOINT INCLUDED (use: omega = pi * k / (N-1))")
    else:
        print("  → ENDPOINT EXCLUDED (use: omega = pi * k / N)")
    print()

    # Load C++ coefficient dump
    corners = load_cpp_coeffs('coeff_dump.json')

    print(f"Loaded {len(corners)} corner dumps\n")

    results = []

    for corner_data in corners:
        name = corner_data['corner']
        stages = corner_data['stages']  # These have boost ALREADY applied to stage 0
        cpp_boost = corner_data['rawBoost']

        # Remove boost from stage 0 to get pre-boost coefficients
        stages_no_boost = [s.copy() for s in stages]
        if cpp_boost > 0:
            stages_no_boost[0]['b0'] /= cpp_boost
            stages_no_boost[0]['b1'] /= cpp_boost
            stages_no_boost[0]['b2'] /= cpp_boost

        # Compute peak WITHOUT boost (to match C++ computeCascadePeakGain)
        peak_no_boost, peak_freq, peak_idx, peak_omega = compute_peak_gain(stages_no_boost, worN=1024, sr=44100)

        # Compute peak WITH boost (should be ~10 after normalization)
        peak_with_boost, _, _, _ = compute_peak_gain(stages, worN=1024, sr=44100)

        results.append({
            'corner': name,
            'peak_no_boost': peak_no_boost,
            'peak_freq': peak_freq,
            'peak_idx': peak_idx,
            'peak_omega': peak_omega,
            'cpp_boost': cpp_boost,
            'peak_with_boost': peak_with_boost
        })

        print(f"{name}:")
        print(f"  SciPy peak (no boost): {peak_no_boost:10.1f}")
        print(f"  SciPy bin index:       k = {peak_idx}")
        print(f"  SciPy omega:           ω = {peak_omega:.10f} rad/sample")
        print(f"  SciPy freq:            f = {peak_freq:.1f} Hz")
        print(f"  C++ boost applied:     {cpp_boost:10.6f}")
        print(f"  Peak with boost:       {peak_with_boost:9.1f}")
        print()

    # Compute ratios
    print("="*80)
    print("RATIO ANALYSIS (if C++ computeCascadePeakGain matches scipy)")
    print("="*80)

    # Group by M0 vs M100
    m0_corners = [r for r in results if r['corner'].startswith('M0_')]
    m100_corners = [r for r in results if r['corner'].startswith('M100_')]

    print("\nM0 Corners (should all have similar peak gains):")
    for r in m0_corners:
        print(f"  {r['corner']:12s}: peak={r['peak_no_boost']:10.1f}")

    print("\nM100 Corners (should all have similar peak gains):")
    for r in m100_corners:
        print(f"  {r['corner']:12s}: peak={r['peak_no_boost']:10.1f}")

    # Compare M100_Q0 vs M0_Q100 (the problematic corners)
    m100_q0 = next((r for r in results if r['corner'] == 'M100_Q0'), None)
    m0_q100 = next((r for r in results if r['corner'] == 'M0_Q100'), None)

    if m100_q0 and m0_q100:
        ratio = m100_q0['peak_no_boost'] / m0_q100['peak_no_boost']
        print(f"\nM100_Q0 / M0_Q100 ratio: {ratio:.2f}x")
        print(f"  M100_Q0 peak:  {m100_q0['peak_no_boost']:.1f}")
        print(f"  M0_Q100 peak:  {m0_q100['peak_no_boost']:.1f}")

        if ratio < 0.2:
            print(f"  ⚠️  M100_Q0 peak is {1/ratio:.1f}x LOWER - bug in C++ frequency response!")

    print("\n" + "="*80)
    print("If scipy peaks match C++ debug output → C++ freq response is correct")
    print("If scipy peaks DON'T match → Bug in C++ computeCascadePeakGain()")
    print("="*80)

if __name__ == '__main__':
    main()
