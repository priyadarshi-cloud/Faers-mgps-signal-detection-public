# Phase 3C.1 — Controlled EBGM/MGPS Implementation & Technical Validation Report

**Project:** Explainable AI Approaches for Adverse Drug Reaction Signal Detection in Pharmacovigilance using FAERS  
**Phase:** Phase 3C.1 (Empirical Bayes Signal Prioritization Engine & Controlled Pilot)  
**Document Target:** `data/12_phase3c_pilot/phase3c1_technical_report.md`  
**Date:** October 11, 2026  
**Auditor / Modeller:** Research Pipeline Technical Audit  
**Status:** **PILOT COMPLETED & SCIENTIFICALLY VALIDATED — HOLDING FULL-SCALE COMPUTATION**  

---

## 1. Executive Summary

Phase 3C.1 successfully implemented and scientifically validated the **Multi-item Gamma Poisson Shrinker (MGPS)** and **Empirical Bayes Geometric Mean (EBGM)** signal prioritization framework within the FAERS AI Model workspace.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                 PHASE 3C.1 SCIENTIFIC VALIDATION SUMMARY                     │
│                                                                             │
│  1. Software & Environment: SciPy 1.18.1 installed and verified in .venv.  │
│     Requirements and import paths validated with 0 regression errors.        │
│                                                                             │
│  2. Mathematical Engine: Implemented in src/signal_detection/ebgm_engine.py │
│     Strictly parameterized via Gamma SHAPE-RATE convention. Numerically     │
│     stabilized marginal mixture likelihood using logsumexp.                  │
│                                                                             │
│  3. Automated Validation Suite: 8/8 automated scientific tests PASSED,      │
│     including exact reproduction of peer-reviewed test vectors from         │
│     Canida & Ihrie (2017, The R Journal 9(2):499-519) within 0.01 tolerance.│
│                                                                             │
│  4. Controlled Pilot (M = 25,000 pairs): Deterministic, label-blind run     │
│     completed in 57.3s. 0 NaNs, 0 numerical failures. Converged in 47 iters.│
│                                                                             │
│  5. Empirical Shrinkage Finding: In sparse pairs (a in [2, 5]), EB05        │
│     achieved a 57.94% reduction in sparse-cell threshold-flagged            │
│     disproportionality alarms under the evaluated screening rule.           │
│                                                                             │
│  6. STOP CONDITION ENFORCED: Scaled 1.16M execution held for authorization. │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Mathematical Specification & Parameterization

### 2.1 The Contingency Foundation & Independence Null
For drug $d$ and adverse reaction $e$, the 2x2 contingency table is defined over the strict historical cohort ($N = 6,005,839$ unique cases, $\le 2018Q4$):
- $a$: Observed co-occurrence count ($N_{ij}$)
- $b$: Total cases with drug $d$ minus $a$
- $c$: Total cases with event $e$ minus $a$
- $d$: Total cases with neither drug $d$ nor event $e$

Under the null hypothesis of independence between drug exposure and adverse event reporting:
$$E_{ij} = \frac{(a_{ij} + b_{ij})(a_{ij} + c_{ij})}{N}$$

### 2.2 Likelihood Model & Two-Component Gamma Mixture Prior
The observed count $N_{ij}$ is assumed to follow a Poisson distribution:
$$N_{ij} \sim \text{Poisson}(\mu_{ij}), \quad \mu_{ij} = \lambda_{ij} E_{ij}$$
where $\lambda_{ij}$ is the latent true relative reporting ratio.

Following DuMouchel (1999), $\lambda_{ij}$ arises from a two-component mixture of Gamma distributions:
$$\pi(\lambda \mid \theta) = w \cdot f_{\text{Gamma}}(\lambda; \alpha_1, \beta_1) + (1 - w) \cdot f_{\text{Gamma}}(\lambda; \alpha_2, \beta_2)$$
with hyperparameter vector $\theta = (\alpha_1, \beta_1, \alpha_2, \beta_2, w)$.

