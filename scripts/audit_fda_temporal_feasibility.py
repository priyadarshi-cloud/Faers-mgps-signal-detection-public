"""
FDA Historical-Label and Continuous FAERS Temporal Coverage Feasibility Audit Script.

Computes exact empirical drug concentration metrics from frozen candidate pairs,
inventories the complete 2014Q1-2023Q4 FAERS quarterly timeline,
and exports machine-readable audit artifacts to data/06_audit_fda_temporal/.
"""

import os
import sys
import json
import pandas as pd
import numpy as np

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

AUDIT_DIR = os.path.join(PROJECT_ROOT, "data", "06_audit_fda_temporal")
PRIMARY_DIR = os.path.join(PROJECT_ROOT, "data", "03_primary")
RAW_SAMPLE_DIR = os.path.join(PROJECT_ROOT, "data", "01_raw", "sample_quarters")

def audit_drug_concentration():
    print("\n--- Part A: Empirical Drug Concentration & Coverage Audit ---")
    cp_path = os.path.join(PRIMARY_DIR, "phase2_candidate_pairs_summary.csv")
    df = pd.read_csv(cp_path, usecols=["canonical_drug", "canonical_pt", "a"])
    total_pairs = len(df)
    total_distinct_drugs = df["canonical_drug"].nunique()
    total_case_volume = df["a"].sum()

    print(f"Total frozen candidate pairs (A >= 2): {total_pairs:,}")
    print(f"Total distinct canonical drugs: {total_distinct_drugs:,}")
    print(f"Total cumulative case occurrences (sum of A): {total_case_volume:,}")

    # Rank drugs by pair count and case volume
    drug_stats = df.groupby("canonical_drug").agg(
        pair_count=("canonical_pt", "count"),
        case_volume=("a", "sum")
    ).reset_index()

    drug_stats_sorted_by_pairs = drug_stats.sort_values("pair_count", ascending=False).reset_index(drop=True)
    drug_stats_sorted_by_pairs["cum_pairs"] = drug_stats_sorted_by_pairs["pair_count"].cumsum()
    drug_stats_sorted_by_pairs["cum_pair_pct"] = drug_stats_sorted_by_pairs["cum_pairs"] / total_pairs * 100
    drug_stats_sorted_by_pairs["cum_cases"] = drug_stats_sorted_by_pairs["case_volume"].cumsum()
    drug_stats_sorted_by_pairs["cum_case_pct"] = drug_stats_sorted_by_pairs["cum_cases"] / total_case_volume * 100

    cohort_benchmarks = {}
    for n in [25, 50, 100, 150, 200, 250, 500, 1000]:
        sub = drug_stats_sorted_by_pairs.iloc[:n]
        p_count = int(sub["pair_count"].sum())
        p_pct = float(p_count / total_pairs * 100)
        c_count = int(sub["case_volume"].sum())
        c_pct = float(c_count / total_case_volume * 100)
        cohort_benchmarks[f"top_{n}"] = {
            "drug_count": n,
            "pairs_covered": p_count,
            "pairs_percentage": round(p_pct, 2),
            "case_volume_covered": c_count,
            "case_volume_percentage": round(c_pct, 2)
        }
        print(f"Top {n:4d} drugs: {p_count:7,} pairs ({p_pct:5.2f}% of universe) | {c_count:9,} cases ({c_pct:5.2f}% of cases)")

    # Analyze therapeutic composition of Top 25
    top_25_list = []
    for idx, row in drug_stats_sorted_by_pairs.head(25).iterrows():
        top_25_list.append({
            "rank": idx + 1,
            "canonical_drug": row["canonical_drug"],
            "pair_count": int(row["pair_count"]),
            "pair_pct": round(row["pair_count"] / total_pairs * 100, 3),
            "case_volume": int(row["case_volume"]),
            "case_pct": round(row["case_volume"] / total_case_volume * 100, 3)
        })

    return {
        "total_pairs": total_pairs,
        "total_distinct_drugs": total_distinct_drugs,
        "total_case_volume": int(total_case_volume),
        "cohort_benchmarks": cohort_benchmarks,
        "top_25_drugs": top_25_list,
        "drug_stats_df": drug_stats_sorted_by_pairs
    }

