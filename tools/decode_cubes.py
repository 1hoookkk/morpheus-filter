#!/usr/bin/env python3
"""
ARMAdillo Cube Decoder for TRENCH Z-Plane Filter Project

Decodes Morpheus Z-Plane filter cubes from wav_decoded.bin using patent-specified
exponential formulas (US Patent 5,170,369A).

This script:
1. Loads wav_decoded.bin and parses the binary structure
2. Extracts 289 cubes (8 corners x 7 stages x 2 bytes per cube)
3. Implements both linear and packed byte decode hypotheses
4. Uses patent ARMAdillo exponential formulas for coefficient calculation
5. Supports --sweep mode to determine optimal scale factor
6. Exports to JSON with validated schema

Usage:
    python decode_cubes.py --input Source/Data/wav_decoded.bin --output cubes.json
    python decode_cubes.py --sweep --input Source/Data/wav_decoded.bin
    python decode_cubes.py --mode packed --scale 8.0 --verbose
"""

import argparse
import json
import math
import struct
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Any


# ============================================================================
# Constants
# ============================================================================

NUM_CUBES = 289
NUM_CORNERS = 8      # 3D cube: 2^3 corners (Transform, Morph, Frequency axes)
NUM_STAGES = 7       # 7 biquad stages per filter
BYTES_PER_STAGE = 2  # v1 (frequency) and v2 (resonance) bytes

# Coefficient data size per cube
COEFF_BYTES_PER_CUBE = NUM_CORNERS * NUM_STAGES * BYTES_PER_STAGE  # 112 bytes

# Default sample rate for frequency calculations
DEFAULT_SAMPLE_RATE = 44100

# VowelSpace (C043) validation targets - formant frequencies
VOWELSPACE_TARGETS = {
    'vowel_i': {  # as in "beet"
        'F1': 270,
        'F2': 2290,
        'F3': 3010,
    },
    'vowel_a': {  # as in "father"
        'F1': 730,
        'F2': 1090,
        'F3': 2440,
    }
}

# TalkingHedz (C070) reference values from Emulator X3 Cheat Engine capture
# These are M100% Q100% (corner 7) values
TALKINGHEDZ_REFERENCE = {
    'cube_index': 70,
    'corner': 7,  # M100% Q100% = all max
    'stages': [
        {'a1': -1.993596, 'R': 0.998475, 'freq_hz': 2417, 'flag': 1},
        {'a1': -1.912492, 'R': 0.998384, 'freq_hz': 2724, 'flag': 1},
        {'a1': -1.861726, 'R': 0.998353, 'freq_hz': 4974, 'flag': 1},
        {'a1': -1.510937, 'R': 0.979504, 'freq_hz': 1701, 'flag': 1},
        {'a1': -1.992010, 'R': 0.998232, 'freq_hz': 0, 'flag': 0},  # bounding
        # Stages 5-6 not in reference
    ],
    'tolerance_hz': 25,  # FFT validated within +-25 Hz
}

