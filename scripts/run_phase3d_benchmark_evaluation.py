"""
Phase 3D — External Benchmark Evaluation and Fit-Robustness Assessment.

Parts:
- Part A: Freeze & verify primary Phase 3C.2 scoring artifact (SHA-256: 79d07631...).
- Part B: Audit & map independent reference standards (OMOP and EU-ADR).
- Part C: Candidate-universe coverage & selection bias auditing.
- Part D: Primary evaluation (PR-AUC, ROC-AUC, P@K, R@K, Sens/Spec, 95% Bootstrap CIs, PRR/ROR comparators).
- Part E: Fit-robustness sensitivity analysis on alpha1 lower optimization bound.
- Part F: Serialization of evaluation metrics and manifests to data/14_phase3d_benchmark_evaluation/.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from typing import Any, Dict, List, Tuple

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import numpy as np
import pandas as pd
import scipy.optimize as opt
import scipy.stats as st

def roc_auc_score(y_true: np.ndarray, scores: np.ndarray) -> float:
    """Exact Mann-Whitney U calculation of ROC-AUC with tie handling."""
    y = np.asarray(y_true)
    s = np.asarray(scores)
    n_pos = np.sum(y == 1)
    n_neg = np.sum(y == 0)
    if n_pos == 0 or n_neg == 0:
        return 0.5
    ranks = st.rankdata(s)
    u_stat = np.sum(ranks[y == 1]) - (n_pos * (n_pos + 1.0)) / 2.0
    return float(u_stat / (n_pos * n_neg))

def precision_recall_curve(y_true: np.ndarray, scores: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Calculate precision-recall curve using sorted thresholds."""
    y = np.asarray(y_true)
    s = np.asarray(scores)
    n_pos = np.sum(y == 1)
    if n_pos == 0:
        return np.array([0.0]), np.array([0.0]), np.array([0.0])
    order = np.argsort(-s)
    y_sorted = y[order]
    tp = np.cumsum(y_sorted)
    fp = np.cumsum(1 - y_sorted)
    rec = tp / float(n_pos)
    prec = tp / (tp + fp)
    # Prepend boundary point (rec=0, prec=1)
    rec = np.concatenate([[0.0], rec])
    prec = np.concatenate([[1.0], prec])
    return prec, rec, s[order]

def auc(x: np.ndarray, y: np.ndarray) -> float:
    """Trapezoidal integration for AUC."""
    return float(np.trapezoid(y, x))

from src.signal_detection.ebgm_engine import EBGMEngine, MGPSHyperparameters

# -----------------------------------------------------------------------------
# File Paths and Constants
# -----------------------------------------------------------------------------
SCORED_CSV = os.path.join(PROJECT_ROOT, "data", "13_phase3c2_mgps_scoring", "phase3c2_scored_candidate_pairs.csv")
FIT_CHECKPOINT_FILE = os.path.join(PROJECT_ROOT, "data", "13_phase3c2_mgps_scoring", "fit_checkpoint.json")
MANIFEST_3C2 = os.path.join(PROJECT_ROOT, "data", "13_phase3c2_mgps_scoring", "phase3c2_manifest.json")
CANDIDATE_SUMMARY_CSV = os.path.join(PROJECT_ROOT, "data", "10_phase3b_features", "candidate_pairs_summary.csv")

OMOP_PATH = os.path.join(PROJECT_ROOT, "data", "05_reference_standards", "omop", "omop_reference_set.csv")
EUADR_PATH = os.path.join(PROJECT_ROOT, "data", "05_reference_standards", "eu_adr", "eu_adr_reference_set.csv")

OUTPUT_DIR = os.path.join(PROJECT_ROOT, "data", "14_phase3d_benchmark_evaluation")
EVAL_RESULTS_JSON = os.path.join(OUTPUT_DIR, "phase3d_benchmark_evaluation_results.json")
SENSITIVITY_JSON = os.path.join(OUTPUT_DIR, "phase3d_sensitivity_analysis.json")
MANIFEST_3D = os.path.join(OUTPUT_DIR, "phase3d_manifest.json")

EXPECTED_SCORED_SHA256 = "79d07631e65fef8a84cd14e3368c3ca379ec59f66088d3a5824d9dbf6ada5758"
EXPECTED_ROW_COUNT = 1167891
TOTAL_COHORT_N = 6005839

