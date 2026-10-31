"""
Phase 3A.2 — Unit Tests for HistoricalSnapshotBuilder.

Covers all required synthetic test fixtures from Phase 3A.2 specification:
1. A case with one report
2. A case with multiple versions before the cutoff
3. A case with a pre-cutoff version and a post-cutoff follow-up
4. Tied version dates (tie-breaking by caseversion and by primaryid)
5. Missing or invalid dates (quarantine verification)
6. A deleted case
7. A deletion identifier that does not match the assumed identifier type
8. A case with a missing primaryid or caseid
9. Duplicate rows across quarters
Additional edge cases:
10. Stress test: 500 multi-version rows (no duplicate caseids in snapshot)
11. Empty input DataFrame
12. All cases deleted
13. Strict count identity verification
14. Date exactly on cutoff boundary

Run with:
    python scripts/test_phase3a2_snapshot.py
"""

from __future__ import annotations

import sys
import os

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import pandas as pd
import numpy as np

from src.preprocessing.historical_snapshot import HistoricalSnapshotBuilder

PASS_MARKER = "✅ PASS"
FAIL_MARKER = "❌ FAIL"

results: list[dict] = []


def run_test(name: str, fn):
    """Execute a test function and record the result."""
    try:
        fn()
        results.append({"test": name, "status": PASS_MARKER, "note": ""})
        print(f"  {PASS_MARKER}  {name}")
    except AssertionError as e:
        results.append({"test": name, "status": FAIL_MARKER, "note": str(e)})
        print(f"  {FAIL_MARKER}  {name}")
        print(f"         → {e}")
    except Exception as e:
        results.append({"test": name, "status": FAIL_MARKER, "note": f"Exception: {e}"})
        print(f"  {FAIL_MARKER}  {name}")
        print(f"         → Exception: {e}")


builder = HistoricalSnapshotBuilder(cutoff_yyyymmdd="20181231")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_demo(**kwargs) -> pd.DataFrame:
    """
    Build a minimal DEMO DataFrame from keyword lists.
    Defaults are broadcast to match the length of provided kwargs.
    """
    defaults = {
        "primaryid": "1",
        "caseid": "C1",
        "caseversion": "1",
        "init_fda_dt": "20180101",
        "fda_dt": "20180601",
        "quarter": "2018Q2",
    }
    n = 1
    for v in kwargs.values():
        if isinstance(v, (list, tuple)):
            n = len(v)
            break
    cols = {}
    for key, default_val in defaults.items():
        if key in kwargs:
            cols[key] = kwargs[key]
        else:
            cols[key] = [default_val] * n
    for key, val in kwargs.items():
        if key not in cols:
            cols[key] = val
    return pd.DataFrame(cols)


# ===========================================================================
# Fixture 1 — A case with one report
# ===========================================================================
def test_case_with_one_report():
    """
    Fixture 1: A case with exactly one report.
    Expected result:
      - Selected into snapshot unchanged.
      - _selection_reason == 'only_version'.
      - _n_eligible_versions == 1.
      - Exactly 1 row in snapshot, 0 in quarantine.
    """
    df = _make_demo(primaryid=["101"], caseid=["CASE_01"], init_fda_dt=["20170501"], fda_dt=["20170501"])
    snap, audit, quarantine = builder.build(df)
    assert len(snap) == 1, f"Expected 1 row, got {len(snap)}"
    assert snap.iloc[0]["caseid"] == "CASE_01"
    assert snap.iloc[0]["primaryid"] == "101"
    assert snap.iloc[0]["_selection_reason"] == "only_version"
    assert int(snap.iloc[0]["_n_eligible_versions"]) == 1
    assert len(quarantine) == 0
    assert audit["n_selected_rows"] == 1


run_test("Fixture 1: Case with one report", test_case_with_one_report)


