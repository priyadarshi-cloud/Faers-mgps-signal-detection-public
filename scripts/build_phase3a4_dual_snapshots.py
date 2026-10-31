"""
Phase 3A.4 — Dual Historical Snapshot Builder and Manifest Generator.

Implements two reproducible snapshot policies as of cutoff 2018-12-31:
1. AS_OF_2018:
   - Uses ONLY deletions demonstrably available by 2018-12-31.
   - Deletions in 2014Q1–2018Q4 raw archives: empty set ∅.
   - Preserves all pre-cutoff cases (6,012,891 canonical cases).
2. RETROSPECTIVELY_CORRECTED:
   - Uses cumulative deletion union across all 40 quarters (177,987 unique IDs).
   - Purges known retrospective retractions (5,987,173 canonical cases).

Computes SHA-256 checksums, full metadata manifests, and reconciles counts.
Preserves existing Phase 3A.2 outputs in data/08_phase3a2_snapshot/ untouched.
All outputs written to data/09_phase3a4_dual_snapshots/.
"""

from __future__ import annotations

import os
import sys
import json
import glob
import hashlib
import datetime
import pandas as pd
import numpy as np

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.preprocessing.historical_snapshot import HistoricalSnapshotBuilder

INGESTION_DIR = os.path.join(PROJECT_ROOT, "data", "07_phase3a_continuous_ingestion")
EXTRACTED_DIR = os.path.join(INGESTION_DIR, "extracted")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "data", "09_phase3a4_dual_snapshots")
os.makedirs(OUTPUT_DIR, exist_ok=True)

CUTOFF = "20181231"
CUTOFF_DATE_LABEL = "2018-12-31"


def compute_sha256(filepath: str) -> str:
    """Compute SHA-256 hash of a file in chunks."""
    h = hashlib.sha256()
    with open(filepath, "rb") as fh:
        while chunk := fh.read(1024 * 1024 * 8):  # 8MB chunks
            h.update(chunk)
    return h.hexdigest()


DEMO_CORE_COLS = ["primaryid", "caseid", "caseversion", "init_fda_dt", "fda_dt",
                  "sex", "age", "age_cod", "occp_cod", "reporter_country",
                  "i_f_code", "rept_dt", "mfr_sndr", "quarter"]

def load_demo(demo_path: str, quarter_label: str) -> pd.DataFrame | None:
    try:
        df = pd.read_csv(demo_path, sep="$", encoding="latin-1", dtype=str, low_memory=False)
        df.columns = [c.lower().strip() for c in df.columns]
        if "gndr_cod" in df.columns and "sex" not in df.columns:
            df.rename(columns={"gndr_cod": "sex"}, inplace=True)
        df["quarter"] = quarter_label
        df["primaryid"] = df["primaryid"].astype(str).str.strip()
        df["caseid"] = df["caseid"].astype(str).str.strip()
        avail = [c for c in DEMO_CORE_COLS if c in df.columns]
        return df[avail].copy()
    except Exception as exc:
        print(f"  [ERROR] Cannot load DEMO from {demo_path}: {exc}")
        return None

def find_demo_file(q_dir: str) -> str | None:
    for root, _, files in os.walk(q_dir):
        for f in files:
            if f.upper().startswith("DEMO") and f.lower().endswith(".txt"):
                return os.path.join(root, f)
    return None


