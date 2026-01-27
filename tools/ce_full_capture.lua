-- TRENCH COMPLETE STRUCTURE CAPTURE
-- Captures the FULL filter data: pre-decode block + boost factor + coefficients
-- Run this in Cheat Engine Lua console while X3 is running

local COEFF_BASE = 0x012EE640  -- Live coefficient buffer (update if needed)
local FS = 44100

-- ============================================================
-- STRUCTURE MAP (relative to COEFF_BASE)
-- ============================================================
-- Offset -96 to -60: Pre-decode stages (Val1, Val2, Val3) x 5
-- Offset -56 to -48: More pre-decode data
-- Offset -44 to -28: Unknown (gain related?)
-- Offset -20: BOOST FACTOR (~1.75)
-- Offset -16: 1.0 (unity?)
-- Offset -12 to -4: Unknown
-- Offset 0 to +60: Coefficient block (a1, radius, flag) x 5
-- ============================================================

print("=" .. string.rep("=", 79))
print("TRENCH COMPLETE STRUCTURE CAPTURE")
print("Base address: " .. string.format("0x%08X", COEFF_BASE))
print("=" .. string.rep("=", 79))

-- ============================================================
-- RAW MEMORY DUMP (-96 to +72 bytes)
-- ============================================================
print("\n--- RAW MEMORY DUMP ---")
print("Offset   Address      Value        Interpretation")
print(string.rep("-", 70))

local raw_data = {}
for off = -96, 72, 4 do
    local addr = COEFF_BASE + off
    local val = readFloat(addr)
    raw_data[off] = val

    local note = ""
    if off >= 0 and off < 60 then
        local stage = math.floor(off / 12)
        local field = off % 12
        if field == 0 then note = string.format("S%d a1", stage)
        elseif field == 4 then note = string.format("S%d radius", stage)
        elseif field == 8 then note = string.format("S%d flag", stage)
        end
    elseif off == -20 then
        note = "BOOST FACTOR"
    elseif off == -16 then
        note = "unity?"
    elseif val and math.abs(val - 0.534912) < 0.01 then
        note = "~0.535 constant"
    elseif val and math.abs(val - 0.51) < 0.02 then
        note = "~0.51 constant"
    elseif val and val > -1.1 and val < -0.2 then
        note = "pre-decode val1?"
    elseif val and val > 0.2 and val < 0.6 then
        note = "pre-decode val2?"
    end

    if val then
        print(string.format("%+4d    0x%08X   %12.6f   %s", off, addr, val, note))
    end
end

-- ============================================================
-- PRE-DECODE BLOCK (Stages in reverse order, offset -96 to -48)
-- ============================================================
print("\n--- PRE-DECODE BLOCK (interpreted) ---")
print("Stage  Val1        Val2        Val3")
print(string.rep("-", 50))

-- Pre-decode appears to be 5 stages x 12 bytes, starting at -96
-- But the stage order might be reversed
for i = 0, 4 do
    local off = -96 + i * 12
    local v1 = raw_data[off] or 0
    local v2 = raw_data[off + 4] or 0
    local v3 = raw_data[off + 8] or 0
    print(string.format("  %d    %10.6f  %10.6f  %10.6f", i, v1, v2, v3))
end

-- ============================================================
-- MYSTERY/GAIN REGION (offset -44 to -4)
-- ============================================================
print("\n--- GAIN/MYSTERY REGION ---")
print("Offset  Value        Note")
print(string.rep("-", 40))

local gain_offsets = {-44, -40, -36, -32, -28, -24, -20, -16, -12, -8, -4}
for _, off in ipairs(gain_offsets) do
    local val = raw_data[off]
    local note = ""
    if off == -20 then note = "*** BOOST FACTOR ***"
    elseif off == -16 and val and math.abs(val - 1.0) < 0.01 then note = "unity"
    end
    if val then
        print(string.format("%+4d   %12.6f  %s", off, val, note))
    end
end

-- ============================================================
-- COEFFICIENT BLOCK (offset 0 to +60)
-- ============================================================
print("\n--- COEFFICIENT BLOCK ---")
print("Stage  Type   a1          radius      flag     Freq Hz")
print(string.rep("-", 65))

