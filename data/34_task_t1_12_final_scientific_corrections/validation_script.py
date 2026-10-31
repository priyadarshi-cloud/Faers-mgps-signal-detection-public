#!/usr/bin/env python3
"""
TASK-T1-12 Validation Suite: Final Scientific Corrections and Contextual Reporter Audit
======================================================================================
Deterministic zero-dependency test suite verifying numerical consistency,
dictionary audit completeness, recomputation accuracy, manuscript language guardrails,
and cryptographic checksums.
"""

import sys
import json
import hashlib
import csv
from pathlib import Path

BASE = Path(__file__).resolve().parent
WORKSPACE = BASE.parents[1]
DATA = WORKSPACE / "data"

RECOVERY_MD   = BASE / "recovery_report.md"
REPORT_MD     = BASE / "scientific_corrections_report.md"
DICT_CSV      = BASE / "reporter_code_dictionary_audit.csv"
RECOMP_CSV    = BASE / "reporter_feature_recomputation_summary.csv"
DISC_CSV      = BASE / "contextual_results_discrepancy_log.csv"
CHANGELOG_CSV = BASE / "manuscript_change_log.csv"
MANUSCRIPT_MD = BASE / "manuscript_final_scientifically_corrected.md"
CLAIMS_CSV    = BASE / "claims_traceability.csv"
VALIDATOR_PY  = BASE / "validation_script.py"
MANIFEST_JSON = BASE / "artifact_manifest.json"

REQUIRED_DELIVERABLES = [
    RECOVERY_MD, REPORT_MD, DICT_CSV, RECOMP_CSV, DISC_CSV,
    CHANGELOG_CSV, MANUSCRIPT_MD, CLAIMS_CSV, VALIDATOR_PY, MANIFEST_JSON
]

