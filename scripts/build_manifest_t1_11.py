#!/usr/bin/env python3
"""
Generate artifact_manifest.json for TASK-T1-11
"""

import hashlib
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DIR_PATH = BASE / "data" / "33_task_t1_11_final_benchmark_audit"

FILES = [
    "final_benchmark_audit_report.md",
    "independently_recomputed_statistics.csv",
    "population_provenance_findings.csv",
    "manuscript_change_log.csv",
    "manuscript_final_audited.md",
    "claims_traceability_final.csv",
    "validation_script.py"
]

manifest = {
    "task": "TASK-T1-11",
    "task_description": "Final Benchmark Audit and Evidence-Controlled Manuscript Integration",
    "output_directory": "data/33_task_t1_11_final_benchmark_audit",
    "created_at": "2026-10-17T19:48:00+05:30",
    "artifacts": {}
}

for fname in FILES:
    fpath = DIR_PATH / fname
    if not fpath.exists():
        raise FileNotFoundError(f"Missing file: {fpath}")
    data = fpath.read_bytes()
    h = hashlib.sha256(data).hexdigest()
    manifest["artifacts"][fname] = {
        "size_bytes": len(data),
        "sha256": h
    }

manifest_path = DIR_PATH / "artifact_manifest.json"
with open(manifest_path, "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2)

print(f"Manifest written to {manifest_path} with {len(manifest['artifacts'])} artifacts.")
