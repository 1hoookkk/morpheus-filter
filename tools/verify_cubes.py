#!/usr/bin/env python3
"""
verify_cubes.py - Validate decoded Morpheus cube data against known reference values.

Part of the TRENCH Z-Plane Filter validation pipeline.

Usage:
    python verify_cubes.py --input decoded_cubes.json
    python verify_cubes.py --input decoded_cubes.json --cube 43 --verbose
"""

import argparse
import json
import math
import sys
from dataclasses import dataclass
from typing import Any, Optional


# =============================================================================
# Reference Values
# =============================================================================

# C043 VowelSpace formant targets (Hz)
# Source: Phonetic formant data, design doc section 5.1
VOWEL_TARGETS = {
    "vowel_i": {  # /i/ as in "beet"
        "F1": 270,
        "F2": 2290,
        "F3": 3010,
    },
    "vowel_a": {  # /a/ as in "father"
        "F1": 730,
        "F2": 1090,
        "F3": 2440,
    },
}

# Talking Hedz reference (M100% Q100%) from Emulator X3 Cheat Engine capture
# Source: skill.md, design doc section 5.2
TALKING_HEDZ_REFERENCE = {
    0: {"freq_hz": 2417, "a1": -1.993596, "R": 0.998475, "flag": 1},
    1: {"freq_hz": 2724, "a1": -1.912492, "R": 0.998384, "flag": 1},
    2: {"freq_hz": 4974, "a1": -1.861726, "R": 0.998353, "flag": 1},
    3: {"freq_hz": 1701, "a1": -1.510937, "R": 0.979504, "flag": 1},
    4: {"freq_hz": None, "a1": -1.992010, "R": 0.998232, "flag": 0},  # bounding
}

# Validation thresholds
FREQ_MIN_HZ = 20.0
FREQ_MAX_HZ = 20000.0
RADIUS_MIN = 0.0
RADIUS_MAX = 1.0
FREQ_TOLERANCE_HZ = 50.0  # +/- tolerance for frequency matching
FORMANT_TOLERANCE_HZ = 100.0  # Wider tolerance for formant matching


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class ValidationResult:
    """Result of a single validation check."""
    name: str
    passed: bool
    message: str
    details: Optional[dict] = None


@dataclass
class ValidationSummary:
    """Summary of all validation results."""
    total_checks: int = 0
    passed_checks: int = 0
    failed_checks: int = 0
    results: list = None

    def __post_init__(self):
        if self.results is None:
            self.results = []

    def add(self, result: ValidationResult):
        self.results.append(result)
        self.total_checks += 1
        if result.passed:
            self.passed_checks += 1
        else:
            self.failed_checks += 1

    @property
    def all_passed(self) -> bool:
        return self.failed_checks == 0


# =============================================================================
# Validation Functions
# =============================================================================

def is_valid_number(value: Any) -> bool:
    """Check if value is a valid finite number."""
    if value is None:
        return False
    try:
        f = float(value)
        return not (math.isnan(f) or math.isinf(f))
    except (TypeError, ValueError):
        return False


def validate_frequency_range(freq_hz: float) -> tuple[bool, str]:
    """Validate frequency is in audible range."""
    if not is_valid_number(freq_hz):
        return False, f"Invalid frequency value: {freq_hz}"
    if freq_hz < FREQ_MIN_HZ:
        return False, f"Frequency {freq_hz:.1f}Hz below minimum {FREQ_MIN_HZ}Hz"
    if freq_hz > FREQ_MAX_HZ:
        return False, f"Frequency {freq_hz:.1f}Hz above maximum {FREQ_MAX_HZ}Hz"
    return True, f"Frequency {freq_hz:.1f}Hz in valid range"


def validate_radius_range(radius: float) -> tuple[bool, str]:
    """Validate pole radius is in valid range (0 < R < 1)."""
    if not is_valid_number(radius):
        return False, f"Invalid radius value: {radius}"
    if radius <= RADIUS_MIN:
        return False, f"Radius {radius:.6f} not greater than {RADIUS_MIN}"
    if radius >= RADIUS_MAX:
        return False, f"Radius {radius:.6f} not less than {RADIUS_MAX}"
    return True, f"Radius {radius:.6f} in valid range"


