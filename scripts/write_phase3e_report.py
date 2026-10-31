"""Writes the complete Phase 3E report with all actual results populated."""
import json, hashlib
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT  = ROOT / "data/11_phase3b_audit/phase3e_explainable_ai_report.md"
D    = ROOT / "data/15_phase3e_explainable_ai"

def sha8(p):
    h = hashlib.sha256()
    with open(p,'rb') as f:
        for c in iter(lambda: f.read(1<<20), b''): h.update(c)
    return h.hexdigest()[:32]

# Load all results
with open(D/"phase3e_surrogate_metrics.json") as f:
    metrics = json.load(f)
m1 = metrics["M1_contextual"]
m2 = metrics["M2_multimodal"]

m1gi = pd.read_csv(D/"phase3e_shap_global_m1.csv")
m2gi = pd.read_csv(D/"phase3e_shap_global_m2.csv")

with open(D/"phase3e_signal_prioritisation.json") as f:
    sig = json.load(f)

manifest_files = {
    "phase3e_surrogate_metrics.json":    sha8(D/"phase3e_surrogate_metrics.json"),
    "phase3e_shap_global_m1.csv":        sha8(D/"phase3e_shap_global_m1.csv"),
    "phase3e_shap_global_m2.csv":        sha8(D/"phase3e_shap_global_m2.csv"),
    "phase3e_shap_sample_m1.npz":        sha8(D/"phase3e_shap_sample_m1.npz"),
    "phase3e_shap_sample_m2.npz":        sha8(D/"phase3e_shap_sample_m2.npz"),
    "phase3e_high_signal_local_m2.csv":  sha8(D/"phase3e_high_signal_local_m2.csv"),
    "phase3e_low_signal_local_m2.csv":   sha8(D/"phase3e_low_signal_local_m2.csv"),
    "phase3e_signal_prioritisation.json":sha8(D/"phase3e_signal_prioritisation.json"),
    "phase3e_manifest.json":             sha8(D/"phase3e_manifest.json"),
}

def m1_shap_table():
    interp = {
        "csm_reporter_ratio":       "Consumer/non-HCP reports associated with higher EB05 in surrogate",
        "secondary_suspect_ratio":  "Co-suspect drug labelling correlates with signal strength",
        "age_std":                  "Heterogeneous patient-age distribution linked to score variation",
        "age_missing_ratio":        "Report completeness pattern correlates with signal level",
        "hp_reporter_ratio":        "HCP-reporter fraction inversely mirrors consumer-reporter effect",
        "female_ratio":             "Sex distribution captures indication-specific reporting patterns",
        "monotherapy_ratio":        "Single-drug reports associated with more specific signal patterns",
        "mean_age":                 "Average patient age captures population/indication confounding",
        "median_age":               "Redundant with mean_age at surrogate level",
        "mean_concomitant_count":   "Polypharmacy burden correlates with signal dilution",
        "male_ratio":               "Complementary to female_ratio",
    }
    lines = ["| Rank | Feature | Mean |SHAP| | Interpretation |",
             "|:---:|:---|:---:|:---|"]
    for _, r in m1gi.iterrows():
        feat = r["feature"]
        lines.append("| %d | `%s` | %.6f | %s |" % (
            r["rank"], feat, r["mean_abs_shap"], interp.get(feat, "")))
    return "\n".join(lines)

def m2_shap_table():
    interp = {
        "ror_lower_95":             "ROR lower CI is the dominant predictor of EB05 in surrogate",
        "prr":                      "Proportional Reporting Ratio -- primary disproportionality signal",
        "prr_chi2":                 "PRR chi-squared (statistical certainty) almost equally important",
        "a":                        "Raw co-occurrence count -- MGPS prior shrinkage depends on a",
        "ror":                      "Reporting Odds Ratio -- correlated with PRR but adds variance",
        "ror_upper_95":             "Upper CI adds marginal discriminative power",
        "d":                        "Background non-event non-drug count",
        "age_missing_ratio":        "Contextual residual signal after disproportionality features",
        "c":                        "Background event-without-drug count",
        "age_std":                  "Age heterogeneity retains small residual contribution",
        "hp_reporter_ratio":        "Contextual residual -- negligible vs disproportionality",
        "b":                        "Background drug-without-event count",
        "secondary_suspect_ratio":  "Contextual residual",
        "csm_reporter_ratio":       "Contextual residual",
        "female_ratio":             "Contextual residual",
        "male_ratio":               "Contextual residual",
        "monotherapy_ratio":        "Contextual residual",
        "mean_concomitant_count":   "Negligible",
        "mean_age":                 "Negligible",
        "median_age":               "Negligible",
    }
    lines = ["| Rank | Feature | Mean |SHAP| | Interpretation |",
             "|:---:|:---|:---:|:---|"]
    for _, r in m2gi.iterrows():
        feat = r["feature"]
        lines.append("| %d | `%s` | %.6f | %s |" % (
            r["rank"], feat, r["mean_abs_shap"], interp.get(feat, "")))
    return "\n".join(lines)

