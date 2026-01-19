# External Integrations

**Analysis Date:** 2026-01-20

## APIs & External Services

**None required for runtime operation.**

The filter operates entirely offline with pre-extracted coefficient data.

## Data Extraction Toolchain

**Cheat Engine:**
- Purpose: Reverse-engineer filter coefficients from EmulatorX.dll at runtime
- Scripts: `ce_capture_grid.lua`, `x3_dump.lua`
- Process: Attach to FL Studio (fl64.exe) with Emulator X3 loaded
- Output: Raw a1/radius/flag coefficients per stage at various Morph/Q positions

**EmulatorX3 (E-mu):**
- Purpose: Source of reference Z-Plane filter implementation ("Talking Hedz" cartridge)
- Version: EmulatorX3 (legacy E-mu software)
- Usage: Generate reference audio recordings for validation
- Files: `hedz - m100q0.wav`, `hedz - 5050.wav`, etc.

**FL Studio:**
- Purpose: DAW host for EmulatorX3 during coefficient extraction
- Version: FL Studio 64-bit
- Process: Host EmulatorX3 VSTi, render audio for reference captures

## Data Storage

**Databases:**
- None - All data stored in JSON files

**File Storage:**
- Local filesystem only
- All cartridge data in project root

**Caching:**
- None

## Data File Format

**Cartridge Format (`talking_hedz_extracted.json`):**
```json
{
  "name": "Talking Hedz",
  "version": "2.0",
  "format": "universal_3variant_grid",
  "topology": "cascade",
  "parameter_map": {
    "morph": "grid_x (0-16)",
    "transform": "grid_y (0-16)",
    "q": "variant (0=Q0%, 1=Q50%, 2=Q100%)"
  },
  "variants": [
    {
      "stages": [
        {
          "stage": 0,
          "shape": "eq",
          "freq_17x17": [...],
          "gain_17x17": [...],
          "radius_17x17": [...]
        }
      ]
    }
  ]
}
```

**Raw Capture Format (`talking_hedz_complete.json`):**
```json
{
  "meta": {
    "name": "Talking Hedz",
    "sample_rate": 44100,
    "topology": "cascade",
    "stages": 5
  },
  "q100": {
    "morph_0": [
      {"a1": -1.974805, "r": 0.998231, "flag": 1}
    ]
  }
}
```

## Authentication & Identity

**Auth Provider:**
- None required

## Monitoring & Observability

**Error Tracking:**
- None (debug builds use `std::printf` for coefficient logging)

**Logs:**
- Console output via `debugPrint()` method (debug builds only)
- Controlled by `JUCE_DEBUG`, `_DEBUG`, or `NDEBUG` macros

## CI/CD & Deployment

**Hosting:**
- Local development only (Phase 1)
- Phase 2: Plugin distribution TBD

**CI Pipeline:**
- None configured

**Version Control:**
- Git (current repository)
- Branch: `master`

## Environment Configuration

**Required env vars:**
- None

**Secrets location:**
- N/A - No secrets required

**Configuration files:**
- `.gitignore` - Excludes build artifacts, debug scripts, audio files

## Webhooks & Callbacks

**Incoming:**
- None

**Outgoing:**
- None

## Future Integrations (Phase 2+)

**JUCE Framework:**
- Purpose: VST3/AU plugin wrapper
- Version: 8.0.10 (planned)
- Integration: CMake-based build system

**DAW Hosts (validation targets):**
- Ableton Live
- Reaper
- FL Studio

## Python Script Dependencies

**Used in validation and data processing:**

| Package | Purpose | Files Using It |
|---------|---------|----------------|
| numpy | Numerical arrays, FFT | All Python scripts |
| scipy.io.wavfile | WAV file loading | `validate_against_reference.py`, `validate_trench.py` |
| scipy.interpolate | Grid interpolation | `Scripts/regenerate_cartridge.py` |
| scipy.signal | Frequency response | `validate_grid_engine.py` |
| matplotlib | Plotting | All validation scripts |
| soundfile | Alternative WAV loading | `validate_against_reference.py` |
| pathlib | Path handling | All Python scripts |
| json | Cartridge parsing | All Python scripts |

**Installation:**
```bash
pip install numpy scipy matplotlib soundfile
```

## Reference File Validation

**Process:**
1. Load reference WAV from EmulatorX3 capture
2. Generate impulse response using Python ZPlaneEngine
3. Compare via FFT/formant analysis
4. Target: <3dB RMS error

**Key validation files:**
- `Tests/validate_against_reference.py` - Main validation suite
- `validate_trench_v2.py` - Alternative validation approach
- `validate_grid_engine.py` - Grid interpolation testing

---

*Integration audit: 2026-01-20*
