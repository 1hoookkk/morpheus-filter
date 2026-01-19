# Codebase Structure

**Analysis Date:** 2026-01-20

## Directory Layout

```
C:/Users/hooki/yup/
├── .claude/                    # Claude Code configuration
├── .planning/                  # GSD planning documents
│   ├── codebase/              # Codebase analysis (this file)
│   ├── debug/                 # Debug investigation docs
│   │   └── resolved/          # Resolved issues
│   └── phases/                # Implementation phases
│       └── 01-dsp-engine/     # Phase 1 plans and summaries
├── Scripts/                    # Data regeneration scripts
├── Source/                     # Main source code
│   ├── dsp/                   # DSP implementation (primary)
│   └── external/              # Third-party headers
├── Tests/                      # C++ and Python tests
├── *.py                        # Validation/analysis scripts (root)
├── *.h                         # Legacy/alternative DSP headers (root)
├── *.json                      # Cartridge data files
├── *.wav                       # Reference audio files
└── *.png                       # Validation plots
```

## Directory Purposes

**Source/dsp/**
- Purpose: Primary DSP implementation for the Morpheus Filter
- Contains: Header-only C++ filter engine classes
- Key files: `ZPlaneFilter.h` (Trench namespace - main implementation)

**Source/external/**
- Purpose: Third-party dependencies (header-only)
- Contains: `json.hpp` (nlohmann/json for cartridge parsing)
- Generated: No
- Committed: Yes

**Tests/**
- Purpose: Test harnesses and validation scripts
- Contains: `test_cartridge_load.cpp`, `validate_against_reference.py`
- Key files: `test_cartridge_load.cpp` - C++ cartridge loading verification

**Scripts/**
- Purpose: Data processing and regeneration tools
- Contains: `regenerate_cartridge.py` - rebuilds cartridge JSON from raw captures
- Key files: Run when cartridge data needs correction

**.planning/**
- Purpose: Project planning, requirements, roadmap
- Contains: `PROJECT.md`, `ROADMAP.md`, `STATE.md`, `REQUIREMENTS.md`
- Key files: `ROADMAP.md` tracks phase completion

**.planning/phases/01-dsp-engine/**
- Purpose: Phase 1 (DSP Engine) implementation plans
- Contains: 5 plan files, 4 summary files, 1 UAT document
- Key files: `01-UAT.md` - user acceptance test results

**Root Directory Python Scripts:**
- Purpose: Validation, analysis, and debugging during development
- Contains: `validate_trench_v2.py`, `validate_zplane.py`, `compare_fft.py`, etc.
- Key files: `validate_trench_v2.py` - primary validation script

**Root Directory Header Files:**
- Purpose: Alternative/legacy DSP implementations (some deprecated)
- Contains: `ZPlaneFilter.h` (ZPlane namespace), `ZPlaneData.h`, `ZPlaneLoader.h`
- Note: `Source/dsp/ZPlaneFilter.h` (Trench namespace) is the current primary

## Key File Locations

**Entry Points:**
- `Source/dsp/ZPlaneFilter.h`: Primary filter engine (Trench::ZPlaneFilter)
- `Tests/test_cartridge_load.cpp`: Cartridge loading test main()

**Configuration:**
- `talking_hedz_cartridge.json`: Simple 5-keyframe cartridge (Q=100% captures)
- `talking_hedz_extracted.json`: Full 17x17 grid cartridge (374KB)
- `talking_hedz_complete.json`: Intermediate format with raw captures

**Core Logic:**
- `Source/dsp/ZPlaneFilter.h`: Complete filter implementation (477 lines)
- `ZPlaneData.h`: Data structures and coefficient formulas (127 lines)
- `ZPlaneLoader.h`: JSON parsing and embedded fallback data (154 lines)

**Testing:**
- `Tests/test_cartridge_load.cpp`: C++ cartridge verification
- `Tests/validate_against_reference.py`: Python reference comparison
- `validate_trench_v2.py`: Primary Python validation (root)

**Reference Data:**
- `hedz - m100q0.wav`: Reference recording (Morph=100%, Q=0%)
- `hedz - 5050.wav`: Reference recording (Morph=50%, Q=50%)
- `hedz - 0 0.wav`: Reference recording (Morph=0%, Q=0%)

**Documentation:**
- `ZPLANE_RECREATION_SPEC_X3.md`: Complete technical specification (722 lines)
- `.planning/PROJECT.md`: Project definition
- `.planning/ROADMAP.md`: Phase roadmap

## Naming Conventions

**Files:**
- C++ headers: `PascalCase.h` (e.g., `ZPlaneFilter.h`, `ZPlaneData.h`)
- Python scripts: `snake_case.py` (e.g., `validate_trench_v2.py`)
- JSON data: `snake_case.json` (e.g., `talking_hedz_cartridge.json`)
- Planning docs: `UPPERCASE.md` or `NN-kebab-case-SUFFIX.md`

**Directories:**
- Source code: `PascalCase` (e.g., `Source`, `Tests`, `Scripts`)
- Hidden config: `.lowercase` (e.g., `.planning`, `.claude`)
- DSP modules: `lowercase` (e.g., `dsp`, `external`)

**C++ Namespaces:**
- `Trench`: Primary implementation namespace (current)
- `ZPlane`: Alternative implementation namespace (legacy/root files)

**C++ Classes:**
- Filter classes: `ZPlaneFilter`, `BiquadSection`
- Data structs: `StageData`, `StageRaw`, `BiquadCoeffs`, `MorphKeyframe`
- Utility structs: `Ramp`, `HChipStage`

## Where to Add New Code

**New DSP Feature:**
- Primary code: `Source/dsp/ZPlaneFilter.h` (add to Trench namespace)
- Tests: `Tests/` directory, create `test_<feature>.cpp`
- Python validation: Root directory `validate_<feature>.py`

**New Data Structure:**
- Implementation: `Source/dsp/ZPlaneData.h` or inline in `ZPlaneFilter.h`
- JSON format changes: Update `ZPlaneLoader.h` parser

**New Cartridge/Preset:**
- Data file: Root directory `<name>_cartridge.json`
- Regeneration script: `Scripts/regenerate_<name>.py`

**Future Plugin Code (Phase 2):**
- Processor: `Source/PluginProcessor.h/.cpp` (to be created)
- Editor: `Source/PluginEditor.h/.cpp` (to be created)
- UI components: `Source/ui/` directory (to be created)

**Documentation:**
- Technical specs: Root directory `*.md`
- Planning docs: `.planning/` directory
- Phase plans: `.planning/phases/<phase-name>/`

## Special Directories

**.planning/debug/**
- Purpose: Investigation documents for issues encountered during development
- Generated: No (manually created during debugging)
- Committed: Yes
- Subdirectory: `resolved/` for completed investigations

**.planning/phases/**
- Purpose: Per-phase implementation plans and summaries
- Generated: No (created by /gsd commands)
- Committed: Yes
- Pattern: `NN-phase-name/` with `NN-PLAN.md` and `NN-SUMMARY.md` files

**Root Directory Artifacts:**
- `.png` files: Validation plots (generated, not committed per .gitignore)
- `.wav` files: Reference recordings (committed as test fixtures)
- `.obj` files: Compiled test objects (generated, not committed)

## File Size Reference

| File | Lines | Purpose |
|------|-------|---------|
| `Source/dsp/ZPlaneFilter.h` | 477 | Primary filter implementation |
| `ZPLANE_RECREATION_SPEC_X3.md` | 722 | Complete technical specification |
| `validate_trench_v2.py` | 403 | Primary Python validation |
| `ZPlaneData.h` (root) | 127 | Data structures |
| `ZPlaneLoader.h` (root) | 154 | JSON loader |
| `ZPlaneFilter.h` (root) | 195 | Alternative implementation |

## Deprecated/Legacy Files

Files in root directory with same names as `Source/dsp/` may be deprecated:
- `ZPlaneFilter.h` (root) - Alternative implementation in `ZPlane` namespace
- `ZPlaneData.h` (root) - May duplicate `Source/dsp/` version
- `ZPlaneLoader.h` (root) - Uses JUCE JSON, may conflict with nlohmann/json approach

**Recommendation:** Use `Source/dsp/ZPlaneFilter.h` (Trench namespace) as primary.

---

*Structure analysis: 2026-01-20*
