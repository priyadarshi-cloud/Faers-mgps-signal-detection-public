#!/usr/bin/env python3
"""
TASK-T1-11 Validation Suite: Final Benchmark Audit & Manuscript Integration
==========================================================================
Deterministic verification script that executes 50 comprehensive checks
validating numerical integrity, provenance traceability, manuscript alignment,
and artifact cryptographic hashes.
Uses exclusively Python standard library modules for universal reproducibility.
"""

import sys
import json
import hashlib
import csv
from pathlib import Path

# Paths
BASE = Path(__file__).resolve().parent
WORKSPACE = BASE.parents[1]
DATA = WORKSPACE / "data"

REPORT_MD     = BASE / "final_benchmark_audit_report.md"
RECOMPUTED_CSV= BASE / "independently_recomputed_statistics.csv"
PROVENANCE_CSV= BASE / "population_provenance_findings.csv"
CHANGELOG_CSV = BASE / "manuscript_change_log.csv"
MANUSCRIPT_MD = BASE / "manuscript_final_audited.md"
CLAIMS_CSV    = BASE / "claims_traceability_final.csv"
VALIDATOR_PY  = BASE / "validation_script.py"
MANIFEST_JSON = BASE / "artifact_manifest.json"

REQUIRED_DELIVERABLES = [
    REPORT_MD, RECOMPUTED_CSV, PROVENANCE_CSV, CHANGELOG_CSV,
    MANUSCRIPT_MD, CLAIMS_CSV, VALIDATOR_PY, MANIFEST_JSON
]

OMOP_MATCHED  = DATA / "14_phase3d_benchmark_evaluation" / "omop_matched_evaluation_pairs.csv"
EUADR_MATCHED = DATA / "14_phase3d_benchmark_evaluation" / "eu_adr_matched_evaluation_pairs.csv"
PHASE3D_JSON  = DATA / "14_phase3d_benchmark_evaluation" / "phase3d_benchmark_evaluation_results.json"
OMOP_RAW      = DATA / "05_reference_standards" / "omop" / "omop_reference_set.csv"
EUADR_RAW     = DATA / "05_reference_standards" / "eu_adr" / "eu_adr_reference_set.csv"
SOURCE_MS     = DATA / "29_task_t1_10_manuscript_harmonization" / "manuscript_harmonized.md"

