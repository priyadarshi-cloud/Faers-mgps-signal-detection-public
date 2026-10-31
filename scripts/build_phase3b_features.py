"""
Phase 3B — Controlled Feature Regeneration Pipeline.

Constructs reproducible candidate pair universe and feature matrices for:
- M1: 11 pure contextual features
- M2: 20 multimodal features (M1 + 4 contingency cell counts + 5 disproportionality metrics)
- M2a: 15 count ablation features (M1 + 4 counts)
- M2b: 16 disproportionality ablation features (M1 + 5 disproportionality metrics)
- M1_sens: 16 sensitivity features (M1 + 5 quarantined outcomes)
- M2_sens: 25 sensitivity features (M2 + 5 quarantined outcomes)

Primary Cohort: Strict Archive-Bounded (2014Q1 - 2018Q4), N = 6,005,839 cases.
Pair Eligibility Threshold: a >= 2.
All outputs written to data/10_phase3b_features/ with full SHA-256 manifests.
"""

from __future__ import annotations

import os
import sys
import json
import hashlib
import datetime
import numpy as np
import pandas as pd

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.preprocessing.drug_normalizer import DrugNormalizer
from src.preprocessing.reaction_normalizer import ReactionNormalizer
from src.pipeline.pair_builder import PairBuilder
from src.signal_detection.disproportionality import DisproportionalityCalculator
from src.features.feature_extractor import FeatureExtractor