# Clinical mappings
OMOP_HOI_MAPPINGS = {
    "OMOP Acute Liver Failure 1": [
        "Acute hepatic failure", "Hepatic failure", "Subacute hepatic failure", "Hepatotoxicity"
    ],
    "OMOP Acute myocardial Infarction  1": [
        "Myocardial infarction", "Acute myocardial infarction"
    ],
    "OMOP Acute Renal Failure 1": [
        "Acute kidney injury", "Renal failure acute", "Renal failure"
    ],
    "HOI Upper GI #3": [
        "Upper gastrointestinal haemorrhage", "Gastrointestinal haemorrhage", "Gastric haemorrhage", "Gastric ulcer haemorrhage"
    ]
}

EUADR_HOI_MAPPINGS = {
    "OMOP Acute Liver Failure 1": [
        "Acute hepatic failure", "Hepatic failure", "Hepatotoxicity"
    ],
    "OMOP Acute myocardial Infarction  1": [
        "Myocardial infarction", "Acute myocardial infarction"
    ],
    "OMOP Acute Renal Failure 1": [
        "Acute kidney injury", "Renal failure acute", "Renal failure"
    ],
    "HOI Upper GI #3": [
        "Upper gastrointestinal haemorrhage", "Gastrointestinal haemorrhage", "Gastric ulcer haemorrhage"
    ],
    "Anaphylaxis #1": [
        "Anaphylactic reaction", "Anaphylactic shock"
    ],
    "Cardiac Valve Fibrosis #1": [
        "Cardiac valve disease", "Heart valve incompetence", "Cardiac fibrosis"
    ],
    "Leukopenia Including Neutropenia and Agranulocytosis": [
        "Neutropenia", "Agranulocytosis", "Leukopenia", "Granulocytopenia"
    ],
    "OMOP Aplastic Anemia 1": [
        "Aplastic anaemia"
    ],
    "Rhabdomyolysis #1": [
        "Rhabdomyolysis"
    ],
    "Stevens-Johnson Syndrome #1": [
        "Stevens-Johnson syndrome", "Toxic epidermal necrolysis"
    ]
}


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while chunk := fh.read(8 * 1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def normalize_drug(name: str) -> str:
    s = str(name).strip().lower()
    for salt in [
        ", conjugated (usp)", " sodium", " potassium", " calcium",
        " hydrochloride", " hcl", " mesylate", " maleate",
        " tartrate", " succinate", " sulfate", " acetate", " phosphate"
    ]:
        if s.endswith(salt):
            s = s[:-len(salt)].strip()
    return s


# -----------------------------------------------------------------------------
# Part A: Freeze & Verify Primary Artifact
# -----------------------------------------------------------------------------
def run_part_a() -> Dict[str, Any]:
    print("\n" + "=" * 80)
    print("PART A: FREEZE AND VERIFY PRIMARY SCORING ARTIFACT")
    print("=" * 80)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"1. Verifying scored table exists: {SCORED_CSV} ...")
    if not os.path.exists(SCORED_CSV):
        raise FileNotFoundError(f"Primary scored table missing: {SCORED_CSV}")

    t0 = time.time()
    h = sha256_file(SCORED_CSV)
    print(f"   SHA-256: {h} (Computed in {time.time()-t0:.2f}s)")
    if h != EXPECTED_SCORED_SHA256:
        raise ValueError(f"Scored table hash mismatch! Expected {EXPECTED_SCORED_SHA256}, got {h}")

    print(f"2. Verifying fit checkpoint: {FIT_CHECKPOINT_FILE} ...")
    with open(FIT_CHECKPOINT_FILE, "r", encoding="utf-8") as fp:
        fit_data = json.load(fp)

    hypers = fit_data["hyperparameters_dict"]
    print(f"   Primary Model Hyperparameters:")
    print(f"     alpha1 = {hypers['alpha1']:.6f}, beta1 = {hypers['beta1']:.6f} -> Mean1 = {hypers['mean_comp1']:.4f}")
    print(f"     alpha2 = {hypers['alpha2']:.6f}, beta2 = {hypers['beta2']:.6f} -> Mean2 = {hypers['mean_comp2']:.4f}")
    print(f"     w = {hypers['w']:.6f} (Comp 1: {hypers['w']*100:.2f}%, Comp 2: {(1-hypers['w'])*100:.2f}%)")
    print(f"     Log-Likelihood: {fit_data['log_likelihood']:.4f}")
    print(f"     Hessian SEs: {fit_data['standard_errors']}")

    part_a_meta = {
        "status": "PASS",
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "scored_table_sha256": h,
        "scored_table_path": SCORED_CSV,
        "scored_table_size_bytes": os.path.getsize(SCORED_CSV),
        "primary_hyperparameters": hypers,
        "fit_log_likelihood": fit_data["log_likelihood"],
        "fit_standard_errors": fit_data["standard_errors"],
    }
    return part_a_meta


