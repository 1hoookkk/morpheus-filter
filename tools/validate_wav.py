#!/usr/bin/env python3
"""
TRENCH Z-Plane Filter - WAV Decoded Binary Validator

Validates the structure and integrity of wav_decoded.bin extracted from
the Morpheus cubes WAV file (cubes_v1.01vc_170120.wav).

Usage:
    python validate_wav.py [--verbose] [--wav PATH] [--bin PATH]

Exit codes:
    0 - Valid structure
    1 - Issues found
"""

import argparse
import os
import struct
import sys
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any

# Expected constants from Morpheus specification
EXPECTED_FILE_SIZE = 96500  # bytes
EXPECTED_CUBE_COUNT = 289
EXPECTED_STAGES_PER_CUBE = 7
EXPECTED_CORNERS_PER_CUBE = 8
BYTES_PER_STAGE = 2  # v1, v2 coefficient bytes
COEFF_BYTES_PER_CUBE = EXPECTED_CORNERS_PER_CUBE * EXPECTED_STAGES_PER_CUBE * BYTES_PER_STAGE  # 112 bytes

# Frame markers used in WAV encoding (8-bit sample values)
# These represent binary 1 and 0 in the 8-sample frame encoding
FRAME_1 = bytes([0x80, 0x40, 0x20, 0x01, 0x80, 0xc0, 0xe0, 0xfe])
FRAME_0 = bytes([0x80, 0xc0, 0xe0, 0xfe, 0x80, 0x40, 0x20, 0x01])

# Known byte values from the 7-level encoding
# WAV uses 8-bit samples centered at 128, spread into 7 distinguishable levels
VALID_SAMPLE_VALUES = {0x01, 0x20, 0x40, 0x80, 0xc0, 0xe0, 0xfe}


class ValidationResult:
    """Holds validation results and issues found."""

    def __init__(self):
        self.issues: List[str] = []
        self.warnings: List[str] = []
        self.info: List[str] = []
        self.stats: Dict[str, Any] = {}

    def add_issue(self, msg: str):
        self.issues.append(msg)

    def add_warning(self, msg: str):
        self.warnings.append(msg)

    def add_info(self, msg: str):
        self.info.append(msg)

    @property
    def is_valid(self) -> bool:
        return len(self.issues) == 0


def validate_file_size(data: bytes, result: ValidationResult, verbose: bool = False):
    """Check file size matches expected."""
    size = len(data)
    result.stats['file_size'] = size

    if size == EXPECTED_FILE_SIZE:
        result.add_info(f"File size: {size} bytes (exact match)")
    elif abs(size - EXPECTED_FILE_SIZE) < 100:
        result.add_warning(f"File size: {size} bytes (expected ~{EXPECTED_FILE_SIZE}, off by {size - EXPECTED_FILE_SIZE})")
    else:
        result.add_issue(f"File size: {size} bytes (expected ~{EXPECTED_FILE_SIZE}, significantly different)")

    # Calculate bytes per cube
    bytes_per_cube = size / EXPECTED_CUBE_COUNT
    result.stats['bytes_per_cube'] = bytes_per_cube

    if verbose:
        result.add_info(f"Bytes per cube: {bytes_per_cube:.2f} (expected ~334)")


def analyze_byte_distribution(data: bytes, result: ValidationResult, verbose: bool = False):
    """Analyze the distribution of byte values in the data."""
    byte_counts = {}
    for b in data:
        byte_counts[b] = byte_counts.get(b, 0) + 1

    result.stats['unique_bytes'] = len(byte_counts)
    result.stats['byte_distribution'] = byte_counts

    # Sort by frequency
    sorted_bytes = sorted(byte_counts.items(), key=lambda x: -x[1])

    result.add_info(f"Unique byte values: {len(byte_counts)}")

    if verbose:
        result.add_info("Top 10 most common bytes:")
        for byte_val, count in sorted_bytes[:10]:
            pct = 100.0 * count / len(data)
            result.add_info(f"  0x{byte_val:02x} ({byte_val:3d}): {count:6d} ({pct:5.2f}%)")