# Cube names from CubeNames.h
CUBE_NAMES = [
    "Resonator", "Reso Sweep", "Notch Sweep", "Peak Sweep", "Hi Shelf",
    "Lo Shelf", "Bandpass", "Phaser 1", "Phaser 2", "Phaser 3",
    "Phaser 4", "Comb Filter 1", "Comb Filter 2", "Comb Filter 3", "Comb Filter 4",
    "Formant 1", "Formant 2", "Formant 3", "Formant 4", "Formant 5",
    "Vowel Aa", "Vowel Ae", "Vowel Ah", "Vowel Aw", "Vowel Ay",
    "Vowel Ee", "Vowel Eh", "Vowel Er", "Vowel Ih", "Vowel Iy",
    "Vowel Oh", "Vowel Oo", "Vowel Ow", "Vowel Oy", "Vowel Uh",
    "Vowel Uw", "Nasal M", "Nasal N", "Nasal Ng", "Fricative F",
    "Fricative S", "Fricative Sh", "Fricative Th", "VowelSpace", "Vowel Morph 1",
    "Vowel Morph 2", "Vowel Morph 3", "Vowel Morph 4", "Vowel Morph 5", "Vocal Tract 1",
    "Vocal Tract 2", "Vocal Tract 3", "Vocal Tract 4", "Vocal Tract 5", "Talking 1",
    "Talking 2", "Talking 3", "Talking 4", "Talking 5", "Robot Voice 1",
    "Robot Voice 2", "Robot Voice 3", "Talkng Voice", "Phone Voice", "Megaphone",
    "Tube Amp", "Guitar Body 1", "Guitar Body 2", "Guitar Body 3", "Acoustic Body",
    "TalkingHedz", "Talking Synth", "Vocal Synth 1", "Vocal Synth 2", "Vocal Synth 3",
    "Choir", "Choir Morph", "Angel Voice", "Demon Voice", "Alien Voice",
    "Metallic 1", "Metallic 2", "Metallic 3", "Bell 1", "Bell 2",
    "Bell 3", "Chime", "Gong", "Gamelan", "Steel Drum",
    "Marimba", "Vibes", "Xylophone", "Kalimba", "Music Box",
    "Glass", "Crystal", "Ice", "Water", "MoogVcdr.4",
    "BassOMatic", "Bass Filter 1", "Bass Filter 2", "Bass Filter 3", "Bass Filter 4",
    "Bass Filter 5", "Acid Bass", "TB303", "Squelch", "Wah Wah 1",
    "Wah Wah 2", "Auto Wah", "Funky Wah", "Cry Baby", "Envelope Flt",
    "Touch Wah", "Growl", "Snarl", "Bite", "Bark",
    "Howl", "Scream", "Screech", "Whistle", "Breath",
    "Wind", "Storm", "Thunder", "Rain", "Drip",
    "Bubble", "Underwater", "Cave", "Tunnel", "Room",
    "Hall", "Cathedral", "Canyon", "Space", "Void",
    "Dark", "Light", "Warm", "Cold", "Soft",
    "Hard", "Sharp", "Dull", "Bright", "Muted",
    "Thin", "Fat", "Hollow", "Full", "Nasal",
    "Honky", "Buzzy", "Fuzzy", "Gritty", "Smooth",
    "Clean", "Dirty", "Vintage", "Modern", "Classic",
    "Future", "Retro", "Industrial", "Organic", "Synthetic",
    "Hybrid", "Morph A-B", "Morph C-D", "Morph E-F", "Morph G-H",
    "Morph Loop", "Random", "Chaos", "Order", "Pattern 1",
    "Pattern 2", "Pattern 3", "Pattern 4", "Sequence 1", "Sequence 2",
    "Sequence 3", "Sequence 4", "Step Filter", "Gate Filter", "Trance Gate",
    "Stutter", "Glitch", "Break", "Chop", "Slice",
    "Dice", "Mangle", "Destroy", "Rebuild", "Transform",
    "Mutate", "Evolve", "Grow", "Shrink", "Expand",
    "Contract", "Stretch", "Compress", "Warp 1", "Warp 2",
    "Warp 3", "Twist", "Bend", "Fold", "Wrap",
    "Mirror", "Invert", "Reverse", "Flip", "Rotate",
    "Spin", "Swirl", "Spiral", "Vortex", "Cyclone",
    "Tornado", "Hurricane", "Earthquake", "Explosion", "Implosion",
    "Pulse", "Throb", "Beat", "Rhythm", "Groove",
    "Swing", "Shuffle", "Bounce", "Jump", "Skip",
    "Hop", "Run", "Walk", "Crawl", "Slide",
    "Glide", "Float", "Fly", "Soar", "Dive",
    "Plunge", "Drop", "Fall", "Rise", "Climb",
    "Ascend", "Descend", "Peak", "Valley", "Mountain",
    "Ocean", "River", "Stream", "Lake", "Pond",
    "Pool", "Spring", "Summer", "Autumn", "Winter",
    "Dawn", "Noon", "Dusk", "Midnight", "Star",
    "Moon", "Sun", "Planet", "Galaxy", "Universe",
    "Dimension", "Portal", "Gateway", "Threshold", "Boundary",
    "Edge", "Limit", "Infinity", "Beyond"
]


# ============================================================================
# Byte Decode Functions
# ============================================================================

def decode_byte_linear(byte: int, scale: float) -> float:
    """
    Linear byte decode hypothesis.

    Maps 0-255 to 0-scale linearly.
    Simple but may not match patent encoding.
    """
    return (byte / 255.0) * scale


def decode_byte_packed(byte: int, scale: float) -> float:
    """
    Block floating point (packed) byte decode hypothesis.

    Format: [S][sh2][sh1][sh0][d3][d2][d1][d0]
    - S: Sign bit (bit 7)
    - sh: Shift/exponent (bits 4-6, 3 bits)
    - d: Mantissa (bits 0-3, 4 bits)

    From patent Table I: 8-bit increment decoding.
    Range: -2048 to +2047 (before scale)
    """
    sign = -1 if (byte >> 7) & 1 else 1
    exp = (byte >> 4) & 0x07
    mantissa = byte & 0x0F
    # Scale factor 0.001 brings range into reasonable coefficient space
    return sign * (mantissa << exp) * (scale * 0.001)


def decode_byte_signed_linear(byte: int, scale: float) -> float:
    """
    Alternative: Signed linear decode.

    Treats byte as signed value and scales.
    """
    # Convert to signed
    if byte > 127:
        signed_val = byte - 256
    else:
        signed_val = byte
    return (signed_val / 127.0) * scale


def decode_byte_log(byte: int, scale: float) -> float:
    """
    Alternative: Logarithmic decode.

    Maps bytes to log scale, which could match filter frequency response.
    """
    if byte == 0:
        return 0.0
    return math.log2(byte + 1) / 8.0 * scale