# -----------------------------------------------------------------------------
# Parts B & C: Audit Reference Standards & Map Universe Coverage
# -----------------------------------------------------------------------------
def run_parts_b_and_c(df_faers: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, Any]]:
    print("\n" + "=" * 80)
    print("PARTS B & C: REFERENCE STANDARDS AUDIT & UNIVERSE COVERAGE MAPPING")
    print("=" * 80)

    # 1. Audit Reference Sets
    df_omop_raw = pd.read_csv(OMOP_PATH)
    df_euadr_raw = pd.read_csv(EUADR_PATH)
    print(f"1. OMOP Reference Standard: {len(df_omop_raw)} pairs ({sum(df_omop_raw['groundTruth']==1)} positive, {sum(df_omop_raw['groundTruth']==0)} negative)")
    print(f"2. EU-ADR Reference Standard: {len(df_euadr_raw)} pairs ({sum(df_euadr_raw['groundTruth']==1)} positive, {sum(df_euadr_raw['groundTruth']==0)} negative)")

    # Index FAERS pairs by (normalized_drug, normalized_pt)
    print("Indexing 1,167,891 FAERS pairs for deterministic O(1) matching...")
    t0 = time.time()
    drugs_arr = df_faers["canonical_drug"].to_numpy()
    pts_arr = df_faers["canonical_pt"].to_numpy()
    ebgm_arr = df_faers["ebgm"].to_numpy()
    eb05_arr = df_faers["eb05"].to_numpy()
    eb95_arr = df_faers["eb95"].to_numpy()
    prr_arr = df_faers["prr"].to_numpy()
    ror_arr = df_faers["ror"].to_numpy()
    a_arr = df_faers["a"].to_numpy()
    e_arr = df_faers["e_expected"].to_numpy()

    faers_map: Dict[Tuple[str, str], int] = {}
    for i in range(len(df_faers)):
        k = (str(drugs_arr[i]).strip().lower(), str(pts_arr[i]).strip())
        faers_map[k] = i
    print(f"Index built in {time.time() - t0:.2f}s.")

    def match_benchmark(df_bench: pd.DataFrame, hoi_mappings: Dict[str, List[str]], benchmark_name: str) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        matched_records = []
        unmatched_records = []

        for _, row in df_bench.iterrows():
            d_orig = row["exposureName"]
            d_norm = str(d_orig).strip().lower()
            d_clean = normalize_drug(d_orig)
            hoi = row["outcomeName"]
            label = int(row["groundTruth"])
            target_pts = hoi_mappings.get(hoi, [])

            best_idx = None
            best_pt = None
            max_eb05 = -1.0

            for d_candidate in [d_norm, d_clean]:
                for pt in target_pts:
                    key = (d_candidate, pt)
                    if key in faers_map:
                        idx = faers_map[key]
                        c_eb05 = eb05_arr[idx]
                        if c_eb05 > max_eb05:
                            max_eb05 = c_eb05
                            best_idx = idx
                            best_pt = pt

            if best_idx is not None:
                matched_records.append({
                    "exposureId": row.get("exposureId", None),
                    "exposureName": d_orig,
                    "outcomeId": row.get("outcomeId", None),
                    "outcomeName": hoi,
                    "groundTruth": label,
                    "matched_pt": best_pt,
                    "a": a_arr[best_idx],
                    "e_expected": e_arr[best_idx],
                    "ebgm": ebgm_arr[best_idx],
                    "eb05": eb05_arr[best_idx],
                    "eb95": eb95_arr[best_idx],
                    "prr": prr_arr[best_idx],
                    "ror": ror_arr[best_idx],
                })
            else:
                unmatched_records.append({
                    "exposureId": row.get("exposureId", None),
                    "exposureName": d_orig,
                    "outcomeId": row.get("outcomeId", None),
                    "outcomeName": hoi,
                    "groundTruth": label,
                    "status": "UNMATCHED_A_LT_2_OR_UNOBSERVED"
                })

        df_matched = pd.DataFrame(matched_records)
        df_unmatched = pd.DataFrame(unmatched_records)

        total_n = len(df_bench)
        matched_n = len(df_matched)
        unmatched_n = len(df_unmatched)

        pos_total = int(sum(df_bench["groundTruth"] == 1))
        neg_total = int(sum(df_bench["groundTruth"] == 0))

        pos_matched = int(sum(df_matched["groundTruth"] == 1)) if matched_n > 0 else 0
        neg_matched = int(sum(df_matched["groundTruth"] == 0)) if matched_n > 0 else 0

        pos_unmatched = int(sum(df_unmatched["groundTruth"] == 1)) if unmatched_n > 0 else 0
        neg_unmatched = int(sum(df_unmatched["groundTruth"] == 0)) if unmatched_n > 0 else 0

        cov_overall = (matched_n / total_n) * 100
        cov_pos = (pos_matched / pos_total) * 100 if pos_total > 0 else 0
        cov_neg = (neg_matched / neg_total) * 100 if neg_total > 0 else 0

        print(f"\n[{benchmark_name} Coverage Summary]")
        print(f"  Total Reference Pairs: {total_n} (Positives: {pos_total}, Negatives: {neg_total})")
        print(f"  Matched in FAERS (a >= 2): {matched_n} ({cov_overall:.1f}%) | Positives: {pos_matched} ({cov_pos:.1f}%), Negatives: {neg_matched} ({cov_neg:.1f}%)")
        print(f"  Unmatched in FAERS (a < 2): {unmatched_n} ({100-cov_overall:.1f}%) | Positives: {pos_unmatched}, Negatives: {neg_unmatched}")
        print(f"  Effective Matched Prevalence: {pos_matched / matched_n * 100:.1f}% (vs. Original: {pos_total / total_n * 100:.1f}%)")

        cov_stats = {
            "total_reference_pairs": total_n,
            "total_positives": pos_total,
            "total_negatives": neg_total,
            "matched_pairs": matched_n,
            "matched_positives": pos_matched,
            "matched_negatives": neg_matched,
            "unmatched_pairs": unmatched_n,
            "unmatched_positives": pos_unmatched,
            "unmatched_negatives": neg_unmatched,
            "coverage_overall_pct": cov_overall,
            "coverage_positive_pct": cov_pos,
            "coverage_negative_pct": cov_neg,
            "original_prevalence_pct": pos_total / total_n * 100,
            "matched_prevalence_pct": pos_matched / matched_n * 100,
        }
        return df_matched, cov_stats

    df_omop_matched, omop_cov = match_benchmark(df_omop_raw, OMOP_HOI_MAPPINGS, "OMOP Reference Standard")
    df_euadr_matched, euadr_cov = match_benchmark(df_euadr_raw, EUADR_HOI_MAPPINGS, "EU-ADR Reference Standard")

    coverage_summary = {
        "omop": omop_cov,
        "euadr": euadr_cov,
    }
    return df_omop_matched, df_euadr_matched, coverage_summary


