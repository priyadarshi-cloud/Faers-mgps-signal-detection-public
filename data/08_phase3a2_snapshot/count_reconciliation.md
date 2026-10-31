# Phase 3A.2 Count Reconciliation Tables

**Generated:** 2026-10-11T01:48:09.077962  
**Cutoff Date:** 2018-12-31  
**Total Quarters Evaluated:** 40 (2014Q1 - 2023Q4)  

## 1. Stage-by-Stage Attrition Table

| Pipeline Stage | Metric / Description | Count | Action / Delta |
|---|---|---|---|
| Raw Ingestion | Raw DEMO rows across all 40 quarters | 15,428,448 | Base Input |
| Identifier Hygiene | Missing / malformed primaryid or caseid | 0 | Quarantined |
| Deduplication | Duplicate primaryid reports across quarters | 463 | Deduplicated |
| Date Hygiene | Invalid calendar dates (init_fda_dt / fda_dt) | 0 | Quarantined |
| Case Temporal Anchor | Initial receipt date after cutoff (> 2018-12-31) | 8,504,708 | Excluded (Post-Cutoff Cases) |
| Version Temporal Anchor | Report version receipt date after cutoff (> 2018-12-31) | 333,954 | Excluded (Post-Cutoff Follow-ups) |
| Retraction Purge | Cases in FDA cumulative retraction list | 28,806 | Excluded (Retracted) |
| Eligible Version Universe | Pre-cutoff, non-deleted report versions | 6,560,517 | Retained for Selection |
| Unique Eligible Cases | Unique patient case entities | 5,987,173 | Unique Cases |
| Canonical Selected Snapshot | Selected best-version rows (one per case) | 5,987,173 | Canonical Snapshot |
| Quality Invariant Check | Duplicate caseids in canonical snapshot | 0 | Strictly Zero |

## 2. Invariant Cross-Checks

| Invariant Cross-Check | Expected | Actual | Status |
|---|---|---|---|
| `raw_rows_match_phase3a` | True | True | ✅ PASS |
| `deleted_ids_match` | True | True | ✅ PASS |
| `no_duplicate_caseids_in_snapshot` | True | True | ✅ PASS |
| `count_identity_holds` | True | True | ✅ PASS |

## 3. Selection Breakdown

- Single-version cases: `5,494,230`
- Multi-version cases: `492,943`
- Cases collapsed during selection: `573,344`
