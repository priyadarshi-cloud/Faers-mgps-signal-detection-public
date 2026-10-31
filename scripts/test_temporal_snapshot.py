"""
Test and verify the 'as-of-date' temporal snapshot rule across FAERS cases.
Ensures no future revision received after cutoff_date is used in an earlier snapshot.
"""

import os
import sys
import pandas as pd

sys.path.insert(0, os.path.abspath("."))
from src.preprocessing.case_deduplication import CaseVersionManager

# Create a synthetic edge-case dataset simulating multi-year follow-ups
synthetic_cases = pd.DataFrame([
    # Case 1: Initial in 2014, follow-up in 2017, follow-up in 2021
    {"caseid": "101", "caseversion": "1", "init_fda_dt": "20140501", "fda_dt": "20140501", "primaryid": "101_v1", "age": "50"},
    {"caseid": "101", "caseversion": "2", "init_fda_dt": "20140501", "fda_dt": "20170810", "primaryid": "101_v2", "age": "53"},
    {"caseid": "101", "caseversion": "3", "init_fda_dt": "20140501", "fda_dt": "20210215", "primaryid": "101_v3", "age": "57"},

    # Case 2: Initial in 2019 (after 2018 cutoff)
    {"caseid": "202", "caseversion": "1", "init_fda_dt": "20190301", "fda_dt": "20190301", "primaryid": "202_v1", "age": "45"},

    # Case 3: Initial in 2018, no follow-up
    {"caseid": "303", "caseversion": "1", "init_fda_dt": "20181120", "fda_dt": "20181120", "primaryid": "303_v1", "age": "70"}
])

print("=== TESTING 'AS-OF-DATE' TEMPORAL SNAPSHOT RULE ===")
cutoff = "20181231"

# 1. Cohort entry filtering: init_fda_dt <= cutoff
cohort = CaseVersionManager.filter_by_initial_date(synthetic_cases, max_init_date=cutoff)
print(f"Total input rows: {len(synthetic_cases)}")
print(f"Rows with init_fda_dt <= {cutoff}: {len(cohort)}")
assert "202" not in cohort["caseid"].values, "Case initiated after cutoff incorrectly entered cohort!"

# 2. Version filtering & deduplication as-of cutoff
snapshot = CaseVersionManager.deduplicate_cases_to_latest_version(cohort, cutoff_date=cutoff)
print(f"Snapshot unique cases: {len(snapshot)}")

# Verify Case 1 selected v2 (2017), NOT v3 (2021)
case1_rec = snapshot[snapshot["caseid"] == "101"].iloc[0]
print(f"Case 101 selected version: {case1_rec['caseversion']} (fda_dt: {case1_rec['fda_dt']}, primaryid: {case1_rec['primaryid']})")
assert case1_rec["caseversion"] == "2", f"Leakage! Expected version 2, got {case1_rec['caseversion']}"
assert case1_rec["fda_dt"] == "20170810", "Future date leaked into snapshot!"

# Verify Case 3 is present
assert "303" in snapshot["caseid"].values

print("\n [TEST PASSED]: 'As-of-date' snapshot rule strictly blocks future follow-up leakage.")
