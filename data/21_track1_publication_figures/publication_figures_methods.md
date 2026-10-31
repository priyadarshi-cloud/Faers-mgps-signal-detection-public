# Publication Figures Methods: TASK-T1-03

**Project:** FAERS Adverse Drug Reaction (ADR) Signal Detection Research  
**Track:** Track 1 — Scientific Validation and Publication Preparation  
**Output directory:** `data/21_track1_publication_figures/`  
**Generator script:** `scripts/generate_task_t1_03_figures.py`  

---

## 1. Scope and Non-Negotiable Constraints

All three figures are produced exclusively from immutable, pre-existing project
artifacts. No model retraining, prior refitting, threshold modification, or data
fabrication was performed. Any figure component that could not be supported by
verified, observation-level data is clearly documented as a limitation.

---

## 2. Figure 1 — Empirical Bayes Shrinkage and PRR Discordance

### 2.1 Source data

| Source file | SHA-256 prefix |
|:---|:---|
| `data/19_track1_contextual_analysis/shrinkage_discordance_by_tier.csv` | `772c44bd` |
| `data/13_phase3c2_mgps_scoring/phase3c2_scored_candidate_pairs.csv` | `79d07631` |

### 2.2 Candidate universe

All **1,167,891** unique drug–ADR pairs with observed report count *a* ≥ 2 from
the archive-bounded FAERS cohort (6,005,839 safety reports across 2004 Q1 –
2023 Q4).  

The Evans PRR decision rule requires *a* ≥ 3; 148,622 pairs with *a* = 2 are
therefore ineligible under the Evans rule but are present in the candidate
universe and are evaluated by EB05.  This eligibility asymmetry is the primary
driver of EB05-only discordance (32,701 pairs, of which 32,486 — 99.3% — fall
in the *a* = 2–3 tier).

### 2.3 Reporting-count tiers

| Tier | a range | N | % of universe |
|:---|:---|---:|---:|
| a = 2–3 | 2–3 | 506,020 | 43.33% |
| a = 4–5 | 4–5 | 181,892 | 15.57% |
| a = 6–10 | 6–10 | 187,995 | 16.10% |
| a = 11–20 | 11–20 | 124,823 | 10.69% |
| a > 20 | 21–32,292 | 167,161 | 14.31% |
| **Overall** | 2–32,292 | **1,167,891** | **100%** |

### 2.4 Decision rules

- **Evans PRR rule:** PRR ≥ 2.0 AND χ² ≥ 4.0 AND a ≥ 3 → **398,018** signals.
- **FDA EB05 rule:** EB05 ≥ 2.0 → **295,560** signals.

### 2.5 Discordance partition

| Category | N | % |
|:---|---:|---:|
| Concordant signals (both) | 262,859 | 22.51% |
| PRR-only discordant | 135,159 | 11.57% |
| EB05-only discordant | 32,701 | 2.80% |
| Concordant non-signals | 737,172 | 63.12% |

**Arithmetic balance:**  135,159 − 32,701 = **102,458** = 398,018 − 295,560 ✓

PRR-only discordant pairs are NOT described as confirmed false positives.
They represent alert-fatigue candidates whose lower Bayesian credibility bound
(EB05) falls below 2.0, indicating statistical uncertainty that precludes a
confident signal assertion under the FDA MGPS standard.

### 2.6 Graphical strategy

- **Scale:** log₁₀(PRR) × log₁₀(EB05), axes bounded [0.08, 2500] × [0.005, 1200].
- **Visualization strategy:** Colored scatter plots with per-category deterministic
  subsampling (seed = 42). Up to 2,000 points sampled per signal-status category
  (Concordant Signal, PRR-Only, EB05-Only, Neither) per tier panel, for a maximum
  of ~8,000 points per panel. Points colored by signal-status category.
- **Overplotting transparency:** Neither-category points plotted at α = 0.15;
  signal-status points at α = 0.45.
- **Threshold lines:** PRR = 2.0 (vertical dashed red) and EB05 = 2.0
  (horizontal dashed blue), both labeled.
- **Layout:** 2-row grid — row 1: overall joint distribution; row 2: five tier
  subpanels with individual hexbin density maps.

### 2.7 Companion table

`figure1_discordance_by_count_tier.csv` records per-tier totals, signal counts,
discordant counts, net reductions, and median PRR / EB05 statistics for each
discordant stratum.  This table is arithmetically verified in the validation
script.

---

## 3. Figure 2 — Independent Benchmark Discrimination

### 3.1 Reference standards

| Standard | Total pairs | FAERS-observed (a ≥ 2) | Pos | Neg |
|:---|---:|---:|---:|---:|
| OMOP | 399 | **203** | 114 | 89 |
| EU-ADR | 94 | **66** | 39 | 27 |

Unobserved pairs (a < 2) are excluded from scoring and evaluation.
OMOP negative controls censored: 145/234 = **61.97%**.
EU-ADR negative controls censored: 23/50 = **46.00%**.

### 3.2 Matched observation files

| File | N | SHA-256 prefix |
|:---|---:|:---|
| `data/14_phase3d_benchmark_evaluation/omop_matched_evaluation_pairs.csv` | 203 | `b0cd1524` |
| `data/14_phase3d_benchmark_evaluation/eu_adr_matched_evaluation_pairs.csv` | 66 | `e82e226e` |

Identical paired observations (same rows, same scores) are used across all four
methods (EB05, EBGM, PRR, ROR) within each benchmark.

### 3.3 Curves

