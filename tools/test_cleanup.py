import unittest
import tempfile
import os
import json
from pathlib import Path
from tools.cleanup_stale import cleanup_stale

class TestCleanupStale(unittest.TestCase):
    def test_dry_run_does_not_delete(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            for i in range(10):
                Path(tmpdir, f"build-{i:08d}.json").write_text('{}')
            
            result = cleanup_stale(tmpdir, apply=False, dry_run=True)
            assert result["mode"] == "DRY-RUN"
            assert len(result["stale_items"]) == 5  # 10 - 5 current = 5 stale
            
            # Verify files still exist
            files_after = list(Path(tmpdir).glob("*.json"))
            assert len(files_after) == 10
    
    def test_apply_deletes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            for i in range(10):
                Path(tmpdir, f"build-{i:08d}.json").write_text('{}')
            
            result = cleanup_stale(tmpdir, apply=True, dry_run=False)
            assert result["mode"] == "APPLIED"
            
            files_after = list(Path(tmpdir).glob("*.json"))
            assert len(files_after) == 5  # Only current kept
    
    def test_preserves_current(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            for i in range(3):
                Path(tmpdir, f"build-{i:08d}.json").write_text('{}')
            
            result = cleanup_stale(tmpdir, apply=True, dry_run=False)
            assert result["current_artifacts_preserved"] == 5
            assert len(result["stale_items"]) == 0

if __name__ == "__main__":
    unittest.main()