# ===========================================================================
# Fixture 2 — A case with multiple versions before the cutoff
# ===========================================================================
def test_case_with_multiple_versions_before_cutoff():
    """
    Fixture 2: A case with 3 follow-up versions, all before the cutoff (2018-12-31).
    Expected result:
      - Exactly 1 row selected (the latest by fda_dt: primaryid='12', fda_dt='20181201').
      - _n_eligible_versions == 3.
      - _selection_reason == 'latest_fda_dt'.
      - audit['n_multi_eligible_version_cases'] == 1.
    """
    df = _make_demo(
        primaryid=["10", "11", "12"],
        caseid=["CASE_02", "CASE_02", "CASE_02"],
        caseversion=["1", "2", "3"],
        init_fda_dt=["20150101", "20150101", "20150101"],
        fda_dt=["20150601", "20170101", "20181201"],
        quarter=["2015Q2", "2017Q1", "2018Q4"],
    )
    snap, audit, quarantine = builder.build(df)
    assert len(snap) == 1, f"Expected 1 row, got {len(snap)}"
    assert snap.iloc[0]["primaryid"] == "12", f"Expected primaryid=12, got {snap.iloc[0]['primaryid']}"
    assert snap.iloc[0]["_selection_reason"] == "latest_fda_dt"
    assert int(snap.iloc[0]["_n_eligible_versions"]) == 3
    assert audit["n_multi_eligible_version_cases"] == 1


run_test("Fixture 2: Case with multiple versions before cutoff", test_case_with_multiple_versions_before_cutoff)


# ===========================================================================
# Fixture 3 — A case with pre-cutoff version and post-cutoff follow-up
# ===========================================================================
def test_case_with_pre_and_post_cutoff_followup():
    """
    Fixture 3: A case with v1 received before cutoff (2018-10-01) and v2 after cutoff (2019-03-01).
    Expected result:
      - v2 is strictly excluded as post-cutoff (n_excluded_fda_after_cutoff == 1).
      - v1 is selected as the latest eligible version available by cutoff.
      - Snapshot contains v1 (primaryid='20'), _n_eligible_versions == 1.
    """
    df = _make_demo(
        primaryid=["20", "21"],
        caseid=["CASE_03", "CASE_03"],
        caseversion=["1", "2"],
        init_fda_dt=["20181001", "20181001"],
        fda_dt=["20181001", "20190301"],
        quarter=["2018Q4", "2019Q1"],
    )
    snap, audit, quarantine = builder.build(df)
    assert len(snap) == 1, f"Expected 1 selected row, got {len(snap)}"
    assert snap.iloc[0]["primaryid"] == "20", f"Expected v1 (primaryid=20), got {snap.iloc[0]['primaryid']}"
    assert audit["n_excluded_fda_after_cutoff"] == 1
    assert int(snap.iloc[0]["_n_eligible_versions"]) == 1


run_test("Fixture 3: Pre-cutoff version with post-cutoff follow-up", test_case_with_pre_and_post_cutoff_followup)


# ===========================================================================
# Fixture 4 — Tied version dates (tie-breaking rules)
# ===========================================================================
def test_tied_version_dates():
    """
    Fixture 4:
      Part A: Tied fda_dt, differing caseversion (v1 vs v2).
              Expected: higher caseversion wins (_selection_reason == 'tie_broken_by_caseversion').
      Part B: Tied fda_dt and tied caseversion, differing primaryid (80 vs 90).
              Expected: higher numeric primaryid wins (_selection_reason == 'tie_broken_by_primaryid').
    """
    # Part A
    df_a = _make_demo(
        primaryid=["70", "71"],
        caseid=["CASE_04A", "CASE_04A"],
        caseversion=["1", "2"],
        init_fda_dt=["20170101", "20170101"],
        fda_dt=["20181201", "20181201"],
        quarter=["2018Q4", "2018Q4"],
    )
    snap_a, _, _ = builder.build(df_a)
    assert snap_a.iloc[0]["primaryid"] == "71", "Higher caseversion should win"
    assert snap_a.iloc[0]["_selection_reason"] == "tie_broken_by_caseversion"

    # Part B
    df_b = _make_demo(
        primaryid=["80", "90"],
        caseid=["CASE_04B", "CASE_04B"],
        caseversion=["1", "1"],
        init_fda_dt=["20170101", "20170101"],
        fda_dt=["20181201", "20181201"],
        quarter=["2018Q4", "2018Q4"],
    )
    snap_b, _, _ = builder.build(df_b)
    assert snap_b.iloc[0]["primaryid"] == "90", "Higher primaryid should win when version and date tie"
    assert snap_b.iloc[0]["_selection_reason"] == "tie_broken_by_primaryid"