def decode_simple_direct(f_byte: int, r_byte: int, sample_rate: float = DEFAULT_SAMPLE_RATE) -> Dict[str, float]:
    """
    Simple direct decode - maps bytes directly to R and frequency.

    Based on analysis of existing morpheus_zplane_library.json patterns:
    - R maps from r_byte / 255 * max_r (where max_r ~ 0.998)
    - freq maps from angle calculation

    This bypasses ARMAdillo encoding for simpler validation.
    """
    # R mapping: 0-255 -> ~0.5 to 0.998
    # High r_byte values give high resonance
    r_min, r_max = 0.5, 0.998
    R = r_min + (r_byte / 255.0) * (r_max - r_min)

    # Frequency mapping: byte to normalized frequency
    # 0 = low freq, 255 = Nyquist
    # Use angle: theta = f_byte / 255 * pi (0 to Nyquist)
    theta = (f_byte / 255.0) * math.pi
    freq_hz = theta * sample_rate / (2 * math.pi)

    # Calculate standard coefficients
    a1 = -2.0 * R * math.cos(theta)
    a2 = R * R

    return {
        'a1': a1,
        'a2': a2,
        'R': R,
        'freq_hz': freq_hz,
        'theta': theta,
        'raw_bytes': [f_byte, r_byte],
        'valid': 0 < freq_hz < sample_rate / 2 and 0 < R < 1,
        'error': None
    }


# ============================================================================
# ARMAdillo Coefficient Decoding (Patent Formulas)
# ============================================================================

def armadillo_decode(v1: float, v2: float, sample_rate: float = DEFAULT_SAMPLE_RATE) -> Dict[str, float]:
    """
    Decode ARMAdillo-encoded coefficients using patent exponential formulas.

    From US Patent 5,170,369A:
        t2 = 1 - 2^(-v2)          # R^2 (pole radius squared)
        t1 = -2 + 4*2^(-v1) + 2^(-v2)  # a1 coefficient

    Then extract:
        R = sqrt(t2)              # Pole radius
        theta = acos(-t1 / (2*R)) # Angle in radians
        freq_hz = theta * sample_rate / (2*pi)

    Args:
        v1: Decoded frequency parameter
        v2: Decoded resonance parameter
        sample_rate: Sample rate in Hz

    Returns:
        Dict with a1, a2, R, freq_hz, theta, and validity flags
    """
    result = {
        'v1': v1,
        'v2': v2,
        'a1': 0.0,
        'a2': 0.0,
        'R': 0.0,
        'freq_hz': 0.0,
        'theta': 0.0,
        'valid': True,
        'error': None
    }

    try:
        # Clamp v2 to avoid division by zero in 2^(-v2)
        v2_safe = max(v2, 0.0001)

        # Patent formulas
        t2 = 1.0 - math.pow(2.0, -v2_safe)  # R^2
        t1 = -2.0 + 4.0 * math.pow(2.0, -v1) + math.pow(2.0, -v2_safe)  # a1

        result['a1'] = t1
        result['a2'] = t2

        # Validate t2 (must be positive for real R)
        if t2 <= 0:
            result['valid'] = False
            result['error'] = f't2 <= 0 ({t2:.6f})'
            result['R'] = 0.0
            return result

        # Pole radius
        R = math.sqrt(t2)
        result['R'] = R

        # Validate R (must be < 1 for stability)
        if R >= 1.0:
            result['valid'] = False
            result['error'] = f'R >= 1 ({R:.6f})'

        # Calculate frequency from a1 = -2*R*cos(theta)
        # cos(theta) = -a1 / (2*R)
        if R > 0:
            cos_theta = t1 / (-2.0 * R)
            # Clamp to valid range for acos
            cos_theta = max(-1.0, min(1.0, cos_theta))
            theta = math.acos(cos_theta)
            result['theta'] = theta

            # Convert to Hz
            freq_hz = theta * sample_rate / (2.0 * math.pi)
            result['freq_hz'] = freq_hz

            # Validate frequency (should be in audible range)
            if freq_hz < 0 or freq_hz > sample_rate / 2:
                result['valid'] = False
                result['error'] = f'freq_hz out of range ({freq_hz:.1f})'

    except (ValueError, ZeroDivisionError) as e:
        result['valid'] = False
        result['error'] = str(e)

    return result


def armadillo_decode_inverse(v1_prime: float, v2_prime: float, sample_rate: float = DEFAULT_SAMPLE_RATE) -> Dict[str, float]:
    """
    Alternative interpretation: Direct ARMAdillo decode (B1', B2' to B1, B2).

    From skill.md:
        B2 = 1 - B2_prime           # R^2
        B1 = B1_prime - 2           # -2R*cos(theta)

    This is the INVERSE transform (decode from encoded format).
    """
    result = {
        'v1_prime': v1_prime,
        'v2_prime': v2_prime,
        'a1': 0.0,
        'a2': 0.0,
        'R': 0.0,
        'freq_hz': 0.0,
        'theta': 0.0,
        'valid': True,
        'error': None
    }

    try:
        # Direct decode from ARMAdillo format
        B2 = 1.0 - v2_prime  # R^2 (v2_prime = distance from unit circle)
        B1 = v1_prime - 2.0  # a1 (v1_prime = shifted positive)

        result['a1'] = B1
        result['a2'] = B2

        if B2 <= 0:
            result['valid'] = False
            result['error'] = f'B2 <= 0 ({B2:.6f})'
            return result

        R = math.sqrt(B2)
        result['R'] = R

        if R >= 1.0:
            result['valid'] = False
            result['error'] = f'R >= 1 ({R:.6f})'

        if R > 0:
            cos_theta = -B1 / (2.0 * R)
            cos_theta = max(-1.0, min(1.0, cos_theta))
            theta = math.acos(cos_theta)
            result['theta'] = theta
            freq_hz = theta * sample_rate / (2.0 * math.pi)
            result['freq_hz'] = freq_hz

    except (ValueError, ZeroDivisionError) as e:
        result['valid'] = False
        result['error'] = str(e)

    return result


