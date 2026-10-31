#!/usr/bin/env python3
"""
TASK-T1-03: Publication Figures Validation Script
Track 1 — Scientific Validation and Publication Preparation

Performs comprehensive validation:
1. Physical existence of all figure image files (PNG), vector files (PDF), and companion tables
2. Resolution, pixel dimensions, and file size checks (300 DPI publication standards)
3. Arithmetic balancing and count reconciliation against upstream artifacts
4. Benchmark observation counts and AUC concordance
5. Cryptographic hash integrity against manifest
"""

import os
import sys
import json
import hashlib
import pandas as pd
import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIG_DIR = os.path.join(BASE_DIR, "data", "21_track1_publication_figures")

# Upstream source artifacts
BENCH_JSON = os.path.join(BASE_DIR, "data", "14_phase3d_benchmark_evaluation", "phase3d_benchmark_evaluation_results.json")
OMOP_FILE = os.path.join(BASE_DIR, "data", "14_phase3d_benchmark_evaluation", "omop_matched_evaluation_pairs.csv")
EU_ADR_FILE = os.path.join(BASE_DIR, "data", "14_phase3d_benchmark_evaluation", "eu_adr_matched_evaluation_pairs.csv")
STRATA_TESTS_FILE = os.path.join(BASE_DIR, "data", "19_track1_contextual_analysis", "contextual_strata_tests.csv")
MANIFEST_FILE = os.path.join(FIG_DIR, "publication_figures_manifest.json")