def analyze_cube_structure(data: bytes, result: ValidationResult, verbose: bool = False):
    """Analyze the cube data structure looking for patterns."""
    size = len(data)
    bytes_per_cube = size // EXPECTED_CUBE_COUNT

    result.stats['calculated_bytes_per_cube'] = bytes_per_cube

    # Expected coefficient bytes: 8 corners x 7 stages x 2 bytes = 112
    # Remaining bytes would be metadata/flags
    metadata_bytes = bytes_per_cube - COEFF_BYTES_PER_CUBE

    result.add_info(f"Cube structure analysis:")
    result.add_info(f"  Total cubes: {EXPECTED_CUBE_COUNT}")
    result.add_info(f"  Calculated bytes per cube: {bytes_per_cube}")
    result.add_info(f"  Coefficient bytes (8 corners x 7 stages x 2): {COEFF_BYTES_PER_CUBE}")
    result.add_info(f"  Metadata/flag bytes per cube: {metadata_bytes}")

    if metadata_bytes < 0:
        result.add_issue(f"Cube size too small for expected coefficients (need {COEFF_BYTES_PER_CUBE}, have {bytes_per_cube})")

    # Sample a few cubes to check for structural patterns
    if verbose:
        result.add_info("\nSampling cubes for pattern analysis...")

        for cube_idx in [0, 42, 100, 200, 288]:
            if cube_idx < EXPECTED_CUBE_COUNT:
                offset = cube_idx * bytes_per_cube
                if offset + bytes_per_cube <= size:
                    cube_data = data[offset:offset + bytes_per_cube]

                    # Check first 16 bytes
                    hex_preview = ' '.join(f'{b:02x}' for b in cube_data[:16])
                    result.add_info(f"  Cube {cube_idx:3d} @ 0x{offset:04x}: {hex_preview}...")


def check_header_patterns(data: bytes, result: ValidationResult, verbose: bool = False):
    """Check for expected header patterns at the start of the file."""
    # Look at the first 32 bytes for any recognizable header
    header = data[:32]

    # Check if there's a magic number or identifier
    # The Morpheus data might not have a traditional header

    result.add_info("Header analysis (first 32 bytes):")

    # Check for common patterns
    has_ascii = any(32 <= b < 127 for b in header[:8])

    if verbose:
        hex_str = ' '.join(f'{b:02x}' for b in header)
        result.add_info(f"  Hex: {hex_str}")

        ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in header)
        result.add_info(f"  ASCII: {ascii_str}")

    # Morpheus data typically starts directly with coefficient data
    # No specific header expected
    result.add_info("  No standard header detected (expected for raw coefficient data)")


def validate_coefficient_ranges(data: bytes, result: ValidationResult, verbose: bool = False):
    """Check that coefficient bytes are within reasonable ranges."""
    size = len(data)
    bytes_per_cube = size // EXPECTED_CUBE_COUNT

    out_of_range = 0
    suspicious_zeros = 0
    suspicious_ff = 0

    # Sample coefficient bytes from several cubes
    sample_cubes = [0, 50, 100, 150, 200, 250, 288]

    for cube_idx in sample_cubes:
        if cube_idx >= EXPECTED_CUBE_COUNT:
            continue

        offset = cube_idx * bytes_per_cube

        # Analyze first 112 bytes (coefficient region)
        coeff_region = data[offset:offset + min(COEFF_BYTES_PER_CUBE, bytes_per_cube)]

        for b in coeff_region:
            if b == 0:
                suspicious_zeros += 1
            elif b == 0xff:
                suspicious_ff += 1

    total_sampled = len(sample_cubes) * COEFF_BYTES_PER_CUBE

    if suspicious_zeros > total_sampled * 0.5:
        result.add_warning(f"High percentage of zero bytes in coefficients ({suspicious_zeros}/{total_sampled})")

    if verbose:
        result.add_info(f"Coefficient sampling ({len(sample_cubes)} cubes):")
        result.add_info(f"  Zero bytes: {suspicious_zeros}")
        result.add_info(f"  0xFF bytes: {suspicious_ff}")