#### Explicit Parameterization Convention: **SHAPE-RATE**
The Gamma probability density function is parameterized by shape $\alpha > 0$ and rate $\beta > 0$ (inverse scale, $\text{scale} = 1/\beta$):
$$f_{\text{Gamma}}(\lambda; \alpha, \beta) = \frac{\beta^\alpha}{\Gamma(\alpha)} \lambda^{\alpha - 1} e^{-\beta \lambda}, \quad \lambda > 0$$
- Expectation: $E[\lambda] = \alpha / \beta$
- Variance: $\text{Var}(\lambda) = \alpha / \beta^2$
- In `scipy.stats.gamma`, parameter mapping is `a = alpha, scale = 1.0 / beta`.
- **Identifiability Convention:** The model enforces $\frac{\alpha_1}{\beta_1} \le \frac{\alpha_2}{\beta_2}$ via canonicalization ($w \to 1 - w$ and permutation if $\text{Mean}_1 > \text{Mean}_2$).

### 2.3 Marginal Negative Binomial Mixture Likelihood
Integrating out $\lambda_{ij}$ yields the marginal distribution of $N_{ij}$ given $E_{ij}$:
$$P(N_{ij} = n \mid E_{ij}, \theta) = w \cdot \text{NB}\left(n; \alpha_1, \frac{\beta_1}{\beta_1 + E_{ij}}\right) + (1 - w) \cdot \text{NB}\left(n; \alpha_2, \frac{\beta_2}{\beta_2 + E_{ij}}\right)$$
where:
$$\text{NB}(n; \alpha, p) = \frac{\Gamma(n + \alpha)}{n! \Gamma(\alpha)} p^\alpha (1 - p)^n, \quad p = \frac{\beta}{\beta + E_{ij}}$$

#### Numerical Stability in Log-Space:
$$\ln \text{NB}(n; \alpha, p) = \ln \Gamma(n + \alpha) - \ln \Gamma(\alpha) - \ln \Gamma(n + 1) + \alpha \ln(p) + n \ln(1 - p)$$
When $n = 0$, $n \ln(1 - p) = 0$ analytically.
The mixture log-likelihood is aggregated across pairs $k$ using `scipy.special.logsumexp`:
$$\ln P(n_k \mid E_k, \theta) = \text{logsumexp}\left( \left[ \ln(w) + \ln \text{NB}_1, \; \ln(1 - w) + \ln \text{NB}_2 \right] \right)$$

### 2.4 Posterior Distribution & Summary Metrics
Given maximum likelihood estimates $\hat{\theta}$, the posterior distribution for each pair $(i, j)$ is:
$$\lambda_{ij} \mid (N_{ij} = n, E_{ij} = E) \sim w_{ij}^* \cdot \text{Gamma}(\alpha_1 + n, \beta_1 + E) + (1 - w_{ij}^*) \cdot \text{Gamma}(\alpha_2 + n, \beta_2 + E)$$
where the posterior weight $w_{ij}^*$ (or $Q_{n, ij}$) is:
$$w_{ij}^* = \frac{w \cdot \text{NB}(n; \hat{\alpha}_1, \hat{\beta}_1 / (\hat{\beta}_1 + E))}{P(n \mid E, \hat{\theta})} = \exp\left( \ln(w) + \ln \text{NB}_1 - \ln P(n \mid E, \hat{\theta}) \right) \in [0, 1]$$

#### 1. Empirical Bayes Geometric Mean (EBGM):
The geometric mean of the posterior distribution is given in **exact closed form**:
$$\text{EBGM}_{ij} = \exp\left( E[\ln \lambda_{ij} \mid n, E] \right) = \exp\left( w_{ij}^* [\psi(\hat{\alpha}_1 + n) - \ln(\hat{\beta}_1 + E)] + (1 - w_{ij}^*) [\psi(\hat{\alpha}_2 + n) - \ln(\hat{\beta}_2 + E)] \right)$$
where $\psi(\cdot)$ is the digamma function (`scipy.special.digamma`).

#### 2. Posterior Quantiles (EB05 and EB95):
Defined by inverting the mixture cumulative distribution function:
$$F_{\text{post}}(q \mid n, E) = w_{ij}^* F_{\text{Gamma}}(q; \hat{\alpha}_1 + n, \hat{\beta}_1 + E) + (1 - w_{ij}^*) F_{\text{Gamma}}(q; \hat{\alpha}_2 + n, \hat{\beta}_2 + E)$$
- **EB05:** The value $q_{0.05}$ solving $F_{\text{post}}(q_{0.05}) = 0.05$ (5th percentile lower credibility bound).
- **EB95:** The value $q_{0.95}$ solving $F_{\text{post}}(q_{0.95}) = 0.95$ (95th percentile upper credibility bound).
- **Bracketing Guarantee:** Solved via Brent root-finding (`scipy.optimize.brentq`). For any probability $p$, $q_p \in [\min(q_{p, 1}, q_{p, 2}), \max(q_{p, 1}, q_{p, 2})]$ where $q_{p, k}$ is the exact single-component quantile from `scipy.stats.gamma.ppf`.
- **Monotonicity Guarantee:** $0 < \text{EB05} \le \text{EBGM} \le \text{EB95}$.

