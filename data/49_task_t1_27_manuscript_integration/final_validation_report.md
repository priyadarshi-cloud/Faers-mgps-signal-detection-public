# Final Validation Report — Controlled Manuscript Integration

**Task Identifier:** TASK-T1-27 — Controlled Manuscript Integration  
**Execution Timestamp:** 2026-10-18T16:35:00  
**Source Manuscript:** `data/41_task_t1_19_residual_claim_check/manuscript_coauthor_review_candidate.md`  
**Revised Manuscript:** `data/49_task_t1_27_manuscript_integration/manuscript_revised_candidate.md`  
**Output Directory:** `data/49_task_t1_27_manuscript_integration/`  
**Overall Validation Status:** **`ALL_VALIDATION_CHECKS_PASSED`**  

---

## 1. Executive Summary

This validation report evaluates the integrated co-author review candidate manuscript (`manuscript_revised_candidate.md`) against all scientific constraints, numerical invariance rules, and statistical wording refinements established across TASK-T1-23 through TASK-T1-26.

All six core validation gates have passed with zero violations:
1. **Source Manuscript Preservation:** The original manuscript `manuscript_coauthor_review_candidate.md` was preserved strictly unchanged (SHA-256: `DCA6074876C1CF35A24E11BD80020678842B1100464090C3C638973E45208AE0`, 40,216 bytes).
2. **Evidence Traceability:** Every revised claim is directly supported by verified repository artifacts in `data/45_task_t1_23_cluster_bootstrap_sensitivity/` and `data/46_task_t1_24_cluster_bootstrap_audit/`.
3. **Numerical Invariance:** All 40 canonical numerical values across cohort counts, candidate pair denominators, mixture model hyperparameters, benchmark discrimination metrics, discordance counts, contextual effect sizes, and surrogate model performance are 100% invariant between the original and revised drafts.
4. **Accurate Seed Sensitivity Representation:** The EU-ADR seed-42 Average Precision interval is reported precisely as `[+0.000140, +0.055024]`, and all 10 alternative seeds tested (seeds 0, 1, 7, 99, 123, 456, 999, 2024, 31337, 8675309) are reported as having lower bounds below zero without claiming prespecification or calling the result an artifact.
5. **Existing Supplementary Deliverable:** The manuscript references `Supplementary Table S1`, which was created directly from verified repository artifacts as `supplementary_table_s1.csv` (35 rows).
6. **Internal Review Draft Labeling:** The revised manuscript is explicitly designated as an **Internal Scientific Review Draft (Co-Author Review Candidate)** and remains unsubmitted and not publication-ready.

---

## 2. Detailed Validation Matrix

| Validation Dimension | Requirement | Method of Verification | Result | Status |
|:---|:---|:---|:---|:---:|
| **1. Source Preservation** | Original manuscript must remain untouched. | SHA-256 hash comparison against pre-task baseline. | Hash identical (`DCA60748...AE0`), length 40,216 bytes unchanged. | **PASS** |
| **2. Bonferroni Exclusion** | Remove unsupported formal Bonferroni claims. | Full-text regex search for `Bonferroni` and `multiplicity` in revised draft. | 0 occurrences of unsupported Bonferroni claims in revised text. | **PASS** |
| **3. Seed Sensitivity Framing** | Report seed-42 `[+0.000140, +0.055024]` and 10 alternative seeds without claiming prespecification or artifact status. | Verification against Section 3.4 and Discussion 4.1 text. | Exact intervals cited; described neutrally as sensitivity to random seed selection. | **PASS** |
| **4. Prevalence Scenario Accuracy** | Describe 56%-to-37% shift as Acute Liver Failure diagnostic scenario, not an overall bootstrap range. | Verification of Methods 2.7 and Limitation 8 text. | Explicitly framed as the documented diagnostic scenario omitting the Acute Liver Failure cluster. | **PASS** |
| **5. Non-Equivalence Framing** | Do not equate intervals spanning zero with proof of no difference. | Verification of Abstract, Results, Discussion, and Conclusions text. | Zero-spanning intervals consistently described as failing to establish statistically significant superiority at $\alpha = 0.05$. | **PASS** |
| **6. Numerical Invariance** | Preserve all 40 canonical numerical values. | Automated audit in `numerical_invariance_audit.csv`. | 40 of 40 values preserved exact (0 discrepancies). | **PASS** |
| **7. Scope Restrictions** | Preserve $a \ge 2$, unobserved negatives, retrospective cohort, non-causal signals, and score emulation. | Verification of Sections 2.1, 2.2, 2.6, 2.9, 4.3, 4.4, and 5. | All scope limitations preserved in full. | **PASS** |
| **8. Supplementary Cross-Reference** | Ensure Supplementary Table S1 exists. | File inspection of `supplementary_table_s1.csv`. | File exists in deliverables directory with 35 validated rows. | **PASS** |
| **9. Compliance Governance** | Keep publication declarations unresolved for author action. | Verification of Section 7 text. | Five `[Author Action Required]` blocks retained and tracked in `remaining_publication_blockers.md`. | **PASS** |
| **10. Draft Status Labeling** | Manuscript must be labeled internal review candidate. | Verification of front-matter banner. | Labeled `INTERNAL SCIENTIFIC REVIEW DRAFT — CO-AUTHOR REVIEW CANDIDATE (TASK-T1-27)`. | **PASS** |

