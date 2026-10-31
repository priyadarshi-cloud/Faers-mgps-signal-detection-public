# TASK-T1-12: Final Scientific Corrections and Contextual Reporter Audit Report

**Task Identifier:** TASK-T1-12  
**Project:** FDA FAERS Adverse Drug Reaction (ADR) Signal Detection Research  
**Output Directory:** `data/34_task_t1_12_final_scientific_corrections/`  
**Execution Date:** October 2026  
**Status:** Completed, Verified, and Evidence-Controlled  

---

## Executive Summary

TASK-T1-12 executes four essential scientific corrections and a full source-level contextual reporter audit on the FAERS ADR signal-detection research project. Continuing directly from `TASK-T1-11`, this task resolves lingering terminology discrepancies, performs a regulatory data dictionary audit of reporter classification codes, recomputes affected reporter features directly from underlying child tables, removes overclaims regarding truncation likelihood and alert volatility, and integrates verified evidence into a final scientifically corrected manuscript (`manuscript_final_scientifically_corrected.md`).

### Key Accomplishments and Audit Results

1. **Reporter Classification & Lawyer (`LW`) Code Resolution:**
   - Source code audit revealed that occupation code `LW` (Lawyer / Attorney) was previously grouped under `hp_occupations` in `src/features/feature_extractor.py:146`.
   - Authoritative FDA FAERS data dictionaries confirm that `LW` designates a legal representative, typically filing in product liability or litigation contexts, not a healthcare professional.
   - The feature definition was corrected to exclude `LW` from healthcare professionals (`MD, PH, HP, RN`).
   - All 84,992 primary cases with `occp_cod == 'LW'` and `rpsr_cod != 'HP'` were extracted from 20 quarterly FAERS child tables (2014Q1–2018Q4), yielding 649,422 suspect pair occurrences across 52,699 affected candidate pairs.
   - Across the 1,167,891 candidate pairs ($a \ge 2$), only 43,709 pairs (3.74%) were affected, with a negligible mean reduction in `hp_reporter_ratio` of $-0.0080$ ($0.3431 \to 0.3351$).
   - Recomputation across EB05 strata confirmed that the Kruskal–Wallis test remains significant ($H = 3839.98$, $p < 10^{-30}$), the effect size remains strictly negligible ($\epsilon^2 = 0.0033$, previously $0.0037$), and the Stratum 5 mean updates from $0.37$ to $0.36$ ($0.3557$).

2. **Non-Complementary Denominators Explicitly Documented:**
   - Both `hp_reporter_ratio` and `csm_reporter_ratio` are evaluated as means over total pair occurrences $a$. Reports with unrecorded reporter qualifications or occupation code `OT` (Other) without a healthcare professional or consumer transmission flag contribute $0.0$ to both numerators.
   - Consequently, the two ratios do not sum to 1.0 (typical stratum sum: $0.60$ to $0.75$), and neither constitutes a complementary partition. This behavior is now explicitly stated in Methods Section 2.8 and Table 4.

3. **Conditional Truncation Likelihood Formulation:**
   - The unsupported claim that truncated likelihood estimation "avoids bias in prior hyperparameters" has been removed.
   - The manuscript now states precisely that the conditional likelihood mathematically accounts for the candidate-universe left-truncation ($a \ge 2$) under the fitted conditional model, while preserving explicit caveats regarding $\alpha_1$ lower-bound contact ($0.001$), ranking invariance ($\rho > 0.999999$), and parameter non-identification.

4. **Threshold-Count Discordance vs. Volatility:**
   - Unsupported phrases such as "reduces low-count alert volatility" and "eliminating 102,458 net frequentist alerts" were eliminated.
   - Verified counts are reported: EB05 $\ge 2$: 295,560; Evans PRR: 398,018; Net threshold difference: 102,458; PRR-only: 135,159; EB05-only: 32,701 (including 32,397 at $a=2$).
   - These are described accurately as threshold-positive pair-count differences and reporting discordance, rather than measured volatility reduction or verified false-positive suppression.

