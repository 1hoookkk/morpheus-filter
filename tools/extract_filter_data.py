#!/usr/bin/env python3
"""
Extract Z-Plane FILTER coefficient data from EmulatorX.bin
Search for Morph filter tables specifically.
"""

import struct
import os

DLL_PATH = r"C:\Program Files\E-MU\Emulator X3\EmulatorX.bin"
IMAGE_BASE = 0x180000000

def parse_pe_sections(data):
    """Parse PE headers to get section info"""
    if data[:2] != b'MZ':
        raise ValueError("Not a valid PE file")
    pe_offset = struct.unpack_from('<I', data, 0x3C)[0]
    if data[pe_offset:pe_offset+4] != b'PE\x00\x00':
        raise ValueError("Invalid PE signature")
    coff_offset = pe_offset + 4
    num_sections = struct.unpack_from('<H', data, coff_offset + 2)[0]
    optional_header_size = struct.unpack_from('<H', data, coff_offset + 16)[0]
    section_offset = coff_offset + 20 + optional_header_size
    sections = []
    for i in range(num_sections):
        sec_data = data[section_offset + i*40 : section_offset + (i+1)*40]
        name = sec_data[:8].rstrip(b'\x00').decode('ascii', errors='ignore')
        virtual_size = struct.unpack_from('<I', sec_data, 8)[0]
        virtual_addr = struct.unpack_from('<I', sec_data, 12)[0]
        raw_size = struct.unpack_from('<I', sec_data, 16)[0]
        raw_offset = struct.unpack_from('<I', sec_data, 20)[0]
        sections.append({
            'name': name,
            'virtual_addr': virtual_addr,
            'virtual_size': virtual_size,
            'raw_offset': raw_offset,
            'raw_size': raw_size
        })
    return sections

def rva_to_file_offset(rva, sections):
    """Convert RVA to file offset"""
    for sec in sections:
        if sec['virtual_addr'] <= rva < sec['virtual_addr'] + sec['virtual_size']:
            return rva - sec['virtual_addr'] + sec['raw_offset']
    return None

