# STATE: TRENCH

Project memory for Claude continuity across sessions.

## Project Reference

**Core Value:** The sound must be 1:1 with Emulator X3

**Current Focus:** Phase 1 - Build Foundation

**Key Files:**
- `.planning/PROJECT.md` - Project definition and constraints
- `.planning/REQUIREMENTS.md` - v1 requirements with traceability
- `.planning/ROADMAP.md` - Phase structure and success criteria
- `CLAUDE.md` - Technical spec (ARMAdillo, v-space, coefficient capture)
- `Source/PluginProcessor.cpp` - Main audio processing
- `Source/DSP/` - DSP components directory

## Current Position

**Phase:** 1 - Build Foundation
**Plan:** 01-02 completed (Fix Issues)
**Status:** In progress - ready for Plan 03 (Validation)

**Progress:**
```
Phase 1: [======....] 67%  Build Foundation (2/3 plans)
Phase 2: [..........] 0%   DSP Engine
Phase 3: [..........] 0%   Coefficient Capture
Phase 4: [..........] 0%   Interpolation System
Phase 5: [..........] 0%   Function Generator
Phase 6: [..........] 0%   Modulation Routing
Phase 7: [..........] 0%   Controls Integration
Phase 8: [..........] 0%   Validation
Phase 9: [..........] 0%   GUI Design
```

**Overall:** 0/36 requirements complete (0%) - BUILD-01 validated (compiles), BUILD-02/03 ready for testing

## Phase 1 Context

**Goal:** Plugin loads successfully in a DAW and can pass audio.

**Requirements:**
- BUILD-01: Plugin compiles without errors on Windows
- BUILD-02: VST3 loads successfully in DAW
- BUILD-03: Standalone app launches and runs

**Success Criteria:**
1. Plugin compiles with zero errors and zero warnings on Windows
2. VST3 binary loads in at least one DAW without crashing
3. Standalone app window opens and remains responsive
4. Audio passes through the plugin unchanged when bypass/passthrough is active

**Codebase State:**
- JUCE 8.0.1 framework configured
- CMake build system exists with TRENCH_All target
- VST3: 6.6 MB binary verified (clean rebuild 2026-01-27)
- Standalone: 6.8 MB binary verified (clean rebuild 2026-01-27)
- Constructor has try/catch error handling
- VST3 auto-installed to C:\Program Files\Common Files\VST3\

## Performance Metrics

| Metric | Target | Current |
|--------|--------|---------|
| Build time | <60s | ~90s (full rebuild with JUCE fetch) |
| Plugin load time | <2s | Pending test |
| CPU usage (idle) | <1% | Pending test |
| CPU usage (active) | <5% | Pending test |

## Accumulated Context

### Key Decisions

| Decision | Rationale | Date |
|----------|-----------|------|
| Coefficient capture over formula derivation | 1:1 accuracy guaranteed, formulas proved complex | 2026-01-27 |
| v-space interpolation | Direct coefficient interp causes pitch wobble | 2026-01-27 |
| Windows-only v1 | Simplify scope, validate sound first | 2026-01-27 |
| Single preset (Talking Hedz) | Prove the approach before expanding | 2026-01-27 |
| Direct Form I topology | Stable during coefficient morphing | 2026-01-27 |
| Full Function Generator system | Required for 1:1 "talking" behavior | 2026-01-27 |
| Constructor try/catch for initialization | Prevents silent plugin load failures | 2026-01-27 |
| TRENCH_All build target | Builds all formats (VST3 + Standalone) in one command | 2026-01-27 |

### Technical Discoveries

- X3 uses 5-stage cascade (not 7 like Morpheus hardware)
- Memory address for coefficients shifts on X3 restart
- flag=0 is lowpass, flag=1 is resonator
- 178 Hz peak in M0_Q100 comes from lowpass stage
- Function Generator is 64-step sequencer, not standard LFO
- Brownian mode bounces at boundaries
- **Standalone builds correctly** when explicitly targeted (TRENCH_Standalone)
- **VST3 bundle structure is valid** (6.9MB binary, moduleinfo.json present)
- **Use TRENCH_All target** to build all formats at once

### TODOs

- [x] Diagnose why plugin fails to load in DAW - **Needs retest; structure is valid**
- [x] Verify CMake configuration is correct - **CONFIRMED: targets exist, build works**
- [x] Add constructor safety (try/catch) - **DONE: Plan 01-02**
- [x] Clean rebuild verification - **DONE: VST3 6.6MB, Standalone 6.8MB**
- [ ] Install pluginval for automated VST3 validation
- [ ] Test Standalone launch (verify window opens)
- [ ] Test VST3 in DAW (FL Studio/Reaper recommended)

### Blockers

None currently.

## Session Continuity

**Last Session:** 2026-01-27 (Plan 01-02 execution)

**What Happened:**
- Executed Plan 01-02 (Fix Issues)
- Verified constructor safety already implemented (try/catch around initializePresets)
- Committed build.bat with TRENCH_All target
- Performed clean rebuild verification (both binaries verified)
- Created 01-02-SUMMARY.md

**What's Next:**
1. Execute Plan 01-03 (Validation) - test actual plugin loading
2. Test Standalone launch - verify window opens and audio works
3. Test VST3 in DAW - verify loads and passes audio

**Open Questions:**
- What DAW should be primary test target? (FL Studio recommended in RESEARCH)
- Does the plugin now load successfully with constructor safety?

**Resolved Questions:**
- Is JUCE 8.0.1 installed correctly? **YES** - builds complete successfully
- Are there any CMake configuration issues? **NO** - all targets generate correctly
- Does the build produce valid binaries? **YES** - VST3 6.6MB, Standalone 6.8MB verified

---
*State initialized: 2026-01-27*
*Last updated: 2026-01-27 after Plan 01-02 completion*
