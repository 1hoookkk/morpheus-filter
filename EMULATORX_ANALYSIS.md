# EmulatorX.dll Analysis Summary

## DLL Structure
- **File Size:** 33.6 MB
- **Format:** PE32+ (64-bit)
- **Image Base:** 0x180000000
- **.text section:** 0x1000 - 0x51A000 (~5MB code)
- **.rdata section:** 0x5F2000 - 0x85E000 (~2.6MB read-only data)
- **.rsrc section:** 0x921000+ (~23MB resources)

## Key Classes Found (RTTI)

### Filter Classes
```
CPhantomFilter        - Base filter class
CPhantomBPFilter      - Bandpass filter
CPhantomLPFilter      - Lowpass filter
CPhantomBP2Pole       - 2-pole bandpass
CPhantomBP4Pole       - 4-pole bandpass
CPhantomLP2Pole       - 2-pole lowpass
CPhantomLP4Pole       - 4-pole lowpass
CPhantomLP6Pole       - 6-pole lowpass
CPhantomE4Filter      - E4 (Emulator 4) filter
CPhantomFilterP2k     - Proteus 2000 filter
```

### Morph Classes (Z-Plane!)
```
CPhantomMorph1        - Morph filter type 1
CPhantomMorph1Basic   - Basic morph
CPhantomMorph2        - Morph filter type 2
CPhantomMorphLP       - Morph lowpass (LIKELY THE Z-PLANE!)
CPhantomMorphLPX      - Extended morph lowpass
CPhantomMorphDesigner - Morph designer UI
```

## Filter Coefficient Computation

### Location: ~0x2BEE20
Found a cluster of `sqrtss` instructions suggesting coefficient computation:
- 18 consecutive sqrt operations
- Processing 6 stages (offsets: -8, -4, 0, 4, 8, 12)
- Conditional sqrt based on sample rate thresholds:
  - `0xFDE8` (65,000) = ~1.5 × 44100
  - `0x1FBD0` (130,000) = ~3 × 44100

### Pattern Analysis
```asm
; Load from coefficient table
lea     rax, [rip+0x416a91]  ; Table address
mov     ecx, 2               ; 2 stages or iterations?

; For each stage:
movss   xmm0, [rax-8]        ; Load value
cmp     edx, 0xFDE8          ; Compare against threshold
jle     skip_sqrt1
sqrtss  xmm0, xmm0           ; Apply sqrt if > threshold

cmp     edx, 0x1FBD0         ; Second threshold
jle     skip_sqrt2
sqrtss  xmm0, xmm0           ; Apply second sqrt

movss   [rcx-4], xmm0        ; Store result
```

### Interpretation
The double-sqrt pattern suggests:
- At low sample rates: use raw value
- At medium rates (44.1k-65k): apply sqrt (value^0.5)
- At high rates (88.2k+): apply sqrt twice (value^0.25)

This is likely **bandwidth scaling** to maintain filter characteristics across sample rates.

## Morph Parameter Strings
```
filter/morph-param/1
filter/morph-param/2
filter/morph-param/3
filter/morph-param/4
filter/morph-param/5
filter/morph-param/6
filter/morph-param/7
filter/morph-param/8
```
These suggest 8 morph interpolation parameters (for 8 cube corners).

## What's Still Unknown

### 1. ARMAdillo Decode Function
The function that converts stored byte values to filter coefficients.
Based on validated cube data:
- **Radius:** `r = sqrt(1 - 2^(-byte/32))`
- **Frequency:** `freq_hz = byte × 86.4` or `byte × 43.2`

### 2. Numerator Computation (b0, b1, b2)
This is the main unknown. Based on captured data:

**For flag=1 (Bandpass/Resonator):**
```cpp
// Zeros at DC and Nyquist
double scale = (1.0 - a2) * 0.5;
b0 = scale;
b1 = 0.0;
b2 = -scale;
```

**For flag=0 (Lowpass):**
```cpp
// Unity DC gain
double norm = (1.0 + a1 + a2) * 0.25;
b0 = norm;
b1 = 2.0 * norm;
b2 = norm;
```

### 3. Cube Data Storage Location
Either:
- Embedded in .rsrc section (23MB)
- In the Morpheus WAV file (cubes_v1.01vc_170120.wav)
- In external bank files

## Recommendations for Full RE

### Option A: Use Ghidra/IDA
1. Load EmulatorX.dll
2. Search for xrefs to "CPhantomMorphLP" RTTI
3. Find the vtable and virtual functions
4. Trace the `Process()` or `Calculate()` method
5. Follow the coefficient computation

### Option B: Dynamic Analysis
1. Use x64dbg to attach to EmuX running process
2. Set breakpoint at 0x180000000 + 0x2BEE20
3. Watch coefficient values being computed
4. Trace source of input values

### Option C: Cheat Engine (Already Done!)
The live capture approach you used is actually the most practical:
- You have the output coefficients (a1, r, flag)
- You have the cube interpolation behavior
- You just need to validate the numerator formula

## Validated Numerator Formula (From Testing)

Based on your FFT validation, this works:

```cpp
if (flag == 1) {
    // Bandpass: zeros at DC and Nyquist
    double scale = (1.0 - a2) * 0.5;
    b0 = scale;
    b1 = 0.0;
    b2 = -scale;
} else {
    // Lowpass: unity DC gain
    double norm = (1.0 + a1 + a2) * 0.25;
    b0 = norm;
    b1 = 2.0 * norm;
    b2 = norm;
}
```

The frequency peaks in your reference audio match within ~8%, which is good enough for a musical implementation.
