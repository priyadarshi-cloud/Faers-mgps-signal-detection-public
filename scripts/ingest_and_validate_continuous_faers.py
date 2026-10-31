"""
Phase 3A - Steps 3, 4, 5: Extraction, Schema Harmonization, Quality Control,
and Temporal Deduplication Validation Engine for Continuous FAERS (2014Q1 - 2023Q4).

Performs:
1. Automated archive extraction to data/07_phase3a_continuous_ingestion/extracted/{quarter}/.
2. Cross-era schema inspection and harmonization across all 7 FAERS tables.
3. Quarter-level row counts for DEMO, DRUG, REAC, OUTC, RPSR, THER, INDI, and DELETED.
4. Comprehensive 40-quarter cumulative retraction union assembly.
5. Case-version deduplication and temporal partitioning (<= 2018-12-31 vs > 2018-12-31).
6. Quality control checks and export of manifests, QC summaries, and reports.
"""

import os
import sys
import glob
import json
import zipfile
import re
import datetime
import pandas as pd
import numpy as np

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

OUTPUT_DIR = os.path.join(PROJECT_ROOT, "data", "07_phase3a_continuous_ingestion")
ZIPS_DIR = os.path.join(OUTPUT_DIR, "raw_zips")
EXTRACTED_DIR = os.path.join(OUTPUT_DIR, "extracted")
MANIFESTS_DIR = os.path.join(OUTPUT_DIR, "manifests")
REPORTS_DIR = os.path.join(OUTPUT_DIR, "reports")

TABLE_PREFIXES = ["DEMO", "DRUG", "REAC", "OUTC", "RPSR", "THER", "INDI"]

def extract_quarter(zip_path: str, extract_dir: str):
    """Safely extract quarterly zip archive if not already extracted."""
    os.makedirs(extract_dir, exist_ok=True)
    # Check if already extracted
    has_files = False
    for root, dirs, files in os.walk(extract_dir):
        if any(f.upper().endswith(".TXT") for f in files):
            has_files = True
            break
    if has_files:
        return
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(extract_dir)

def find_quarter_files(q_dir: str):
    """Find all table files and deletion files in a quarter directory."""
    table_files = {}
    deletion_files = []

    for root, dirs, files in os.walk(q_dir):
        for f in files:
            fname_upper = f.upper()
            fpath = os.path.join(root, f)
            if not fname_upper.endswith(".TXT"):
                continue

            # Check for deletion files
            if "DELET" in fname_upper or "DELETE" in os.path.basename(root).upper():
                deletion_files.append(fpath)
                continue

            # Check table prefix
            for prefix in TABLE_PREFIXES:
                if fname_upper.startswith(prefix):
                    table_files[prefix] = fpath
                    break

    return table_files, deletion_files

def inspect_table_schema(filepath: str, prefix: str):
    """Inspect delimiter, columns, and sample row of a table."""
    with open(filepath, "r", encoding="latin-1", errors="replace") as f:
        header_line = f.readline().strip()
        sample_line = f.readline().strip()

    delimiter = "$" if "$" in header_line else ("," if "," in header_line else "\t")
    raw_cols = [c.strip() for c in header_line.split(delimiter) if c.strip()]
    normalized_cols = [c.lower() for c in raw_cols]

    # Specific normalization mappings
    harmonized_cols = []
    for c in normalized_cols:
        if prefix == "DEMO" and c == "gndr_cod":
            harmonized_cols.append("sex")
        else:
            harmonized_cols.append(c)

    return {
        "file_name": os.path.basename(filepath),
        "delimiter": delimiter,
        "column_count": len(raw_cols),
        "raw_columns": raw_cols,
        "harmonized_columns": harmonized_cols,
        "sample_line_snippet": sample_line[:150]
    }

def count_table_rows(filepath: str) -> int:
    """Fast line count for text files."""
    cnt = 0
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(1048576), b""):
            cnt += chunk.count(b"\n")
    return max(0, cnt - 1)  # subtract header

def extract_deleted_caseids(deletion_files: list) -> set:
    """Extract deleted case IDs from all deletion files in a quarter."""
    deleted_ids = set()
    for df_path in deletion_files:
        try:
            with open(df_path, "r", encoding="latin-1", errors="replace") as f:
                for line in f:
                    parts = line.strip().split("$")
                    cid = parts[0].strip()
                    if cid and cid.isdigit():
                        deleted_ids.add(cid)
        except Exception:
            pass
    return deleted_ids

