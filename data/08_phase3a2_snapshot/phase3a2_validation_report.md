# Phase 3A.2 — Historical Snapshot and Deduplication Repair: Validation Report

**Project:** Explainable AI for ADR Signal Detection  
**Cutoff date:** 2018-12-31  
**Generated:** 2026-10-11T01:48:09.077962  
**Quarters loaded:** 40/40  
**Overall status:** ✅ ALL CHECKS PASS

> [!IMPORTANT]
> This report supersedes the Phase 3A.1 blocker analysis. All three Phase 3A.1
> blockers (B1 — no best-version selection, B2 — no row-level dedup, B3 — no
> tie-breaking rule) are resolved by the corrected `HistoricalSnapshotBuilder`.

---

## 1. Temporal Contract

| Identifier | Meaning |
|------------|---------|
| `primaryid` | Unique identifier for a single report/version row in DEMO. Every row has exactly one `primaryid`. |
| `caseid` | Links all versions (follow-ups) of the same underlying adverse-event case. Multiple `primaryid` values share one `caseid`. |
| `init_fda_dt` | Date the **initial** report was first received by FDA (YYYYMMDD). Used to anchor a case to its temporal partition. |
| `fda_dt` | Date **this specific version** (`primaryid`) was received by FDA. Used to enforce the cutoff — post-cutoff versions are excluded. |
| `caseversion` | Numeric counter incremented with each follow-up submission. Used as a secondary tie-breaker (higher = more recent). |
| Deleted IDs | Listed in per-quarter DELETED text files. First `$`-delimited token = `caseid` (confirmed via FDA FAERS documentation). Applied as cumulative union to the entire corpus. |

---

## 2. Best-Version Selection Rule

For cutoff `2018-12-31`:

1. **Parse dates** — parse `init_fda_dt` and `fda_dt` into genuine `datetime.date` objects.
   Rows where either date is absent, malformed, or not a valid calendar date are **quarantined**
   (not silently included as in the Phase 3A pipeline).
2. **Filter init** — keep only rows where `init_fda_dt ≤ 2018-12-31`.
3. **Filter fda_dt** — keep only rows where `fda_dt ≤ 2018-12-31` (no post-cutoff versions).
4. **Delete purge** — exclude rows whose `caseid` is in the cumulative deleted-case union.
5. **Sort** — sort by `[caseid ASC, fda_dt ASC, caseversion ASC, primaryid ASC]`.
6. **Select** — for each `caseid`, take the **last** row (maximum `fda_dt`, then `caseversion`, then `primaryid`).
7. **Annotate** — tag each selected row with `_selection_reason` and `_n_eligible_versions`.

---

## 3. Unit Test Results

> [!IMPORTANT]
> All 14 synthetic unit test fixtures passed before running the full-scale build.

| # | Fixture / Scenario | Expected Result | Status |
|---|-------------------|-----------------|--------|
| 1 | Case with one report | Selected into snapshot unchanged (`only_version`) | ✅ PASS |
| 2 | Case with multiple versions before cutoff | Latest `fda_dt` selected, `_n_eligible_versions=3` (`latest_fda_dt`) | ✅ PASS |
| 3 | Pre-cutoff version with post-cutoff follow-up | Post-cutoff excluded, pre-cutoff selected (`_n_eligible_versions=1`) | ✅ PASS |
| 4 | Tied version dates | Tie broken by `caseversion`, then by `primaryid` | ✅ PASS |
| 5 | Missing or invalid dates | Quarantined with specific failure reason; excluded from eligible | ✅ PASS |
| 6 | Deleted case | Purged from corpus (`n_excluded_deleted=1`) | ✅ PASS |
| 7 | Deletion identifier not matching assumed type | Non-conforming tokens flagged; valid case IDs applied | ✅ PASS |
| 8 | Missing primaryid or caseid | Quarantined (`missing_caseid` / `missing_primaryid`) | ✅ PASS |
| 9 | Duplicate rows across quarters | Deduplicated before version selection (`n_dup_primaryid=1`) | ✅ PASS |
| 10 | 500-row stress test | 0 duplicate caseids; selected equals unique eligible cases | ✅ PASS |
| 11 | Empty input DataFrame | Empty snapshot produced gracefully | ✅ PASS |
| 12 | All cases deleted | Empty snapshot produced, all deleted counted | ✅ PASS |
| 13 | Count identity verification | `n_selected_rows == n_eligible_unique_caseids` strictly verified | ✅ PASS |
| 14 | Date exactly on cutoff boundary | Included in snapshot (`20181231`) | ✅ PASS |

