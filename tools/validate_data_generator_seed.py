#!/usr/bin/env python3
"""
Validation script for deterministic data generator seed support.
Tests that the data generator produces byte-for-byte identical output
when run with the same seed and arguments.
"""

import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path


def compute_file_hash(filepath: str) -> str:
    """Compute SHA256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            sha256.update(chunk)
    return sha256.hexdigest()


def compute_directory_hash(directory: str) -> dict:
    """Compute hashes of all files in a directory."""
    hashes = {}
    for root, dirs, files in os.walk(directory):
        for file in sorted(files):
            filepath = os.path.join(root, file)
            rel_path = os.path.relpath(filepath, directory)
            hashes[rel_path] = compute_file_hash(filepath)
    return hashes


def run_generator(seed: int, output_dir: str) -> int:
    """Run the data generator with the given seed."""
    cmd = [
        sys.executable,
        "tools/data_generator.py",
        "--seed", str(seed),
        "--output-dir", output_dir,
        "--users", "10",
        "--orders", "20",
        "--trades", "30",
        "--ticks", "50",
        "--candles", "25",
        "--format", "both",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    return result.returncode


def validate_seed(seed: int) -> bool:
    """Validate that the same seed produces identical output twice."""
    print(f"\n{'='*70}")
    print(f"Testing seed: {seed}")
    print(f"{'='*70}")

    output_dir1 = f"./test_output_seed_{seed}_run1"
    output_dir2 = f"./test_output_seed_{seed}_run2"

    # Clean up any existing directories
    for dir_path in [output_dir1, output_dir2]:
        if os.path.exists(dir_path):
            shutil.rmtree(dir_path)

    # Run generator twice with the same seed
    print(f"\nRun 1 with seed {seed}:")
    ret1 = run_generator(seed, output_dir1)
    if ret1 != 0:
        print(f"ERROR: Generator failed on run 1 (exit code {ret1})")
        return False

    print(f"\nRun 2 with seed {seed}:")
    ret2 = run_generator(seed, output_dir2)
    if ret2 != 0:
        print(f"ERROR: Generator failed on run 2 (exit code {ret2})")
        return False

    # Compare outputs
    print(f"\nComparing outputs...")
    hashes1 = compute_directory_hash(output_dir1)
    hashes2 = compute_directory_hash(output_dir2)

    all_files = set(hashes1.keys()) | set(hashes2.keys())
    mismatches = []

    for filename in sorted(all_files):
        if filename not in hashes1:
            print(f"  [FAIL] {filename}: Missing in run 1")
            mismatches.append(filename)
        elif filename not in hashes2:
            print(f"  [FAIL] {filename}: Missing in run 2")
            mismatches.append(filename)
        elif hashes1[filename] != hashes2[filename]:
            print(f"  [FAIL] {filename}: Hash mismatch")
            print(f"     Run 1: {hashes1[filename]}")
            print(f"     Run 2: {hashes2[filename]}")
            mismatches.append(filename)
        else:
            print(f"  [PASS] {filename}: Identical (SHA256: {hashes1[filename][:16]}...)")

    # Clean up
    shutil.rmtree(output_dir1)
    shutil.rmtree(output_dir2)

    if mismatches:
        print(f"\n[FAIL] Seed {seed} produced different outputs")
        print(f"   {len(mismatches)} file(s) did not match")
        return False
    else:
        print(f"\n[PASS] Seed {seed} produced byte-for-byte identical outputs")
        return True


def main():
    print("Deterministic Data Generator Seed Validation")
    print("=" * 70)

    # Test seeds as required by bounty
    test_seeds = [1, 42, 8675309]

    results = {}
    for seed in test_seeds:
        results[seed] = validate_seed(seed)

    # Summary
    print("\n" + "=" * 70)
    print("VALIDATION SUMMARY")
    print("=" * 70)

    all_passed = True
    for seed, passed in results.items():
        status = "[PASS]" if passed else "[FAIL]"
        print(f"  Seed {seed:>7}: {status}")
        if not passed:
            all_passed = False

    print("=" * 70)

    if all_passed:
        print("\n[PASS] All validation tests passed!")
        print("  The data generator produces deterministic, reproducible output.")
        return 0
    else:
        print("\n[FAIL] Some validation tests failed!")
        print("  The data generator does not produce deterministic output.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