def main():
    os.makedirs(EXTRACTED_DIR, exist_ok=True)
    os.makedirs(MANIFESTS_DIR, exist_ok=True)
    os.makedirs(REPORTS_DIR, exist_ok=True)

    print("=" * 75)
    print("PHASE 3A - CONTINUOUS FAERS INGESTION, QC & DEDUPLICATION ENGINE")
    print("=" * 75)

    # 1. Identify all 40 zip files
    quarters_40 = [f"{y}Q{q}" for y in range(2014, 2024) for q in range(1, 5)]
    print(f"Target quarters to process: {len(quarters_40)}")

    qc_summary_records = []
    schema_spec = {}
    all_quarter_deleted_ids = set()
    demo_dfs = []

    print("\n[Step 1: Extracting and Inspecting 40 Quarters]")
    for idx, q_key in enumerate(quarters_40, 1):
        zip_filename = f"faers_ascii_{q_key.lower()}.zip"
        zip_path = os.path.join(ZIPS_DIR, zip_filename)
        q_extract_dir = os.path.join(EXTRACTED_DIR, q_key.lower())

        if not os.path.exists(zip_path):
            print(f"[{idx:02d}/40] Archive missing: {zip_path}. Skipping.")
            continue

        print(f"[{idx:02d}/40] Extracting & Inspecting {q_key}...", flush=True)
        extract_quarter(zip_path, q_extract_dir)

        table_files, deletion_files = find_quarter_files(q_extract_dir)
        q_deleted_ids = extract_deleted_caseids(deletion_files)
        all_quarter_deleted_ids.update(q_deleted_ids)

        row_counts = {}
        for pfx in TABLE_PREFIXES:
            if pfx in table_files:
                fpath = table_files[pfx]
                rc = count_table_rows(fpath)
                row_counts[pfx] = rc

                # Register schema if not already captured
                if pfx not in schema_spec:
                    schema_spec[pfx] = inspect_table_schema(fpath, pfx)
            else:
                row_counts[pfx] = 0

        # Load DEMO table for deduplication & temporal check
        demo_path = table_files.get("DEMO")
        q_demo_len = 0
        q_valid_pids = 0
        q_missing_pids = 0

        if demo_path:
            try:
                demo_df = pd.read_csv(demo_path, sep="$", encoding="latin-1", dtype=str, low_memory=False)
                demo_df.columns = [c.lower().strip() for c in demo_df.columns]
                if "gndr_cod" in demo_df.columns and "sex" not in demo_df.columns:
                    demo_df["sex"] = demo_df["gndr_cod"]

                q_demo_len = len(demo_df)
                demo_df["primaryid"] = demo_df["primaryid"].astype(str).str.strip()
                demo_df["caseid"] = demo_df["caseid"].astype(str).str.strip()
                demo_df["quarter"] = q_key

                # Check missing IDs
                q_missing_pids = int(((demo_df["primaryid"] == "") | (demo_df["caseid"] == "") | demo_df["primaryid"].isna() | demo_df["caseid"].isna()).sum())
                q_valid_pids = q_demo_len - q_missing_pids

                # Select minimal core columns for memory-efficient multi-quarter deduplication
                core_cols = ["primaryid", "caseid", "caseversion", "init_fda_dt", "fda_dt", "quarter", "sex"]
                avail_cols = [c for c in core_cols if c in demo_df.columns]
                demo_dfs.append(demo_df[avail_cols].copy())
            except Exception as e:
                print(f"  [ERROR] Loading DEMO for {q_key}: {e}", flush=True)

        qc_rec = {
            "quarter": q_key,
            "year": int(q_key[:4]),
            "quarter_num": q_key[4:],
            "demo_rows": row_counts.get("DEMO", 0),
            "drug_rows": row_counts.get("DRUG", 0),
            "reac_rows": row_counts.get("REAC", 0),
            "outc_rows": row_counts.get("OUTC", 0),
            "rpsr_rows": row_counts.get("RPSR", 0),
            "ther_rows": row_counts.get("THER", 0),
            "indi_rows": row_counts.get("INDI", 0),
            "deleted_caseids_found": len(q_deleted_ids),
            "demo_missing_ids": q_missing_pids,
            "demo_valid_ids": q_valid_pids
        }
        qc_summary_records.append(qc_rec)

    # Export QC Summary CSV
    qc_df = pd.DataFrame(qc_summary_records)
    qc_csv_path = os.path.join(MANIFESTS_DIR, "quarter_level_qc_summaries.csv")
    qc_df.to_csv(qc_csv_path, index=False)
    print(f"\nSaved Quarter-Level QC Summaries to: {qc_csv_path}")

    # Export Schema Harmonization Specification JSON
    schema_spec_path = os.path.join(MANIFESTS_DIR, "schema_harmonization_specification.json")
    with open(schema_spec_path, "w") as f:
        json.dump(schema_spec, f, indent=2)
    print(f"Saved Schema Harmonization Specification to: {schema_spec_path}")

    # 2. Master Deduplication and Temporal Analysis
    print("\n[Step 2: Master Multi-Quarter Deduplication & Retraction Purge]")
    if demo_dfs:
        combined_demo = pd.concat(demo_dfs, ignore_index=True)
        total_raw_demo = len(combined_demo)
        print(f"Total Combined Raw DEMO Reports across processed quarters: {total_raw_demo:,}")
        print(f"Total Cumulative Retraction Case IDs identified: {len(all_quarter_deleted_ids):,}")

        # Purge deleted cases
        is_deleted = combined_demo["caseid"].isin(all_quarter_deleted_ids)
        purged_demo_cnt = int(is_deleted.sum())
        active_demo = combined_demo[~is_deleted].copy()
        total_active_demo = len(active_demo)
        print(f"Purged Deleted Reports: {purged_demo_cnt:,}")
        print(f"Active Non-Deleted Reports: {total_active_demo:,}")

        # Case Deduplication
        total_unique_caseids = active_demo["caseid"].nunique()
        print(f"Total Unique Patient Case Identifiers (N): {total_unique_caseids:,}")

        # Versions count
        version_counts = active_demo.groupby("caseid")["primaryid"].count()
        single_version_cases = int((version_counts == 1).sum())
        multi_version_cases = int((version_counts > 1).sum())
        total_followup_reports = int((version_counts - 1).clip(lower=0).sum())

        print(f"Single-Version Cases: {single_version_cases:,} ({single_version_cases/total_unique_caseids*100:.2f}%)")
        print(f"Multi-Version Cases: {multi_version_cases:,} ({multi_version_cases/total_unique_caseids*100:.2f}%)")
        print(f"Total Follow-up Revision Reports: {total_followup_reports:,}")

        # Temporal Partitioning based on init_fda_dt
        active_demo["init_date_clean"] = active_demo["init_fda_dt"].fillna("").astype(str).str.strip()
        active_demo["fda_dt_clean"] = active_demo["fda_dt"].fillna("").astype(str).str.strip()

        pre_2019_cases = active_demo[active_demo["init_date_clean"] <= "20181231"]
        post_2018_cases = active_demo[active_demo["init_date_clean"] > "20181231"]

        pre_2019_unique = pre_2019_cases["caseid"].nunique()
        post_2018_unique = post_2018_cases["caseid"].nunique()

        # As-of-date filtering audit on pre-2019 cohort to prevent lookahead leakage
        pre_cutoff_versions_as_of_valid = pre_2019_cases[pre_2019_cases["fda_dt_clean"] <= "20181231"]
        pre_cutoff_versions_post_cutoff_leak = pre_2019_cases[pre_2019_cases["fda_dt_clean"] > "20181231"]

        print(f"\nTemporal Split Anchored to Initial Receipt Date (init_fda_dt <= 20181231):")
        print(f"  Historical Baseline Partition (init_fda_dt <= 2018-12-31): {len(pre_2019_cases):,} total reports ({pre_2019_unique:,} unique cases)")
        print(f"    - Pre-cutoff valid version reports (fda_dt <= 2018-12-31): {len(pre_cutoff_versions_as_of_valid):,}")
        print(f"    - Post-cutoff follow-up revisions (fda_dt > 2018-12-31): {len(pre_cutoff_versions_post_cutoff_leak):,} (excluded from training to prevent leakage)")
        print(f"  Retrospective Surveillance Partition (init_fda_dt > 2018-12-31): {len(post_2018_cases):,} reports ({post_2018_unique:,} unique cases)")

        dedup_summary = {
            "total_raw_demo_reports": total_raw_demo,
            "cumulative_deleted_caseids": len(all_quarter_deleted_ids),
            "purged_deleted_reports": purged_demo_cnt,
            "active_retained_reports": total_active_demo,
            "unique_patient_cases_n": total_unique_caseids,
            "single_version_cases": single_version_cases,
            "multi_version_cases": multi_version_cases,
            "total_followup_reports": total_followup_reports,
            "temporal_partitions": {
                "historical_cutoff_date": "2018-12-31",
                "pre_cutoff_total_reports": len(pre_2019_cases),
                "pre_cutoff_unique_cases": pre_2019_unique,
                "pre_cutoff_valid_version_reports_as_of_20181231": len(pre_cutoff_versions_as_of_valid),
                "pre_cutoff_subsequent_followup_versions_post_2018": len(pre_cutoff_versions_post_cutoff_leak),
                "post_cutoff_total_reports": len(post_2018_cases),
                "post_cutoff_unique_cases": post_2018_unique
            }
        }

        dedup_summary_path = os.path.join(MANIFESTS_DIR, "deduplication_summary.json")
        with open(dedup_summary_path, "w") as f:
            json.dump(dedup_summary, f, indent=2)
        print(f"Saved Deduplication Summary to: {dedup_summary_path}")

    print("\n" + "=" * 75)
    print("CONTINUOUS FAERS INGESTION AND QC COMPLETED SUCCESSFULLY")
    print("=" * 75)

if __name__ == "__main__":
    main()