# -----------------------------------------------------------------------------
# Part D: Primary Evaluation & Statistical Bootstrapping
# -----------------------------------------------------------------------------
def compute_metrics_with_bootstrap(
    y_true: np.ndarray,
    scores: np.ndarray,
    method_name: str,
    k_values: List[int],
    eb05_thresholds: List[float] = [1.0, 2.0],
    n_boot: int = 1000,
    seed: int = 42,
) -> Dict[str, Any]:
    """Compute PR-AUC, ROC-AUC, P@K, R@K, Sens/Spec, and 95% bootstrap CIs."""
    # Primary metrics point estimates
    prec, rec, _ = precision_recall_curve(y_true, scores)
    pr_auc_val = float(auc(rec, prec))
    roc_auc_val = float(roc_auc_score(y_true, scores))

    # P@K and R@K
    order = np.argsort(-scores)
    y_sorted = y_true[order]
    n_pos_total = int(np.sum(y_true))

    pk_dict = {}
    rk_dict = {}
    for k in k_values:
        if k <= len(y_true):
            top_k = y_sorted[:k]
            p_k = float(np.mean(top_k))
            r_k = float(np.sum(top_k) / n_pos_total) if n_pos_total > 0 else 0.0
            pk_dict[f"P@{k}"] = p_k
            rk_dict[f"R@{k}"] = r_k

    # Threshold metrics (if EB05)
    thresh_dict = {}
    for t in eb05_thresholds:
        preds = scores >= t
        tp = int(np.sum((preds == 1) & (y_true == 1)))
        fp = int(np.sum((preds == 1) & (y_true == 0)))
        tn = int(np.sum((preds == 0) & (y_true == 0)))
        fn = int(np.sum((preds == 0) & (y_true == 1)))

        sens = float(tp / (tp + fn)) if (tp + fn) > 0 else 0.0
        spec = float(tn / (tn + fp)) if (tn + fp) > 0 else 0.0
        ppv = float(tp / (tp + fp)) if (tp + fp) > 0 else 0.0
        thresh_dict[f"thresh_{t}"] = {
            "threshold": t,
            "tp": tp, "fp": fp, "tn": tn, "fn": fn,
            "sensitivity": sens,
            "specificity": spec,
            "ppv_precision": ppv,
        }

    # Bootstrap 95% Confidence Intervals
    rng = np.random.RandomState(seed)
    boot_pr_aucs = []
    boot_roc_aucs = []

    n_samples = len(y_true)
    for _ in range(n_boot):
        boot_idx = rng.choice(n_samples, size=n_samples, replace=True)
        b_true = y_true[boot_idx]
        b_scores = scores[boot_idx]

        if len(np.unique(b_true)) < 2:
            continue

        b_p, b_r, _ = precision_recall_curve(b_true, b_scores)
        boot_pr_aucs.append(auc(b_r, b_p))
        boot_roc_aucs.append(roc_auc_score(b_true, b_scores))

    pr_auc_ci = (float(np.percentile(boot_pr_aucs, 2.5)), float(np.percentile(boot_pr_aucs, 97.5)))
    roc_auc_ci = (float(np.percentile(boot_roc_aucs, 2.5)), float(np.percentile(boot_roc_aucs, 97.5)))

    return {
        "method": method_name,
        "n_evaluated": n_samples,
        "n_positives": n_pos_total,
        "n_negatives": int(n_samples - n_pos_total),
        "prevalence": float(n_pos_total / n_samples),
        "pr_auc": pr_auc_val,
        "pr_auc_95ci": pr_auc_ci,
        "roc_auc": roc_auc_val,
        "roc_auc_95ci": roc_auc_ci,
        "precision_at_k": pk_dict,
        "recall_at_k": rk_dict,
        "threshold_metrics": thresh_dict,
    }


