"""
Phase 3A.4 — Automated Tests for Version-Safe Demographic Join & Role Prioritization.

Validates:
1. Cross-version leakage prevention: unselected follow-up versions cannot leak into canonical pairs.
2. Demographic fidelity: demographic attributes correspond strictly to the selected report version.
3. Multi-drug preservation: legitimate multiple medications on the same report are preserved.
4. Multi-reaction preservation: legitimate multiple adverse events on the same report are preserved.
5. Role-code prioritization: Primary Suspect (PS) takes deterministic precedence over Secondary Suspect (SS).
6. Cohort pre- vs post-fix comparative quantification.

Run with:
    python scripts/test_version_safe_join.py
"""

from __future__ import annotations

import sys
import os

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import pandas as pd
import numpy as np

from src.pipeline.pair_builder import PairBuilder

PASS = "✅ PASS"
FAIL = "❌ FAIL"
results = []


def run_test(name: str, fn):
    try:
        fn()
        results.append({"test": name, "status": PASS, "note": ""})
        print(f"  {PASS}  {name}")
    except AssertionError as e:
        results.append({"test": name, "status": FAIL, "note": str(e)})
        print(f"  {FAIL}  {name}\n         → {e}")
    except Exception as e:
        results.append({"test": name, "status": FAIL, "note": f"Exception: {e}"})
        print(f"  {FAIL}  {name}\n         → Exception: {e}")


pb = PairBuilder()


# ===========================================================================
# Test 1 — Cross-version leakage strictly prevented
# ===========================================================================
def test_cross_version_leakage_prevented():
    """
    Case C1 has:
      - Version 1 (primaryid=101): age=50, sex=M, drug=METFORMIN, reaction=Nausea
      - Version 2 (primaryid=102): age=65, sex=F, drug=LISINOPRIL, reaction=Cough
    Canonical DEMO contains ONLY Version 1.
    Expected:
      - ONLY 1 pair is produced (primaryid=101, METFORMIN, Nausea, age=50, sex=M).
      - Zero attributes from Version 2 (LISINOPRIL, Cough, age 65, sex F) appear.
    """
    demo_df = pd.DataFrame([{"caseid": "C1", "primaryid": "101", "age": "50", "sex": "M"}])
    drug_raw = pd.DataFrame([
        {"primaryid": "101", "caseid": "C1", "drugname": "METFORMIN", "role_cod": "PS"},
        {"primaryid": "102", "caseid": "C1", "drugname": "LISINOPRIL", "role_cod": "PS"},
    ])
    reac_raw = pd.DataFrame([
        {"primaryid": "101", "caseid": "C1", "pt": "Nausea"},
        {"primaryid": "102", "caseid": "C1", "pt": "Cough"},
    ])

    d_proc = pb.process_drugs(drug_raw)
    r_proc = pb.process_reactions(reac_raw)
    pairs = pb.build_case_pairs(demo_df=demo_df, drug_df=d_proc, reac_df=r_proc)

    assert len(pairs) == 1, f"Expected exactly 1 pair, got {len(pairs)}"
    row = pairs.iloc[0]
    assert row["primaryid"] == "101", f"Expected primaryid=101, got {row['primaryid']}"
    assert row["canonical_drug"] == "metformin", f"Expected metformin, got {row['canonical_drug']}"
    assert row["canonical_pt"] == "Nausea", f"Expected Nausea, got {row['canonical_pt']}"
    assert row["age"] == "50", f"Expected age=50, got {row['age']}"
    assert row["sex"] == "M", f"Expected sex=M, got {row['sex']}"
    assert "lisinopril" not in pairs["canonical_drug"].values, "Leaked Version 2 drug found!"
    assert "Cough" not in pairs["canonical_pt"].values, "Leaked Version 2 reaction found!"


run_test("Cross-version leakage strictly prevented", test_cross_version_leakage_prevented)


