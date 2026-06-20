#!/usr/bin/env python3
"""
Test suite for log_aggregator.py JSONL output functionality.

Tests the JSONL export feature including:
- Correct JSONL schema output
- Timestamp ordering across multiple input files
- Warning records for unparseable lines
- Support for JSON and text log formats
"""

import json
import os
import sys
import tempfile
from pathlib import Path

# Add tools directory to path
sys.path.insert(0, str(Path(__file__).parent))

from log_aggregator import LogAggregator


def test_jsonl_schema():
    """Test that JSONL output has correct schema with required fields."""
    print("Test 1: JSONL Schema Validation")

    aggregator = LogAggregator()

    # Create sample log content with JSON format
    with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
        log_file = f.name
        f.write('{"timestamp": 1704067200, "level": "INFO", "service": "api", "message": "Server started"}\n')
        f.write('{"timestamp": 1704067260, "level": "ERROR", "service": "db", "message": "Connection failed"}\n')

    try:
        aggregator.process_file(log_file)

        # Export to JSONL
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as out:
            output_file = out.name

        aggregator.export_jsonl(output_file)

        # Validate JSONL output
        with open(output_file, 'r') as f:
            lines = f.readlines()
            assert len(lines) == 2, f"Expected 2 lines, got {len(lines)}"

            for line in lines:
                record = json.loads(line)
                # Check required fields
                assert 'timestamp' in record, "Missing timestamp field"
                assert 'level' in record, "Missing level field"
                assert 'source' in record, "Missing source field"
                assert 'message' in record, "Missing message field"
                assert 'metadata' in record, "Missing metadata field"

                # Validate timestamp is ISO format string
                if record['timestamp']:
                    assert 'T' in record['timestamp'], "Timestamp not in ISO format"

        print("  [PASS] JSONL schema validation passed")
        return True
    finally:
        os.unlink(log_file)
        if 'output_file' in locals():
            os.unlink(output_file)


def test_timestamp_ordering():
    """Test that entries are ordered by timestamp across multiple files."""
    print("\nTest 2: Timestamp Ordering Across Files")

    aggregator = LogAggregator()

    # Create two log files with interleaved timestamps
    with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f1:
        log_file1 = f1.name
        f1.write('2024-01-01 10:00:00 INFO [service1] First message\n')
        f1.write('2024-01-01 10:02:00 INFO [service1] Third message\n')

    with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f2:
        log_file2 = f2.name
        f2.write('2024-01-01 10:01:00 INFO [service2] Second message\n')
        f2.write('2024-01-01 10:03:00 INFO [service2] Fourth message\n')

    try:
        # Process both files
        aggregator.process_file(log_file1)
        aggregator.process_file(log_file2)

        # Export to JSONL
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as out:
            output_file = out.name

        aggregator.export_jsonl(output_file)

        # Validate ordering
        with open(output_file, 'r') as f:
            lines = f.readlines()
            records = [json.loads(line) for line in lines]

            # Check that records are ordered by timestamp
            assert 'First message' in records[0]['message'], f"Expected 'First message' in first record"
            assert 'Second message' in records[1]['message'], f"Expected 'Second message' in second record"
            assert 'Third message' in records[2]['message'], f"Expected 'Third message' in third record"
            assert 'Fourth message' in records[3]['message'], f"Expected 'Fourth message' in fourth record"

        print("  [PASS] Timestamp ordering validation passed")
        return True
    finally:
        os.unlink(log_file1)
        os.unlink(log_file2)
        if 'output_file' in locals():
            os.unlink(output_file)


