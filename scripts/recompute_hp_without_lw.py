#!/usr/bin/env python3
"""
Exact recomputation of hp_reporter_ratio without LW
===================================================
1. Identifies the 84,992 primary cases with occp_cod == 'LW' and rpsr_cod != 'HP'.
2. Scans 20 quarterly DRUG and REAC files for occurrences belonging to these cases.
3. Maps to normalized canonical_drug and canonical_pt using the existing normalizers.
4. Counts occurrences m_ij per candidate pair.
5. Computes corrected hp_reporter_ratio_new = hp_reporter_ratio_old - (m_ij / a).
6. Evaluates impact on Table 4 strata summaries, Kruskal-Wallis test, and epsilon^2.
"""

import os
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import stats

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.preprocessing.drug_normalizer import DrugNormalizer
from src.preprocessing.reaction_normalizer import ReactionNormalizer
from src.pipeline.pair_builder import PairBuilder

EXTRACTED_DIR = BASE_DIR / "data" / "07_phase3a_continuous_ingestion" / "extracted"
SNAP_PATH = BASE_DIR / "data" / "09_phase3a4_dual_snapshots" / "as_of_2018_snapshot.csv"
M1_PATH = BASE_DIR / "data" / "10_phase3b_features" / "m1_pure_contextual_features.csv"
CAND_PATH = BASE_DIR / "data" / "10_phase3b_features" / "candidate_pairs_summary.csv"
SCORED_PATH = BASE_DIR / "data" / "13_phase3c2_mgps_scoring" / "phase3c2_scored_candidate_pairs.csv"
OUT_DIR = BASE_DIR / "data" / "34_task_t1_12_final_scientific_corrections"
OUT_DIR.mkdir(parents=True, exist_ok=True)
CACHE_LW_COUNTS = OUT_DIR / "lw_pair_counts.csv"

if CACHE_LW_COUNTS.exists():
    print(f"Loading cached LW counts from {CACHE_LW_COUNTS}...")
    lw_counts = pd.read_csv(CACHE_LW_COUNTS)
else:
    print("Step 1: Identifying affected LW cases...")
    df_snap = pd.read_csv(SNAP_PATH, usecols=["primaryid", "caseid", "quarter", "occp_cod"], dtype=str)
    df_primary = df_snap[df_snap["quarter"].str.upper() <= "2018Q4"]
    valid_primaryids = set(df_primary["primaryid"])

    # Find HP in RPSR
    hp_rpsr_cases = set()
    quarters = sorted([d for d in os.listdir(EXTRACTED_DIR) if (EXTRACTED_DIR / d).is_dir() and d.upper() <= "2018Q4"])
    for q in quarters:
        for root, _, files in os.walk(EXTRACTED_DIR / q):
            for f in files:
                if f.upper().startswith("RPSR") and f.lower().endswith(".txt"):
                    df_rp = pd.read_csv(os.path.join(root, f), sep="$", encoding="latin-1", dtype=str, low_memory=False)
                    df_rp.columns = [c.lower().strip() for c in df_rp.columns]
                    if "primaryid" in df_rp.columns and "rpsr_cod" in df_rp.columns:
                        df_rp_valid = df_rp[df_rp["primaryid"].isin(valid_primaryids)]
                        hp_rows = df_rp_valid[df_rp_valid["rpsr_cod"].str.strip().str.upper() == "HP"]
                        if "caseid" in hp_rows.columns:
                            hp_rpsr_cases.update(hp_rows["caseid"].dropna().unique())

    lw_cases_all = df_primary[df_primary["occp_cod"] == "LW"]
    affected_df = lw_cases_all[~lw_cases_all["caseid"].isin(hp_rpsr_cases)]
    affected_primaryids = set(affected_df["primaryid"])
    affected_caseids = set(affected_df["caseid"])
    print(f"  Total affected LW cases (occp_cod=='LW' and rpsr!='HP'): {len(affected_caseids):,}")

    print("\nStep 2: Scanning DRUG and REAC child tables for affected cases only...")
    all_drug = []
    all_reac = []

    for q in quarters:
        q_dir = EXTRACTED_DIR / q
        for root, _, files in os.walk(q_dir):
            for f in files:
                f_u = f.upper()
                if f_u.startswith("DRUG") and f.lower().endswith(".txt"):
                    df_d = pd.read_csv(os.path.join(root, f), sep="$", encoding="latin-1", dtype=str, low_memory=False)
                    df_d.columns = [c.lower().strip() for c in df_d.columns]
                    avail = [c for c in ["primaryid", "caseid", "drug_seq", "role_cod", "drugname", "prod_ai"] if c in df_d.columns]
                    df_d = df_d[avail]
                    df_d = df_d[df_d["primaryid"].isin(affected_primaryids)]
                    if len(df_d) > 0:
                        all_drug.append(df_d)
                elif f_u.startswith("REAC") and f.lower().endswith(".txt"):
                    df_r = pd.read_csv(os.path.join(root, f), sep="$", encoding="latin-1", dtype=str, low_memory=False)
                    df_r.columns = [c.lower().strip() for c in df_r.columns]
                    avail = [c for c in ["primaryid", "caseid", "pt"] if c in df_r.columns]
                    df_r = df_r[avail]
                    df_r = df_r[df_r["primaryid"].isin(affected_primaryids)]
                    if len(df_r) > 0:
                        all_reac.append(df_r)

    drug_aff = pd.concat(all_drug, ignore_index=True) if all_drug else pd.DataFrame()
    reac_aff = pd.concat(all_reac, ignore_index=True) if all_reac else pd.DataFrame()
    print(f"  Affected DRUG rows: {len(drug_aff):,}, REAC rows: {len(reac_aff):,}")

    print("\nStep 3: Processing drugs and reactions...")
    pb = PairBuilder()
    drug_proc = pb.process_drugs(drug_aff)
    reac_proc = pb.process_reactions(reac_aff)

    # Build suspect occurrences
    case_pairs_aff = pb.build_case_pairs(
        demo_df=affected_df,
        drug_df=drug_proc,
        reac_df=reac_proc,
        only_normalized_drugs=True,
        only_suspect_drugs=True
    )
    print(f"  Affected case-level suspect pair occurrences: {len(case_pairs_aff):,}")

    # Count occurrences per (canonical_drug, canonical_pt)
    lw_counts = case_pairs_aff.groupby(["canonical_drug", "canonical_pt"]).size().reset_index(name="lw_count")
    print(f"  Distinct candidate pairs with >=1 affected LW report: {len(lw_counts):,}")
    lw_counts.to_csv(CACHE_LW_COUNTS, index=False)
    print(f"  Saved LW pair counts to cache: {CACHE_LW_COUNTS}")