def audit_faers_quarterly_timeline():
    print("\n--- Part C: Complete FAERS Quarterly Inventory (2014-2023) ---")

    # Ingested quarters currently in data/01_raw/sample_quarters
    ingested_folders = set()
    if os.path.exists(RAW_SAMPLE_DIR):
        for item in os.listdir(RAW_SAMPLE_DIR):
            if os.path.isdir(os.path.join(RAW_SAMPLE_DIR, item)) and item.lower().endswith("q1"):
                ingested_folders.add(item.lower())

    print(f"Currently ingested quarterly sample folders: {sorted(list(ingested_folders))}")

    # Generate complete list of 40 quarters from 2014Q1 to 2023Q4
    all_quarters = []
    missing_quarters = []

    years = range(2014, 2024)
    quarters = ["q1", "q2", "q3", "q4"]

    inventory_records = []

    for yr in years:
        for q in quarters:
            q_code = f"{yr}{q}"
            is_ingested = q_code in ingested_folders

            # FDA FIS export URL pattern
            # Note: 2019+ often uses uppercase Q in FIS URLs, e.g. 2019Q1.zip
            if yr >= 2019:
                url_q = q.upper()
            else:
                url_q = q.lower()
            download_url = f"https://fis.fda.gov/content/Exports/faers_ascii_{yr}{url_q}.zip"

            # Estimate compressed zip size based on observed empirical trends:
            # 2014: ~30-40 MB, 2019: ~58 MB, 2023: ~68 MB
            est_size_mb = round(30.0 + (yr - 2014) * 4.2, 1)

            rec = {
                "quarter": q_code.upper(),
                "year": yr,
                "quarter_num": q.upper(),
                "is_ingested": is_ingested,
                "status": "INGESTED" if is_ingested else "MISSING",
                "download_url": download_url,
                "estimated_compressed_mb": est_size_mb,
                "estimated_uncompressed_mb": round(est_size_mb * 5.5, 1)
            }
            inventory_records.append(rec)
            all_quarters.append(q_code)
            if not is_ingested:
                missing_quarters.append(q_code)

    print(f"Total timeline quarters (2014Q1 - 2023Q4): {len(all_quarters)}")
    print(f"Ingested quarters: {len(ingested_folders)} ({sorted(list(ingested_folders))})")
    print(f"Missing quarters count: {len(missing_quarters)}")

    # Gaps breakdown
    gap_1 = [q.upper() for q in all_quarters if "2014q1" < q < "2019q1"]
    gap_2 = [q.upper() for q in all_quarters if "2019q1" < q < "2023q1"]
    gap_3 = [q.upper() for q in all_quarters if q > "2023q1"]

    print(f"Gap 1 (2014Q2 to 2018Q4): {len(gap_1)} quarters missing")
    print(f"Gap 2 (2019Q2 to 2022Q4): {len(gap_2)} quarters missing")
    print(f"Gap 3 (2023Q2 to 2023Q4): {len(gap_3)} quarters missing")

    total_est_download_mb = sum(r["estimated_compressed_mb"] for r in inventory_records if not r["is_ingested"])
    total_est_uncompressed_mb = sum(r["estimated_uncompressed_mb"] for r in inventory_records if not r["is_ingested"])

    print(f"Total estimated download volume for missing quarters: {total_est_download_mb / 1024:.2f} GB (compressed)")
    print(f"Total estimated uncompressed ASCII volume: {total_est_uncompressed_mb / 1024:.2f} GB")

    return {
        "total_timeline_quarters": len(all_quarters),
        "ingested_count": len(ingested_folders),
        "ingested_quarters": sorted(list(ingested_folders)),
        "missing_count": len(missing_quarters),
        "missing_quarters": missing_quarters,
        "gap_1_quarters": gap_1,
        "gap_2_quarters": gap_2,
        "gap_3_quarters": gap_3,
        "total_estimated_download_gb": round(total_est_download_mb / 1024, 2),
        "total_estimated_uncompressed_gb": round(total_est_uncompressed_mb / 1024, 2),
        "inventory_records": inventory_records
    }

