# Roadmap: Morpheus Filter v1.0

**Created:** 2026-01-18
**Milestone:** v1.0 — Talking Hedz 1:1 Recreation

## Phase Overview

| Phase | Name | Goal | Requirements | Plans |
|-------|------|------|--------------|-------|
| 1 | DSP Engine | Grid-based filter that matches reference files | DSP-01 through DSP-08, VAL-01 through VAL-04 | 4 plans |
| 2 | Plugin Shell | VST3 wrapper with parameters | PLG-01 through PLG-06 | 0 plans |
| 3 | Visualizer | Real-time frequency response display | VIS-01 through VIS-05 | 0 plans |

---

## Phase 1: DSP Engine

**Goal:** Build the grid-based filter engine and validate against EmulatorX3 reference recordings.

**Why this first:** The DSP is the core value. If the filter doesn't sound right, nothing else matters. Validate accuracy before building UI.

**Plans:** 4 plans in 3 waves

Plans:
- [ ] 01-grid-interpolator-PLAN.md — Data structures, Hz/semitone conversion, trilinear interpolation
- [ ] 02-cartridge-loader-PLAN.md — JSON parsing with nlohmann/json, Hz-to-semitone on load
- [ ] 03-filter-engine-PLAN.md — 7-stage cascade biquad processor with ultrasonic bypass
- [ ] 04-validation-PLAN.md — Python reference implementation, RMS comparison, plots

Wave Structure:
| Wave | Plans | Can Run Parallel |
|------|-------|------------------|
| 1 | 01-grid-interpolator | - |
| 2 | 02-cartridge-loader, 03-filter-engine | Yes |
| 3 | 04-validation | - |

### Success Criteria

1. Filter loads `talking_hedz_extracted.json` and parses all 3 variants × 7 stages
2. Morph parameter sweeps through grid X-axis with audible formant changes
3. Q parameter interpolates between variants (Q=0% flatter, Q=100% resonant)
4. Cascade topology: signal flows stage0 → stage1 → ... → stage6
5. Reference file comparison: <3dB RMS error for M=100% Q=0% and M=50% Q=50%

### Requirements Covered

- DSP-01: Grid data loading
- DSP-02: Morph interpolation
- DSP-03: Q variant interpolation
- DSP-04: Biquad coefficient computation
- DSP-05: Cascade topology
- DSP-06: Ultrasonic bypass
- DSP-07: Sample rate warping
- DSP-08: Per-stage gain
- VAL-01: Reference match (m100q0)
- VAL-02: Reference match (5050)
- VAL-03: Audible formant changes
- VAL-04: Q behavior verification

### Deliverables

- `Source/dsp/GridInterpolator.h` — 17×17×3 grid lookup and interpolation
- `Source/dsp/ZPlaneEngine.h` — 7-stage cascade filter processor
- `Source/dsp/CartridgeLoader.h` — JSON parsing for cartridge files
- `Tests/validate_against_reference.py` — Automated accuracy testing

---

## Phase 2: Plugin Shell

**Goal:** Wrap the DSP engine in a functional VST3 plugin with automatable parameters.

**Why this second:** Once DSP is validated, wrap it for DAW use. Keep UI minimal — GenericAudioProcessorEditor is fine for this phase.

### Success Criteria

1. Plugin loads in Ableton Live, Reaper, and FL Studio without errors
2. Morph, Q, and Mix parameters appear in DAW automation lanes
3. Parameter changes are sample-accurate (no zipper noise)
4. Preset changes load different parameter snapshots
5. State save/restore works across DAW sessions

### Requirements Covered

- PLG-01: VST3 compilation and loading
- PLG-02: Morph parameter
- PLG-03: Q parameter
- PLG-04: Mix parameter
- PLG-05: Preset selector
- PLG-06: State persistence

### Deliverables

- `Source/PluginProcessor.h/.cpp` — AudioProcessor with parameter tree
- `Source/PluginEditor.h/.cpp` — Basic UI (can use GenericAudioProcessorEditor initially)
- `CMakeLists.txt` — JUCE 8.0.10 CMake build configuration
- `Builds/` — Platform-specific build outputs

---

## Phase 3: Visualizer

**Goal:** Add real-time frequency response visualization matching EmulatorX3 style.

**Why this last:** Visual polish. The plugin is already functional after Phase 2. Visualizer is UX enhancement.

### Success Criteria

1. Frequency response curve renders in plugin window
2. Curve updates in real-time as Morph/Q change
3. Visual style: gray background, cyan/green curve, grid lines
4. X-axis: 20Hz to 20kHz (logarithmic scale)
5. Y-axis: -24dB to +12dB (linear scale)

### Requirements Covered

- VIS-01: Real-time curve display
- VIS-02: Parameter-responsive updates
- VIS-03: EmulatorX3 visual style
- VIS-04: Frequency axis
- VIS-05: Amplitude axis

### Deliverables

- `Source/ui/FrequencyResponseDisplay.h/.cpp` — Custom JUCE component
- `Source/ui/PluginLookAndFeel.h/.cpp` — Custom styling
- Updated `PluginEditor` with visualizer integration

---

## Dependency Graph

```
Phase 1 (DSP Engine)
    │
    ▼
Phase 2 (Plugin Shell) ─── depends on Phase 1 DSP classes
    │
    ▼
Phase 3 (Visualizer) ─── depends on Phase 2 plugin structure
```

---

## Risk Register

| Risk | Impact | Mitigation |
|------|--------|------------|
| Reference files not representative | High | Test multiple Morph/Q positions, compare visually in SPAN |
| Cascade vs parallel uncertainty | Medium | Already confirmed via NotebookLM + extracted data analysis |
| Sample rate warping artifacts | Low | Use bilinear transform, test at 48kHz and 96kHz |
| JUCE 8.0.10 compatibility | Low | Use stable CMake API, avoid deprecated methods |

---

*Roadmap created: 2026-01-18*
*Last updated: 2026-01-19 after Phase 1 planning*
