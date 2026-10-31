"""
Modelling Dataset Preparation and Feature Matrix Alignment Script.

Aligns feature matrices to the approved candidate-pair universe (A >= 2, N=519,748).
Enforces:
1. Backup of unaligned feature matrices.
2. Exact key alignment across candidate pairs, Model A, and Model B.
3. Feature column specifications for M1, M2, M2a, M2b, and sensitivity sets.
4. Methodological firewalls against outcome confounding, disproportionality leakage, and benchmark contamination.
"""

import os
import sys
import shutil
import json
import pandas as pd
import numpy as np

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

def backup_unaligned_features(primary_dir: str, backup_dir: str):
    """Safely back up unaligned feature matrices before modification."""
    os.makedirs(backup_dir, exist_ok=True)
    for fname in ["phase2_model_a_features.csv", "phase2_model_b_features.csv"]:
        src = os.path.join(primary_dir, fname)
        dst = os.path.join(backup_dir, fname)
        if os.path.exists(src) and not os.path.exists(dst):
            print(f"[Backup] Copying {src} -> {dst}...")
            shutil.copy2(src, dst)
        else:
            print(f"[Backup] {dst} already exists or src missing. Skipping copy.")

def main():
    primary_dir = os.path.join(PROJECT_ROOT, "data", "03_primary")
    backup_dir = os.path.join(primary_dir, "backup_unaligned_features")

    cp_path = os.path.join(primary_dir, "phase2_candidate_pairs_summary.csv")
    ma_path = os.path.join(primary_dir, "phase2_model_a_features.csv")
    mb_path = os.path.join(primary_dir, "phase2_model_b_features.csv")

    print("=" * 70)
    print("STEP 1: PRESERVE BACKUP OF UNALIGNED FEATURE MATRICES")
    print("=" * 70)
    backup_unaligned_features(primary_dir, backup_dir)

    print("\n" + "=" * 70)
    print("STEP 2: LOAD CANONICAL CANDIDATE PAIRS (A >= 2)")
    print("=" * 70)
    cp_df = pd.read_csv(cp_path)
    print(f"Candidate pairs loaded: {len(cp_df):,} rows.")
    assert (cp_df["a"] >= 2).all(), "Invariant violation: A < 2 found in candidate pairs summary!"

    # Sort CP deterministically by canonical keys
    cp_df = cp_df.sort_values(["canonical_drug", "canonical_pt"]).reset_index(drop=True)
    valid_keys = set(zip(cp_df["canonical_drug"], cp_df["canonical_pt"]))
    print(f"Unique candidate pair keys: {len(valid_keys):,}")

    print("\n" + "=" * 70)
    print("STEP 3: ALIGN MODEL A FEATURES (11 CORE CONTEXTUAL + 5 QUARANTINED)")
    print("=" * 70)
    # Read unaligned Model A from backup if available, else from primary
    ma_source = os.path.join(backup_dir, "phase2_model_a_features.csv")
    if not os.path.exists(ma_source):
        ma_source = ma_path
    ma_df = pd.read_csv(ma_source)
    print(f"Original Model A rows: {len(ma_df):,}")

    # Inner merge with CP keys to strictly preserve candidate universe
    ma_aligned = pd.merge(
        cp_df[["canonical_drug", "canonical_pt"]],
        ma_df,
        on=["canonical_drug", "canonical_pt"],
        how="inner"
    )
    print(f"Aligned Model A rows: {len(ma_aligned):,}")
    assert len(ma_aligned) == len(cp_df), f"Mismatch in Model A alignment: {len(ma_aligned)} vs {len(cp_df)}"

    print("\n" + "=" * 70)
    print("STEP 4: ALIGN MODEL B FEATURES (EXTENDED WITH A, B, C, D, PRR, ROR)")
    print("=" * 70)
    mb_source = os.path.join(backup_dir, "phase2_model_b_features.csv")
    if not os.path.exists(mb_source):
        mb_source = mb_path
    mb_df = pd.read_csv(mb_source)
    print(f"Original Model B rows: {len(mb_df):,}")

    mb_aligned = pd.merge(
        cp_df[["canonical_drug", "canonical_pt"]],
        mb_df,
        on=["canonical_drug", "canonical_pt"],
        how="inner"
    )
    print(f"Aligned Model B rows: {len(mb_aligned):,}")
    assert len(mb_aligned) == len(cp_df), f"Mismatch in Model B alignment: {len(mb_aligned)} vs {len(cp_df)}"

    # Check for NaN in disproportionality metrics in aligned Model B
    disprop_cols = ["a", "b", "c", "d", "prr", "prr_chi2", "ror", "ror_lower_95", "ror_upper_95"]
    nan_counts = mb_aligned[disprop_cols].isna().sum().to_dict()
    print("Disproportionality NaN check in aligned Model B:", nan_counts)
    assert all(c == 0 for c in nan_counts.values()), "Disproportionality metrics contain NaNs in aligned universe!"

    print("\n" + "=" * 70)
    print("STEP 5: CONFIRM EXACT FEATURE COLUMN SPECIFICATIONS")
    print("=" * 70)

    # Identifiers (Keys)
    key_cols = ["canonical_drug", "canonical_pt"]

    # 11 Primary Pure Contextual Features (M1)
    m1_features = [
        # Demographics (6)
        "mean_age", "median_age", "age_std", "age_missing_ratio", "female_ratio", "male_ratio",
        # Reporter Dynamics (2)
        "hp_reporter_ratio", "csm_reporter_ratio",
        # Polypharmacy (2)
        "monotherapy_ratio", "mean_concomitant_count",
        # Attribution (1)
        "secondary_suspect_ratio"
    ]

    # Quarantined Outcome Seriousness Features (5) - EXCLUDED from primary models
    quarantined_outcome_features = [
        "death_ratio", "life_threatening_ratio", "hospitalization_ratio",
        "disability_ratio", "serious_outcome_ratio"
    ]

    # Contingency Cell Counts (4)
    contingency_counts = ["a", "b", "c", "d"]

    # Disproportionality Metrics (5)
    disproportionality_metrics = ["prr", "prr_chi2", "ror", "ror_lower_95", "ror_upper_95"]

    # M2: Multimodal (M1 [11] + contingency [4] + disproportionality [5] = 20 features)
    m2_features = m1_features + contingency_counts + disproportionality_metrics

    # M2a: Count Ablation (M1 [11] + contingency [4] = 15 features)
    m2a_features = m1_features + contingency_counts

    # M2b: Disproportionality Ablation (M1 [11] + disproportionality [5] = 16 features)
    m2b_features = m1_features + disproportionality_metrics

    # Sensitivity Sets
    m1_sens_features = m1_features + quarantined_outcome_features  # 16 features
    m2_sens_features = m2_features + quarantined_outcome_features  # 25 features

    print(f"M1 Feature Count (Pure Contextual): {len(m1_features)}")
    print(f"M2 Feature Count (Multimodal): {len(m2_features)}")
    print(f"M2a Feature Count (Count Ablation): {len(m2a_features)}")
    print(f"M2b Feature Count (Disproportionality Ablation): {len(m2b_features)}")
    print(f"M1_sens Feature Count (M1 + Outcomes): {len(m1_sens_features)}")
    print(f"M2_sens Feature Count (M2 + Outcomes): {len(m2_sens_features)}")

    # Methodological verification checks
    for feat in quarantined_outcome_features:
        assert feat not in m1_features, f"Confounder leakage: {feat} in M1!"
        assert feat not in m2_features, f"Confounder leakage: {feat} in M2!"
        assert feat not in m2a_features, f"Confounder leakage: {feat} in M2a!"
        assert feat not in m2b_features, f"Confounder leakage: {feat} in M2b!"

    for feat in ["prr", "ror", "a", "b", "c", "d"]:
        assert feat not in m1_features, f"Disproportionality leakage: {feat} in M1!"
    for feat in ["prr", "ror", "prr_chi2", "ror_lower_95", "ror_upper_95"]:
        assert feat not in m2a_features, f"Disproportionality leakage: {feat} in M2a!"
    for feat in ["a", "b", "c", "d"]:
        assert feat not in m2b_features, f"Count leakage: {feat} in M2b!"

    for feat in ["omop_status", "omop_phenotype", "evidence_category"]:
        assert feat not in ma_aligned.columns, f"Benchmark label leakage: {feat} in Model A!"
        assert feat not in mb_aligned.columns, f"Benchmark label leakage: {feat} in Model B!"

    print("\n" + "=" * 70)
    print("STEP 6: PERSIST ALIGNED DATASETS AND FEATURE SCHEMA METADATA")
    print("=" * 70)

    # Save aligned feature matrices in primary dir
    ma_aligned.to_csv(ma_path, index=False)
    mb_aligned.to_csv(mb_path, index=False)
    cp_df.to_csv(cp_path, index=False)
    print(f"Updated {ma_path} (rows: {len(ma_aligned):,})")
    print(f"Updated {mb_path} (rows: {len(mb_aligned):,})")
    print(f"Updated {cp_path} (rows: {len(cp_df):,})")

    # Export formal feature schema metadata JSON
    schema_metadata = {
        "candidate_pair_universe": {
            "row_count": len(cp_df),
            "filter_condition": "a >= 2",
            "unique_pair_keys": len(valid_keys),
            "key_columns": key_cols
        },
        "model_specifications": {
            "M1": {
                "name": "Pure Contextual Baseline",
                "feature_count": len(m1_features),
                "features": m1_features,
                "outcome_derived_quarantined": True,
                "disproportionality_free": True
            },
            "M2": {
                "name": "Multimodal Full Model",
                "feature_count": len(m2_features),
                "features": m2_features,
                "outcome_derived_quarantined": True
            },
            "M2a": {
                "name": "Count Ablation Model",
                "feature_count": len(m2a_features),
                "features": m2a_features,
                "disproportionality_metrics_excluded": True
            },
            "M2b": {
                "name": "Disproportionality Ablation Model",
                "feature_count": len(m2b_features),
                "features": m2b_features,
                "contingency_counts_excluded": True
            },
            "M1_sens": {
                "name": "M1 with Outcome Seriousness Sensitivity",
                "feature_count": len(m1_sens_features),
                "features": m1_sens_features
            },
            "M2_sens": {
                "name": "M2 with Outcome Seriousness Sensitivity",
                "feature_count": len(m2_sens_features),
                "features": m2_sens_features
            }
        },
        "quarantined_outcome_features": quarantined_outcome_features,
        "leakage_safeguards": {
            "benchmark_labels_in_features": False,
            "identifiers_used_as_features": False,
            "prr_ror_pseudo_labels_created": False,
            "unverifiable_pairs_unlabeled": True
        }
    }

    schema_path = os.path.join(primary_dir, "modelling_feature_specifications.json")
    with open(schema_path, "w") as f:
        json.dump(schema_metadata, f, indent=2)
    print(f"Saved feature specifications schema to: {schema_path}")

    print("\n" + "=" * 70)
    print("MODELLING DATASET PREPARATION COMPLETED SUCCESSFULLY")
    print("=" * 70)

if __name__ == "__main__":
    main()