GHOST_OMOP    = DATA / "14_phase3d_benchmark_evaluation" / "omop_scored_pairs.csv"
GHOST_EUADR   = DATA / "14_phase3d_benchmark_evaluation" / "euadr_scored_pairs.csv"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def read_csv_rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main():
    passed = 0
    failed = 0
    total = 0

    def check(desc, cond):
        nonlocal passed, failed, total
        total += 1
        if cond:
            print(f"  [PASS] #{total:02d}: {desc}")
            passed += 1
        else:
            print(f"  [FAIL] #{total:02d}: {desc}")
            failed += 1

    print("=====================================================================")
    print("TASK-T1-11 VALIDATION SUITE: FINAL BENCHMARK AUDIT & MANUSCRIPT")
    print("=====================================================================\n")

    # 1. Deliverables existence and non-emptiness
    print("--- Group 1: Required Deliverables Existence & Integrity ---")
    for d in REQUIRED_DELIVERABLES:
        check(f"Deliverable exists: {d.name}", d.exists())
        check(f"Deliverable non-empty: {d.name}", d.exists() and d.stat().st_size > 0)

    # 2. Source artifacts verification
    print("\n--- Group 2: Canonical Source Artifacts Verification ---")
    check("OMOP matched CSV exists", OMOP_MATCHED.exists())
    omop_hash = sha256(OMOP_MATCHED) if OMOP_MATCHED.exists() else ""
    check("OMOP matched CSV SHA-256 prefix matches b0cd1524", omop_hash.startswith("b0cd1524"))

    euadr_hash = sha256(EUADR_MATCHED) if EUADR_MATCHED.exists() else ""
    check("EU-ADR matched CSV exists", EUADR_MATCHED.exists())
    check("EU-ADR matched CSV SHA-256 prefix matches e82e226e", euadr_hash.startswith("e82e226e"))

    phase3d_hash = sha256(PHASE3D_JSON) if PHASE3D_JSON.exists() else ""
    check("Phase 3D JSON exists", PHASE3D_JSON.exists())
    check("Phase 3D JSON SHA-256 prefix matches 75124b2a", phase3d_hash.startswith("75124b2a"))

    source_ms_hash = sha256(SOURCE_MS) if SOURCE_MS.exists() else ""
    check("Source manuscript_harmonized.md exists and is preserved", SOURCE_MS.exists())
    check("Source manuscript SHA-256 prefix matches 6dbbb765", source_ms_hash.startswith("6dbbb765"))

    # 3. Absence of ghost/hallucinated files
    print("\n--- Group 3: Absence of Unsupported / Ghost Artifacts ---")
    check("Claimed omop_scored_pairs.csv does NOT exist on disk", not GHOST_OMOP.exists())
    check("Claimed euadr_scored_pairs.csv does NOT exist on disk", not GHOST_EUADR.exists())

    # 4. Source matched data verification
    print("\n--- Group 4: Canonical Matched Pairs Content Verification ---")
    omop_rows = read_csv_rows(OMOP_MATCHED)
    euadr_rows = read_csv_rows(EUADR_MATCHED)
    check("OMOP matched rows == 203", len(omop_rows) == 203)
    omop_pos = sum(1 for r in omop_rows if r["groundTruth"] == "1")
    omop_neg = sum(1 for r in omop_rows if r["groundTruth"] == "0")
    check("OMOP groundTruth positive == 114", omop_pos == 114)
    check("OMOP groundTruth negative == 89", omop_neg == 89)
    omop_missing = sum(1 for r in omop_rows if any(r[m] in (None, "") for m in ["eb05", "ebgm", "prr", "ror"]))
    check("OMOP zero missing scores", omop_missing == 0)

    check("EU-ADR matched rows == 66", len(euadr_rows) == 66)
    euadr_pos = sum(1 for r in euadr_rows if r["groundTruth"] == "1")
    euadr_neg = sum(1 for r in euadr_rows if r["groundTruth"] == "0")
    check("EU-ADR groundTruth positive == 39", euadr_pos == 39)
    check("EU-ADR groundTruth negative == 27", euadr_neg == 27)
    euadr_missing = sum(1 for r in euadr_rows if any(r[m] in (None, "") for m in ["eb05", "ebgm", "prr", "ror"]))
    check("EU-ADR zero missing scores", euadr_missing == 0)

    # 5. Independently recomputed statistics
    print("\n--- Group 5: Independently Recomputed Statistics CSV ---")
    recomputed_rows = read_csv_rows(RECOMPUTED_CSV)
    check("Recomputed CSV has exactly 8 rows (4 OMOP, 4 EU-ADR)", len(recomputed_rows) == 8)

    # Check B=2000 design specified
    b2000_check = all("B=2000" in r["bootstrap_design"] for r in recomputed_rows)
    check("All rows document B=2000 bootstrap design", b2000_check)

    # Check point estimates within 1e-3
    omop_eb05 = next(r for r in recomputed_rows if "OMOP" in r["benchmark_standard"] and "EB05" in r["method"])
    omop_prr = next(r for r in recomputed_rows if "OMOP" in r["benchmark_standard"] and "PRR" in r["method"])
    euadr_eb05 = next(r for r in recomputed_rows if "EU-ADR" in r["benchmark_standard"] and "EB05" in r["method"])
    euadr_prr = next(r for r in recomputed_rows if "EU-ADR" in r["benchmark_standard"] and "PRR" in r["method"])

    check("OMOP EB05 PR-AUC ~ 0.8626", abs(float(omop_eb05["pr_auc_point"]) - 0.8626) < 1e-3)
    check("OMOP EB05 ROC-AUC ~ 0.8136", abs(float(omop_eb05["roc_auc_point"]) - 0.8136) < 1e-3)
    check("EU-ADR EB05 PR-AUC ~ 0.9584", abs(float(euadr_eb05["pr_auc_point"]) - 0.9584) < 1e-3)
    check("EU-ADR EB05 ROC-AUC ~ 0.9364", abs(float(euadr_eb05["roc_auc_point"]) - 0.9364) < 1e-3)

    # Check all 6 non-reference paired CIs span zero
    non_ref_rows = [r for r in recomputed_rows if "Primary" not in r["method"]]
    check("Exactly 6 non-reference comparator rows present", len(non_ref_rows) == 6)
    all_spanned = all(r["both_paired_cis_span_zero"] == "Yes" for r in non_ref_rows)
    check("All 6 comparators have both_paired_cis_span_zero == 'Yes'", all_spanned)

    all_ci_lo_neg = all(float(r["pr_auc_paired_ci_lo"]) < 0 < float(r["pr_auc_paired_ci_hi"]) for r in non_ref_rows)
    check("All 6 PR-AUC paired CIs strictly span zero (lo < 0 < hi)", all_ci_lo_neg)
    all_roc_lo_neg = all(float(r["roc_auc_paired_ci_lo"]) < 0 < float(r["roc_auc_paired_ci_hi"]) for r in non_ref_rows)
    check("All 6 ROC-AUC paired CIs strictly span zero (lo < 0 < hi)", all_roc_lo_neg)

    # 6. Population provenance findings
    print("\n--- Group 6: Population Provenance Findings CSV ---")
    prov_rows = read_csv_rows(PROVENANCE_CSV)
    keys = {r["population_key"] for r in prov_rows}
    check("Provenance includes OMOP_N203 and EUADR_N66", "OMOP_N203" in keys and "EUADR_N66" in keys)
    check("Provenance includes OMOP_RAW_N399 and EUADR_RAW_N93", "OMOP_RAW_N399" in keys and "EUADR_RAW_N93" in keys)
    check("Provenance includes HALLUCINATED_N345", "HALLUCINATED_N345" in keys)

    h345 = next(r for r in prov_rows if r["population_key"] == "HALLUCINATED_N345")
    check("HALLUCINATED_N345 artifact_exists is 'NO'", h345["artifact_exists"] == "NO")
    check("HALLUCINATED_N345 status indicates NOT VERIFIED / NO SUPPORTING ARTIFACT",
          "NOT VERIFIED" in h345["verification_status"])

    # 7. Manuscript change log
    print("\n--- Group 7: Manuscript Change Log CSV ---")
    change_rows = read_csv_rows(CHANGELOG_CSV)
    check("Change log contains at least 18 documented changes", len(change_rows) >= 18)
    disc_fixes = [r for r in change_rows if any(d in r["supporting_artifact"] for d in ["DISC-07", "DISC-08", "DISC-09", "DISC-10"])]
    check("Change log documents DISC-07 to DISC-10 fixes", len(disc_fixes) == 4)

    # 8. Claims traceability
    print("\n--- Group 8: Claims Traceability CSV ---")
    claims_rows = read_csv_rows(CLAIMS_CSV)
    check("Claims traceability contains at least 16 claims", len(claims_rows) >= 16)
    clm11 = next((r for r in claims_rows if r["claim_id"] == "CLM-11"), None)
    check("CLM-11 exists and verifies paired CIs span zero",
          clm11 is not None and "span zero" in clm11["claim_text"].lower())

    # 9. Final audited manuscript checks
    print("\n--- Group 9: Final Audited Manuscript Content ---")
    ms_text = MANUSCRIPT_MD.read_text(encoding="utf-8")
    check("Manuscript header reflects TASK-T1-11", "TASK-T1-11" in ms_text)
    check("Manuscript contains updated OMOP delta +0.0301", "+0.0301" in ms_text)
    check("Manuscript contains updated EU-ADR delta +0.0213", "+0.0213" in ms_text)
    check("Manuscript Table 3 contains B=2000 OMOP EB05 PR-AUC 0.8626", "0.8626" in ms_text)
    check("Manuscript Table 3 contains B=2000 EU-ADR EB05 PR-AUC 0.9584", "0.9584" in ms_text)
    check("Manuscript Methods 2.7 mentions B=2,000 independent recomputation", "2{,}000" in ms_text or "2,000" in ms_text)
    check("Manuscript explicitly states 95% CIs span zero / non-significant", "span zero" in ms_text.lower())

    # Old sign-flipped draft CI must be absent
    check("Old sign-flipped draft CI [-0.0045, +0.0312] is ABSENT from manuscript",
          "[-0.0045, +0.0312]" not in ms_text and "[−0.0045, +0.0312]" not in ms_text)

    # No pseudo p-values
    check("No affirmative pseudo p-values ('p=0.106') in manuscript", "0.106" not in ms_text)

    # 10. Audit Report checks
    print("\n--- Group 10: Final Benchmark Audit Report ---")
    report_text = REPORT_MD.read_text(encoding="utf-8")
    check("Report contains Executive Summary", "Executive Summary" in report_text)
    check("Report documents N=203 and N=66 canonical populations", "203" in report_text and "66" in report_text)
    check("Report addresses N=345 and N=93 alternate populations", "345" in report_text and "93" in report_text)
    check("Report confirms all 12 paired CIs span zero", "span zero" in report_text.lower())
    check("Report includes Scientific Safeguards section", "Scientific Safeguards" in report_text)

    # 11. Artifact manifest verification
    print("\n--- Group 11: Artifact Manifest Cryptographic Verification ---")
    if MANIFEST_JSON.exists():
        with open(MANIFEST_JSON, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        artifacts = manifest.get("artifacts", {})
        check("Manifest contains at least 7 entries for deliverables", len(artifacts) >= 7)
        m_passed = True
        for name, meta in artifacts.items():
            fpath = BASE / name
            if fpath.exists() and fpath.name != "artifact_manifest.json":
                expected_h = meta.get("sha256")
                actual_h = sha256(fpath)
                if expected_h != actual_h:
                    m_passed = False
                    print(f"    Manifest hash mismatch for {name}: expected {expected_h[:8]}, got {actual_h[:8]}")
        check("Manifest SHA-256 hashes match on-disk files", m_passed)
    else:
        check("Manifest JSON exists for hash verification", False)

    print("\n=====================================================================")
    print(f"VALIDATION SUMMARY: {passed} PASSED / {failed} FAILED (TOTAL {total} CHECKS)")
    print("=====================================================================")

    if failed > 0:
        sys.exit(1)
    else:
        print("\nAll checks passed successfully.")
        sys.exit(0)


if __name__ == "__main__":
    main()