run_test("Fixture 4: Tied version dates (deterministic tie-breaking)", test_tied_version_dates)


# ===========================================================================
# Fixture 5 — Missing or invalid dates (quarantine verification)
# ===========================================================================
def test_missing_or_invalid_dates():
    """
    Fixture 5:
      Cases with:
        - blank init_fda_dt ('')
        - invalid calendar date in fda_dt ('20180231' — Feb 31 does not exist)
        - wrong-length date ('9999999' — 7 digits)
        - valid case for control
      Expected result:
        - All 3 malformed/empty rows are quarantined with specific reasons.
        - Exactly 1 valid case is selected into snapshot.
        - n_date_ineligible_quarantined == 3.
    """
    df = _make_demo(
        primaryid=["51", "52", "53", "54"],
        caseid=["CASE_BLANK_INIT", "CASE_INVALID_CAL", "CASE_WRONG_LEN", "CASE_VALID"],
        init_fda_dt=["", "20170101", "20170101", "20170101"],
        fda_dt=["20180101", "20180231", "9999999", "20180101"],
        quarter=["2018Q1"] * 4,
    )
    snap, audit, quarantine = builder.build(df)
    assert len(snap) == 1, f"Expected 1 valid row in snapshot, got {len(snap)}"
    assert snap.iloc[0]["caseid"] == "CASE_VALID"
    assert len(quarantine) == 3, f"Expected 3 rows in quarantine, got {len(quarantine)}"
    assert audit["n_date_ineligible_quarantined"] == 3

    q_reasons = set(quarantine["_exclusion_reason"].tolist())
    assert "init_fda_dt_invalid" in q_reasons
    assert "fda_dt_invalid" in q_reasons


run_test("Fixture 5: Missing or invalid dates (quarantine isolation)", test_missing_or_invalid_dates)


# ===========================================================================
# Fixture 6 — A deleted case
# ===========================================================================
def test_deleted_case():
    """
    Fixture 6: Two cases, CASE_DEL and CASE_KEEP. CASE_DEL is present in deleted set.
    Expected result:
      - CASE_DEL is excluded under deletion policy (n_excluded_deleted == 1).
      - CASE_KEEP is retained in snapshot.
      - Exactly 1 row in snapshot.
    """
    df = _make_demo(
        primaryid=["61", "62"],
        caseid=["10155345", "10155346"],
        init_fda_dt=["20170101", "20170101"],
        fda_dt=["20170601", "20170601"],
        quarter=["2017Q2", "2017Q2"],
    )
    snap, audit, _ = builder.build(df, deleted_caseids={"10155345"})
    assert len(snap) == 1
    assert snap.iloc[0]["caseid"] == "10155346"
    assert audit["n_excluded_deleted"] == 1


run_test("Fixture 6: Deleted case purged", test_deleted_case)


# ===========================================================================
# Fixture 7 — Deletion identifier not matching assumed identifier type
# ===========================================================================
def test_deletion_identifier_not_matching_assumed_type():
    """
    Fixture 7: Deletion set contains non-standard tokens:
      - Text header 'CASE_ID'
      - Alphanumeric string 'INVALID_TOKEN_XYZ'
      - Blank string ' '
      - Valid numeric caseid '999901'
    Expected result:
      - Valid caseid '999901' is parsed and successfully purges CASE_999901.
      - Non-numeric tokens are isolated and flagged (n_invalid_deletion_tokens_flagged == 2).
      - Normal cases are NOT inadvertently purged by non-matching deletion tokens.
    """
    df = _make_demo(
        primaryid=["71", "72"],
        caseid=["999901", "999902"],
        init_fda_dt=["20170101", "20170101"],
        fda_dt=["20170601", "20170601"],
        quarter=["2017Q2", "2017Q2"],
    )
    deleted_set = {"CASE_ID", "INVALID_TOKEN_XYZ", "   ", "999901"}
    snap, audit, _ = builder.build(df, deleted_caseids=deleted_set)
    assert len(snap) == 1, f"Expected 1 retained case, got {len(snap)}"
    assert snap.iloc[0]["caseid"] == "999902"
    assert audit["n_valid_deleted_caseids"] == 1
    assert audit["n_invalid_deletion_tokens_flagged"] == 2
    assert audit["n_excluded_deleted"] == 1


