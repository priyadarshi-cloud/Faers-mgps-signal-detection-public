# Phase 3A.3 — Retraction Look-Ahead and Cross-Table Linkage Audit Report

**Project:** Explainable AI for Pharmacovigilance & Adverse Drug Reaction Discovery  
**Audit Scope:** Retraction Look-Ahead Bias, Deletion Temporal Validity, and Child-Table Linkage Architecture  
**Audit Date:** 2026-10-11  
**Status:** Audit Complete — No data, models, or snapshots modified (Strict Audit-Only)

---

## Executive Summary

Phase 3A.3 audits two fundamental methodological dimensions of the FAERS historical snapshot pipeline:
1. **Retraction Look-Ahead Bias:** Whether the current snapshot builder inadvertently incorporates future information by applying a cumulative union of FDA deletion/retraction records across all 40 quarters (including 2019Q1–2023Q4) to a historical snapshot bounded at `2018-12-31`.
2. **Cross-Table Child Linkage Integrity:** Whether child tables (`DRUG`, `REAC`, `OUTC`, `RPSR`, `THER`, `INDI`) are joined to demographic records strictly through canonical version identifiers (`primaryid`), preventing information leakage from subsequent follow-up versions.

---

## Checklist Summary Matrix

| Audit Check ID | Focus Area | Specific Requirement | Status | Key Evidence / Code Reference |
|---|---|---|---|---|
| **CHK-RET-01** | Deletion Date Availability | Deletion records possess a reliable internal timestamp indicating effective deletion date | **FAIL** | All 21 deletion files contain only naked integer tokens; 0 date fields or transaction logs exist in source files. |
| **CHK-RET-02** | Retraction Look-Ahead | Current code removes cases deleted after the historical cutoff (`2018-12-31`) | **FAIL** | `build_phase3a2_snapshot.py` (lines 67, 220–240) computes cumulative union across all 40 quarters (177,987 IDs), incorporating retractions published up to 2023Q4. |
| **CHK-RET-03** | Future Retraction Count | Exact count of 2018-eligible cases excluded solely by future deletions | **PASS** | **6,144 unique cases** excluded solely by 2019Q2–2023Q4 files; **25,718 unique cases** excluded if 2014–2018 archive availability is strictly enforced. |
| **CHK-RET-04** | Identifier Distinction | Deletion files distinguish `primaryid` from `caseid` | **FAIL** | Deletion files contain raw numbers without headers or type tags. Verified via FDA `ASC_NTS.pdf` that tokens correspond to `caseid`. |
| **CHK-RET-05** | Retraction Date Derivation | Effective retraction dates can be established from FDA official docs | **UNRESOLVED** | FDA documentation provides no transaction-level retraction dates; only archive release dates are known. |
| **CHK-LNK-01** | PrimaryID Child Filtering | Only child rows belonging to canonical `primaryid` are retained | **PASS** | `PipelineOrchestrator` (lines 152–155) filters all child tables via `primaryid.isin(valid_primaryids)`. |
| **CHK-LNK-02** | Follow-Up Leakage Prevention | Information from follow-ups is not linked through `caseid` into earlier snapshot | **FAIL (Latent)** | `pair_builder.py` (line 145) joins demographic metadata `on="caseid"` rather than `primaryid`. |
| **CHK-LNK-03** | Multi-Drug / Multi-ADR Preservation | Duplicate child row handling preserves legitimate multi-drug/multi-reaction records | **PASS** | `pair_builder.py` (line 136) drops duplicates on `(caseid, canonical_drug, canonical_pt)`. Distinct drug–ADR pairs are fully preserved. |
| **CHK-LNK-04** | Pair Structure Integrity | Inner joins between suspect drugs and reactions preserve intended pair structure | **PASS** | `pair_builder.py` (lines 127–132) inner-joins on `primaryid`, generating exact cartesian product of suspect drugs and MedDRA PTs per case version. |

---

## 1. Audit of Retraction Timing and Look-Ahead Bias

### 1.1 Anatomy of Raw Deletion Archives
An exhaustive scan of all 40 quarterly archives (`2014q1` through `2023q4`) in `data/07_phase3a_continuous_ingestion/extracted/` and raw zip archives revealed:

