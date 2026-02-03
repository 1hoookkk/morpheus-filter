#!/usr/bin/env python3
"""
Dump the radius lookup tables found in EmulatorX.bin
"""

import struct

DLL_PATH = r"C:\Program Files\E-MU\Emulator X3\EmulatorX.bin"
IMAGE_BASE = 0x180000000

def parse_pe_sections(data):
    if data[:2] != b'MZ':
        raise ValueError("Not a valid PE file")
    pe_offset = struct.unpack_from('<I', data, 0x3C)[0]
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
        raw_offset = struct.unpack_from('<I', sec_data, 20)[0]
        sections.append({
            'name': name, 'virtual_addr': virtual_addr,
            'virtual_size': virtual_size, 'raw_offset': raw_offset
        })
    return sections

def rva_to_file_offset(rva, sections):
    for sec in sections:
        if sec['virtual_addr'] <= rva < sec['virtual_addr'] + sec['virtual_size']:
            return rva - sec['virtual_addr'] + sec['raw_offset']
    return None

def main():
    with open(DLL_PATH, 'rb') as f:
        data = f.read()

    sections = parse_pe_sections(data)

    # Dump first radius table (Q to radius mapping)
    print("="*70)
    print("RADIUS TABLE 1 (0x18065bb70) - Q to Radius Mapping")
    print("="*70)

    addr1 = 0x18065bb70
    rva1 = addr1 - IMAGE_BASE
    offset1 = rva_to_file_offset(rva1, sections)

    if offset1:
        print(f"\nFile offset: 0x{offset1:x}")
        print(f"{'Index':>5s} {'Address':>18s} {'Radius':>12s} {'Q equiv':>12s}")
        print("-" * 50)

        for i in range(128):  # Read 128 values
            val = struct.unpack_from('<d', data, offset1 + i*8)[0]
            if val < 0.5 or val > 1.0:
                break
            # Q approximation from radius
            q_approx = 1.0 / (2.0 * (1.0 - val)) if val < 0.9999 else 100.0
            addr = addr1 + i*8
            print(f"{i:5d} 0x{addr:012x} {val:12.6f} {q_approx:12.2f}")

    # Dump second radius table (inverse mapping)
    print("\n" + "="*70)
    print("RADIUS TABLE 2 (0x180717af0) - Inverse Radius Mapping")
    print("="*70)

    addr2 = 0x180717af0
    rva2 = addr2 - IMAGE_BASE
    offset2 = rva_to_file_offset(rva2, sections)

    if offset2:
        print(f"\nFile offset: 0x{offset2:x}")
        print(f"{'Index':>5s} {'Address':>18s} {'Radius':>12s}")
        print("-" * 40)

        for i in range(64):
            val = struct.unpack_from('<d', data, offset2 + i*8)[0]
            if val < 0.5 or val > 1.0:
                break
            addr = addr2 + i*8
            print(f"{i:5d} 0x{addr:012x} {val:12.6f}")

    # Dump the area around 0x1806d7a48 where we found some a1-like values
    print("\n" + "="*70)
    print("FILTER FREQUENCY DATA (0x1806d7a00 - 0x1806d8600)")
    print("="*70)

    start_addr = 0x1806d7a00
    rva = start_addr - IMAGE_BASE
    offset = rva_to_file_offset(rva, sections)

    if offset:
        print(f"\nFile offset: 0x{offset:x}")
        num_values = 256

        for i in range(num_values):
            val = struct.unpack_from('<d', data, offset + i*8)[0]
            if val != 0.0:
                addr = start_addr + i*8
                # Check if this could be a filter parameter
                note = ""
                if -2.0 < val < -1.0:
                    note = " <-- a1-like"
                elif 0.9 < val < 1.0:
                    note = " <-- radius-like"
                elif 0.4 < val < 0.7:
                    note = " <-- val1-like"
                print(f"0x{addr:012x}: {val:18.6f}{note}")

    # Look for formant frequency values (500-5000 Hz range when scaled)
    print("\n" + "="*70)
    print("SEARCHING FOR FORMANT FREQUENCIES (100-6000 range)")
    print("="*70)

    rdata = None
    for sec in sections:
        if sec['name'] == '.rdata':
            rdata = sec
            break

    if rdata:
        start = rdata['raw_offset']
        end = start + rdata['raw_size']

        formant_candidates = []
        pos = start
        while pos < end - 8:
            val = struct.unpack_from('<d', data, pos)[0]
            # Look for values in typical formant frequency range
            if 100 < val < 6000:
                formant_candidates.append((pos, val))
            pos += 8

        # Group candidates that are close together
        print(f"\nFound {len(formant_candidates)} values in formant frequency range")

        # Show clusters
        if formant_candidates:
            print("\nShowing values that cluster (potential formant tables):")
            prev_pos = 0
            cluster_start = None
            for pos, val in formant_candidates[:100]:
                if pos - prev_pos <= 64:  # Values within 8 doubles of each other
                    if cluster_start is None:
                        cluster_start = prev_pos
                    rva = pos - rdata['raw_offset'] + rdata['virtual_addr']
                    addr = IMAGE_BASE + rva
                    print(f"  0x{addr:012x}: {val:10.2f} Hz")
                else:
                    if cluster_start:
                        print()
                    cluster_start = None
                prev_pos = pos

if __name__ == '__main__':
    main()
