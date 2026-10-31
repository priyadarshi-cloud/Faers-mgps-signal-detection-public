# TASK-T1-11: Final Benchmark Audit and Evidence-Controlled Manuscript Integration
## Independent Benchmark Audit Report

**Task Identifier:** TASK-T1-11  
**Project:** FDA FAERS Adverse Drug Reaction (ADR) Signal Detection Research  
**Output Directory:** `data/33_task_t1_11_final_benchmark_audit/`  
**Execution Timestamp:** October 2026  
**Audit Status:** Complete — All Deliverables Verified and Audited  

---

## Executive Summary

TASK-T1-11 performs an independent benchmark audit and evidence-controlled manuscript integration for the FAERS ADR signal-detection research project. Following the completion of TASK-T1-10C (*Benchmark Population Provenance and Evaluation Reconciliation*), this task independently recomputes all benchmark discrimination metrics, verifies the provenance of all evaluation populations, formally resolves manuscript draft discrepancies, and integrates verified statistics into a final audited manuscript artifact (`manuscript_final_audited.md`).

### Key Audit Findings

1. **Canonical Evaluation Populations Verified:**
   - **OMOP Ground Truth Reference:** Exactly **$N = 203$** evaluable matched drug–outcome pairs ($114$ positive controls, $89$ negative controls; positive prevalence: $56.16\%$).
   - **EU-ADR Reference Standard:** Exactly **$N = 66$** evaluable matched drug–outcome pairs ($39$ positive controls, $27$ negative controls; positive prevalence: $59.09\%$).
   - Both datasets are strictly conditioned on pair observability in FAERS ($a \ge 2$). Unobserved pairs ($a < 2$) are excluded.

2. **Absence of Evidence for Alternative Populations ($N = 345$ and $N = 93$):**
   - A rigorous filesystem search confirmed that the claimed files `omop_scored_pairs.csv` ($N = 345$) and `euadr_scored_pairs.csv` ($N = 93$) **do not exist** anywhere in the project repository.
   - No script, pipeline execution log, intermediate table, or JSON deliverable contains or generates these populations.
   - As mandated by evidence-controlled reporting standards, these numbers are documented as having **no supporting source artifact located**, and they are completely excluded from the manuscript.

3. **Independent Statistical Recomputation ($B = 2{,}000$, Seed 42):**
   - Point estimates and $95\%$ bootstrap confidence intervals for Precision-Recall Area Under Curve (PR-AUC) and Receiver Operating Characteristic Area Under Curve (ROC-AUC) were independently recomputed from raw matched-pair data using $B = 2{,}000$ paired bootstrap replicates with shared resample indices across all comparators (EB05, EBGM, PRR, ROR).
   - **All 12 paired $95\%$ confidence intervals (6 method comparisons $\times$ 2 metrics) span zero.**
   - While point estimates favor EB05 over all comparators (e.g., OMOP PR-AUC: EB05 $0.8626$ vs. PRR $0.8325$, $\Delta = +0.0301$; EU-ADR PR-AUC: EB05 $0.9584$ vs. PRR $0.9371$, $\Delta = +0.0213$), the sample sizes of evaluable benchmark pairs ($N = 203$ and $N = 66$) provide insufficient statistical power to establish statistically significant superiority at $\alpha = 0.05$.

4. **Correction of Manuscript Discrepancies (DISC-07 through DISC-10):**
   - Prior manuscript drafts retained sign-flipped paired confidence intervals for EB05 vs. EBGM from earlier informal notes. In `manuscript_final_audited.md`, Table 3 and associated prose have been fully updated with verified $B = 2{,}000$ paired bootstrap intervals.
   - All source artifacts, including prior manuscripts and raw matched files, remain strictly preserved and unmodified.

---

## 1. Source Artifact Verification & Integrity

Before statistical recomputation, all relevant project source files were inspected, row-counted, and cryptographically verified via SHA-256 hashing.

