"""
Phase 3C.1 — Controlled Small-Scale EBGM/MGPS Pilot Execution Script.

Strict Boundaries:
- Operates on a deterministic, label-blind sample (M = 25,000) from candidate_pairs_summary.csv.
- Zero benchmark labels (OMOP/EU-ADR) used for sampling, fitting, or tuning.
- Preserves all Phase 3A snapshots and Phase 3B feature matrices untouched.
- Compares EBGM/EB05 with existing PRR/ROR descriptively.
- Produces versioned outputs and diagnostic metrics in data/12_phase3c_pilot/.
"""

from __future__ import annotations

import json
import math
import os
import sys
import time
from typing import Any, Dict, List, Tuple

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import numpy as np
import pandas as pd
import scipy.stats as st

from src.signal_detection.ebgm_engine import (
    EBGMEngine,
    MGPSHyperparameters,
    OptimizationResult,
)

TOTAL_COHORT_N = 6005839  # Strict AS_OF_2018 universe count from Phase 3A.2/3B
PILOT_SAMPLE_SIZE = 25000
RANDOM_SEED = 42

INPUT_PAIRS_CSV = os.path.join(PROJECT_ROOT, "data", "10_phase3b_features", "candidate_pairs_summary.csv")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "data", "12_phase3c_pilot")


def sample_deterministic_universe(
    df: pd.DataFrame, sample_size: int = PILOT_SAMPLE_SIZE, seed: int = RANDOM_SEED
) -> pd.DataFrame:
    """
    Select a deterministic, label-blind sample of candidate pairs spanning all count strata:
    - a = 2
    - a = 3
    - a in [4, 5]
    - a in [6, 10]
    - a > 10
    Uses fixed seed, zero external labels or outcome knowledge.
    """
    conditions = [
        df["a"] == 2,
        df["a"] == 3,
        df["a"].between(4, 5),
        df["a"].between(6, 10),
        df["a"] > 10,
    ]
    strata_names = ["a=2", "a=3", "a=4-5", "a=6-10", "a>10"]

    # Proportional sampling across strata with deterministic seed
    sampled_subsets = []
    strata_counts = [int(cond.sum()) for cond in conditions]
    total_available = len(df)

    rng = np.random.RandomState(seed)

    for cond, name, count in zip(conditions, strata_names, strata_counts):
        stratum_df = df[cond]
        # Target proportion matches universe proportion
        target_n = max(100, int(round(sample_size * (count / total_available))))
        target_n = min(target_n, len(stratum_df))
        sampled = stratum_df.sample(n=target_n, random_state=rng)
        sampled["stratum"] = name
        sampled_subsets.append(sampled)

    combined = pd.concat(sampled_subsets, ignore_index=True)
    # If slight rounding difference, adjust deterministically to exact sample_size
    if len(combined) > sample_size:
        combined = combined.sample(n=sample_size, random_state=rng).sort_values(by=["canonical_drug", "canonical_pt"])
    elif len(combined) < sample_size:
        rem = sample_size - len(combined)
        remaining_df = df[~df.index.isin(combined.index)]
        fill = remaining_df.sample(n=rem, random_state=rng)
        fill["stratum"] = "fill"
        combined = pd.concat([combined, fill], ignore_index=True).sort_values(by=["canonical_drug", "canonical_pt"])

    return combined.reset_index(drop=True)