Precision-recall (PR) and receiver operating characteristic (ROC) curves are
constructed via `sklearn.metrics.precision_recall_curve` and `roc_curve` using
the continuous disproportionality scores as ranking statistics.  
PR curves use step-wise interpolation; no probability calibration is applied.

### 3.4 Verified AUC values

| Benchmark | Method | PR-AUC | ROC-AUC |
|:---|:---|---:|---:|
| OMOP | EB05 | 0.8619 | 0.8136 |
| OMOP | EBGM | 0.8498 | 0.8071 |
| OMOP | PRR | 0.8313 | 0.7995 |
| OMOP | ROR | 0.8299 | 0.7986 |
| EU-ADR | EB05 | 0.9578 | 0.9364 |
| EU-ADR | EBGM | 0.9486 | 0.9240 |
| EU-ADR | PRR | 0.9362 | 0.9060 |
| EU-ADR | ROR | 0.9376 | 0.9069 |

All AUC values are sourced from and cross-checked against  
`data/14_phase3d_benchmark_evaluation/phase3d_benchmark_evaluation_results.json`
(SHA-256: `75124b2a`).

### 3.5 Baseline references

- PR baseline: empirical positive prevalence per benchmark  
  (OMOP: 114/203 = 56.16%; EU-ADR: 39/66 = 59.09%).
- ROC baseline: random classifier diagonal (AUC = 0.5000).

### 3.6 Epidemiological caveat

All discrimination metrics are conditioned on a ≥ 2.  The systematic
exclusion of unobserved pairs — especially true negative controls — inflates
apparent precision.  Results do not extend to unobserved drug–ADR pairs.

---

## 4. Figure 3 — Contextual Feature Distributions Across EB05 Strata

### 4.1 Source data

| File | SHA-256 prefix |
|:---|:---|
| `data/19_track1_contextual_analysis/contextual_strata_summary.csv` | `cdd432d0` |
| `data/19_track1_contextual_analysis/contextual_strata_tests.csv` | `239ee31a` |

### 4.2 EB05 strata

| Stratum | N | % of universe |
|:---|---:|---:|
| EB05 < 1.0 | 677,671 | 58.03% |
| 1.0 ≤ EB05 < 2.0 | 194,660 | 16.67% |
| 2.0 ≤ EB05 < 5.0 | 143,877 | 12.32% |
| 5.0 ≤ EB05 < 10.0 | 50,946 | 4.36% |
| EB05 ≥ 10.0 | 100,737 | 8.63% |
| **Total** | **1,167,891** | **100%** |

### 4.3 The 11 contextual features

1. `mean_age` — mean patient age across reports for the pair
2. `median_age` — median patient age
3. `age_std` — SD of patient age
4. `age_missing_ratio` — proportion of reports missing age
5. `female_ratio` — proportion specifying female sex
6. `primary_suspect_ratio` — proportion coding drug as Primary Suspect (PS)
7. `secondary_suspect_ratio` — proportion coding drug as Secondary Suspect (SS)
8. `polypharmacy_mean` / `mean_concomitant_count` — mean concomitant drug count
9. `physician_reporter_ratio` / `hp_reporter_ratio` — physician-submitted reports
10. `csm_reporter_ratio` — health professional (non-physician) submitted reports
11. `consumer_reporter_ratio` / `monotherapy_ratio` — consumer-submitted reports

### 4.4 Graphical layout

- 4 × 3 small-multiple grid: 11 feature panels + 1 effect-size ranking panel.
- Distributional representation drawn from aggregate summary statistics
  (`contextual_strata_summary.csv`): median (bar center), interquartile range
  Q25/Q75 (error bars), and arithmetic mean (red diamond) per stratum.
- Missingness percentage annotated per stratum where non-zero.

### 4.5 Statistical tests

Kruskal-Wallis omnibus H-tests were computed on pair-level data in TASK-T1-01
(`scripts/run_task_t1_01_contextual_analysis.py`). Adjusted p-values use
Benjamini-Hochberg FDR. All 11 features are statistically significant (all
q < 10⁻³²), but all practical effect sizes (ε²) are small or negligible.

| Feature | ε² | Interpretation |
|:---|---:|:---|
| secondary_suspect_ratio | 0.0273 | Small |
| csm_reporter_ratio | 0.0182 | Small |
| age_std | 0.0107 | Small |
| mean_age | 0.0091 | Negligible |
| median_age | 0.0079 | Negligible |
| hp_reporter_ratio | 0.0037 | Negligible |
| mean_concomitant_count | 0.0037 | Negligible |
| female_ratio | 0.0027 | Negligible |
| monotherapy_ratio | 0.0072 | Negligible |
| age_missing_ratio | 0.0001 | Negligible |

Scientific emphasis is on effect magnitude, not p-values.

### 4.6 Limitation

Contextual features describe observational reporting patterns.  Differences
across EB05 strata reflect pharmacological and clinical confounders inherent to
spontaneous reporting systems.  They do NOT establish pharmacological causality
or independently confirm clinical ADRs.

---

## 5. Technical Specifications

| Figure | PNG dimensions | DPI | PDF format |
|:---|:---|---:|:---|
| Figure 1 | 4305 × 2767 px | 300 | Vector |
| Figure 2 | 3378 × 3124 px | 300 | Vector |
| Figure 3 | 4571 × 3286 px | 300 | Vector |

**Software:** Python 3.13, matplotlib 3.11, pandas 3.0, scikit-learn 1.9, scipy 1.18.  
**Reproducibility:** All figures regenerable with `python scripts/generate_task_t1_03_figures.py`.  
**Validation:** `python data/21_track1_publication_figures/validate_task_t1_03_figures.py`.