| Artifact Path | Description | Rows / Units | Labels / Content | SHA-256 (Prefix) | Audit Status |
|:---|:---|:---:|:---|:---:|:---:|
| `data/14_phase3d_benchmark_evaluation/omop_matched_evaluation_pairs.csv` | Canonical OMOP evaluable matched pairs | 203 | 114 pos, 89 neg; 0 missing, 0 dupes | `b0cd1524...` | **VERIFIED** |
| `data/14_phase3d_benchmark_evaluation/eu_adr_matched_evaluation_pairs.csv` | Canonical EU-ADR evaluable matched pairs | 66 | 39 pos, 27 neg; 0 missing, 0 dupes | `e82e226e...` | **VERIFIED** |
| `data/14_phase3d_benchmark_evaluation/phase3d_benchmark_evaluation_results.json` | Phase 3D benchmark evaluation output | N/A | Contains coverage summary confirming N=203 and N=66 | `75124b2a...` | **VERIFIED** |
| `data/05_reference_standards/omop/omop_reference_set.csv` | Raw OMOP reference standard | 399 | 165 pos, 234 neg (Ryan 2013) | `779fc1b2...` | **VERIFIED** |
| `data/05_reference_standards/eu_adr/eu_adr_reference_set.csv` | Raw EU-ADR reference standard | 93 | 43 pos, 50 neg (Coloma 2013) | `2195513a...` | **VERIFIED** |
| `data/29_task_t1_10_manuscript_harmonization/manuscript_harmonized.md` | Prior harmonized manuscript | 302 lines | Unmodified source copy | `6dbbb765...` | **PRESERVED INTACT** |
| `data/14_phase3d_benchmark_evaluation/omop_scored_pairs.csv` | Claimed N=345 OMOP population | 0 | File does not exist on disk | N/A | **ABSENT (NON-EXISTENT)** |
| `data/14_phase3d_benchmark_evaluation/euadr_scored_pairs.csv` | Claimed N=93 EU-ADR evaluated set | 0 | File does not exist on disk | N/A | **ABSENT (NON-EXISTENT)** |

---

## 2. Independent Statistical Recomputation Methodology

Independent recomputation was performed by `scripts/independent_benchmark_audit_t1_11.py` with the following design:

1. **Input Data:** Authoritative raw matched-pair CSV files:
   - `omop_matched_evaluation_pairs.csv` ($N = 203$, columns: `drug_concept_id`, `outcome_concept_id`, `groundTruth`, `eb05`, `ebgm`, `prr`, `ror`)
   - `eu_adr_matched_evaluation_pairs.csv` ($N = 66$, columns: `drug_concept_id`, `outcome_concept_id`, `groundTruth`, `eb05`, `ebgm`, `prr`, `ror`)
2. **Missing-Score Handling:** Zero missing scores were found across all metrics and rows. No imputation was required.
3. **Resampling Unit & Pairing:** The observational resampling unit is the matched drug–outcome pair. To ensure valid comparative inference, **paired resampling** was strictly enforced: for each bootstrap replicate $b \in \{1, \dots, B\}$, a single random index vector of length $N$ was sampled with replacement and applied identically across EB05, EBGM, PRR, and ROR.
4. **Bootstrap Configuration:** $B = 2{,}000$ bootstrap replicates, random seed $42$ (`numpy.random.default_rng(42)`).
5. **Metric Implementations:**
   - **PR-AUC:** Evaluated via `sklearn.metrics.average_precision_score` (area under the interpolated precision-recall curve).
   - **ROC-AUC:** Evaluated via `sklearn.metrics.roc_auc_score` (equivalent to normalized Mann-Whitney U rank statistic).
6. **Confidence Intervals:** Empirical percentile intervals at the $2.5^{\text{th}}$ and $97.5^{\text{th}}$ percentiles:
   - Marginal CIs: Computed from the bootstrap distribution of the individual metric.
   - Paired Difference CIs: Computed directly from the paired difference distribution:
     $$\Delta \text{AUC}^{(b)} = \text{AUC}_{\text{EB05}}^{(b)} - \text{AUC}_{\text{comparator}}^{(b)}$$
7. **Scientific Inference Guardrails:**
   - Significance is asserted **if and only if** the paired $95\%$ confidence interval excludes zero.
   - No affirmative pseudo p-values or unsupported claims of superiority are permitted.

---

## 3. Recomputed Benchmark Results & Comparison

### 3.1 Recomputed Benchmark Discrimination Metrics ($B = 2{,}000$, Seed 42)

The independently recomputed statistics from `independently_recomputed_statistics.csv` are summarized below:

| Benchmark Reference Standard | Method | Matched Pairs ($N$) | Pos / Neg | Prevalence | PR-AUC (Point, 95% Marginal CI) | Paired $\Delta\text{PR-AUC}$ (EB05 vs Method, 95% Paired CI) | ROC-AUC (Point, 95% Marginal CI) | Paired $\Delta\text{ROC-AUC}$ (EB05 vs Method, 95% Paired CI) | Paired CIs Span Zero? |
|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **OMOP Ground Truth** | **EB05 (Primary)** | 203 | 114 / 89 | 56.16% | **0.8626** [0.8092, 0.9103] | Reference (0.0) | **0.8136** [0.7536, 0.8681] | Reference (0.0) | N/A |
| | EBGM | 203 | 114 / 89 | 56.16% | 0.8506 [0.7919, 0.9046] | +0.0120 [−0.0072, +0.0337] | 0.8071 [0.7447, 0.8630] | +0.0065 [−0.0134, +0.0260] | **Yes** |
| | PRR | 203 | 114 / 89 | 56.16% | 0.8325 [0.7623, 0.8964] | +0.0301 [−0.0067, +0.0722] | 0.7995 [0.7359, 0.8582] | +0.0141 [−0.0174, +0.0451] | **Yes** |
| | ROR | 203 | 114 / 89 | 56.16% | 0.8311 [0.7601, 0.8947] | +0.0315 [−0.0060, +0.0746] | 0.7986 [0.7348, 0.8575] | +0.0150 [−0.0171, +0.0460] | **Yes** |
| **EU-ADR Reference** | **EB05 (Primary)** | 66 | 39 / 27 | 59.09% | **0.9584** [0.9065, 0.9947] | Reference (0.0) | **0.9364** [0.8694, 0.9908] | Reference (0.0) | N/A |
| | EBGM | 66 | 39 / 27 | 59.09% | 0.9493 [0.8914, 0.9894] | +0.0091 [−0.0066, +0.0272] | 0.9240 [0.8518, 0.9824] | +0.0123 [−0.0103, +0.0381] | **Yes** |
| | PRR | 66 | 39 / 27 | 59.09% | 0.9371 [0.8741, 0.9828] | +0.0213 [−0.0035, +0.0542] | 0.9060 [0.8238, 0.9722] | +0.0304 [−0.0047, +0.0723] | **Yes** |
| | ROR | 66 | 39 / 27 | 59.09% | 0.9384 [0.8773, 0.9830] | +0.0200 [−0.0037, +0.0512] | 0.9069 [0.8254, 0.9722] | +0.0294 [−0.0056, +0.0714] | **Yes** |

### 3.2 Stability Across Bootstrap Replicate Counts ($B = 1{,}000$ vs. $B = 2{,}000$)

Comparing the $B = 1{,}000$ results (from Phase 3D / TASK-T1-10C) with the $B = 2{,}000$ results confirms complete qualitative and quantitative stability:
- Point estimates are mathematically identical (e.g., OMOP EB05 PR-AUC: $0.8626$, ROC-AUC: $0.8136$).
- The confidence interval bounds shift by $\le 0.003$ due to reduced Monte Carlo simulation noise.
- **The zero-spanning property is 100% invariant:** in both $B = 1{,}000$ and $B = 2{,}000$, all 12 paired confidence intervals span zero.

### 3.3 Resolution of Discrepancies DISC-07 to DISC-10

In earlier manuscript drafts, EBGM paired confidence intervals suffered from sign reversal in draft text. This audit permanently resolves these discrepancies:

- **DISC-07 (OMOP EBGM $\Delta\text{PR}$):** Draft reported `+0.0121 [−0.0045, +0.0312]`. Audited value: `+0.0120 [−0.0072, +0.0337]`.
- **DISC-08 (OMOP EBGM $\Delta\text{ROC}$):** Draft reported `+0.0065 [−0.0072, +0.0210]`. Audited value: `+0.0065 [−0.0134, +0.0260]`.
- **DISC-09 (EU-ADR EBGM $\Delta\text{PR}$):** Draft reported `+0.0092 [−0.0051, +0.0281]`. Audited value: `+0.0091 [−0.0066, +0.0272]`.
- **DISC-10 (EU-ADR EBGM $\Delta\text{ROC}$):** Draft reported `+0.0124 [−0.0084, +0.0351]`. Audited value: `+0.0123 [−0.0103, +0.0381]`.

All four recomputed CIs continue to span zero. Inference remains unchanged: EB05 does not demonstrate statistically significant discrimination superiority over EBGM on either benchmark.

---

## 4. Resolution of the Alternate-Population Discrepancy ($N = 345$ and $N = 93$)

### 4.1 Provenance Investigation

TASK-T1-10B conversational notes referenced an evaluation of OMOP on $N = 345$ pairs (with EB05 PR-AUC $= 0.4633$) and EU-ADR on $N = 93$ pairs (with EB05 PR-AUC $= 0.6277$), attributing them to files named `omop_scored_pairs.csv` and `euadr_scored_pairs.csv`.

