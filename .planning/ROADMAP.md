# ROADMAP: TRENCH v1

**Core Value:** The sound must be 1:1 with Emulator X3
**Depth:** Comprehensive
**Created:** 2026-01-27

## Overview

TRENCH v1 delivers a single-preset (Talking Hedz) VST3 filter plugin for Windows that is sonically indistinguishable from Emulator X3. This includes the full 3x Function Generator modulation system that creates the characteristic "talking" effect.

The roadmap progresses: Build -> DSP Engine -> Coefficient Capture -> Interpolation -> Function Generator -> Modulation Routing -> Controls -> Validation -> GUI.

## Phases

### Phase 1: Build Foundation

**Goal:** Plugin loads successfully in a DAW and can pass audio.

**Dependencies:** None (foundation phase)

**Requirements:**
- BUILD-01: Plugin compiles without errors on Windows
- BUILD-02: VST3 loads successfully in DAW (tested in at least one host)
- BUILD-03: Standalone app launches and runs

**Success Criteria:**
1. Plugin compiles with zero errors and zero warnings on Windows
2. VST3 binary loads in at least one DAW without crashing (FL Studio, Reaper, or Ableton)
3. Standalone app window opens and remains responsive
4. Audio passes through the plugin unchanged when bypass/passthrough is active

**Plans:** 3 plans

Plans:
- [ ] 01-01-PLAN.md - Diagnose plugin loading and standalone build failures
- [ ] 01-02-PLAN.md - Apply fixes (constructor safety, standalone build)
- [ ] 01-03-PLAN.md - Validate working builds (pluginval, DAW test, passthrough)

---

### Phase 2: DSP Engine

**Goal:** Audio is processed through a working 5-stage biquad cascade using Direct Form I.

**Dependencies:** Phase 1 (plugin must load)

**Requirements:**
- DSP-01: Audio passes through plugin (bypass works)
- DSP-02: 5-stage cascaded biquad filter processes audio
- DSP-03: Direct Form I topology for stable morphing (NOT DF-II)
- DSP-04: Denormal protection prevents CPU spikes
- DSP-05: Control-rate coefficient updates (every 32-64 samples, not per-sample)

**Success Criteria:**
1. Pink noise input produces audibly filtered output (not silence, not passthrough)
2. Filter cascade modifies frequency spectrum visibly in a spectrum analyzer
3. CPU usage remains stable during extended playback (no spikes from denormals)
4. Hardcoded test coefficients produce predictable frequency response
5. Coefficient updates happen at control rate (not per-sample) verified by profiling

---

### Phase 3: Coefficient Capture

**Goal:** Complete Talking Hedz coefficient data extracted from X3 memory.

**Dependencies:** Phase 2 (DSP engine must be ready to consume coefficients)

**Requirements:**
- COEF-01: Talking Hedz coefficients captured from X3 memory
- COEF-02: Full morph sweep captured (not just 3 keyframes)

**Success Criteria:**
1. Full morph sweep coefficients captured (60+ frames across 0-100% morph range)
2. Q axis coefficients captured (at least 3 Q levels: 0%, 50%, 100%)
3. Captured data matches known reference points (M0_Q100, M100_Q100, M100_Q0)
4. Data stored in JSON format with clear structure
5. Capture tools remain external Python scripts (not linked into plugin)

---

### Phase 4: Interpolation System

**Goal:** Smooth morphing between coefficient states using v-space math.

**Dependencies:** Phase 3 (need captured coefficients to interpolate)

**Requirements:**
- COEF-03: Coefficients stored in v-space format
- COEF-04: v-space to biquad decode implemented
- COEF-05: Smooth interpolation across morph range

**Success Criteria:**
1. v-space encode/decode roundtrip produces identical biquad coefficients
2. Linear interpolation in v-space produces logarithmic frequency sweep
3. No pitch wobble or zipper noise during continuous morph sweep
4. Morph from 0% to 100% sounds continuous and musical (not stepped)

---

### Phase 5: Function Generator

**Goal:** 3x 64-step modulation sequencers with all E-mu playback modes.

**Dependencies:** Phase 4 (need interpolation working for modulation to have effect)

**Requirements:**
- FGEN-01: 64-step level sequencer per Function Generator
- FGEN-02: 64-step gate sequencer (trigger output)
- FGEN-03: 3 independent Function Generator instances
- FGEN-04: All playback modes (Forward, Reverse, Pendulum, Random, Brownian, One-Shot)
- FGEN-05: Smooth interpolation option (linear between steps)
- FGEN-06: Rate range 0.081 Hz to 18.147 Hz
- FGEN-07: Brownian motion with boundary bounce
- FGEN-08: Key sync (reset on note-on)
- FGEN-09: Grid quantization (Major, Minor, Chromatic, Octaves)