for i = 0, 4 do
    local off = i * 12
    local a1 = raw_data[off] or 0
    local r = raw_data[off + 4] or 0
    local flag = raw_data[off + 8] or 0

    local freq = 0
    if r > 0 and r < 1.1 then
        local c = -a1 / (2.0 * r)
        if c >= -1 and c <= 1 then
            freq = math.acos(c) * FS / (2 * math.pi)
        end
    end

    local ftype = flag > 0.5 and "RES" or "LP"
    print(string.format("  %d    [%s]  %10.6f  %10.6f  %4.1f    %7.1f",
          i, ftype, a1, r, flag, freq))
end

-- ============================================================
-- EXTRACT KEY VALUES FOR IMPLEMENTATION
-- ============================================================
print("\n--- KEY VALUES FOR TRENCH ---")
print(string.rep("-", 50))

local boost = raw_data[-20] or 1.0
print(string.format("BOOST_FACTOR = %.6f", boost))

-- Calculate what gain compensation might be needed
-- If cascade of 4 bandpass with b0 = (1-a2)/2 each...
local cascade_atten = 1.0
for i = 0, 3 do  -- First 4 stages are resonators
    local r = raw_data[i * 12 + 4] or 0.998
    local a2 = r * r
    local b0 = (1.0 - a2) * 0.5
    cascade_atten = cascade_atten * b0
end
print(string.format("Theoretical cascade attenuation: %.2e (%.1f dB)",
      cascade_atten, 20 * math.log(cascade_atten + 1e-30) / math.log(10)))
print(string.format("Compensation needed: %.1f dB",
      -20 * math.log(cascade_atten + 1e-30) / math.log(10)))

-- ============================================================
-- JSON OUTPUT FOR CARTRIDGE
-- ============================================================
print("\n--- JSON CARTRIDGE DATA ---")
print("{")
print('  "name": "Talking Hedz",')
print('  "captureTime": "' .. os.date("%Y-%m-%d %H:%M:%S") .. '",')
print(string.format('  "boostFactor": %.6f,', boost))

print('  "preDecodeBlock": [')
for i = 0, 4 do
    local off = -96 + i * 12
    local v1 = raw_data[off] or 0
    local v2 = raw_data[off + 4] or 0
    local v3 = raw_data[off + 8] or 0
    local comma = i < 4 and "," or ""
    print(string.format('    {"val1": %.6f, "val2": %.6f, "val3": %.6f}%s', v1, v2, v3, comma))
end
print('  ],')

print('  "gainRegion": {')
print(string.format('    "offset_m44": %.6f,', raw_data[-44] or 0))
print(string.format('    "offset_m40": %.6f,', raw_data[-40] or 0))
print(string.format('    "offset_m36": %.6f,', raw_data[-36] or 0))
print(string.format('    "offset_m32": %.6f,', raw_data[-32] or 0))
print(string.format('    "offset_m28": %.6f,', raw_data[-28] or 0))
print(string.format('    "offset_m24": %.6f,', raw_data[-24] or 0))
print(string.format('    "offset_m20_boost": %.6f,', raw_data[-20] or 0))
print(string.format('    "offset_m16": %.6f,', raw_data[-16] or 0))
print(string.format('    "offset_m12": %.6f,', raw_data[-12] or 0))
print(string.format('    "offset_m8": %.6f,', raw_data[-8] or 0))
print(string.format('    "offset_m4": %.6f', raw_data[-4] or 0))
print('  },')

print('  "coefficients": [')
for i = 0, 4 do
    local off = i * 12
    local a1 = raw_data[off] or 0
    local r = raw_data[off + 4] or 0
    local flag = raw_data[off + 8] or 0
    local comma = i < 4 and "," or ""
    print(string.format('    {"a1": %.6f, "radius": %.6f, "flag": %.1f}%s', a1, r, flag, comma))
end
print('  ]')
print("}")

print("\n" .. string.rep("=", 80))
print("CAPTURE COMPLETE - Copy the JSON above to your cartridge file")
print(string.rep("=", 80))