print("\nStep 4: Merging with existing M1 features and candidate pairs...")
df_m1 = pd.read_csv(M1_PATH)
df_cand = pd.read_csv(CAND_PATH, usecols=["canonical_drug", "canonical_pt", "a"])
df_scored = pd.read_csv(SCORED_PATH, usecols=["canonical_drug", "canonical_pt", "eb05"])

df_merged = df_m1.merge(df_cand, on=["canonical_drug", "canonical_pt"], how="left")
df_merged = df_merged.merge(df_scored, on=["canonical_drug", "canonical_pt"], how="left")
df_merged = df_merged.merge(lw_counts, on=["canonical_drug", "canonical_pt"], how="left")
df_merged["lw_count"] = df_merged["lw_count"].fillna(0).astype(int)

# Correction: hp_reporter_ratio_corrected = hp_reporter_ratio - (lw_count / a)
# Bound at 0.0 to prevent floating point negative
df_merged["hp_reporter_ratio_corrected"] = np.clip(
    df_merged["hp_reporter_ratio"] - (df_merged["lw_count"] / df_merged["a"]),
    0.0, 1.0
)

diff = df_merged["hp_reporter_ratio"] - df_merged["hp_reporter_ratio_corrected"]
print(f"\nCorrection statistics across all 1,167,891 pairs:")
print(f"  Pairs with diff > 0: {(diff > 1e-6).sum():,} ({(diff > 1e-6).sum() / len(df_merged) * 100:.2f}%)")
print(f"  Mean diff: {diff.mean():.6f}")
print(f"  Max diff:  {diff.max():.6f}")
print(f"  Overall old hp_reporter_ratio mean: {df_merged['hp_reporter_ratio'].mean():.4f}")
print(f"  Overall new hp_reporter_ratio mean: {df_merged['hp_reporter_ratio_corrected'].mean():.4f}")
print(f"  Overall old hp_reporter_ratio median: {df_merged['hp_reporter_ratio'].median():.4f}")
print(f"  Overall new hp_reporter_ratio median: {df_merged['hp_reporter_ratio_corrected'].median():.4f}")

# Strata analysis
strata_defs = [
    ("EB05 < 1.0", df_merged["eb05"] < 1.0),
    ("1.0 <= EB05 < 2.0", (df_merged["eb05"] >= 1.0) & (df_merged["eb05"] < 2.0)),
    ("2.0 <= EB05 < 5.0", (df_merged["eb05"] >= 2.0) & (df_merged["eb05"] < 5.0)),
    ("5.0 <= EB05 < 10.0", (df_merged["eb05"] >= 5.0) & (df_merged["eb05"] < 10.0)),
    ("EB05 >= 10.0", df_merged["eb05"] >= 10.0),
]

print("\n--- Contextual Strata Summary: Old vs Corrected ---")
strata_groups_old = []
strata_groups_new = []

strata_stats = []