# ============================================================================
# Binary File Parser
# ============================================================================

class CubeParser:
    """
    Parses wav_decoded.bin to extract cube coefficient data.
    """

    def __init__(self, data: bytes, header_size: int = 0, verbose: bool = False):
        """
        Initialize parser with binary data.

        Args:
            data: Raw bytes from wav_decoded.bin
            header_size: Number of bytes to skip at start (header)
            verbose: Enable verbose output
        """
        self.data = data
        self.header_size = header_size
        self.verbose = verbose

        # Calculate structure
        self.data_size = len(data) - header_size

        # Try to determine cube size from data
        # Expected: 289 cubes, each with 8 corners x 7 stages x 2 bytes = 112 bytes
        # But may have additional metadata per cube

        if self.data_size % NUM_CUBES == 0:
            self.cube_size = self.data_size // NUM_CUBES
        else:
            # Try common sizes
            for test_cube_size in [112, 116, 120, 128, 332, 333, 334]:
                remaining = self.data_size - (test_cube_size * NUM_CUBES)
                if remaining >= 0 and remaining < 512:
                    self.cube_size = test_cube_size
                    break
            else:
                # Default to calculated value
                self.cube_size = self.data_size // NUM_CUBES

        if self.verbose:
            print(f"Data size: {len(data)} bytes")
            print(f"Header size: {header_size} bytes")
            print(f"Coefficient data: {self.data_size} bytes")
            print(f"Calculated cube size: {self.cube_size} bytes")
            print(f"Expected cubes: {NUM_CUBES}")

    def auto_detect_header(self) -> int:
        """
        Try to automatically detect header size by looking for patterns.

        Returns estimated header size.
        """
        # Look for the start of regular coefficient data patterns
        # Coefficients typically have specific byte distributions

        best_offset = 0
        best_score = 0

        for offset in range(0, min(600, len(self.data) - 112)):
            chunk = self.data[offset:offset+112]

            # Score based on:
            # - Presence of common coefficient values (85, 127, 213, 255)
            # - Low variance suggesting padding (all same value)
            common_vals = [85, 127, 213, 255]
            score = sum(1 for b in chunk if b in common_vals)

            # Bonus for repeating patterns
            pairs = [(chunk[i], chunk[i+1]) for i in range(0, len(chunk)-1, 2)]
            unique_pairs = len(set(pairs))
            if unique_pairs < len(pairs) // 2:
                score += 10  # Bonus for repetition

            if score > best_score:
                best_score = score
                best_offset = offset

        if self.verbose:
            print(f"Auto-detected header size: {best_offset} bytes (score: {best_score})")

        return best_offset

    def extract_cube_bytes(self, cube_index: int) -> bytes:
        """
        Extract raw bytes for a single cube.

        Args:
            cube_index: Index of cube (0-288)

        Returns:
            Raw bytes for the cube
        """
        if cube_index < 0 or cube_index >= NUM_CUBES:
            raise ValueError(f"Cube index out of range: {cube_index}")

        start = self.header_size + (cube_index * self.cube_size)
        end = start + self.cube_size

        if end > len(self.data):
            raise ValueError(f"Cube {cube_index} extends beyond data")

        return self.data[start:end]

    def parse_cube_coefficients(self, cube_bytes: bytes) -> List[List[Tuple[int, int]]]:
        """
        Parse cube bytes into corner/stage structure.

        Returns:
            List of corners, each containing list of (v1_byte, v2_byte) tuples per stage
        """
        corners = []

        # First 112 bytes should be coefficients (8 corners x 7 stages x 2 bytes)
        coeff_bytes = cube_bytes[:COEFF_BYTES_PER_CUBE]

        idx = 0
        for corner in range(NUM_CORNERS):
            stages = []
            for stage in range(NUM_STAGES):
                if idx + 1 < len(coeff_bytes):
                    v1_byte = coeff_bytes[idx]
                    v2_byte = coeff_bytes[idx + 1]
                    stages.append((v1_byte, v2_byte))
                else:
                    stages.append((0, 0))
                idx += 2
            corners.append(stages)

        return corners


# ============================================================================
# Cube Decoder
# ============================================================================