# ===========================================================================
# Test 2 — Demographic fidelity of selected version
# ===========================================================================
def test_demographic_fidelity_selected_version():
    """
    When Version 2 is the canonical selected version instead of Version 1:
    Canonical DEMO contains Version 2 (primaryid=102, age=65, sex=F).
    Expected:
      - Pairs produced strictly correspond to Version 2's demographics and events.
    """
    demo_df = pd.DataFrame([{"caseid": "C1", "primaryid": "102", "age": "65", "sex": "F"}])
    drug_raw = pd.DataFrame([
        {"primaryid": "101", "caseid": "C1", "drugname": "METFORMIN", "role_cod": "PS"},
        {"primaryid": "102", "caseid": "C1", "drugname": "LISINOPRIL", "role_cod": "PS"},
    ])
    reac_raw = pd.DataFrame([
        {"primaryid": "101", "caseid": "C1", "pt": "Nausea"},
        {"primaryid": "102", "caseid": "C1", "pt": "Cough"},
    ])

    d_proc = pb.process_drugs(drug_raw)
    r_proc = pb.process_reactions(reac_raw)
    pairs = pb.build_case_pairs(demo_df=demo_df, drug_df=d_proc, reac_df=r_proc)

    assert len(pairs) == 1, f"Expected 1 pair, got {len(pairs)}"
    row = pairs.iloc[0]
    assert row["primaryid"] == "102"
    assert row["canonical_drug"] == "lisinopril"
    assert row["canonical_pt"] == "Cough"
    assert row["age"] == "65"
    assert row["sex"] == "F"


run_test("Demographic fidelity of selected version", test_demographic_fidelity_selected_version)


# ===========================================================================
# Test 3 — Multi-drug preservation
# ===========================================================================
def test_multi_drug_preservation():
    """
    A single canonical report (primaryid=201) reports 2 suspect drugs: METFORMIN and LISINOPRIL,
    and 1 adverse event: Dizziness.
    Expected:
      - Both pairs (METFORMIN, Dizziness) and (LISINOPRIL, Dizziness) are retained.
      - Neither is dropped due to sharing the same caseid.
    """
    demo_df = pd.DataFrame([{"caseid": "C2", "primaryid": "201", "age": "55"}])
    drug_raw = pd.DataFrame([
        {"primaryid": "201", "caseid": "C2", "drugname": "METFORMIN", "role_cod": "PS"},
        {"primaryid": "201", "caseid": "C2", "drugname": "LISINOPRIL", "role_cod": "SS"},
    ])
    reac_raw = pd.DataFrame([
        {"primaryid": "201", "caseid": "C2", "pt": "Dizziness"},
    ])

    d_proc = pb.process_drugs(drug_raw)
    r_proc = pb.process_reactions(reac_raw)
    pairs = pb.build_case_pairs(demo_df=demo_df, drug_df=d_proc, reac_df=r_proc)

    assert len(pairs) == 2, f"Expected 2 pairs, got {len(pairs)}"
    drugs = set(pairs["canonical_drug"])
    assert "metformin" in drugs and "lisinopril" in drugs


run_test("Multi-drug preservation on same report", test_multi_drug_preservation)


# ===========================================================================
# Test 4 — Multi-reaction preservation
# ===========================================================================
def test_multi_reaction_preservation():
    """
    A single canonical report (primaryid=301) reports 1 suspect drug and 2 adverse events:
    Nausea and Vomiting.
    Expected:
      - Both pairs (METFORMIN, Nausea) and (METFORMIN, Vomiting) are retained.
    """
    demo_df = pd.DataFrame([{"caseid": "C3", "primaryid": "301"}])
    drug_raw = pd.DataFrame([
        {"primaryid": "301", "caseid": "C3", "drugname": "METFORMIN", "role_cod": "PS"},
    ])
    reac_raw = pd.DataFrame([
        {"primaryid": "301", "caseid": "C3", "pt": "Nausea"},
        {"primaryid": "301", "caseid": "C3", "pt": "Vomiting"},
    ])

    d_proc = pb.process_drugs(drug_raw)
    r_proc = pb.process_reactions(reac_raw)
    pairs = pb.build_case_pairs(demo_df=demo_df, drug_df=d_proc, reac_df=r_proc)

    assert len(pairs) == 2, f"Expected 2 pairs, got {len(pairs)}"
    pts = set(pairs["canonical_pt"])
    assert "Nausea" in pts and "Vomiting" in pts


run_test("Multi-reaction preservation on same report", test_multi_reaction_preservation)


