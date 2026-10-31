"""
Phase 3A - Step 1 & 2: Continuous FAERS Data Acquisition and Integrity Verification.
Multi-threaded, resilient downloader for 40 quarterly FAERS archives (2014Q1 - 2023Q4).

Features:
- Official FDA URL mapping from FIS portal.
- Multi-threaded parallel downloads (max_workers=4) with retries.
- Resumes already completed and verified archives.
- Copies existing local sample archives (2014Q1, 2019Q1, 2023Q1).
- Computes SHA-256 checksums for all 40 archives.
- Verifies ZIP integrity (testzip) for all archives.
- Produces quarterly ingestion manifest (CSV and JSON).
"""

import os
import sys
import shutil
import hashlib
import zipfile
import datetime
import requests
import re
import json
import time
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

OUTPUT_DIR = os.path.join(PROJECT_ROOT, "data", "07_phase3a_continuous_ingestion")
ZIPS_DIR = os.path.join(OUTPUT_DIR, "raw_zips")
MANIFESTS_DIR = os.path.join(OUTPUT_DIR, "manifests")
RAW_SAMPLE_DIR = os.path.join(PROJECT_ROOT, "data", "01_raw", "sample_quarters")

def check_disk_space(required_gb: float = 20.0):
    total, used, free = shutil.disk_usage(PROJECT_ROOT)
    free_gb = free / (1024 ** 3)
    print(f"[Disk Space Check] Free: {free_gb:.2f} GB (Required: {required_gb:.2f} GB)")
    if free_gb < required_gb:
        raise RuntimeError(f"Insufficient disk space: {free_gb:.2f} GB free < {required_gb:.2f} GB required!")

def fetch_official_fda_urls():
    url = "https://fis.fda.gov/extensions/FPD-QDE-FAERS/FPD-QDE-FAERS.html"
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    zip_links = set(re.findall(r'href=[\'"]([^\'"]+?\.zip)[\'"]', r.text, re.IGNORECASE))
    mapping = {}
    for l in zip_links:
        if "ascii" in l.lower():
            m = re.search(r'(\d{4})[Qq](\d)', l)
            if m:
                key = f"{m.group(1)}Q{m.group(2)}"
                mapping[key] = l
    return mapping

def calculate_sha256(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(1048576), b""):
            h.update(chunk)
    return h.hexdigest()

def verify_zip_integrity(filepath: str) -> bool:
    try:
        if not os.path.exists(filepath) or os.path.getsize(filepath) < 1000:
            return False
        with zipfile.ZipFile(filepath, "r") as z:
            corrupt = z.testzip()
            return corrupt is None
    except Exception:
        return False

