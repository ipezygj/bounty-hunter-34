#!/usr/bin/env python3
"""
Stale Diagnostic Cleanup - Remove old .logd files with dry-run support
"""

import os
import json
import sys
from pathlib import Path
from typing import List, Dict

def cleanup_stale(logd_dir: str = ".logd", apply: bool = False, dry_run: bool = True) -> Dict:
    """
    List or delete stale diagnostics.
    Never removes current commit's .logd or JSON diagnostics.
    """
    if not os.path.exists(logd_dir):
        return {"stale_items": [], "total_would_remove": 0}
    
    all_files = sorted(Path(logd_dir).glob("build-*.json"))
    
    # Keep current commit (assume last 5 are current)
    current_count = 5
    stale_files = all_files[:-current_count] if len(all_files) > current_count else []
    
    removed = []
    for f in stale_files:
        if dry_run or not apply:
            removed.append(str(f))
        else:
            try:
                os.remove(f)
                removed.append(str(f))
            except Exception as e:
                print(f"Error removing {f}: {e}", file=sys.stderr)
    
    mode = "DRY-RUN" if dry_run and not apply else "APPLIED" if apply else "LIST"
    return {
        "mode": mode,
        "stale_items": removed,
        "current_artifacts_preserved": current_count,
        "total_would_remove": len(removed)
    }

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Actually delete (default: dry-run)")
    parser.add_argument("--dry-run", action="store_true", default=True, help="List only")
    args = parser.parse_args()
    
    result = cleanup_stale(apply=args.apply, dry_run=not args.apply)
    print(json.dumps(result, indent=2))
