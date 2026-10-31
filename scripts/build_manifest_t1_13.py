import os
import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone

TARGET_DIR = Path("data/35_task_t1_13_independent_verification")

def sha256_file(filepath: Path) -> str:
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()

manifest = {
    "task_id": "TASK-T1-13",
    "task_title": "Independent Verification of TASK-T1-12",
    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    "output_directory": str(TARGET_DIR.as_posix()),
    "artifacts": {}
}

deliverables = [
    "independent_verification_report.md",
    "mgps_parameter_discrepancy_audit.csv",
    "reporter_recomputation_verification.csv",
    "contextual_statistics_reproduction.csv",
    "benchmark_consistency_check.csv",
    "manuscript_claims_audit.csv",
    "validation_quality_review.md",
    "validation_script.py"
]

for name in deliverables:
    fpath = TARGET_DIR / name
    if fpath.exists():
        manifest["artifacts"][name] = {
            "size_bytes": fpath.stat().st_size,
            "sha256": sha256_file(fpath)
        }
    else:
        print(f"Warning: {name} not found!")

out_manifest = TARGET_DIR / "artifact_manifest.json"
with open(out_manifest, "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2)

print(f"Manifest written to {out_manifest.resolve()} with {len(manifest['artifacts'])} artifacts.")
