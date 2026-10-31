# Phase 3C.1 Dependency Change Record — SciPy Installation in `.venv`

**Project:** Explainable AI Approaches for Adverse Drug Reaction Signal Detection in Pharmacovigilance using FAERS  
**Phase:** Phase 3C.1 (Empirical Bayes Signal Prioritization Engine)  
**Date:** October 11, 2026  
**Auditor / Modeller:** Research Pipeline Environment Audit  
**Target Environment:** Project virtual environment (`.\.venv\Scripts\python.exe`)  

---

## 1. Reason for Dependency Change
Phase 3C pivots from supervised classification (blocked by the absence of verified pre-2018 positive training labels) to unsupervised Empirical Bayes signal prioritization using the Multi-item Gamma Poisson Shrinker (MGPS / EBGM) framework (DuMouchel 1999).

Calculating empirical Bayesian shrinkage requires:
1. `scipy.optimize.minimize` (L-BFGS-B constrained numerical optimization of the 5-parameter Negative Binomial mixture log-likelihood).
2. `scipy.special.gammaln`, `scipy.special.logsumexp`, and `scipy.special.digamma` (evaluation of log-gamma functions and closed-form posterior geometric means).
3. `scipy.stats.gamma` (evaluation of cumulative distribution functions and inversion via Brent's root-finding for EB05 and EB95 quantiles).

Prior to Phase 3C.1, `scipy` was not installed in `.venv`.

---

## 2. Installation Details & Constraints

- **Package Installed:** `scipy==1.18.1` (wheel: `scipy-1.18.1-cp313-cp313-win_amd64.whl`)
- **Interpreter:** `<project-root>/.venv\Scripts\python.exe` (Python 3.13.14 x64 on Windows)
- **Installation Command:**
  ```powershell
  .\.venv\Scripts\python.exe -m pip install "scipy==1.18.1"
  ```
- **Requirements File Update:**
  Updated `requirements.txt` to include `scipy==1.18.1` with UTF-8 encoding.

---

## 3. Compatibility & Package Regression Audit

| Package | Pre-Installation Version | Post-Installation Version | Change Status | Compatibility Impact |
| :--- | :--- | :--- | :--- | :--- |
| **Python** | 3.13.14 | 3.13.14 | Unchanged | Fully supported |
| **scipy** | *None* | 1.18.1 | **NEW** | Added for optimization & special funcs |
| **numpy** | 2.5.3 | 2.5.3 | Unchanged | Requirement `numpy<2.8,>=2.0.0` satisfied |
| **pandas** | 3.0.6 | 3.0.6 | Unchanged | Zero regression |
| **pyreadr** | 0.5.7 | 0.5.7 | Unchanged | Zero regression |
| **requests** | 2.34.2 | 2.34.2 | Unchanged | Zero regression |
| **urllib3** | 2.8.0 | 2.8.0 | Unchanged | Zero regression |

---

## 4. Submodule Import Verification

All required submodules were verified via:
```python
import scipy, scipy.optimize, scipy.special, scipy.stats, numpy, pandas
```
- Exit code: `0`
- Status: **ALL IMPORTS VERIFIED.**