# ===========================================================================
# Test 5 — Role-code prioritization (PS over SS)
# ===========================================================================
def test_role_code_prioritization():
    """
    A single report lists the exact same drug twice: once as Secondary Suspect (SS)
    and once as Primary Suspect (PS), for the same event.
    Expected:
      - Deduplicated to 1 pair.
      - Deterministically retains role_cod == 'PS' (Primary Suspect takes priority).
    """
    demo_df = pd.DataFrame([{"caseid": "C4", "primaryid": "401"}])
    # Note: SS is listed first in DataFrame to test that sorting overcomes insertion order
    drug_raw = pd.DataFrame([
        {"primaryid": "401", "caseid": "C4", "drugname": "ASPIRIN", "role_cod": "SS"},
        {"primaryid": "401", "caseid": "C4", "drugname": "ASPIRIN", "role_cod": "PS"},
    ])
    reac_raw = pd.DataFrame([
        {"primaryid": "401", "caseid": "C4", "pt": "Headache"},
    ])

    d_proc = pb.process_drugs(drug_raw)
    r_proc = pb.process_reactions(reac_raw)
    pairs = pb.build_case_pairs(demo_df=demo_df, drug_df=d_proc, reac_df=r_proc)

    assert len(pairs) == 1, f"Expected 1 deduplicated pair, got {len(pairs)}"
    assert pairs.iloc[0]["role_cod"] == "PS", f"Expected PS priority, got {pairs.iloc[0]['role_cod']}"


run_test("Role-code prioritization (PS > SS)", test_role_code_prioritization)


# ===========================================================================
# Test 6 — Pre- vs Post-Fix Cohort Quantification
# ===========================================================================
def test_cohort_quantification():
    """
    Simulate a 10-case cohort where 3 cases have follow-up versions with additional drugs.
    Compare old join logic (on caseid) vs new join logic (on primaryid + caseid).
    Expected:
      - Old join produces inflated pairs with cross-version leakage.
      - New join eliminates all leaked pairs and retains strictly canonical version pairs.
    """
    cases = []
    drugs = []
    reacs = []

    for i in range(1, 11):
        cid = f"CASE_{i}"
        pid_v1 = f"100{i}"
        cases.append({"caseid": cid, "primaryid": pid_v1, "age": str(40 + i)})
        drugs.append({"primaryid": pid_v1, "caseid": cid, "drugname": "METFORMIN", "role_cod": "PS"})
        reacs.append({"primaryid": pid_v1, "caseid": cid, "pt": "Hypoglycaemia"})

        # Cases 1, 2, 3 have follow-up version 2 with a new drug and reaction
        if i <= 3:
            pid_v2 = f"200{i}"
            drugs.append({"primaryid": pid_v2, "caseid": cid, "drugname": "INSULIN", "role_cod": "PS"})
            reacs.append({"primaryid": pid_v2, "caseid": cid, "pt": "Ketoacidosis"})

    demo_df = pd.DataFrame(cases)
    d_df = pb.process_drugs(pd.DataFrame(drugs))
    r_df = pb.process_reactions(pd.DataFrame(reacs))

    # Old logic simulation (join on caseid)
    pairs_old = pd.merge(
        d_df[["primaryid", "caseid", "canonical_drug", "role_cod", "norm_status"]],
        r_df[["primaryid", "canonical_pt"]],
        on="primaryid",
        how="inner"
    )
    pairs_old = pairs_old.drop_duplicates(subset=["caseid", "canonical_drug", "canonical_pt"])
    pairs_old = pd.merge(pairs_old, demo_df[["caseid", "primaryid", "age"]], on="caseid", suffixes=("", "_demo"))
    n_old = len(pairs_old)

    # New logic (fixed PairBuilder)
    pairs_new = pb.build_case_pairs(demo_df=demo_df, drug_df=d_df, reac_df=r_df)
    n_new = len(pairs_new)

    print(f"       [Cohort Simulation] Pre-fix pairs: {n_old} | Post-fix pairs: {n_new} | Leakage eliminated: {n_old - n_new}")
    assert n_new == 10, f"Expected exactly 10 canonical pairs, got {n_new}"
    assert n_old == 13, f"Expected 13 inflated pairs in pre-fix logic, got {n_old}"
    assert (n_old - n_new) == 3, "Failed to eliminate 3 leaked follow-up pairs!"


run_test("Pre- vs Post-Fix Cohort Quantification", test_cohort_quantification)


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print()
print("=" * 65)
n_pass = sum(1 for r in results if r["status"] == PASS)
n_fail = sum(1 for r in results if r["status"] == FAIL)
print(f"Results: {n_pass} PASS  |  {n_fail} FAIL  |  {len(results)} total tests")
print("=" * 65)

if n_fail > 0:
    sys.exit(1)