def validate_flag_field(flag: Any) -> tuple[bool, str]:
    """Validate flag field is 0 or 1."""
    if flag is None:
        return False, "Flag field is None"
    if flag not in (0, 1):
        return False, f"Flag field {flag} is not 0 or 1"
    return True, f"Flag field {flag} is valid"


def validate_stage(stage: dict, cube_idx: int, corner_idx: int, stage_idx: int) -> list[ValidationResult]:
    """Validate a single stage's data."""
    results = []
    prefix = f"Cube {cube_idx}, Corner {corner_idx}, Stage {stage_idx}"

    # Check frequency
    freq_hz = stage.get("freq_hz")
    valid, msg = validate_frequency_range(freq_hz)
    results.append(ValidationResult(
        name=f"{prefix}: Frequency range",
        passed=valid,
        message=msg,
        details={"freq_hz": freq_hz}
    ))

    # Check radius
    radius = stage.get("R")
    valid, msg = validate_radius_range(radius)
    results.append(ValidationResult(
        name=f"{prefix}: Radius range",
        passed=valid,
        message=msg,
        details={"R": radius}
    ))

    # Check for NaN/Inf in critical fields
    for field in ["a1", "a2", "v1", "v2"]:
        value = stage.get(field)
        if value is not None:
            valid = is_valid_number(value)
            results.append(ValidationResult(
                name=f"{prefix}: {field} valid number",
                passed=valid,
                message=f"{field}={value}" if valid else f"{field}={value} is NaN/Inf/invalid",
                details={field: value}
            ))

    # Check flag field
    flag = stage.get("flag")
    if flag is not None:
        valid, msg = validate_flag_field(flag)
        results.append(ValidationResult(
            name=f"{prefix}: Flag field",
            passed=valid,
            message=msg,
            details={"flag": flag}
        ))

    return results


def validate_all_cubes(cubes: list, verbose: bool = False) -> ValidationSummary:
    """Validate all cubes for basic sanity checks."""
    summary = ValidationSummary()

    for cube in cubes:
        cube_idx = cube.get("index", "?")
        corners = cube.get("corners", [])

        for corner in corners:
            corner_idx = corner.get("corner_index", "?")
            stages = corner.get("stages", [])

            for stage in stages:
                stage_idx = stage.get("stage", "?")
                results = validate_stage(stage, cube_idx, corner_idx, stage_idx)

                for result in results:
                    summary.add(result)
                    if verbose and not result.passed:
                        print(f"  FAIL: {result.name} - {result.message}")

    return summary


def check_frequency_match(actual: float, expected: float, tolerance: float = FREQ_TOLERANCE_HZ) -> tuple[bool, float]:
    """Check if actual frequency matches expected within tolerance."""
    if not is_valid_number(actual) or not is_valid_number(expected):
        return False, float('inf')
    error = abs(actual - expected)
    return error <= tolerance, error


def find_formant_matches(stages: list[dict], formants: dict[str, float], tolerance: float = FORMANT_TOLERANCE_HZ) -> dict:
    """
    Find best matches for formant frequencies in stage data.
    Returns dict with F1, F2, F3 matches and their errors.
    """
    stage_freqs = [(i, s.get("freq_hz", 0)) for i, s in enumerate(stages)]
    stage_freqs = [(i, f) for i, f in stage_freqs if is_valid_number(f) and f > 0]

    matches = {}
    for formant_name, target_freq in formants.items():
        best_match = None
        best_error = float('inf')

        for stage_idx, freq in stage_freqs:
            error = abs(freq - target_freq)
            if error < best_error:
                best_error = error
                best_match = {
                    "stage": stage_idx,
                    "freq_hz": freq,
                    "target_hz": target_freq,
                    "error_hz": error,
                    "within_tolerance": error <= tolerance
                }

        matches[formant_name] = best_match

    return matches