5. **Benchmark Metric Terminology and Power Framing:**
   - Inspection of `scripts/independent_benchmark_audit_t1_11.py` confirmed that precision-recall discrimination is computed using `sklearn.metrics.average_precision_score`.
   - The manuscript explicitly designates this metric as Average Precision ($\text{AP}$, denoted $\text{PR-AUC}/\text{AP}$), eliminating inaccurate claims of "interpolated PR-curve area".
   - Confidence intervals in Table 3 are documented as derived from $B = 2{,}000$ paired bootstrap resamples with seed 42 and shared row indices across methods.
   - The manuscript states that paired confidence intervals crossing zero do not establish statistically significant superiority at $\alpha = 0.05$, removing secondary claims that low power was proven solely from those intervals.

---

## 1. Reporter-Code Mapping & Data Dictionary Audit

### 1.1 Source Code Lineage
In `src/features/feature_extractor.py:137-155`:
```python
# Primary source: RPSR table (report source code)
hp_cases.update(rpsr_clean[rpsr_clean["rpsr_cod"] == "HP"]["caseid"].unique())
csm_cases.update(rpsr_clean[rpsr_clean["rpsr_cod"] == "CSM"]["caseid"].unique())

# Secondary source: DEMO table (occupation code)
hp_occupations = {"MD", "PH", "HP", "RN", "LW", "PHYSICIAN", "PHARMACIST", ...}
csm_occupations = {"CN", "CSM", "CONSUMER", ...}

is_hp_reported = (pairs["caseid"].isin(hp_cases) | occp_s.isin(hp_occupations)).astype(float)
is_csm_reported = (pairs["caseid"].isin(csm_cases) | occp_s.isin(csm_occupations)).astype(float)
```

### 1.2 Authoritative FDA FAERS Data Dictionary Mapping
Per the official US FDA FAERS Data Dictionary (DEMO and RPSR table specifications):

| Table | Column | Code | Official Meaning | Original Mapping | Corrected Mapping | Cohort Count ($N=6,005,839$) | Cohort Pct |
|:---|:---|:---:|:---|:---:|:---:|:---:|:---:|
| `DEMO` | `occp_cod` | `MD` | Physician | `hp_occupations` | `hp_occupations` | 1,318,291 | 21.950% |
| `DEMO` | `occp_cod` | `PH` | Pharmacist | `hp_occupations` | `hp_occupations` | 413,742 | 6.889% |
| `DEMO` | `occp_cod` | `RN` | Registered Nurse | `hp_occupations` | `hp_occupations` | 2,354 | 0.039% |
| `DEMO` | `occp_cod` | `HP` | Health Professional | `hp_occupations` | `hp_occupations` | 0 | 0.000% |
| `DEMO` | `occp_cod` | `LW` | **Lawyer / Attorney** | **`hp_occupations`** | **EXCLUDED (Legal / Non-HP)** | **85,337** | **1.421%** |
| `DEMO` | `occp_cod` | `CN` | Consumer | `csm_occupations` | `csm_occupations` | 2,940,798 | 48.966% |
| `DEMO` | `occp_cod` | `CSM`| Consumer Safety Monitor | `csm_occupations` | `csm_occupations` | 0 | 0.000% |
| `DEMO` | `occp_cod` | `OT` | Other | Excluded (0.0) | Excluded (0.0) | 1,089,005 | 18.132% |
| `DEMO` | `occp_cod` | `NULL`| Missing / Unrecorded | Excluded (0.0) | Excluded (0.0) | 156,310 | 2.603% |
| `DEMO` | `occp_cod` | `SALES`| Manufacturer Sales Rep | Excluded (0.0) | Excluded (0.0) | 2 | 0.000% |
| `RPSR` | `rpsr_cod` | `HP` | Health Professional | `hp_cases` | `hp_cases` | 224,809 | 3.743% |
| `RPSR` | `rpsr_cod` | `CSM`| Consumer | `csm_cases` | `csm_cases` | 188,612 | 3.140% |
| `RPSR` | `rpsr_cod` | `OT` | Other | Excluded (0.0) | Excluded (0.0) | 11,354 | 0.189% |
| `RPSR` | `rpsr_cod` | `FGN`| Foreign Authority | Excluded (0.0) | Excluded (0.0) | 42,203 | 0.703% |
| `RPSR` | `rpsr_cod` | `LIT`| Literature | Excluded (0.0) | Excluded (0.0) | 89,504 | 1.490% |
| `RPSR` | `rpsr_cod` | `STD`| Clinical Study | Excluded (0.0) | Excluded (0.0) | 12,739 | 0.212% |