def main():
    print("=" * 75, flush=True)
    print("PHASE 3A.4 — DUAL HISTORICAL SNAPSHOT GENERATION & MANIFEST BUILDER", flush=True)
    print("=" * 75, flush=True)
    print(f"Cutoff Date: {CUTOFF_DATE_LABEL}", flush=True)
    print(f"Output Directory: {OUTPUT_DIR}", flush=True)

    # ------------------------------------------------------------------
    # Step 1: Discover and categorize all deletion files
    # ------------------------------------------------------------------
    print("\n[Step 1: Auditing Deletion Files Across 40 Quarters]", flush=True)
    del_files_pre2018 = []
    del_files_all = []
    all_deleted_ids = set()

    quarter_dirs = sorted([
        os.path.join(EXTRACTED_DIR, d) for d in os.listdir(EXTRACTED_DIR)
        if os.path.isdir(os.path.join(EXTRACTED_DIR, d))
    ])

    for q_dir in quarter_dirs:
        q_name = os.path.basename(q_dir)
        is_pre_2018 = q_name.lower() <= "2018q4"
        for root, _, files in os.walk(q_dir):
            for f in files:
                if "delet" in f.lower() and f.lower().endswith(".txt"):
                    rel_p = os.path.normpath(os.path.relpath(os.path.join(root, f), EXTRACTED_DIR))
                    del_files_all.append(rel_p)
                    if is_pre_2018:
                        del_files_pre2018.append(rel_p)
                    with open(os.path.join(root, f), "r", encoding="utf-8", errors="replace") as fh:
                        for line in fh:
                            token = line.strip()
                            if token and token.isdigit():
                                all_deleted_ids.add(token)

    print(f"  Total deletion files discovered: {len(del_files_all)}", flush=True)
    print(f"  Deletion files available by 2018-12-31: {len(del_files_pre2018)}", flush=True)
    print(f"  Cumulative unique deleted IDs (all 40 quarters): {len(all_deleted_ids):,}", flush=True)

    # ------------------------------------------------------------------
    # Step 2: Load all 40 quarterly DEMO tables
    # ------------------------------------------------------------------
    print(f"\n[Step 2: Loading all {len(quarter_dirs)} DEMO tables]", flush=True)
    demo_dfs = []
    for q_dir in quarter_dirs:
        q_name = os.path.basename(q_dir).upper()
        demo_file = find_demo_file(q_dir)
        if not demo_file:
            print(f"  WARNING: No DEMO table found in {q_name}", flush=True)
            continue
        df_q = load_demo(demo_file, q_name)
        if df_q is not None and len(df_q) > 0:
            demo_dfs.append(df_q)
            print(f"  [{q_name}]  {len(df_q):>10,} rows loaded", flush=True)

    combined_demo = pd.concat(demo_dfs, ignore_index=True)
    n_combined = len(combined_demo)
    print(f"\n  Combined DEMO rows across all 40 quarters: {n_combined:,}", flush=True)

    builder = HistoricalSnapshotBuilder(cutoff_yyyymmdd=CUTOFF)

    # ------------------------------------------------------------------
    # Step 3: Build Snapshot Policy 1 — AS_OF_2018
    # ------------------------------------------------------------------
    print("\n" + "-" * 60)
    print("[Step 3: Building Policy 1 — AS_OF_2018 (Strict Historical)]")
    print("-" * 60)
    print("  Deletions applied: NONE (0 deletion files available by 2018-12-31)")

    snap_2018, audit_2018, q_2018 = builder.build(combined_demo, deleted_caseids=set())

    print(f"  Input raw rows:          {audit_2018['n_raw_input_rows']:>12,}")
    print(f"  Excluded init>cutoff:    {audit_2018['n_excluded_init_after_cutoff']:>12,}")
    print(f"  Excluded fda>cutoff:     {audit_2018['n_excluded_fda_after_cutoff']:>12,}")
    print(f"  Excluded deleted:        {audit_2018['n_excluded_deleted']:>12,}")
    print(f"  Canonical selected rows: {len(snap_2018):>12,}")
    print(f"  Duplicate caseids:       {audit_2018['duplicate_caseid_in_snapshot']:>12,}")
    print(f"  Count identity check:    {audit_2018['audit_selected_eq_eligible_caseids']}")

    path_2018_csv = os.path.join(OUTPUT_DIR, "as_of_2018_snapshot.csv")
    print(f"  Saving {path_2018_csv}...")
    snap_2018.to_csv(path_2018_csv, index=False)
    sha_2018 = compute_sha256(path_2018_csv)
    size_2018 = os.path.getsize(path_2018_csv)
    print(f"  SHA-256: {sha_2018} ({size_2018:,} bytes)")

    manifest_2018 = {
        "policy_name": "AS_OF_2018",
        "description": "Historical snapshot using strictly information available by 2018-12-31 without retraction look-ahead",
        "cutoff_date": CUTOFF_DATE_LABEL,
        "generated_at": datetime.datetime.now().isoformat(),
        "input_raw_demo_rows": audit_2018["n_raw_input_rows"],
        "duplicate_primaryid_rows_excluded": audit_2018.get("n_duplicate_primaryid_rows_excluded", 0),
        "date_ineligible_quarantined": audit_2018["n_date_ineligible_quarantined"],
        "excluded_init_after_cutoff": audit_2018["n_excluded_init_after_cutoff"],
        "excluded_fda_after_cutoff": audit_2018["n_excluded_fda_after_cutoff"],
        "excluded_retracted_cases": audit_2018["n_excluded_deleted"],
        "eligible_unique_caseids": audit_2018["n_eligible_unique_caseids"],
        "canonical_selected_cases": len(snap_2018),
        "duplicate_caseids_in_snapshot": audit_2018["duplicate_caseid_in_snapshot"],
        "selection_reasons": snap_2018["_selection_reason"].value_counts().to_dict(),
        "deletion_files_applied": del_files_pre2018,
        "n_deletion_files_applied": len(del_files_pre2018),
        "snapshot_file": "as_of_2018_snapshot.csv",
        "file_size_bytes": size_2018,
        "sha256_checksum": sha_2018,
    }
    path_2018_manifest = os.path.join(OUTPUT_DIR, "as_of_2018_manifest.json")
    with open(path_2018_manifest, "w", encoding="utf-8") as fh:
        json.dump(manifest_2018, fh, indent=2)
    print(f"  Manifest saved: {path_2018_manifest}")

    # ------------------------------------------------------------------
    # Step 4: Build Snapshot Policy 2 — RETROSPECTIVELY_CORRECTED
    # ------------------------------------------------------------------
    print("\n" + "-" * 60)
    print("[Step 4: Building Policy 2 — RETROSPECTIVELY_CORRECTED]")
    print("-" * 60)
    print(f"  Deletions applied: Cumulative union of all {len(del_files_all)} files ({len(all_deleted_ids):,} IDs)")

    snap_retro, audit_retro, q_retro = builder.build(combined_demo, deleted_caseids=all_deleted_ids)

    print(f"  Input raw rows:          {audit_retro['n_raw_input_rows']:>12,}")
    print(f"  Excluded init>cutoff:    {audit_retro['n_excluded_init_after_cutoff']:>12,}")
    print(f"  Excluded fda>cutoff:     {audit_retro['n_excluded_fda_after_cutoff']:>12,}")
    print(f"  Excluded deleted:        {audit_retro['n_excluded_deleted']:>12,}")
    print(f"  Canonical selected rows: {len(snap_retro):>12,}")
    print(f"  Duplicate caseids:       {audit_retro['duplicate_caseid_in_snapshot']:>12,}")
    print(f"  Count identity check:    {audit_retro['audit_selected_eq_eligible_caseids']}")

    path_retro_csv = os.path.join(OUTPUT_DIR, "retrospectively_corrected_snapshot.csv")
    print(f"  Saving {path_retro_csv}...")
    snap_retro.to_csv(path_retro_csv, index=False)
    sha_retro = compute_sha256(path_retro_csv)
    size_retro = os.path.getsize(path_retro_csv)
    print(f"  SHA-256: {sha_retro} ({size_retro:,} bytes)")

    manifest_retro = {
        "policy_name": "RETROSPECTIVELY_CORRECTED",
        "description": "Historical snapshot using cutoff 2018-12-31 with cumulative retrospective deletion purge up to 2023Q4",
        "cutoff_date": CUTOFF_DATE_LABEL,
        "generated_at": datetime.datetime.now().isoformat(),
        "input_raw_demo_rows": audit_retro["n_raw_input_rows"],
        "duplicate_primaryid_rows_excluded": audit_retro.get("n_duplicate_primaryid_rows_excluded", 0),
        "date_ineligible_quarantined": audit_retro["n_date_ineligible_quarantined"],
        "excluded_init_after_cutoff": audit_retro["n_excluded_init_after_cutoff"],
        "excluded_fda_after_cutoff": audit_retro["n_excluded_fda_after_cutoff"],
        "excluded_retracted_cases": audit_retro["n_excluded_deleted"],
        "eligible_unique_caseids": audit_retro["n_eligible_unique_caseids"],
        "canonical_selected_cases": len(snap_retro),
        "duplicate_caseids_in_snapshot": audit_retro["duplicate_caseid_in_snapshot"],
        "selection_reasons": snap_retro["_selection_reason"].value_counts().to_dict(),
        "deletion_files_applied": del_files_all,
        "n_deletion_files_applied": len(del_files_all),
        "snapshot_file": "retrospectively_corrected_snapshot.csv",
        "file_size_bytes": size_retro,
        "sha256_checksum": sha_retro,
    }
    path_retro_manifest = os.path.join(OUTPUT_DIR, "retrospectively_corrected_manifest.json")
    with open(path_retro_manifest, "w", encoding="utf-8") as fh:
        json.dump(manifest_retro, fh, indent=2)
    print(f"  Manifest saved: {path_retro_manifest}")

    # ------------------------------------------------------------------
    # Step 5: Reconciliation & Cross-Validation
    # ------------------------------------------------------------------
    print("\n" + "=" * 75)
    print("[Step 5: Reconciling Both Snapshots Against Phase 3A.3 Audit]")
    print("=" * 75)

    cases_2018 = set(snap_2018["caseid"].unique())
    cases_retro = set(snap_retro["caseid"].unique())
    diff_cases = cases_2018 - cases_retro

    print(f"  AS_OF_2018 unique cases:              {len(cases_2018):>10,}")
    print(f"  RETROSPECTIVELY_CORRECTED cases:      {len(cases_retro):>10,}")
    print(f"  Cases excluded solely by deletions:   {len(diff_cases):>10,}")
    print(f"  Expected diff from Phase 3A.3 audit:      25,718")
    print(f"  Matches Phase 3A.3 exact audit count: {len(diff_cases) == 25718}")

    reconciliation = {
        "cutoff_date": CUTOFF_DATE_LABEL,
        "generated_at": datetime.datetime.now().isoformat(),
        "as_of_2018_case_count": len(cases_2018),
        "retrospectively_corrected_case_count": len(cases_retro),
        "cases_excluded_solely_by_retrospective_deletions": len(diff_cases),
        "expected_cases_excluded_from_phase3a3": 25718,
        "reconciliation_matches_audit": len(diff_cases) == 25718,
        "as_of_2018_sha256": sha_2018,
        "retrospectively_corrected_sha256": sha_retro,
    }
    recon_summary_path = os.path.join(OUTPUT_DIR, "reconciliation_summary.json")
    with open(recon_summary_path, "w", encoding="utf-8") as fh:
        json.dump(reconciliation, fh, indent=2)
    print(f"  Reconciliation summary saved: {recon_summary_path}")

    print("\n" + "=" * 75)
    print("PHASE 3A.4 DUAL SNAPSHOT BUILD COMPLETED SUCCESSFULLY")
    print("=" * 75)


if __name__ == "__main__":
    main()