def validate_vowelspace_cube(cube: dict, verbose: bool = False) -> ValidationSummary:
    """
    Validate C043 VowelSpace cube against phonetic formant targets.

    The VowelSpace cube should have formant frequencies that match
    known vowel positions. We check corner 0 and corner 7 for vowel patterns.
    """
    summary = ValidationSummary()
    cube_idx = cube.get("index", "?")
    corners = cube.get("corners", [])

    if verbose:
        print(f"\n--- VowelSpace Validation (Cube {cube_idx}) ---")

    # Check various corners for vowel formant patterns
    for corner in corners:
        corner_idx = corner.get("corner_index", 0)
        stages = corner.get("stages", [])

        if not stages:
            continue

        # Try to match against vowel /i/ and /a/ targets
        for vowel_name, targets in VOWEL_TARGETS.items():
            matches = find_formant_matches(stages, targets, FORMANT_TOLERANCE_HZ)

            # Check if all formants are within tolerance
            all_match = all(
                m and m.get("within_tolerance", False)
                for m in matches.values()
                if m is not None
            )

            if all_match and matches:
                avg_error = sum(m["error_hz"] for m in matches.values() if m) / len(matches)
                summary.add(ValidationResult(
                    name=f"Cube {cube_idx}, Corner {corner_idx}: {vowel_name} formants",
                    passed=True,
                    message=f"All formants match within {FORMANT_TOLERANCE_HZ}Hz (avg error: {avg_error:.1f}Hz)",
                    details={"matches": matches, "avg_error": avg_error}
                ))

                if verbose:
                    print(f"  Corner {corner_idx} matches {vowel_name}:")
                    for fname, m in matches.items():
                        if m:
                            print(f"    {fname}: {m['freq_hz']:.1f}Hz (target: {m['target_hz']}Hz, error: {m['error_hz']:.1f}Hz)")

            elif verbose:
                # Report partial matches or misses
                matched_count = sum(1 for m in matches.values() if m and m.get("within_tolerance", False))
                total = len(matches)
                print(f"  Corner {corner_idx}, {vowel_name}: {matched_count}/{total} formants match")
                for fname, m in matches.items():
                    if m:
                        status = "OK" if m["within_tolerance"] else "MISS"
                        print(f"    {fname}: {m['freq_hz']:.1f}Hz (target: {m['target_hz']}Hz, error: {m['error_hz']:.1f}Hz) [{status}]")

    return summary


def validate_talking_hedz(cube: dict, verbose: bool = False) -> ValidationSummary:
    """
    Validate cube against Talking Hedz reference values.

    Reference from Emulator X3 Cheat Engine capture (M100% Q100%):
    - Stage 0: ~2417 Hz
    - Stage 1: ~2724 Hz
    - Stage 2: ~4974 Hz
    - Stage 3: ~1701 Hz
    """
    summary = ValidationSummary()
    cube_idx = cube.get("index", "?")
    corners = cube.get("corners", [])

    if verbose:
        print(f"\n--- Talking Hedz Validation (Cube {cube_idx}) ---")

    # Check corner 7 (all max - M100% Q100%)
    corner_7 = None
    for corner in corners:
        if corner.get("corner_index") == 7:
            corner_7 = corner
            break

    if not corner_7:
        summary.add(ValidationResult(
            name=f"Cube {cube_idx}: Talking Hedz corner 7",
            passed=False,
            message="Corner 7 not found in cube data"
        ))
        return summary

    stages = corner_7.get("stages", [])

    for ref_stage_idx, ref_values in TALKING_HEDZ_REFERENCE.items():
        if ref_stage_idx >= len(stages):
            summary.add(ValidationResult(
                name=f"Cube {cube_idx}: Talking Hedz stage {ref_stage_idx}",
                passed=False,
                message=f"Stage {ref_stage_idx} not found (only {len(stages)} stages)"
            ))
            continue

        stage = stages[ref_stage_idx]
        actual_freq = stage.get("freq_hz")
        expected_freq = ref_values.get("freq_hz")

        # Check frequency (if expected is not None - stage 4 is bounding)
        if expected_freq is not None:
            matches, error = check_frequency_match(actual_freq, expected_freq, FREQ_TOLERANCE_HZ)
            summary.add(ValidationResult(
                name=f"Cube {cube_idx}: Talking Hedz stage {ref_stage_idx} frequency",
                passed=matches,
                message=f"Expected ~{expected_freq}Hz, got {actual_freq:.1f}Hz (error: {error:.1f}Hz)",
                details={"expected": expected_freq, "actual": actual_freq, "error": error}
            ))

            if verbose:
                status = "PASS" if matches else "FAIL"
                print(f"  Stage {ref_stage_idx}: {actual_freq:.1f}Hz (expected ~{expected_freq}Hz, error: {error:.1f}Hz) [{status}]")

        # Check flag field
        expected_flag = ref_values.get("flag")
        actual_flag = stage.get("flag")
        if expected_flag is not None and actual_flag is not None:
            flag_match = actual_flag == expected_flag
            summary.add(ValidationResult(
                name=f"Cube {cube_idx}: Talking Hedz stage {ref_stage_idx} flag",
                passed=flag_match,
                message=f"Expected flag={expected_flag}, got flag={actual_flag}",
                details={"expected": expected_flag, "actual": actual_flag}
            ))

    return summary


