"""
Phase 3D.1 Independent Audit: Benchmark Implementation, Metrics, Mappings, and Provable False-Positive Reduction.
"""

import json
import os
import sys
import numpy as np
import pandas as pd
import scipy.stats as st

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

OMOP_PATH = os.path.join(PROJECT_ROOT, "data", "05_reference_standards", "omop", "omop_reference_set.csv")
EUADR_PATH = os.path.join(PROJECT_ROOT, "data", "05_reference_standards", "eu_adr", "eu_adr_reference_set.csv")
OMOP_MATCHED_CSV = os.path.join(PROJECT_ROOT, "data", "14_phase3d_benchmark_evaluation", "omop_matched_evaluation_pairs.csv")
EUADR_MATCHED_CSV = os.path.join(PROJECT_ROOT, "data", "14_phase3d_benchmark_evaluation", "eu_adr_matched_evaluation_pairs.csv")
RESULTS_JSON = os.path.join(PROJECT_ROOT, "data", "14_phase3d_benchmark_evaluation", "phase3d_benchmark_evaluation_results.json")

def average_precision_score(y_true: np.ndarray, scores: np.ndarray) -> float:
    """Standard non-interpolated Average Precision (AP) calculation."""
    y = np.asarray(y_true)
    s = np.asarray(scores)
    n_pos = np.sum(y == 1)
    if n_pos == 0:
        return 0.0
    order = np.argsort(-s)
    y_sorted = y[order]
    tp = np.cumsum(y_sorted)
    fp = np.cumsum(1 - y_sorted)
    prec = tp / (tp + fp)
    # Sum P(k) * [y_k == 1] / n_pos
    return float(np.sum(prec * y_sorted) / n_pos)

def trapezoidal_pr_auc(y_true: np.ndarray, scores: np.ndarray) -> float:
    """Trapezoidal PR-AUC with boundary prepending."""
    y = np.asarray(y_true)
    s = np.asarray(scores)
    n_pos = np.sum(y == 1)
    if n_pos == 0:
        return 0.0
    order = np.argsort(-s)
    y_sorted = y[order]
    tp = np.cumsum(y_sorted)
    fp = np.cumsum(1 - y_sorted)
    rec = tp / float(n_pos)
    prec = tp / (tp + fp)
    rec = np.concatenate([[0.0], rec])
    prec = np.concatenate([[1.0], prec])
    return float(np.trapezoid(prec, rec))

def roc_auc(y_true: np.ndarray, scores: np.ndarray) -> float:
    """Exact Mann-Whitney U calculation of ROC-AUC."""
    y = np.asarray(y_true)
    s = np.asarray(scores)
    n_pos = np.sum(y == 1)
    n_neg = np.sum(y == 0)
    if n_pos == 0 or n_neg == 0:
        return 0.5
    ranks = st.rankdata(s)
    u_stat = np.sum(ranks[y == 1]) - (n_pos * (n_pos + 1.0)) / 2.0
    return float(u_stat / (n_pos * n_neg))