SNAPSHOT_PATH = os.path.join(PROJECT_ROOT, "data", "09_phase3a4_dual_snapshots", "as_of_2018_snapshot.csv")
EXTRACTED_DIR = os.path.join(PROJECT_ROOT, "data", "07_phase3a_continuous_ingestion", "extracted")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "data", "10_phase3b_features")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def compute_sha256(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as fh:
        while chunk := fh.read(8 * 1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def main():
    print("=" * 75)
    print("PHASE 3B — CONTROLLED FEATURE REGENERATION PIPELINE")
    print("=" * 75)
    print(f"Timestamp: {datetime.datetime.now().isoformat()}")
    print(f"Output Directory: {OUTPUT_DIR}")

    # ------------------------------------------------------------------
    # Step 1: Load Canonical Snapshot & Define Primary Cohort
    # ------------------------------------------------------------------
    print("\n[Step 1: Freezing Primary Cohort — Strict Archive-Bounded (<=2018Q4)]")
    df_snap = pd.read_csv(SNAPSHOT_PATH, dtype=str)
    print(f"  Full AS_OF_2018 Snapshot Rows: {len(df_snap):,}")

    # Strict Archive-Bounded Cohort: quarter <= 2018Q4
    df_primary = df_snap[df_snap["quarter"].str.upper() <= "2018Q4"].copy()
    n_primary_cases = len(df_primary)
    print(f"  Strict Archive-Bounded Primary Cases (N): {n_primary_cases:,}")
    assert n_primary_cases == 6005839, f"Unexpected primary case count: {n_primary_cases}"

    valid_primaryids = set(df_primary["primaryid"].unique())
    valid_caseids = set(df_primary["caseid"].unique())
    print(f"  Canonical Unique PrimaryIDs: {len(valid_primaryids):,}")
    print(f"  Canonical Unique CaseIDs:    {len(valid_caseids):,}")

    # ------------------------------------------------------------------
    # Step 2: Ingest Pre-Cutoff Child Tables (2014Q1 - 2018Q4)
    # ------------------------------------------------------------------
    print("\n[Step 2: Ingesting Child Tables from 20 Pre-Cutoff Quarters]")
    quarter_dirs = sorted([
        d for d in os.listdir(EXTRACTED_DIR)
        if os.path.isdir(os.path.join(EXTRACTED_DIR, d)) and d.upper() <= "2018Q4"
    ])
    print(f"  Quarters to load: {len(quarter_dirs)} ({quarter_dirs[0]} to {quarter_dirs[-1]})")

    all_drug = []
    all_reac = []
    all_outc = []
    all_rpsr = []

    for q in quarter_dirs:
        q_dir = os.path.join(EXTRACTED_DIR, q)
        q_upper = q.upper()

        # Find child files
        drug_file, reac_file, outc_file, rpsr_file = None, None, None, None
        for root, _, files in os.walk(q_dir):
            for f in files:
                f_u = f.upper()
                if f_u.startswith("DRUG") and f.lower().endswith(".txt"):
                    drug_file = os.path.join(root, f)
                elif f_u.startswith("REAC") and f.lower().endswith(".txt"):
                    reac_file = os.path.join(root, f)
                elif f_u.startswith("OUTC") and f.lower().endswith(".txt"):
                    outc_file = os.path.join(root, f)
                elif f_u.startswith("RPSR") and f.lower().endswith(".txt"):
                    rpsr_file = os.path.join(root, f)

        # Load DRUG
        if drug_file:
            d_cols = ["primaryid", "caseid", "drugname", "role_cod"]
            df_d = pd.read_csv(drug_file, sep="$", encoding="latin-1", dtype=str, low_memory=False)
            df_d.columns = [c.lower().strip() for c in df_d.columns]
            if "prod_ai" in df_d.columns:
                d_cols.append("prod_ai")
            avail_d = [c for c in d_cols if c in df_d.columns]
            df_d = df_d[avail_d].copy()
            df_d["primaryid"] = df_d["primaryid"].astype(str).str.strip()
            df_d["caseid"] = df_d["caseid"].astype(str).str.strip()
            # Filter to active snapshot primaryids
            df_d = df_d[df_d["primaryid"].isin(valid_primaryids)].copy()
            if len(df_d) > 0:
                all_drug.append(df_d)

        # Load REAC
        if reac_file:
            df_r = pd.read_csv(reac_file, sep="$", encoding="latin-1", dtype=str, low_memory=False)
            df_r.columns = [c.lower().strip() for c in df_r.columns]
            avail_r = [c for c in ["primaryid", "caseid", "pt"] if c in df_r.columns]
            df_r = df_r[avail_r].copy()
            df_r["primaryid"] = df_r["primaryid"].astype(str).str.strip()
            df_r["caseid"] = df_r["caseid"].astype(str).str.strip()
            df_r = df_r[df_r["primaryid"].isin(valid_primaryids)].copy()
            if len(df_r) > 0:
                all_reac.append(df_r)

        # Load OUTC
        if outc_file:
            df_o = pd.read_csv(outc_file, sep="$", encoding="latin-1", dtype=str, low_memory=False)
            df_o.columns = [c.lower().strip() for c in df_o.columns]
            avail_o = [c for c in ["primaryid", "caseid", "outc_cod"] if c in df_o.columns]
            df_o = df_o[avail_o].copy()
            df_o["primaryid"] = df_o["primaryid"].astype(str).str.strip()
            df_o["caseid"] = df_o["caseid"].astype(str).str.strip()
            df_o = df_o[df_o["primaryid"].isin(valid_primaryids)].copy()
            if len(df_o) > 0:
                all_outc.append(df_o)

        # Load RPSR
        if rpsr_file:
            df_rp = pd.read_csv(rpsr_file, sep="$", encoding="latin-1", dtype=str, low_memory=False)
            df_rp.columns = [c.lower().strip() for c in df_rp.columns]
            avail_rp = [c for c in ["primaryid", "caseid", "rpsr_cod"] if c in df_rp.columns]
            df_rp = df_rp[avail_rp].copy()
            df_rp["primaryid"] = df_rp["primaryid"].astype(str).str.strip()
            df_rp["caseid"] = df_rp["caseid"].astype(str).str.strip()
            df_rp = df_rp[df_rp["primaryid"].isin(valid_primaryids)].copy()
            if len(df_rp) > 0:
                all_rpsr.append(df_rp)

        print(f"  [{q_upper}] Filtered child records loaded successfully.")

    drug_combined = pd.concat(all_drug, ignore_index=True)
    reac_combined = pd.concat(all_reac, ignore_index=True)
    outc_combined = pd.concat(all_outc, ignore_index=True) if all_outc else pd.DataFrame()
    rpsr_combined = pd.concat(all_rpsr, ignore_index=True) if all_rpsr else pd.DataFrame()

    print(f"\n  Combined Active Child Tables:")
    print(f"    DRUG rows: {len(drug_combined):,}")
    print(f"    REAC rows: {len(reac_combined):,}")
    print(f"    OUTC rows: {len(outc_combined):,}")
    print(f"    RPSR rows: {len(rpsr_combined):,}")

    # ------------------------------------------------------------------
    # Step 3: Normalization & Report-Level Pair Construction
    # ------------------------------------------------------------------
    print("\n[Step 3: Normalization and Report-Level Pair Construction]")
    pair_builder = PairBuilder()

    print("  Processing drug records...")
    drug_proc = pair_builder.process_drugs(drug_combined)
    norm_dist = drug_proc["norm_status"].value_counts().to_dict()
    print(f"  Drug normalization distribution:")
    for st_k, cnt_v in norm_dist.items():
        print(f"    - {st_k}: {cnt_v:,} ({cnt_v / len(drug_proc) * 100:.2f}%)")

    print("  Processing reaction records...")
    reac_proc = pair_builder.process_reactions(reac_combined)

    print("  Building case pairs (Suspect PS/SS drugs, Normalized ingredients only)...")
    case_pairs = pair_builder.build_case_pairs(
        demo_df=df_primary,
        drug_df=drug_proc,
        reac_df=reac_proc,
        only_normalized_drugs=True,
        only_suspect_drugs=True
    )
    print(f"  Total case-level suspect drug-ADR occurrences: {len(case_pairs):,}")

    # Free raw child tables to release memory
    import gc
    del all_drug, all_reac, drug_combined, reac_combined
    gc.collect()

    # ------------------------------------------------------------------
    # Step 4: Disproportionality Calculation & Candidate Universe (A >= 2)
    # ------------------------------------------------------------------
    print("\n[Step 4: Disproportionality Calculation & Filtering (a >= 2)]")
    disprop_calc = DisproportionalityCalculator(min_case_count=2)
    disprop_df = disprop_calc.compute_contingency_and_metrics(
        case_pairs_df=case_pairs,
        total_case_count=n_primary_cases
    )
    n_candidate_pairs = len(disprop_df)
    print(f"  Distinct candidate drug-event pairs (a >= 2): {n_candidate_pairs:,}")

    # Sort deterministically
    disprop_df = disprop_df.sort_values(["canonical_drug", "canonical_pt"]).reset_index(drop=True)

    # ------------------------------------------------------------------
    # Step 5: Contextual Feature Extraction
    # ------------------------------------------------------------------
    print("\n[Step 5: Contextual Feature Extraction]")
    extractor = FeatureExtractor()
    model_a_df, model_b_df = extractor.extract_features(
        case_pairs_df=case_pairs,
        drug_df=drug_proc,
        outc_df=outc_combined,
        rpsr_df=rpsr_combined,
        disproportionality_df=disprop_df
    )

    # Align strictly to candidate pairs (a >= 2)
    model_a_aligned = pd.merge(
        disprop_df[["canonical_drug", "canonical_pt"]],
        model_a_df,
        on=["canonical_drug", "canonical_pt"],
        how="inner"
    ).sort_values(["canonical_drug", "canonical_pt"]).reset_index(drop=True)

    model_b_aligned = pd.merge(
        disprop_df[["canonical_drug", "canonical_pt"]],
        model_b_df,
        on=["canonical_drug", "canonical_pt"],
        how="inner"
    ).sort_values(["canonical_drug", "canonical_pt"]).reset_index(drop=True)

    print(f"  Aligned Model A matrix shape: {model_a_aligned.shape}")
    print(f"  Aligned Model B matrix shape: {model_b_aligned.shape}")

    # ------------------------------------------------------------------
    # Step 6: Assemble Feature Sets (M1, M2, M2a, M2b, M1_sens, M2_sens)
    # ------------------------------------------------------------------
    print("\n[Step 6: Assembling and Validating Model Feature Tiers]")

    key_cols = ["canonical_drug", "canonical_pt"]

    m1_core_features = [
        "mean_age", "median_age", "age_std", "age_missing_ratio", "female_ratio", "male_ratio",
        "hp_reporter_ratio", "csm_reporter_ratio",
        "monotherapy_ratio", "mean_concomitant_count",
        "secondary_suspect_ratio"
    ]

    quarantined_outcomes = [
        "death_ratio", "life_threatening_ratio", "hospitalization_ratio",
        "disability_ratio", "serious_outcome_ratio"
    ]

    contingency_counts = ["a", "b", "c", "d"]
    disprop_metrics = ["prr", "prr_chi2", "ror", "ror_lower_95", "ror_upper_95"]

    # Construct individual DataFrames
    df_m1 = model_a_aligned[key_cols + m1_core_features].copy()
    df_m2 = model_b_aligned[key_cols + m1_core_features + contingency_counts + disprop_metrics].copy()
    df_m2a = model_b_aligned[key_cols + m1_core_features + contingency_counts].copy()
    df_m2b = model_b_aligned[key_cols + m1_core_features + disprop_metrics].copy()
    df_m1_sens = model_a_aligned[key_cols + m1_core_features + quarantined_outcomes].copy()
    df_m2_sens = model_b_aligned[key_cols + m1_core_features + contingency_counts + disprop_metrics + quarantined_outcomes].copy()

    print(f"  M1 (Pure Contextual):             {len(df_m1):,} rows x {len(m1_core_features)} features")
    print(f"  M2 (Multimodal Full):             {len(df_m2):,} rows x {len(m1_core_features + contingency_counts + disprop_metrics)} features")
    print(f"  M2a (Count Ablation):             {len(df_m2a):,} rows x {len(m1_core_features + contingency_counts)} features")
    print(f"  M2b (Disproportionality Ablation):{len(df_m2b):,} rows x {len(m1_core_features + disprop_metrics)} features")
    print(f"  M1_sens (Sensitivity):            {len(df_m1_sens):,} rows x {len(m1_core_features + quarantined_outcomes)} features")
    print(f"  M2_sens (Sensitivity):            {len(df_m2_sens):,} rows x {len(m1_core_features + contingency_counts + disprop_metrics + quarantined_outcomes)} features")

    # Invariant checks
    assert len(df_m1) == n_candidate_pairs
    assert len(df_m2) == n_candidate_pairs
    assert (df_m2["a"] >= 2).all()

    for q_f in quarantined_outcomes:
        assert q_f not in df_m1.columns
        assert q_f not in df_m2.columns
        assert q_f not in df_m2a.columns
        assert q_f not in df_m2b.columns

    for d_f in contingency_counts + disprop_metrics:
        assert d_f not in df_m1.columns

    # ------------------------------------------------------------------
    # Step 7: Export Outputs & Compute Cryptographic Manifests
    # ------------------------------------------------------------------
    print("\n[Step 7: Persisting Feature Matrices and Manifests]")
    files_to_save = {
        "candidate_pairs_summary.csv": disprop_df,
        "m1_pure_contextual_features.csv": df_m1,
        "m2_multimodal_features.csv": df_m2,
        "m2a_count_ablation_features.csv": df_m2a,
        "m2b_disproportionality_ablation_features.csv": df_m2b,
        "m1_sens_features.csv": df_m1_sens,
        "m2_sens_features.csv": df_m2_sens,
    }

    manifest_files = {}

    for fname, df_out in files_to_save.items():
        fpath = os.path.join(OUTPUT_DIR, fname)
        print(f"  Saving {fname} ({len(df_out):,} rows)...")
        df_out.to_csv(fpath, index=False)
        sha = compute_sha256(fpath)
        sz = os.path.getsize(fpath)
        manifest_files[fname] = {
            "row_count": len(df_out),
            "column_count": len(df_out.columns),
            "columns": list(df_out.columns),
            "file_size_bytes": sz,
            "sha256_checksum": sha
        }
        print(f"    SHA-256: {sha}")

    # Build Master Manifest
    master_manifest = {
        "phase": "Phase 3B — Controlled Feature Regeneration",
        "cohort_name": "STRICT_ARCHIVE_BOUNDED_2018Q4",
        "cohort_description": "Strict historical simulation using solely raw FAERS quarterly archives released on or before 2018Q4 without post-cutoff backfills or retrospective retractions",
        "temporal_cutoff": "2018-12-31",
        "archive_range": "2014Q1 to 2018Q4",
        "generated_at": datetime.datetime.now().isoformat(),
        "total_unique_cases_n": n_primary_cases,
        "pair_eligibility_filter": "a >= 2",
        "candidate_pairs_count": n_candidate_pairs,
        "model_specifications": {
            "M1": {
                "name": "Pure Contextual Baseline",
                "feature_count": len(m1_core_features),
                "features": m1_core_features,
                "outcome_derived_quarantined": True,
                "disproportionality_free": True
            },
            "M2": {
                "name": "Multimodal Full Model",
                "feature_count": len(m1_core_features + contingency_counts + disprop_metrics),
                "features": m1_core_features + contingency_counts + disprop_metrics,
                "outcome_derived_quarantined": True
            },
            "M2a": {
                "name": "Count Ablation Model",
                "feature_count": len(m1_core_features + contingency_counts),
                "features": m1_core_features + contingency_counts,
                "disproportionality_metrics_excluded": True
            },
            "M2b": {
                "name": "Disproportionality Ablation Model",
                "feature_count": len(m1_core_features + disprop_metrics),
                "features": m1_core_features + disprop_metrics,
                "contingency_counts_excluded": True
            },
            "M1_sens": {
                "name": "M1 with Outcome Seriousness Sensitivity",
                "feature_count": len(m1_core_features + quarantined_outcomes),
                "features": m1_core_features + quarantined_outcomes
            },
            "M2_sens": {
                "name": "M2 with Outcome Seriousness Sensitivity",
                "feature_count": len(m1_core_features + contingency_counts + disprop_metrics + quarantined_outcomes),
                "features": m1_core_features + contingency_counts + disprop_metrics + quarantined_outcomes
            }
        },
        "quarantined_outcome_features": quarantined_outcomes,
        "files": manifest_files
    }

    manifest_path = os.path.join(OUTPUT_DIR, "phase3b_feature_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as fh:
        json.dump(master_manifest, fh, indent=2)
    print(f"\n  Saved Master Manifest: {manifest_path}")

    print("\n" + "=" * 75)
    print("PHASE 3B FEATURE REGENERATION COMPLETED SUCCESSFULLY")
    print("=" * 75)


if __name__ == "__main__":
    main()
