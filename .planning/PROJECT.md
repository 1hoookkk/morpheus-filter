# Morpheus Filter

## What This Is

A VST3 audio plugin that recreates E-mu's formant filter technology using extracted coefficient data. No branding or historical references — just a tasteful, musical filter with a simple two-knob interface and real-time frequency visualization.

## Core Value

**1:1 accuracy with Talking Hedz cartridge.** If it doesn't match the EmulatorX3 reference files, it's wrong.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Grid-based filter engine using extracted 17×17×3 data
- [ ] Morph parameter (0-100%) sweeping filter configurations
- [ ] Q parameter (0-100%) interpolating between 3 variants
- [ ] Cascade topology with 7 biquad stages
- [ ] Mix control (wet/dry blend)
- [ ] Preset selector for cartridge selection
- [ ] Frequency response visualizer matching X3 style
- [ ] VST3 plugin wrapper

### Out of Scope

- E-mu/Z-Plane branding or historical references — clean slate
- Transform parameter — not needed for Talking Hedz
- Multiple simultaneous cartridges — one at a time
- MIDI learn / automation mapping — v2
- Additional cartridge extraction — Talking Hedz only for v1

## Context

**Technical Foundation:**
- Extracted data: `talking_hedz_extracted.json` (374KB, complete 17×17×3 grid)
- Source: EmulatorX.dll reverse-engineered via Cheat Engine + Python extraction
- Reference files: `hedz - m100q0.wav`, `hedz - 5050.wav`, etc.

**Key Discovery (2026-01-18):**
Q mechanism is NOT radius scaling — it's complete configuration interpolation. At Q=0%, resonant stages are pushed to ultrasonic frequencies (30-95kHz), effectively bypassing them. At Q=100%, stages are at audible formant frequencies.

**Validation Approach:**
Compare plugin output against EmulatorX3 reference recordings using FFT analysis. Target: <3dB RMS error across frequency bands.

## Constraints

- **Framework**: JUCE 8.0.10 — CMake-based build, juce_dsp module for IIR filters
- **Format**: VST3 primary, AU secondary
- **Sample Rate**: Must handle 44.1kHz (captured rate) and 48kHz/96kHz with proper warping
- **Latency**: Zero latency (IIR filters are sample-by-sample)
- **Data Source**: `talking_hedz_extracted.json` is the single source of truth

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Cascade topology | E-mu patents + documentation confirm series, not parallel | — Pending |
| Grid interpolation for Q | Extracted data shows Q=0% pushes stages ultrasonic, not radius scaling | — Pending |
| JUCE framework | Cross-platform, proven for audio plugins | — Pending |
| Diagonal morph traversal | Transform fixed at 0 for Talking Hedz simplicity | — Pending |

---
*Last updated: 2026-01-18 after project initialization*
