#!/usr/bin/env python3
"""
TASK-T1-01: Contextual Feature Stratification and Signal-Contrast Analysis
Track 1 — Scientific Validation and Publication Preparation

Performs:
1. Analysis A: Contextual feature distributions across EB05 strata (5 strata + overall)
   with Kruskal-Wallis omnibus tests, effect sizes (epsilon^2, eta^2_H), and BH-FDR correction.
2. Analysis B: Signal contrast analysis comparing EB05-defined signals (EB05 >= 2.0)
   against below-threshold pairs (EB05 < 2.0) with Mann-Whitney U, Cohen's d,
   rank-biserial r, and BH-FDR correction.
3. Analysis C: Bayesian shrinkage vs PRR discordance analysis stratified by report count (a tiers),
   explaining the resolution of the reported 102,458 net difference vs 135,159 PRR-only pairs.
"""

import os
import sys
import json
import hashlib
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import scipy.stats as stats

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCORED_FILE = os.path.join(BASE_DIR, "data", "13_phase3c2_mgps_scoring", "phase3c2_scored_candidate_pairs.csv")
M1_FILE = os.path.join(BASE_DIR, "data", "10_phase3b_features", "m1_pure_contextual_features.csv")
OUTPUT_DIR = os.path.join(BASE_DIR, "data", "19_track1_contextual_analysis")

EXPECTED_ROWS = 1167891
EXPECTED_SCORED_SHA256 = "79d07631e65fef8a84cd14e3368c3ca379ec59f66088d3a5824d9dbf6ada5758"
EXPECTED_M1_SHA256 = "ff13912020a4ae116e7cb0e39735fc4a4fa6574b3616844711b1f1a6eb133397"

CONTEXTUAL_FEATURES = [
    "mean_age",
    "median_age",
    "age_std",
    "age_missing_ratio",
    "female_ratio",
    "male_ratio",
    "hp_reporter_ratio",
    "csm_reporter_ratio",
    "monotherapy_ratio",
    "mean_concomitant_count",
    "secondary_suspect_ratio"
]

STRATA_CONFIG = [
    ("EB05 < 1.0", lambda df: df["eb05"] < 1.0),
    ("1.0 <= EB05 < 2.0", lambda df: (df["eb05"] >= 1.0) & (df["eb05"] < 2.0)),
    ("2.0 <= EB05 < 5.0", lambda df: (df["eb05"] >= 2.0) & (df["eb05"] < 5.0)),
    ("5.0 <= EB05 < 10.0", lambda df: (df["eb05"] >= 5.0) & (df["eb05"] < 10.0)),
    ("EB05 >= 10.0", lambda df: df["eb05"] >= 10.0),
]

TIER_CONFIG = [
    ("a = 2-3", 2, 3),
    ("a = 4-5", 4, 5),
    ("a = 6-10", 6, 10),
    ("a = 11-20", 11, 20),
    ("a > 20", 21, 100000000)
]


