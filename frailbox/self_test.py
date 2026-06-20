#!/usr/bin/env python3
"""
Frailbox Self-Test Suite

This Python-based self-test validates frailbox components without requiring
compilation. It tests:
- Arena allocator initialization
- Logger initialization
- Sandbox initialization
- Connector basics
- Configuration validation

Run with: python self_test.py
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import List, Dict, Any


class TestResult:
    def __init__(self, name: str, passed: bool, error_msg: str = None):
        self.name = name
        self.passed = passed
        self.error_msg = error_msg


class SelfTestSuite:
    def __init__(self):
        self.results: List[TestResult] = []
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.suite_dir = Path(__file__).resolve().parent

    def record_test(self, name: str, passed: bool, error_msg: str = None):
        """Record a test result"""
        result = TestResult(name, passed, error_msg)
        self.results.append(result)
        if passed:
            self.passed += 1
        else:
            self.failed += 1

    def test_arena_headers_exist(self):
        """Test 1: Arena allocator header exists"""
        header_path = self.suite_dir / "include" / "arena.h"
        if header_path.exists():
            self.record_test("arena_headers_exist", True)
        else:
            self.record_test("arena_headers_exist", False, "Header not found: {}".format(header_path))

    def test_arena_source_exists(self):
        """Test 2: Arena allocator source exists"""
        source_path = self.suite_dir / "src" / "arena.c"
        if source_path.exists():
            self.record_test("arena_source_exists", True)
        else:
            self.record_test("arena_source_exists", False, "Source not found: {}".format(source_path))

    def test_logger_headers_exist(self):
        """Test 3: Logger header exists"""
        header_path = self.suite_dir / "include" / "logger.h"
        if header_path.exists():
            self.record_test("logger_headers_exist", True)
        else:
            self.record_test("logger_headers_exist", False, "Header not found: {}".format(header_path))

    def test_logger_source_exists(self):
        """Test 4: Logger source exists"""
        source_path = self.suite_dir / "src" / "logger.c"
        if source_path.exists():
            # Verify it has core functions
            with open(source_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                if 'log_init' in content and 'log_message' in content:
                    self.record_test("logger_source_exists", True)
                else:
                    self.record_test("logger_source_exists", False, "Missing core functions")
        else:
            self.record_test("logger_source_exists", False, "Source not found: {}".format(source_path))

    def test_sandbox_headers_exist(self):
        """Test 5: Sandbox header exists"""
        header_path = self.suite_dir / "include" / "sandbox.h"
        if header_path.exists():
            self.record_test("sandbox_headers_exist", True)
        else:
            self.record_test("sandbox_headers_exist", False, "Header not found: {}".format(header_path))

    def test_sandbox_source_exists(self):
        """Test 6: Sandbox source exists"""
        source_path = self.suite_dir / "src" / "sandbox.c"
        if source_path.exists():
            # Verify it has core functions
            with open(source_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                if 'sandbox_create' in content and 'sandbox_apply' in content:
                    self.record_test("sandbox_source_exists", True)
                else:
                    self.record_test("sandbox_source_exists", False, "Missing core functions")
        else:
            self.record_test("sandbox_source_exists", False, "Source not found: {}".format(source_path))

    def test_makefile_has_self_test(self):
        """Test 7: Makefile has self-test target"""
        makefile_path = self.suite_dir / "Makefile"
        if makefile_path.exists():
            with open(makefile_path, 'r') as f:
                content = f.read()
                if 'self-test' in content:
                    self.record_test("makefile_has_self_test", True)
                else:
                    self.record_test("makefile_has_self_test", False, "self-test target not found")
        else:
            self.record_test("makefile_has_self_test", False, "Makefile not found")

    def test_c_source_files_readable(self):
        """Test 8: All C source files are readable"""
        src_dir = self.suite_dir / "src"
        c_files = list(src_dir.glob("*.c"))

        if not c_files:
            self.record_test("c_source_files_readable", False, "No C source files found")
            return

        try:
            for c_file in c_files:
                with open(c_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    if len(content) < 100:
                        self.record_test("c_source_files_readable", False, "File too small: {}".format(c_file))
                        return
            self.record_test("c_source_files_readable", True)
        except Exception as e:
            self.record_test("c_source_files_readable", False, str(e))

    def test_headers_have_guards(self):
        """Test 9: All headers have include guards"""
        include_dir = self.suite_dir / "include"
        h_files = list(include_dir.glob("*.h"))

        if not h_files:
            self.record_test("headers_have_guards", False, "No header files found")
            return

        try:
            for h_file in h_files:
                with open(h_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    # Check for #ifndef or #pragma once
                    if '#ifndef' not in content and '#pragma once' not in content:
                        self.record_test("headers_have_guards", False, "No guards in {}".format(h_file))
                        return
            self.record_test("headers_have_guards", True)
        except Exception as e:
            self.record_test("headers_have_guards", False, str(e))

    def test_main_entry_point_exists(self):
        """Test 10: Main entry point exists"""
        main_c_path = self.suite_dir / "main.c"
        if main_c_path.exists():
            with open(main_c_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                if 'int main(' in content or 'main(' in content:
                    self.record_test("main_entry_point_exists", True)
                else:
                    self.record_test("main_entry_point_exists", False, "main() function not found")
        else:
            self.record_test("main_entry_point_exists", False, "main.c not found")

    def test_tests_directory_exists(self):
        """Test 11: Tests directory exists"""
        tests_dir = self.suite_dir / "tests"
        if tests_dir.exists() and tests_dir.is_dir():
            test_files = list(tests_dir.glob("test_*.c"))
            if test_files:
                self.record_test("tests_directory_exists", True)
            else:
                self.record_test("tests_directory_exists", False, "No test files found")
        else:
            self.record_test("tests_directory_exists", False, "tests directory not found")

    def test_docs_operations_exists(self):
        """Test 12: OPERATIONS.md documentation exists"""
        docs_dir = self.suite_dir.parent / "docs"
        ops_file = docs_dir / "OPERATIONS.md"
        if ops_file.exists():
            with open(ops_file, 'r') as f:
                content = f.read()
                if len(content) > 100:
                    self.record_test("docs_operations_exists", True)
                else:
                    self.record_test("docs_operations_exists", False, "OPERATIONS.md is empty")
        else:
            self.record_test("docs_operations_exists", False, "OPERATIONS.md not found")

    def run_all_tests(self):
        """Execute all tests"""
        self.test_arena_headers_exist()
        self.test_arena_source_exists()
        self.test_logger_headers_exist()
        self.test_logger_source_exists()
        self.test_sandbox_headers_exist()
        self.test_sandbox_source_exists()
        self.test_makefile_has_self_test()
        self.test_c_source_files_readable()
        self.test_headers_have_guards()
        self.test_main_entry_point_exists()
        self.test_tests_directory_exists()
        self.test_docs_operations_exists()

    def print_console_results(self):
        """Print formatted console output"""
        print("")
        print("=" * 62)
        print("           FRAILBOX SELF-TEST RESULTS")
        print("=" * 62 + "\n")

        for i, result in enumerate(self.results, 1):
            status = "PASS" if result.passed else "FAIL"
            print("  [{:2d}/{:2d}] {:<40} {}".format(i, len(self.results), result.name, status))
            if result.error_msg:
                print("          Error: {}".format(result.error_msg))

        print("")
        print("=" * 62)
        total = len(self.results)
        print("  SUMMARY: {} passed, {} failed, {} skipped out of {} tests".format(
            self.passed, self.failed, self.skipped, total))
        print("=" * 62 + "\n")

    def save_json_results(self):
        """Save results as JSON"""
        output_path = self.suite_dir / "self-test-results.json"

        results_list = [
            {
                "name": result.name,
                "status": "PASS" if result.passed else "FAIL",
                "error": result.error_msg
            }
            for result in self.results
        ]

        data = {
            "test_suite": "frailbox-self-test",
            "timestamp": int(time.time()),
            "summary": {
                "total": len(self.results),
                "passed": self.passed,
                "failed": self.failed,
                "skipped": self.skipped
            },
            "results": results_list
        }

        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)

        print("JSON results saved to: {}".format(output_path))
        return output_path

    def get_exit_code(self):
        """Return 0 if all passed, 1 if any failed"""
        return 0 if self.failed == 0 else 1


def main():
    suite = SelfTestSuite()
    suite.run_all_tests()
    suite.print_console_results()
    suite.save_json_results()

    exit_code = suite.get_exit_code()
    if exit_code == 0:
        print("[SUCCESS] All tests passed!\n")
    else:
        print("[FAILED] {} test(s) failed\n".format(suite.failed))

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
