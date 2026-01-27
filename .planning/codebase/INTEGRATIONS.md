# External Integrations

**Analysis Date:** 2026-01-27

## APIs & External Services

**None** - This is a fully offline audio plugin. No external APIs or web services.

## Data Storage

**Databases:**
- None - All data is file-based

**File Storage:**
- Local filesystem only
- Binary coefficient data embedded in plugin at build time
- JSON coefficient captures stored locally

**Caching:**
- None required - coefficients loaded once at plugin init

## File Formats

**Input Data:**
- `.wav` - E-mu Morpheus cube data file (`cubes_v1.01vc_170120.wav`)
- `.json` - Coefficient captures and filter libraries
- `.bin` - Pre-decoded binary coefficient ROM

**Audio:**
- `.wav` - Reference recordings for validation (`validation/`)
- Internal: 32-bit float audio buffers

## Authentication & Identity

**Auth Provider:**
- None - No licensing or auth system implemented

## Monitoring & Observability

**Error Tracking:**
- None - errors handled via JUCE assertions

**Logs:**
- `DBG()` macro (JUCE) - Debug console output only
- No file logging

## CI/CD & Deployment

**Hosting:**
- Local development only
- No cloud deployment

**CI Pipeline:**
- None configured
- Manual builds via `build.bat`

## Reverse Engineering Integrations

**EmulatorX.dll Integration:**
- Purpose: Extract filter coefficients from running Emulator X3 process
- Tool: `tools/ripper.py`, `tools/rip_all_data.py`
- Library: `pymem` (Windows process memory reading)
- Protocol: Direct memory read via Win32 API
- Address: Dynamic per session (typically `0x012EE640` area)

**Cheat Engine Integration:**
- Purpose: Manual coefficient exploration and capture
- Tool: `tools/ce_full_capture.lua`
- Protocol: Lua script executed in Cheat Engine console
- Required: Cheat Engine 7.x with Lua scripting

## Environment Configuration

**Required env vars:**
- None

**Build-time configuration:**
- `CMakeLists.txt` defines all plugin metadata
- Memory addresses hardcoded in Python scripts

**Secrets location:**
- None - no secrets required

## Webhooks & Callbacks

**Incoming:**
- None

**Outgoing:**
- None

## Hardware Integration

**MIDI:**
- Disabled (`NEEDS_MIDI_INPUT FALSE`, `NEEDS_MIDI_OUTPUT FALSE`)

**Audio Interface:**
- Via JUCE audio device manager (Standalone mode)
- Via host (VST3/AU mode)

## Third-Party Software Dependencies

**Development-time:**
| Software | Purpose | Required |
|----------|---------|----------|
| Emulator X3 | Source of filter coefficients | Optional |
| Cheat Engine | Memory analysis tool | Optional |
| Python 3.10+ | Run analysis/capture scripts | Optional |

**Runtime:**
| Software | Purpose | Required |
|----------|---------|----------|
| VST3 host (DAW) | Plugin hosting | Yes (or use Standalone) |
| Audio interface | Sound I/O | Yes (Standalone only) |

## Data Flow

```
[Emulator X3 Process]
        |
        | (pymem memory read)
        v
[Python capture scripts] --> [JSON coefficient files]
        |
        | (manual copy)
        v
[C++ plugin source] --> [Embedded binary data]
        |
        | (JUCE build)
        v
[VST3 Plugin] <--> [DAW Host]
```

## Validation Data Sources

**Reference Recordings:**
- `validation/bypassed-pinknoise.wav` - Dry reference signal
- `validation/hedzmorph0q100.wav` - X3 output at Morph=0%, Q=100%
- `validation/hedzmorph100q100.wav` - X3 output at Morph=100%, Q=100%
- `validation/hedzmorph100q0.wav` - X3 output at Morph=100%, Q=0%

**Coefficient Sources:**
- `TalkingHedz.json` - Validated keyframe coefficients
- `Source/Data/morpheus_zplane_library.json` - Full filter library
- `trench_full_capture_*.json` - Runtime sweep captures

---

*Integration audit: 2026-01-27*
