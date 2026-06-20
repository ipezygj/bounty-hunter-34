import unittest
import tempfile
import os
import json
from pathlib import Path
from tools.build_retention import retention_report

class TestRetentionReport(unittest.TestCase):
    def test_current_artifacts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test artifacts
            Path(tmpdir, "build-20260620-001.json").write_text('{"status":"ok"}')
            Path(tmpdir, "build-20260620-002.json").write_text('{"status":"ok"}')
            
            report = retention_report(tmpdir)
            assert report["total_artifact_count"] == 2
            assert report["total_bytes_used"] > 0
    
    def test_stale_artifacts_preserved(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            for i in range(10):
                Path(tmpdir, f"build-00000{i}.json").write_text('{"x":"y"}')
            
            report = retention_report(tmpdir)
            assert len(report["current_commit_artifacts"]) == 5
            assert len(report["older_artifacts"]) == 5

if __name__ == "__main__":
    unittest.main()