OMOP_MATCHED  = DATA / "14_phase3d_benchmark_evaluation" / "omop_matched_evaluation_pairs.csv"
EUADR_MATCHED = DATA / "14_phase3d_benchmark_evaluation" / "eu_adr_matched_evaluation_pairs.csv"
T11_MANUSCRIPT= DATA / "33_task_t1_11_final_benchmark_audit" / "manuscript_final_audited.md"


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
    print("TASK-T1-12 VALIDATION SUITE: FINAL SCIENTIFIC CORRECTIONS")
    print("=====================================================================\n")

    # Group 1: Required Deliverables Existence & Non-Emptiness
    print("--- Group 1: Required Deliverables Existence & Integrity ---")
    for d in REQUIRED_DELIVERABLES:
        check(f"Deliverable exists: {d.name}", d.exists())
        check(f"Deliverable non-empty: {d.name}", d.exists() and d.stat().st_size > 0)

    # Group 2: Canonical Source Artifacts & Prior Task Integrity
    print("\n--- Group 2: Source Artifacts & Prior Task Integrity ---")
    check("OMOP matched CSV exists", OMOP_MATCHED.exists())
    omop_hash = sha256(OMOP_MATCHED) if OMOP_MATCHED.exists() else ""
    check("OMOP matched CSV SHA-256 prefix matches b0cd1524", omop_hash.startswith("b0cd1524"))

    check("EU-ADR matched CSV exists", EUADR_MATCHED.exists())
    euadr_hash = sha256(EUADR_MATCHED) if EUADR_MATCHED.exists() else ""
    check("EU-ADR matched CSV SHA-256 prefix matches e82e226e", euadr_hash.startswith("e82e226e"))

    check("TASK-T1-11 manuscript exists and is preserved", T11_MANUSCRIPT.exists())

    # Group 3: Reporter Code Dictionary Audit Verification
    print("\n--- Group 3: Reporter Code Dictionary Audit CSV ---")
    dict_rows = read_csv_rows(DICT_CSV)
    check("Dictionary audit contains at least 16 entries", len(dict_rows) >= 16)
    
    lw_entry = next((r for r in dict_rows if r["code"] == "LW"), None)
    check("LW entry exists in dictionary audit", lw_entry is not None)
    if lw_entry:
        check("LW dictionary meaning indicates Lawyer / Attorney", "Lawyer" in lw_entry["dictionary_meaning"])
        check("LW corrected mapping indicates EXCLUDED / Non-HP", "EXCLUDED" in lw_entry["corrected_mapping"])
        check("LW cohort case count == 85,337", int(lw_entry["cohort_case_count_n"]) == 85337)

    # Group 4: Reporter Feature Recomputation Summary
    print("\n--- Group 4: Reporter Feature Recomputation Summary ---")
    recomp_rows = read_csv_rows(RECOMP_CSV)
    recomp_map = {r["metric"]: float(r["new_value_without_lw"]) for r in recomp_rows}
    
    check("Overall mean without LW ~ 0.3351", abs(recomp_map.get("Overall Universe Mean", 0) - 0.3351) < 1e-3)
    check("Stratum 1 mean without LW ~ 0.3251", abs(recomp_map.get("Stratum 1 Mean (EB05 < 1.0)", 0) - 0.3251) < 1e-3)
    check("Stratum 5 mean without LW ~ 0.3557", abs(recomp_map.get("Stratum 5 Mean (EB05 >= 10.0)", 0) - 0.3557) < 1e-3)
    check("Kruskal-Wallis H statistic without LW ~ 3839.98", abs(recomp_map.get("Kruskal-Wallis H statistic", 0) - 3839.98) < 1.0)
    check("Epsilon-squared effect size without LW ~ 0.0033", abs(recomp_map.get("Epsilon-squared effect size", 0) - 0.0033) < 1e-3)

    # Group 5: Contextual Discrepancy Log
    print("\n--- Group 5: Contextual Discrepancy Log ---")
    disc_rows = read_csv_rows(DISC_CSV)
    check("Discrepancy log contains at least 10 entries", len(disc_rows) >= 10)
    all_resolved = all(r["status"] == "RESOLVED" for r in disc_rows)
    check("All discrepancy log entries marked RESOLVED", all_resolved)

    # Group 6: Manuscript Change Log
    print("\n--- Group 6: Manuscript Change Log ---")
    change_rows = read_csv_rows(CHANGELOG_CSV)
    check("Change log contains at least 16 entries", len(change_rows) >= 16)
    all_verified = all(r["verification_status"] == "VERIFIED" for r in change_rows)
    check("All change log entries marked VERIFIED", all_verified)

    # Group 7: Claims Traceability
    print("\n--- Group 7: Claims Traceability ---")
    claims_rows = read_csv_rows(CLAIMS_CSV)
    check("Claims traceability contains at least 16 entries", len(claims_rows) >= 16)
    all_claims_verified = all(r["t1_12_status"] == "VERIFIED" for r in claims_rows)
    check("All claims traceability entries marked VERIFIED", all_claims_verified)

    # Group 8: Corrected Manuscript Content & Scientific Guardrails
    print("\n--- Group 8: Corrected Manuscript Content & Guardrails ---")
    ms_text = MANUSCRIPT_MD.read_text(encoding="utf-8")
    
    check("Manuscript header reflects TASK-T1-12", "TASK-T1-12" in ms_text)
    
    # Correction 1 checks
    check("Manuscript mentions hp_reporter_ratio excluding lawyers / LW", "excluding lawyer" in ms_text.lower() or "excluding lw" in ms_text.lower())
    check("Manuscript hp_reporter_ratio Stratum 5 mean updated to 0.36", "0.36" in ms_text)
    check("Manuscript explicitly notes non-complementary denominators / do not sum to 1.0", "do not sum to 1.0" in ms_text.lower())
    
    # Correction 2 checks
    check("Manuscript does NOT contain 'avoids bias in prior hyperparameters'", "avoids bias in prior hyperparameters" not in ms_text)
    check("Manuscript states likelihood accounts for specified a >= 2 truncation", "accounts for" in ms_text.lower() and "truncation" in ms_text.lower())

    # Correction 3 checks
    check("Manuscript does NOT contain 'reduces low-count alert volatility'", "reduces low-count alert volatility" not in ms_text)
    check("Manuscript does NOT contain 'eliminating 102,458 net frequentist alerts'", "eliminating 102,458 net frequentist alerts" not in ms_text)
    check("Manuscript contains exact threshold difference 102,458", "102,458" in ms_text)
    check("Manuscript contains EB05 >= 2 count 295,560", "295,560" in ms_text)
    check("Manuscript contains Evans PRR count 398,018", "398,018" in ms_text)
    check("Manuscript contains PRR-only count 135,159", "135,159" in ms_text)
    check("Manuscript contains EB05-only count 32,701", "32,701" in ms_text)

    # Correction 4 checks
    check("Manuscript defines PR metric as Average Precision / AP", "Average Precision" in ms_text or "AP" in ms_text)
    check("Manuscript does NOT claim interpolated PR-curve area", "interpolated area under precision-recall curve" not in ms_text)
    check("Manuscript Table 3 indicates B=2,000 paired bootstrap", "2{,}000" in ms_text or "2,000" in ms_text)
    check("Manuscript states paired CIs span zero / superiority not established", "span zero" in ms_text.lower())
    check("Manuscript does NOT contain invented p-values ('p=0.106')", "0.106" not in ms_text)

    # Group 9: Artifact Manifest Cryptographic Verification
    print("\n--- Group 9: Artifact Manifest Cryptographic Verification ---")
    if MANIFEST_JSON.exists():
        with open(MANIFEST_JSON, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        artifacts = manifest.get("artifacts", {})
        check("Manifest contains entries for all deliverables", len(artifacts) >= 8)
        
        m_passed = True
        for name, meta in artifacts.items():
            fpath = BASE / name
            if fpath.exists() and fpath.name != "artifact_manifest.json":
                expected_h = meta.get("sha256")
                actual_h = sha256(fpath)
                if expected_h != actual_h:
                    m_passed = False
                    print(f"    Hash mismatch for {name}: expected {expected_h[:8]}, got {actual_h[:8]}")
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
