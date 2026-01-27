#!/usr/bin/env python3
"""
TRENCH Coefficient Ripper

Captures biquad coefficients from EmulatorX memory in real-time
as you sweep the Morph knob. Creates a lookup table for the VST.

Usage:
1. pip install pymem
2. Open Emulator X3, load Talking Hedz preset
3. Run this script
4. Sweep the Morph knob from 0% to 100% during the countdown
5. Use the resulting JSON as your filter ROM

Based on validated memory address from Cheat Engine captures.
"""

import json
import time
import sys

try:
    import pymem
    import pymem.process
except ImportError:
    print("ERROR: pymem not installed. Run: pip install pymem")
    sys.exit(1)

# CONFIGURATION
# ---------------------------------------------------------
# Base address where coefficient block starts
# Update this if it changes between sessions!
TARGET_BASE_ADDR = 0x012EE610

# Number of floats to capture per frame
# 5 stages * 3 values (a1, r, flag) = 15, plus extra for safety
FLOAT_COUNT = 32

# Capture rate (frames per second)
SAMPLE_RATE = 60

# Duration of the sweep (seconds)
DURATION = 12

# Also capture Q sweep? Set to True for 2D grid
CAPTURE_Q = False
# ---------------------------------------------------------


def capture_morph_sweep():
    """Main capture function."""
    print("[TRENCH] Coefficient Ripper v1.0")
    print("=" * 50)

    # Find process
    print("[TRENCH] Looking for EmulatorX.exe...")
    try:
        pm = pymem.Pymem("EmulatorX.exe")
        print(f"[TRENCH] Attached to Process ID: {pm.process_id}")
    except Exception as e:
        print(f"[ERROR] Could not find process: {e}")
        print("[HINT] Make sure Emulator X3 is running with Talking Hedz loaded")
        return

    # Verify we can read the address
    try:
        test_val = pm.read_float(TARGET_BASE_ADDR)
        print(f"[TRENCH] Test read at 0x{TARGET_BASE_ADDR:08X}: {test_val:.6f}")
    except Exception as e:
        print(f"[ERROR] Cannot read memory at 0x{TARGET_BASE_ADDR:08X}: {e}")
        print("[HINT] The address may have changed. Check Cheat Engine.")
        return

    # Create storage
    capture_data = {
        "preset": "TalkingHedz",
        "base_address": hex(TARGET_BASE_ADDR),
        "float_count": FLOAT_COUNT,
        "sample_rate": SAMPLE_RATE,
        "capture_date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "frames": []
    }

    print()
    print("[TRENCH] Ready to capture!")
    print(f"[ACTION] You have {DURATION} seconds to sweep the Morph knob 0% -> 100%")
    print()
    print("Starting in 3...")
    time.sleep(1)
    print("2...")
    time.sleep(1)
    print("1...")
    time.sleep(1)
    print()
    print("[GO!] CAPTURING - SWEEP THE MORPH KNOB NOW!")
    print()

    start_time = time.time()
    frame_count = 0
    last_print = 0

    while (time.time() - start_time) < DURATION:
        try:
            # Read coefficient block
            values = []
            for i in range(FLOAT_COUNT):
                addr = TARGET_BASE_ADDR + (i * 4)
                val = pm.read_float(addr)
                values.append(round(val, 6))

            # Store frame
            t = round(time.time() - start_time, 3)
            capture_data["frames"].append({
                "t": t,
                "data": values
            })

            frame_count += 1

            # Progress feedback
            if time.time() - last_print > 0.5:
                elapsed = time.time() - start_time
                pct = (elapsed / DURATION) * 100
                print(f"  [{pct:5.1f}%] Frame {frame_count}, Val[0]={values[0]:.4f}, Val[3]={values[3]:.4f}")
                last_print = time.time()

            time.sleep(1.0 / SAMPLE_RATE)

        except Exception as e:
            print(f"[ERROR] Read failed: {e}")
            break

    print()
    print("[DONE] Capture complete!")
    print(f"       Captured {len(capture_data['frames'])} frames")

    # Save
    output_file = f"trench_capture_{int(time.time())}.json"
    with open(output_file, "w") as f:
        json.dump(capture_data, f, indent=2)

    print(f"       Saved to: {output_file}")
    print()
    print("[NEXT STEPS]")
    print("  1. Review the captured data in the JSON file")
    print("  2. Convert to C++ lookup table with tools/convert_capture.py")
    print("  3. Load in TrenchFilter for coefficient playback")

    return output_file


if __name__ == "__main__":
    capture_morph_sweep()