---

## 3. Epistemological Safeguard: Signal Prioritization vs Causal Inference

A strict methodological invariant is maintained throughout this research:

| Dimension | Pharmacovigilance Signal Prioritization (EBGM/EB05) | Epidemiological Causal Inference |
| :--- | :--- | :--- |
| **Statistical Objective** | Screen, shrink, and prioritize 1.16M hypotheses in voluntary reporting. | Establish whether drug administration caused the adverse clinical outcome. |
| **Denominator Nature** | No healthy control denominator; only spontaneous reported events. | Longitudinal patient cohorts with verified unexposed comparator groups. |
| **Metric Meaning** | Relative reporting disproportionality compared to background. | Causal Relative Risk / Hazard Ratio adjusted for confounders. |
| **Language Invariant** | *"Signal of disproportionate reporting for regulatory review."* | *"Drug causes adverse reaction."* (PROHIBITED IN THIS STAGE) |

EBGM and EB05 values are **not** probabilities of causality. Concordance with PRR or ROR indicates mathematical alignment between disproportionality formulas, **not** clinical validity.

---

## 4. Scientific Verification & Reference Test Vectors

The automated test suite in [`scripts/test_ebgm_engine.py`](<project-root>/scripts/test_ebgm_engine.py) verified 8 core statistical criteria:

```
================================================================================
PHASE 3C.1 — EMPIRICAL BAYES (EBGM/MGPS) SCIENTIFIC VALIDATION SUITE
================================================================================
  ✅ PASS  1. Hand-Calculated Expected Counts
  ✅ PASS  2. Zero and Sparse Counts Handling
  ✅ PASS  3. Numerical Stability for Extreme Count Ratios
  ✅ PASS  4. Valid Posterior Distribution and Quantile Ordering (EB05 <= EBGM <= EB95)
  ✅ PASS  5. Mixture-Weight and Hyperparameter Identifiability Constraints
  ✅ PASS  6. Optimizer Multi-Start Convergence and Failure Handling
  ✅ PASS  7. Deterministic Reproducibility Across Engine Restarts
  ✅ PASS  8. Published Reference Vectors (Canida & Ihrie 2017) & Analytic Boundaries
================================================================================
Summary: 8/8 tests PASSED.
```

### Verification Against Published Literature (Canida & Ihrie 2017)
The implementation was verified against the published CAERS benchmark in *The R Journal* (2017; 9(2): 499–519, Section 5.2):
- Hyperparameters: $\hat{\theta} = (\alpha_1=3.251187, \beta_1=0.399767, \alpha_2=2.026961, \beta_2=1.908933, w=0.065396)$

| Test Case | Observed $N$ | Expected $E$ | Published EBGM | Calculated EBGM | Published EB05 | Calculated EB05 | Published EB95 | Calculated EB95 | Test Status |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Pair 1** | 1 | 0.036055 | **2.23** | **2.2266** | **0.49** | **0.4911** | **13.85** | **13.8539** | **PASS** |
| **Pair 2** | 1 | 0.003874 | **2.58** | **2.5830** | **0.52** | **0.5181** | **15.78** | **15.7836** | **PASS** |
| **Pair 3** | 1 | 0.000298 | **2.63** | **2.6312** | **0.52** | **0.5215** | **16.02** | **16.0155** | **PASS** |

The Python engine reproduces the published R results down to the last printed decimal.

---

## 5. Controlled Small-Scale Pilot Results ($M = 25,000$ Pairs)

### 5.1 Pilot Sampling & Cohort Provenance
- **Universe Source:** [`data/10_phase3b_features/candidate_pairs_summary.csv`](<project-root>/data/10_phase3b_features/candidate_pairs_summary.csv) (SHA-256: `1ba9e48...`, $N_{\text{pairs}} = 1,167,891$).
- **Sample Selection:** Deterministic stratified sampling by count tier ($a=2, a=3, a \in [4, 5], a \in [6, 10], a > 10$) with `seed = 42`.
- **Label Blinding:** Zero OMOP or EU-ADR benchmark tables were accessed, merged, or used for sampling or tuning.
- **Universe Count ($N$):** Exactly $6,005,839$ canonical reports.

