# Publication Figures Audit Report: TASK-T1-03

**Task:** TASK-T1-03 — Publication Figures Production and Validation  
**Track:** Track 1 — Scientific Validation and Publication Preparation  
**Audit date:** 2026-10-15  
**Auditor:** Automated validation pipeline  

---

## 1. Recovered Execution State

### 1.1 Pre-existing completed work
All three figure pairs (PNG + PDF) and the companion CSV were already present
in `data/21_track1_publication_figures/` prior to this audit execution.  The
following documents were missing and are created in this session:
- `publication_figures_methods.md` ← **created now**
- `publication_figures_audit_report.md` ← **created now**
- `publication_figures_manifest.json` ← **created now**

No figures were regenerated, overwritten, or modified.

---

## 2. Upstream Source Integrity

| Artifact role | File path | Size (bytes) | SHA-256 |
|:---|:---|---:|:---|
| Primary scored pairs | `data/13_phase3c2_mgps_scoring/phase3c2_scored_candidate_pairs.csv` | 346,348,936 | `79d07631e65fef8a…` |
| OMOP matched pairs | `data/14_phase3d_benchmark_evaluation/omop_matched_evaluation_pairs.csv` | 39,430 | `b0cd1524cff3b89b…` |
| EU-ADR matched pairs | `data/14_phase3d_benchmark_evaluation/eu_adr_matched_evaluation_pairs.csv` | 12,974 | `e82e226e835d51e1…` |
| Benchmark AUC JSON | `data/14_phase3d_benchmark_evaluation/phase3d_benchmark_evaluation_results.json` | 16,837 | `75124b2aa29e7e6b…` |
| Strata summary | `data/19_track1_contextual_analysis/contextual_strata_summary.csv` | 6,660 | `cdd432d07557c50c…` |
| Strata test results | `data/19_track1_contextual_analysis/contextual_strata_tests.csv` | 1,919 | `239ee31a4b882f4d…` |
| Shrinkage tier CSV | `data/19_track1_contextual_analysis/shrinkage_discordance_by_tier.csv` | 1,824 | `772c44bd7f4ff43d…` |
| Signal contrast JSON | `data/19_track1_contextual_analysis/signal_contrast_statistics.json` | 14,083 | `8bb6d643aa9b0c1a…` |

None of the above upstream artifacts were modified during TASK-T1-03.

---

## 3. Figure 1 — Shrinkage and Discordance Audit

### 3.1 Input traceability
- Primary data: `shrinkage_discordance_by_tier.csv` (identical to `figure1_discordance_by_count_tier.csv`; SHA-256 match confirms byte-for-byte identity).
- Score columns sourced from `phase3c2_scored_candidate_pairs.csv` during TASK-T1-01.

### 3.2 Arithmetic reconciliation

| Quantity | Expected | Source |
|:---|---:|:---|
| Total candidate universe | 1,167,891 | Primary scored pairs |
| Evans PRR signals | 398,018 | Tier CSV overall row |
| EB05 signals | 295,560 | Tier CSV overall row |
| Concordant signals (both) | 262,859 | Tier CSV |
| PRR-only discordant | 135,159 | Tier CSV |
| EB05-only discordant | 32,701 | Tier CSV |
| Concordant non-signals | 737,172 | Tier CSV |
| Net signal reduction | 102,458 | 398,018 − 295,560 |
| Balance check (PRR_only − EB05_only) | 102,458 | 135,159 − 32,701 ✓ |
| Sum of 5 tier rows | 1,167,891 | Tier CSV ✓ |

### 3.3 Tier-level discordance summary

| Tier | N pairs | PRR signals | EB05 signals | PRR-only | EB05-only |
|:---|---:|---:|---:|---:|---:|
| a = 2–3 | 506,020 | 69,103 | 62,473 | 39,116 | 32,486 |
| a = 4–5 | 181,892 | 81,583 | 47,017 | 34,676 | 110 |
| a = 6–10 | 187,995 | 94,423 | 63,027 | 31,466 | 70 |
| a = 11–20 | 124,823 | 65,083 | 47,995 | 17,113 | 25 |
| a > 20 | 167,161 | 87,826 | 75,048 | 12,788 | 10 |
| **Overall** | **1,167,891** | **398,018** | **295,560** | **135,159** | **32,701** |

### 3.4 Documented disclosures

