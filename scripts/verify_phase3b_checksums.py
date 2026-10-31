import os
import json
import hashlib

features_dir = os.path.join("data", "10_phase3b_features")
manifest_path = os.path.join(features_dir, "phase3b_feature_manifest.json")

with open(manifest_path, "r", encoding="utf-8") as f:
    manifest = json.load(f)

print(f"Verifying {len(manifest['files'])} manifest files in {features_dir}...")
results = []
for fname, meta in manifest["files"].items():
    fpath = os.path.join(features_dir, fname)
    if not os.path.exists(fpath):
        print(f"MISSING: {fname}")
        results.append((fname, False, False, 0, 0))
        continue
    actual_size = os.path.getsize(fpath)
    expected_size = meta["file_size_bytes"]

    h = hashlib.sha256()
    with open(fpath, "rb") as fh:
        while chunk := fh.read(8 * 1024 * 1024):
            h.update(chunk)
    actual_sha = h.hexdigest()
    expected_sha = meta["sha256_checksum"]

    sha_match = (actual_sha == expected_sha)
    size_match = (actual_size == expected_size)
    print(f"  {fname}: Size {'OK' if size_match else 'FAIL'} ({actual_size:,} bytes), SHA-256 {'OK' if sha_match else 'FAIL'}")
    results.append((fname, size_match, sha_match, actual_size, expected_size))

all_ok = all(r[1] and r[2] for r in results)
print(f"\nOverall Checksum Verification: {'ALL PASSED' if all_ok else 'FAILED'}")