### 1.3 Identification of the Lawyer (`LW`) Misclassification
- **Regulatory Nature:** In FDA FAERS data documentation, `LW` identifies reports where the designated reporter occupation is an attorney or legal representative. These reports typically arise in the context of pharmaceutical product liability litigation or mass-tort claims.
- **Scientific Impact:** Attorneys are legal representatives representing clients, not healthcare clinical practitioners administering, prescribing, or monitoring pharmacotherapy. Grouping `LW` into healthcare professional reporting erroneously conflates legal filings with clinical bedside vigilance.
- **Correction:** `LW` was excised from `hp_occupations`. Reports where `occp_cod == 'LW'` now contribute $0.0$ to `hp_reporter_ratio` unless the report was independently transmitted by a healthcare professional source (`rpsr_cod == 'HP'`, which occurred in only 345 cases).

### 1.4 Non-Complementary Denominators
For each candidate pair $(i, j)$:
$$\text{hp\_reporter\_ratio} = \frac{1}{a} \sum_{k=1}^a \mathbb{I}(\text{case}_k \in \text{HP})$$
$$\text{csm\_reporter\_ratio} = \frac{1}{a} \sum_{k=1}^a \mathbb{I}(\text{case}_k \in \text{CSM})$$
- Because cases with unrecorded occupation or code `OT` (Other) without a specific HP or CSM flag contribute $0.0$ to both numerators while incrementing $a$, $\text{hp\_reporter\_ratio} + \text{csm\_reporter\_ratio} < 1.0$.
- In the primary dataset, the sum across strata medians is typically $0.60$ to $0.75$. The remainder represents unclassified reporters, manufacturer sales representatives, or unrecorded fields.
- The manuscript now explicitly alerts readers that these ratios do not constitute a complementary partition.

---

## 2. Empirical Recomputation of Reporter Ratios

### 2.1 Recomputation Pipeline
To avoid regenerating the entire 1.167-million-pair feature matrix from scratch, a targeted, exact recomputation was executed via `scripts/recompute_hp_without_lw.py`:
1. **Case Sequestration:** Identified 84,992 primary cases with `occp_cod == 'LW'` and `rpsr_cod != 'HP'`.
2. **Occurrence Ingestion:** Scanned 20 quarterly child tables (`DRUG` and `REAC`), extracting 689,050 drug records and 262,846 reaction records belonging to these cases.
3. **Normalization & Pairing:** Standardized active ingredients and mapped MedDRA PTs using `PairBuilder`, identifying 649,422 case-level suspect pair occurrences affecting 52,699 candidate pairs (cached in `lw_pair_counts.csv`).
4. **Exact Mathematical Correction:** For each candidate pair $(i, j)$ with observed co-occurrence count $a_{ij}$ and $m_{ij}$ reports from affected `LW` cases:
   $$\text{hp\_reporter\_ratio}_{\text{new}}(i, j) = \text{hp\_reporter\_ratio}_{\text{old}}(i, j) - \frac{m_{ij}}{a_{ij}}$$
5. **Statistical Re-evaluation:** Recomputed overall universe statistics, stratum-by-stratum medians, IQRs, means, standard deviations, Kruskal–Wallis omnibus $H$ statistics, and epsilon-squared ($\epsilon^2$) effect sizes.

### 2.2 Recomputation Results Summary