### 5.2 Hyperparameter Estimation & Convergence Diagnostics
Optimization was performed using multi-start L-BFGS-B (5 diverse starting vectors spanning the prior parameter space).

| Parameter | Unbinned Exact Estimate | Standard Error | 2D-Binned Estimate (decimals=2) | Deviation |
| :--- | :---: | :---: | :---: | :---: |
| $\alpha_1$ (Shape 1) | **1.1367** | $\pm 0.0176$ | 1.1483 | +1.02% |
| $\beta_1$ (Rate 1) | **0.4727** | $\pm 0.0136$ | 0.4848 | +2.56% |
| $\alpha_2$ (Shape 2) | **0.4747** | $\pm 0.0108$ | 0.4850 | +2.17% |
| $\beta_2$ (Rate 2) | **0.0055** | $\pm 0.0002$ | 0.0060 | +9.09% |
| $w$ (Weight 1) | **0.7584** | $\pm 0.0056$ | 0.7538 | -0.61% |
| **Log-Likelihood** | **-96,207.02** | — | -95,814.03 | — |
| **Iterations** | **47** | — | 45 | — |
| **Runtime** | **13.56 s** | — | **6.82 s** | 2.0x speedup |

- **Component 1 (Candidate Universe Baseline):** Prior mean $\alpha_1 / \beta_1 = 2.4048$, capturing 75.8% of candidate pairs. Because the candidate universe excludes unobserved ($a=0$) and singleton ($a=1$) pairs, the median crude ratio is 2.21, and 69.4% of candidate pairs have $a/E > 1.0$. Thus, this fitted prior reflects the conditional candidate universe $\pi(\lambda \mid a \ge 2)$ rather than a globally representative null distribution over the entire untruncated drug–event universe.
- **Component 2 (Elevated Signal Tail):** Prior mean $\alpha_2 / \beta_2 = 85.75$, capturing 24.2% of pairs with heavily elevated reporting ratios.
- **Convergence Status:** Confirmed (`CONVERGENCE: RELATIVE REDUCTION OF F <= FACTR*EPSMCH`).

### 5.3 Numerical Integrity
- Pairs Evaluated: **25,000**
- Successfully Scored: **25,000 (100.0%)**
- Excluded Rows / Failures: **0 (0.0%)**
- NaN Counts (`ebgm`, `eb05`, `eb95`): **Exactly 0**
- Quantile Monotonicity Violation ($0 < \text{EB05} \le \text{EBGM} \le \text{EB95}$): **0 violations across all 25,000 rows**

---

## 6. Descriptive Comparison: EBGM/EB05 vs PRR vs ROR

### 6.1 Sparse-Cell False Alarm Attenuation (Observed $a \in [2, 5]$)
Spontaneous reporting databases are heavily dominated by small cell counts ($a=2$ and $a=3$ constitute nearly 50% of all pairs). In small cells, frequentist metrics suffer extreme variance and divide-by-zero artifacts:

| Count Stratum | Pair Count | PRR Max | $\text{ROR}_{025}$ Max | EBGM Max | EB05 Max | % $\text{PRR} \ge 2.0$ | % $\text{ROR}_{025} > 1.0$ | % $\text{EB05} \ge 2.0$ |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| $a = 2$ | 7,189 | **285,992.0** | **67,316.3** | 357.6 | 99.8 | **58.12%** | 43.04% | **19.35%** |
| $a = 3$ | 3,643 | **62,560.8** | **14,340.9** | 535.0 | 191.5 | **54.93%** | 45.10% | **25.01%** |
| $a \in [4, 5]$ | 3,894 | **44,079.5** | **24,435.6** | 797.5 | 363.5 | **53.42%** | 47.66% | **30.10%** |
| $a \in [6, 10]$| 4,024 | 640,620.2 | 230,117.8 | 1,673.4 | 968.7 | 54.60% | 54.15% | 37.72% |
| $a > 10$ | 6,250 | 196,553.7 | 410,796.7 | 6,509.9 | 5,472.6 | 51.94% | 61.79% | 42.45% |

