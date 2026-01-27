# Phase 1 Diagnostic Report

**Date:** 2026-01-27
**Plugin:** TRENCH VST3/Standalone
**Environment:** Windows, Visual Studio 2022, CMake, JUCE 8.0.1

## VST3 Validation (pluginval)

**Result:** NOT TESTED - pluginval not installed

### pluginval Status
- Not found in PATH
- Not found in common locations (Program Files, Chocolatey, LocalAppData)
- **Recommendation:** Install from https://github.com/Tracktion/pluginval/releases

### VST3 Bundle Structure Analysis (Manual)

The VST3 bundle appears structurally correct:

```
TRENCH.vst3/
  Contents/
    Resources/
      moduleinfo.json     [EXISTS - required metadata]
    x86_64-win/
      TRENCH.vst3         [EXISTS - 6.9 MB binary]
```

**Structural Assessment:** PASS - all required components present

### Key Observations
1. Binary size (6.9 MB) indicates full compilation with all modules linked
2. moduleinfo.json present (required for VST3 host scanning)
3. Bundle follows standard Windows VST3 structure

### Root Cause Analysis
Cannot determine VST3 loading issues without pluginval or DAW testing. Possible causes to investigate:
- Constructor exception (most likely if plugin fails to load silently)
- Binary data loading failure
- Parameter initialization error

## Standalone Build

**Result:** SUCCESS (after explicit build)

### Discovery
The Standalone target existed in CMakeLists.txt but was **never built**. The default build command was only building the VST3 target.

### Build Output
```
cmake --build build --config Release --target TRENCH_Standalone

TRENCH_Standalone.vcxproj -> C:\Users\hooki\do-it\build\TRENCH_artefacts\Release\Standalone\TRENCH.exe
```

### Verified Artifacts
- **TRENCH.exe** exists at `build/TRENCH_artefacts/Release/Standalone/`
- File size: 7.1 MB (indicates full compilation)

### Root Cause
Not a build system bug - the Standalone simply wasn't being built explicitly. The `FORMATS VST3 AU Standalone` in CMakeLists.txt is correct; it creates the target but doesn't automatically build all formats.

## Binary Data Files

**Status:** VERIFIED EXISTS

Files referenced in CMakeLists.txt:
| File | Status | Location |
|------|--------|----------|
| wav_decoded.bin | EXISTS | Source/Data/ |
| morpheus_zplane_library.json | EXISTS | Source/Data/ |

Additional files in Source/Data/:
- CubeNames.h
- morpheus_cubes_validated.json

## Available CMake Targets

```
ALL_BUILD.vcxproj
INSTALL.vcxproj
juce_vst3_helper.vcxproj
TRENCH.vcxproj              (shared code library)
TRENCH_All.vcxproj          (builds all formats)
TRENCH_rc_lib.vcxproj
TRENCH_Standalone.vcxproj   (standalone app)
TRENCH_VST3.vcxproj         (VST3 plugin)
TrenchData.vcxproj          (binary data)
ZERO_CHECK.vcxproj
```

**Recommendation:** Use `TRENCH_All` target to build all formats at once:
```bash
cmake --build build --config Release --target TRENCH_All
```

## Action Items for Plan 02

| Priority | Issue | Fix Required | File(s) |
|----------|-------|--------------|---------|
| HIGH | pluginval not installed | Download and install pluginval for proper VST3 validation | System (external tool) |
| HIGH | Unknown if VST3 loads | Test in AudioPluginHost or DAW with debugger | None (testing) |
| MEDIUM | Build script incomplete | Update build.bat to build all targets or use TRENCH_All | build.bat |
| LOW | No CI validation | Add pluginval to CI pipeline when created | CI config |

## Immediate Next Steps

1. **Install pluginval** - Download from GitHub releases and add to PATH
2. **Run pluginval validation** on VST3 with strictness level 5+
3. **Test Standalone launch** - Run TRENCH.exe to verify it opens without crash
4. **Test in DAW** if pluginval passes - Load in FL Studio/Reaper/Ableton

## Current Build Status

| Artifact | Exists | Size | Path |
|----------|--------|------|------|
| VST3 binary | YES | 6.9 MB | build/TRENCH_artefacts/Release/VST3/TRENCH.vst3 |
| Standalone | YES | 7.1 MB | build/TRENCH_artefacts/Release/Standalone/TRENCH.exe |
| Binary data | YES | N/A | Source/Data/*.bin, *.json |

## Recommendations

### For Plan 02: Fix Issues
1. Add constructor try/catch with logging for debugging load failures
2. Verify binary data can be loaded without exception
3. Test audio passthrough in Standalone before DAW testing

### For Development Workflow
Update `build.bat` to use:
```batch
cmake --build build --config Release --target TRENCH_All
```
This builds VST3 + Standalone in one command.

---
*Diagnostic completed: 2026-01-27*