1. The Evans PRR rule requires a ≥ 3; the candidate universe includes a = 2.
   This is the dominant cause of EB05-only discordant pairs (32,486 / 32,701 = 99.3% in tier a = 2–3).
2. PRR-only discordant pairs are NOT described as false positives.
3. Deterministic subsample of N = 10,000 used for scatter overlay (seed = 42).
4. Log₁₀ scale applied to both PRR and EB05 axes for readability.
5. Hexagonal binning (grid 90, log-count) used to handle 1,167,891 observations.

### 3.5 Figure 1 output verification

| File | Size (bytes) | SHA-256 | PNG dims (px) |
|:---|---:|:---|:---|
| `figure1_eb_shrinkage.png` | 1,382,507 | `fa802f82acdce80f…` | 4305 × 2767 |
| `figure1_eb_shrinkage.pdf` | 555,829 | `0b68bebc79f71e54…` | Vector |
| `figure1_discordance_by_count_tier.csv` | 1,824 | `772c44bd7f4ff43d…` | — |

---

## 4. Figure 2 — Benchmark Curves Audit

### 4.1 Data availability confirmation
Observation-level matched files with continuous disproportionality scores are
confirmed to exist for both benchmark standards:

| File | N pairs | Positives | Negatives | SHA-256 |
|:---|---:|---:|---:|:---|
| `omop_matched_evaluation_pairs.csv` | 203 | 114 | 89 | `b0cd1524…` |
| `eu_adr_matched_evaluation_pairs.csv` | 66 | 39 | 27 | `e82e226e…` |

Both files contain columns: `eb05`, `ebgm`, `prr`, `ror`, `groundTruth`, `a`.

### 4.2 Curve construction
- All four methods (EB05, EBGM, PRR, ROR) are evaluated on identical matched
  pairs within each benchmark.
- `sklearn.metrics.precision_recall_curve` and `roc_curve` with `pos_label=1`.
- No score interpolation, probability calibration, or synthetic augmentation.

### 4.3 AUC concordance with source JSON

| Benchmark | Method | Plot PR-AUC | JSON PR-AUC | Match | Plot ROC-AUC | JSON ROC-AUC | Match |
|:---|:---|---:|---:|:---|---:|---:|:---|
| OMOP | EB05 | 0.8619 | 0.8619 | ✓ | 0.8136 | 0.8136 | ✓ |
| OMOP | EBGM | 0.8498 | 0.8498 | ✓ | 0.8071 | 0.8071 | ✓ |
| OMOP | PRR | 0.8313 | 0.8313 | ✓ | 0.7995 | 0.7995 | ✓ |
| OMOP | ROR | 0.8299 | 0.8299 | ✓ | 0.7986 | 0.7986 | ✓ |
| EU-ADR | EB05 | 0.9578 | 0.9578 | ✓ | 0.9364 | 0.9364 | ✓ |
| EU-ADR | EBGM | 0.9486 | 0.9486 | ✓ | 0.9240 | 0.9240 | ✓ |
| EU-ADR | PRR | 0.9362 | 0.9362 | ✓ | 0.9060 | 0.9060 | ✓ |
| EU-ADR | ROR | 0.9376 | 0.9376 | ✓ | 0.9069 | 0.9069 | ✓ |

### 4.4 Negative control censoring disclosure

| Benchmark | Reference neg controls | Unobserved (a<2) | Censoring rate |
|:---|---:|---:|---:|
| OMOP | 234 | 145 | 61.97% |
| EU-ADR | 50 | 23 | 46.00% |

Discrimination metrics are conditioned on a ≥ 2 and do NOT extrapolate to
unobserved pairs.

### 4.5 Figure 2 output verification

| File | Size (bytes) | SHA-256 | PNG dims (px) |
|:---|---:|:---|:---|
| `figure2_benchmark_curves.png` | 734,705 | `3155bc4f31ad1e0b…` | 3378 × 3124 |
| `figure2_benchmark_curves.pdf` | 60,999 | `48aa01653c7c3630…` | Vector |

---

## 5. Figure 3 — Contextual Features Audit

### 5.1 Source data availability
Pair-level raw feature data are not stored in the output directory; aggregate
summaries are available in `contextual_strata_summary.csv`.  Boxplot
representations in Figure 3 are constructed from these pre-computed summary
statistics (median, Q25, Q75, min, max) per stratum.  This is documented
explicitly on the figure and is scientifically defensible — no distributions
were invented.

