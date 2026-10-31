import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone

TARGET_DIR = Path("data/36_task_t1_14_final_numerical_reconciliation")

def sha256_file(filepath: Path) -> str:
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()

manifest = {
    "task_id": "TASK-T1-14",
    "task_title": "Final Reporter-Metric Reconciliation and Scientific Sign-Off",
    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    "output_directory": str(TARGET_DIR.as_posix()),
    "artifacts": {}
}

deliverables = [
    "final_numerical_reconciliation_report.md",
    "reporter_median_reconciliation.csv",
    "reporter_ratio_sum_reconciliation.csv",
    "lw_formula_unit_audit.csv",
    "downstream_change_log.csv",
    "final_claims_traceability.csv",
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