def run_pilot() -> Dict[str, Any]:
    print("=" * 80)
    print("PHASE 3C.1 — CONTROLLED EBGM/MGPS SMALL-SCALE PILOT EXECUTION")
    print("=" * 80)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"Loading candidate pairs from: {INPUT_PAIRS_CSV}...")
    t0 = time.time()
    # Read only needed columns to be fast and memory-efficient
    cols_to_read = [
        "canonical_drug", "canonical_pt", "a", "b", "c", "d",
        "prr", "prr_chi2", "prr_signal", "ror", "ror_se", "ror_lower_95", "ror_upper_95", "ror_signal"
    ]
    pairs_df = pd.read_csv(INPUT_PAIRS_CSV, usecols=cols_to_read)
    load_time = time.time() - t0
    print(f"Loaded {len(pairs_df):,} total pairs in {load_time:.2f}s.")

    # 1. Deterministic Sampling
    print(f"\nDrawing deterministic sample of {PILOT_SAMPLE_SIZE:,} pairs (seed={RANDOM_SEED})...")
    sample_df = sample_deterministic_universe(pairs_df, sample_size=PILOT_SAMPLE_SIZE, seed=RANDOM_SEED)
    print(f"Sample drawn: {len(sample_df):,} pairs across count strata:")
    print(sample_df["stratum"].value_counts().to_string())

    # 2. Expected Count Calculation
    engine = EBGMEngine(seed=RANDOM_SEED)
    print(f"\nComputing exact expected counts E under independence (N = {TOTAL_COHORT_N:,})...")
    sample_df["e_expected"] = engine.calculate_expected_counts(
        sample_df["a"].to_numpy(),
        sample_df["b"].to_numpy(),
        sample_df["c"].to_numpy(),
        total_n=TOTAL_COHORT_N,
    )
    sample_df["crude_rr"] = sample_df["a"] / sample_df["e_expected"]
    print(f"Expected counts computed. Min E: {sample_df['e_expected'].min():.6f}, Max E: {sample_df['e_expected'].max():.2f}")

    # 3. Model Fitting on Pilot Sample (Exact vs 2D-Binned Comparison)
    print("\nFitting EBGM mixture prior on pilot sample...")

    # Unbinned exact fit
    t_fit_start = time.time()
    fit_exact = engine.fit(
        n=sample_df["a"].to_numpy(),
        e=sample_df["e_expected"].to_numpy(),
        compute_se=True,
    )
    t_fit_exact = time.time() - t_fit_start
    print(f"Exact unbinned fit finished in {t_fit_exact:.2f}s (Converged: {fit_exact.converged}, Iterations: {fit_exact.iterations}).")
    if fit_exact.hyperparameters:
        h = fit_exact.hyperparameters
        print(f"  Estimates: alpha1={h.alpha1:.4f}, beta1={h.beta1:.4f}, alpha2={h.alpha2:.4f}, beta2={h.beta2:.4f}, w={h.w:.4f}")
        print(f"  Prior means: Component 1 = {h.mean_component1():.4f}, Component 2 = {h.mean_component2():.4f}")
        print(f"  Log-likelihood: {fit_exact.log_likelihood:.2f}")

    # 2D-binned fit benchmark
    t_squash_start = time.time()
    n_sq, e_sq, w_sq = engine.squash_counts_2d(
        sample_df["a"].to_numpy(),
        sample_df["e_expected"].to_numpy(),
        decimals=2,
    )
    t_squash = time.time() - t_squash_start
    print(f"\n2D Count Binning: collapsed {len(sample_df):,} pairs into {len(n_sq):,} unique bins in {t_squash:.3f}s (compression ratio: {len(sample_df)/len(n_sq):.1f}x).")

    t_fit_binned_start = time.time()
    fit_binned = engine.fit(
        n=n_sq,
        e=e_sq,
        weights=w_sq,
        compute_se=True,
    )
    t_fit_binned = time.time() - t_fit_binned_start
    print(f"Binned fit finished in {t_fit_binned:.2f}s (Converged: {fit_binned.converged}, Iterations: {fit_binned.iterations}).")
    if fit_binned.hyperparameters:
        hb = fit_binned.hyperparameters
        print(f"  Estimates: alpha1={hb.alpha1:.4f}, beta1={hb.beta1:.4f}, alpha2={hb.alpha2:.4f}, beta2={hb.beta2:.4f}, w={hb.w:.4f}")
        print(f"  Log-likelihood (binned): {fit_binned.log_likelihood:.2f}")

    # Use exact fit for pilot scoring
    best_hypers = fit_exact.hyperparameters if fit_exact.converged and fit_exact.hyperparameters else fit_binned.hyperparameters
    assert best_hypers is not None, "Model fitting failed to converge!"

    # 4. Score Pilot Sample
    print(f"\nCalculating posterior EBGM, EB05, EB95 across {len(sample_df):,} pairs...")
    t_score_start = time.time()
    scored_df = engine.score_candidate_pairs(sample_df, best_hypers, n_col="a", e_col="e_expected")
    t_score = time.time() - t_score_start
    print(f"Posterior scoring completed in {t_score:.2f}s ({len(sample_df)/t_score:.0f} pairs/sec).")

    # Verify zero NaNs in output
    nan_count = scored_df[["ebgm", "eb05", "eb95"]].isna().sum().to_dict()
    print(f"Numerical validation (NaN counts): {nan_count}")

    # 5. Descriptive Comparison: EBGM/EB05 vs PRR vs ROR
    print("\nComputing descriptive comparative metrics...")

    # (A) Rank Correlations
    eval_cols = ["ebgm", "eb05", "prr", "ror", "ror_lower_95"]
    corr_spearman = scored_df[eval_cols].corr(method="spearman").to_dict()

    # Kendall tau (subsample of 5,000 for speed if needed, or full 25k)
    tau_sub = scored_df.sample(n=min(5000, len(scored_df)), random_state=RANDOM_SEED)
    corr_kendall = tau_sub[eval_cols].corr(method="kendall").to_dict()

    # (B) Sparse Cell Behavior by Count Tier
    tier_stats = {}
    for stratum_name, grp in scored_df.groupby("stratum"):
        tier_stats[stratum_name] = {
            "count": int(len(grp)),
            "prr_median": float(grp["prr"].median()),
            "prr_q75": float(grp["prr"].quantile(0.75)),
            "prr_max": float(grp["prr"].max()),
            "ror_lower_95_median": float(grp["ror_lower_95"].median()),
            "ror_lower_95_q75": float(grp["ror_lower_95"].quantile(0.75)),
            "ror_lower_95_max": float(grp["ror_lower_95"].max()),
            "ebgm_median": float(grp["ebgm"].median()),
            "ebgm_q75": float(grp["ebgm"].quantile(0.75)),
            "ebgm_max": float(grp["ebgm"].max()),
            "eb05_median": float(grp["eb05"].median()),
            "eb05_q75": float(grp["eb05"].quantile(0.75)),
            "eb05_max": float(grp["eb05"].max()),
            "pct_prr_ge_2": float((grp["prr"] >= 2.0).mean() * 100),
            "pct_ror_lower_gt_1": float((grp["ror_lower_95"] > 1.0).mean() * 100),
            "pct_eb05_ge_2": float((grp["eb05"] >= 2.0).mean() * 100),
            "pct_eb05_ge_1": float((grp["eb05"] >= 1.0).mean() * 100),
        }

    # (C) Top-K Overlap (Jaccard similarity)
    k_values = [100, 1000, 5000, 10000]
    top_k_results = {}
    for k in k_values:
        if k > len(scored_df):
            continue
        top_prr_idx = set(scored_df.nlargest(k, "prr").index)
        top_ror_lower_idx = set(scored_df.nlargest(k, "ror_lower_95").index)
        top_eb05_idx = set(scored_df.nlargest(k, "eb05").index)
        top_ebgm_idx = set(scored_df.nlargest(k, "ebgm").index)

        def jaccard(s1, s2):
            u = len(s1.union(s2))
            return len(s1.intersection(s2)) / u if u > 0 else 0.0

        top_k_results[f"top_{k}"] = {
            "jaccard_eb05_vs_prr": float(jaccard(top_eb05_idx, top_prr_idx)),
            "jaccard_eb05_vs_ror_lower": float(jaccard(top_eb05_idx, top_ror_lower_idx)),
            "jaccard_eb05_vs_ebgm": float(jaccard(top_eb05_idx, top_ebgm_idx)),
            "overlap_count_eb05_prr": int(len(top_eb05_idx.intersection(top_prr_idx))),
            "overlap_count_eb05_ror_lower": int(len(top_eb05_idx.intersection(top_ror_lower_idx))),
            "overlap_count_eb05_ebgm": int(len(top_eb05_idx.intersection(top_ebgm_idx))),
        }

    # (D) Sparse Pairs (a between 2 and 5) Ranking Stability Analysis
    sparse_mask = scored_df["a"].between(2, 5)
    sparse_df = scored_df[sparse_mask].copy()
    scored_df["rank_prr"] = scored_df["prr"].rank(ascending=False, method="min")
    scored_df["rank_ror_lower"] = scored_df["ror_lower_95"].rank(ascending=False, method="min")
    scored_df["rank_eb05"] = scored_df["eb05"].rank(ascending=False, method="min")
    scored_df["rank_ebgm"] = scored_df["ebgm"].rank(ascending=False, method="min")

    sparse_df["rank_prr"] = scored_df.loc[sparse_mask, "rank_prr"]
    sparse_df["rank_eb05"] = scored_df.loc[sparse_mask, "rank_eb05"]
    sparse_df["rank_delta_prr_eb05"] = (sparse_df["rank_prr"] - sparse_df["rank_eb05"]).abs()

    sparse_stability = {
        "sparse_pair_count_a_2_to_5": int(len(sparse_df)),
        "sparse_pair_pct_of_sample": float(len(sparse_df) / len(scored_df) * 100),
        "mean_absolute_rank_delta_prr_eb05": float(sparse_df["rank_delta_prr_eb05"].mean()),
        "median_absolute_rank_delta_prr_eb05": float(sparse_df["rank_delta_prr_eb05"].median()),
        "max_absolute_rank_delta_prr_eb05": float(sparse_df["rank_delta_prr_eb05"].max()),
        "sparse_prr_ge_2_count": int((sparse_df["prr"] >= 2.0).sum()),
        "sparse_eb05_ge_2_count": int((sparse_df["eb05"] >= 2.0).sum()),
        "sparse_shrinkage_reduction_pct": float(
            (1.0 - (sparse_df["eb05"] >= 2.0).sum() / max(1, (sparse_df["prr"] >= 2.0).sum())) * 100
        ),
    }

    # (E) Threshold Signal Concordance
    concordance = {
        "evans_prr_signal_count": int(scored_df["prr_signal"].sum()),
        "ror_lower_signal_count": int(scored_df["ror_signal"].sum()),
        "eb05_conservative_signal_count": int(scored_df["signal_eb05_conservative"].sum()),
        "eb05_permissive_signal_count": int(scored_df["signal_eb05_permissive"].sum()),
        "concordance_eb05_cons_and_prr": int((scored_df["signal_eb05_conservative"] & scored_df["prr_signal"]).sum()),
        "concordance_eb05_cons_and_ror": int((scored_df["signal_eb05_conservative"] & scored_df["ror_signal"]).sum()),
        "prr_signal_but_not_eb05_cons": int((scored_df["prr_signal"] & ~scored_df["signal_eb05_conservative"]).sum()),
        "eb05_cons_but_not_prr_signal": int((scored_df["signal_eb05_conservative"] & ~scored_df["prr_signal"]).sum()),
    }

    # 6. Save Scored Data and Metrics Artifacts
    scored_csv_path = os.path.join(OUTPUT_DIR, "phase3c1_pilot_scored_pairs.csv")
    hypers_json_path = os.path.join(OUTPUT_DIR, "phase3c1_pilot_hyperparameters.json")
    metrics_json_path = os.path.join(OUTPUT_DIR, "phase3c1_pilot_comparison_metrics.json")
    metadata_json_path = os.path.join(OUTPUT_DIR, "phase3c1_pilot_run_metadata.json")

    print(f"\nWriting scored pilot pairs to: {scored_csv_path}...")
    scored_df.to_csv(scored_csv_path, index=False)

    print(f"Writing hyperparameter diagnostics to: {hypers_json_path}...")
    with open(hypers_json_path, "w") as f:
        json.dump({
            "unbinned_fit": fit_exact.to_dict(),
            "binned_fit": fit_binned.to_dict(),
            "selected_model": "unbinned_exact",
            "pilot_sample_size": PILOT_SAMPLE_SIZE,
            "total_universe_n": TOTAL_COHORT_N,
            "fit_runtime_seconds": t_fit_exact,
            "scoring_runtime_seconds": t_score,
            "squashing_runtime_seconds": t_squash,
        }, f, indent=2)

    print(f"Writing comparison metrics to: {metrics_json_path}...")
    with open(metrics_json_path, "w") as f:
        json.dump({
            "spearman_rank_correlation": corr_spearman,
            "kendall_rank_correlation_subsample": corr_kendall,
            "count_tier_stratification": tier_stats,
            "top_k_jaccard_overlap": top_k_results,
            "sparse_count_stability_a_2_to_5": sparse_stability,
            "signal_threshold_concordance": concordance,
        }, f, indent=2)

    # Write run metadata
    import hashlib
    import scipy
    def file_sha256(path):
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    run_meta = {
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "pilot_sample_size": PILOT_SAMPLE_SIZE,
        "random_seed": RANDOM_SEED,
        "input_dataset": INPUT_PAIRS_CSV,
        "input_sha256": file_sha256(INPUT_PAIRS_CSV),
        "python_version": sys.version,
        "numpy_version": np.__version__,
        "pandas_version": pd.__version__,
        "scipy_version": scipy.__version__,
        "total_cohort_cases_N": TOTAL_COHORT_N,
        "fit_converged": fit_exact.converged,
        "fit_iterations": fit_exact.iterations,
        "fit_log_likelihood": fit_exact.log_likelihood,
        "fitted_hyperparameters": fit_exact.hyperparameters.to_tuple() if fit_exact.hyperparameters else None,
        "runtimes_seconds": {
            "load_time": load_time,
            "fit_exact": t_fit_exact,
            "squash_2d": t_squash,
            "fit_binned": t_fit_binned,
            "posterior_scoring": t_score,
            "total_pipeline": time.time() - t0,
        },
    }
    with open(metadata_json_path, "w") as f:
        json.dump(run_meta, f, indent=2)

    # Compute manifest of all created outputs
    manifest = {}
    for fname in sorted(os.listdir(OUTPUT_DIR)):
        if fname == "phase3c1_pilot_manifest.json":
            continue
        fpath = os.path.join(OUTPUT_DIR, fname)
        if os.path.isfile(fpath):
            manifest[fname] = {
                "sha256": file_sha256(fpath),
                "size_bytes": os.path.getsize(fpath),
            }
    manifest_path = os.path.join(OUTPUT_DIR, "phase3c1_pilot_manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"Generated output manifest with {len(manifest)} files: {manifest_path}")

    # 7. Print Summary
    print("\n" + "=" * 80)
    print("PILOT DESCRIPTIVE COMPARISON SUMMARY")
    print("=" * 80)
    print(f"1. Rank Correlation (EB05 vs PRR): rho = {corr_spearman['eb05']['prr']:.4f}")
    print(f"2. Rank Correlation (EB05 vs ROR Lower 95): rho = {corr_spearman['eb05']['ror_lower_95']:.4f}")
    print(f"3. Rank Correlation (EBGM vs PRR): rho = {corr_spearman['ebgm']['prr']:.4f}")
    print(f"4. Top-100 Overlap (EB05 vs PRR): Jaccard = {top_k_results['top_100']['jaccard_eb05_vs_prr']:.4f} ({top_k_results['top_100']['overlap_count_eb05_prr']}/100 pairs)")
    print(f"5. Top-100 Overlap (EB05 vs ROR Lower 95): Jaccard = {top_k_results['top_100']['jaccard_eb05_vs_ror_lower']:.4f} ({top_k_results['top_100']['overlap_count_eb05_ror_lower']}/100 pairs)")
    print(f"6. Signal Flags: Evans PRR = {concordance['evans_prr_signal_count']:,}, ROR Lower = {concordance['ror_lower_signal_count']:,}, EB05>=2 = {concordance['eb05_conservative_signal_count']:,}")
    print(f"   Pairs with Evans PRR signal flagged as FALSE by EB05>=2: {concordance['prr_signal_but_not_eb05_cons']:,} (sparse-cell false alarm attenuation)")
    print("=" * 80)
    print("STATUS: PHASE 3C.1 PILOT COMPLETED SUCCESSFULLY")

    return {
        "sample_size": PILOT_SAMPLE_SIZE,
        "hypers": best_hypers.to_tuple(),
        "runtime_fit": t_fit_exact,
        "runtime_score": t_score,
        "spearman": corr_spearman,
        "concordance": concordance,
    }


if __name__ == "__main__":
    run_pilot()
