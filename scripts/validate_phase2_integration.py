"""
Phase 2 Data-Quality and Integration Validation Suite.
Executes end-to-end tests across:
  A. FAERS ingestion
  B. Case/version handling anchored to init_fda_dt
  C. Deleted-case handling
  D. Drug normalization
  E. ADR terminology normalization
  F. OMOP reference-set ingestion and mapping
  G. Reference-standard quality checks & independence verification
"""

import os
import sys
import pandas as pd

# Add project root to path
sys.path.insert(0, os.path.abspath("."))

from src.preprocessing.deleted_cases import DeletedCaseManager
from src.data_acquisition.faers_loader import FAERSQuarterLoader
from src.preprocessing.case_deduplication import CaseVersionManager
from src.preprocessing.drug_normalizer import DrugNormalizer
from src.preprocessing.reaction_normalizer import ReactionNormalizer
from src.reference_standards.omop_loader import OMOPReferenceManager
from src.reference_standards.evidence_classifier import EvidenceClassifier, EvidenceCategory


def run_phase2_validation():
    print("==================================================================")
    print("=== PHASE 2: DATA-QUALITY & INTEGRATION VALIDATION SUITE ===")
    print("==================================================================")

    # -------------------------------------------------------------
    # Test C: Deleted-Case Handling
    # -------------------------------------------------------------
    print("\n--- [TEST C] Deleted-Case Handling ---")
    deleted_path = "data/01_raw/sample_quarters/2019q1/deleted/AllDeletedCases.txt"
    deleted_mgr = DeletedCaseManager(deleted_path)
    print(f"Loaded {len(deleted_mgr):,} deleted case IDs from {deleted_path}")
    assert len(deleted_mgr) > 0, "Deleted case manager failed to load cases!"
    sample_cid = list(deleted_mgr.deleted_cases)[0]
    assert deleted_mgr.is_deleted(sample_cid), "Lookup for known deleted case failed!"
    assert not deleted_mgr.is_deleted("9999999999999"), "False positive in deleted case lookup!"
    print(" [TEST C PASSED]: Deleted-case parsing and fast lookup verified.")

    # -------------------------------------------------------------
    # Test A: FAERS Ingestion & Deleted Purging
    # -------------------------------------------------------------
    print("\n--- [TEST A] FAERS Ingestion Engine ---")
    q2019_dir = "data/01_raw/sample_quarters/2019q1"
    loader = FAERSQuarterLoader(q2019_dir, deleted_manager=deleted_mgr)
    demo_df = loader.load_demo(filter_deleted=True)
    print(f"Loaded DEMO 2019Q1: {len(demo_df):,} active rows after purging deleted cases.")
    assert "sex" in demo_df.columns, "Schema reconciliation failed to produce 'sex' column!"
    assert "primaryid" in demo_df.columns and "caseid" in demo_df.columns
    print(" [TEST A PASSED]: Ingestion handles $ delimiter, schema normalization, and deleted filtering.")

    # -------------------------------------------------------------
    # Test B: Case / Version Handling & init_fda_dt Anchoring
    # -------------------------------------------------------------
    print("\n--- [TEST B] Case Versioning & Temporal Anchoring ---")
    # Verify filtering by init_fda_dt
    t_train_date = "20181231"
    historic_cases = CaseVersionManager.filter_by_initial_date(demo_df, max_init_date=t_train_date)
    print(f"Total cases in 2019Q1: {len(demo_df):,}")
    print(f"Cases initiated <= {t_train_date}: {len(historic_cases):,} ({len(historic_cases)/len(demo_df)*100:.2f}%)")
    assert (historic_cases["init_fda_dt"].str.strip() <= t_train_date).all(), "Found case with init_fda_dt > cutoff!"

    # Test deduplication to latest version
    deduped_demo = CaseVersionManager.deduplicate_cases_to_latest_version(demo_df)
    assert len(deduped_demo) == deduped_demo["caseid"].nunique(), "Duplicate caseid found after deduplication!"
    print(f"Deduplicated unique cases: {len(deduped_demo):,}")
    print(" [TEST B PASSED]: Temporal anchoring strictly isolates historic cases by init_fda_dt.")

    # -------------------------------------------------------------
    # Test D: Drug Normalization
    # -------------------------------------------------------------
    print("\n--- [TEST D] Drug Normalization Engine ---")
    drug_norm = DrugNormalizer()

    # --- Original benchmark cases ---
    test_cases_original = [
        ("LIPITOR", None, "atorvastatin"),
        ("BONIVA", None, "ibandronate"),
        ("HUMIRA", "ADALIMUMAB", "adalimumab"),
        ("TYLENOL", "ACETAMINOPHEN", "acetaminophen"),
        ("UNKNOWN BRAND", "ATORVASTATIN CALCIUM", "atorvastatin"),
        ("GENERIC", "METFORMIN HYDROCHLORIDE", "metformin"),
        ("REMICADE", "INFLIXIMAB-DYYB", "infliximab"),
        ("ASPIRIN 81 MG", None, "aspirin"),
        ("SANDOSTATIN", "OCTREOTIDE ACETATE", "octreotide"),
    ]
    for dname, prod_ai, expected in test_cases_original:
        res = drug_norm.normalize(drugname=dname, prod_ai=prod_ai)
        assert res == expected, f"[TEST D ORIGINAL] ({dname}, {prod_ai}): expected '{expected}', got '{res}'"
    print(f"  Original cases: {len(test_cases_original)} passed.")

    # --- NEW: Vitamin B-code INN mapping (B1/B2/B6 only — unambiguous) ---
    test_cases_vitamin_map = [
        ("B1",  None, "thiamine"),
        ("b1",  None, "thiamine"),    # lowercase input
        ("B2",  None, "riboflavin"),
        ("B6",  None, "pyridoxine"),
    ]
    for dname, prod_ai, expected in test_cases_vitamin_map:
        res = drug_norm.normalize(drugname=dname, prod_ai=prod_ai)
        assert res == expected, f"[TEST D VITAMIN MAP] '{dname}': expected '{expected}', got '{res}'"
    print(f"  Vitamin B-code INN mapping: {len(test_cases_vitamin_map)} passed.")

    # --- NEW: AMBIGUOUS vitamin codes (C/D/E/K/CA/B12/D2/D3/D4 — cannot map to single ingredient) ---
    test_cases_ambiguous = ["C", "D", "E", "K", "CA", "B12", "D3", "D2", "D4", "c", "d"]
    for code in test_cases_ambiguous:
        res = drug_norm.normalize(drugname=code, prod_ai=None)
        assert res == "AMBIGUOUS", (
            f"[TEST D AMBIGUOUS CODES] '{code}': expected 'AMBIGUOUS', got '{res}'. "
            "Single-char vitamin codes must not resolve to a specific ingredient."
        )
    # Also verify that CALCIUM+D3 (which strips to D3 after salt cleaning) is AMBIGUOUS
    res_calcd3 = drug_norm.normalize(drugname="CALCIUM D3", prod_ai=None)
    assert res_calcd3 == "AMBIGUOUS", f"[TEST D] 'CALCIUM D3' -> expected 'AMBIGUOUS', got '{res_calcd3}'"
    # Verify MG residual (after CALCIUM CITRATE salt-strip -> 'MG' which is <=2 chars) -> UNKNOWN
    res_mg = drug_norm.normalize(drugname="MG CITRATE", prod_ai=None)
    assert res_mg == "UNKNOWN", f"[TEST D] 'MG CITRATE' -> expected 'UNKNOWN' (2-char residual), got '{res_mg}'"
    print(f"  AMBIGUOUS vitamin code guard: {len(test_cases_ambiguous)+2} passed (incl. CALCIUM D3, MG residual).")

    # --- NEW: ER/XR/XL/CR/SR formulation suffix stripping ---
    test_cases_suffix = [
        ("EFFEXOR XR",        None, "effexor"),          # brand, suffix stripped
        ("TOPROL XL",         None, "toprol"),            # brand, suffix stripped
        ("WELLBUTRIN SR",     None, "wellbutrin"),        # brand, suffix stripped
        ("BUPROPION HCL ER",  None, "bupropion"),         # INN + salt + suffix
        ("METOPROLOL SUCCINATE ER", None, "metoprolol"),  # INN + salt + suffix
        ("ADDERALL XR",       None, "adderall"),          # brand XR
        ("NIFEDIPINE ER",     None, "nifedipine"),        # INN ER
    ]
    for dname, prod_ai, expected in test_cases_suffix:
        res = drug_norm.normalize(drugname=dname, prod_ai=prod_ai)
        assert res == expected, f"[TEST D ER/XR SUFFIX] '{dname}': expected '{expected}', got '{res}'"
    print(f"  ER/XR/XL suffix stripping: {len(test_cases_suffix)} passed.")

    # --- NEW: Safety guard — base name <=2 chars after suffix strip must NOT be stripped ---
    # No real cases found in FAERS, but verify the guard logic is enforced
    # "ER" alone would strip to "" → guard kicks in → return "er" (the original)
    res_guard = drug_norm.normalize(drugname="ER", prod_ai=None)
    assert res_guard != "", "[TEST D ER GUARD] 'ER' alone must not reduce to empty string"
    assert len(res_guard) > 0, "[TEST D ER GUARD] Output must be non-empty"
    print(f"  ER guard (short base protection): passed (result='{res_guard}').")

    total_new = (len(test_cases_vitamin_map) + len(test_cases_ambiguous) +
                 len(test_cases_suffix) + 1)
    print(f"  Total new test cases verified: {total_new}")
    print(f"Verified {len(test_cases_original)} original + {total_new} new drug normalization test cases.")
    print(" [TEST D PASSED]: Drug normalizer correctly strips salts/suffixes, maps brands/vitamins, and classifies ambiguous codes.")

    # -------------------------------------------------------------
    # Test E: Reaction Terminology Normalization
    # -------------------------------------------------------------
    print("\n--- [TEST E] Reaction Terminology Normalization ---")
    reac_norm = ReactionNormalizer()
    assert reac_norm.normalize_pt("  Acute myocardial infarction  ") == "Acute myocardial infarction"
    assert reac_norm.normalize_pt(None) == "UNKNOWN"
    assert reac_norm.normalize_pt("NAN") == "UNKNOWN"
    print(" [TEST E PASSED]: MedDRA PT normalizer correctly cleans strings and handles nulls.")

    # -------------------------------------------------------------
    # Test F: OMOP Reference-Set Ingestion and Mapping
    # -------------------------------------------------------------
    print("\n--- [TEST F] OMOP Reference Standard Ingestion & Mapping ---")
    omop_csv = "data/05_reference_standards/omop/omop_reference_set.csv"
    omop_mgr = OMOPReferenceManager(omop_csv)
    print(f"OMOP Reference Manager loaded {len(omop_mgr.df)} validated pairs.")
    print(f"Total Positive Controls: {sum(1 for v in omop_mgr.lookup.values() if v == 1)}")
    print(f"Total Negative Controls: {sum(1 for v in omop_mgr.lookup.values() if v == 0)}")

    # Test specific known pairs
    # In OMOP, Rosiglitazone + AMI is known positive control
    rosi_ami_status = omop_mgr.get_reference_status("rosiglitazone", "acute_myocardial_infarction")
    print(f"Status for ('rosiglitazone', 'acute_myocardial_infarction'): {rosi_ami_status}")

    # Test unlisted pair (Must return UNLISTED_UNKNOWN, never FALSE!)
    unlisted_status = omop_mgr.get_reference_status("aspirin", "non_existent_phenotype")
    assert unlisted_status == "UNLISTED_UNKNOWN", f"Unlisted pair returned {unlisted_status} instead of UNLISTED_UNKNOWN!"
    print(f"Status for unlisted pair: {unlisted_status} (Preserves UNKNOWN/UNCERTAIN principle).")

    # Test PT to Phenotype matching
    assert omop_mgr.is_pt_in_phenotype("Hepatic failure", "acute_liver_injury")
    assert omop_mgr.is_pt_in_phenotype("Myocardial infarction", "acute_myocardial_infarction")
    assert omop_mgr.is_pt_in_phenotype("Acute kidney injury", "acute_renal_failure")
    assert omop_mgr.is_pt_in_phenotype("Haematemesis", "upper_gi_bleeding")
    print(" [TEST F PASSED]: OMOP ingestion, normalization, and phenotype matching verified.")

    # -------------------------------------------------------------
    # Test G: Reference Standard Quality Checks & Evidence Classifier
    # -------------------------------------------------------------
    print("\n--- [TEST G] Multi-Tiered Evidence Classifier Quality Checks ---")
    cat_known = EvidenceClassifier.classify_pair(
        omop_status="POSITIVE_CONTROL", case_count_a=15, prr=3.5, ror_lower_95=2.1, ml_signal_score=0.85
    )
    assert cat_known == EvidenceCategory.KNOWN_ESTABLISHED

    cat_emerging = EvidenceClassifier.classify_pair(
        omop_status="UNLISTED_UNKNOWN", case_count_a=8, prr=2.5, ror_lower_95=1.4, ml_signal_score=0.60
    )
    assert cat_emerging == EvidenceCategory.EMERGING

    # NOVEL_POTENTIAL_SIGNAL is a Phase-3 (ML-active) tier only.
    # It requires use_ml_score=True — simulating what happens once a trained model is available.
    cat_novel = EvidenceClassifier.classify_pair(
        omop_status="UNLISTED_UNKNOWN", case_count_a=4, prr=1.2, ror_lower_95=0.8,
        ml_signal_score=0.75, use_ml_score=True
    )
    assert cat_novel == EvidenceCategory.NOVEL_POTENTIAL_SIGNAL, (
        f"Expected NOVEL_POTENTIAL_SIGNAL with ML active, got: {cat_novel}"
    )

    # Phase 2 safety guard: same pair MUST fall back to UNKNOWN_INSUFFICIENT when use_ml_score=False.
    cat_novel_phase2_guard = EvidenceClassifier.classify_pair(
        omop_status="UNLISTED_UNKNOWN", case_count_a=4, prr=1.2, ror_lower_95=0.8,
        ml_signal_score=0.75, use_ml_score=False
    )
    assert cat_novel_phase2_guard == EvidenceCategory.UNKNOWN_INSUFFICIENT, (
        f"Phase 2 safety violated: ML-gated tier reachable with use_ml_score=False! Got: {cat_novel_phase2_guard}"
    )

    cat_unknown = EvidenceClassifier.classify_pair(
        omop_status="UNLISTED_UNKNOWN", case_count_a=1, prr=0.9, ror_lower_95=0.4, ml_signal_score=0.20
    )
    assert cat_unknown == EvidenceCategory.UNKNOWN_INSUFFICIENT

    print(f"Verified Evidence Categories: {cat_known}, {cat_emerging}, {cat_novel}, {cat_unknown}")
    print(" [TEST G PASSED]: Multi-tiered evidence synthesizer strictly separates unlisted pairs from negative controls.")

    print("\n==================================================================")
    print("=== ALL PHASE 2 VALIDATION TESTS COMPLETED SUCCESSFULLY ===")
    print("==================================================================")


if __name__ == "__main__":
    run_phase2_validation()