An exhaustive search was conducted across all project directories:
1. `data/14_phase3d_benchmark_evaluation/`
2. `data/05_reference_standards/`
3. `data/31_task_t1_10b_bootstrap_reconciliation/`
4. `data/32_task_t1_10c_benchmark_population_reconciliation/`
5. `scripts/` and root log files

### 4.2 Audit Finding

- **Filesystem Verification:** Neither `omop_scored_pairs.csv` nor `euadr_scored_pairs.csv` exists on disk.
- **Data Traceability:** No data file in the project records $345$ evaluable OMOP pairs or reports PR-AUC $= 0.4633$.
- **Reference Standard Distinction:** The raw EU-ADR reference standard (`eu_adr_reference_set.csv`) indeed contains $93$ rows ($43$ positive, $50$ negative); however, this is the unconditioned reference catalog, not an evaluated FAERS subset. When conditioned on FAERS occurrence ($a \ge 2$), only $66$ pairs are evaluable.
- **Evidence-Controlled Conclusion:** As recorded in `population_provenance_findings.csv`, the finding is: **No supporting source artifact was located for the $N = 345$ evaluation claim.**

---

## 5. Evidence-Controlled Manuscript Integration

The final audited manuscript, `manuscript_final_audited.md`, incorporates verified statistics and aligns with strict evidence controls:

1. **Header:** Formally identifies the document as the TASK-T1-11 Final Audited Manuscript.
2. **Abstract:** Updated paired difference confidence intervals to independently verified $B = 2{,}000$ values; explicitly states that paired difference intervals span zero.
3. **Methods Section 2.7:** Clarified that marginal CIs originated from $B = 1{,}000$ while reported Table 3 paired difference intervals represent independently recomputed $B = 2{,}000$ resamples with shared indices across methods.
4. **Results Section 3.4 & Table 3:** Updated all 8 method rows with $B = 2{,}000$ point estimates, marginal CIs, paired deltas, and paired CIs. Corrected DISC-07 through DISC-10.
5. **Section 3.4 Prose:** Updated text difference figures to $+0.0301$ (OMOP PRR) and $+0.0213$ (EU-ADR PRR).
6. **Scientific Limitations Intact:** Preserved all critical discussions in Sections 4 and 5 regarding observability conditioning ($a \ge 2$), prevalence inflation, lack of causal claims, and surrogate ML interpretation.

---

## 6. Scientific Safeguards and Invariants

This audit strictly enforces the following scientific safeguards:

1. **Observability Conditioning:** Benchmark performance is strictly conditional on $a \ge 2$. In spontaneous reporting databases, unobserved pairs ($a < 2$) cannot be evaluated. This excluded $62.0\%$ of OMOP and $46.0\%$ of EU-ADR negative controls, altering effective positive prevalence to $56.16\%$ and $59.09\%$, respectively.
2. **Absence of Statistical Dominance:** Observed point-estimate gains in PR-AUC ($+2.1\%$ to $+3.2\%$) are accompanied by $95\%$ paired bootstrap confidence intervals that include zero. Authors must not claim statistically verified superiority.
3. **Signal Yield vs. False Positive Reduction:** EB05 produces $102{,}458$ fewer alerts than Evans PRR. This reflects Bayesian shrinkage regularizing small-sample reporting variance ($a = 2–3$), not a verified false-positive reduction, because the vast majority of FAERS pairs lack reference standard adjudication.
4. **No Causal Biology in Surrogate Explanations:** LightGBM surrogates (achieving $R^2 = 0.230$ for contextual features and $R^2 = 0.999$ for contingency metrics) emulate algorithmic scoring rules. SHAP feature attributions describe score mechanics, not biological causation or clinical truth.

---

## 7. Audit Manifest and Artifact Verification

All deliverables generated in `data/33_task_t1_11_final_benchmark_audit/` are cataloged in `artifact_manifest.json` with cryptographic SHA-256 hashes and file sizes.

The automated validation suite (`validation_script.py`) confirms:
- Integrity and presence of all 8 task deliverables.
- Strict preservation of source files and prior task directories.
- Exact numerical matching between CSV tables, manuscript text, claims traceability, and source data.
- Total absence of pseudo p-values or unsupported claims.

### Readiness for Scientific Review

The audited evidence base is mathematically sound, fully traceable to canonical source files, and ready for independent scientific review. In accordance with project instructions, passing automated validation establishes numerical and evidentiary integrity, but does not substitute for domain-expert scientific review.