def compute_statistics(cubes: list) -> dict:
    """Compute summary statistics across all cubes."""
    all_freqs = []
    all_radii = []
    all_a1 = []
    all_a2 = []
    flag_counts = {0: 0, 1: 0, "other": 0}

    for cube in cubes:
        for corner in cube.get("corners", []):
            for stage in corner.get("stages", []):
                freq = stage.get("freq_hz")
                if is_valid_number(freq):
                    all_freqs.append(freq)

                r = stage.get("R")
                if is_valid_number(r):
                    all_radii.append(r)

                a1 = stage.get("a1")
                if is_valid_number(a1):
                    all_a1.append(a1)

                a2 = stage.get("a2")
                if is_valid_number(a2):
                    all_a2.append(a2)

                flag = stage.get("flag")
                if flag == 0:
                    flag_counts[0] += 1
                elif flag == 1:
                    flag_counts[1] += 1
                elif flag is not None:
                    flag_counts["other"] += 1

    stats = {
        "total_cubes": len(cubes),
        "total_stages": len(all_freqs),
    }

    if all_freqs:
        stats["frequency"] = {
            "min": min(all_freqs),
            "max": max(all_freqs),
            "mean": sum(all_freqs) / len(all_freqs),
            "count": len(all_freqs),
        }

    if all_radii:
        stats["radius"] = {
            "min": min(all_radii),
            "max": max(all_radii),
            "mean": sum(all_radii) / len(all_radii),
            "count": len(all_radii),
        }

    if all_a1:
        stats["a1"] = {
            "min": min(all_a1),
            "max": max(all_a1),
            "mean": sum(all_a1) / len(all_a1),
        }

    if all_a2:
        stats["a2"] = {
            "min": min(all_a2),
            "max": max(all_a2),
            "mean": sum(all_a2) / len(all_a2),
        }

    stats["flag_distribution"] = flag_counts

    return stats


# =============================================================================
# Main Entry Point
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Validate decoded Morpheus cube data against known reference values.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --input decoded_cubes.json
  %(prog)s --input decoded_cubes.json --cube 43 --verbose
  %(prog)s --input decoded_cubes.json --verbose