run_test("Fixture 7: Deletion identifier type validation", test_deletion_identifier_not_matching_assumed_type)


# ===========================================================================
# Fixture 8 — Case with missing primaryid or caseid
# ===========================================================================
def test_case_with_missing_primaryid_or_caseid():
    """
    Fixture 8: Rows with missing / None / empty string / 'nan' identifiers:
      - Row with missing caseid (None or '')
      - Row with missing primaryid (None or '')
      - Row with valid caseid and primaryid
    Expected result:
      - Both rows with missing identifiers are quarantined with explicit reason.
      - Valid row is processed normally.
      - Snapshot contains only the valid case.
      - audit['n_missing_identifier_quarantined'] == 2.
    """
    df = pd.DataFrame({
        "primaryid": ["801", "", "803"],
        "caseid": ["", "CASE_802", "CASE_803"],
        "caseversion": ["1", "1", "1"],
        "init_fda_dt": ["20170101", "20170101", "20170101"],
        "fda_dt": ["20170601", "20170601", "20170601"],
        "quarter": ["2017Q2", "2017Q2", "2017Q2"],
    })
    snap, audit, quarantine = builder.build(df)
    assert len(snap) == 1, f"Expected 1 valid row in snapshot, got {len(snap)}"
    assert snap.iloc[0]["caseid"] == "CASE_803"
    assert audit["n_missing_identifier_quarantined"] == 2

    id_reasons = set(quarantine[quarantine["_exclusion_reason"].str.startswith("missing")]["_exclusion_reason"].tolist())
    assert "missing_caseid" in id_reasons
    assert "missing_primaryid" in id_reasons


run_test("Fixture 8: Missing primaryid or caseid quarantined", test_case_with_missing_primaryid_or_caseid)


# ===========================================================================
# Fixture 9 — Duplicate rows across quarters
# ===========================================================================
def test_duplicate_rows_across_quarters():
    """
    Fixture 9: The exact same report version (primaryid='901') appearing in
    two consecutive quarters (e.g. 2018Q2 and 2018Q3) due to re-publication.
    Expected result:
      - Deduplication eliminates the duplicate report row.
      - n_duplicate_primaryid_rows_excluded == 1.
      - Case is evaluated as having 1 eligible version, NOT 2 inflated versions.
      - Snapshot contains 1 row with _selection_reason == 'only_version'.
    """
    df = pd.DataFrame({
        "primaryid": ["901", "901"],
        "caseid": ["CASE_900", "CASE_900"],
        "caseversion": ["1", "1"],
        "init_fda_dt": ["20180101", "20180101"],
        "fda_dt": ["20180401", "20180401"],
        "quarter": ["2018Q2", "2018Q3"],
    })
    snap, audit, _ = builder.build(df)
    assert len(snap) == 1, f"Expected 1 snapshot row, got {len(snap)}"
    assert audit["n_duplicate_primaryid_rows_excluded"] == 1
    assert int(snap.iloc[0]["_n_eligible_versions"]) == 1
    assert snap.iloc[0]["_selection_reason"] == "only_version"


run_test("Fixture 9: Duplicate rows across quarters deduplicated", test_duplicate_rows_across_quarters)


# ===========================================================================
# Fixture 10 — Stress test: 500 multi-version rows (no duplicate caseids)
# ===========================================================================
def test_no_duplicate_caseids_stress():
    """
    Fixture 10: 500 rows across ~166 cases with multiple versions each.
    Expected result:
      - 0 duplicate caseids in snapshot.
      - Selected rows exactly equals eligible unique caseids.
    """
    n = 500
    caseids = [f"CASE_{i // 3}" for i in range(n)]
    primaryids = [str(i + 10000) for i in range(n)]
    versions = [str((i % 3) + 1) for i in range(n)]
    init_dates = ["20160101"] * n
    fda_dates = [f"201{6 + (i % 3)}0101" for i in range(n)]
    quarters = [f"201{6 + (i % 3)}Q1" for i in range(n)]
    df = pd.DataFrame({
        "primaryid": primaryids,
        "caseid": caseids,
        "caseversion": versions,
        "init_fda_dt": init_dates,
        "fda_dt": fda_dates,
        "quarter": quarters,
    })
    snap, audit, _ = builder.build(df)
    assert audit["duplicate_caseid_in_snapshot"] == 0
    assert audit["audit_selected_eq_eligible_caseids"]
    assert len(snap) == audit["n_eligible_unique_caseids"]