1. **2014Q1 – 2018Q4 Archives Contain ZERO Deletion Files:**
   - In all 20 quarterly packages published by the FDA from 2014Q1 through 2018Q4 (`faers_ascii_2014q1.zip` to `faers_ascii_2018q4.zip`), **no deletion files or folders were packaged**.
2. **First Deletion Archive Appeared in 2019Q1:**
   - The first archive containing a `deleted/` directory is `2019q1`, which included:
     - `deleted/AllDeletedCases.txt`: **83,845** case ID entries.
     - `deleted/ADR19Q1DeletedCases.txt`: **2,856** case ID entries.
3. **Subsequent Quarterly Deletions (2019Q2 – 2023Q4):**
   - Each quarter contains a single text file (e.g. `ADR19Q2DeletedCases.txt`, `DELETE23Q1.txt`) containing 2,900 to 7,900 case IDs.
   - Total cumulative unique deleted IDs across all 21 deletion files: **177,987**.

### 1.2 Format and Syntactic Limitations of Deletion Files
Every deletion file in FAERS consists of newline-delimited bare integers (e.g. `10242528`, `4820242`).
- **No date of deletion:** The files do not contain timestamps, dates of manufacturer retraction, or receipt dates.
- **No identifier tag:** The files do not indicate whether the token is a `caseid` or `primaryid`.
- **FDA Technical Contract:** FDA `ASC_NTS.pdf` Section B and ERD documentation confirms that retracted entries apply to the entire case (`caseid`). When an FDA case is deleted, all versions (`primaryid` values) are retracted.

### 1.3 Quantification of Retraction Look-Ahead Bias
To evaluate how many 2018-eligible cases are affected by future deletions, all pre-cutoff cases (`init_fda_dt <= 2018-12-31` and `fda_dt <= 2018-12-31`) were cross-referenced against each deletion file independently:

| Deletion Archive / Quarter | File Path | Total IDs in File | Pre-Cutoff Cases in File | Incremental (Newly Retracted) Pre-Cutoff Cases |
|---|---|---|---|---|
| **2014Q1 – 2018Q4** | *(None published by FDA)* | 0 | 0 | **0** |
| **2019Q1 Master** | `2019q1/deleted/AllDeletedCases.txt` | 83,845 | 19,573 | **18,964** |
| **2019Q1 Incremental** | `2019q1/deleted/ADR19Q1DeletedCases.txt` | 2,856 | 610 | **610** |
| *Subtotal (through 2019Q1)* | | *84,701 unique* | *19,574 unique* | ***19,574 unique*** |
| **2019Q2** | `2019q2/deleted/ADR19Q2DeletedCases.txt` | 4,405 | 1,200 | **+1,015** |
| **2019Q3** | `2019q3/deleted/ADR19Q3DeletedCases.txt` | 4,455 | 625 | **+562** |
| **2019Q4** | `2019q4/deleted/ADR19Q4DeletedCases.txt` | 5,338 | 391 | **+341** |
| **2020Q1** | `2020q1/DELETED/ADR20Q1DeletedCases.txt` | 4,489 | 199 | **+196** |
| **2020Q2** | `2020q2/DELETED/ADR20Q2DeletedCases.txt` | 5,016 | 500 | **+487** |
| **2020Q3** | `2020q3/Deleted/ADR20Q3DeletedCases.txt` | 7,238 | 462 | **+440** |
| **2020Q4** | `2020q4/Deleted/20Q4DeletedCases.txt` | 4,428 | 404 | **+348** |
| **2021Q1** | `2021q1/Deleted/21Q1DeletedCases.txt` | 5,067 | 508 | **+495** |
| **2021Q2** | `2021q2/Deleted/21Q2DeletedCases.txt` | 6,881 | 484 | **+452** |
| **2021Q3** | `2021q3/Deleted/21Q3DeletedCases.txt` | 7,033 | 312 | **+288** |
| **2021Q4** | `2021q4/Deleted/DELETE21Q4.txt` | 7,983 | 785 | **+783** |
| **2022Q1** | `2022q1/Deleted/DELETE22Q1.txt` | 3,118 | 128 | **+127** |
| **2022Q2** | `2022q2/Deleted/DELETE22Q2.txt` | 5,567 | 159 | **+159** |
| **2022Q3** | `2022q3/Deleted/DELETE22Q3.txt` | 5,016 | 123 | **+123** |
| **2022Q4** | `2022q4/Deleted/DELETE22Q4.txt` | 3,624 | 43 | **+43** |
| **2023Q1** | `2023q1/Deleted/DELETE23Q1.txt` | 5,251 | 78 | **+78** |
| **2023Q2** | `2023q2/Deleted/DELETE23Q2.txt` | 5,581 | 70 | **+70** |
| **2023Q3** | `2023q3/Deleted/DELETE23Q3.txt` | 5,433 | 102 | **+101** |
| **2023Q4** | `2023q4/Deleted/DELETE23Q4.txt` | 2,940 | 36 | **+36** |
| **Total Future Retractions (2019Q2–2023Q4)** | *(19 quarterly files)* | | | **+6,144 unique cases** |
| **Grand Total (All Deletion Files)** | | **177,987 unique** | **25,718 unique** | **25,718 unique cases** |