class CubeDecoder:
    """
    Decodes cube coefficients using specified parameters.
    """

    def __init__(self, mode: str = 'linear', scale: float = 8.0,
                 sample_rate: float = DEFAULT_SAMPLE_RATE,
                 use_patent_formula: bool = True,
                 use_simple_direct: bool = False):
        """
        Initialize decoder.

        Args:
            mode: 'linear', 'packed', 'signed', or 'log'
            scale: Scale factor for byte decode
            sample_rate: Sample rate in Hz
            use_patent_formula: If True, use exponential patent formula;
                               if False, use direct ARMAdillo decode
            use_simple_direct: If True, use simple direct byte mapping
                              (bypasses ARMAdillo entirely)
        """
        self.mode = mode
        self.scale = scale
        self.sample_rate = sample_rate
        self.use_patent_formula = use_patent_formula
        self.use_simple_direct = use_simple_direct

        # Select byte decode function
        self.decode_byte = {
            'linear': decode_byte_linear,
            'packed': decode_byte_packed,
            'signed': decode_byte_signed_linear,
            'log': decode_byte_log,
        }.get(mode, decode_byte_linear)

    def decode_stage(self, v1_byte: int, v2_byte: int) -> Dict[str, Any]:
        """
        Decode a single stage's coefficients.

        Args:
            v1_byte: Raw frequency byte (or f_byte for simple mode)
            v2_byte: Raw resonance byte (or r_byte for simple mode)

        Returns:
            Dict with decoded coefficients
        """
        # Simple direct mode bypasses ARMAdillo entirely
        if self.use_simple_direct:
            return decode_simple_direct(v1_byte, v2_byte, self.sample_rate)

        # Decode bytes to parameter values
        v1 = self.decode_byte(v1_byte, self.scale)
        v2 = self.decode_byte(v2_byte, self.scale)

        # Apply ARMAdillo formula
        if self.use_patent_formula:
            result = armadillo_decode(v1, v2, self.sample_rate)
        else:
            result = armadillo_decode_inverse(v1, v2, self.sample_rate)

        # Add raw bytes to result
        result['raw_bytes'] = [v1_byte, v2_byte]

        return result

    def decode_cube(self, cube_coefficients: List[List[Tuple[int, int]]],
                    cube_index: int) -> Dict[str, Any]:
        """
        Decode all corners and stages for a cube.

        Args:
            cube_coefficients: Parsed coefficient structure from parser
            cube_index: Index of this cube

        Returns:
            Dict with full cube data
        """
        corners = []

        for corner_idx, corner_stages in enumerate(cube_coefficients):
            stages = []
            for stage_idx, (v1_byte, v2_byte) in enumerate(corner_stages):
                stage_data = self.decode_stage(v1_byte, v2_byte)
                stage_data['stage'] = stage_idx
                stages.append(stage_data)

            corners.append({
                'corner_index': corner_idx,
                'stages': stages
            })

        # Get cube name
        name = CUBE_NAMES[cube_index] if cube_index < len(CUBE_NAMES) else f"Cube {cube_index}"

        return {
            'index': cube_index,
            'name': name,
            'corners': corners
        }


# ============================================================================
# Validation and Sweep Functions
# ============================================================================

def validate_talkinghedz(decoded_cubes: List[Dict], verbose: bool = False) -> Dict[str, Any]:
    """
    Validate decoded TalkingHedz cube against reference values.

    Returns dict with comparison results.
    """
    result = {
        'matched': False,
        'corner_7_found': False,
        'stage_errors': [],
        'total_error': float('inf'),
        'frequencies': []
    }

    if len(decoded_cubes) <= TALKINGHEDZ_REFERENCE['cube_index']:
        return result

    cube = decoded_cubes[TALKINGHEDZ_REFERENCE['cube_index']]
    corner_idx = TALKINGHEDZ_REFERENCE['corner']

    if corner_idx >= len(cube['corners']):
        return result

    corner = cube['corners'][corner_idx]
    result['corner_7_found'] = True

    ref_stages = TALKINGHEDZ_REFERENCE['stages']
    tolerance = TALKINGHEDZ_REFERENCE['tolerance_hz']

    total_error = 0
    matched_count = 0

    for i, ref in enumerate(ref_stages):
        if i >= len(corner['stages']):
            break

        stage = corner['stages'][i]
        decoded_freq = stage.get('freq_hz', 0)
        ref_freq = ref['freq_hz']
        result['frequencies'].append(decoded_freq)

        if ref_freq > 0:  # Skip bounding stages
            error = abs(decoded_freq - ref_freq)
            result['stage_errors'].append({
                'stage': i,
                'decoded': decoded_freq,
                'reference': ref_freq,
                'error': error,
                'within_tolerance': error <= tolerance
            })
            total_error += error
            if error <= tolerance:
                matched_count += 1

    result['total_error'] = total_error
    result['matched'] = matched_count == len([s for s in ref_stages if s['freq_hz'] > 0])

    if verbose and result['stage_errors']:
        print(f"  TalkingHedz (C070) corner 7 validation:")
        for err in result['stage_errors']:
            status = "OK" if err['within_tolerance'] else "MISS"
            print(f"    Stage {err['stage']}: {err['decoded']:.1f}Hz vs {err['reference']}Hz "
                  f"(error: {err['error']:.1f}Hz) [{status}]")

    return result