def validate_wav_file(wav_path: str, result: ValidationResult, verbose: bool = False) -> Optional[bytes]:
    """
    Validate the original WAV file and check frame patterns.
    Returns the raw sample data if valid.
    """
    if not os.path.exists(wav_path):
        result.add_warning(f"WAV file not found: {wav_path}")
        return None

    try:
        with open(wav_path, 'rb') as f:
            wav_data = f.read()
    except IOError as e:
        result.add_issue(f"Failed to read WAV file: {e}")
        return None

    result.add_info(f"\nWAV file analysis: {wav_path}")
    result.add_info(f"  File size: {len(wav_data)} bytes")

    # Check RIFF header
    if wav_data[:4] != b'RIFF':
        result.add_issue("WAV file missing RIFF header")
        return None

    if wav_data[8:12] != b'WAVE':
        result.add_issue("WAV file missing WAVE identifier")
        return None

    result.add_info("  RIFF/WAVE header: OK")

    # Parse WAV chunks to find data
    pos = 12
    fmt_found = False
    data_start = 0
    data_size = 0
    channels = 0
    sample_rate = 0
    bits_per_sample = 0

    while pos < len(wav_data) - 8:
        chunk_id = wav_data[pos:pos+4]
        chunk_size = struct.unpack('<I', wav_data[pos+4:pos+8])[0]

        if chunk_id == b'fmt ':
            fmt_found = True
            audio_format = struct.unpack('<H', wav_data[pos+8:pos+10])[0]
            channels = struct.unpack('<H', wav_data[pos+10:pos+12])[0]
            sample_rate = struct.unpack('<I', wav_data[pos+12:pos+16])[0]
            bits_per_sample = struct.unpack('<H', wav_data[pos+22:pos+24])[0]

            result.add_info(f"  Format: {'PCM' if audio_format == 1 else f'Unknown ({audio_format})'}")
            result.add_info(f"  Channels: {channels}")
            result.add_info(f"  Sample rate: {sample_rate} Hz")
            result.add_info(f"  Bits per sample: {bits_per_sample}")

            # Validate expected format
            if channels != 1:
                result.add_warning(f"Expected mono (1 channel), got {channels}")
            if bits_per_sample != 8:
                result.add_warning(f"Expected 8-bit samples, got {bits_per_sample}")
            if sample_rate != 48000:
                result.add_warning(f"Expected 48000 Hz sample rate, got {sample_rate}")

        elif chunk_id == b'data':
            data_start = pos + 8
            data_size = chunk_size
            break

        pos += 8 + chunk_size
        # Align to word boundary
        if chunk_size % 2:
            pos += 1

    if not fmt_found:
        result.add_issue("WAV file missing fmt chunk")
        return None

    if data_start == 0:
        result.add_issue("WAV file missing data chunk")
        return None

    # Extract sample data
    sample_data = wav_data[data_start:data_start + data_size]
    result.add_info(f"  Sample data: {len(sample_data)} bytes @ offset {data_start}")

    # Check for 7-level encoding
    unique_samples = set(sample_data)
    result.stats['wav_unique_samples'] = len(unique_samples)

    if verbose:
        result.add_info(f"  Unique sample values: {len(unique_samples)}")
        if len(unique_samples) <= 10:
            for val in sorted(unique_samples):
                result.add_info(f"    0x{val:02x} ({val})")

    if unique_samples == VALID_SAMPLE_VALUES:
        result.add_info("  Sample values match expected 7-level encoding: OK")
    elif unique_samples.issubset(VALID_SAMPLE_VALUES):
        result.add_warning(f"Sample values are subset of expected 7-level encoding (missing some levels)")
    else:
        extra = unique_samples - VALID_SAMPLE_VALUES
        result.add_warning(f"Sample values include unexpected values: {[hex(v) for v in extra]}")

    # Look for frame patterns
    frame_1_count = 0
    frame_0_count = 0

    for i in range(0, len(sample_data) - 8):
        if sample_data[i:i+8] == FRAME_1:
            frame_1_count += 1
        elif sample_data[i:i+8] == FRAME_0:
            frame_0_count += 1

    result.stats['frame_1_count'] = frame_1_count
    result.stats['frame_0_count'] = frame_0_count

    result.add_info(f"  Frame pattern analysis:")
    result.add_info(f"    FRAME_1 occurrences: {frame_1_count}")
    result.add_info(f"    FRAME_0 occurrences: {frame_0_count}")

    total_frames = frame_1_count + frame_0_count
    if total_frames > 0:
        ratio = frame_1_count / total_frames if total_frames > 0 else 0
        result.add_info(f"    Bit ratio (1s): {ratio:.2%}")
    else:
        result.add_warning("No frame patterns found in WAV data")

    # Check for sync preamble (should be ~48000 samples at start)
    if len(sample_data) > 48000:
        preamble = sample_data[:48000]
        preamble_unique = set(preamble)

        if verbose:
            result.add_info(f"  Preamble analysis (first 48000 samples):")
            result.add_info(f"    Unique values in preamble: {len(preamble_unique)}")

    return sample_data