**Success Criteria:**
1. Function Generator produces 64-step waveform at correct rate range
2. All 6 playback modes produce distinct, correct behavior
3. Brownian mode bounces at boundaries (doesn't wrap or stop)
4. Smooth mode produces linear interpolation between steps
5. Grid quantization snaps output to correct intervals (1/12, 1/3, etc.)
6. Key sync resets phase on MIDI note-on
7. 3 instances run independently without interference

---

### Phase 6: Modulation Routing

**Goal:** Function Generators connected to filter parameters with E-mu modulation math.

**Dependencies:** Phase 5 (Function Generators must work)

**Requirements:**
- MOD-01: Function Generator to Morph modulation
- MOD-02: Function Generator to Q modulation
- MOD-03: Rate modulation input (exponential: Rate x 2^ModAmount)
- MOD-04: Length modulation (EndStep adjustment with wraparound)
- MOD-05: Direction modulation override

**Success Criteria:**
1. Function Generator output modulates Morph parameter smoothly
2. Function Generator output modulates Q parameter smoothly
3. Rate modulation is exponential (doubling, not linear addition)
4. Length modulation causes correct wraparound behavior
5. Direction modulation overrides static setting momentarily
6. Combined modulations produce the characteristic "talking" vowel movement

---

### Phase 7: Controls Integration

**Goal:** User can control filter via DAW-automatable parameters.

**Dependencies:** Phase 6 (modulation must work for full control)

**Requirements:**
- CTRL-01: Morph parameter (0-100%) controls Ah to Ee transition
- CTRL-02: Q parameter (0-100%) controls resonance amount
- CTRL-03: Parameters persist when DAW saves/loads project

**Success Criteria:**
1. Morph knob sweeps from "Ah" vowel sound (0%) to "Ee" vowel sound (100%)
2. Q knob audibly increases resonance (peaks become sharper)
3. Parameters save with DAW project and recall correctly on project load
4. Parameters are automatable from DAW automation lanes

---

### Phase 8: Validation

**Goal:** Sonic match to X3 reference recordings confirmed.

**Dependencies:** Phase 7 (need full working plugin to validate)

**Requirements:**
- VAL-01: FFT peaks match X3 reference at M0_Q100 (within +/-10%)
- VAL-02: FFT peaks match X3 reference at M100_Q100 (within +/-10%)
- VAL-03: FFT peaks match X3 reference at M100_Q0 (within +/-10%)
- VAL-04: Ear test confirms sonic match (A/B blind)

**Success Criteria:**
1. FFT analysis at M0_Q100 shows peaks at 178, 1077, 1701, 2498, 4915 Hz (+/-10%)
2. FFT analysis at M100_Q100 shows peaks at 221, 2417, 2719 Hz (+/-10%)
3. FFT analysis at M100_Q0 shows peaks at 215, 2024, 2681, 3047 Hz (+/-10%)
4. Blind A/B test passes: listener cannot distinguish TRENCH from X3
5. Python validation script runs and produces PASS result

---

### Phase 9: GUI Design

**Goal:** Polished custom visual interface for the filter.

**Dependencies:** Phase 8 (sound must be validated before polishing visuals)

**Requirements:**
- GUI-01: Custom TRENCH visual design (user provides direction)
- GUI-02: Morph knob/slider functional
- GUI-03: Q knob/slider functional
- GUI-04: Responsive UI updates with parameter changes

**Success Criteria:**
1. Custom visual design implemented per user direction (not default JUCE look)
2. Morph control is visually clear, responsive, and shows current value
3. Q control is visually clear, responsive, and shows current value
4. UI responds instantly to parameter changes (no visual lag)

---

## Progress

| Phase | Name | Requirements | Status |
|-------|------|--------------|--------|
| 1 | Build Foundation | BUILD-01, BUILD-02, BUILD-03 | Planned (3 plans) |
| 2 | DSP Engine | DSP-01, DSP-02, DSP-03, DSP-04, DSP-05 | Pending |
| 3 | Coefficient Capture | COEF-01, COEF-02 | Pending |
| 4 | Interpolation System | COEF-03, COEF-04, COEF-05 | Pending |
| 5 | Function Generator | FGEN-01 thru FGEN-09 | Pending |
| 6 | Modulation Routing | MOD-01 thru MOD-05 | Pending |
| 7 | Controls Integration | CTRL-01, CTRL-02, CTRL-03 | Pending |
| 8 | Validation | VAL-01, VAL-02, VAL-03, VAL-04 | Pending |
| 9 | GUI Design | GUI-01, GUI-02, GUI-03, GUI-04 | Pending |

**Total Requirements:** 36
**Phases:** 9

---
*Roadmap created: 2026-01-27*
*Updated: 2026-01-27 after Phase 1 planning*