run_test("Fixture 10: 500-row stress test (uniqueness verified)", test_no_duplicate_caseids_stress)


# ===========================================================================
# Fixture 11 — Empty input DataFrame
# ===========================================================================
def test_empty_input():
    """
    Fixture 11: Empty input DataFrame.
    Expected result: Empty snapshot, 0 selected rows, 0 error.
    """
    df = pd.DataFrame(columns=["primaryid", "caseid", "caseversion", "init_fda_dt", "fda_dt", "quarter"])
    snap, audit, _ = builder.build(df)
    assert len(snap) == 0
    assert audit["n_selected_rows"] == 0


run_test("Fixture 11: Empty input DataFrame", test_empty_input)


# ===========================================================================
# Fixture 12 — All cases deleted
# ===========================================================================
def test_all_deleted():
    """
    Fixture 12: All cases in input are in deleted set.
    Expected result: Empty snapshot, n_excluded_deleted == 2.
    """
    df = _make_demo(
        primaryid=["1201", "1202"],
        caseid=["DEL_A", "DEL_B"],
        init_fda_dt=["20170101", "20170101"],
        fda_dt=["20180101", "20180101"],
        quarter=["2017Q1", "2017Q1"],
    )
    snap, audit, _ = builder.build(df, deleted_caseids={"DEL_A", "DEL_B"})
    assert len(snap) == 0
    assert audit["n_excluded_deleted"] == 2


run_test("Fixture 12: All cases deleted", test_all_deleted)


# ===========================================================================
# Fixture 13 — Strict count identity verification
# ===========================================================================
def test_count_identity():
    """
    Fixture 13: Strict identity check that n_selected_rows == n_eligible_unique_caseids.
    """
    df = _make_demo(
        primaryid=["1301", "1302", "1303"],
        caseid=["ID_1", "ID_1", "ID_2"],
        caseversion=["1", "2", "1"],
        init_fda_dt=["20170101", "20170101", "20160101"],
        fda_dt=["20170601", "20181201", "20161201"],
        quarter=["2017Q2", "2018Q4", "2016Q4"],
    )
    snap, audit, _ = builder.build(df)
    assert audit["audit_selected_eq_eligible_caseids"]
    assert audit["n_selected_rows"] == 2
    assert audit["n_eligible_unique_caseids"] == 2


run_test("Fixture 13: Count identity verification", test_count_identity)


# ===========================================================================
# Fixture 14 — Date exactly on cutoff boundary
# ===========================================================================
def test_cutoff_boundary_inclusion():
    """
    Fixture 14: Report with date exactly on cutoff (20181231).
    Expected result: Included (not excluded as post-cutoff).
    """
    df = _make_demo(
        primaryid=["1401"],
        caseid=["CASE_ON_CUTOFF"],
        init_fda_dt=["20181231"],
        fda_dt=["20181231"],
        quarter=["2018Q4"],
    )
    snap, audit, _ = builder.build(df)
    assert len(snap) == 1
    assert audit["n_excluded_init_after_cutoff"] == 0
    assert audit["n_excluded_fda_after_cutoff"] == 0


run_test("Fixture 14: Date exactly on cutoff boundary included", test_cutoff_boundary_inclusion)


# ---------------------------------------------------------------------------
# Final summary
# ---------------------------------------------------------------------------
print()
print("=" * 65)
n_pass = sum(1 for r in results if r["status"] == PASS_MARKER)
n_fail = sum(1 for r in results if r["status"] == FAIL_MARKER)
print(f"Results: {n_pass} PASS  |  {n_fail} FAIL  |  {len(results)} total fixtures")
print("=" * 65)

if n_fail > 0:
    print("\nFailed tests:")
    for r in [r for r in results if r["status"] == FAIL_MARKER]:
        print(f"  {r['test']}: {r['note']}")
    sys.exit(1)
