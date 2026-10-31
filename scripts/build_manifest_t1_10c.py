import json, hashlib
from pathlib import Path
from datetime import datetime, timezone

base = Path('data/32_task_t1_10c_benchmark_population_reconciliation')

files = [
    'benchmark_population_reconciliation_report.md',
    'input_file_inventory.csv',
    'pair_overlap_and_label_audit.csv',
    'matched_population_recomputed_statistics.csv',
    'alternate_population_statistics.csv',
    'manuscript_discrepancy_log.csv',
    'validation_script.py',
]

def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

artifacts = {}
for fname in files:
    fpath = base / fname
    if fpath.exists():
        digest = sha256(fpath)
        artifacts[fname] = {
            'sha256': digest,
            'size_bytes': fpath.stat().st_size,
            'role': 'TASK-T1-10C Deliverable'
        }
        print('OK', fname, digest[:20])
    else:
        print('MISSING', fname)

manifest = {
    'task': 'TASK-T1-10C',
    'description': 'Benchmark Population Provenance and Evaluation Reconciliation',
    'timestamp_utc': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
    'status': 'COMPLETE',
    'artifacts': artifacts
}

out = base / 'artifact_manifest.json'
with open(out, 'w', encoding='utf-8') as f:
    json.dump(manifest, f, indent=2)
print('Saved', str(out))