### 5.2 Stratum counts

| Stratum | N pairs | % |
|:---|---:|---:|
| EB05 < 1.0 | 677,671 | 58.03% |
| 1.0 ≤ EB05 < 2.0 | 194,660 | 16.67% |
| 2.0 ≤ EB05 < 5.0 | 143,877 | 12.32% |
| 5.0 ≤ EB05 < 10.0 | 50,946 | 4.36% |
| EB05 ≥ 10.0 | 100,737 | 8.63% |
| **Total** | **1,167,891** | **100%** |

### 5.3 Feature effect size and significance

| Rank | Feature | ε² | Interpretation | Kruskal-Wallis H | q-value |
|:---|:---|---:|:---|---:|:---|
| 1 | secondary_suspect_ratio | 0.0273 | Small | 31,932.8 | <10⁻³² |
| 2 | csm_reporter_ratio | 0.0182 | Small | 21,275.8 | <10⁻³² |
| 3 | age_std | 0.0107 | Small | 10,084.7 | <10⁻³² |
| 4 | mean_age | 0.0091 | Negligible | 9,951.1 | <10⁻³² |
| 5 | median_age | 0.0079 | Negligible | 8,579.9 | <10⁻³² |
| 6 | monotherapy_ratio | 0.0071 | Negligible | 8,345.2 | <10⁻³² |
| 7 | hp_reporter_ratio | 0.0037 | Negligible | 4,303.4 | <10⁻³² |
| 8 | mean_concomitant_count | 0.0037 | Negligible | 4,316.1 | <10⁻³² |
| 9 | female_ratio | 0.0027 | Negligible | 3,136.6 | <10⁻³² |
| 10 | male_ratio | 0.0006 | Negligible | 734.2 | <10⁻³² |
| 11 | age_missing_ratio | 0.0001 | Negligible | 155.4 | 1.4×10⁻³² |

All effects are statistically significant (q < 10⁻³²) due to very large N.
The scientific focus is on practical effect magnitudes only.

### 5.4 Figure 3 output verification

| File | Size (bytes) | SHA-256 | PNG dims (px) |
|:---|---:|:---|:---|
| `figure3_contextual_features.png` | 786,307 | `e55d1e8216…` | 4571 × 3286 |
| `figure3_contextual_features.pdf` | 66,217 | `12b2531b0a…` | Vector |

---

## 6. Scientific Safeguard Checklist

| Safeguard | Status |
|:---|:---|
| Figures traced to input files with SHA-256 hashes | ✓ |
| Clear axis titles, units, legends, readable fonts | ✓ |
| Consistent method labels and colors across panels | ✓ |
| Transformations documented (log scale, hexbin, 10K sample seed=42) | ✓ |
| Missing values preserved; no silent zero-imputation | ✓ |
| External benchmark labels NOT used for training or tuning | ✓ |
| PRR-only pairs NOT described as confirmed false positives | ✓ |
| Plotted counts reconciled against source artifacts | ✓ |
| Deterministic sampling documented (seed=42) | ✓ |
| No upstream figures or scientific outputs overwritten | ✓ |
| Evans rule a ≥ 3 requirement explicitly disclosed | ✓ |
| Benchmark evaluation conditioned on a ≥ 2 stated | ✓ |
| Negative control censoring rate disclosed | ✓ |
| No causation claimed for contextual features | ✓ |

---

## 7. Unresolved Limitations

1. **Figure 3 boxplots from aggregate summaries:** Pair-level raw features were
   not stored in the output directory. Boxplots are constructed from pre-computed
   Q25/median/Q75 statistics, not from the raw distribution.  This is documented
   on the figure itself and in this report.

2. **Benchmark coverage:** 61.97% of OMOP negative controls and 46.0% of EU-ADR
   negative controls are unobserved in FAERS (a < 2).  AUC metrics are
   conditional on observability and should not be interpreted as sensitivity or
   specificity over the full reference standard.

3. **PRR χ² criterion:** The Evans rule requires χ² ≥ 4.0 in addition to
   PRR ≥ 2.0 and a ≥ 3.  The χ² criterion was applied in generating the
   discordance statistics; a small proportion of PRR discordance is due to this
   criterion rather than the PRR threshold alone.

---

## 8. Validation Script

`data/21_track1_publication_figures/validate_task_t1_03_figures.py`

Run: `python data/21_track1_publication_figures/validate_task_t1_03_figures.py`
