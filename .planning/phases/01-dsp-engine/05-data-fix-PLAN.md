---
phase: 01-dsp-engine
plan: 05
type: fix
wave: 4
depends_on: []
fixes: ["GAP-01"]
files_modified:
  - talking_hedz_extracted.json
  - Scripts/regenerate_cartridge.py
autonomous: true

must_haves:
  truths:
    - "Raw a1/r coefficients from Cheat Engine captures are the source of truth"
    - "Hz decoding formula: freq = arccos(-a1/(2*r)) * sr / (2*pi)"
    - "7.4 semitone tuning correction must be applied"
    - "Sparse morph points interpolated to fill 17x17 grid"
  artifacts:
    - path: "talking_hedz_extracted.json"
      provides: "Corrected 17x17x3 grid with accurate frequencies"
    - path: "Scripts/regenerate_cartridge.py"
      provides: "Reproducible cartridge generation from raw captures"
---

<objective>
Fix GAP-01: Regenerate `talking_hedz_extracted.json` from validated Cheat Engine captures.

The current JSON contains incorrect Hz values (likely from DLL extraction with RGB contamination). The correct raw a1/r coefficients are in `talking_hedz_complete.json`.

Output: Corrected `talking_hedz_extracted.json` that produces formants matching reference IRs.
</objective>

<context>
@talking_hedz_complete.json (raw a1/r coefficients from Cheat Engine)
@talking_hedz_extracted.json (current WRONG data - to be replaced)
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create cartridge regeneration script</name>
  <files>Scripts/regenerate_cartridge.py</files>
  <action>
Create `Scripts/regenerate_cartridge.py` that:

1. Loads raw a1/r coefficients from `talking_hedz_complete.json`
2. Decodes to Hz using: `freq = arccos(-a1/(2*r)) * sr / (2*pi)`
3. Applies 7.4 semitone tuning correction: `freq_corrected = freq * 2^(-7.4/12)`
4. Interpolates sparse morph points to 17x17 grid
5. Outputs corrected `talking_hedz_extracted.json`

Key data points in complete.json:
- Q=100%: morph_0, morph_25, morph_32_5, morph_45_8_climax, morph_50, morph_75, morph_100
- Q=0%: morph_0, morph_25, morph_50, morph_75, morph_100
- M=0% Q sweep: q_0, q_25, q_50, q_75, q_100

Interpolation approach:
- Use scipy.interpolate for smooth morph interpolation
- Linear interpolation sufficient for Q dimension (only 2-3 variants needed)
  </action>
  <verify>
Script runs without errors and produces JSON output
  </verify>
</task>

<task type="auto">
  <name>Task 2: Regenerate corrected JSON</name>
  <files>talking_hedz_extracted.json</files>
  <action>
Run the regeneration script:
```bash
python Scripts/regenerate_cartridge.py
```

Verify the output by checking key frequencies match Cheat Engine captures:
- Q=100%, M=100%, Stage 0: should be ~217 Hz (not 1371 Hz)
- Q=100%, M=100%, Stage 1: should be ~1565 Hz
  </action>
  <verify>
```python
import json
with open('talking_hedz_extracted.json') as f:
    data = json.load(f)
v2 = data['variants'][2]  # Q=100%
freq = v2['stages'][0]['freq_17x17'][16]  # M=100%
assert 200 < freq < 250, f"Stage 0 freq should be ~217 Hz, got {freq}"
print(f"PASS: Stage 0 freq = {freq:.1f} Hz")
```
  </verify>
</task>

<task type="auto">
  <name>Task 3: Re-run validation</name>
  <files>Tests/validate_against_reference.py</files>
  <action>
Re-run the validation script to verify formants now match:
```bash
python Tests/validate_against_reference.py
```

Expected: F1 offset should be <3 semitones (not 47 semitones)
  </action>
  <verify>
Validation output shows formant frequencies within expected range.
VAL-01 and VAL-02 should show meaningful RMS comparison (not just level matching).
  </verify>
</task>

</tasks>

<success_criteria>
- [ ] Regeneration script created and documented
- [ ] talking_hedz_extracted.json regenerated from raw Cheat Engine captures
- [ ] Q=100% M=100% Stage 0 frequency is ~217 Hz (not 1371 Hz)
- [ ] Validation shows formant match within 3 semitones of reference
- [ ] All changes committed
</success_criteria>