def download_quarter(q_key: str, url: str):
    zip_filename = f"faers_ascii_{q_key.lower()}.zip"
    dest_path = os.path.join(ZIPS_DIR, zip_filename)
    temp_path = dest_path + ".part"
    retrieval_status = "FETCHED_REMOTE"

    # Check if already present and valid in ZIPS_DIR
    if os.path.exists(dest_path) and verify_zip_integrity(dest_path):
        size = os.path.getsize(dest_path)
        sha = calculate_sha256(dest_path)
        print(f"[{q_key}] Already downloaded & verified ({size/(1024*1024):.1f} MB).")
        return {
            "quarter": q_key,
            "year": int(q_key[:4]),
            "quarter_num": q_key[4:],
            "official_url": url,
            "http_status": 200,
            "archive_filename": zip_filename,
            "archive_bytes": size,
            "archive_mb": round(size / (1024 * 1024), 2),
            "sha256": sha,
            "zip_integrity_passed": True,
            "retrieval_status": "CACHED_LOCAL",
            "retrieval_timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }

    # Check if present in RAW_SAMPLE_DIR
    sample_zip = os.path.join(RAW_SAMPLE_DIR, f"{q_key.lower()}.zip")
    if os.path.exists(sample_zip) and verify_zip_integrity(sample_zip):
        print(f"[{q_key}] Copying from sample archives...")
        shutil.copy2(sample_zip, dest_path)
        size = os.path.getsize(dest_path)
        sha = calculate_sha256(dest_path)
        return {
            "quarter": q_key,
            "year": int(q_key[:4]),
            "quarter_num": q_key[4:],
            "official_url": url,
            "http_status": 200,
            "archive_filename": zip_filename,
            "archive_bytes": size,
            "archive_mb": round(size / (1024 * 1024), 2),
            "sha256": sha,
            "zip_integrity_passed": True,
            "retrieval_status": "COPIED_FROM_SAMPLE",
            "retrieval_timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }

    # Download with up to 3 retries (supporting resume via -C -)
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            t0 = time.time()
            current_bytes = os.path.getsize(temp_path) if os.path.exists(temp_path) else 0
            print(f"[{q_key}] Downloading (attempt {attempt}/{max_retries}) via curl (resuming from {current_bytes/(1024*1024):.1f} MB) from {url}...", flush=True)
            cmd = ["curl.exe", "-L", "-s", "-f", "-C", "-", "--retry", "5", "--retry-delay", "3", "-o", temp_path, url]
            ret = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
            if ret.returncode != 0:
                print(f"[{q_key}] curl code {ret.returncode}: {ret.stderr}. Cleaning partial file for next attempt...", flush=True)
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except Exception:
                        pass
                raise RuntimeError(f"curl returned code {ret.returncode}: {ret.stderr}")

            # Verify zip before replacing
            if verify_zip_integrity(temp_path):
                os.replace(temp_path, dest_path)
                size = os.path.getsize(dest_path)
                sha = calculate_sha256(dest_path)
                dur = time.time() - t0
                mb_s = (size / (1024 * 1024)) / dur if dur > 0 else 0
                print(f"[{q_key}] SUCCESS: {size/(1024*1024):.1f} MB in {dur:.1f}s ({mb_s:.2f} MB/s)", flush=True)
                return {
                    "quarter": q_key,
                    "year": int(q_key[:4]),
                    "quarter_num": q_key[4:],
                    "official_url": url,
                    "http_status": 200,
                    "archive_filename": zip_filename,
                    "archive_bytes": size,
                    "archive_mb": round(size / (1024 * 1024), 2),
                    "sha256": sha,
                    "zip_integrity_passed": True,
                    "retrieval_status": retrieval_status,
                    "retrieval_timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()
                }
            else:
                print(f"[{q_key}] ZIP integrity failed on attempt {attempt}. Removing corrupted file.", flush=True)
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except Exception:
                        pass
        except Exception as e:
            print(f"[{q_key}] Download error on attempt {attempt}: {e}", flush=True)
            time.sleep(2 * attempt)

    raise RuntimeError(f"FATAL: All {max_retries} download attempts failed for {q_key} from {url}")

def main():
    os.makedirs(ZIPS_DIR, exist_ok=True)
    os.makedirs(MANIFESTS_DIR, exist_ok=True)

    print("=" * 75)
    print("PHASE 3A - PARALLEL RESILIENT FAERS ACQUISITION (2014Q1 - 2023Q4)")
    print("=" * 75)

    check_disk_space(required_gb=20.0)

    print("\n[Step 1: Resolving Official FDA URLs]")
    fda_url_map = fetch_official_fda_urls()
    print(f"Successfully resolved {len(fda_url_map)} quarterly ASCII URLs from FDA FIS portal.")

    quarters_40 = [f"{y}Q{q}" for y in range(2014, 2024) for q in range(1, 5)]

    print(f"\n[Step 2: Downloading & Verifying 40 Quarters (max_workers=4)]", flush=True)
    results = []

    with ThreadPoolExecutor(max_workers=4) as executor:
        future_to_quarter = {
            executor.submit(download_quarter, q, fda_url_map[q]): q
            for q in quarters_40
        }
        for future in as_completed(future_to_quarter):
            q_code = future_to_quarter[future]
            try:
                res = future.result()
                results.append(res)
            except Exception as e:
                print(f"FATAL EXCEPTION for {q_code}: {e}")
                raise e

    # Sort results by quarter chronologically
    results.sort(key=lambda r: (r["year"], r["quarter_num"]))

    # Save Ingestion Manifest
    manifest_df = pd.DataFrame(results)
    csv_path = os.path.join(MANIFESTS_DIR, "quarterly_ingestion_manifest.csv")
    json_path = os.path.join(MANIFESTS_DIR, "quarterly_ingestion_manifest.json")

    manifest_df.to_csv(csv_path, index=False)
    with open(json_path, "w") as f:
        json.dump(results, f, indent=2)

    total_download_mb = manifest_df["archive_mb"].sum()
    print("\n" + "=" * 75)
    print("CONTINUOUS FAERS ACQUISITION COMPLETED SUCCESSFULLY")
    print(f"Total Quarters Verified: {len(manifest_df)} / 40 (100%)")
    print(f"Total Archive Volume: {total_download_mb:.2f} MB ({total_download_mb / 1024:.2f} GB)")
    print(f"Ingestion Manifest CSV: {csv_path}")
    print(f"Ingestion Manifest JSON: {json_path}")
    print("=" * 75)

if __name__ == "__main__":
    main()