---

## 3. Verification of Statistical and Numerical Concordance

### 3.1 Primary Canonical Benchmark Invariants
- **Cohort Flow:**
  - Physical archive-bounded cohort: **6,005,839 reports** (2014Q1–2018Q4).
  - Quarantined post-2018Q4 backfilled cases: **7,052**.
  - FDA retrospective deletion cases: **25,718**.
  - Retrospectively corrected cohort: **5,987,173**.
- **Candidate Universe ($a \ge 2$):**
  - Unique drug–ADR pairs: **1,167,891**.
  - Pairs with $a = 2$: **335,816** (28.75%).
  - Pairs with $a \ge 3$: **832,075** (71.25%).
- **MGPS Model Fit:**
  - Maximized log-likelihood: **−3,372,348.34**.
  - Bins: **61,709**.
  - Hyperparameters: $\alpha_1 = 0.0010$, $\beta_1 = 0.0068$, $\alpha_2 = 0.2859$, $\beta_2 = 0.4004$, $w = 0.8499$.
- **Signal Yields & Discordance:**
  - EB05 $\ge 2.0$: **295,560 pairs** (25.31%).
  - Evans PRR: **398,018 pairs** (34.08%).
  - Concordant signals: **262,859 pairs**.
  - Concordant non-signals: **737,172 pairs**.
  - Net difference: **102,458 pairs** (−25.74%).
  - PRR-only: **135,159 pairs**.
  - EB05-only: **32,701 pairs** (32,397 at $a = 2$, 99.07%).
- **Benchmark Evaluation Pairs:**
  - OMOP: **203 evaluable pairs** (114 pos, 89 neg; prevalence 56.16%). 145 of 234 negs (62.0%) excluded.
  - EU-ADR: **66 evaluable pairs** (39 pos, 27 neg; prevalence 59.09%). 23 of 50 negs (46.0%) excluded.
- **Table 3 Baseline Discrimination Metrics:**
  - OMOP EB05: PR-AUC 0.8626 [0.8092, 0.9103], ROC 0.8136 [0.7536, 0.8681].
  - OMOP PRR: PR-AUC 0.8325 [0.7623, 0.8964], ROC 0.7995 [0.7359, 0.8582]; $\Delta\text{AP} = +0.0301$ [−0.0067, +0.0722], $\Delta\text{ROC} = +0.0141$ [−0.0174, +0.0451].
  - OMOP ROR: PR-AUC 0.8311 [0.7601, 0.8947], ROC 0.7986 [0.7348, 0.8575]; $\Delta\text{AP} = +0.0315$ [−0.0060, +0.0746], $\Delta\text{ROC} = +0.0150$ [−0.0171, +0.0460].
  - EU-ADR EB05: PR-AUC 0.9584 [0.9065, 0.9947], ROC 0.9364 [0.8694, 0.9908].
  - EU-ADR PRR: PR-AUC 0.9371 [0.8741, 0.9828], ROC 0.9060 [0.8238, 0.9722]; $\Delta\text{AP} = +0.0213$ [−0.0035, +0.0542], $\Delta\text{ROC} = +0.0304$ [−0.0047, +0.0723].
  - EU-ADR ROR: PR-AUC 0.9384 [0.8773, 0.9830], ROC 0.9069 [0.8254, 0.9722]; $\Delta\text{AP} = +0.0200$ [−0.0037, +0.0512], $\Delta\text{ROC} = +0.0294$ [−0.0056, +0.0714].

### 3.2 Integrated Drug-Cluster Sensitivity Values
- **OMOP Drug-Cluster Paired Differences:**
  - EB05 vs. PRR $\Delta\text{PR-AUC} = +0.0301$ (95% CI: [−0.0088, +0.0724], spans zero).
  - EB05 vs. PRR $\Delta\text{ROC-AUC} = +0.0141$ (95% CI: [−0.0171, +0.0475], spans zero).
- **EU-ADR Drug-Cluster Paired Differences:**
  - EB05 vs. PRR Average Precision (Seed 42): Point delta = **+0.021325**; 95% CI: **[+0.000140, +0.055024]**.
  - Alternative Seeds (10 runs): Lower bounds range from −0.0019 to −0.0004; **all 10 span zero**.
  - EB05 vs. PRR ROC-AUC: Point delta = **+0.0304**; 95% CI: **[−0.0009, +0.0742]** (spans zero).

---

## 4. Final Assessment & Next Steps

The controlled manuscript integration in `manuscript_revised_candidate.md` is **complete, mathematically consistent, and fully verified**.

The revised candidate manuscript is ready for formal distribution to co-authors for review. The author team should complete the six items outlined in [remaining_publication_blockers.md](<project-root>/data/49_task_t1_27_manuscript_integration/remaining_publication_blockers.md) before journal submission.