def sha256_file(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def benjamini_hochberg(p_values: np.ndarray) -> np.ndarray:
    p_values = np.asarray(p_values)
    n = len(p_values)
    if n == 0:
        return np.array([])
    order = np.argsort(p_values)
    ordered_p = p_values[order]
    adjusted = np.empty(n, dtype=float)
    cumulative_min = 1.0
    for i in range(n - 1, -1, -1):
        rank = i + 1
        adj_p = ordered_p[i] * n / rank
        if adj_p < cumulative_min:
            cumulative_min = adj_p
        adjusted[order[i]] = min(cumulative_min, 1.0)
    return adjusted


def compute_distribution_summary(series: pd.Series):
    valid = series.dropna()
    n_total = len(series)
    n_valid = len(valid)
    n_missing = n_total - n_valid
    pct_missing = (n_missing / n_total) * 100.0 if n_total > 0 else 0.0

    if n_valid == 0:
        return {
            "n_total": n_total,
            "n_valid": 0,
            "n_missing": n_missing,
            "pct_missing": round(pct_missing, 4),
            "mean": None,
            "std": None,
            "median": None,
            "q25": None,
            "q75": None,
            "iqr": None,
            "min": None,
            "max": None
        }

    q25, median, q75 = np.percentile(valid.values, [25, 50, 75])
    return {
        "n_total": n_total,
        "n_valid": n_valid,
        "n_missing": n_missing,
        "pct_missing": round(pct_missing, 4),
        "mean": float(np.mean(valid.values)),
        "std": float(np.std(valid.values, ddof=1)) if n_valid > 1 else 0.0,
        "median": float(median),
        "q25": float(q25),
        "q75": float(q75),
        "iqr": float(q75 - q25),
        "min": float(np.min(valid.values)),
        "max": float(np.max(valid.values))
    }


def main():
    start_time = time.time()
    print("=" * 80)
    print("TASK-T1-01: Contextual Feature Stratification and Signal-Contrast Analysis")
    print("=" * 80)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 1. Verify inputs
    print("\n--- STEP 1: Verifying input checksums and schemas ---")
    scored_sha = sha256_file(SCORED_FILE)
    m1_sha = sha256_file(M1_FILE)
    print(f"Scored file SHA-256: {scored_sha}")
    print(f"Expected SHA-256:    {EXPECTED_SCORED_SHA256}")
    assert scored_sha == EXPECTED_SCORED_SHA256, "Scored dataset checksum mismatch!"

    print(f"M1 file SHA-256:     {m1_sha}")
    print(f"Expected SHA-256:    {EXPECTED_M1_SHA256}")
    assert m1_sha == EXPECTED_M1_SHA256, "M1 feature dataset checksum mismatch!"

    # 2. Load and validate data
    print("\n--- STEP 2: Loading datasets ---")
    df_scored = pd.read_csv(
        SCORED_FILE,
        usecols=["canonical_drug", "canonical_pt", "a", "prr", "prr_chi2", "prr_signal", "eb05", "signal_eb05_conservative"]
    )
    df_m1 = pd.read_csv(
        M1_FILE,
        usecols=["canonical_drug", "canonical_pt"] + CONTEXTUAL_FEATURES
    )

    assert len(df_scored) == EXPECTED_ROWS, f"Expected {EXPECTED_ROWS} rows in scored, got {len(df_scored)}"
    assert len(df_m1) == EXPECTED_ROWS, f"Expected {EXPECTED_ROWS} rows in M1, got {len(df_m1)}"

    # Validate 1-to-1 key alignment
    key_match = (
        (df_scored["canonical_drug"] == df_m1["canonical_drug"]).all() and
        (df_scored["canonical_pt"] == df_m1["canonical_pt"]).all()
    )
    assert key_match, "Row-by-row key alignment failed between scored and M1 files!"
    print(f"Row alignment verified: exactly {EXPECTED_ROWS:,} pairs with 1-to-1 deterministic correspondence.")

    # Combine needed columns
    df = pd.concat([df_scored, df_m1[CONTEXTUAL_FEATURES]], axis=1)
    del df_scored, df_m1

    # Assign strata
    strata_labels = []
    for label, cond in STRATA_CONFIG:
        df.loc[cond(df), "stratum"] = label

    # Verify strata assignment completeness
    assert df["stratum"].isnull().sum() == 0, "Some candidate pairs were not assigned to an EB05 stratum!"
    print("Stratum counts:")
    for label, _ in STRATA_CONFIG:
        cnt = (df["stratum"] == label).sum()
        pct = (cnt / EXPECTED_ROWS) * 100.0
        print(f"  {label:<20}: {cnt:>8,} ({pct:6.2f}%)")

    # -------------------------------------------------------------
    # ANALYSIS A: Contextual Feature Strata Summary and Omnibus Tests
    # -------------------------------------------------------------
    print("\n--- STEP 3: Executing Analysis A (Contextual Feature Strata) ---")
    summary_rows = []

    # Calculate distributions across strata + overall
    all_strata_labels = [label for label, _ in STRATA_CONFIG] + ["Overall"]

    for feat in CONTEXTUAL_FEATURES:
        for stratum_name in all_strata_labels:
            if stratum_name == "Overall":
                series = df[feat]
            else:
                series = df.loc[df["stratum"] == stratum_name, feat]

            stats_dict = compute_distribution_summary(series)
            summary_rows.append({
                "feature": feat,
                "stratum": stratum_name,
                "n_total": stats_dict["n_total"],
                "n_valid": stats_dict["n_valid"],
                "n_missing": stats_dict["n_missing"],
                "pct_missing": stats_dict["pct_missing"],
                "mean": round(stats_dict["mean"], 4) if stats_dict["mean"] is not None else None,
                "std": round(stats_dict["std"], 4) if stats_dict["std"] is not None else None,
                "median": round(stats_dict["median"], 4) if stats_dict["median"] is not None else None,
                "q25": round(stats_dict["q25"], 4) if stats_dict["q25"] is not None else None,
                "q75": round(stats_dict["q75"], 4) if stats_dict["q75"] is not None else None,
                "iqr": round(stats_dict["iqr"], 4) if stats_dict["iqr"] is not None else None,
                "min": round(stats_dict["min"], 4) if stats_dict["min"] is not None else None,
                "max": round(stats_dict["max"], 4) if stats_dict["max"] is not None else None
            })

    df_strata_summary = pd.DataFrame(summary_rows)
    strata_summary_csv = os.path.join(OUTPUT_DIR, "contextual_strata_summary.csv")
    df_strata_summary.to_csv(strata_summary_csv, index=False)
    print(f"Saved: {strata_summary_csv} ({len(df_strata_summary)} rows)")

    # Omnibus statistical tests (Kruskal-Wallis across the 5 strata)
    test_rows = []
    kw_raw_p = []
    kw_stats = []

    for feat in CONTEXTUAL_FEATURES:
        groups = []
        for label, _ in STRATA_CONFIG:
            group_vals = df.loc[df["stratum"] == label, feat].dropna().values
            groups.append(group_vals)

        h_stat, p_val = stats.kruskal(*groups)
        n_obs = sum(len(g) for g in groups)
        k_groups = len(groups)

        # Effect sizes:
        # Epsilon-squared (epsilon^2) = (H - k + 1) / (N - k) or H / (N - 1)
        # Using standard formula epsilon^2 = H / ((N^2 - 1) / (N + 1)) = H / (N - 1)
        epsilon_sq = float(h_stat / (n_obs - 1)) if n_obs > 1 else 0.0
        # Eta-squared_H = (H - k + 1) / (N - k)
        eta_sq_h = float((h_stat - k_groups + 1) / (n_obs - k_groups)) if n_obs > k_groups else 0.0

        # Practical magnitude interpretation:
        # < 0.01: Negligible; 0.01 - 0.06: Small; 0.06 - 0.14: Moderate; >= 0.14: Large
        if epsilon_sq < 0.01:
            magnitude = "Negligible (<0.01)"
        elif epsilon_sq < 0.06:
            magnitude = "Small (0.01-0.06)"
        elif epsilon_sq < 0.14:
            magnitude = "Moderate (0.06-0.14)"
        else:
            magnitude = "Large (>=0.14)"

        kw_stats.append({
            "feature": feat,
            "test_type": "Kruskal-Wallis omnibus H-test",
            "k_groups": k_groups,
            "n_observations": n_obs,
            "degrees_of_freedom": k_groups - 1,
            "h_statistic": float(h_stat),
            "p_value_raw": float(p_val),
            "epsilon_squared": float(epsilon_sq),
            "eta_squared_h": float(eta_sq_h),
            "practical_magnitude": magnitude
        })
        kw_raw_p.append(p_val)

    # Benjamini-Hochberg correction
    kw_adj_p = benjamini_hochberg(np.array(kw_raw_p))
    for i, item in enumerate(kw_stats):
        item["p_value_fdr_bh"] = float(kw_adj_p[i])
        item["statistically_significant_005"] = bool(kw_adj_p[i] < 0.05)

    df_strata_tests = pd.DataFrame(kw_stats)
    strata_tests_csv = os.path.join(OUTPUT_DIR, "contextual_strata_tests.csv")
    df_strata_tests.to_csv(strata_tests_csv, index=False)
    print(f"Saved: {strata_tests_csv} ({len(df_strata_tests)} tests)")

    # -------------------------------------------------------------
    # ANALYSIS B: EB05 Signal Contrast (EB05 >= 2.0 vs EB05 < 2.0)
    # -------------------------------------------------------------
    print("\n--- STEP 4: Executing Analysis B (EB05 Signal Contrast) ---")
    signal_mask = df["signal_eb05_conservative"] == True
    below_mask = ~signal_mask

    n_signal = int(signal_mask.sum())
    n_below = int(below_mask.sum())
    print(f"EB05-defined signal group (EB05 >= 2.0): {n_signal:,} pairs ({n_signal / EXPECTED_ROWS * 100:.2f}%)")
    print(f"Below-threshold group (EB05 < 2.0):      {n_below:,} pairs ({n_below / EXPECTED_ROWS * 100:.2f}%)")

    contrast_results = {
        "metadata": {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "total_candidate_pairs": EXPECTED_ROWS,
            "signal_group_definition": "EB05 >= 2.0 (Conservative signal)",
            "below_threshold_definition": "EB05 < 2.0 (Sub-threshold and noise)",
            "n_signal_group": n_signal,
            "n_below_threshold": n_below,
            "signal_prevalence_pct": round(n_signal / EXPECTED_ROWS * 100.0, 4)
        },
        "features": {}
    }

    mw_raw_p = []
    contrast_feature_keys = []

    for feat in CONTEXTUAL_FEATURES:
        vals_signal = df.loc[signal_mask, feat].dropna().values
        vals_below = df.loc[below_mask, feat].dropna().values

        stats_signal = compute_distribution_summary(df.loc[signal_mask, feat])
        stats_below = compute_distribution_summary(df.loc[below_mask, feat])

        # Inferential comparison
        u_stat, p_val = stats.mannwhitneyu(vals_signal, vals_below, alternative="two-sided")
        n1 = len(vals_signal)
        n2 = len(vals_below)

        # Rank-biserial correlation r = 1 - (2*U) / (n1*n2)
        # Ranges from -1 to +1
        rank_biserial_r = float(1.0 - (2.0 * float(u_stat)) / (float(n1) * float(n2)))
        cliffs_delta = float(-rank_biserial_r)

        # Cohen's d (parametric effect size)
        mean1, std1 = stats_signal["mean"], stats_signal["std"]
        mean2, std2 = stats_below["mean"], stats_below["std"]
        if n1 > 1 and n2 > 1 and (std1 is not None) and (std2 is not None):
            s_pooled = np.sqrt(((n1 - 1) * (std1 ** 2) + (n2 - 1) * (std2 ** 2)) / (n1 + n2 - 2))
            cohens_d = float((mean1 - mean2) / s_pooled) if s_pooled > 0 else 0.0
            # Standard error of d
            se_d = float(np.sqrt((n1 + n2) / (n1 * n2) + (cohens_d ** 2) / (2 * (n1 + n2))))
            ci_95_d = [float(cohens_d - 1.96 * se_d), float(cohens_d + 1.96 * se_d)]
        else:
            cohens_d = 0.0
            ci_95_d = [0.0, 0.0]

        # Practical magnitude of Cohen's d:
        # < 0.2: Negligible; 0.2 - 0.5: Small; 0.5 - 0.8: Medium; >= 0.8: Large
        abs_d = abs(cohens_d)
        if abs_d < 0.2:
            d_magnitude = "Negligible (<0.20)"
        elif abs_d < 0.5:
            d_magnitude = "Small (0.20-0.50)"
        elif abs_d < 0.8:
            d_magnitude = "Medium (0.50-0.80)"
        else:
            d_magnitude = "Large (>=0.80)"

        median_diff = stats_signal["median"] - stats_below["median"] if stats_signal["median"] is not None and stats_below["median"] is not None else None
        mean_diff = mean1 - mean2 if mean1 is not None and mean2 is not None else None

        contrast_results["features"][feat] = {
            "signal_group": stats_signal,
            "below_threshold_group": stats_below,
            "mean_difference": round(mean_diff, 4) if mean_diff is not None else None,
            "median_difference": round(median_diff, 4) if median_diff is not None else None,
            "cohens_d": round(cohens_d, 4),
            "cohens_d_95ci": [round(ci_95_d[0], 4), round(ci_95_d[1], 4)],
            "cohens_d_magnitude": d_magnitude,
            "mann_whitney_u_statistic": float(u_stat),
            "rank_biserial_r": round(rank_biserial_r, 4),
            "cliffs_delta": round(cliffs_delta, 4),
            "p_value_raw": float(p_val)
        }
        mw_raw_p.append(p_val)
        contrast_feature_keys.append(feat)

    # Benjamini-Hochberg adjustment for Analysis B
    mw_adj_p = benjamini_hochberg(np.array(mw_raw_p))
    for i, feat in enumerate(contrast_feature_keys):
        contrast_results["features"][feat]["p_value_fdr_bh"] = float(mw_adj_p[i])
        contrast_results["features"][feat]["statistically_significant_005"] = bool(mw_adj_p[i] < 0.05)

    signal_contrast_json = os.path.join(OUTPUT_DIR, "signal_contrast_statistics.json")
    with open(signal_contrast_json, "w") as f:
        json.dump(contrast_results, f, indent=2)
    print(f"Saved: {signal_contrast_json}")

    # -------------------------------------------------------------
    # ANALYSIS C: Shrinkage vs PRR Discordance by Report Volume Tier
    # -------------------------------------------------------------
    print("\n--- STEP 5: Executing Analysis C (Shrinkage vs PRR Discordance) ---")
    # Verify overall discordance matrix
    # Evans PRR signal: a >= 3 & prr >= 2.0 & prr_chi2 >= 4.0
    prr_signal_mask = df["prr_signal"] == True
    eb05_signal_mask = df["signal_eb05_conservative"] == True

    both_mask = prr_signal_mask & eb05_signal_mask
    neither_mask = (~prr_signal_mask) & (~eb05_signal_mask)
    prr_only_mask = prr_signal_mask & (~eb05_signal_mask)
    eb05_only_mask = (~prr_signal_mask) & eb05_signal_mask

    n_prr_total = int(prr_signal_mask.sum())
    n_eb05_total = int(eb05_signal_mask.sum())
    n_both = int(both_mask.sum())
    n_neither = int(neither_mask.sum())
    n_prr_only = int(prr_only_mask.sum())
    n_eb05_only = int(eb05_only_mask.sum())

    print("Overall Disproportionality Signal Matrix:")
    print(f"  PRR Signals (Evans criterion):     {n_prr_total:,}")
    print(f"  EB05 Signals (EB05 >= 2.0):        {n_eb05_total:,}")
    print(f"  Net difference (PRR - EB05):       {n_prr_total - n_eb05_total:,} (reported as 102,458)")
    print(f"  Concordant Signals (Both):         {n_both:,}")
    print(f"  Concordant Non-signals (Neither):  {n_neither:,}")
    print(f"  PRR-only Discordant:               {n_prr_only:,}")
    print(f"  EB05-only Discordant:              {n_eb05_only:,}")
    assert n_prr_total - n_eb05_total == 102458, "Net difference mismatch!"

    # Tiered breakdown
    tier_rows = []
    all_tiers = TIER_CONFIG + [("Overall (a >= 2)", 2, 100000000)]

    for tier_name, a_min, a_max in all_tiers:
        tier_sub = (df["a"] >= a_min) & (df["a"] <= a_max)
        n_tier = int(tier_sub.sum())

        sub_prr = prr_signal_mask & tier_sub
        sub_eb05 = eb05_signal_mask & tier_sub
        sub_prr_only = prr_only_mask & tier_sub
        sub_eb05_only = eb05_only_mask & tier_sub
        sub_both = both_mask & tier_sub
        sub_neither = neither_mask & tier_sub

        n_t_prr = int(sub_prr.sum())
        n_t_eb05 = int(sub_eb05.sum())
        n_t_prr_only = int(sub_prr_only.sum())
        n_t_eb05_only = int(sub_eb05_only.sum())
        n_t_both = int(sub_both.sum())
        n_t_neither = int(sub_neither.sum())

        # Distribution of PRR and EB05 among PRR-only discordant pairs
        df_prr_only_tier = df.loc[sub_prr_only]
        if len(df_prr_only_tier) > 0:
            prr_q25, prr_med, prr_q75 = np.percentile(df_prr_only_tier["prr"].values, [25, 50, 75])
            prr_mean = float(np.mean(df_prr_only_tier["prr"].values))
            eb05_q25, eb05_med, eb05_q75 = np.percentile(df_prr_only_tier["eb05"].values, [25, 50, 75])
            eb05_mean = float(np.mean(df_prr_only_tier["eb05"].values))

            # Contextual medians among PRR-only discordant
            age_valid = df_prr_only_tier["mean_age"].dropna()
            age_med = float(np.median(age_valid.values)) if len(age_valid) > 0 else None
            age_missing_pct = float(df_prr_only_tier["mean_age"].isnull().mean() * 100.0)

            fem_med = float(np.median(df_prr_only_tier["female_ratio"].values))
            hp_med = float(np.median(df_prr_only_tier["hp_reporter_ratio"].values))
            csm_med = float(np.median(df_prr_only_tier["csm_reporter_ratio"].values))
            mono_med = float(np.median(df_prr_only_tier["monotherapy_ratio"].values))
            concom_med = float(np.median(df_prr_only_tier["mean_concomitant_count"].values))
            sec_med = float(np.median(df_prr_only_tier["secondary_suspect_ratio"].values))
        else:
            prr_q25, prr_med, prr_q75, prr_mean = None, None, None, None
            eb05_q25, eb05_med, eb05_q75, eb05_mean = None, None, None, None
            age_med, age_missing_pct = None, 0.0
            fem_med, hp_med, csm_med, mono_med, concom_med, sec_med = None, None, None, None, None, None

        tier_rows.append({
            "tier": tier_name,
            "a_min": a_min,
            "a_max": a_max if a_max < 100000000 else df["a"].max(),
            "n_total_tier": n_tier,
            "pct_of_all_candidate_pairs": round(n_tier / EXPECTED_ROWS * 100.0, 4),
            "n_prr_signal": n_t_prr,
            "pct_prr_signal_in_tier": round(n_t_prr / n_tier * 100.0, 4) if n_tier > 0 else 0.0,
            "n_eb05_signal": n_t_eb05,
            "pct_eb05_signal_in_tier": round(n_t_eb05 / n_tier * 100.0, 4) if n_tier > 0 else 0.0,
            "n_discordant_prr_only": n_t_prr_only,
            "pct_discordant_prr_only_in_tier": round(n_t_prr_only / n_tier * 100.0, 4) if n_tier > 0 else 0.0,
            "n_discordant_eb05_only": n_t_eb05_only,
            "pct_discordant_eb05_only_in_tier": round(n_t_eb05_only / n_tier * 100.0, 4) if n_tier > 0 else 0.0,
            "n_concordant_both": n_t_both,
            "n_concordant_neither": n_t_neither,
            "net_signal_reduction": n_t_prr - n_t_eb05,
            "prr_median_discordant": round(prr_med, 4) if prr_med is not None else None,
            "prr_iqr_discordant": round(prr_q75 - prr_q25, 4) if prr_med is not None else None,
            "prr_mean_discordant": round(prr_mean, 4) if prr_mean is not None else None,
            "eb05_median_discordant": round(eb05_med, 4) if eb05_med is not None else None,
            "eb05_iqr_discordant": round(eb05_q75 - eb05_q25, 4) if eb05_med is not None else None,
            "eb05_mean_discordant": round(eb05_mean, 4) if eb05_mean is not None else None,
            "mean_age_median_discordant": round(age_med, 2) if age_med is not None else None,
            "mean_age_pct_missing_discordant": round(age_missing_pct, 2),
            "female_ratio_median_discordant": round(fem_med, 4) if fem_med is not None else None,
            "hp_reporter_ratio_median_discordant": round(hp_med, 4) if hp_med is not None else None,
            "csm_reporter_ratio_median_discordant": round(csm_med, 4) if csm_med is not None else None,
            "monotherapy_ratio_median_discordant": round(mono_med, 4) if mono_med is not None else None,
            "concomitant_count_median_discordant": round(concom_med, 2) if concom_med is not None else None,
            "secondary_suspect_ratio_median_discordant": round(sec_med, 4) if sec_med is not None else None
        })

    df_tier_discordance = pd.DataFrame(tier_rows)
    tier_discordance_csv = os.path.join(OUTPUT_DIR, "shrinkage_discordance_by_tier.csv")
    df_tier_discordance.to_csv(tier_discordance_csv, index=False)
    print(f"Saved: {tier_discordance_csv}")

    elapsed = time.time() - start_time
    print(f"\nContextual analysis execution completed successfully in {elapsed:.2f} seconds.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