def run_part_d(df_omop: pd.DataFrame, df_euadr: pd.DataFrame) -> Dict[str, Any]:
    print("\n" + "=" * 80)
    print("PART D: PRIMARY BENCHMARK EVALUATION & COMPARATOR ANALYSIS")
    print("=" * 80)

    results: Dict[str, Any] = {"omop": {}, "euadr": {}}

    # --- OMOP Evaluation ---
    print("\n1. Evaluating OMOP Reference Standard (Matched Subset, N=203)...")
    y_omop = df_omop["groundTruth"].to_numpy(dtype=np.int64)
    eb05_omop = df_omop["eb05"].to_numpy(dtype=np.float64)
    ebgm_omop = df_omop["ebgm"].to_numpy(dtype=np.float64)
    prr_omop = df_omop["prr"].to_numpy(dtype=np.float64)
    ror_omop = df_omop["ror"].to_numpy(dtype=np.float64)

    k_omop = [10, 25, 50, 100]
    res_omop_eb05 = compute_metrics_with_bootstrap(y_omop, eb05_omop, "EB05 (Primary)", k_omop, n_boot=1000, seed=42)
    res_omop_ebgm = compute_metrics_with_bootstrap(y_omop, ebgm_omop, "EBGM", k_omop, n_boot=1000, seed=42)
    res_omop_prr = compute_metrics_with_bootstrap(y_omop, prr_omop, "PRR (Comparator)", k_omop, n_boot=1000, seed=42)
    res_omop_ror = compute_metrics_with_bootstrap(y_omop, ror_omop, "ROR (Comparator)", k_omop, n_boot=1000, seed=42)

    results["omop"]["EB05"] = res_omop_eb05
    results["omop"]["EBGM"] = res_omop_ebgm
    results["omop"]["PRR"] = res_omop_prr
    results["omop"]["ROR"] = res_omop_ror

    print(f"  [OMOP] EB05  PR-AUC: {res_omop_eb05['pr_auc']:.4f} [95% CI: {res_omop_eb05['pr_auc_95ci'][0]:.4f}, {res_omop_eb05['pr_auc_95ci'][1]:.4f}] | ROC-AUC: {res_omop_eb05['roc_auc']:.4f}")
    print(f"  [OMOP] EBGM  PR-AUC: {res_omop_ebgm['pr_auc']:.4f} [95% CI: {res_omop_ebgm['pr_auc_95ci'][0]:.4f}, {res_omop_ebgm['pr_auc_95ci'][1]:.4f}] | ROC-AUC: {res_omop_ebgm['roc_auc']:.4f}")
    print(f"  [OMOP] PRR   PR-AUC: {res_omop_prr['pr_auc']:.4f} [95% CI: {res_omop_prr['pr_auc_95ci'][0]:.4f}, {res_omop_prr['pr_auc_95ci'][1]:.4f}] | ROC-AUC: {res_omop_prr['roc_auc']:.4f}")
    print(f"  [OMOP] ROR   PR-AUC: {res_omop_ror['pr_auc']:.4f} [95% CI: {res_omop_ror['pr_auc_95ci'][0]:.4f}, {res_omop_ror['pr_auc_95ci'][1]:.4f}] | ROC-AUC: {res_omop_ror['roc_auc']:.4f}")

    # --- EU-ADR Evaluation ---
    print("\n2. Evaluating EU-ADR Reference Standard (Matched Subset, N=66)...")
    y_euadr = df_euadr["groundTruth"].to_numpy(dtype=np.int64)
    eb05_euadr = df_euadr["eb05"].to_numpy(dtype=np.float64)
    ebgm_euadr = df_euadr["ebgm"].to_numpy(dtype=np.float64)
    prr_euadr = df_euadr["prr"].to_numpy(dtype=np.float64)
    ror_euadr = df_euadr["ror"].to_numpy(dtype=np.float64)

    k_euadr = [5, 10, 20, 30]
    res_euadr_eb05 = compute_metrics_with_bootstrap(y_euadr, eb05_euadr, "EB05 (Primary)", k_euadr, n_boot=1000, seed=42)
    res_euadr_ebgm = compute_metrics_with_bootstrap(y_euadr, ebgm_euadr, "EBGM", k_euadr, n_boot=1000, seed=42)
    res_euadr_prr = compute_metrics_with_bootstrap(y_euadr, prr_euadr, "PRR (Comparator)", k_euadr, n_boot=1000, seed=42)
    res_euadr_ror = compute_metrics_with_bootstrap(y_euadr, ror_euadr, "ROR (Comparator)", k_euadr, n_boot=1000, seed=42)

    results["euadr"]["EB05"] = res_euadr_eb05
    results["euadr"]["EBGM"] = res_euadr_ebgm
    results["euadr"]["PRR"] = res_euadr_prr
    results["euadr"]["ROR"] = res_euadr_ror

    print(f"  [EU-ADR] EB05  PR-AUC: {res_euadr_eb05['pr_auc']:.4f} [95% CI: {res_euadr_eb05['pr_auc_95ci'][0]:.4f}, {res_euadr_eb05['pr_auc_95ci'][1]:.4f}] | ROC-AUC: {res_euadr_eb05['roc_auc']:.4f}")
    print(f"  [EU-ADR] EBGM  PR-AUC: {res_euadr_ebgm['pr_auc']:.4f} [95% CI: {res_euadr_ebgm['pr_auc_95ci'][0]:.4f}, {res_euadr_ebgm['pr_auc_95ci'][1]:.4f}] | ROC-AUC: {res_euadr_ebgm['roc_auc']:.4f}")
    print(f"  [EU-ADR] PRR   PR-AUC: {res_euadr_prr['pr_auc']:.4f} [95% CI: {res_euadr_prr['pr_auc_95ci'][0]:.4f}, {res_euadr_prr['pr_auc_95ci'][1]:.4f}] | ROC-AUC: {res_euadr_prr['roc_auc']:.4f}")
    print(f"  [EU-ADR] ROR   PR-AUC: {res_euadr_ror['pr_auc']:.4f} [95% CI: {res_euadr_ror['pr_auc_95ci'][0]:.4f}, {res_euadr_ror['pr_auc_95ci'][1]:.4f}] | ROC-AUC: {res_euadr_ror['roc_auc']:.4f}")

    return results