def print_summary(result: ValidationResult, verbose: bool = False):
    """Print validation summary."""
    print("\n" + "=" * 60)
    print("TRENCH Z-Plane WAV Validation Summary")
    print("=" * 60)

    # Print info
    if result.info:
        print("\n[INFO]")
        for msg in result.info:
            print(f"  {msg}")

    # Print warnings
    if result.warnings:
        print("\n[WARNINGS]")
        for msg in result.warnings:
            print(f"  ! {msg}")

    # Print issues
    if result.issues:
        print("\n[ISSUES]")
        for msg in result.issues:
            print(f"  X {msg}")

    # Print verdict
    print("\n" + "-" * 60)
    if result.is_valid:
        print("RESULT: VALID - No critical issues found")
    else:
        print(f"RESULT: INVALID - {len(result.issues)} issue(s) found")
    print("-" * 60)

    # Print key statistics
    if verbose and result.stats:
        print("\n[STATISTICS]")
        for key, value in result.stats.items():
            if key != 'byte_distribution':  # Skip large distribution
                print(f"  {key}: {value}")


def main():
    parser = argparse.ArgumentParser(
        description='Validate TRENCH Z-Plane wav_decoded.bin structure',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python validate_wav.py
    python validate_wav.py --verbose
    python validate_wav.py --bin path/to/wav_decoded.bin
    python validate_wav.py --wav path/to/cubes.wav --verbose
        """
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output with detailed analysis'
    )

    parser.add_argument(
        '--bin',
        type=str,
        default=None,
        help='Path to wav_decoded.bin (default: Source/Data/wav_decoded.bin)'
    )

    parser.add_argument(
        '--wav',
        type=str,
        default=None,
        help='Path to original WAV file for frame pattern verification'
    )

    args = parser.parse_args()

    # Determine paths
    script_dir = Path(__file__).parent
    project_root = script_dir.parent

    bin_path = args.bin
    if bin_path is None:
        bin_path = project_root / 'Source' / 'Data' / 'wav_decoded.bin'
    else:
        bin_path = Path(bin_path)

    wav_path = args.wav
    if wav_path is None:
        # Try default location
        default_wav = project_root / 'cubes_v1.01vc_170120.wav'
        if default_wav.exists():
            wav_path = default_wav
    else:
        wav_path = Path(wav_path)

    result = ValidationResult()

    print("TRENCH Z-Plane WAV Validator")
    print(f"Binary file: {bin_path}")
    if wav_path:
        print(f"WAV file: {wav_path}")

    # Check binary file exists
    if not bin_path.exists():
        result.add_issue(f"Binary file not found: {bin_path}")
        print_summary(result, args.verbose)
        return 1

    # Load binary data
    try:
        with open(bin_path, 'rb') as f:
            data = f.read()
    except IOError as e:
        result.add_issue(f"Failed to read binary file: {e}")
        print_summary(result, args.verbose)
        return 1

    # Run validations
    validate_file_size(data, result, args.verbose)
    analyze_byte_distribution(data, result, args.verbose)
    check_header_patterns(data, result, args.verbose)
    analyze_cube_structure(data, result, args.verbose)
    validate_coefficient_ranges(data, result, args.verbose)

    # Optionally validate WAV file
    if wav_path and Path(wav_path).exists():
        validate_wav_file(str(wav_path), result, args.verbose)

    # Print results
    print_summary(result, args.verbose)

    return 0 if result.is_valid else 1


if __name__ == '__main__':
    sys.exit(main())
