#!/usr/bin/env python3
"""
Generate artifact_manifest.json for TASK-T1-12
"""

import hashlib
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DIR_PATH = BASE / "data" / "34_task_t1_12_final_scientific_corrections"

FILES = [
    "recovery_report.md",
    "scientific_corrections_report.md",
    "reporter_code_dictionary_audit.csv",
    "reporter_feature_recomputation_summary.csv",
    "contextual_results_discrepancy_log.csv",
    "manuscript_change_log.csv",
    "manuscript_final_scientifically_corrected.md",
    "claims_traceability.csv",
    "validation_script.py"
]

manifest = {
    "task": "TASK-T1-12",
    "task_description": "Final Scientific Corrections and Contextual Reporter Audit",
    "output_directory": "data/34_task_t1_12_final_scientific_corrections",
    "created_at": "2026-10-18T00:43:00+05:30",
    "artifacts": {}
}

for fname in FILES:
    fpath = DIR_PATH / fname
    if not fpath.exists():
        raise FileNotFoundError(f"Missing deliverable: {fpath}")
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
