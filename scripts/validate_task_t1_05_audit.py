#!/usr/bin/env python3
"""
Validation script for TASK-T1-05: Critical Scientific Consistency Audit.
Audits the presence, internal consistency, mathematical reconciliation,
statistical rigor, and cryptographic hashes of the audit deliverables.
"""

import os
import sys
import json
import csv
import hashlib

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIT_DIR = os.path.join(ROOT_DIR, "data", "24_task_t1_05_scientific_consistency_audit")

REQUIRED_DELIVERABLES = [
    "scientific_consistency_audit_report.md",
    "numerical_discrepancies.csv",
    "cohort_reconciliation.csv",
    "mgps_likelihood_audit.md",
    "benchmark_uncertainty_audit.md",
    "author_decisions_required.md",
    "audit_manifest.json"
]

def sha256_file(filepath):
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def run_validations():
    checks = []

    def log_check(name, passed, detail=""):
        status = "PASS" if passed else "FAIL"
        checks.append({"name": name, "status": status, "detail": detail})
        print(f"[{status}] {name}: {detail}")

    print("=" * 80)
    print("TASK-T1-05 SCIENTIFIC CONSISTENCY AUDIT VALIDATION SUITE")
    print("=" * 80)

    # 1. Deliverables existence and non-zero size
    for fname in REQUIRED_DELIVERABLES:
        fpath = os.path.join(AUDIT_DIR, fname)
        exists = os.path.exists(fpath)
        sz = os.path.getsize(fpath) if exists else 0
        log_check(f"Deliverable presence: {fname}", exists and sz > 300, f"size={sz} bytes")

    # 2. Cohort reconciliation CSV validation
    cr_path = os.path.join(AUDIT_DIR, "cohort_reconciliation.csv")
    if os.path.exists(cr_path):
        with open(cr_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            req_cols = {"stage", "cohort_or_step", "case_or_pair_count", "count_unit", "inclusion_exclusion_rule", "source_file", "source_field_or_calculation", "status"}
            cols_ok = req_cols.issubset(set(reader.fieldnames or []))
            log_check("Cohort reconciliation CSV headers", cols_ok, f"cols={reader.fieldnames}")
            rows = list(reader)

        row_map = {r["cohort_or_step"]: int(r["case_or_pair_count"]) for r in rows if r["case_or_pair_count"].isdigit()}

        # Verify exact counts
        as_of_2018 = row_map.get("as_of_2018_receipt_bounded_snapshot")
        backfills = row_map.get("post_2018q4_backfilled_cases")
        primary_cohort = row_map.get("physical_archive_bounded_feature_cohort")
        deletions = row_map.get("fda_retrospective_deletions")
        corrected = row_map.get("retrospectively_corrected_snapshot")
        universe = row_map.get("candidate_pairs_universe_a_ge_2")
        sparse = row_map.get("candidate_pairs_sparse_tier_a_eq_2")
        dense = row_map.get("candidate_pairs_dense_tier_a_ge_3")

        log_check("Cohort count: as_of_2018 (6,012,891)", as_of_2018 == 6012891, f"val={as_of_2018}")
        log_check("Cohort count: backfills (7,052)", backfills == 7052, f"val={backfills}")
        log_check("Cohort count: primary cohort (6,005,839)", primary_cohort == 6005839, f"val={primary_cohort}")
        log_check("Cohort count: deletions (25,718)", deletions == 25718, f"val={deletions}")
        log_check("Cohort count: corrected (5,987,173)", corrected == 5987173, f"val={corrected}")
        log_check("Universe count: total candidate pairs (1,167,891)", universe == 1167891, f"val={universe}")
        log_check("Universe count: sparse tier a=2 (335,816)", sparse == 335816, f"val={sparse}")
        log_check("Universe count: dense tier a>=3 (832,075)", dense == 832075, f"val={dense}")

        # Mathematical consistency
        math_cohort_ok = (as_of_2018 - backfills == primary_cohort)
        math_deletions_ok = (as_of_2018 - deletions == corrected)
        math_universe_ok = (sparse + dense == universe)
        log_check("Mathematical reconciliation: primary cohort (6012891 - 7052 = 6005839)", math_cohort_ok, f"{as_of_2018} - {backfills} == {primary_cohort}")
        log_check("Mathematical reconciliation: retrospective deletions (6012891 - 25718 = 5987173)", math_deletions_ok, f"{as_of_2018} - {deletions} == {corrected}")
        log_check("Mathematical reconciliation: candidate tiers (335816 + 832075 = 1167891)", math_universe_ok, f"{sparse} + {dense} == {universe}")

    # 3. Numerical discrepancies CSV validation
    nd_path = os.path.join(AUDIT_DIR, "numerical_discrepancies.csv")
    if os.path.exists(nd_path):
        with open(nd_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            req_cols = {"finding_id", "category", "severity", "item_description", "manuscript_text", "authoritative_source_artifact", "authoritative_value", "impact_assessment", "recommended_resolution"}
            cols_ok = req_cols.issubset(set(reader.fieldnames or []))
            log_check("Numerical discrepancies CSV headers", cols_ok, f"cols={reader.fieldnames}")
            nd_rows = list(reader)

        severities = {r["severity"] for r in nd_rows}
        valid_sevs = {"Critical", "Major", "Minor", "Verified"}
        log_check("Numerical discrepancies severities valid", severities.issubset(valid_sevs), f"severities={severities}")

        finding_ids = [r["finding_id"] for r in nd_rows]
        log_check("Numerical discrepancies IDs unique", len(finding_ids) == len(set(finding_ids)), f"total={len(finding_ids)}")

        has_csm = any("CSM" in r["finding_id"] for r in nd_rows)
        has_opt = any("GLOBAL" in r["finding_id"] for r in nd_rows)
        has_bench = any("BENCH" in r["finding_id"] for r in nd_rows)
        log_check("Key findings present (CSM, Global Optimum, Benchmark Uncertainty)", all([has_csm, has_opt, has_bench]), f"csm={has_csm}, opt={has_opt}, bench={has_bench}")

    # 4. MGPS likelihood audit document validation
    mgps_path = os.path.join(AUDIT_DIR, "mgps_likelihood_audit.md")
    if os.path.exists(mgps_path):
        with open(mgps_path, "r", encoding="utf-8") as f:
            mgps_text = f.read().lower()

        kw_mgps = [
            "betainc",
            "logsumexp",
            "logarithmic binning",
            "brentq",
            "0.0010",
            "lowest local minimum identified",
            "ranking stability from parameter identification"
        ]
        log_check("MGPS likelihood audit technical content", all(k in mgps_text for k in kw_mgps), f"verified keywords: {len(kw_mgps)}")

    # 5. Benchmark uncertainty audit document validation
    bu_path = os.path.join(AUDIT_DIR, "benchmark_uncertainty_audit.md")
    if os.path.exists(bu_path):
        with open(bu_path, "r", encoding="utf-8") as f:
            bu_text = f.read().lower()

        kw_bu = [
            "omop reference standard (n = 203",
            "eu-adr reference standard (n = 66",
            "0.8619",
            "0.9578",
            "+0.0307",
            "[-0.0085, +0.0735]",
            "+0.0216",
            "[-0.0013, +0.0548]",
            "includes zero",
            "significant at"
        ]
        log_check("Benchmark uncertainty audit paired statistics", all(k in bu_text for k in kw_bu), f"verified keywords: {len(kw_bu)}")

    # 6. Author decisions document validation
    ad_path = os.path.join(AUDIT_DIR, "author_decisions_required.md")
    if os.path.exists(ad_path):
        with open(ad_path, "r", encoding="utf-8") as f:
            ad_text = f.read().lower()

        kw_ad = [
            "## 1. verified scientific facts",
            "## 2. unresolved methodological questions",
            "## 3. decisions requiring human author confirmation before submission",
            "csm_reporter_ratio",
            "global optimum",
            "paired benchmark statistical uncertainty"
        ]
        log_check("Author decisions document structure", all(k in ad_text for k in kw_ad), f"verified keywords: {len(kw_ad)}")

    # 7. Audit report document validation
    rep_path = os.path.join(AUDIT_DIR, "scientific_consistency_audit_report.md")
    if os.path.exists(rep_path):
        with open(rep_path, "r", encoding="utf-8") as f:
            rep_text = f.read().lower()

        kw_rep = [
            "## 1. executive summary",
            "## 2. detailed findings by scope",
            "## 3. summary of findings",
            "## 4. prioritized action plan for manuscript revision",
            "scope 1", "scope 2", "scope 3", "scope 4", "scope 5"
        ]
        log_check("Audit report comprehensive sections", all(k in rep_text for k in kw_rep), f"verified keywords: {len(kw_rep)}")

    # 8. Manifest validation and checksum matching
    man_path = os.path.join(AUDIT_DIR, "audit_manifest.json")
    if os.path.exists(man_path):
        with open(man_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        has_keys = {"task", "title", "audit_verdict", "findings_summary", "deliverables", "source_artifacts_audited"}.issubset(set(manifest.keys()))
        log_check("Audit manifest required keys", has_keys, f"keys={list(manifest.keys())}")

        mismatches = []
        for deliv in manifest.get("deliverables", []):
            full_p = os.path.join(ROOT_DIR, deliv["path"])
            if not os.path.exists(full_p):
                mismatches.append((deliv["path"], "FILE_NOT_FOUND"))
            else:
                h = sha256_file(full_p)
                if h != deliv["sha256"]:
                    mismatches.append((deliv["path"], f"HASH_MISMATCH: expected {deliv['sha256'][:8]} got {h[:8]}"))

        log_check("Audit manifest deliverable hashes match disk", len(mismatches) == 0, f"verified={len(manifest.get('deliverables', []))}, mismatches={mismatches}")

    # Summary
    total_checks = len(checks)
    passed_checks = sum(1 for c in checks if c["status"] == "PASS")
    failed_checks = sum(1 for c in checks if c["status"] == "FAIL")

    print("=" * 80)
    print(f"VALIDATION SUMMARY: {passed_checks}/{total_checks} CHECKS PASSED ({(passed_checks/total_checks)*100:.1f}%)")
    if failed_checks > 0:
        print(f"FAILED CHECKS ({failed_checks}):")
        for c in checks:
            if c["status"] == "FAIL":
                print(f"  - {c['name']}: {c['detail']}")
    print("=" * 80)

    return failed_checks == 0

if __name__ == "__main__":
    success = run_validations()
    sys.exit(0 if success else 1)
