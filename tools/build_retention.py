#!/usr/bin/env python3
"""
Build Diagnostic Retention Report - Shows artifact usage statistics
"""

import json
import os
from pathlib import Path
from typing import Dict, List

def retention_report(logd_dir: str = ".logd") -> Dict:
    """Generate retention report of diagnostics"""
    if not os.path.exists(logd_dir):
        return {
            "current_commit_artifacts": [],
            "older_artifacts": [],
            "total_artifact_count": 0,
            "total_bytes_used": 0
        }
    
    artifacts = []
    total_bytes = 0
    
    for f in Path(logd_dir).glob("*.json"):
        size = os.path.getsize(f)
        artifacts.append({
            "name": f.name,
            "size": size,
            "path": str(f)
        })
        total_bytes += size
    
    # Sort by timestamp (filename)
    artifacts.sort(key=lambda x: x["name"], reverse=True)
    
    current = artifacts[:5] if artifacts else []  # Assume last 5 are current
    older = artifacts[5:] if len(artifacts) > 5 else []
    
    return {
        "current_commit_artifacts": current,
        "older_artifacts": older,
        "total_artifact_count": len(artifacts),
        "total_bytes_used": total_bytes
    }

if __name__ == "__main__":
    import sys
    report = retention_report()
    print(json.dumps(report, indent=2))
