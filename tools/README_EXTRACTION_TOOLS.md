# E-mu EmulatorX Data Extraction Tools

These Python scripts were created to extract coefficient data from the E-mu EmulatorX binary file. They were part of the research effort documented in commit 77d5029 (2026-02-03).

## ⚠️ Important Notes

1. **Windows Only**: These tools require access to `EmulatorX.bin` from the E-mu Emulator X3 installation at:
   ```
   C:\Program Files\E-MU\Emulator X3\EmulatorX.bin
   ```

2. **Research Tools**: These are research/reverse-engineering tools used during development. They are NOT needed for building or running the TRENCH plugin.

3. **Extracted Data**: The results of these tools are already incorporated into:
   - `emu_coefficient_dump.json` - All extracted numeric values
   - `Source/dsp/ZPlaneFilter.cpp` - EMU_Q_TO_RADIUS table (currently unused, see comments)
   - `GHIDRA_COEFFICIENT_EXTRACTION.md` - Documentation of findings

## Tools Overview

### extract_dll_data.py
Extracts data from specific virtual addresses in the EmulatorX binary.
- Uses PE file parsing to convert virtual addresses to file offsets
- Reads double-precision floating-point values
- Addresses discovered via Ghidra reverse engineering

**Usage**: 
```bash
python extract_dll_data.py
```

**Output**: Prints values at hardcoded addresses

### dump_radius_table.py
Dumps the Q-to-Radius lookup tables found in EmulatorX.bin.
- Extracts the 70-entry Q-to-radius table at 0x18065bb70
- Extracts the 13-entry inverse radius table at 0x180717af0
- Includes Q approximation calculations

**Usage**:
```bash
python dump_radius_table.py
```

**Output**: Formatted table of radius values with indices

### extract_filter_data.py
Searches for Z-Plane filter coefficient patterns in the binary.
- Looks for known Golden Master values (a1, radius, val1/val2/val3)
- Searches .rdata section for coefficient tables
- Attempts to locate formant frequency tables

**Usage**:
```bash
python extract_filter_data.py
```

**Output**: Reports on found patterns and potential coefficient data

## Integration Status

As of 2026-02-03 review:

### ✅ Successfully Extracted
- **Q-to-Radius table** (70 entries) - added to ZPlaneFilter.cpp but NOT used
- **Pan table spline points** - in emu_coefficient_dump.json
- **HChip amplitude curve** - in emu_coefficient_dump.json
- **Various constants** - in emu_coefficient_dump.json

### ⚠️ Integration Challenges
The EMU_Q_TO_RADIUS table **cannot be directly substituted** for captured radius values because:
1. Range mismatch: EMU 0.986→0.500 vs Captured 0.999→0.875
2. Captured data has different radius per stage; EMU table is uniform
3. Mathematical relationship between EMU table and captured values is unknown

See `GHIDRA_COEFFICIENT_EXTRACTION.md` for detailed analysis.

### ❌ Not Found
- Formant frequency tables for all morph positions
- Runtime coefficient generation formulas
- CPhantomMorph1 class implementation details

These are likely computed at runtime rather than stored as static tables.

## Future Research

If continuing this reverse engineering work:

1. **Find CPhantomMorph1 implementation**
   - Look for RTTI string at 0x180898a70
   - Decompile virtual methods (SetParameter, Process)
   - Trace where formant frequencies come from

2. **Parse .rsrc section**
   - Resource section is ~23 MB
   - May contain preset banks, wavetables, or coefficient data

3. **Locate runtime formulas**
   - Functions that call sin/cos for frequency→a1 conversion
   - Functions that access Q-to-radius table
   - Filter cascade building code

## Legal Note

These tools are for **educational and interoperability research only**. The E-mu EmulatorX software is proprietary. Reverse engineering was performed to understand and recreate the Z-Plane filter behavior, not to extract or redistribute E-mu's intellectual property.

The TRENCH plugin is a clean-room implementation based on:
- Audio analysis of actual E-mu X3 hardware
- Mathematical modeling of filter behavior
- Public domain DSP algorithms

No E-mu proprietary code or copyrighted material is included in the TRENCH plugin.