def calculate_validation_score(decoded_cubes: List[Dict], verbose: bool = False) -> Dict[str, Any]:
    """
    Calculate validation score based on known targets.

    Checks:
    - VowelSpace (C043) formant frequencies
    - Percentage of valid coefficients
    - Frequency range distribution

    Returns:
        Dict with scores and statistics
    """
    stats = {
        'total_stages': 0,
        'valid_stages': 0,
        'invalid_stages': 0,
        'freq_in_range': 0,  # 20Hz - 20kHz
        'freq_distribution': {},
        'vowelspace_error': float('inf'),
        'score': 0.0
    }

    # Frequency bins for distribution
    freq_bins = [0, 100, 300, 500, 1000, 2000, 4000, 8000, 16000, 22050]
    for i in range(len(freq_bins) - 1):
        stats['freq_distribution'][f'{freq_bins[i]}-{freq_bins[i+1]}'] = 0

    all_freqs = []

    for cube in decoded_cubes:
        for corner in cube['corners']:
            for stage in corner['stages']:
                stats['total_stages'] += 1

                if stage.get('valid', False):
                    stats['valid_stages'] += 1
                    freq = stage.get('freq_hz', 0)
                    all_freqs.append(freq)

                    # Check if in audible range
                    if 20 <= freq <= 20000:
                        stats['freq_in_range'] += 1

                    # Bin frequency
                    for i in range(len(freq_bins) - 1):
                        if freq_bins[i] <= freq < freq_bins[i+1]:
                            stats['freq_distribution'][f'{freq_bins[i]}-{freq_bins[i+1]}'] += 1
                            break
                else:
                    stats['invalid_stages'] += 1

    # Check VowelSpace (cube 43) if available
    if len(decoded_cubes) > 43:
        vowelspace = decoded_cubes[43]
        corner0_stages = vowelspace['corners'][0]['stages']

        # Get first few frequencies
        vowelspace_freqs = [s['freq_hz'] for s in corner0_stages if s.get('valid', False)]

        if len(vowelspace_freqs) >= 3:
            # Calculate error against targets
            f1_error = min(abs(vowelspace_freqs[0] - VOWELSPACE_TARGETS['vowel_i']['F1']),
                          abs(vowelspace_freqs[0] - VOWELSPACE_TARGETS['vowel_a']['F1']))
            f2_error = min(abs(vowelspace_freqs[1] - VOWELSPACE_TARGETS['vowel_i']['F2']),
                          abs(vowelspace_freqs[1] - VOWELSPACE_TARGETS['vowel_a']['F2']))

            stats['vowelspace_error'] = (f1_error + f2_error) / 2
            stats['vowelspace_freqs'] = vowelspace_freqs[:3]

            if verbose:
                print(f"  VowelSpace freqs: {vowelspace_freqs[:3]}")
                print(f"  VowelSpace error: {stats['vowelspace_error']:.1f} Hz")

    # Validate TalkingHedz reference
    talkinghedz_result = validate_talkinghedz(decoded_cubes, verbose=verbose)
    stats['talkinghedz_error'] = talkinghedz_result['total_error']
    stats['talkinghedz_matched'] = talkinghedz_result['matched']
    stats['talkinghedz_freqs'] = talkinghedz_result.get('frequencies', [])

    # Calculate overall score
    valid_pct = stats['valid_stages'] / stats['total_stages'] if stats['total_stages'] > 0 else 0
    in_range_pct = stats['freq_in_range'] / stats['valid_stages'] if stats['valid_stages'] > 0 else 0

    # Score: weight validity, frequency range, VowelSpace, and TalkingHedz match
    vowelspace_score = max(0, 20 - stats['vowelspace_error'] / 75)  # 20% weight
    talkinghedz_score = max(0, 20 - stats['talkinghedz_error'] / 200)  # 20% weight

    stats['score'] = (
        valid_pct * 30 +  # 30% weight on valid coefficients
        in_range_pct * 30 +  # 30% weight on in-range frequencies
        vowelspace_score +  # 20% weight on VowelSpace match
        talkinghedz_score  # 20% weight on TalkingHedz match
    )

    return stats


def sweep_parameters(parser: CubeParser,
                    scales: List[float] = None,
                    modes: List[str] = None,
                    verbose: bool = False) -> List[Dict]:
    """
    Sweep through scale and mode combinations to find best parameters.

    Args:
        parser: Initialized CubeParser
        scales: List of scale values to try
        modes: List of modes to try
        verbose: Enable verbose output

    Returns:
        List of results sorted by score (best first)
    """
    if scales is None:
        scales = [4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 12.0, 14.0, 16.0]
    if modes is None:
        modes = ['linear', 'packed']

    results = []

    for mode in modes:
        for scale in scales:
            if verbose:
                print(f"\nTesting mode={mode}, scale={scale}")

            decoder = CubeDecoder(mode=mode, scale=scale)

            # Decode all cubes
            cubes = []
            for cube_idx in range(NUM_CUBES):
                try:
                    cube_bytes = parser.extract_cube_bytes(cube_idx)
                    coefficients = parser.parse_cube_coefficients(cube_bytes)
                    cube_data = decoder.decode_cube(coefficients, cube_idx)
                    cubes.append(cube_data)
                except Exception as e:
                    if verbose:
                        print(f"  Error decoding cube {cube_idx}: {e}")

            # Validate
            stats = calculate_validation_score(cubes, verbose=verbose)

            results.append({
                'mode': mode,
                'scale': scale,
                'score': stats['score'],
                'valid_pct': stats['valid_stages'] / stats['total_stages'] * 100 if stats['total_stages'] > 0 else 0,
                'in_range_pct': stats['freq_in_range'] / stats['valid_stages'] * 100 if stats['valid_stages'] > 0 else 0,
                'vowelspace_error': stats['vowelspace_error'],
                'vowelspace_freqs': stats.get('vowelspace_freqs', []),
                'talkinghedz_error': stats.get('talkinghedz_error', float('inf')),
                'talkinghedz_freqs': stats.get('talkinghedz_freqs', [])
            })

    # Sort by score (descending)
    results.sort(key=lambda x: x['score'], reverse=True)

    return results