for sname, smask in strata_defs:
    sub = df_merged[smask]
    old_vals = sub["hp_reporter_ratio"].values
    new_vals = sub["hp_reporter_ratio_corrected"].values
    strata_groups_old.append(old_vals)
    strata_groups_new.append(new_vals)

    old_med = float(np.median(old_vals))
    old_iqr = float(np.percentile(old_vals, 75) - np.percentile(old_vals, 25))
    old_mean = float(np.mean(old_vals))
    old_sd = float(np.std(old_vals))

    new_med = float(np.median(new_vals))
    new_iqr = float(np.percentile(new_vals, 75) - np.percentile(new_vals, 25))
    new_mean = float(np.mean(new_vals))
    new_sd = float(np.std(new_vals))

    strata_stats.append({
        "stratum": sname,
        "n": len(sub),
        "old_median": round(old_med, 4),
        "old_iqr": round(old_iqr, 4),
        "old_mean": round(old_mean, 4),
        "old_sd": round(old_sd, 4),
        "new_median": round(new_med, 4),
        "new_iqr": round(new_iqr, 4),
        "new_mean": round(new_mean, 4),
        "new_sd": round(new_sd, 4),
        "mean_change": round(new_mean - old_mean, 4)
    })

    print(f"\nStratum: {sname} (N = {len(sub):,}):")
    print(f"  Old: Median = {old_med:.4f} [IQR = {old_iqr:.4f}], Mean = {old_mean:.4f} (SD = {old_sd:.4f})")
    print(f"  New: Median = {new_med:.4f} [IQR = {new_iqr:.4f}], Mean = {new_mean:.4f} (SD = {new_sd:.4f})")

# Kruskal-Wallis
kw_old = stats.kruskal(*strata_groups_old)
kw_new = stats.kruskal(*strata_groups_new)
n_total = len(df_merged)
eps2_old = (kw_old.statistic - 4) / (n_total - 5)
eps2_new = (kw_new.statistic - 4) / (n_total - 5)

print("\n--- Kruskal-Wallis Omnibus Test Results ---")
print(f"Old: H = {kw_old.statistic:.2f}, p = {kw_old.pvalue:.4e}, epsilon^2 = {eps2_old:.4f}")
print(f"New: H = {kw_new.statistic:.2f}, p = {kw_new.pvalue:.4e}, epsilon^2 = {eps2_new:.4f}")

# Write summary CSV
summary_df = pd.DataFrame([
    {
        "metric": "Overall Universe Mean",
        "old_value_with_lw": round(float(df_merged["hp_reporter_ratio"].mean()), 4),
        "new_value_without_lw": round(float(df_merged["hp_reporter_ratio_corrected"].mean()), 4),
        "delta": round(float(df_merged["hp_reporter_ratio_corrected"].mean() - df_merged["hp_reporter_ratio"].mean()), 4)
    },
    {
        "metric": "Overall Universe Median",
        "old_value_with_lw": round(float(df_merged["hp_reporter_ratio"].median()), 4),
        "new_value_without_lw": round(float(df_merged["hp_reporter_ratio_corrected"].median()), 4),
        "delta": round(float(df_merged["hp_reporter_ratio_corrected"].median() - df_merged["hp_reporter_ratio"].median()), 4)
    },
    {
        "metric": "Stratum 1 Mean (EB05 < 1.0)",
        "old_value_with_lw": round(float(np.mean(strata_groups_old[0])), 4),
        "new_value_without_lw": round(float(np.mean(strata_groups_new[0])), 4),
        "delta": round(float(np.mean(strata_groups_new[0]) - np.mean(strata_groups_old[0])), 4)
    },
    {
        "metric": "Stratum 1 Median (EB05 < 1.0)",
        "old_value_with_lw": round(float(np.median(strata_groups_old[0])), 4),
        "new_value_without_lw": round(float(np.median(strata_groups_new[0])), 4),
        "delta": round(float(np.median(strata_groups_new[0]) - np.median(strata_groups_old[0])), 4)
    },
    {
        "metric": "Stratum 5 Mean (EB05 >= 10.0)",
        "old_value_with_lw": round(float(np.mean(strata_groups_old[4])), 4),
        "new_value_without_lw": round(float(np.mean(strata_groups_new[4])), 4),
        "delta": round(float(np.mean(strata_groups_new[4]) - np.mean(strata_groups_old[4])), 4)
    },
    {
        "metric": "Stratum 5 Median (EB05 >= 10.0)",
        "old_value_with_lw": round(float(np.median(strata_groups_old[4])), 4),
        "new_value_without_lw": round(float(np.median(strata_groups_new[4])), 4),
        "delta": round(float(np.median(strata_groups_new[4]) - np.median(strata_groups_old[4])), 4)
    },
    {
        "metric": "Kruskal-Wallis H statistic",
        "old_value_with_lw": round(float(kw_old.statistic), 2),
        "new_value_without_lw": round(float(kw_new.statistic), 2),
        "delta": round(float(kw_new.statistic - kw_old.statistic), 2)
    },
    {
        "metric": "Epsilon-squared effect size",
        "old_value_with_lw": round(float(eps2_old), 4),
        "new_value_without_lw": round(float(eps2_new), 4),
        "delta": round(float(eps2_new - eps2_old), 4)
    }
])

summary_df.to_csv(OUT_DIR / "reporter_feature_recomputation_summary.csv", index=False)
print(f"\nSaved summary to {OUT_DIR / 'reporter_feature_recomputation_summary.csv'}")

# Also save detailed strata stats
pd.DataFrame(strata_stats).to_csv(OUT_DIR / "hp_reporter_strata_comparison.csv", index=False)
print(f"Saved strata breakdown to {OUT_DIR / 'hp_reporter_strata_comparison.csv'}")