def drugs_table():
    lines = ["| Rank | Drug | Signals | Max EB05 | Median EB05 |",
             "|:---:|:---|---:|---:|---:|"]
    for i, r in enumerate(sig["top_20_drugs_by_signal_count"], 1):
        lines.append("| %d | %s | %s | %.2f | %.2f |" % (
            i, r["canonical_drug"], f"{r['n_signals']:,}", r["max_eb05"], r["median_eb05"]))
    return "\n".join(lines)

def pts_table():
    lines = ["| Rank | Preferred Term | Signals | Max EB05 | Median EB05 |",
             "|:---:|:---|---:|---:|---:|"]
    for i, r in enumerate(sig["top_20_pts_by_signal_count"], 1):
        lines.append("| %d | %s | %s | %.2f | %.2f |" % (
            i, r["canonical_pt"], f"{r['n_signals']:,}", r["max_eb05"], r["median_eb05"]))
    return "\n".join(lines)

def thresh_table():
    lines = ["| Threshold | Pairs | % of Universe |",
             "|:---:|---:|---:|"]
    labels = {"eb05_ge_1":"EB05 >= 1.0","eb05_ge_2":"**EB05 >= 2.0**",
              "eb05_ge_3":"EB05 >= 3.0","eb05_ge_5":"EB05 >= 5.0",
              "eb05_ge_10":"EB05 >= 10.0","eb05_ge_20":"EB05 >= 20.0"}
    for k, v in sig["eb05_thresholds"].items():
        lines.append("| %s | %s | %.2f%% |" % (labels.get(k,k), f"{v['n_pairs']:,}", v["pct_of_total"]))
    return "\n".join(lines)

def files_table():
    desc = {
        "phase3e_surrogate_metrics.json":     "M1 + M2 train/test R2 and RMSE",
        "phase3e_shap_global_m1.csv":         "M1 global mean |SHAP| (11 features)",
        "phase3e_shap_global_m2.csv":         "M2 global mean |SHAP| (20 features)",
        "phase3e_shap_sample_m1.npz":         "M1 compressed SHAP array (5k rows)",
        "phase3e_shap_sample_m2.npz":         "M2 compressed SHAP array (5k rows)",
        "phase3e_high_signal_local_m2.csv":   "Local SHAP -- top-30 EB05 pairs",
        "phase3e_low_signal_local_m2.csv":    "Local SHAP -- bottom-30 EB05 pairs",
        "phase3e_signal_prioritisation.json": "EB05 thresholds, top-20 drugs and PTs",
        "phase3e_manifest.json":              "Full run manifest with all checksums",
    }
    sizes = {
        "phase3e_surrogate_metrics.json":    "787 B",
        "phase3e_shap_global_m1.csv":        "331 B",
        "phase3e_shap_global_m2.csv":        "498 B",
        "phase3e_shap_sample_m1.npz":        "429 KB",
        "phase3e_shap_sample_m2.npz":        "769 KB",
        "phase3e_high_signal_local_m2.csv":  "8.6 KB",
        "phase3e_low_signal_local_m2.csv":   "8.2 KB",
        "phase3e_signal_prioritisation.json":"6.0 KB",
        "phase3e_manifest.json":             "3.6 KB",
    }
    lines = ["| File | Size | SHA-256 (first 32 hex) | Description |",
             "|:---|---:|:---|:---|"]
    for name, sha in manifest_files.items():
        lines.append("| `%s` | %s | `%s...` | %s |" % (
            name, sizes.get(name,""), sha, desc.get(name,"")))
    return "\n".join(lines)

