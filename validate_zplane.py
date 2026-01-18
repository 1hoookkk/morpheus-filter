import numpy as np
from scipy.io import wavfile

# Load reference
fs, ref = wavfile.read('hedz - m100q0.wav')
ref = ref.astype(np.float32) / 32768.0

# Skip silent portion, analyze the actual impulse response
ir = ref[8530:]

# Test 1: DC gain (mean of IR)
# Cascade of bandpass = DC near zero
# Parallel/Hybrid = DC non-zero
dc_gain_db = 20 * np.log10(abs(np.mean(ir)) + 1e-12)
print(f"DC gain: {dc_gain_db:.1f} dB")

# Test 2: Sum of IR (related to DC gain at z=1)
# This is the filter's gain at 0 Hz
ir_sum = np.sum(ir)
print(f"IR sum: {ir_sum:.6f}")
print(f"IR sum dB: {20*np.log10(abs(ir_sum)+1e-12):.1f} dB")

# Interpretation:
# If DC gain < -80 dB: Strong evidence for cascade (DC rejection compounds)
# If DC gain > -40 dB: Strong evidence for parallel/hybrid (DC passes through LP stage)