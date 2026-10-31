"""
Comprehensive Independent Feature Alignment and Leakage Audit Script.
Validates the aligned datasets and asserts all methodological invariants.
"""

import os
import sys
import json
import pandas as pd
import numpy as np

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

def main():
    print("=" * 70)
    print("INDEPENDENT FEATURE ALIGNMENT & LEAKAGE AUDIT")
    print("=" * 70)

    base_dir = os.path.join(PROJECT_ROOT, "data", "03_primary")
    cp_path = os.path.join(base_dir, "phase2_candidate_pairs_summary.csv")
    ma_path = os.path.join(base_dir, "phase2_model_a_features.csv")
    mb_path = os.path.join(base_dir, "phase2_model_b_features.csv")
    spec_path = os.path.join(base_dir, "modelling_feature_specifications.json")

    # 1. Load schema specification
    with open(spec_path, "r") as f:
        specs = json.load(f)
    print("Loaded feature specifications successfully.")

    # 2. Load datasets
    print("Loading datasets...")
    cp_df = pd.read_csv(cp_path)
    ma_df = pd.read_csv(ma_path)
    mb_df = pd.read_csv(mb_path)

    n_cp = len(cp_df)
    n_ma = len(ma_df)
    n_mb = len(mb_df)

    print(f"\nRow Counts:")
    print(f"  Candidate Pairs: {n_cp:,}")
    print(f"  Model A Features: {n_ma:,}")
    print(f"  Model B Features: {n_mb:,}")

    # Check 1: Identical Row Counts
    assert n_cp == 519748, f"Candidate pairs count expected 519,748, got {n_cp}"
    assert n_ma == 519748, f"Model A count expected 519,748, got {n_ma}"
    assert n_mb == 519748, f"Model B count expected 519,748, got {n_mb}"
    print(" Check 1: Row count consistency across all datasets PASSED.")

    # Check 2: 1-to-1 Identical Key Alignment
    cp_keys = list(zip(cp_df["canonical_drug"], cp_df["canonical_pt"]))
    ma_keys = list(zip(ma_df["canonical_drug"], ma_df["canonical_pt"]))
    mb_keys = list(zip(mb_df["canonical_drug"], mb_df["canonical_pt"]))

    assert cp_keys == ma_keys, "Key mismatch between Candidate Pairs and Model A!"
    assert cp_keys == mb_keys, "Key mismatch between Candidate Pairs and Model B!"
    print(f" Check 2: Exact row-for-row key alignment ({len(cp_keys):,} pairs) PASSED.")

    # Check 3: Zero Disproportionality Missingness in Aligned Universe
    disprop_cols = ["a", "b", "c", "d", "prr", "prr_chi2", "ror", "ror_lower_95", "ror_upper_95"]
    missing_disprop = mb_df[disprop_cols].isna().sum().sum()
    assert missing_disprop == 0, f"Disproportionality metrics contain {missing_disprop} missing values!"
    print(" Check 3: Disproportionality NaN check in Model B PASSED (0 missing).")

    # Check 4: Outcome Confounder Quarantine
    quarantined = specs["quarantined_outcome_features"]
    m1_cols = specs["model_specifications"]["M1"]["features"]
    m2_cols = specs["model_specifications"]["M2"]["features"]
    m2a_cols = specs["model_specifications"]["M2a"]["features"]
    m2b_cols = specs["model_specifications"]["M2b"]["features"]

    for q in quarantined:
        assert q not in m1_cols, f"Leakage: Quarantined feature {q} in M1!"
        assert q not in m2_cols, f"Leakage: Quarantined feature {q} in M2!"
        assert q not in m2a_cols, f"Leakage: Quarantined feature {q} in M2a!"
        assert q not in m2b_cols, f"Leakage: Quarantined feature {q} in M2b!"
    print(f" Check 4: Outcome seriousness quarantine PASSED ({len(quarantined)} features quarantined).")

    # Check 5: Anti-Circularity & Disproportionality Isolation
    for d in ["a", "b", "c", "d", "prr", "ror", "prr_chi2", "ror_lower_95", "ror_upper_95"]:
        assert d not in m1_cols, f"Circularity leakage: Disproportionality feature {d} in M1!"
    for d in ["prr", "prr_chi2", "ror", "ror_lower_95", "ror_upper_95"]:
        assert d not in m2a_cols, f"Circularity leakage: Disproportionality metric {d} in M2a!"
    for d in ["a", "b", "c", "d"]:
        assert d not in m2b_cols, f"Count leakage: Contingency cell count {d} in M2b!"
    print(" Check 5: Model feature tier isolation (M1, M2a, M2b) PASSED.")

    # Check 6: Benchmark Label Firewall
    for b in ["omop_phenotype", "omop_status", "evidence_category"]:
        assert b not in ma_df.columns, f"Benchmark leakage: {b} in Model A!"
        assert b not in mb_df.columns, f"Benchmark leakage: {b} in Model B!"
    print(" Check 6: External reference benchmark firewall PASSED (Zero benchmark labels in feature matrices).")

    # Check 7: Feature Dimensionalities
    print(f"\nFeature Matrix Dimensionalities:")
    print(f"  M1 (Pure Contextual): {len(m1_cols)} features")
    print(f"  M2 (Multimodal): {len(m2_cols)} features")
    print(f"  M2a (Count Ablation): {len(m2a_cols)} features")
    print(f"  M2b (Disproportionality Ablation): {len(m2b_cols)} features")
    print(f"  M1_sens (Sensitivity): {len(specs['model_specifications']['M1_sens']['features'])} features")
    print(f"  M2_sens (Sensitivity): {len(specs['model_specifications']['M2_sens']['features'])} features")
    assert len(m1_cols) == 11
    assert len(m2_cols) == 20
    assert len(m2a_cols) == 15
    assert len(m2b_cols) == 16
    assert len(specs['model_specifications']['M1_sens']['features']) == 16
    assert len(specs['model_specifications']['M2_sens']['features']) == 25
    print(" Check 7: All feature counts exactly match locked specifications PASSED.")

    print("\n" + "=" * 70)
    print("ALL AUDIT CHECKS PASSED WITH ZERO VIOLATIONS.")
    print("=" * 70)

if __name__ == "__main__":
    main()
