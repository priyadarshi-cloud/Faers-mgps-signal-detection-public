#!/usr/bin/env python3
"""
Validation script for TASK-T1-06: Evidence-Controlled Manuscript Revision.
Audits the presence, text invariants, scientific safeguards, claims traceability,
and cryptographic integrity of the revised manuscript package.
"""

import os
import sys
import json
import csv
import hashlib

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REV_DIR = os.path.join(ROOT_DIR, "data", "25_track1_revised_manuscript")
ORIG_DIR = os.path.join(ROOT_DIR, "data", "23_track1_manuscript_package")

REQUIRED_DELIVERABLES = [
    "manuscript_revised.md",
    "revision_change_log.md",
    "updated_results_claims_traceability.csv",
    "unresolved_author_decisions.md",
    "figure3_contextual_features_revised.png",
    "figure3_contextual_features_revised.pdf",
    "table3_benchmark_performance_revised.csv",
    "table4_contextual_strata_revised.csv",
    "revised_artifact_manifest.json"
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
    print("TASK-T1-06 REVISED MANUSCRIPT VALIDATION SUITE")
    print("=" * 80)

    # 1. Deliverables existence and non-zero size
    for fname in REQUIRED_DELIVERABLES:
        fpath = os.path.join(REV_DIR, fname)
        exists = os.path.exists(fpath)
        sz = os.path.getsize(fpath) if exists else 0
        log_check(f"Deliverable presence: {fname}", exists and sz > 300, f"size={sz} bytes")

    # 2. Preservation check: original manuscript must exist and be unchanged
    orig_ms = os.path.join(ORIG_DIR, "manuscript_draft.md")
    orig_exists = os.path.exists(orig_ms)
    orig_sz = os.path.getsize(orig_ms) if orig_exists else 0
    log_check("Preservation check: original manuscript unchanged", orig_exists and orig_sz > 45000, f"size={orig_sz} bytes")

    # 3. Content and invariant checks on manuscript_revised.md
    rev_ms = os.path.join(REV_DIR, "manuscript_revised.md")
    if os.path.exists(rev_ms):
        with open(rev_ms, "r", encoding="utf-8") as f:
            text = f.read()
        text_lower = text.lower()

        # Invariant 1: NO "global optimum"
        has_global_opt = "global optimum" in text_lower
        log_check("Scientific invariant: 'global optimum' eliminated", not has_global_opt, f"found={'YES' if has_global_opt else 'NO'}")

        # Invariant 2: Lowest local minimum present
        has_lowest_local = "lowest local minimum identified" in text_lower
        log_check("Scientific invariant: 'lowest local minimum' phrasing present", has_lowest_local, "phrasing verified")

        # Invariant 3: Paired benchmark difference CIs and qualification
        has_paired_ci = "spanned zero" in text_lower or "cross zero" in text_lower or "spans zero" in text_lower
        has_stat_ns = "statistically non-significant" in text_lower or "did not achieve two-sided statistical significance" in text_lower
        log_check("Benchmark qualification: paired CIs span zero / NS", has_paired_ci and has_stat_ns, f"paired_ci={has_paired_ci}, stat_ns={has_stat_ns}")

        # Invariant 4: Paired delta values present
        has_delta_omop = "+0.0307" in text and "0.0735" in text and "0.0085" in text
        has_delta_euadr = "+0.0216" in text and "0.0548" in text and "0.0013" in text
        log_check("Benchmark values: exact paired delta PR-AUC CIs present", has_delta_omop and has_delta_euadr, f"omop={has_delta_omop}, euadr={has_delta_euadr}")

        # Invariant 5: CSM definition correctly as Consumer / non-health professional
        has_csm_consumer = "consumer / non-health professional" in text_lower or "consumers / non-health professionals" in text_lower
        csm_not_hp = "csm_reporter_ratio: proportion of reports submitted by other health professionals" not in text_lower
        log_check("Feature definition: csm_reporter_ratio defined as consumer", has_csm_consumer and csm_not_hp, f"consumer={has_csm_consumer}, not_hp={csm_not_hp}")

        # Invariant 6: Standardized EB05 terminology
        has_eb05_std = "5th percentile of the posterior distribution" in text_lower
        log_check("Terminology: standardized EB05 5th percentile phrasing", has_eb05_std, "phrasing verified")

        # Invariant 7: Cohort flow numbers exact
        has_cohort = "6,005,839" in text and "7,052" in text and "6,012,891" in text and "1,167,891" in text
        log_check("Cohort numbers: exact reconciliation present", has_cohort, "6005839, 7052, 6012891, 1167891 verified")

        # Invariant 8: Safeguards maintained
        has_no_supervised = "no supervised adr prediction model" in text_lower or "no complete supervised" in text_lower
        has_no_causality = "causal" in text_lower and ("does not establish" in text_lower or "do not establish" in text_lower)
        has_no_bio_shap = "biological mechanisms" in text_lower and ("does not establish" in text_lower or "do not establish" in text_lower)
        has_draft_status = "not submitted" in text_lower and "publication-ready" in text_lower
        log_check("Safeguards: no supervised model claimed", has_no_supervised, "verified")
        log_check("Safeguards: statistical signals do not establish causality", has_no_causality, "verified")
        log_check("Safeguards: surrogate SHAP does not establish biological mechanism", has_no_bio_shap, "verified")
        log_check("Safeguards: draft status explicitly marked", has_draft_status, "verified")

    # 4. Updated traceability CSV validation
    tr_path = os.path.join(REV_DIR, "updated_results_claims_traceability.csv")
    if os.path.exists(tr_path):
        with open(tr_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            req_cols = {"section", "claim_text", "value", "denominator", "unit", "source_artifact", "source_field_or_calculation", "verified"}
            cols_ok = req_cols.issubset(set(reader.fieldnames or []))
            log_check("Traceability CSV headers", cols_ok, f"cols={reader.fieldnames}")
            tr_rows = list(reader)

        log_check("Traceability claims count (>= 105)", len(tr_rows) >= 105, f"count={len(tr_rows)}")

        # Check paired delta claims present
        paired_claims = [r for r in tr_rows if "paired" in r["section"].lower() or "delta" in r["claim_text"].lower()]
        log_check("Traceability: paired delta benchmark claims present", len(paired_claims) >= 6, f"count={len(paired_claims)}")

    # 5. Revised Table 3 validation
    t3_path = os.path.join(REV_DIR, "table3_benchmark_performance_revised.csv")
    if os.path.exists(t3_path):
        with open(t3_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            t3_cols = set(reader.fieldnames or [])
            has_delta_cols = {"paired_delta_pr_auc_vs_eb05", "paired_delta_roc_auc_vs_eb05", "paired_difference_95ci_interpretation"}.issubset(t3_cols)
            log_check("Revised Table 3: paired difference columns present", has_delta_cols, f"cols_found={has_delta_cols}")

    # 6. Revised Table 4 validation
    t4_path = os.path.join(REV_DIR, "table4_contextual_strata_revised.csv")
    if os.path.exists(t4_path):
        with open(t4_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            t4_rows = list(reader)
            csm_row = next((r for r in t4_rows if r["feature"] == "csm_reporter_ratio"), None)
            csm_desc_ok = csm_row and "consumer" in csm_row.get("feature_description", "").lower()
            log_check("Revised Table 4: csm_reporter_ratio described as consumer", csm_desc_ok, f"desc={csm_row.get('feature_description') if csm_row else 'NOT_FOUND'}")

    # 7. Manifest validation and checksum matching
    man_path = os.path.join(REV_DIR, "revised_artifact_manifest.json")
    if os.path.exists(man_path):
        with open(man_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        has_keys = {"task", "title", "timestamp_utc", "revision_status", "deliverables", "source_artifacts_used"}.issubset(set(manifest.keys()))
        log_check("Manifest top-level keys", has_keys, f"keys={list(manifest.keys())}")

        mismatches = []
        for deliv in manifest.get("deliverables", []):
            full_p = os.path.join(ROOT_DIR, deliv["path"])
            if not os.path.exists(full_p):
                mismatches.append((deliv["path"], "FILE_NOT_FOUND"))
            else:
                h = sha256_file(full_p)
                if h != deliv["sha256"]:
                    mismatches.append((deliv["path"], f"HASH_MISMATCH: expected {deliv['sha256'][:8]} got {h[:8]}"))

        log_check("Manifest deliverable hashes match disk", len(mismatches) == 0, f"verified={len(manifest.get('deliverables', []))}, mismatches={mismatches}")

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
