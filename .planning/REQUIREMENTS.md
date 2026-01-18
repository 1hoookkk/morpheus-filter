# Requirements: Morpheus Filter

**Defined:** 2026-01-18
**Core Value:** 1:1 accuracy with Talking Hedz cartridge

## v1 Requirements

### DSP Engine

- [ ] **DSP-01**: Filter engine loads 17×17×3 grid data from JSON cartridge files
- [ ] **DSP-02**: Morph parameter (0-100%) indexes X-axis of grid with linear interpolation
- [ ] **DSP-03**: Q parameter (0-100%) interpolates between 3 variants (0%, 50%, 100%)
- [ ] **DSP-04**: Each stage computes biquad coefficients from grid freq/radius/gain
- [ ] **DSP-05**: 7-stage cascade topology processes signal sequentially
- [ ] **DSP-06**: Stages with ultrasonic frequencies (>20kHz) pass signal unchanged
- [ ] **DSP-07**: Sample rate warping for 48kHz/96kHz (captured at 44.1kHz)
- [ ] **DSP-08**: Per-stage gain applied from grid data

### Plugin Interface

- [ ] **PLG-01**: VST3 plugin compiles and loads in DAW (Ableton, Reaper, FL Studio)
- [ ] **PLG-02**: Morph parameter exposed and automatable
- [ ] **PLG-03**: Q parameter exposed and automatable
- [ ] **PLG-04**: Mix parameter (wet/dry blend) exposed and automatable
- [ ] **PLG-05**: Preset selector dropdown for cartridge selection
- [ ] **PLG-06**: State save/restore preserves all parameters

### Visualizer

- [ ] **VIS-01**: Frequency response curve displayed in real-time
- [ ] **VIS-02**: Curve updates when Morph or Q changes
- [ ] **VIS-03**: Visual style matches EmulatorX3 (gray background, cyan/green curve)
- [ ] **VIS-04**: Frequency axis: 20Hz - 20kHz logarithmic
- [ ] **VIS-05**: Amplitude axis: -24dB to +12dB

### Validation

- [ ] **VAL-01**: Output matches reference file "hedz - m100q0.wav" within 3dB RMS error
- [ ] **VAL-02**: Output matches reference file "hedz - 5050.wav" within 3dB RMS error
- [ ] **VAL-03**: Morph sweep produces audible vowel-like formant changes
- [ ] **VAL-04**: Q=0% produces flatter response than Q=100%

## v2 Requirements

### Extended Features

- **EXT-01**: Additional cartridge support (Bass-O-Matic, DJ Alkaline, etc.)
- **EXT-02**: MIDI learn for parameter control
- **EXT-03**: Resizable UI
- **EXT-04**: AU plugin format
- **EXT-05**: Cartridge import from EmulatorX.dll

## Out of Scope

| Feature | Reason |
|---------|--------|
| E-mu/Z-Plane branding | Clean slate design, no historical references |
| Transform parameter | Not needed for Talking Hedz, fixed at 0 |
| Real-time cartridge extraction | Complex, v2+ feature |
| Polyphonic operation | Single filter instance is sufficient |
| CLAP format | VST3 covers primary use cases |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| DSP-01 | Phase 1 | Pending |
| DSP-02 | Phase 1 | Pending |
| DSP-03 | Phase 1 | Pending |
| DSP-04 | Phase 1 | Pending |
| DSP-05 | Phase 1 | Pending |
| DSP-06 | Phase 1 | Pending |
| DSP-07 | Phase 1 | Pending |
| DSP-08 | Phase 1 | Pending |
| VAL-01 | Phase 1 | Pending |
| VAL-02 | Phase 1 | Pending |
| VAL-03 | Phase 1 | Pending |
| VAL-04 | Phase 1 | Pending |
| PLG-01 | Phase 2 | Pending |
| PLG-02 | Phase 2 | Pending |
| PLG-03 | Phase 2 | Pending |
| PLG-04 | Phase 2 | Pending |
| PLG-05 | Phase 2 | Pending |
| PLG-06 | Phase 2 | Pending |
| VIS-01 | Phase 3 | Pending |
| VIS-02 | Phase 3 | Pending |
| VIS-03 | Phase 3 | Pending |
| VIS-04 | Phase 3 | Pending |
| VIS-05 | Phase 3 | Pending |

**Coverage:**
- v1 requirements: 21 total
- Mapped to phases: 21
- Unmapped: 0 ✓

---
*Requirements defined: 2026-01-18*
*Last updated: 2026-01-18 after initial definition*
