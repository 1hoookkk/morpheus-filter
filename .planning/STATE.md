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
**Plan:** 01-01 completed (Diagnostic)
**Status:** In progress - ready for Plan 02

**Progress:**
```
Phase 1: [===.......] 33%  Build Foundation (1/3 plans)
Phase 2: [..........] 0%   DSP Engine
Phase 3: [..........] 0%   Coefficient Capture
Phase 4: [..........] 0%   Interpolation System
Phase 5: [..........] 0%   Function Generator
Phase 6: [..........] 0%   Modulation Routing
Phase 7: [..........] 0%   Controls Integration
Phase 8: [..........] 0%   Validation
Phase 9: [..........] 0%   GUI Design
```

**Overall:** 0/36 requirements complete (0%) - BUILD-01 partially validated

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
- CMake build system exists
- Plugin builds but does not load in DAW (as of last test)
- DSP architecture exists but may need fixes

## Performance Metrics

| Metric | Target | Current |
|--------|--------|---------|
| Build time | <60s | Unknown |
| Plugin load time | <2s | Fails to load |
| CPU usage (idle) | <1% | Unknown |
| CPU usage (active) | <5% | Unknown |

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
- [ ] Install pluginval for automated VST3 validation
- [ ] Test Standalone launch (verify window opens)
- [ ] Test VST3 in DAW after pluginval passes

### Blockers

None currently.

## Session Continuity

**Last Session:** 2026-01-27 (Plan 01-01 execution)

**What Happened:**
- Executed Plan 01-01 (Diagnostic Plan)
- Discovered pluginval is not installed
- Confirmed Standalone builds successfully when explicitly targeted
- Verified VST3 bundle structure is correct
- Created diagnostic report with action items for Plan 02

**What's Next:**
1. Execute Plan 01-02 (Fix Issues) - install pluginval, test loading
2. Test Standalone app launches and remains responsive
3. Test VST3 in DAW after pluginval validation

**Open Questions:**
- What DAW should be primary test target? (FL Studio recommended in RESEARCH)
- Does the "fails to load" issue still exist with fresh build?

**Resolved Questions:**
- Is JUCE 8.0.1 installed correctly? **YES** - builds complete successfully
- Are there any CMake configuration issues? **NO** - all targets generate correctly

---
*State initialized: 2026-01-27*
*Last updated: 2026-01-27 after Plan 01-01 diagnostic completion*