#### Key Statistical Observation:
- At $a = 2$, PRR produces an astronomical maximum of **285,992.0** and flags **58.12%** of all 2-case pairs as putative signals ($\text{PRR} \ge 2.0$).
- EB05 shrinks small-cell estimates back toward the prior mean, reducing the flag rate to **19.35%**.
- Across all sparse pairs ($a \in [2, 5]$, $N = 14,726$), PRR flags 8,259 pairs, whereas EB05 conservative flags only 3,474 pairs — a **57.94% reduction in sparse-cell threshold-flagged disproportionality alarms under the evaluated screening rule**.
- **Crucial Scientific Clarification:** No clinical ground-truth labels (such as OMOP or EU-ADR reference sets) were used in this evaluation. Consequently, this difference reflects Bayesian shrinkage of high-variance small-cell estimates toward the empirical prior, and must NOT be interpreted as a measured reduction in false positives or empirical proof of superior clinical validity.
- The mean absolute rank delta between PRR and EB05 among sparse pairs is **1,503 ranks** (with a maximum shift of **24,555 ranks**).

### 6.2 Global Rank Correlations (Spearman $\rho$ and Kendall $\tau$)

| Metric 1 | Metric 2 | Spearman $\rho$ | Kendall $\tau$ (Subsample) | Statistical Relationship |
| :--- | :--- | :---: | :---: | :--- |
| **EB05** | **ROR Lower 95% ($\text{ROR}_{025}$)** | **0.9744** | **0.9280** | Extremely high rank concordance; both represent conservative lower bounds. |
| **EBGM** | **PRR Point Estimate** | **0.9937** | **0.9610** | Almost perfect rank monotonicity between point estimators. |
| **EB05** | **EBGM Point Estimate** | **0.9684** | **0.8494** | High concordance, with EB05 down-weighting low-count pairs. |
| **EB05** | **PRR Point Estimate** | **0.9512** | **0.8222** | Divergence concentrated entirely in the sparse-count regime. |

### 6.3 Top-$K$ Concordance & Jaccard Overlap

| Screening Depth | Jaccard Overlap (EB05 vs PRR) | Shared Pairs (EB05 $\cap$ PRR) | Jaccard Overlap (EB05 vs $\text{ROR}_{025}$) | Shared Pairs (EB05 $\cap$ $\text{ROR}_{025}$) | Jaccard Overlap (EB05 vs EBGM) | Shared Pairs (EB05 $\cap$ EBGM) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Top 100** | **0.2579** | **41 shared (union: 159)** | **0.3889** | 56 shared (union: 144) | **0.7544** | 86 shared (union: 114) |
| **Top 1,000** | **0.6327** | **775 / 1,000** | **0.8018** | **890 / 1,000** | **0.7241** | **840 / 1,000** |
| **Top 5,000** | **0.6281** | **3,858 / 5,000** | **0.7737** | **4,362 / 5,000** | **0.7400** | **4,253 / 5,000** |
| **Top 10,000**| **0.7565** | **8,614 / 10,000** | **0.8965** | **9,454 / 10,000** | **0.8129** | **8,968 / 10,000** |

#### Top-100 Overlap Disambiguation & Jaccard Calculation:
- **Shared Pairs:** Exactly 41 pairs appear in both the EB05 Top-100 and PRR Top-100 ranking lists.
- **Union Size:** $|A \cup B| = 100 + 100 - 41 = 159$ unique pairs across both lists.
- **Jaccard Index:** $J(A, B) = \frac{|A \cap B|}{|A \cup B|} = \frac{41}{159} = 0.25786 \approx 0.2579$.
- **Statistical Interpretation:** The low Jaccard overlap (25.8%) arises because PRR's top ranks are heavily populated by sparse-count pairs ($a=2, 3$) with tiny expected values ($E \approx 10^{-5}$), generating unstable point ratios ($> 100,000$). EB05 penalizes this sampling variance, pulling these pairs down and placing high-volume, well-supported associations into the top 100.

### 6.4 Signal Flag Concordance Matrix

| Signal Rule | Formula | Flagged Pairs ($M=25,000$) |
| :--- | :--- | :---: |
| **Evans PRR Criteria** | $a \ge 3 \land \text{PRR} \ge 2.0 \land \chi^2 \ge 4.0$ | **8,545** |
| **van Puijenbroek ROR Criteria** | $a \ge 3 \land \text{ROR}_{025} > 1.0$ | **9,540** |
| **FDA / PhRMA EB05 Permissive** | $\text{EB05} \ge 1.0$ | **12,709** |
| **FDA / PhRMA EB05 Conservative** | $\text{EB05} \ge 2.0$ | **7,645** |