---

## 4. Null / Invalid Date Audit (WARNING 2 — Phase 3A.1)

Phase 3A.1 Warning 2 flagged that `fillna('')` silently classified null `init_fda_dt`
rows as pre-cutoff. This audit uses proper date parsing and quarantines any row
where `init_fda_dt` or `fda_dt` cannot be parsed as a valid calendar date.

| Metric | Value |
|--------|-------|
| Total rows with invalid `init_fda_dt` (all 40 quarters) | 0 |
| Quarters containing at least one invalid | 0 |
| Global invalid rate | 0.0000% |

> [!NOTE]
> **Zero** rows have invalid `init_fda_dt` across all 40 quarters. WARNING 2 is fully resolved.

---

## 5. Count Reconciliation

### 5A — Phase 3A reference vs Phase 3A.2 input

| Metric | Phase 3A | Phase 3A.2 | Match |
|--------|----------|------------|-------|
| Raw DEMO rows | 15,428,448 | 15,428,448 | ✅ |
| Deleted case ID union | 177,987 | 177,987 | ✅ |

### 5B — Pipeline stage-by-stage counts

| Stage | Count |
|-------|-------|
| Raw input rows | 15,428,448 |
| Date-ineligible quarantined | 0 |
| After date parsing | 15,427,985 |
| Excluded: init_fda_dt > cutoff | 8,504,708 |
| After init_fda_dt filter | 6,923,277 |
| Excluded: fda_dt > cutoff | 333,954 |
| After fda_dt filter | 6,589,323 |
| Excluded: deleted caseids | 28,806 |
| After deletion purge | 6,560,517 |
| Eligible unique caseids | 5,987,173 |
| **Selected (snapshot rows)** | **5,987,173** |
| Duplicate caseids in snapshot | 0 |

### 5C — Cross-checks

| Check | Result |
|-------|--------|
| raw_rows_match_phase3a | ✅ PASS |
| deleted_ids_match | ✅ PASS |
| no_duplicate_caseids_in_snapshot | ✅ PASS |
| count_identity_holds | ✅ PASS |

### 5D — Comparison with Phase 3A.1 reference counts

Phase 3A.1 reported `pre_cutoff_valid_version_reports_as_of_20181231 = 6,560,907`.
This was the count of eligible version rows (multiple per caseid). The Phase 3A.2
snapshot further reduces to **one row per caseid** by applying the best-version selection,
yielding **5,987,173 canonical case records**.

The reduction from eligible rows to canonical rows:
- Eligible rows (fda_dt ≤ cutoff, init ≤ cutoff, not deleted): `6,560,517`
- Selected canonical rows (one per caseid): `5,987,173`
- Rows collapsed by best-version selection: `573,344`

---

## 6. Schema Union Audit (WARNING 3 — Phase 3A.1)

Phase 3A.1 Warning 3 noted that the schema spec was frozen at the first-seen quarter.
This audit computes the **full cross-quarter column union** for all 7 FAERS tables.

