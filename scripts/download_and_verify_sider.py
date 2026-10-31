"""
Script to download SIDER 4.1 files and verify their SHA-256 checksums.
Preserves existing files and downloads strictly to data/04_audit_sider/.
"""

import os
import sys
import hashlib
import requests

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TARGET_DIR = os.path.join(PROJECT_ROOT, "data", "04_audit_sider")

SIDER_FILES = {
    "drug_names.tsv": "https://sideeffects.embl.de/media/download/drug_names.tsv",
    "drug_atc.tsv": "https://sideeffects.embl.de/media/download/drug_atc.tsv",
    "meddra_all_se.tsv.gz": "https://sideeffects.embl.de/media/download/meddra_all_se.tsv.gz",
    "meddra_all_indications.tsv.gz": "https://sideeffects.embl.de/media/download/meddra_all_indications.tsv.gz",
    "README": "https://sideeffects.embl.de/media/download/README"
}

def calculate_sha256(filepath: str) -> str:
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha256.update(chunk)
    return sha256.hexdigest()

def main():
    os.makedirs(TARGET_DIR, exist_ok=True)
    print("=" * 70)
    print("DOWNLOADING SIDER 4.1 DATA FILES")
    print(f"Target Directory: {TARGET_DIR}")
    print("=" * 70)

    checksums = {}

    for filename, url in SIDER_FILES.items():
        dest_path = os.path.join(TARGET_DIR, filename)
        if not os.path.exists(dest_path):
            print(f"Fetching {filename} from {url}...")
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()
            with open(dest_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=65536):
                    f.write(chunk)
            print(f"  Downloaded: {dest_path} ({os.path.getsize(dest_path):,} bytes)")
        else:
            print(f"  Existing file found: {dest_path} ({os.path.getsize(dest_path):,} bytes)")

        chk = calculate_sha256(dest_path)
        checksums[filename] = {
            "source_url": url,
            "bytes": os.path.getsize(dest_path),
            "sha256": chk
        }
        print(f"  SHA-256 [{filename}]: {chk}")

    # Write checksum manifest
    manifest_path = os.path.join(TARGET_DIR, "sider_source_checksums.json")
    import json
    with open(manifest_path, "w") as f:
        json.dump(checksums, f, indent=2)
    print(f"\nManifest saved to: {manifest_path}")

if __name__ == "__main__":
    main()