def main():
    print("=" * 80)
    print("PHASE 3D.1 AUDIT: BENCHMARK IMPLEMENTATION & METRIC REPRODUCIBILITY")
    print("=" * 80)

    # 1. Audit Raw Reference Sets
    df_omop_raw = pd.read_csv(OMOP_PATH)
    df_euadr_raw = pd.read_csv(EUADR_PATH)
    print(f"\n1. Raw Reference Standard Inventories:")
    print(f"   OMOP:   {len(df_omop_raw)} rows (Pos: {sum(df_omop_raw['groundTruth']==1)}, Neg: {sum(df_omop_raw['groundTruth']==0)})")
    print(f"   EU-ADR: {len(df_euadr_raw)} rows (Pos: {sum(df_euadr_raw['groundTruth']==1)}, Neg: {sum(df_euadr_raw['groundTruth']==0)})")

    # Check duplicates in raw reference sets
    omop_dups = df_omop_raw.duplicated(subset=["exposureName", "outcomeName"]).sum()
    euadr_dups = df_euadr_raw.duplicated(subset=["exposureName", "outcomeName"]).sum()
    print(f"   OMOP internal duplicate (drug, outcome) pairs: {omop_dups}")
    print(f"   EU-ADR internal duplicate (drug, outcome) pairs: {euadr_dups}")

    # Check overlap between OMOP and EU-ADR
    omop_keys = set(df_omop_raw["exposureName"].str.lower().str.strip() + ":::" + df_omop_raw["outcomeName"])
    euadr_keys = set(df_euadr_raw["exposureName"].str.lower().str.strip() + ":::" + df_euadr_raw["outcomeName"])
    overlap_keys = omop_keys.intersection(euadr_keys)
    print(f"\n2. Overlap Between OMOP and EU-ADR:")
    print(f"   Shared (drug, outcome) pairs: {len(overlap_keys)}")

    # Check for label discordance on shared pairs
    m_omop = {row["exposureName"].lower().strip() + ":::" + row["outcomeName"]: row["groundTruth"] for _, row in df_omop_raw.iterrows()}
    m_euadr = {row["exposureName"].lower().strip() + ":::" + row["outcomeName"]: row["groundTruth"] for _, row in df_euadr_raw.iterrows()}
    discordant = []
    for k in overlap_keys:
        if m_omop[k] != m_euadr[k]:
            discordant.append((k, m_omop[k], m_euadr[k]))
    print(f"   Conflicting ground truth labels across shared pairs: {len(discordant)}")
    for d in discordant[:5]:
        print(f"     Conflict: {d[0]} -> OMOP={d[1]}, EU-ADR={d[2]}")

    # 3. Audit Matched Subsets
    df_omop_m = pd.read_csv(OMOP_MATCHED_CSV)
    df_euadr_m = pd.read_csv(EUADR_MATCHED_CSV)
    print(f"\n3. Matched Subsets Reconciliation:")
    print(f"   OMOP Matched:   {len(df_omop_m)} rows (Pos: {sum(df_omop_m['groundTruth']==1)}, Neg: {sum(df_omop_m['groundTruth']==0)})")
    print(f"   EU-ADR Matched: {len(df_euadr_m)} rows (Pos: {sum(df_euadr_m['groundTruth']==1)}, Neg: {sum(df_euadr_m['groundTruth']==0)})")

    # 4. Metric Comparison: Trapezoidal PR-AUC vs. Average Precision (AP)
    print("\n4. Metric Comparison: Trapezoidal PR-AUC vs. Discrete Average Precision (AP):")
    methods = [("EB05", "eb05"), ("EBGM", "ebgm"), ("PRR", "prr"), ("ROR", "ror")]

    print("\n   --- OMOP Reference Standard (N=203) ---")
    y_o = df_omop_m["groundTruth"].to_numpy()
    for name, col in methods:
        s = df_omop_m[col].to_numpy()
        pr_trap = trapezoidal_pr_auc(y_o, s)
        ap_val = average_precision_score(y_o, s)
        roc_val = roc_auc(y_o, s)
        print(f"   {name:6s}: Trapezoidal PR-AUC = {pr_trap:.4f} | Average Precision (AP) = {ap_val:.4f} | ROC-AUC = {roc_val:.4f}")

    print("\n   --- EU-ADR Reference Standard (N=66) ---")
    y_e = df_euadr_m["groundTruth"].to_numpy()
    for name, col in methods:
        s = df_euadr_m[col].to_numpy()
        pr_trap = trapezoidal_pr_auc(y_e, s)
        ap_val = average_precision_score(y_e, s)
        roc_val = roc_auc(y_e, s)
        print(f"   {name:6s}: Trapezoidal PR-AUC = {pr_trap:.4f} | Average Precision (AP) = {ap_val:.4f} | ROC-AUC = {roc_val:.4f}")

    # 5. False-Positive Reduction Claims Verification
    print("\n5. Auditing False-Positive Reduction Claims at Threshold 2.0 (OMOP Matched N=203):")
    eb05_thresh = df_omop_m["eb05"] >= 2.0
    prr_thresh = df_omop_m["prr"] >= 2.0

    eb05_tp = int(sum((eb05_thresh) & (y_o == 1)))
    eb05_fp = int(sum((eb05_thresh) & (y_o == 0)))
    eb05_tn = int(sum((~eb05_thresh) & (y_o == 0)))
    eb05_fn = int(sum((~eb05_thresh) & (y_o == 1)))

    prr_tp = int(sum((prr_thresh) & (y_o == 1)))
    prr_fp = int(sum((prr_thresh) & (y_o == 0)))
    prr_tn = int(sum((~prr_thresh) & (y_o == 0)))
    prr_fn = int(sum((~prr_thresh) & (y_o == 1)))

    eb05_spec = eb05_tn / (eb05_tn + eb05_fp)
    prr_spec = prr_tn / (prr_tn + prr_fp)
    fp_reduction = (prr_fp - eb05_fp) / prr_fp * 100

    print(f"   EB05 (>= 2.0): TP={eb05_tp}, FP={eb05_fp}, TN={eb05_tn}, FN={eb05_fn} | Specificity={eb05_spec*100:.1f}%")
    print(f"   PRR  (>= 2.0): TP={prr_tp}, FP={prr_fp}, TN={prr_tn}, FN={prr_fn} | Specificity={prr_spec*100:.1f}%")
    print(f"   False Positives: EB05 has {eb05_fp} vs. PRR {prr_fp} -> Reduction of {prr_fp - eb05_fp} FP flags ({fp_reduction:.1f}% relative reduction)")
    print(f"   Specificity Difference: +{(eb05_spec - prr_spec)*100:.1f} percentage points")

    # Statistical significance of specificity difference (McNemar test on negative controls)
    neg_mask = y_o == 0
    eb05_neg_call = eb05_thresh[neg_mask]
    prr_neg_call = prr_thresh[neg_mask]
    b = sum((~eb05_neg_call) & (prr_neg_call))  # Corrected by EB05 but missed by PRR
    c = sum((eb05_neg_call) & (~prr_neg_call))  # Corrected by PRR but missed by EB05
    print(f"   McNemar on Negative Controls: b (PRR FP, EB05 TN) = {b}, c (EB05 FP, PRR TN) = {c}")
    mcnemar_stat = (abs(b - c) - 1)**2 / (b + c) if (b + c) > 0 else 0
    mcnemar_p = 1 - st.chi2.cdf(mcnemar_stat, df=1)
    print(f"   McNemar Chi2 = {mcnemar_stat:.4f}, p-value = {mcnemar_p:.4e}")

if __name__ == "__main__":
    main()