### 1.4 Code Implementation Reference
In `scripts/build_phase3a2_snapshot.py`:
- **Line 220–240 (`load_all_quarters`):** Scans all quarterly folders in `INGESTION_DIR` and aggregates all files matching `*delet*.txt` into a global `all_deleted_ids` set without filtering by quarterly release date.
- **Line 330–332 (`HistoricalSnapshotBuilder.build`):** Passes the unpartitioned global union `deleted_caseids=all_deleted_ids` into the snapshot builder.
- **Stage 4 Purge (`src/preprocessing/historical_snapshot.py`, lines 268–272):**
  ```python
  is_deleted = df["caseid"].isin(valid_deleted)
  df = df[~is_deleted].copy()
  ```
  Consequently, **25,718 eligible pre-cutoff cases** (comprising 28,806 report rows) are excluded using post-2018 information.

---

## 2. Specification of the Two Candidate Historical Snapshots

To address the methodological trade-off between strict temporal fidelity and retrospective data cleanliness, two reproducible snapshot rules are defined:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        CANDIDATE SNAPSHOT COMPARISON TABLE                             │
├───────────────────────────┬──────────────────────────────┬─────────────────────────────┤
│ Dimension                 │ Snapshot A: AS_OF_2018       │ Snapshot B: RETROSPECTIVE   │
├───────────────────────────┼──────────────────────────────┼─────────────────────────────┤
│ Core Objective            │ Perfect historical simulation│ Maximum data hygiene        │
│ Temporal Cutoff           │ 2018-12-31                   │ 2018-12-31                  │
│ Permitted Deletions       │ Deletions known by 2018-12-31│ Cumulative union (2023Q4)   │
│ Deletion File Set         │ Empty set ∅                  │ All 21 deletion files       │
│ Eligible Unique Cases     │ 6,012,891                    │ 5,987,173                   │
│ Cases Excluded by Del.    │ 0                            │ 25,718                      │
│ Look-Ahead Bias           │ Strictly Zero (0.00%)        │ 25,718 cases (0.43%)        │
│ Data Noise / Retractions  │ Retains later-retracted cases│ Purges invalid/fraud cases  │
└───────────────────────────┴──────────────────────────────┴─────────────────────────────┘
```

### Snapshot Rule 1: `AS_OF_2018` (Strict Historical Simulation)
1. **Temporal Horizon:** Bounded strictly at `2018-12-31`.
2. **Date Filters:**
   - Parse `init_fda_dt` and `fda_dt` to true dates; quarantine unparseable records.
   - Keep only rows where `init_fda_dt <= 2018-12-31` AND `fda_dt <= 2018-12-31`.
3. **Deletion Policy:**
   - Apply only deletion files whose official FDA extract release date was on or before `2018-12-31`.
   - Because the 2014Q1–2018Q4 quarterly archives downloaded from the FDA contain **0 deletion files**, `deleted_caseids = set()`.
4. **Deduplication & Selection:**
   - Drop identical duplicate `primaryid` submissions across quarters.
   - Group eligible versions by `caseid`.
   - Deterministically sort by `[caseid ASC, _fda_date ASC, _caseversion_num ASC, _primaryid_num ASC]`.
   - Select the last row per group.
5. **Resulting Size:** Exactly **6,012,891 canonical cases**.
6. **Methodological Trade-Off:** Completely free from future look-ahead bias; accurately models what an AI system deployed on January 1, 2019 would have observed. However, it contains 25,718 cases that manufacturers or FDA later withdrew due to falsification, clerical duplication, or error.

### Snapshot Rule 2: `RETROSPECTIVELY_CORRECTED` (Cleaned Reference Universe)
1. **Temporal Horizon:** Bounded at `2018-12-31` for report submissions, but incorporates future retraction knowledge up through `2023-12-31` (2023Q4).
2. **Date Filters:**
   - Identical to `AS_OF_2018`: `init_fda_dt <= 2018-12-31` AND `fda_dt <= 2018-12-31`.
3. **Deletion Policy:**
   - Apply the full cumulative union of all 21 deletion files available across all 40 quarters (177,987 unique case IDs).
   - Purge all matching `caseid` records.
4. **Deduplication & Selection:**
   - Identical deterministic tie-breaking logic.
5. **Resulting Size:** Exactly **5,987,173 canonical cases** (the current Phase 3A.2 canonical snapshot).
6. **Methodological Trade-Off:** Eliminates known false/retracted reports, preventing the model from learning spurious associations from corrupted records. However, introduces mild look-ahead survivorship bias (0.43% case differential).

---

## 3. Audit of Cross-Table Child Linkage Architecture

The relational structure connecting DEMO to the 6 child tables (`DRUG`, `REAC`, `OUTC`, `RPSR`, `THER`, `INDI`) was audited across the ingestion, preprocessing, pair-building, and feature-extraction pipelines:

### 3.1 PrimaryID Isolation (`PipelineOrchestrator`)
- **Code Reference:** `src/pipeline/pipeline_orchestrator.py`, lines 102–106 and lines 152–155:
  ```python
  # Line 102-106 (Ingestion stage)
  demo_q = loader.load_demo(filter_deleted=True)
  valid_pids = set(demo_q["primaryid"].unique())
  drug_q = loader.load_drug(valid_primaryids=valid_pids)
  reac_q = loader.load_reac(valid_primaryids=valid_pids)

  # Line 152-155 (Post-deduplication child filtering)
  valid_primaryids = set(deduped_demo["primaryid"].unique())
  drug_clean = drug_combined[drug_combined["primaryid"].isin(valid_primaryids)].copy()
  reac_clean = reac_combined[reac_combined["primaryid"].isin(valid_primaryids)].copy()
  outc_clean = outc_combined[outc_combined["primaryid"].isin(valid_primaryids)].copy()
  rpsr_clean = rpsr_combined[rpsr_combined["primaryid"].isin(valid_primaryids)].copy()
  ```
- **Audit Assessment:** **PASS**. Child tables are filtered strictly against the `valid_primaryids` belonging to the canonical selected snapshot. Child records associated with non-selected follow-up versions or post-cutoff submissions are purged prior to normalization.

### 3.2 Join Key Vulnerability in `PairBuilder`
- **Code Reference:** `src/pipeline/pair_builder.py`, lines 127–148:
  ```python
  # Line 127-132: Correct inner merge on primaryid
  pairs = pd.merge(
      d_df[["primaryid", "caseid", "canonical_drug", "role_cod", "norm_status"]],
      r_df[["primaryid", "canonical_pt"]],
      on="primaryid",
      how="inner"
  )

  # Line 136: Deduplication
  pairs = pairs.drop_duplicates(subset=["caseid", "canonical_drug", "canonical_pt"])

  # Line 145: Demographic attachment on caseid
  demo_sub = demo_df[demo_cols].drop_duplicates(subset=["caseid"])
  pairs = pd.merge(pairs, demo_sub, on="caseid", how="inner", suffixes=("", "_demo"))
  
  if "primaryid_demo" in pairs.columns:
      pairs = pairs.drop(columns=["primaryid_demo"])
  ```
- **Audit Assessment:** **FAIL (Latent Architectural Risk)**.
  - While `d_df` and `r_df` are merged on `primaryid` (Line 130), the demographic join on Line 145 merges `pairs` with `demo_sub` **on `"caseid"`**, rather than `primaryid`.
  - In the current pipeline, this is mitigated upstream because `d_df` and `r_df` were already filtered to `valid_primaryids` in `PipelineOrchestrator`.
  - However, if `PairBuilder.build_case_pairs` is called directly with multi-version data, merging on `caseid` would link drugs from a later follow-up version to the demographic attributes of an earlier version.
  - **Remediation Required:** Line 145 should be updated to merge on `primaryid` (or `["primaryid", "caseid"]`).

### 3.3 Assessment of Child Row Deduplication
- **Code Reference:** `src/pipeline/pair_builder.py`, line 136:
  ```python
  pairs = pairs.drop_duplicates(subset=["caseid", "canonical_drug", "canonical_pt"])
  ```
- **Audit Assessment:** **PASS for pair uniqueness; NOTE on role priority**.
  - **Multi-Drug Preservation:** If a case reports Drug A (Metformin) and Drug B (Lisinopril), the subsets are `("C1", "METFORMIN", "PT1")` and `("C1", "LISINOPRIL", "PT1")`. These are distinct and **100% preserved**.
  - **Multi-Reaction Preservation:** If a case reports Reaction 1 (Jaundice) and Reaction 2 (Pruritus), the subsets are `("C1", "METFORMIN", "JAUNDICE")` and `("C1", "METFORMIN", "PRURITUS")`. These are distinct and **100% preserved**.
  - **Duplicate Handling:** If the same drug is listed multiple times under different dosages or sequence numbers for the same event, duplicate pairs are collapsed to 1 occurrence per case. This matches standard pharmacovigilance practice (preventing double-counting in 2x2 contingency tables).
  - **Role Code Priority:** If a drug appears as both Primary Suspect (`PS`) and Secondary Suspect (`SS`), `drop_duplicates` retains the first row encountered. A priority sort on `role_cod` (`PS` before `SS`) should be formally enforced before deduplication.

---

## 4. Unresolved Limitations & Engineering Recommendations

### 4.1 Unresolved Limitations
1. **Unavailability of Intra-Quarter Retraction Dates:**
   - The FDA does not disclose the calendar date a report was retracted. It is fundamentally impossible to know whether a case listed in `ADR19Q2DeletedCases.txt` was retracted on January 15, 2019 or June 1, 2019.
2. **Absence of Pre-2019 Deletion Archives:**
   - Because FDA FAERS public distribution archives for 2014–2018 omitted deletion files, an analyst in 2018 had no standardized machine-readable deletion feed unless they had captured legacy FDA website notices.

### 4.2 Engineering Recommendations for Phase 3B

1. **Maintain Both Snapshots for Sensitivity Analysis (Primary Recommendation):**
   - Retain `data/08_phase3a2_snapshot/canonical_snapshot.csv` as the `RETROSPECTIVELY_CORRECTED` primary training universe (**5,987,173 cases**).
   - In Phase 3B/3C, run a sensitivity check against the `AS_OF_2018` universe (**6,012,891 cases**) to verify that signal discovery performance and PRR/ROR rankings are invariant to the 25,718 retracted cases (0.43% perturbation).
2. **Harden Join Keys in `PairBuilder`:**
   - In `src/pipeline/pair_builder.py` line 145, change `on="caseid"` to `on=["primaryid", "caseid"]`.
   - Before line 136, explicitly sort `pairs` by `role_cod` priority (`PS` > `SS`) so that suspect drug attribution is deterministic if duplicate drug entries exist.
3. **Formalize Documentation in Model Card:**
   - State transparently in the final research paper/model card that retractions were handled under a retrospectively corrected regime, with a measured impact of 0.43% case volume.

---

*Report compiled and verified by automated audit subagent. No code, datasets, or feature matrices were altered during this audit.*