def test_unparseable_lines():
    """Test that unparseable lines generate warning records."""
    print("\nTest 3: Warning Records for Unparseable Lines")

    aggregator = LogAggregator()

    # Create log with some unparseable lines
    with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
        log_file = f.name
        f.write('2024-01-01 10:00:00 INFO [service] Valid log line\n')
        f.write('This is not a valid log line at all\n')
        f.write('Another unparseable line\n')
        f.write('{"timestamp": 1704067260, "level": "INFO", "message": "Another valid line"}\n')

    try:
        aggregator.process_file(log_file)

        # Export to JSONL
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as out:
            output_file = out.name

        aggregator.export_jsonl(output_file)

        # Validate warning records
        with open(output_file, 'r') as f:
            lines = f.readlines()
            records = [json.loads(line) for line in lines]

            # Check for parse_error records
            parse_errors = [r for r in records if r['level'] == 'parse_error']
            assert len(parse_errors) == 2, f"Expected 2 parse errors, got {len(parse_errors)}"

            # Verify parse errors have raw_line in metadata
            for error in parse_errors:
                assert 'raw_line' in error['metadata'], "Parse error missing raw_line in metadata"
                assert error['message'] == 'Failed to parse log line'

        print("  [PASS] Warning records validation passed")
        return True
    finally:
        os.unlink(log_file)
        if 'output_file' in locals():
            os.unlink(output_file)


def test_multiple_formats():
    """Test parsing of JSON and text log formats."""
    print("\nTest 4: Multiple Log Format Support")

    aggregator = LogAggregator()

    # Create log with mixed formats
    with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
        log_file = f.name
        f.write('{"timestamp": 1704067200, "level": "INFO", "service": "api", "message": "JSON format"}\n')
        f.write('2024-01-01 10:01:00 WARN [service] Text format\n')
        f.write('192.168.1.1 - - [01/Jan/2024:10:02:00 +0000] "GET /api HTTP/1.1" 200 1234 "-" "Mozilla"\n')

    try:
        aggregator.process_file(log_file)

        # Export to JSONL
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as out:
            output_file = out.name

        aggregator.export_jsonl(output_file)

        # Validate different format parsing
        with open(output_file, 'r') as f:
            lines = f.readlines()
            records = [json.loads(line) for line in lines]

            assert len(records) == 3, f"Expected 3 records, got {len(records)}"

            # Check formats are preserved in metadata
            formats = [r['metadata'].get('format') for r in records]
            assert 'json' in formats, "JSON format not detected"
            assert 'text' in formats, "Text format not detected"
            assert 'nginx' in formats, "Nginx format not detected"

        print("  [PASS] Multiple format support validation passed")
        return True
    finally:
        os.unlink(log_file)
        if 'output_file' in locals():
            os.unlink(output_file)


def test_null_timestamp_ordering():
    """Test that entries without timestamps are ordered by source and line number."""
    print("\nTest 5: Null Timestamp Ordering")

    aggregator = LogAggregator()

    # Create log with lines that won't have timestamps
    with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
        log_file = f.name
        f.write('2024-01-01 10:00:00 INFO [service] Has timestamp\n')
        f.write('No timestamp line 1\n')
        f.write('No timestamp line 2\n')

    try:
        aggregator.process_file(log_file)

        # Export to JSONL
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as out:
            output_file = out.name

        aggregator.export_jsonl(output_file)

        # Validate ordering: timestamped entry first, then null timestamps in order
        with open(output_file, 'r') as f:
            lines = f.readlines()
            records = [json.loads(line) for line in lines]

            # First record should have timestamp
            assert records[0]['timestamp'] is not None, "First record should have timestamp"

            # Next records should have null timestamps but be ordered by line number
            assert records[1]['timestamp'] is None, "Second record should have null timestamp"
            assert records[2]['timestamp'] is None, "Third record should have null timestamp"
            assert records[1]['metadata']['source_line'] < records[2]['metadata']['source_line']

        print("  [PASS] Null timestamp ordering validation passed")
        return True
    finally:
        os.unlink(log_file)
        if 'output_file' in locals():
            os.unlink(output_file)


def main():
    print("Running log_aggregator JSONL tests...\n")
    print("=" * 60)

    tests = [
        test_jsonl_schema,
        test_timestamp_ordering,
        test_unparseable_lines,
        test_multiple_formats,
        test_null_timestamp_ordering,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
        except AssertionError as e:
            print(f"  [FAIL] FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"  [FAIL] ERROR: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