def main():
    os.makedirs(AUDIT_DIR, exist_ok=True)
    print("=" * 75)
    print("FDA HISTORICAL-LABEL & FAERS TEMPORAL FEASIBILITY AUDIT")
    print(f"Audit Target Directory: {AUDIT_DIR}")
    print("=" * 75)

    # 1. Run Drug Concentration Audit
    drug_results = audit_drug_concentration()

    # 2. Run FAERS Quarterly Inventory Audit
    timeline_results = audit_faers_quarterly_timeline()

    # 3. Export Machine-Readable Summaries
    print("\n--- Exporting Machine-Readable Artifacts ---")

    # CSV 1: Drug Coverage & Concentration
    drug_df = drug_results.pop("drug_stats_df")
    drug_csv_path = os.path.join(AUDIT_DIR, "drug_coverage_concentration.csv")
    drug_df.to_csv(drug_csv_path, index=False)
    print(f"  Saved drug concentration CSV: {drug_csv_path}")

    # CSV 2: Quarterly Inventory
    inv_df = pd.DataFrame(timeline_results.pop("inventory_records"))
    inv_csv_path = os.path.join(AUDIT_DIR, "faers_quarterly_inventory.csv")
    inv_df.to_csv(inv_csv_path, index=False)
    print(f"  Saved quarterly inventory CSV: {inv_csv_path}")

    # JSON: Combined Machine-Readable Audit Summary
    summary_data = {
        "audit_name": "FDA Historical-Label and Continuous FAERS Temporal Coverage Feasibility Audit",
        "audit_timestamp": "2026-10-10",
        "candidate_universe": {
            "total_candidate_pairs": drug_results["total_pairs"],
            "total_distinct_drugs": drug_results["total_distinct_drugs"],
            "total_case_volume": drug_results["total_case_volume"]
        },
        "drug_concentration_benchmarks": drug_results["cohort_benchmarks"],
        "top_25_drugs_profile": drug_results["top_25_drugs"],
        "quarterly_coverage_inventory": timeline_results,
        "decision_matrix": {
            "historical_label_construction": {
                "decision": "NO-GO",
                "primary_blocker": "Drugs@FDA contains only document action metadata (PDF letters), not structured MedDRA adverse reaction tables; FDA SrLC only covers Jan 2016-present with narrative text and Akamai anti-bot blocking; zero verified historical positive labels exist in the workspace."
            },
            "continuous_faers_coverage": {
                "decision": "CONDITIONAL GO",
                "condition": "Feasible to download 37 missing quarters (~2.0 GB compressed, ~11 GB uncompressed) via official FDA FIS URLs, but requires out-of-core chunked processing and explicit user approval before execution."
            },
            "model_training": {
                "decision": "NO-GO",
                "primary_blocker": "Cannot train without defensible, dated historical positive labels. Positive-Unlabeled learning is blocked because P is currently empty (N_P = 0). A targeted cohort of 100-250 drugs covers only 26-46% of pairs and introduces extreme immunosuppressive/biologic spectrum bias."
            }
        }
    }

    summary_json_path = os.path.join(AUDIT_DIR, "fda_temporal_audit_summary.json")
    with open(summary_json_path, "w") as f:
        json.dump(summary_data, f, indent=2)
    print(f"  Saved audit summary JSON: {summary_json_path}")

    print("\n" + "=" * 75)
    print("AUDIT EXECUTION COMPLETED")
    print("=" * 75)

if __name__ == "__main__":
    main()