# -----------------------------------------------------------------------------
# Part E: Fit-Robustness Sensitivity Analysis
# -----------------------------------------------------------------------------
def run_part_e() -> Dict[str, Any]:
    print("\n" + "=" * 80)
    print("PART E: INVESTIGATING BOUNDARY-FIT LIMITATION (SENSITIVITY ANALYSIS)")
    print("=" * 80)

    print("Loading candidate summary for sensitivity fitting...")
    df_raw = pd.read_csv(CANDIDATE_SUMMARY_CSV)
    a = df_raw["a"].to_numpy(dtype=np.float64)
    b = df_raw["b"].to_numpy(dtype=np.float64)
    c = df_raw["c"].to_numpy(dtype=np.float64)
    e = (a + b) * (a + c) / float(TOTAL_COHORT_N)

    engine = EBGMEngine(seed=42)
    n_bin, e_bin, w_bin = engine.squash_counts_2d(a, e, decimals=2, use_log=True)
    print(f"Compressed into {len(n_bin):,} logarithmic bins.")

    # Primary baseline: alpha1 >= 0.001
    with open(FIT_CHECKPOINT_FILE, "r", encoding="utf-8") as fp:
        primary_fit = json.load(fp)

    primary_hypers = primary_fit["hyperparameters_dict"]

    sensitivity_configs = [
        {"name": "sens_alpha1_ge_0_01", "alpha1_min": 0.01, "desc": "Tighter lower bound (alpha1 >= 0.01)"},
        {"name": "sens_alpha1_ge_0_05", "alpha1_min": 0.05, "desc": "openEBGM default bound (alpha1 >= 0.05)"},
        {"name": "sens_alpha1_ge_0_0001", "alpha1_min": 0.0001, "desc": "Ultra-relaxed bound (alpha1 >= 0.0001)"},
    ]

    sens_results = {
        "primary_fit": {
            "bounds": [0.001, 10.0],
            "hyperparameters": primary_hypers,
            "log_likelihood": primary_fit["log_likelihood"],
        },
        "alternative_fits": {},
    }

    initial_guess = (0.2339, 0.3354, 2.2487, 0.05, 0.99)

    for cfg in sensitivity_configs:
        name = cfg["name"]
        a1_min = cfg["alpha1_min"]
        print(f"\nEvaluating sensitivity: {cfg['desc']} ...")

        # Custom bounds
        bounds = [
            (a1_min, 10.0),   # alpha1
            (0.001, 100.0),  # beta1
            (0.05, 10.0),    # alpha2
            (0.05, 10.0),    # beta2
            (0.0001, 0.9999) # w
        ]

        t0 = time.time()
        res = opt.minimize(
            fun=engine.negative_log_likelihood,
            x0=initial_guess,
            args=(n_bin, e_bin, w_bin, 2),
            method="L-BFGS-B",
            bounds=bounds,
            options={"maxiter": 500, "ftol": 1e-9, "gtol": 1e-6},
        )
        t_fit = time.time() - t0

        if res.success:
            p = res.x
            hypers_alt = MGPSHyperparameters(alpha1=p[0], beta1=p[1], alpha2=p[2], beta2=p[3], w=p[4])
            log_lik = -res.fun
            delta_ll = log_lik - primary_fit["log_likelihood"]
            print(f"  Converged in {t_fit:.2f}s | Iterations: {res.nit}")
            print(f"  Hyperparameters: alpha1={hypers_alt.alpha1:.6f}, beta1={hypers_alt.beta1:.6f}, alpha2={hypers_alt.alpha2:.6f}, beta2={hypers_alt.beta2:.6f}, w={hypers_alt.w:.4f}")
            print(f"  Log-Likelihood: {log_lik:.4f} (Delta LL vs Primary: {delta_ll:.4f})")

            # Check rank correlation on a representative deterministic sample of 50,000 pairs
            sample_idx = np.linspace(0, len(a)-1, 50000, dtype=np.int64)
            sub_a = a[sample_idx]
            sub_e = e[sample_idx]

            theta_prim = MGPSHyperparameters.from_tuple(tuple(primary_fit["hyperparameters"]))
            ebgm_prim = engine.calculate_ebgm(sub_a, sub_e, theta_prim)
            ebgm_alt = engine.calculate_ebgm(sub_a, sub_e, hypers_alt)

            spearman_rho, _ = st.spearmanr(ebgm_prim, ebgm_alt)
            pearson_r, _ = st.pearsonr(ebgm_prim, ebgm_alt)
            print(f"  Correlation with Primary Scores (N=50,000): Spearman rho = {spearman_rho:.6f}, Pearson r = {pearson_r:.6f}")

            sens_results["alternative_fits"][name] = {
                "description": cfg["desc"],
                "alpha1_min_bound": a1_min,
                "converged": bool(res.success),
                "iterations": int(res.nit),
                "fit_time_seconds": t_fit,
                "hyperparameters": {
                    "alpha1": hypers_alt.alpha1,
                    "beta1": hypers_alt.beta1,
                    "alpha2": hypers_alt.alpha2,
                    "beta2": hypers_alt.beta2,
                    "w": hypers_alt.w,
                    "mean_comp1": hypers_alt.mean_component1(),
                    "mean_comp2": hypers_alt.mean_component2(),
                },
                "log_likelihood": float(log_lik),
                "delta_log_likelihood": float(delta_ll),
                "spearman_rank_correlation": float(spearman_rho),
                "pearson_correlation": float(pearson_r),
            }
        else:
            print(f"  Failed to converge: {res.message}")
            sens_results["alternative_fits"][name] = {
                "converged": False,
                "message": str(res.message)
            }

    with open(SENSITIVITY_JSON, "w", encoding="utf-8") as fp:
        json.dump(sens_results, fp, indent=2)

    print(f"\nSensitivity analysis saved to: {SENSITIVITY_JSON}")
    return sens_results


