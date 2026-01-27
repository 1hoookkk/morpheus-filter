# TRENCH

## What This Is

TRENCH is a VST3 filter effect plugin for Windows that recreates the E-mu Z-Plane filter sound. V1 ships a single preset ("Talking Hedz") that is sonically indistinguishable from Emulator X3's implementation. No Z-Plane branding — clean IP with original patent.

## Core Value

**The sound must be 1:1 with Emulator X3.** A/B blind test must pass. If the filter doesn't sound identical, nothing else matters.

## Requirements

### Validated

- [x] JUCE 8.0.1 plugin framework configured — existing
- [x] CMake build system with VST3/Standalone targets — existing
- [x] 7-stage cascaded biquad architecture defined — existing
- [x] Parameter management via APVTS — existing
- [x] WavCubeLoader for coefficient data — existing
- [x] Python validation tooling structure — existing

### Active

- [ ] Plugin loads successfully in DAW
- [ ] DSP engine processes audio through biquad cascade
- [ ] Talking Hedz coefficients captured from X3 (all morph/Q combinations)
- [ ] v-space interpolation for smooth morphing
- [ ] Morph control (0-100%: Ah → Ee transition)
- [ ] Q control (0-100%: flat → resonant)
- [ ] FFT peaks match X3 reference within tolerance
- [ ] Ear test confirms sonic match
- [ ] Custom TRENCH GUI design (user to provide direction)

### Out of Scope

- macOS/Linux builds — Windows only for v1
- Multiple filter presets — Talking Hedz only for v1
- AU format — VST3 only for v1
- Z-Plane branding — clean IP, own patent
- Formula reverse-engineering — capture approach for 1:1 accuracy

## Context

**Technical Background:**
- E-mu Z-Plane is a 6-stage morphing resonant filter from Morpheus/UltraProteus hardware
- Emulator X3 (software) implemented a 6-stage version, slightly "fizzier" than hardware
- Original used "ARMAdillo" coordinate system for coefficient interpolation
- Direct coefficient interpolation causes pitch wobble; v-space (log domain) required

**Current Codebase State:**
- Plugin builds but doesn't load in DAW (as of last test)
- Architecture: Processor-Editor MVC, 7-stage biquad cascade
- DSP uses Direct Form II Transposed (CLAUDE.md recommends DF-I for morphing)
- TrenchFilter.h exists but disabled
- v-space interpolation documented but not implemented
- Reference audio exists in validation/ folder

**Coefficient Capture:**
- Memory at X3 address contains final cooked biquad coefficients
- 5 stages, 12 bytes each: [a1: float][radius: float][flag: float]
- Validated captures exist for M0_Q100, M100_Q100, M100_Q0
- Full morph sweep capture possible via tools/ripper.py

**Validation Reference:**
- validation/bypassed-pinknoise.wav — dry reference
- validation/hedzmorph0q100.wav — X3 M0_Q100
- validation/hedzmorph100q100.wav — X3 M100_Q100
- validation/hedzmorph100q0.wav — X3 M100_Q0

## Constraints

- **Platform:** Windows 10/11 only for v1
- **Format:** VST3 plugin (production-ready for DAW use)
- **Accuracy:** Sonically indistinguishable from Emulator X3
- **Validation:** FFT comparison + ear test against reference recordings
- **IP:** No Z-Plane terminology in product — own patent filing

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Coefficient capture over formula derivation | 1:1 accuracy guaranteed, formulas proved complex | — Pending |
| v-space interpolation | Direct coefficient interp causes pitch wobble | — Pending |
| Windows-only v1 | Simplify scope, validate sound first | — Pending |
| Single preset (Talking Hedz) | Prove the approach before expanding | — Pending |

---
*Last updated: 2026-01-27 after initialization*