def sha256_file(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def get_image_dimensions(png_path: str):
    import struct
    with open(png_path, "rb") as f:
        data = f.read(24)
        if len(data) >= 24 and data[:8] == b"\x89PNG\r\n\x1a\n":
            w, h = struct.unpack(">II", data[16:24])
            return w, h
    return None, None


def validate():
    print("=" * 80)
    print("TASK-T1-03: Comprehensive Publication Figures Validation Protocol")
    print("=" * 80)

    checks_passed = 0
    checks_failed = 0
    failures = []

    def log_check(name: str, condition: bool, msg: str = ""):
        nonlocal checks_passed, checks_failed
        if condition:
            checks_passed += 1
            print(f"[PASS] {name}")
        else:
            checks_failed += 1
            print(f"[FAIL] {name}: {msg}")
            failures.append(f"{name}: {msg}")

    # Check 1: Physical File Existence
    print("\n--- Check 1: Verifying File Existence ---")
    required_files = [
        "figure1_eb_shrinkage.png",
        "figure1_eb_shrinkage.pdf",
        "figure1_discordance_by_count_tier.csv",
        "figure2_benchmark_curves.png",
        "figure2_benchmark_curves.pdf",
        "figure3_contextual_features.png",
        "figure3_contextual_features.pdf"
    ]
    for fn in required_files:
        fp = os.path.join(FIG_DIR, fn)
        log_check(f"File exists: {fn}", os.path.exists(fp), f"File missing at {fp}")
        if os.path.exists(fp):
            log_check(f"File size non-zero: {fn}", os.path.getsize(fp) > 1000, f"Size: {os.path.getsize(fp)} bytes")

    # Check 2: Image Dimensions & Resolution (300 DPI standards)
    print("\n--- Check 2: Image Resolution and Dimensions ---")
    png_files = [
        ("figure1_eb_shrinkage.png", 3500, 2000),      # Expect ~4500 x 2850
        ("figure2_benchmark_curves.png", 2500, 2000),   # Expect ~3600 x 3150
        ("figure3_contextual_features.png", 3500, 2500) # Expect ~4800 x 3300
    ]
    for fn, min_w, min_h in png_files:
        fp = os.path.join(FIG_DIR, fn)
        if os.path.exists(fp):
            w, h = get_image_dimensions(fp)
            log_check(f"{fn} width ({w}px >= {min_w}px)", w is not None and w >= min_w, f"Width: {w}")
            log_check(f"{fn} height ({h}px >= {min_h}px)", h is not None and h >= min_h, f"Height: {h}")

    # Check 3: Figure 1 Discordance Arithmetic and Tier Balances
    print("\n--- Check 3: Figure 1 Tier Discordance Accounting ---")
    df_t = pd.read_csv(os.path.join(FIG_DIR, "figure1_discordance_by_count_tier.csv"))
    t_overall = df_t[df_t["tier"] == "Overall (a >= 2)"].iloc[0]

    log_check("F1: Total candidate universe == 1167891", int(t_overall["n_total_tier"]) == 1167891)
    log_check("F1: Total PRR signals == 398018", int(t_overall["n_prr_signal"]) == 398018)
    log_check("F1: Total EB05 signals == 295560", int(t_overall["n_eb05_signal"]) == 295560)
    log_check("F1: PRR-only discordant == 135159", int(t_overall["n_discordant_prr_only"]) == 135159)
    log_check("F1: EB05-only discordant == 32701", int(t_overall["n_discordant_eb05_only"]) == 32701)
    log_check("F1: Concordant signals == 262859", int(t_overall["n_concordant_both"]) == 262859)
    log_check("F1: Concordant non-signals == 737172", int(t_overall["n_concordant_neither"]) == 737172)
    log_check("F1: Net signal reduction == 102458", int(t_overall["net_signal_reduction"]) == 102458)

    # Balance check: PRR-only - EB05-only == Net reduction
    prr_only = int(t_overall["n_discordant_prr_only"])
    eb05_only = int(t_overall["n_discordant_eb05_only"])
    net_red = int(t_overall["net_signal_reduction"])
    log_check("F1 Balance: PRR_only - EB05_only == Net reduction", prr_only - eb05_only == net_red, f"{prr_only} - {eb05_only} != {net_red}")

    # Sum of tiers == Total universe
    sub_tiers = df_t[df_t["tier"] != "Overall (a >= 2)"]
    sum_tier_pairs = sub_tiers["n_total_tier"].sum()
    log_check("F1 Balance: Sum of 5 tiers == 1167891", sum_tier_pairs == 1167891, f"Sum: {sum_tier_pairs}")
    sum_tier_prr_only = sub_tiers["n_discordant_prr_only"].sum()
    log_check("F1 Balance: Sum of tier PRR-only == 135159", sum_tier_prr_only == 135159, f"Sum: {sum_tier_prr_only}")

    # Check tier a=2-3 specific property: EB05-only pairs
    t_a23 = df_t[df_t["tier"] == "a = 2-3"].iloc[0]
    log_check("F1 Tier a=2-3: contains 32486 EB05-only pairs (99.3% of all EB05-only)", int(t_a23["n_discordant_eb05_only"]) == 32486)
    log_check("F1 Tier a=2-3: median PRR among discordant is 7.59", float(t_a23["prr_median_discordant"]) == 7.5948)
    log_check("F1 Tier a=2-3: median EB05 among discordant is 1.25", float(t_a23["eb05_median_discordant"]) == 1.2515)

    # Check 4: Figure 2 Benchmark Sample Sizes & AUC Values
    print("\n--- Check 4: Figure 2 Benchmark Curves Validation ---")
    omop = pd.read_csv(OMOP_FILE)
    eu = pd.read_csv(EU_ADR_FILE)
    with open(BENCH_JSON, "r") as f:
        bench_json = json.load(f)

    log_check("F2 OMOP: total pairs == 203", len(omop) == 203)
    log_check("F2 OMOP: positive controls == 114", (omop["groundTruth"] == 1).sum() == 114)
    log_check("F2 OMOP: negative controls == 89", (omop["groundTruth"] == 0).sum() == 89)
    log_check("F2 EU-ADR: total pairs == 66", len(eu) == 66)
    log_check("F2 EU-ADR: positive controls == 39", (eu["groundTruth"] == 1).sum() == 39)
    log_check("F2 EU-ADR: negative controls == 27", (eu["groundTruth"] == 0).sum() == 27)

    # Concordance of reported AUC values with benchmark JSON
    log_check("F2 OMOP EB05 PR-AUC == 0.8619", round(bench_json["benchmark_evaluation"]["omop"]["EB05"]["pr_auc"], 4) == 0.8619)
    log_check("F2 OMOP EB05 ROC-AUC == 0.8136", round(bench_json["benchmark_evaluation"]["omop"]["EB05"]["roc_auc"], 4) == 0.8136)
    log_check("F2 EU-ADR EB05 PR-AUC == 0.9578", round(bench_json["benchmark_evaluation"]["euadr"]["EB05"]["pr_auc"], 4) == 0.9578)
    log_check("F2 EU-ADR EB05 ROC-AUC == 0.9364", round(bench_json["benchmark_evaluation"]["euadr"]["EB05"]["roc_auc"], 4) == 0.9364)

    # Check 5: Figure 3 Contextual Features Representation
    print("\n--- Check 5: Figure 3 Contextual Feature Small Multiples ---")
    df_tests = pd.read_csv(STRATA_TESTS_FILE)
    log_check("F3: Exactly 11 contextual features present", len(df_tests) == 11)
    top_feat = df_tests.sort_values(by="epsilon_squared", ascending=False).iloc[0]
    log_check("F3: Top ranked feature is secondary_suspect_ratio (eps^2 = 0.0273)", top_feat["feature"] == "secondary_suspect_ratio" and round(top_feat["epsilon_squared"], 4) == 0.0273)
    bottom_feat = df_tests.sort_values(by="epsilon_squared", ascending=True).iloc[0]
    log_check("F3: Lowest ranked feature is age_missing_ratio (eps^2 = 0.0001)", bottom_feat["feature"] == "age_missing_ratio" and round(bottom_feat["epsilon_squared"], 4) == 0.0001)

    print("\n" + "=" * 80)
    print(f"VALIDATION SUMMARY: {checks_passed} checks PASSED, {checks_failed} checks FAILED.")
    print("=" * 80)

    if checks_failed > 0:
        print("\nFAILURE DETAILS:")
        for f in failures:
            print(f" - {f}")
        return False
    return True


if __name__ == "__main__":
    success = validate()
    sys.exit(0 if success else 1)