| Metric / Stratum | Old Value (With `LW`) | Corrected Value (Without `LW`) | Absolute Delta | Relative Change |
|:---|:---:|:---:|:---:|:---:|
| **Overall Universe Mean** | 0.3431 | 0.3351 | −0.0080 | −2.33% |
| **Overall Universe Median** | 0.3333 | 0.3261 | −0.0072 | −2.16% |
| **Stratum 1 Mean (EB05 < 1.0)** | 0.3320 | 0.3251 | −0.0069 | −2.08% |
| **Stratum 1 Median (EB05 < 1.0)** | 0.3333 | 0.3030 | −0.0303 | −9.09% |
| **Stratum 2 Mean (1.0 ≤ EB05 < 2.0)** | 0.3503 | 0.3426 | −0.0077 | −2.20% |
| **Stratum 2 Median (1.0 ≤ EB05 < 2.0)** | 0.3333 | 0.3333 | 0.0000 | 0.00% |
| **Stratum 3 Mean (2.0 ≤ EB05 < 5.0)** | 0.3598 | 0.3511 | −0.0087 | −2.42% |
| **Stratum 3 Median (2.0 ≤ EB05 < 5.0)** | 0.3333 | 0.3333 | 0.0000 | 0.00% |
| **Stratum 4 Mean (5.0 ≤ EB05 < 10.0)** | 0.3623 | 0.3527 | −0.0096 | −2.65% |
| **Stratum 4 Median (5.0 ≤ EB05 < 10.0)** | 0.3333 | 0.3333 | 0.0000 | 0.00% |
| **Stratum 5 Mean (EB05 ≥ 10.0)** | 0.3696 | 0.3557 | −0.0139 | −3.76% |
| **Stratum 5 Median (EB05 ≥ 10.0)** | 0.3333 | 0.3333 | 0.0000 | 0.00% |
| **Kruskal–Wallis $H$ Statistic** | 4,303.36 | 3,839.98 | −463.38 | −10.77% |
| **Epsilon-squared ($\epsilon^2$) Effect Size** | 0.0037 | 0.0033 | −0.0004 | −10.81% |

### 2.3 Scientific Implications of the Correction
- **Qualitative Invariant:** The monotonic trajectory across strata is preserved: `hp_reporter_ratio` mean remains stable to slightly increasing across strata ($0.325 \to 0.356$; rounded: $0.33 \to 0.36$).
- **Effect Size Invariant:** Practical magnitude remains strictly **Negligible** ($\epsilon^2 = 0.0033 < 0.01$).
- **Manuscript Text Correction:** In the Abstract and Results Section 3.5, the mean range is updated from "mean: 0.33 to 0.37" to "mean: 0.33 to 0.36", and $\epsilon^2$ is updated from $0.0037$ to $0.0033$.

---

## 3. Conditional Truncation Likelihood Wording Correction

### 3.1 Background of the Overclaim
Prior drafts stated that the truncated likelihood "avoids bias in prior hyperparameters." This wording overclaimed complete elimination of bias. In observational spontaneous reporting, empirical Bayes prior estimation is subject to multiple structural reporting artifacts:
1. Left-truncation at $a \ge 2$ removes unobserved or single-report pairs from the likelihood.
2. Zero-inflation and extreme reporting sparsity cause the shape parameter $\alpha_1$ to converge to the lower optimization bound ($0.0010$).

### 3.2 Corrected Mathematical Framing
In `manuscript_final_scientifically_corrected.md` (Methods Section 2.4 and Strengths Section 5.1):
- The phrase "avoids bias in prior hyperparameters" was excised.
- The text now states:
  > *"Truncation at $a \ge 2$ mathematically accounts for candidate-universe left-truncation under the fitted conditional model, while leaving observational reporting biases to be addressed through contextual analysis."*
- Caveats regarding $\alpha_1$ boundary contact, parameter non-identification away from zero, and score calibration for borderline pairs at $a = 2$ are preserved intact in Sections 3.2, 4.2, and 5.2.

---

## 4. Threshold-Count Claims & Reporting Discordance

### 4.1 Audited Threshold Counts
The manuscript was audited to ensure exact agreement with verified counting artifacts (`data/13_phase3c2_mgps_scoring/phase3c2_summary_metrics.json` and `data/19_track1_contextual_analysis/shrinkage_discordance_by_tier.csv`):
- **Candidate Universe ($a \ge 2$):** 1,167,891 pairs.
- **EB05 ≥ 2.0 Signals:** 295,560 pairs (25.31%).
- **Evans PRR Signals ($a \ge 3$, PRR $\ge 2.0$, $\chi^2 \ge 4.0$):** 398,018 pairs (34.08%).
- **Concordant Signals (Both Positive):** 262,859 pairs.
- **Concordant Non-Signals (Both Negative):** 737,172 pairs.
- **Net Threshold-Positive Difference:** 102,458 pairs (−25.74% relative to PRR).
- **PRR-Only Discordant Pairs:** 135,159 pairs.
- **EB05-Only Discordant Pairs:** 32,701 pairs (including 32,397 pairs [99.07%] at $a = 2$).

### 4.2 Replaced Interpretative Claims
- **Replaced:** "reduces low-count alert volatility"  
  **With:** "restrains sparse-count ratio inflation relative to PRR under Bayesian shrinkage without arbitrary count exclusion".
