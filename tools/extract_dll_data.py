#!/usr/bin/env python3
"""
Extract coefficient data from EmulatorX.dll at specific addresses.
Uses PE file parsing to convert virtual addresses to file offsets.
"""

import struct
import os

# Path to the DLL/EXE (EmulatorX.bin is the extracted raw file)
DLL_PATH = r"C:\Program Files\E-MU\Emulator X3\EmulatorX.bin"

# Addresses from Ghidra decompilation (these are absolute virtual addresses)
# Image base is 0x180000000
IMAGE_BASE = 0x180000000

# Key addresses from the decompiled code
ADDRESSES = [
    0x1806f0df8,
    0x1806ecc28,
    0x1806ecc80,
    0x1806f0df0,
    0x1806f0de8,
    0x1806f0dd8,
    0x1806f0dd0,
    0x1806f0dc8,
    0x1806f0dc0,
    0x1806f0db8,
    0x1806f0cd8,
    0x1806f0cd0,
    0x1806f0cc8,
    0x1806f0cc0,
    0x1806f0cb8,
    # More from the decompiled functions
    0x1806ecb88,  # dVar3 multiplier
    0x1806ecc98,  # dVar4 multiplier
    0x1806ead30,  # dVar2
    0x1806ead28,  # uVar1
    0x1806f0e10,  # dVar5
    0x1806eb550,  # dVar3
]

def parse_pe_sections(data):
    """Parse PE headers to get section info"""
    # DOS header
    if data[:2] != b'MZ':
        raise ValueError("Not a valid PE file")

    pe_offset = struct.unpack_from('<I', data, 0x3C)[0]

    # PE signature
    if data[pe_offset:pe_offset+4] != b'PE\x00\x00':
        raise ValueError("Invalid PE signature")

    # COFF header
    coff_offset = pe_offset + 4
    num_sections = struct.unpack_from('<H', data, coff_offset + 2)[0]
    optional_header_size = struct.unpack_from('<H', data, coff_offset + 16)[0]

    # Section headers start after optional header
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
        print(f"Section {name}: VA=0x{virtual_addr:08x}, Size=0x{virtual_size:x}, RawOff=0x{raw_offset:x}")

    return sections

def rva_to_file_offset(rva, sections):
    """Convert RVA to file offset"""
    for sec in sections:
        if sec['virtual_addr'] <= rva < sec['virtual_addr'] + sec['virtual_size']:
            return rva - sec['virtual_addr'] + sec['raw_offset']
    return None

def main():
    dll_path = DLL_PATH
    if not os.path.exists(dll_path):
        print(f"DLL not found: {dll_path}")
        # Try alternate paths
        alt_paths = [
            r"C:\Program Files (x86)\Creative Professional\E-MU EmulatorX3\EmulatorX.dll",
            r"C:\Program Files\E-MU\EmulatorX3\EmulatorX.dll",
            r"C:\Program Files\Creative\E-MU EmulatorX3\EmulatorX.dll",
        ]
        for p in alt_paths:
            if os.path.exists(p):
                dll_path = p
                print(f"Found at: {p}")
                break
        else:
            print("Please provide the correct path to EmulatorX.dll")
            return

    with open(dll_path, 'rb') as f:
        data = f.read()

    print(f"\nParsing PE file: {dll_path}")
    print(f"File size: {len(data)} bytes\n")

    sections = parse_pe_sections(data)

    print("\n" + "="*60)
    print("COEFFICIENT VALUES AT SPECIFIED ADDRESSES")
    print("="*60 + "\n")

    for addr in sorted(set(ADDRESSES)):
        rva = addr - IMAGE_BASE
        file_offset = rva_to_file_offset(rva, sections)

        if file_offset is None:
            print(f"0x{addr:012x}: RVA 0x{rva:08x} - NOT IN ANY SECTION")
            continue

        if file_offset + 8 > len(data):
            print(f"0x{addr:012x}: File offset 0x{file_offset:x} out of range")
            continue

        # Read as double (float64)
        value_double = struct.unpack_from('<d', data, file_offset)[0]
        # Also read as float32 for comparison
        value_float = struct.unpack_from('<f', data, file_offset)[0]
        # Raw bytes
        raw_bytes = data[file_offset:file_offset+8]

        print(f"0x{addr:012x} (file 0x{file_offset:06x}): {value_double:20.12f}  (float32: {value_float:.6f})  raw: {raw_bytes.hex()}")

    # Dump a range around the coefficient area
    print("\n" + "="*60)
    print("DUMP OF COEFFICIENT REGION (0x1806f0c00 - 0x1806f0e00)")
    print("="*60 + "\n")

    start_addr = 0x1806f0c00
    end_addr = 0x1806f0e20

    rva_start = start_addr - IMAGE_BASE
    file_start = rva_to_file_offset(rva_start, sections)

    if file_start:
        num_doubles = (end_addr - start_addr) // 8
        print(f"Reading {num_doubles} doubles starting at file offset 0x{file_start:x}\n")

        for i in range(num_doubles):
            addr = start_addr + i * 8
            offset = file_start + i * 8
            value = struct.unpack_from('<d', data, offset)[0]
            if value != 0.0:  # Only print non-zero values
                print(f"DAT_{addr:012x}: {value:20.12f}")

    # Also dump the second region mentioned
    print("\n" + "="*60)
    print("DUMP OF ECC REGION (0x1806ecb80 - 0x1806ecf00)")
    print("="*60 + "\n")

    start_addr2 = 0x1806ecb80
    end_addr2 = 0x1806ecf00

    rva_start2 = start_addr2 - IMAGE_BASE
    file_start2 = rva_to_file_offset(rva_start2, sections)

    if file_start2:
        num_doubles2 = (end_addr2 - start_addr2) // 8
        print(f"Reading {num_doubles2} doubles starting at file offset 0x{file_start2:x}\n")

        for i in range(num_doubles2):
            addr = start_addr2 + i * 8
            offset = file_start2 + i * 8
            value = struct.unpack_from('<d', data, offset)[0]
            if value != 0.0:
                print(f"DAT_{addr:012x}: {value:20.12f}")

if __name__ == '__main__':
    main()