Reference Targets:
  C043 VowelSpace:
    Vowel /i/: F1 ~270Hz, F2 ~2290Hz, F3 ~3010Hz
    Vowel /a/: F1 ~730Hz, F2 ~1090Hz, F3 ~2440Hz

  Talking Hedz (M100%% Q100%%):
    Stage 0: ~2417 Hz
    Stage 1: ~2724 Hz
    Stage 2: ~4974 Hz
    Stage 3: ~1701 Hz
        """
    )

    parser.add_argument(
        "--input", "-i",
        required=True,
        help="Path to JSON file (output from decode_cubes.py)"
    )

    parser.add_argument(
        "--cube", "-c",
        type=int,
        default=None,
        help="Specific cube index to check (default: check known reference cubes)"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output with detailed validation results"
    )

    parser.add_argument(
        "--stats-only",
        action="store_true",
        help="Only print summary statistics, skip detailed validation"
    )

    args = parser.parse_args()

    # Load JSON data
    try:
        with open(args.input, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"ERROR: File not found: {args.input}")
        return 1
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in {args.input}: {e}")
        return 1

    cubes = data.get("cubes", [])
    if not cubes:
        print("ERROR: No cubes found in input file")
        return 1

    print(f"Loaded {len(cubes)} cubes from {args.input}")

    # Show decode parameters if available
    decode_params = data.get("decode_params", {})
    if decode_params and args.verbose:
        print(f"Decode parameters: mode={decode_params.get('mode', '?')}, "
              f"scale={decode_params.get('scale', '?')}, "
              f"sample_rate={decode_params.get('sample_rate', '?')}")

    # Compute and display statistics
    print("\n" + "=" * 60)
    print("SUMMARY STATISTICS")
    print("=" * 60)

    stats = compute_statistics(cubes)
    print(f"Total cubes: {stats['total_cubes']}")
    print(f"Total stages analyzed: {stats['total_stages']}")

    if "frequency" in stats:
        freq = stats["frequency"]
        print(f"\nFrequency (Hz):")
        print(f"  Min:  {freq['min']:.1f}")
        print(f"  Max:  {freq['max']:.1f}")
        print(f"  Mean: {freq['mean']:.1f}")

    if "radius" in stats:
        r = stats["radius"]
        print(f"\nPole Radius (R):")
        print(f"  Min:  {r['min']:.6f}")
        print(f"  Max:  {r['max']:.6f}")
        print(f"  Mean: {r['mean']:.6f}")

    if "a1" in stats:
        a1 = stats["a1"]
        print(f"\nCoefficient a1:")
        print(f"  Min:  {a1['min']:.6f}")
        print(f"  Max:  {a1['max']:.6f}")
        print(f"  Mean: {a1['mean']:.6f}")

    if "a2" in stats:
        a2 = stats["a2"]
        print(f"\nCoefficient a2:")
        print(f"  Min:  {a2['min']:.6f}")
        print(f"  Max:  {a2['max']:.6f}")
        print(f"  Mean: {a2['mean']:.6f}")

    if "flag_distribution" in stats:
        flags = stats["flag_distribution"]
        print(f"\nFlag Distribution:")
        print(f"  flag=0 (lowpass): {flags.get(0, 0)}")
        print(f"  flag=1 (parametric): {flags.get(1, 0)}")
        if flags.get("other", 0) > 0:
            print(f"  other values: {flags['other']}")

    if args.stats_only:
        print("\n(Stats-only mode, skipping detailed validation)")
        return 0

    # Run validations
    overall_summary = ValidationSummary()

    # Basic validation of all cubes
    print("\n" + "=" * 60)
    print("BASIC VALIDATION (All Cubes)")
    print("=" * 60)

    basic_summary = validate_all_cubes(cubes, verbose=args.verbose)
    for result in basic_summary.results:
        overall_summary.add(result)

    print(f"Checks: {basic_summary.total_checks}, "
          f"Passed: {basic_summary.passed_checks}, "
          f"Failed: {basic_summary.failed_checks}")

    # Specific cube validation
    if args.cube is not None:
        # Find the specified cube
        target_cube = None
        for cube in cubes:
            if cube.get("index") == args.cube:
                target_cube = cube
                break

        if target_cube is None:
            print(f"\nWARNING: Cube {args.cube} not found in data")
        else:
            print(f"\n" + "=" * 60)
            print(f"SPECIFIC CUBE VALIDATION (Cube {args.cube})")
            print("=" * 60)

            # Check if it might be VowelSpace (index 43)
            if args.cube == 43:
                vs_summary = validate_vowelspace_cube(target_cube, verbose=args.verbose)
                for result in vs_summary.results:
                    overall_summary.add(result)
                print(f"VowelSpace checks: {vs_summary.total_checks}, "
                      f"Passed: {vs_summary.passed_checks}, "
                      f"Failed: {vs_summary.failed_checks}")

            # Try Talking Hedz validation as well
            th_summary = validate_talking_hedz(target_cube, verbose=args.verbose)
            for result in th_summary.results:
                overall_summary.add(result)
            print(f"Talking Hedz checks: {th_summary.total_checks}, "
                  f"Passed: {th_summary.passed_checks}, "
                  f"Failed: {th_summary.failed_checks}")

    else:
        # Try to find and validate known reference cubes
        print("\n" + "=" * 60)
        print("REFERENCE CUBE VALIDATION")
        print("=" * 60)

        # Look for C043 VowelSpace
        cube_43 = None
        for cube in cubes:
            if cube.get("index") == 43:
                cube_43 = cube
                break

        if cube_43:
            print("\nC043 VowelSpace:")
            vs_summary = validate_vowelspace_cube(cube_43, verbose=args.verbose)
            for result in vs_summary.results:
                overall_summary.add(result)
            print(f"  Checks: {vs_summary.total_checks}, "
                  f"Passed: {vs_summary.passed_checks}, "
                  f"Failed: {vs_summary.failed_checks}")
        else:
            print("\nC043 VowelSpace: Not found in data (cube index 43)")

        # Search for potential Talking Hedz cube
        # We don't know the exact index, so we search for frequency patterns
        print("\nSearching for Talking Hedz reference pattern...")

        best_match_cube = None
        best_match_score = 0

        for cube in cubes:
            for corner in cube.get("corners", []):
                if corner.get("corner_index") != 7:
                    continue

                stages = corner.get("stages", [])
                if len(stages) < 4:
                    continue

                # Check how many reference frequencies match
                match_count = 0
                for ref_idx, ref_vals in TALKING_HEDZ_REFERENCE.items():
                    if ref_idx >= len(stages):
                        continue
                    if ref_vals.get("freq_hz") is None:
                        continue

                    actual = stages[ref_idx].get("freq_hz", 0)
                    expected = ref_vals["freq_hz"]
                    if is_valid_number(actual) and abs(actual - expected) <= FREQ_TOLERANCE_HZ:
                        match_count += 1

                if match_count > best_match_score:
                    best_match_score = match_count
                    best_match_cube = cube

        if best_match_cube and best_match_score > 0:
            print(f"  Best match: Cube {best_match_cube.get('index', '?')} "
                  f"({best_match_score}/4 stage frequencies match)")
            th_summary = validate_talking_hedz(best_match_cube, verbose=args.verbose)
            for result in th_summary.results:
                overall_summary.add(result)
            print(f"  Checks: {th_summary.total_checks}, "
                  f"Passed: {th_summary.passed_checks}, "
                  f"Failed: {th_summary.failed_checks}")
        else:
            print("  No cube found matching Talking Hedz frequency pattern")

    # Final summary
    print("\n" + "=" * 60)
    print("FINAL RESULTS")
    print("=" * 60)
    print(f"Total checks:  {overall_summary.total_checks}")
    print(f"Passed:        {overall_summary.passed_checks}")
    print(f"Failed:        {overall_summary.failed_checks}")

    if overall_summary.all_passed:
        print("\n*** ALL CHECKS PASSED ***")
        return 0
    else:
        print(f"\n*** {overall_summary.failed_checks} CHECK(S) FAILED ***")

        if args.verbose:
            print("\nFailed checks:")
            for result in overall_summary.results:
                if not result.passed:
                    print(f"  - {result.name}: {result.message}")

        return 1


if __name__ == "__main__":
    sys.exit(main())
