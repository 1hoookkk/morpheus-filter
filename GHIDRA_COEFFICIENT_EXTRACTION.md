# E-mu X3 Coefficient Extraction Results
## Session: 2026-02-03

---

## ✅ SUCCESSFULLY EXTRACTED DATA

### 1. Q-to-Radius Lookup Table (CRITICAL!)
**Address:** `0x18065bb70`
**Size:** 70 entries (doubles)
**Purpose:** Maps Q parameter (0-69) to filter pole radius

```
Index  Radius    Q-equiv
-----  --------  --------
  0    0.986271    36.4
  5    0.982939    29.3
 10    0.973381    18.8
 15    0.958023    11.9
 20    0.936865     7.9
 25    0.910076     5.6
 30    0.878012     4.1
 35    0.841085     3.2
 40    0.799742     2.5
 45    0.754467     2.0
 50    0.705799     1.7
 55    0.654308     1.4
 60    0.600580     1.25
 65    0.545223     1.10
 69    0.500175     1.00
```

**USE IN TRENCH:** This table should replace hardcoded radius values. Interpolate Q (0.0-1.0) to index (0-69), then lookup radius.

### 2. Pan Table Spline Control Points
**Address:** `0x1806f0c00`
**Size:** ~64 control points

Key values:
- Gain scaling factors: 0.965, 0.858, 0.913, 0.735, 0.798, 0.515...
- dB attenuation curve: -21.974, -23.873, -26.307, -28.604...
- Boundary markers: 200.0, 63.0, -96.0, -135.421

### 3. HChip Amplitude Table
**Address:** `0x1806ecb80`
**Size:** 106 control points (0x6a)

Smooth dB attenuation curve from -73.118 dB to 0.0 dB.
Used for amplitude envelope/velocity scaling.

### 4. Inverse Radius Table
**Address:** `0x180717af0`
**Size:** 13 entries

```
0.857981, 0.870365, 0.882643, 0.894818, 0.906891,
0.918863, 0.930737, 0.942514, 0.954196, 0.965784,
0.977280, 0.988685, 1.000000
```

### 5. Key Constants
| Address | Value | Purpose |
|---------|-------|---------|
| DAT_1806ead28 | 10.0 | Gain multiplier |
| DAT_1806ead30 | 0.05 | Scaling factor |
| DAT_1806eb550 | 0.003921568627 | 1/255 normalization |
| DAT_1806ecb88 | 0.001956947162 | Spline step size |
| DAT_1806ecc98 | 106.0 | Table size |
| DAT_1806f0e10 | 63.0 | Max index |

---

## ⚠️ PARTIAL/NEEDS MORE WORK

### a1-like Values Found (Filter Poles)
Several a1 values detected but NOT in organized formant tables:
- `-1.810667` @ 0x1806d81c8
- `-1.811033` @ 0x1806d81d8
- `-1.811155` @ 0x1806d81f0
- `-1.900000` @ 0x1806669f8
- `-1.500000` @ 0x180666a00
- `-1.850000` @ 0x1806f0d48

**PROBLEM:** These are scattered, not the organized 5-stage × 4-corner tables we need.

### Missing: Formant Frequency Tables
The actual formant filter coefficients (a1, val1, val2, val3 for each stage at each morph position) were NOT found as static tables.

**HYPOTHESIS:** E-mu computes filter coefficients at runtime from:
1. Formant frequency targets (Hz)
2. Q-to-radius lookup table
3. Mathematical formulas

---

## 🔍 NEXT SESSION: WHERE TO LOOK

### 1. CPhantomMorph1 Class
**RTTI String:** `0x180898a70` - `.?AVCPhantomMorph1@@`

This class handles the "Morph" filter type. Need to:
- Find vtable near this RTTI string
- Decompile virtual methods (especially `SetParameter`, `Process`)
- Trace where formant frequency data comes from

### 2. Resource Section (.rsrc)
**Address:** `0x180921000` (Section VA)
**Size:** ~23 MB (!!)

The `.rsrc` section is HUGE. E-mu likely stores:
- Preset data
- Wavetable samples
- Possibly filter coefficient banks

**TODO:** Parse PE resources for XML/binary preset data.

### 3. Runtime Coefficient Generation
Look for functions that:
- Call sin/cos (for frequency to a1 conversion: `a1 = -2 * cos(2π * f / sr)`)
- Access the Q-to-radius table at 0x18065bb70
- Build 5-stage filter cascades

**Key function candidates:**
- `FUN_1802e6490` - Builds CPhantomPanTable
- `FUN_1802e5360` - Builds CPhantomHChipAmpTable
- Search for functions referencing CPhantomMorph* vtables