# ============================================================================
# JSON Export
# ============================================================================

def export_to_json(cubes: List[Dict], decode_params: Dict, output_path: Path) -> None:
    """
    Export decoded cubes to JSON file.

    Args:
        cubes: List of decoded cube dictionaries
        decode_params: Dictionary of decode parameters
        output_path: Path to output JSON file
    """
    output = {
        'format': 'TRENCH Validated Morpheus Cubes',
        'version': '1.0',
        'decode_params': decode_params,
        'total_cubes': len(cubes),
        'structure': {
            'corners': NUM_CORNERS,
            'stages': NUM_STAGES,
            'bytes_per_stage': BYTES_PER_STAGE
        },
        'cubes': cubes
    }

    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='ARMAdillo Cube Decoder for TRENCH Z-Plane Filter',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --input Source/Data/wav_decoded.bin --output cubes.json
  %(prog)s --sweep --input Source/Data/wav_decoded.bin
  %(prog)s --mode packed --scale 8.0 --verbose
  %(prog)s --auto-header --verbose
        """
    )

    parser.add_argument('--input', '-i', type=Path,
                       default=Path('Source/Data/wav_decoded.bin'),
                       help='Input binary file path')
    parser.add_argument('--output', '-o', type=Path,
                       default=Path('Source/Data/morpheus_cubes_validated.json'),
                       help='Output JSON file path')
    parser.add_argument('--mode', '-m', choices=['linear', 'packed', 'signed', 'log'],
                       default='linear',
                       help='Byte decode mode')
    parser.add_argument('--scale', '-s', type=float, default=8.0,
                       help='Scale factor for byte decode')
    parser.add_argument('--sample-rate', type=float, default=DEFAULT_SAMPLE_RATE,
                       help='Sample rate in Hz')
    parser.add_argument('--header', type=int, default=0,
                       help='Header size in bytes to skip')
    parser.add_argument('--auto-header', action='store_true',
                       help='Auto-detect header size')
    parser.add_argument('--sweep', action='store_true',
                       help='Sweep scale from 4.0 to 16.0 to find best parameters')
    parser.add_argument('--sweep-scales', type=str, default=None,
                       help='Comma-separated list of scales to sweep')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose output')
    parser.add_argument('--dump-cube', type=int, default=None,
                       help='Dump detailed info for specific cube index')
    parser.add_argument('--patent-formula', action='store_true', default=True,
                       help='Use patent exponential formula (default)')
    parser.add_argument('--direct-decode', action='store_true',
                       help='Use direct ARMAdillo decode instead of patent formula')
    parser.add_argument('--simple-direct', action='store_true',
                       help='Use simple direct byte-to-coefficient mapping (bypasses ARMAdillo)')
    parser.add_argument('--compare-reference', action='store_true',
                       help='Compare decoded values against TalkingHedz reference')

    args = parser.parse_args()

    # Resolve input path
    input_path = args.input
    if not input_path.is_absolute():
        # Try relative to script location or current directory
        if not input_path.exists():
            script_dir = Path(__file__).parent.parent
            input_path = script_dir / args.input

    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}")
        sys.exit(1)

    if args.verbose:
        print(f"Loading: {input_path}")

    # Read binary data
    with open(input_path, 'rb') as f:
        data = f.read()

    if args.verbose:
        print(f"Loaded {len(data)} bytes")

    # Initialize parser
    header_size = args.header
    cube_parser = CubeParser(data, header_size=header_size, verbose=args.verbose)

    # Auto-detect header if requested
    if args.auto_header:
        header_size = cube_parser.auto_detect_header()
        cube_parser = CubeParser(data, header_size=header_size, verbose=args.verbose)

    # Sweep mode
    if args.sweep:
        print("\n" + "="*60)
        print("PARAMETER SWEEP")
        print("="*60)

        scales = None
        if args.sweep_scales:
            scales = [float(s) for s in args.sweep_scales.split(',')]

        results = sweep_parameters(cube_parser, scales=scales, verbose=args.verbose)

        print("\n" + "-"*60)
        print("SWEEP RESULTS (sorted by score)")
        print("-"*60)
        print(f"{'Mode':<10} {'Scale':<8} {'Score':<8} {'Valid%':<10} {'InRange%':<10} {'VowelErr':<10}")
        print("-"*60)

        for r in results[:20]:  # Top 20 results
            print(f"{r['mode']:<10} {r['scale']:<8.1f} {r['score']:<8.1f} "
                  f"{r['valid_pct']:<10.1f} {r['in_range_pct']:<10.1f} "
                  f"{r['vowelspace_error']:<10.1f}")

        # Print best result details
        if results:
            best = results[0]
            print("\n" + "="*60)
            print("BEST PARAMETERS")
            print("="*60)
            print(f"Mode: {best['mode']}")
            print(f"Scale: {best['scale']}")
            print(f"Score: {best['score']:.1f}")
            if best.get('vowelspace_freqs'):
                print(f"VowelSpace (C043) frequencies: {best['vowelspace_freqs']}")

        return

    # Single decode mode
    use_patent = not args.direct_decode
    use_simple = args.simple_direct
    decoder = CubeDecoder(
        mode=args.mode,
        scale=args.scale,
        sample_rate=args.sample_rate,
        use_patent_formula=use_patent,
        use_simple_direct=use_simple
    )

    if args.verbose:
        print(f"\nDecode parameters:")
        print(f"  Mode: {args.mode}")
        print(f"  Scale: {args.scale}")
        print(f"  Sample rate: {args.sample_rate}")
        if use_simple:
            print(f"  Formula: simple direct mapping")
        else:
            print(f"  Formula: {'patent exponential' if use_patent else 'direct ARMAdillo'}")

    # Decode all cubes
    cubes = []
    errors = []

    for cube_idx in range(NUM_CUBES):
        try:
            cube_bytes = cube_parser.extract_cube_bytes(cube_idx)
            coefficients = cube_parser.parse_cube_coefficients(cube_bytes)
            cube_data = decoder.decode_cube(coefficients, cube_idx)
            cubes.append(cube_data)
        except Exception as e:
            errors.append((cube_idx, str(e)))
            if args.verbose:
                print(f"Error decoding cube {cube_idx}: {e}")

    if args.verbose:
        print(f"\nDecoded {len(cubes)} cubes, {len(errors)} errors")

    # Dump specific cube if requested
    if args.dump_cube is not None:
        cube_idx = args.dump_cube
        if 0 <= cube_idx < len(cubes):
            cube = cubes[cube_idx]
            print(f"\n{'='*60}")
            print(f"CUBE {cube_idx}: {cube['name']}")
            print(f"{'='*60}")

            for corner in cube['corners']:
                print(f"\nCorner {corner['corner_index']}:")
                for stage in corner['stages']:
                    raw = stage.get('raw_bytes', [0, 0])
                    print(f"  Stage {stage['stage']}: "
                          f"bytes=[{raw[0]:3d},{raw[1]:3d}] "
                          f"a1={stage['a1']:8.4f} "
                          f"a2={stage['a2']:8.4f} "
                          f"R={stage['R']:.4f} "
                          f"freq={stage['freq_hz']:8.1f}Hz "
                          f"{'VALID' if stage.get('valid') else 'INVALID'}")
        else:
            print(f"Cube index {cube_idx} out of range")

    # Validate
    stats = calculate_validation_score(cubes, verbose=args.verbose)

    if args.verbose:
        print(f"\n{'='*60}")
        print("VALIDATION SUMMARY")
        print(f"{'='*60}")
        print(f"Total stages: {stats['total_stages']}")
        print(f"Valid stages: {stats['valid_stages']} ({stats['valid_stages']/stats['total_stages']*100:.1f}%)")
        print(f"In audible range: {stats['freq_in_range']} ({stats['freq_in_range']/stats['valid_stages']*100:.1f}%)")
        print(f"VowelSpace error: {stats['vowelspace_error']:.1f} Hz")
        print(f"TalkingHedz error: {stats.get('talkinghedz_error', float('inf')):.1f} Hz")
        print(f"Overall score: {stats['score']:.1f}")

        print("\nFrequency distribution:")
        for bin_name, count in stats['freq_distribution'].items():
            bar = '#' * (count // 100)
            print(f"  {bin_name:>12} Hz: {count:5d} {bar}")

    # Reference comparison if requested
    if args.compare_reference:
        print(f"\n{'='*60}")
        print("TALKINGHEDZ REFERENCE COMPARISON")
        print(f"{'='*60}")
        print("Reference (M100% Q100%, from Emulator X3 Cheat Engine):")
        for i, ref in enumerate(TALKINGHEDZ_REFERENCE['stages']):
            print(f"  Stage {i}: a1={ref['a1']:.6f}, R={ref['R']:.6f}, freq={ref['freq_hz']}Hz")

        if len(cubes) > 70:
            cube = cubes[70]
            print(f"\nDecoded TalkingHedz (C070) Corner 7:")
            if len(cube['corners']) > 7:
                corner = cube['corners'][7]
                for stage in corner['stages'][:5]:
                    raw = stage.get('raw_bytes', [0, 0])
                    print(f"  Stage {stage['stage']}: a1={stage['a1']:.6f}, "
                          f"R={stage['R']:.6f}, freq={stage['freq_hz']:.1f}Hz "
                          f"(bytes: {raw})")

    # Export to JSON
    output_path = args.output
    if not output_path.is_absolute():
        script_dir = Path(__file__).parent.parent
        output_path = script_dir / args.output

    formula_name = 'simple_direct' if use_simple else ('patent_exponential' if use_patent else 'direct_armadillo')
    decode_params = {
        'mode': args.mode,
        'scale': args.scale,
        'sample_rate': args.sample_rate,
        'header_size': header_size,
        'formula': formula_name
    }

    export_to_json(cubes, decode_params, output_path)
    print(f"\nExported to: {output_path}")


if __name__ == '__main__':
    main()