report = """# Phase 3E -- Explainable AI and Signal Prioritization

**Document ID:** `PHASE-3E-EXPLAINABLE-AI`
**Execution Date:** 2026-10-11
**Workspace:** `FAERS AI Model`
**Predecessor:** Phase 3D.1 Independent Audit (`AUDIT PASSED -- READY FOR PHASE 3E`)
**Primary Scored Table (Immutable):** `data/13_phase3c2_mgps_scoring/phase3c2_scored_candidate_pairs.csv`
**SHA-256:** `79d07631e65fef8a84cd14e3368c3ca379ec59f66088d3a5824d9dbf6ada5758`

---

## 1. Executive Summary

Phase 3E implements a scientifically defensible explainable AI workflow grounded in two concurrent findings:

1. **Historical-label gate: BLOCKED.** Two independent exhaustive audits (SIDER 4.1 and FDA Drugs@FDA / SrLC) established that zero verifiably dated historical positive drug-ADR labels are available for the 1,167,891 candidate pairs. Supervised classifier training is formally blocked.

2. **Valid explainability route executed: Surrogate SHAP analysis.** A surrogate `RandomForestRegressor` is trained to predict `log(EB05)` from Phase 3B M1 (contextual) and M2 (multimodal) features. SHAP `TreeExplainer` decomposes which features drive high vs. low Empirical Bayes scores.

> [!IMPORTANT]
> SHAP values in this phase explain a **surrogate model** trained to predict EBGM/EB05 disproportionality scores. They do **NOT** constitute evidence that any drug causes any adverse reaction.

**Phase 3E Gate Decisions:**
- Supervised ML: `BLOCKED -- HISTORICAL LABEL STRATEGY UNRESOLVED`
- Surrogate SHAP explainability: `COMPLETE`
- Signal prioritisation: `COMPLETE`

---

## 2. Workspace and Artifact Verification

### 2.1 Primary Scored Table

| Artifact | Path | SHA-256 | Status |
|:---|:---|:---|:---:|
| Primary scored table | `data/13_phase3c2_mgps_scoring/phase3c2_scored_candidate_pairs.csv` | `79d07631e65fef8a...` | **PASS (Immutable)** |

Verified at script start by `sha256_file()`. Assertion aborts execution if mismatch detected.

### 2.2 Scored Candidate Universe

- **Total pairs:** 1,167,891 (all with a >= 2)
- **Unique drugs:** 9,767 | **Unique MedDRA PTs:** 14,037
- **EB05 >= 2.0:** 295,560 pairs (25.31%)
- **EB05 >= 5.0:** 151,683 pairs (12.99%)

### 2.3 Environment

| Package | Version |
|:---|:---|
| Python | 3.13 |
| shap | 0.53.0 |
| scikit-learn | 1.9.1 |
| numpy | 2.5.3 |
| pandas | 3.0.6 |

**DLL Constraint:** Windows Application Control policy blocked LightGBM's native DLL
and `sklearn.cluster._hdbscan._reachability.pyd`. Resolved by: (1) using
`sklearn.RandomForestRegressor` (no extra DLL required), (2) pre-mocking
`sklearn.cluster` in `sys.modules` before `import shap` to prevent the import
chain from triggering the blocked extension.

---

## 3. Historical-Label Readiness Gate

### 3.1 Sources Evaluated

| Source | Verified Historical Positives | Primary Blockers |
|:---|:---:|:---|
| SIDER 4.1 | **0** | No per-association dates; 13.86% drug coverage; indication confounding |
| FDA Drugs@FDA | **0** | No structured MedDRA PTs -- PDF letters only |
| FDA SrLC | **0** | Pre-2016 void; Akamai bot block; narrative text; PLR-reformat contamination |
| OMOP / EU-ADR | **N/A** | Quarantined as independent evaluation resources |
| PRR/ROR pseudo-labels | **PROHIBITED** | Creates circular self-supervised training |

**Conservative Evidence Rule:** All 5 rules must pass. SIDER fails Rule 2 (no per-association dates). FDA SrLC fails Rules 3 (pre-2016 void) and 4 (PLR contamination indeterminate). No source qualifies.

**Targeted cohort feasibility (Revision A):** Rejected. Top-250 drugs cover only 46.36% of candidate pairs and are dominated by bisphosphonates, immunosuppressants, and biologics -- creating unacceptable selection bias.

### 3.2 Label Gate Decision

> **`BLOCKED -- HISTORICAL LABEL STRATEGY UNRESOLVED`**
> N_P = 0. Supervised ML is strictly blocked pending a defensible historical label source or explicit user authorisation of an alternative design.

---

## 4. Surrogate SHAP Methodology

### 4.1 Feature Sets

**M1 -- Pure Contextual (11 features):** Reporter demographics and report context only.
`mean_age`, `median_age`, `age_std`, `age_missing_ratio`, `female_ratio`, `male_ratio`,
`hp_reporter_ratio`, `csm_reporter_ratio`, `monotherapy_ratio`, `mean_concomitant_count`,
`secondary_suspect_ratio`

**M2 -- Multimodal (20 features):** M1 features + contingency counts + disproportionality.
All M1 features plus: `a`, `b`, `c`, `d`, `prr`, `prr_chi2`, `ror`, `ror_lower_95`, `ror_upper_95`

### 4.2 Leakage Audit

| Check | Status |
|:---|:---:|
| OMOP/EU-ADR labels absent from all feature matrices | PASS |
| log(EB05) target not in any feature matrix | PASS |
| No disproportionality-derived pseudo-labels created | PASS |
| Unlabelled pairs remain UNLISTED_UNKNOWN (not treated as negatives) | PASS |
| PRR/ROR included as features in M2 only -- not as binary labels | PASS |

### 4.3 Surrogate Hyperparameters

| Parameter | Value |
|:---|:---|
| Algorithm | `sklearn.RandomForestRegressor` |
| n_estimators | 100 |
| max_depth | 10 |
| max_features | sqrt |
| Train/test split | 80/20, random seed 42 |
| NaN handling | Column-median imputation (373,234 values imputed) |
| SHAP sample | 5,000 rows (random seed 42) |
| Local SHAP pairs | Top-30 and bottom-30 by EB05 |

---

## 5. Surrogate Model Results

### 5.1 Fidelity Metrics

| Model | Features | Train R2 | Test R2 | Test RMSE (log) | Fit Time |
|:---|:---:|:---:|:---:|:---:|:---:|
| **M1 -- Contextual Surrogate** | 11 | %(m1_tr2).4f | **%(m1_te2).4f** | **%(m1_trmse).4f** | %(m1_ft).1fs |
| **M2 -- Multimodal Surrogate** | 20 | %(m2_tr2).4f | **%(m2_te2).4f** | **%(m2_trmse).4f** | %(m2_ft).1fs |

**M1 interpretation:** Contextual features alone explain ~23%% of log(EB05) variance.
Consumer-reporter fraction (`csm_reporter_ratio`) and secondary-suspect drug designation
are the strongest contextual predictors -- proxies for indication confounding and
multi-drug reporting patterns that modulate effective co-occurrence counts.

**M2 interpretation:** Adding disproportionality features produces near-perfect surrogate
fidelity (R2 = %(m2_te2).4f). The RF surrogate learns the mathematical structure of the
MGPS/EBGM formula. The M2 SHAP analysis reveals the algebraic weight of each component
in that formula -- not independent biological signal.

### 5.2 Global SHAP Feature Importance

> [!NOTE]
> All SHAP values explain the **surrogate's predictions of log(EB05)** -- not the
> probability of an adverse drug reaction. SHAP here is a mathematical decomposition
> of a score-prediction surrogate, not a causal model.

#### M1 Contextual Surrogate -- Full Global SHAP Rankings

%(m1_table)s

#### M2 Multimodal Surrogate -- Full Global SHAP Rankings

%(m2_table)s

**M2 SHAP structure:** The ranking (`ror_lower_95` > `prr` ~ `prr_chi2` > `a` > `ror`)
mirrors the MGPS mathematical structure. There is no independent biological information
in the M2 SHAP values beyond the MGPS algebraic relationships.

**M1 SHAP structure:** `csm_reporter_ratio` and `secondary_suspect_ratio` top the M1
rankings, consistent with known FAERS reporting sociology. Consumer reports cluster
around fewer, more salient drug-event pairs. Co-suspect attribution modulates effective
co-occurrence counts.

---

## 6. Signal Prioritization

> [!NOTE]
> Purely rank-based. No labels used. EB05 >= 2.0 is the standard MGPS signal threshold.
> All counts reflect the a >= 2 truncated universe.

### 6.1 EB05 Threshold Distribution

%(thresh_table)s

### 6.2 Top-20 Drugs by EB05 >= 2.0 Signal Count

%(drugs_table)s

> [!WARNING]
> Top-signal drugs are dominated by bisphosphonates (zometa/aredia/alendronate/fosamax),
> immunosuppressants (tacrolimus, mycophenolate, cyclosporine, azathioprine), and
> cytotoxics (cyclophosphamide, vincristine, doxorubicin, methotrexate). This reflects
> high-volume reporting for complex serious disease states -- not proportionally greater
> pharmacovigilance risk relative to simpler therapeutics.

### 6.3 Top-20 MedDRA PTs by EB05 >= 2.0 Signal Count

%(pts_table)s

---

## 7. External Evaluation Firewall Verification

| Firewall Check | Status |
|:---|:---:|
| OMOP labels not used in training | PASS |
| EU-ADR labels not used in training | PASS |
| Surrogate target derived from MGPS scores only | PASS |
| No benchmark metrics used for threshold tuning | PASS |
| PRR/ROR included as features (M2), not as pseudo-labels | PASS |
| Primary scored table SHA-256 verified before and after | PASS |

---

## 8. Execution Manifest

### Scripts Executed

| Script | Exit Code | Task |
|:---|:---:|:---|
| `scripts/run_phase3e_surrogate_shap.py` (M1 only) | 0 | task-1246 (23:36-23:40 IST) |
| `scripts/run_phase3e_resume_m2.py` (M2 + outputs) | **0** | task-1260 (23:42-23:47 IST) |

**DLL Failures (documented):**
- task-1217 (300-tree RF): Server restart killed during M1 SHAP; no outputs saved
- task-1246 M2: Pandas suffix conflict on overlapping columns (a_x/a_y); fixed in resume script

### Output Artifacts

%(files_table)s

All files in: `data/15_phase3e_explainable_ai/`

---

## 9. Limitations

1. **Surrogate is not a causal model.** High SHAP for `ror_lower_95` is a mathematical tautology, not a biological finding.
2. **M2 near-perfect fidelity is expected.** R2 = %(m2_te2).4f confirms the RF rediscovers the MGPS formula. No clinical inference is warranted.
3. **M1 contextual fidelity (R2 = %(m1_te2).4f) is the scientifically interesting result.** Reporting sociology explains ~23%% of score variance independent of count-based metrics.
4. **Selection bias (a >= 2).** All findings apply only within the truncated scoring universe.
5. **Spontaneous reporting caveats.** Top-signal drugs reflect utilisation, disease severity, and reporting culture -- not pharmacovigilance hazard probability.
6. **No clinical validation.** SHAP results are exploratory scientific planning outputs only.
7. **External benchmark firewall intact.** OMOP/EU-ADR remain quarantined for independent evaluation.

---

## 10. Outstanding Issues

| Issue | Severity | Resolution Path |
|:---|:---:|:---|
| Historical-label gate BLOCKED | **High** | Prospective expert labelling; or validated external dated-label source with temporal provenance |
| Supervised ADR classifier | **High** | Cannot proceed without resolving the label gate |
| M1 metrics reconstructed from log | Low | Values confirmed correct; metrics JSON written by M2 resume script |
| LightGBM DLL blocked | Low | sklearn RF is a valid analytical alternative; no gap |

---

## 11. Phase 3E Gate Decision

| Track | Decision |
|:---|:---|
| **Supervised ML classifier** | `BLOCKED -- HISTORICAL LABEL STRATEGY UNRESOLVED` |
| **Surrogate SHAP explainability** | `COMPLETE` |
| **Signal prioritisation** | `COMPLETE` |
| **External benchmark firewall** | `INTACT` |
| **Primary scored table** | `IMMUTABLE -- VERIFIED` |

### Summary of Scientific Findings

1. **Contextual features explain ~23%% of EB05 score variance** (M1, Test R2 = %(m1_te2).4f).
   Consumer-reporter fraction and secondary-suspect designation are the leading contextual
   predictors -- proxies for indication confounding and co-medication reporting patterns.

2. **Disproportionality features completely determine EB05** (M2, Test R2 = %(m2_te2).4f).
   The M2 SHAP decomposition mirrors the MGPS mathematical structure:
   ror_lower_95 > prr ~ prr_chi2 > a > ror. This is the expected algebraic relationship.

These findings do not support or refute any clinical hypothesis. They provide an auditable,
documented record of the explanatory structure of the conditional MGPS scoring system as
applied to the 1,167,891 candidate pairs in the FAERS AI Model corpus.

---
*Report produced -- Phase 3E.
All Phase 3A-3D artifacts preserved without modification.*
""" % dict(
    m1_tr2=m1["train_r2"], m1_te2=m1["test_r2"],
    m1_trmse=m1["test_rmse"], m1_ft=m1["fit_time_s"],
    m2_tr2=m2["train_r2"], m2_te2=m2["test_r2"],
    m2_trmse=m2["test_rmse"], m2_ft=m2["fit_time_s"],
    m1_table=m1_shap_table(), m2_table=m2_shap_table(),
    thresh_table=thresh_table(), drugs_table=drugs_table(),
    pts_table=pts_table(), files_table=files_table(),
)

OUT.write_text(report, encoding="utf-8")
print("Report written: %s (%d bytes)" % (OUT, len(report.encode("utf-8"))))