- Concordant Signals (Both Evans PRR and EB05 Conservative): **6,245 pairs**
- Evans PRR flagged **TRUE**, but EB05 Conservative flagged **FALSE**: **2,300 pairs** (sparse-cell threshold-flagged alarms filtered by shrinkage).
- EB05 Conservative flagged **TRUE**, but Evans PRR flagged **FALSE**: **1,400 pairs** (stable elevated associations where $\chi^2$ Yates penalty was too conservative).

---

## 7. Computational Profiling & Scaling Feasibility

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                   COMPUTATIONAL PROFILE (PILOT: M = 25,000)                  │
├────────────────────────────────────────┬──────────────────┬─────────────────┤
│ Pipeline Stage                         │ Runtime (sec)    │ Throughput      │
├────────────────────────────────────────┼──────────────────┼─────────────────┤
│ CSV Loading (1.16M rows to memory)     │ 2.21 s           │ 528K rows/s     │
│ Stratified Pilot Sampling              │ 0.15 s           │ —               │
│ Expected Count Vectorization           │ 0.01 s           │ 2.5M pairs/s    │
│ 2D Frequency Binning (Squashing)       │ 0.02 s           │ 1.25M pairs/s   │
│ Hyperparameter Fitting (Exact Unbinned)│ 13.56 s          │ 47 iterations   │
│ Hyperparameter Fitting (2D Binned)     │ 6.82 s           │ 45 iterations   │
│ Posterior Scoring (EBGM, EB05, EB95)   │ 33.72 s          │ 742 pairs/s     │
├────────────────────────────────────────┼──────────────────┼─────────────────┤
│ TOTAL PILOT RUNTIME                    │ 57.32 s          │ < 1 minute      │
└────────────────────────────────────────┴──────────────────┴─────────────────┘
```

### Extrapolation to Full Dataset ($N_{\text{pairs}} = 1,167,891$):
1. **Hyperparameter Fitting on Full Table:**
   - Evaluating unbinned likelihood across 1.16M rows per optimizer step would require ~20 minutes.
   - Using **2D Frequency Binning** collapses 1.16M rows into ~15,000 unique frequency bins.
   - Binned optimization on the full table will complete in **10–25 seconds**.
2. **Posterior Scoring on Full Table:**
   - Single-threaded scoring throughput is ~750 pairs/second ($\approx 25$ minutes for 1.16M pairs).
   - Scoring can be accelerated via vectorization of digamma and vectorized Brent brackets or multi-core batching, taking **8–12 minutes** total.
3. **Memory Footprint:** Peak RAM during pilot was **< 400 MB**. Full table scoring will remain well within the 8 GB host threshold.

---

## 8. Limitations & Unresolved Issues

1. **Exchangeability Assumption:** The two-component Gamma mixture assumes that all 1.16 million drug-event pairs share a single common background reporting distribution. In reality, oncology biologics have higher background reporting rates than topical anti-infectives. Subgroup-stratified EBGM is addressed in Phase 3C.2.
2. **Co-prescription & Indication Confounding:** Empirical Bayes shrinkage addresses sampling variance, but it does **not** adjust for clinical indications (e.g., metformin reported with diabetic ketoacidosis). Contextual M1 features must be incorporated for triage.
3. **Truncation at $a \ge 2$:** The candidate universe is pre-filtered to $a \ge 2$. Consequently, the fitted prior distribution $\pi(\lambda)$ describes the conditional distribution of latent reporting ratios within the selected candidate universe given $a \ge 2$, rather than a globally representative null distribution over the entire untruncated drug–event reporting matrix ($a \ge 0$). This conditionality accounts for why the baseline prior mean is $\text{Mean}_1 = 2.4048$ rather than 1.0. In Phase 3C.2, the impact of zero/one truncation on hyperparameter estimates will be formally assessed.

---

## 9. Gate Decision & Next Steps

### Gate Status: **PHASE 3C.1 VALIDATION SUITE & PILOT COMPLETED**

The implementation is verified, reproducible, numerically stable, and benchmarked against peer-reviewed literature.

### STOP CONDITION ENFORCEMENT:
In accordance with instructions, **full-dataset scoring (1.16M pairs) has NOT been launched**. Execution is paused pending user review of this technical report and authorization for Phase 3C.2 (Full-Scale Computation, M1 Contextual Analysis, and Blind OMOP/EU-ADR Benchmark Evaluation).