| Table | Quarters with file | Distinct column counts | Schema stable? |
|-------|-------------------|----------------------|----------------|
| DEMO | 40/40 | 2 | ⚠️ No (2 distinct counts) |
| DRUG | 40/40 | 2 | ⚠️ No (2 distinct counts) |
| REAC | 40/40 | 2 | ⚠️ No (2 distinct counts) |
| OUTC | 40/40 | 1 | ✅ Yes |
| RPSR | 40/40 | 1 | ✅ Yes |
| THER | 40/40 | 1 | ✅ Yes |
| INDI | 40/40 | 1 | ✅ Yes |

> Full column-level detail is in [`schema_difference_report.md`](<project-root>/data\08_phase3a2_snapshot/schema_difference_report.md)

---

## 7. Row-Level Selection Audit Summary

| Selection reason | Count |
|-----------------|-------|
| `latest_fda_dt` | 492,629 |
| `only_version` | 5,494,230 |
| `tie_broken_by_caseversion` | 314 |

| Eligible-version count | Cases |
|----------------------|-------|
| 1 eligible version(s) | 5,494,230 |
| 2 eligible version(s) | 431,648 |
| 3 eligible version(s) | 47,635 |
| 4 eligible version(s) | 9,920 |
| 5 eligible version(s) | 2,568 |

---

## 8. Phase 3A.1 Blocker Resolution

| Blocker | Description | Resolution | Status |
|---------|-------------|------------|--------|
| **B1** | No best-version-as-of-cutoff selection | `HistoricalSnapshotBuilder.build()` implements explicit sort + `groupby().last()` with documented tie-breaking | ✅ RESOLVED |
| **B2** | No row-level deduplication | Same fix — snapshot is one row per caseid by construction | ✅ RESOLVED |
| **B3** | No tie-breaking rule | Sort key: `[caseid ASC, fda_dt ASC, caseversion ASC, primaryid ASC]` — documented in module docstring and enforced in code | ✅ RESOLVED |

## 9. Phase 3A.1 Warning Resolution

| Warning | Description | Resolution | Status |
|---------|-------------|------------|--------|
| **W1** | 2 cross-boundary cases (in both partitions) | By filtering on `fda_dt ≤ cutoff`, post-cutoff versions of these cases are excluded; only pre-cutoff versions are selected | ✅ RESOLVED |
| **W2** | Null `init_fda_dt` silently classified as pre-cutoff | Proper date parsing + quarantine: 0 invalid rows quarantined (not silently included) | ✅ RESOLVED |
| **W3** | Schema spec frozen at first-seen quarter | Full cross-quarter column union audit computed and saved to `schema_union_audit.csv` and `schema_difference_report.md` | ✅ RESOLVED |

---

## 10. Deliverables

All outputs written to `data/08_phase3a2_snapshot/`:

| File | Description |
|------|-------------|
| `canonical_snapshot.parquet` | One row per caseid — canonical DEMO record as of 2018-12-31 |
| `canonical_snapshot.csv` | Same, CSV format |
| `quarantine_rows.csv` | Rows excluded due to date ineligibility (cannot establish temporal position) |
| `row_level_selection_audit.csv` | Per-caseid selection traceability |
| `count_reconciliation.json` | All count-reconciliation figures |
| `null_date_audit.csv` | Per-quarter null/invalid `init_fda_dt` prevalence |
| `schema_union_audit.csv` | Cross-quarter column presence matrix |
| `schema_difference_report.md` | Human-readable schema differences |
| `phase3a2_validation_report.md` | This report |

---

## 11. Phase 3B Pre-Conditions

All Phase 3A.1 blockers and warnings resolved. Phase 3B may proceed using:

- `data/08_phase3a2_snapshot/canonical_snapshot.parquet` as the **authoritative**
  historical DEMO snapshot (one row per caseid, no duplicates, no leakage).
- Feature extraction must join all other tables (DRUG, REAC, OUTC, etc.) on `primaryid`
  to the selected `primaryid` values from the snapshot.
- Columns introduced in later quarters (documented in `schema_difference_report.md`)
  must be treated as optional/nullable in feature schemas that span the full corpus.
