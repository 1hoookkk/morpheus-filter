# Requirements: TRENCH

**Defined:** 2026-01-27
**Core Value:** The sound must be 1:1 with Emulator X3

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Build

- [ ] **BUILD-01**: Plugin compiles without errors on Windows
- [ ] **BUILD-02**: VST3 loads successfully in DAW (tested in at least one host)
- [ ] **BUILD-03**: Standalone app launches and runs

### DSP Engine

- [ ] **DSP-01**: Audio passes through plugin (bypass works)
- [ ] **DSP-02**: 5-stage cascaded biquad filter processes audio
- [ ] **DSP-03**: Direct Form I topology for stable morphing (NOT DF-II)
- [ ] **DSP-04**: Denormal protection prevents CPU spikes
- [ ] **DSP-05**: Control-rate coefficient updates (every 32-64 samples, not per-sample)

### Coefficient System

- [ ] **COEF-01**: Talking Hedz coefficients captured from X3 memory
- [ ] **COEF-02**: Full morph sweep captured (not just 3 keyframes)
- [ ] **COEF-03**: Coefficients stored in v-space format
- [ ] **COEF-04**: v-space to biquad decode implemented
- [ ] **COEF-05**: Smooth interpolation across morph range

### Function Generator

- [ ] **FGEN-01**: 64-step level sequencer per Function Generator
- [ ] **FGEN-02**: 64-step gate sequencer (trigger output)
- [ ] **FGEN-03**: 3 independent Function Generator instances
- [ ] **FGEN-04**: All playback modes (Forward, Reverse, Pendulum, Random, Brownian, One-Shot)
- [ ] **FGEN-05**: Smooth interpolation option (linear between steps)
- [ ] **FGEN-06**: Rate range 0.081 Hz to 18.147 Hz
- [ ] **FGEN-07**: Brownian motion with boundary bounce
- [ ] **FGEN-08**: Key sync (reset on note-on)
- [ ] **FGEN-09**: Grid quantization (Major, Minor, Chromatic, Octaves)

### Modulation Routing

- [ ] **MOD-01**: Function Generator to Morph modulation
- [ ] **MOD-02**: Function Generator to Q modulation
- [ ] **MOD-03**: Rate modulation input (exponential: Rate × 2^ModAmount)
- [ ] **MOD-04**: Length modulation (EndStep adjustment with wraparound)
- [ ] **MOD-05**: Direction modulation override

### Controls

- [ ] **CTRL-01**: Morph parameter (0-100%) controls Ah to Ee transition
- [ ] **CTRL-02**: Q parameter (0-100%) controls resonance amount
- [ ] **CTRL-03**: Parameters persist when DAW saves/loads project

### Validation

- [ ] **VAL-01**: FFT peaks match X3 reference at M0_Q100 (within ±10%)
- [ ] **VAL-02**: FFT peaks match X3 reference at M100_Q100 (within ±10%)
- [ ] **VAL-03**: FFT peaks match X3 reference at M100_Q0 (within ±10%)
- [ ] **VAL-04**: Ear test confirms sonic match (A/B blind)

### GUI

- [ ] **GUI-01**: Custom TRENCH visual design (user provides direction)
- [ ] **GUI-02**: Morph knob/slider functional
- [ ] **GUI-03**: Q knob/slider functional
- [ ] **GUI-04**: Responsive UI updates with parameter changes

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Additional Presets

- **PRESET-01**: Additional Z-Plane filter presets captured (Phaser, Choir, etc.)
- **PRESET-02**: Preset browser/selector UI
- **PRESET-03**: 10-15 essential filters from Morpheus collection

### Platform Expansion

- **PLAT-01**: macOS build (Intel + Apple Silicon)
- **PLAT-02**: AU format support
- **PLAT-03**: Linux build

### Advanced Features

- **ADV-01**: Phantom 7th stage (hardware warmth)
- **ADV-02**: Drive/saturation control
- **ADV-03**: Wet/dry mix control
- **ADV-04**: Output gain control
- **ADV-05**: 6-Stage Envelope Generator

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Z-Plane branding | Clean IP, own patent filing |
| Formula reverse-engineering | Coefficient capture is more accurate |
| Multiple presets in v1 | Prove approach with one preset first |
| macOS/Linux in v1 | Windows-only simplifies validation |
| Phantom stage | v2 feature, focus on X3 match first |
| Ripper tools in plugin | Keep external Python tools separate, avoid AV triggers |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| BUILD-01 | Phase 1 | Pending |
| BUILD-02 | Phase 1 | Pending |
| BUILD-03 | Phase 1 | Pending |
| DSP-01 | Phase 2 | Pending |
| DSP-02 | Phase 2 | Pending |
| DSP-03 | Phase 2 | Pending |
| DSP-04 | Phase 2 | Pending |
| DSP-05 | Phase 2 | Pending |
| COEF-01 | Phase 3 | Pending |
| COEF-02 | Phase 3 | Pending |
| COEF-03 | Phase 4 | Pending |
| COEF-04 | Phase 4 | Pending |
| COEF-05 | Phase 4 | Pending |
| FGEN-01 | Phase 5 | Pending |
| FGEN-02 | Phase 5 | Pending |
| FGEN-03 | Phase 5 | Pending |
| FGEN-04 | Phase 5 | Pending |
| FGEN-05 | Phase 5 | Pending |
| FGEN-06 | Phase 5 | Pending |
| FGEN-07 | Phase 5 | Pending |
| FGEN-08 | Phase 5 | Pending |
| FGEN-09 | Phase 5 | Pending |
| MOD-01 | Phase 6 | Pending |
| MOD-02 | Phase 6 | Pending |
| MOD-03 | Phase 6 | Pending |
| MOD-04 | Phase 6 | Pending |
| MOD-05 | Phase 6 | Pending |
| CTRL-01 | Phase 7 | Pending |
| CTRL-02 | Phase 7 | Pending |
| CTRL-03 | Phase 7 | Pending |
| VAL-01 | Phase 8 | Pending |
| VAL-02 | Phase 8 | Pending |
| VAL-03 | Phase 8 | Pending |
| VAL-04 | Phase 8 | Pending |
| GUI-01 | Phase 9 | Pending |
| GUI-02 | Phase 9 | Pending |
| GUI-03 | Phase 9 | Pending |
| GUI-04 | Phase 9 | Pending |

**Coverage:**
- v1 requirements: 36 total
- Mapped to phases: 36
- Unmapped: 0

---
*Requirements defined: 2026-01-27*
*Last updated: 2026-01-27 after Function Generator scope expansion*