### 4. Filter Type Strings
Found filter/morph parameter paths:
```
filter/morph-param/1 through /8
filter/designer-section/1-6/type
filter/designer-section/1-6/high-freq
filter/designer-section/1-6/low-freq
filter/designer-section/1-6/high-gain
filter/designer-section/1-6/low-gain
```

These suggest a 6-section parametric EQ designer mode separate from the Morph filter.

---

## 📁 FILES CREATED THIS SESSION

1. **tools/extract_dll_data.py** - Extracts data at specific addresses
2. **tools/extract_filter_data.py** - Searches for filter coefficient patterns
3. **tools/dump_radius_table.py** - Dumps Q-to-radius tables
4. **tools/emu_coefficient_dump.json** - All extracted numeric values

---

## 🎯 IMMEDIATE ACTION FOR TRENCH

### ⚠️ UPDATE (2026-02-03 Review): Integration Challenge Identified

**PROBLEM**: The EMU_Q_TO_RADIUS table cannot be directly substituted for the captured radius values due to significant differences:

1. **Range mismatch**:
   - EMU table: 0.986 (Q=1.0) → 0.500 (Q=0.0)
   - Captured values: 0.999 → 0.875 (narrower, much higher)

2. **Per-stage variation**: Captured data has different radius per stage, EMU table is uniform

3. **Unclear relationship**: The mathematical relationship between EMU table and captured values is unknown

**HYPOTHESIS**: The EMU_Q_TO_RADIUS table may be:
- For a different filter type (designer EQ, not morph filter)
- A base curve that's transformed before use (scaling, offset)
- Used in combination with frequency-dependent formulas

**CURRENT STATUS**: Table added to code with warning comments but NOT integrated. Golden Master 4-corner interpolation continues to be used.

**NEXT STEPS**:
1. Investigate if EMU table is referenced in CPhantomMorph1 class
2. Find the actual formula that converts EMU table values to filter radii
3. Determine if table should modulate captured values rather than replace them

### Original Suggestion (May Not Be Correct)

~~Use the Q-to-Radius Table NOW!~~

~~Replace hardcoded radius values in ZPlaneFilter.cpp with lookup:~~

```cpp
// Q-to-Radius table from E-mu X3 (70 entries)
static const double Q_TO_RADIUS[70] = {
    0.986271, 0.986136, 0.985727, 0.985056, 0.984125,
    0.982939, 0.981503, 0.979822, 0.977907, 0.975760,
    0.973381, 0.970770, 0.967930, 0.964859, 0.961557,
    0.958023, 0.954256, 0.950254, 0.946020, 0.941557,
    0.936865, 0.931948, 0.926807, 0.921446, 0.915869,
    0.910076, 0.904072, 0.897861, 0.891445, 0.884827,
    0.878012, 0.871002, 0.863800, 0.856411, 0.848839,
    0.841085, 0.833155, 0.825050, 0.816778, 0.808340,
    0.799742, 0.790985, 0.782074, 0.773016, 0.763811,
    0.754467, 0.744988, 0.735376, 0.725637, 0.715776,
    0.705799, 0.695709, 0.685509, 0.675207, 0.664805,
    0.654308, 0.643722, 0.633051, 0.622301, 0.611477,
    0.600580, 0.589621, 0.578598, 0.567522, 0.556395,
    0.545223, 0.534010, 0.522760, 0.511482, 0.500175
};

double getRadiusFromQ(double q) {
    // q is 0.0 to 1.0, map to index 0-69
    double idx = q * 69.0;
    int i = (int)idx;
    double frac = idx - i;
    if (i >= 69) return Q_TO_RADIUS[69];
    return Q_TO_RADIUS[i] + frac * (Q_TO_RADIUS[i+1] - Q_TO_RADIUS[i]);
}
```

This replaces the current linear interpolation of captured radius values with E-mu's actual Q curve!

---

## 🔬 TECHNICAL INSIGHT

The E-mu architecture works like this:

1. **Static Tables:** Q-to-radius, pan curves, amp curves stored in .rdata
2. **Spline Interpolation:** Tables are ~70-106 control points, expanded to 256-512 entries at runtime
3. **Runtime Computation:** Filter coefficients (a1) likely computed from frequency using `a1 = -2 * cos(2π * f / sr)`
4. **The "Secret Sauce":** Not just coefficients, but the CURVES - how Q maps to radius, how gain changes with frequency

We now have the Q curve. The spectral shape improvement should come from using this authentic E-mu Q-to-radius mapping instead of linear interpolation.

---

## 📊 CURRENT SPECTRAL MATCH STATUS

Before this session: **60-70%** correlation with X3 reference
After implementing Q-to-radius table: **TBD** (needs testing)

Expected improvement: The authentic Q curve should better match E-mu's resonance behavior, especially at intermediate Q values where linear interpolation was likely wrong.