- **Replaced:** "eliminating 102,458 net frequentist alerts"  
  **With:** "demonstrates a threshold-positive pair-count reduction of 102,458 pairs (−25.74% relative to PRR)".
- **Replaced:** Unsubstantiated claims of "false-positive reduction"  
  **With:** Precise explanation that the 135,159 PRR-only pairs reflect Bayesian shrinkage regularizing small-sample reporting variance at $a = 2–3$, rather than verified false-positive alerts, because spontaneous reports lack reference-standard adjudication.

---

## 5. Benchmark Metric Terminology & Statistical Inference

### 5.1 Confirmation of Metric Implementation
Inspection of `scripts/independent_benchmark_audit_t1_11.py:28-74`:
- Precision-recall performance is computed via:
  ```python
  from sklearn.metrics import average_precision_score, roc_auc_score
  pr_point = average_precision_score(labels, scores)
  ```
- In scikit-learn, `average_precision_score` calculates discrete Average Precision ($\text{AP}$):
  $$\text{AP} = \sum_n (R_n - R_{n-1}) P_n$$
  where $P_n$ and $R_n$ are precision and recall at the $n^{\text{th}}$ threshold.
- This is a weighted-step Average Precision metric, **not** continuous trapezoidal integration or linear interpolation across the precision-recall curve.
- In `manuscript_final_scientifically_corrected.md`, the metric is explicitly defined as **Average Precision ($\text{AP}$)**, denoted as $\text{PR-AUC}/\text{AP}$, removing inaccurate descriptions of "interpolated area under precision-recall curve".

### 5.2 Bootstrap Design and Table 3 Parameters
- Table 3 confidence intervals represent $B = 2{,}000$ paired bootstrap resamples with seed 42 and shared row indices across methods.
- Earlier $B = 1{,}000$ values from exploratory fits are preserved in historical audit trails but explicitly distinguished from Table 3 values.

### 5.3 Superiority and Power Claims
- **Corrected Framing:** The manuscript states:
  > *"Because each paired 95% confidence interval includes zero, these observed point-estimate differences do not establish statistically significant discrimination superiority at $\alpha = 0.05$."*
- Assertions that "statistical power was proven insufficient" have been removed, as the paired bootstrap confidence intervals establish that superiority is not demonstrated, but do not themselves constitute an empirical power calculation.

---

## 6. Deliverables and Artifact Manifest

All 10 required deliverables for TASK-T1-12 are complete and located in `data/34_task_t1_12_final_scientific_corrections/`:

| Deliverable | File | Size | Description |
|:---|:---|:---:|:---|
| 1. Recovery Report | `recovery_report.md` | ~2.5 KB | Incident recovery checkpoint audit |
| 2. Scientific Corrections Report | `scientific_corrections_report.md` | ~16.5 KB | Comprehensive technical audit report |
| 3. Reporter Code Dictionary Audit | `reporter_code_dictionary_audit.csv` | 3,227 B | Complete 16-code DEMO/RPSR dictionary mapping |
| 4. Recomputation Summary | `reporter_feature_recomputation_summary.csv` | 453 B | Recomputed universe and strata statistics |
| 5. Contextual Discrepancy Log | `contextual_results_discrepancy_log.csv` | 3,859 B | Catalog of 10 contextual discrepancies resolved |
| 6. Manuscript Change Log | `manuscript_change_log.csv` | 7,422 B | Catalog of 16 specific manuscript edits |
| 7. Scientifically Corrected Manuscript | `manuscript_final_scientifically_corrected.md` | 37,210 B | Final evidence-controlled manuscript draft |
| 8. Claims Traceability | `claims_traceability.csv` | 6,850 B | Verification of 16 scientific claims against data |
| 9. Validation Script | `validation_script.py` | ~13 KB | Deterministic zero-dependency test suite |
| 10. Artifact Manifest | `artifact_manifest.json` | ~1.5 KB | Cryptographic SHA-256 and byte-length catalog |

---

## 7. Audit Conclusion & Readiness for Scientific Review

The scientific corrections implemented in TASK-T1-12 resolve all remaining wording overclaims, align reporter feature definitions with official FDA data dictionaries, provide exact empirical recomputation for affected features, and ensure complete fidelity between code implementations and manuscript text.

The evidence base is mathematically verified, reproducible, and ready for independent peer review.
