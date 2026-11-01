# Empirical Bayes Signal Detection in Spontaneous Pharmacovigilance Reports

**A Systematic Evaluation of the Multi-Item Gamma-Poisson Shrinker Against Independent Benchmark Standards with Contextual Characterisation of Drug–Adverse Drug Reaction Pairs**

> **Repository status:** Public research software release.
> This repository contains source code, validated reference standards, and pre-computed publication tables for reproducing the key results of the study.
> Raw FAERS archives (~14.7 GB) must be downloaded separately. See [Section 13](#13-data-access-instructions).

## Project Attribution

**Developed by: Adarsh Kumar Priyadarshi**

---

## Table of Contents

1. [Research Objectives and Scope](#1-research-objectives-and-scope)
2. [Data Sources and Historical Cohort Definition](#2-data-sources-and-historical-cohort-definition)
3. [MGPS / EB05 Methodology and Comparator Methods](#3-mgps--eb05-methodology-and-comparator-methods)
4. [Benchmark Evaluation](#4-benchmark-evaluation)
5. [Bootstrap Sensitivity Analyses](#5-bootstrap-sensitivity-analyses)
6. [Contextual Analysis](#6-contextual-analysis)
7. [Installation and Dependencies](#7-installation-and-dependencies)
8. [Step-by-Step Reproduction Instructions](#8-step-by-step-reproduction-instructions)
9. [Expected Outputs and Locations](#9-expected-outputs-and-locations)
10. [Repository Structure](#10-repository-structure)
11. [Known Limitations](#11-known-limitations)
12. [Citation and Reference](#12-citation-and-reference)
13. [Data Access Instructions](#13-data-access-instructions)
14. [License](#14-license)
15. [Ethics and Regulatory Declarations](#15-ethics-and-regulatory-declarations)

---

## 1. Research Objectives and Scope

This study evaluates the **Multi-Item Gamma-Poisson Shrinker (MGPS)** — specifically its lower credibility bound **EB05** — for pharmacovigilance signal detection in spontaneous adverse drug reaction (ADR) reports from the US FDA Adverse Event Reporting System (FAERS).

The research addresses four empirical questions:

1. Does empirical Bayes shrinkage translate into statistically verifiable discrimination gains over the frequentist Proportional Reporting Ratio (PRR) and Reporting Odds Ratio (ROR) when evaluated against independent external reference standards under identical observability constraints?
2. What is the exact composition of discordance between EB05 >= 2.0 and the Evans PRR rule across sparse reporting-count tiers?
3. How do patient demographics, reporting channels, and co-medication context vary across EB05 signal-strength strata?
4. Can surrogate machine-learning models emulate EB05 scores from contextual features, and what does this imply about score predictability?

> **Scope boundary:** This is an **unsupervised statistical disproportionality signal detection** study. No supervised ADR prediction model is claimed or developed. Surrogate Random Forest models are analytical tools for score emulation only; they do not predict true ADR occurrence or biological causality.

> **Historical Label Feasibility Investigation:** Two pre-modelling audit reports included in the repository (`modelling_readiness_and_historical_label_audit.md` and `pre_modelling_readiness_report.md`) document an earlier investigation into the feasibility of constructing dated positive labels from historical DailyMed Structured Product Labeling (SPL) XML archives. That audit established a formal "NO-GO" decision for supervised machine-learning model training due to the absence of reliable regulatory approval timestamps in retrospective SPL files. In accordance with research integrity standards, these reports are retained for methodological transparency, demonstrating why this study focuses strictly on unsupervised statistical disproportionality signal detection (MGPS/EB05) rather than supervised ADR prediction.

---

## 2. Data Sources and Historical Cohort Definition

### Primary Data: FDA FAERS ASCII Archives

> **FDA Disclaimer:** This analysis is an independent research effort. It was not conducted by or on behalf of the U.S. Food and Drug Administration and does not represent FDA views, findings, or endorsement.

- **Source:** US FDA Adverse Event Reporting System (FAERS) — https://www.fda.gov/drugs/questions-and-answers-fdas-adverse-event-reporting-system-faers/fda-adverse-event-reporting-system-faers-public-dashboard
- **Cohort span:** 20 quarterly archive packages, **2014 Q1 to 2018 Q4**
- **Physical archive boundary:** Strict temporal sequestration enforced to prevent retrospective look-ahead contamination
  - 6,012,891 cases with an initial FDA receipt date on or before 2018-12-31 across all archives ingested through 2023 Q1
  - 7,052 backfilled cases (first appearing in post-2018 Q4 archive packages) were quarantined
  - **Feature cohort: 6,005,839 unique safety cases** (6,012,891 minus 7,052)
  - An independent audit confirmed 25,718 retrospective FDA deletions, leaving 5,987,173 retrospectively corrected cases

FAERS raw archive files (**not included in this repository** — approximately 14.7 GB extracted) must be downloaded by the user. See Section 13.

### Reference Standards

Two independent external reference standards were used for benchmark evaluation:

| Reference Set       | Source                        | Matched Pairs (a>=2) | Positives | Negatives |
|:--------------------|:------------------------------|:--------------------:|:---------:|:---------:|
| OMOP Ground Truth   | OHDSI MethodEvaluation package| 203                  | 114       | 89        |
| EU-ADR Reference    | Coloma et al. 2013            | 66                   | 39        | 27        |

Files are stored in `data/05_reference_standards/`.

### SIDER Side-Effect Resource

- SIDER 4.1 was used for drug-normalisation audit purposes only (pipeline feasibility assessment)
- Provenance checksums are in `data/04_audit_sider/sider_source_checksums.json`
- SIDER 4.1 source files are **not included** in this release due to ambiguity in redistribution rights for MedDRA-linked content. They can be downloaded from https://sideeffects.embl.de/

---

## 3. MGPS / EB05 Methodology and Comparator Methods

### 3.1 Candidate Universe

Drug-ADR pairs were constructed from DRUG (suspect roles: Primary Suspect, Secondary Suspect) and REAC tables. Drug names were normalized to active ingredient concepts via string standardisation and salt stripping; adverse events were mapped to MedDRA Preferred Terms (PTs). The candidate universe was restricted to pairs with observed co-occurrence count **a >= 2**, yielding **1,167,891 unique candidate pairs**:

- 335,816 pairs at a = 2 (28.75%)
- 832,075 pairs at a >= 3 (71.25%)

### 3.2 Disproportionality Metrics

For each drug i and event j, the expected count under independence is:

```
E_ij = ((a + b)(a + c)) / N_total
```

where N_total = 6,005,839.

| Metric | Signal Rule |
|:-------|:------------|
| PRR    | Evans: a >= 3, PRR >= 2.0, chi-squared >= 4.0 |
| ROR    | Lower 95% Wald CI > 1 |
| EBGM   | `exp(E[ln λ \| n, E])` |
| EB05   | 5th percentile of posterior; EB05 >= 2.0 |

### 3.3 MGPS Model (Truncated Conditional Likelihood)

A two-component Gamma-Poisson mixture prior was fitted to all candidate pairs using a **conditional likelihood truncated at $a \ge 2$**, normalizing for left-truncation bias. The truncation normalization denominator uses the regularized incomplete beta function.

The prior distribution on the true relative reporting ratio $\lambda$ follows the classic DuMouchel (1999) two-component Poisson-Gamma mixture parameterized by shape ($\alpha$) and rate ($\beta$):
$$\pi(\lambda \mid \theta) = w \cdot \text{Gamma}(\alpha_1, \beta_1) + (1 - w) \cdot \text{Gamma}(\alpha_2, \beta_2)$$
where $\mathbb{E}[\lambda] = \alpha/\beta$ and $\text{Var}(\lambda) = \alpha/\beta^2$.

**Key implementation:** `src/signal_detection/ebgm_engine.py`

**Optimization:** Multi-start L-BFGS-B across seven diverse initial configurations passed by the production pipeline (`scripts/run_phase3c2_mgps_pipeline.py`), spanning pilot conditional regimes, openEBGM defaults, and balanced baselines (while `src/signal_detection/ebgm_engine.py` provides 5 default configurations for standalone library usage). Convergence to log-likelihood = -3,372,348.34 was replicated across restarts 1 and 5 ($\Delta\text{NLL} < 0.0001$).

**Fitted hyperparameters** (frozen; see `data/20_track1_publication_tables/table2_mgps_fit_sensitivity.csv` and `data/13_phase3c2_mgps_scoring/fit_checkpoint.json`):

| Parameter | Value | Standard Error | Meaning / Optimization Note |
|:---|:---:|:---:|:---|
| $\alpha_1$ (Component 1 Shape) | 0.001000 | $6.77 \times 10^{-5}$ | Boundary hit at lower optimization limit $[0.001, 10.0]$ |
| $\beta_1$ (Component 1 Rate) | 0.006809 | $4.35 \times 10^{-5}$ | Component 1 mean $\mu_1 = \alpha_1/\beta_1 = 0.1469$ (heavy shrinkage toward zero) |
| $\alpha_2$ (Component 2 Shape) | 0.285887 | $2.64 \times 10^{-3}$ | Well-conditioned interior solution |
| $\beta_2$ (Component 2 Rate) | 0.400371 | $2.12 \times 10^{-3}$ | Component 2 mean $\mu_2 = \alpha_2/\beta_2 = 0.7141$ |
| $w$ (Mixture Weight Component 1) | 0.849904 | $8.72 \times 10^{-3}$ | 84.99% prior mixture weight assigned to extreme-shrinkage component 1 |
| Log-Likelihood | -3,372,348.34 | N/A | Maximized conditional log-likelihood (converged in 103 iterations) |

> **Warning — $\alpha_1$ boundary contact:** $\alpha_1$ converged to its lower boundary ($0.001$). Sensitivity analysis across $\alpha_1 \ge \{0.0001, 0.001, 0.010, 0.050\}$ shows Spearman rank correlations $\rho > 0.999999$ with the primary fit, indicating negligible practical impact on signal rankings.

**2D logarithmic binning:** Pairs were compressed into 61,709 unique bins for scalable optimization. Pilot calibration (Phase 3c1; 100,000 reports, approximately 42,000 pairs) measured approximately 0.00013% relative log-likelihood error vs. exact unbinned summation. This bound applies to the pilot cohort and is not asserted as an exact full-dataset error guarantee.

---

## 4. Benchmark Evaluation

Discrimination was evaluated on evaluable subsets (a >= 2) for all four methods against both reference standards.

### Primary Results (Canonical Pair-Level Bootstrap, B=2000, seed 42)

| Reference Standard | Method | AP [95% CI]              | ROC-AUC [95% CI]         |
|:-------------------|:-------|:------------------------:|:------------------------:|
| OMOP (N=203)       | EB05   | 0.8626 [0.8092, 0.9103]  | 0.8136 [0.7536, 0.8681]  |
|                    | EBGM   | 0.8506 [0.7919, 0.9046]  | 0.8071 [0.7447, 0.8630]  |
|                    | PRR    | 0.8325 [0.7623, 0.8964]  | 0.7995 [0.7359, 0.8582]  |
|                    | ROR    | 0.8311 [0.7601, 0.8947]  | 0.7986 [0.7348, 0.8575]  |
| EU-ADR (N=66)      | EB05   | 0.9584 [0.9065, 0.9947]  | 0.9364 [0.8694, 0.9908]  |
|                    | EBGM   | 0.9493 [0.8914, 0.9894]  | 0.9240 [0.8518, 0.9824]  |
|                    | PRR    | 0.9371 [0.8741, 0.9828]  | 0.9060 [0.8238, 0.9722]  |
|                    | ROR    | 0.9384 [0.8773, 0.9830]  | 0.9069 [0.8254, 0.9722]  |

AP = Average Precision (sklearn `average_precision_score`). All paired 95% CIs for OMOP and EU-ADR span zero — differences are not statistically significant at alpha=0.05.

> **Metric Distinction:** Primary discrimination is evaluated as non-interpolated Average Precision (AP via `sklearn.metrics.average_precision_score`). Trapezoidal area under the precision-recall curve yields 0.8619 for OMOP EB05 and 0.9578 for EU-ADR EB05 (reported in `data/20_track1_publication_tables/table3_benchmark_performance.csv`). Both metrics rank methods identically: EB05 > EBGM > PRR / ROR.

Source: `data/33_task_t1_11_final_benchmark_audit/independently_recomputed_statistics.csv`

### Unobserved Negative Controls

- **62.0%** of OMOP negative controls have a < 2 in FAERS — excluded from evaluation
- **46.0%** of EU-ADR negative controls have a < 2 — excluded
- All benchmark statistics are **conditional on a >= 2**

---

## 5. Bootstrap Sensitivity Analyses

### Pair-Level Bootstrap (Primary Specification)
Paired percentile bootstrap resampling at the drug-event pair level (B = 2,000, seed 42, shared row indices across methods). All paired difference CIs span zero.

### Drug-Cluster Bootstrap Sensitivity
Resampling at the drug active-substance cluster level ($K = 126$ OMOP clusters, $K = 46$ EU-ADR clusters; $B = 2,000$):
- **OMOP:** All difference intervals continue to span zero.
- **EU-ADR (10 alternative seeds — Primary Robustness Finding):** Across 10 alternative random seeds (Seeds 0, 1, 7, 99, 123, 456, 999, 2024, 31337, 8675309), every single paired $\Delta\text{AP}$ confidence interval spans zero (lower bounds range from $-0.001906$ to $-0.000351$; upper bounds range from $+0.053792$ to $+0.058160$). Under drug-clustered resampling, the apparent discrimination advantage of EB05 over PRR is not statistically significant at the 5% level.
- **EU-ADR (canonical seed 42 — Secondary Sensitivity):** $\Delta\text{AP}$ (EB05 minus PRR) = $+0.021325$, 95% CI $[+0.000140, +0.055024]$; ROC-AUC CI spans zero. This nominal exclusion of zero is sensitive to random seed selection and is not replicated across the alternative seeds.
- **Outcome-cluster resampling:** Infeasible — only 4 OMOP and 10 EU-ADR outcome clusters; omitting the single Acute Liver Failure OMOP cluster drops positive control prevalence from 56.2% to 37.3%.

Source: `data/49_task_t1_27_manuscript_integration/supplementary_table_s1.csv`
Script: `scripts/run_phase3f_robustness.py`

---

## 6. Contextual Analysis

Eleven contextual features (demographic, reporting-channel, polypharmacy) were computed per candidate pair and stratified across five EB05 strata (<1.0, 1.0-2.0, 2.0-5.0, 5.0-10.0, >=10.0). Kruskal-Wallis omnibus tests with Benjamini-Hochberg FDR correction and epsilon-squared rank-based effect size were applied.

**Key findings:**
- All 11 features show statistically significant variation (all BH-FDR p < 0.05)
- Effect sizes are uniformly small-to-negligible (max epsilon-squared = 0.0273, secondary suspect ratio)
- Consumer reporting (`csm_reporter_ratio`) declines across strata (median 0.44 to 0.16)
- Healthcare professional reporting (`hp_reporter_ratio`: MD, PH, HP, RN; **excludes** lawyer code LW) remains stable to slightly increasing (mean 0.33 to 0.36; epsilon-squared = 0.0033)

> **Important:** `hp_reporter_ratio` captures MD, PH, HP, and RN reporter codes only. Lawyer (LW) cases were excluded per FDA CDER FAERS ASCII Data Dictionary — LW is an administrative/legal classification, not a clinical reporter type.

Source: `data/20_track1_publication_tables/table4_contextual_strata.csv`

---

## 7. Installation and Dependencies

### Requirements

- **Python 3.13** (standard runtime; see `requirements.txt` for pinned dependencies)

### Verified Packages

| Package     | Version | Role                                              |
|:------------|:--------|:--------------------------------------------------|
| numpy       | 2.5.3   | Array computation                                 |
| pandas      | 3.0.6   | Tabular data handling                             |
| scipy       | 1.18.1  | MGPS optimization, beta functions                 |
| scikit-learn| 1.9.1   | AP, ROC-AUC, Random Forest surrogates             |
| lightgbm    | 4.7.0   | Boosted surrogate models                          |
| matplotlib  | 3.11.2  | Figure generation                                 |
| shap        | 0.53.0  | SHAP feature attribution                          |
| requests    | 2.34.2  | FAERS archive download utilities                  |

> **Dependency specification:** `requirements.txt` pins the verified minimal direct dependencies used by the computational and statistical pipeline under Python 3.13. All benchmark standards are bundled as pre-converted CSV files read via `pandas`. `pyreadr` (GNU AGPL-3.0) is not required for running the pipeline and is documented as an optional developer dependency if re-extracting from raw `.rda` files.

### Setup

```bash
# Clone the repository
git clone https://github.com/priyadarshi-cloud/Faers-mgps-signal-detection-public.git
cd Faers-mgps-signal-detection-public

# Create and activate virtual environment
python -m venv .venv
# On Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
# On Windows (Command Prompt):
.venv\Scripts\activate.bat
# On Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

> **Note:** The pipeline was developed and validated on Windows 10 with Python 3.13. Automated CI validates core algorithmic and analytical modules on Ubuntu Linux with Python 3.13.

---

## 8. Step-by-Step Reproduction Instructions

> **Prerequisites:**
> - Python 3.13 virtual environment activated
> - FAERS ASCII data downloaded into `data/07_phase3a_continuous_ingestion/raw_zips/` (see Section 13)
> - Reference standard files present in `data/05_reference_standards/`

All scripts are run from the project root.

### Quick Validation (no FAERS data required)

```bash
# Run unit tests and offline mathematical/benchmark audits
python scripts/test_ebgm_engine.py
python scripts/test_phase3a2_snapshot.py
python scripts/test_version_safe_join.py
python scripts/test_temporal_snapshot.py
python scripts/audit_stress_test.py
python scripts/audit_phase3d_benchmarks.py
python scripts/independent_benchmark_audit_t1_11.py
```

### Full Pipeline Reproduction (requires FAERS download)

#### Phase 1: Data Ingestion and Snapshot Construction

```bash
python scripts/download_continuous_faers.py
python scripts/ingest_and_validate_continuous_faers.py
python scripts/build_phase3a2_snapshot.py
# Output: data/08_phase3a2_snapshot/canonical_snapshot.csv

python scripts/build_phase3a4_dual_snapshots.py
# Output: data/09_phase3a4_dual_snapshots/
```

#### Phase 2: Feature Extraction

```bash
python scripts/build_phase3b_features.py
# Output: data/10_phase3b_features/
```

#### Phase 3: MGPS Scoring

```bash
python scripts/run_phase3c2_mgps_pipeline.py
# Output: data/13_phase3c2_mgps_scoring/phase3c2_scored_candidate_pairs.csv
```

#### Phase 4: Benchmark Evaluation

```bash
python scripts/run_phase3d_benchmark_evaluation.py
python scripts/audit_phase3d_benchmarks.py
# Output: data/14_phase3d_benchmark_evaluation/
```

#### Phase 5: Robustness and Sensitivity

```bash
python scripts/run_phase3f_robustness.py
# Output: data/16_phase3f_robustness/
```

#### Phase 6: Publication Outputs

```bash
python scripts/generate_task_t1_02_publication_tables.py
python scripts/generate_task_t1_03_figures.py
python scripts/validate_task_t1_02_publication_tables.py
```

---

## 9. Expected Outputs and Locations

| Output | Location | Description |
|:-------|:---------|:------------|
| Canonical snapshot | `data/08_phase3a2_snapshot/canonical_snapshot.csv` | 6,005,839-case archive-bounded cohort [Not in repo; reproducible from FAERS or from Zenodo/Dryad deposit — see Section 13] |
| Retrospectively corrected | `data/09_phase3a4_dual_snapshots/retrospectively_corrected_snapshot.csv` | Post-deletion cohort [Not in repo] |
| Scored candidate pairs | `data/13_phase3c2_mgps_scoring/phase3c2_scored_candidate_pairs.csv` | 1,167,891 pairs with EBGM, EB05, EB95, PRR, ROR [Not in repo — see Section 13] |
| Table 1 (study population) | `data/20_track1_publication_tables/table1_study_population.csv` | Cohort flow |
| Table 2 (MGPS fit) | `data/20_track1_publication_tables/table2_mgps_fit_sensitivity.csv` | Hyperparameters + boundary sensitivity |
| Table 3 (benchmark) | `data/20_track1_publication_tables/table3_benchmark_performance.csv` | AP, ROC-AUC, paired delta-CIs |
| Table 4 (contextual strata) | `data/20_track1_publication_tables/table4_contextual_strata.csv` | KW, epsilon-squared, medians by stratum |
| Supplementary Table S1 | `data/49_task_t1_27_manuscript_integration/supplementary_table_s1.csv` | Cluster-bootstrap sensitivity |
| Figure 1 | `data/21_track1_publication_figures/figure1_eb_shrinkage.{png,pdf}` | PRR vs EB05 discordance scatter |
| Figure 2 | `data/21_track1_publication_figures/figure2_benchmark_curves.{png,pdf}` | PR and ROC curves |
| Figure 3 | `data/25_track1_revised_manuscript/figure3_contextual_features_revised.{png,pdf}` | Feature distributions by stratum |
| Independently recomputed stats | `data/33_task_t1_11_final_benchmark_audit/independently_recomputed_statistics.csv` | Ground-truth benchmark values |

---

## 10. Repository Structure

```
faers-mgps-signal-detection/
├── src/
│   ├── signal_detection/
│   │   ├── ebgm_engine.py          # MGPS Gamma-Poisson engine (main algorithm)
│   │   └── disproportionality.py   # PRR / ROR computation
│   ├── preprocessing/
│   │   ├── historical_snapshot.py  # Archive-bounded cohort construction
│   │   ├── case_deduplication.py   # FAERS case versioning and deduplication
│   │   ├── drug_normalizer.py      # Ingredient normalization and salt stripping
│   │   ├── deleted_cases.py        # FDA retrospective deletion list handling
│   │   └── reaction_normalizer.py  # MedDRA PT mapping
│   ├── pipeline/
│   │   ├── pair_builder.py         # Drug-ADR pair construction
│   │   └── pipeline_orchestrator.py
│   ├── features/
│   │   └── feature_extractor.py    # Contextual feature computation
│   ├── data_acquisition/
│   │   └── faers_loader.py         # FAERS ASCII file parsing
│   └── reference_standards/
│       ├── omop_loader.py          # OMOP reference set loading
│       └── evidence_classifier.py  # Positive/negative control classification
├── scripts/                        # Executable pipeline and test scripts
│   ├── build_phase3a2_snapshot.py
│   ├── build_phase3b_features.py
│   ├── run_phase3c2_mgps_pipeline.py
│   ├── run_phase3d_benchmark_evaluation.py
│   ├── run_phase3f_robustness.py
│   ├── test_ebgm_engine.py         # Unit tests for MGPS engine (run without FAERS data)
│   └── test_phase3a2_snapshot.py   # Unit tests for snapshot logic
├── data/
│   ├── 04_audit_sider/             # SIDER provenance checksums (source files not included)
│   ├── 05_reference_standards/     # OMOP and EU-ADR benchmark files [INCLUDED]
│   ├── 07_phase3a_continuous_ingestion/  # Ingestion manifests [raw zips EXCLUDED - 14.7 GB]
│   ├── 08_phase3a2_snapshot/       # Cohort manifests [CSV EXCLUDED - 544 MB]
│   ├── 09_phase3a4_dual_snapshots/ # Dual snapshot manifests [CSV EXCLUDED - 546 MB]
│   ├── 10_phase3b_features/        # Feature manifests [CSV EXCLUDED - 1.5 GB]
│   ├── 12_phase3c_pilot/           # Pilot technical reports
│   ├── 13_phase3c2_mgps_scoring/   # Fit checkpoint and metrics JSON [scored CSV EXCLUDED - 346 MB]
│   ├── 14_phase3d_benchmark_evaluation/  # Benchmark evaluation results
│   ├── 15_phase3e_explainable_ai/  # XAI results
│   ├── 16_phase3f_robustness/      # Robustness analyses
│   ├── 20_track1_publication_tables/   # Final publication tables (CSV) [INCLUDED]
│   ├── 21_track1_publication_figures/  # Final publication figures (PNG/PDF) [INCLUDED]
│   ├── 25_track1_revised_manuscript/   # Figure 3 and revised tables [INCLUDED]
│   ├── 33_task_t1_11_final_benchmark_audit/  # Independently recomputed statistics [INCLUDED]
│   ├── 34_task_t1_12_final_scientific_corrections/  # Scientific corrections [INCLUDED]
│   └── 49_task_t1_27_manuscript_integration/  # Supplementary Table S1 [INCLUDED]
├── requirements.txt                # Pinned runtime dependencies (Python 3.13)
├── pyproject.toml                  # PEP 621 metadata, Python version requirement, dependencies, & Pyrefly config
├── research_architecture_blueprint.md
├── LICENSE                         # Apache License 2.0
├── DATA_NOTICES.md                 # Third-party data notices & citations
└── README.md
```

---

## 11. Known Limitations

The following limitations are disclosed in the manuscript (Section 5.2):

1. **Conditional evaluation at a >= 2:** All benchmark statistics are conditioned on pair observability. 62.0% of OMOP and 46.0% of EU-ADR negative controls are excluded.
2. **Benchmark cluster dependence:** Pair-level bootstrap does not model intra-cluster correlation. Drug-cluster sensitivity on EU-ADR shows the canonical seed-42 delta-AP lower bound (+0.000140) collapses to zero across 10 alternative seeds.
3. **Outcome-cluster resampling infeasible:** Only K=4 OMOP and K=10 EU-ADR outcome clusters exist; omitting Acute Liver Failure shifts OMOP positive-control prevalence from 56.2% to 37.3%.
4. **alpha_1 boundary contact:** Fitted alpha_1 = 0.0010 contacts the lower optimization boundary (rho > 0.999999 sensitivity; negligible rank-order impact).
5. **2D binning approximation:** Pilot-calibration error bound (~0.00013%) is specific to the Phase 3c1 cohort and is not guaranteed to generalize to the full dataset.
6. **Surrogate validation limitations:** Surrogate Random Forest models emulate EB05 scores (R-squared = 0.9991 for M2 multimodal) but **true ADR identification by contextual features was not evaluated**. Surrogate models must not be interpreted as ADR classifiers.
7. **Single-database scope:** Results restricted to US FAERS; may not generalize to EudraVigilance or VigiBase.
8. **Observational reporting biases:** Conditional likelihood truncation does not eliminate notoriety bias, channeling, the Weber effect, or indication confounding.
9. **Ingredient-level normalization:** Dosage, formulation, route, and indication are not modeled.
10. **No causal proof:** Disproportionality signals do not establish biological causality or clinical incidence rates.
11. **Environment:** Pipeline developed and validated on Windows 10 with Python 3.13. Automated CI validates core algorithmic and analytical modules on Ubuntu Linux with Python 3.13.

---

## 12. Citation and Reference

If you use this software or its methodology, please cite this repository:

```text
Priyadarshi, A. K. (2026). FAERS-MGPS: Empirical Bayes Signal Detection in Spontaneous Pharmacovigilance Reports.
GitHub repository: https://github.com/priyadarshi-cloud/Faers-mgps-signal-detection-public
```

*A formal journal citation and article DOI will be added here if the associated research is published.*

### Key Methodological References

1. DuMouchel W. Bayesian data mining in large frequency tables, with an application to the FDA spontaneous reporting system. *The American Statistician*. 1999;53(3):177-190.
2. Evans SJW, Waller PC, Davis S. Use of proportional reporting ratios (PRRs) for signal generation from spontaneous adverse drug reaction reports. *Pharmacoepidemiology and Drug Safety*. 2001;10(6):483-486.
3. Ryan PB, Schuemie MJ, Welebob E, Duke J, Valentine S, Hartzema AG. Defining a reference set to support methodological research in drug safety. *Drug Safety*. 2013;36(Suppl 1):S33-S47. DOI: [10.1007/s40264-013-0097-8](https://doi.org/10.1007/s40264-013-0097-8).
4. Coloma PM, Avillach P, Salvo F, Schuemie MJ, Ferrajolo C, Pariente A, et al. A reference standard for evaluation of methods for drug safety signal detection using electronic healthcare record databases. *Drug Safety*. 2013;36(1):13-23. DOI: [10.1007/s40264-012-0002-x](https://doi.org/10.1007/s40264-012-0002-x).
5. Benjamini Y, Hochberg Y. Controlling the false discovery rate. *JRSS-B*. 1995;57(1):289-300.

---

## 13. Data Access Instructions

### FDA FAERS ASCII Archives

Publicly available. Use the provided download script:

```bash
python scripts/download_continuous_faers.py
```

Archives are downloaded from `https://fis.fda.gov/content/Exports/faers_ascii_<YEAR>q<Q>.zip` into `data/07_phase3a_continuous_ingestion/raw_zips/`. The study requires 2014 Q1 to 2018 Q4 (20 quarters, approximately 2.1 GB compressed, approximately 12.5 GB extracted). Raw archives and extracted ASCII files are excluded from this repository via `.gitignore`.

### OMOP and EU-ADR Reference Standards

- OMOP: https://github.com/OHDSI/MethodEvaluation
- EU-ADR: Coloma et al. 2013, Drug Safety 36(1):13-23

Files in `data/05_reference_standards/` are included in this repository (no patient-level information).

### Primary Derived Datasets

Pre-computed primary evaluation tables and sensitivity outputs are bundled directly in this repository for local verification:

| Dataset | Location | Description |
|:--------|:---------|:------------|
| Publication Tables 1-4 | `data/20_track1_publication_tables/` | Final manuscript tables (CSV) |
| Independently recomputed statistics | `data/33_task_t1_11_final_benchmark_audit/independently_recomputed_statistics.csv` | Audit-verified benchmark values |
| Supplementary Table S1 | `data/49_task_t1_27_manuscript_integration/supplementary_table_s1.csv` | Cluster-bootstrap sensitivity |
| MGPS fit checkpoint | `data/13_phase3c2_mgps_scoring/fit_checkpoint.json` | Frozen hyperparameters |

---

## 14. License

This project's software code is licensed under the **Apache License, Version 2.0** (the "License"). See the [`LICENSE`](LICENSE) file for the full text of the license.

```text
Copyright 2026 Adarsh Kumar Priyadarshi

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
```

### Third-Party Data Licensing

The Apache License 2.0 applies to the project software code in `src/` and `scripts/`. Bundled reference standards and public datasets in `data/` are governed by their respective upstream licenses, public-domain determinations, and citations:

- **OMOP Reference Standard:** Distributed under the Apache License 2.0 by OHDSI (Ryan et al. 2013).
- **EU-ADR Reference Standard:** Standardized into OMOP concepts and distributed under the Apache License 2.0 by OHDSI MethodEvaluation (Coloma et al. 2013).
- **FAERS Public Data:** Spontaneous adverse event report compilations publicly distributed by the U.S. FDA without copyright restriction. See [FDA Disclaimer](#2-data-sources-and-historical-cohort-definition) and [`DATA_NOTICES.md`](DATA_NOTICES.md) for details.

For comprehensive details on dataset provenance, cryptographic hashes, transformation methodologies, and bibliographic citations, see [`DATA_NOTICES.md`](DATA_NOTICES.md).

---

## 15. Ethics and Regulatory Declarations

- **Data Governance and Institutional Independence:** This research was independently conducted by two Master's students as a collaborative academic research project intended for publication. The institution with which the author making this declaration is affiliated had no role in the design, development, funding, supervision, conduct, or oversight of this project. The study used publicly available structured data from the U.S. FDA Adverse Event Reporting System (FAERS) quarterly releases and publicly available external reference standards from OHDSI. No non-public patient records were obtained for this analysis. No institutional IRB approval, exemption, or non-human-subjects research determination is claimed in this repository.
- **Regulatory Disclaimer:** This analysis is an independent academic research effort. It was not conducted by or on behalf of the U.S. Food and Drug Administration and does not represent FDA views, findings, or endorsement.

---

*Code and validation suite developed October 2026.*