def search_for_patterns(data, sections):
    """Search for coefficient-like patterns in data"""
    print("="*70)
    print("SEARCHING FOR Z-PLANE FILTER COEFFICIENT PATTERNS")
    print("="*70)

    # Z-Plane filter coefficients have specific patterns:
    # - a1 values: typically -1.9 to -1.3 (pole frequency related)
    # - radius: typically 0.85 to 0.999
    # - val1/val2/val3: typically 0.2 to 0.6

    # Our known golden master values for validation:
    known_values = [
        -1.974805,  # M0_Q100 S0 a1
        0.998231,   # M0_Q100 S0 radius
        0.548706,   # M0_Q100 val1
        -1.939721,  # M0_Q100 S1 a1
        -1.873399,  # M0_Q100 S2 a1
        -1.524112,  # M0_Q100 S3 a1
        -1.938511,  # M0_Q0 S0 a1
        0.959007,   # M0_Q0 S0 radius
    ]

    # Search in .rdata section
    rdata = None
    for sec in sections:
        if sec['name'] == '.rdata':
            rdata = sec
            break

    if not rdata:
        print("Could not find .rdata section")
        return

    start = rdata['raw_offset']
    end = start + rdata['raw_size']
    print(f"\nSearching .rdata section: offset 0x{start:x} to 0x{end:x}")
    print(f"Section size: {rdata['raw_size']} bytes ({rdata['raw_size']//8} doubles)")

    # Search for known a1 value (-1.974805)
    target_a1 = -1.974805
    target_bytes = struct.pack('<d', target_a1)

    print(f"\nSearching for known a1 value: {target_a1}")
    print(f"Bytes: {target_bytes.hex()}")

    pos = start
    matches = []
    while pos < end - 8:
        val = struct.unpack_from('<d', data, pos)[0]
        # Check if close to our known values
        for known in known_values:
            if abs(val - known) < 0.0001:
                matches.append((pos, val, known))
        pos += 8

    if matches:
        print(f"\nFound {len(matches)} potential matches:")
        for offset, val, known in matches:
            rva = offset - rdata['raw_offset'] + rdata['virtual_addr']
            addr = IMAGE_BASE + rva
            print(f"  File 0x{offset:06x} (addr 0x{addr:012x}): {val:.6f} (matches {known:.6f})")
    else:
        print("No exact matches found. Searching for similar patterns...")

    # Search for any value in the a1 range (-2.0 to -1.3)
    print("\n" + "="*70)
    print("SEARCHING FOR a1-LIKE VALUES (-2.0 to -1.3)")
    print("="*70)

    a1_candidates = []
    pos = start
    while pos < end - 8:
        val = struct.unpack_from('<d', data, pos)[0]
        if -2.0 < val < -1.3:
            a1_candidates.append((pos, val))
        pos += 8

    print(f"\nFound {len(a1_candidates)} values in a1 range:")
    for offset, val in a1_candidates[:50]:  # Show first 50
        rva = offset - rdata['raw_offset'] + rdata['virtual_addr']
        addr = IMAGE_BASE + rva
        print(f"  0x{addr:012x}: {val:.6f}")

    # Look for clusters of filter coefficients (5 a1 values close together)
    print("\n" + "="*70)
    print("SEARCHING FOR FILTER COEFFICIENT CLUSTERS")
    print("="*70)

    # Check for 5 consecutive values that look like filter poles
    pos = start
    while pos < end - 40:
        vals = [struct.unpack_from('<d', data, pos + i*8)[0] for i in range(5)]
        # Check if these look like filter a1 values
        if all(-2.0 < v < -1.0 for v in vals):
            rva = pos - rdata['raw_offset'] + rdata['virtual_addr']
            addr = IMAGE_BASE + rva
            print(f"\nCluster at 0x{addr:012x}:")
            for i, v in enumerate(vals):
                print(f"  [{i}]: {v:.6f}")
            # Also print the next 5 values (might be radii)
            next_vals = [struct.unpack_from('<d', data, pos + (5+i)*8)[0] for i in range(5)]
            print("  Following values (potential radii):")
            for i, v in enumerate(next_vals):
                print(f"  [{5+i}]: {v:.6f}")
        pos += 8

    # Search for radius-like values (0.85 to 0.9999) in clusters
    print("\n" + "="*70)
    print("SEARCHING FOR RADIUS CLUSTERS (0.85 to 0.9999)")
    print("="*70)

    pos = start
    while pos < end - 40:
        vals = [struct.unpack_from('<d', data, pos + i*8)[0] for i in range(5)]
        # Check if these look like radius values
        if all(0.85 < v < 1.0 for v in vals):
            rva = pos - rdata['raw_offset'] + rdata['virtual_addr']
            addr = IMAGE_BASE + rva
            print(f"\nRadius cluster at 0x{addr:012x}:")
            for i, v in enumerate(vals):
                print(f"  [{i}]: {v:.6f}")
        pos += 8

def dump_data_section(data, sections):
    """Dump the .data section looking for runtime filter tables"""
    print("\n" + "="*70)
    print("CHECKING .data SECTION FOR FILTER TABLES")
    print("="*70)

    data_sec = None
    for sec in sections:
        if sec['name'] == '.data':
            data_sec = sec
            break

    if not data_sec:
        print("Could not find .data section")
        return

    start = data_sec['raw_offset']
    end = start + min(data_sec['raw_size'], 0x10000)  # First 64KB

    print(f"\nSearching .data section: offset 0x{start:x}")

    # Look for sequences that look like filter coefficients
    pos = start
    found_patterns = 0
    while pos < end - 80 and found_patterns < 10:
        # Read 10 doubles
        vals = [struct.unpack_from('<d', data, pos + i*8)[0] for i in range(10)]

        # Check if this looks like filter data:
        # - Mix of negative values (a1) and values 0-1 (radius/val)
        neg_count = sum(1 for v in vals if -2.0 < v < 0)
        pos_small = sum(1 for v in vals if 0 < v < 1.0)

        if neg_count >= 3 and pos_small >= 3:
            rva = pos - data_sec['raw_offset'] + data_sec['virtual_addr']
            addr = IMAGE_BASE + rva
            print(f"\nPotential filter data at 0x{addr:012x}:")
            for i, v in enumerate(vals):
                print(f"  [{i}]: {v:15.6f}")
            found_patterns += 1
        pos += 8

def main():
    with open(DLL_PATH, 'rb') as f:
        data = f.read()

    print(f"Loaded: {DLL_PATH}")
    print(f"Size: {len(data)} bytes\n")

    sections = parse_pe_sections(data)
    for sec in sections:
        print(f"Section {sec['name']:10s}: VA=0x{sec['virtual_addr']:08x}, RawOff=0x{sec['raw_offset']:08x}, Size=0x{sec['virtual_size']:x}")

    search_for_patterns(data, sections)
    dump_data_section(data, sections)

if __name__ == '__main__':
    main()