# -----------------------------------------------------------------------------
# Main Execution CLI
# -----------------------------------------------------------------------------
def main():
    print("=" * 80)
    print("PHASE 3D: EXTERNAL BENCHMARK EVALUATION & FIT-ROBUSTNESS ASSESSMENT")
    print("=" * 80)

    try:
        # Part A
        meta_a = run_part_a()

        # Load scored dataset for evaluation
        print(f"\nLoading master scored candidate table ({SCORED_CSV})...")
        t0 = time.time()
        df_faers = pd.read_csv(SCORED_CSV)
        print(f"Loaded {len(df_faers):,} rows in {time.time()-t0:.2f}s.")

        # Parts B & C
        df_omop_matched, df_euadr_matched, cov_summary = run_parts_b_and_c(df_faers)

        # Save matched tables
        omop_matched_csv = os.path.join(OUTPUT_DIR, "omop_matched_evaluation_pairs.csv")
        euadr_matched_csv = os.path.join(OUTPUT_DIR, "eu_adr_matched_evaluation_pairs.csv")
        df_omop_matched.to_csv(omop_matched_csv, index=False)
        df_euadr_matched.to_csv(euadr_matched_csv, index=False)
        print(f"\nSaved matched benchmark evaluation subsets:\n  - {omop_matched_csv}\n  - {euadr_matched_csv}")

        # Part D
        eval_metrics = run_part_d(df_omop_matched, df_euadr_matched)

        # Part E
        sens_results = run_part_e()

        # Part F: Aggregate results & save Manifest
        print("\n" + "=" * 80)
        print("PART F: AGGREGATE RESULTS & MANIFEST GENERATION")
        print("=" * 80)

        full_results = {
            "phase": "Phase 3D",
            "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "status": "EVALUATION_COMPLETE",
            "scored_dataset_metadata": meta_a,
            "coverage_summary": cov_summary,
            "benchmark_evaluation": eval_metrics,
            "sensitivity_analysis": sens_results,
        }

        with open(EVAL_RESULTS_JSON, "w", encoding="utf-8") as fp:
            json.dump(full_results, fp, indent=2)

        manifest = {
            "phase": "Phase 3D",
            "description": "External Benchmark Evaluation and Fit-Robustness Assessment Artifacts",
            "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "status": "COMPLETED_VERIFIED",
            "artifacts": {
                EVAL_RESULTS_JSON: {
                    "sha256": sha256_file(EVAL_RESULTS_JSON),
                    "size_bytes": os.path.getsize(EVAL_RESULTS_JSON),
                },
                SENSITIVITY_JSON: {
                    "sha256": sha256_file(SENSITIVITY_JSON),
                    "size_bytes": os.path.getsize(SENSITIVITY_JSON),
                },
                omop_matched_csv: {
                    "sha256": sha256_file(omop_matched_csv),
                    "size_bytes": os.path.getsize(omop_matched_csv),
                    "row_count": len(df_omop_matched),
                },
                euadr_matched_csv: {
                    "sha256": sha256_file(euadr_matched_csv),
                    "size_bytes": os.path.getsize(euadr_matched_csv),
                    "row_count": len(df_euadr_matched),
                },
            }
        }

        with open(MANIFEST_3D, "w", encoding="utf-8") as fp:
            json.dump(manifest, fp, indent=2)

        print(f"Results and Manifest successfully written to:\n  - {EVAL_RESULTS_JSON}\n  - {MANIFEST_3D}")
        print("\n" + "=" * 80)
        print("PHASE 3D PIPELINE EXECUTION SUCCESSFUL")
        print("=" * 80)
        return 0

    except Exception as exc:
        print(f"\n[PIPELINE FAILURE] Phase 3D failed: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
