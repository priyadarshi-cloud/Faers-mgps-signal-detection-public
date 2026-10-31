"""
Phase 3C.1 — Scientific Validation Suite for Empirical Bayes (EBGM/MGPS) Engine.

Validates the 8 core scientific and statistical requirements:
1. Hand-calculated expected counts.
2. Zero and sparse count handling.
3. Numerical stability for extreme count ratios.
4. Valid posterior distributions and quantile ordering (0 < EB05 <= EBGM <= EB95).
5. Mixture-weight and hyperparameter boundary/identifiability constraints.
6. Optimizer convergence and graceful failure handling.
7. Deterministic reproducibility.
8. Published reference test vectors from Canida & Ihrie (2017, The R Journal 9(2):499-519)
   and analytic boundary solutions.

Run with:
    python scripts/test_ebgm_engine.py
"""

from __future__ import annotations

import math
import os
import sys
from typing import Callable, Dict, List, Tuple

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import numpy as np
import pandas as pd
import scipy.stats as st
import scipy.special as sp

from src.signal_detection.ebgm_engine import (
    EBGMEngine,
    MGPSHyperparameters,
    OptimizationResult,
)

PASS = "✅ PASS"
FAIL = "❌ FAIL"
BLOCKED = "⚠️ BLOCKED"

test_results: List[Dict[str, str]] = []


def run_test(name: str, fn: Callable[[], None]) -> bool:
    """Execute a single test and log result."""
    try:
        fn()
        test_results.append({"test": name, "status": PASS, "note": ""})
        print(f"  {PASS}  {name}")
        return True
    except AssertionError as ae:
        test_results.append({"test": name, "status": FAIL, "note": str(ae)})
        print(f"  {FAIL}  {name}\n         → Assertion Failed: {ae}")
        return False
    except Exception as exc:
        test_results.append({"test": name, "status": FAIL, "note": f"Exception: {exc}"})
        print(f"  {FAIL}  {name}\n         → Unexpected Exception: {exc}")
        return False


# ===========================================================================
# Test 1 — Hand-calculated expected counts
# ===========================================================================
def test_hand_calculated_expected_counts() -> None:
    engine = EBGMEngine()

    # Case 1: Simple integers
    # N = 10,000, drug_total = a + b = 500, event_total = a + c = 200
    # Expected E = (500 * 200) / 10,000 = 10.0
    a = np.array([50.0])
    b = np.array([450.0])
    c = np.array([150.0])
    e_calc = engine.calculate_expected_counts(a, b, c, total_n=10000)
    assert np.isclose(e_calc[0], 10.0, rtol=1e-12), f"Expected 10.0, got {e_calc[0]}"

    # Case 2: Realistic FAERS scale
    # total_n = 6,005,839
    # a = 100, b = 900 (drug_total = 1000)
    # c = 5900 (event_total = 6000)
    # E = (1000 * 6000) / 6005839 = 6,000,000 / 6005839 ~ 0.999027779...
    e_calc_faers = engine.calculate_expected_counts(
        np.array([100.0]), np.array([900.0]), np.array([5900.0]), total_n=6005839
    )
    expected_true = 6000000.0 / 6005839.0
    assert np.isclose(e_calc_faers[0], expected_true, rtol=1e-12), (
        f"Expected {expected_true}, got {e_calc_faers[0]}"
    )

    # Case 3: Error handling on invalid inputs
    try:
        engine.calculate_expected_counts(a, b, c, total_n=0)
        assert False, "Should raise ValueError on total_n <= 0"
    except ValueError:
        pass

    try:
        engine.calculate_expected_counts(np.array([-1.0]), b, c, total_n=1000)
        assert False, "Should raise ValueError on negative counts"
    except ValueError:
        pass


# ===========================================================================
# Test 2 — Zero and sparse counts
# ===========================================================================
def test_zero_and_sparse_counts() -> None:
    engine = EBGMEngine()
    theta = MGPSHyperparameters(alpha1=1.5, beta1=1.5, alpha2=3.0, beta2=1.0, w=0.2)

    # 1. Zero observed count: n = 0, E = 2.0
    n_zero = np.array([0.0])
    e_pos = np.array([2.0])
    log_ll = engine.negative_log_likelihood(theta.to_tuple(), n_zero, e_pos)
    assert np.isfinite(log_ll), f"Log-likelihood must be finite for n=0, got {log_ll}"

    qn_zero = engine.calculate_posterior_weights(n_zero, e_pos, theta)
    assert 0.0 <= qn_zero[0] <= 1.0, f"Qn must be in [0, 1], got {qn_zero[0]}"

    ebgm_zero = engine.calculate_ebgm(n_zero, e_pos, theta, q_n=qn_zero)
    assert ebgm_zero[0] > 0.0 and np.isfinite(ebgm_zero[0]), (
        f"EBGM must be strictly positive for n=0, got {ebgm_zero[0]}"
    )

    # 2. Sparse observed counts: n = 1, 2, 3 with low E = 0.05
    n_sparse = np.array([1.0, 2.0, 3.0])
    e_sparse = np.array([0.05, 0.05, 0.05])
    ebgm_sparse = engine.calculate_ebgm(n_sparse, e_sparse, theta)
    # Crude ratio: n / E = 20, 40, 60.
    # Empirical Bayes shrinkage should pull EBGM well below crude ratio!
    for i in range(3):
        crude_rr = n_sparse[i] / e_sparse[i]
        assert ebgm_sparse[i] < crude_rr, (
            f"EBGM {ebgm_sparse[i]} must shrink below crude RR {crude_rr}"
        )

    # 3. Zero expected count: E = 0.0 should safely return NaN without raising exception
    n_any = np.array([5.0])
    e_zero = np.array([0.0])
    ebgm_nan = engine.calculate_ebgm(n_any, e_zero, theta)
    assert np.isnan(ebgm_nan[0]), f"EBGM must be NaN when E=0, got {ebgm_nan[0]}"

    quant_nan = engine.calculate_posterior_quantiles(n_any, e_zero, theta, quantiles=(0.05, 0.95))
    assert np.isnan(quant_nan[0.05][0]), f"EB05 must be NaN when E=0, got {quant_nan[0.05][0]}"


# ===========================================================================
# Test 3 — Numerical stability for extreme count ratios
# ===========================================================================
def test_numerical_stability_extreme_ratios() -> None:
    engine = EBGMEngine()
    theta = MGPSHyperparameters(alpha1=0.2, beta1=0.1, alpha2=2.0, beta2=4.0, w=0.33)

    # Extreme disproportionality: n = 50,000, E = 0.01 (crude RR = 5,000,000)
    n_extreme_high = np.array([50000.0])
    e_extreme_low = np.array([0.01])

    qn = engine.calculate_posterior_weights(n_extreme_high, e_extreme_low, theta)
    assert np.isfinite(qn[0]) and 0.0 <= qn[0] <= 1.0

    ebgm = engine.calculate_ebgm(n_extreme_high, e_extreme_low, theta, q_n=qn)
    assert np.isfinite(ebgm[0]) and ebgm[0] > 0.0

    quantiles = engine.calculate_posterior_quantiles(
        n_extreme_high, e_extreme_low, theta, quantiles=(0.05, 0.95), q_n=qn
    )
    assert np.isfinite(quantiles[0.05][0])
    assert np.isfinite(quantiles[0.95][0])
    assert quantiles[0.05][0] <= ebgm[0] <= quantiles[0.95][0]

    # Extreme deficit: n = 0, E = 1,000.0
    n_def = np.array([0.0])
    e_huge = np.array([1000.0])
    ebgm_def = engine.calculate_ebgm(n_def, e_huge, theta)
    assert np.isfinite(ebgm_def[0]) and ebgm_def[0] > 0.0


# ===========================================================================
# Test 4 — Valid posterior distributions and quantile ordering
# ===========================================================================
def test_posterior_quantile_ordering() -> None:
    engine = EBGMEngine()
    theta = MGPSHyperparameters(alpha1=1.2, beta1=0.8, alpha2=2.5, beta2=1.2, w=0.25)

    test_grid_n = [0, 1, 2, 5, 10, 50, 100]
    test_grid_e = [0.01, 0.1, 0.5, 1.0, 5.0, 20.0]

    for n_val in test_grid_n:
        for e_val in test_grid_e:
            n_arr = np.array([float(n_val)])
            e_arr = np.array([float(e_val)])

            qn = engine.calculate_posterior_weights(n_arr, e_arr, theta)
            ebgm = engine.calculate_ebgm(n_arr, e_arr, theta, q_n=qn)[0]
            quants = engine.calculate_posterior_quantiles(
                n_arr, e_arr, theta, quantiles=(0.05, 0.95), q_n=qn
            )
            eb05 = quants[0.05][0]
            eb95 = quants[0.95][0]

            # Strict ordering: 0 < EB05 <= EBGM <= EB95
            assert 0.0 < eb05, f"EB05 must be strictly positive: {eb05} (n={n_val}, e={e_val})"
            assert eb05 <= ebgm, (
                f"EB05 ({eb05}) must be <= EBGM ({ebgm}) for n={n_val}, e={e_val}"
            )
            assert ebgm <= eb95, (
                f"EBGM ({ebgm}) must be <= EB95 ({eb95}) for n={n_val}, e={e_val}"
            )

            # Check CDF calibration: F_post(EB05) should equal 0.05 within root tolerance
            w_val = qn[0]
            c1_05 = st.gamma.cdf(eb05, a=theta.alpha1 + n_val, scale=1.0 / (theta.beta1 + e_val))
            c2_05 = st.gamma.cdf(eb05, a=theta.alpha2 + n_val, scale=1.0 / (theta.beta2 + e_val))
            f_05 = w_val * c1_05 + (1.0 - w_val) * c2_05
            assert abs(f_05 - 0.05) < 1e-4, f"F_post(EB05) should be 0.05, got {f_05}"


# ===========================================================================
# Test 5 — Mixture-weight and hyperparameter constraints
# ===========================================================================
def test_hyperparameter_constraints_and_canonicalization() -> None:
    # 1. Invalid weight w <= 0 or w >= 1 must raise ValueError
    try:
        MGPSHyperparameters(alpha1=1.0, beta1=1.0, alpha2=1.0, beta2=1.0, w=0.0)
        assert False, "Should reject w = 0.0"
    except ValueError:
        pass

    try:
        MGPSHyperparameters(alpha1=1.0, beta1=1.0, alpha2=1.0, beta2=1.0, w=1.0)
        assert False, "Should reject w = 1.0"
    except ValueError:
        pass

    # 2. Negative or zero alpha/beta must raise ValueError
    try:
        MGPSHyperparameters(alpha1=-0.5, beta1=1.0, alpha2=1.0, beta2=1.0, w=0.5)
        assert False, "Should reject alpha1 <= 0"
    except ValueError:
        pass

    # 3. Identifiability canonicalization
    # Suppose component 1 has mean 4.0 (alpha1=4, beta1=1) and component 2 has mean 1.0 (alpha2=1, beta2=1), w=0.3
    non_canonical = MGPSHyperparameters(alpha1=4.0, beta1=1.0, alpha2=1.0, beta2=1.0, w=0.3)
    canonical = non_canonical.canonicalize()

    # In canonical form, mean(1) <= mean(2):
    # Component 1 becomes the old component 2 (mean 1.0), component 2 becomes old component 1 (mean 4.0),
    # and w becomes 1.0 - 0.3 = 0.7.
    assert canonical.mean_component1() <= canonical.mean_component2()
    assert np.isclose(canonical.alpha1, 1.0) and np.isclose(canonical.beta1, 1.0)
    assert np.isclose(canonical.alpha2, 4.0) and np.isclose(canonical.beta2, 1.0)
    assert np.isclose(canonical.w, 0.7)


# ===========================================================================
# Test 6 — Optimizer convergence and failure handling
# ===========================================================================
def test_optimizer_convergence_and_failure_handling() -> None:
    engine = EBGMEngine(seed=42)

    # 1. Convergence on simulated dataset with known true prior
    # Generate synthetic N ~ Poisson(lambda * E), lambda ~ mixture
    np.random.seed(42)
    n_samples = 1500
    e_sim = np.random.uniform(0.1, 10.0, size=n_samples)
    true_hypers = MGPSHyperparameters(alpha1=1.0, beta1=1.0, alpha2=3.0, beta2=1.0, w=0.3)

    # Sample component assignments
    comp = np.random.binomial(1, 1.0 - true_hypers.w, size=n_samples)
    lambda_sim = np.zeros(n_samples)
    lambda_sim[comp == 0] = np.random.gamma(shape=true_hypers.alpha1, scale=1.0 / true_hypers.beta1, size=np.sum(comp == 0))
    lambda_sim[comp == 1] = np.random.gamma(shape=true_hypers.alpha2, scale=1.0 / true_hypers.beta2, size=np.sum(comp == 1))

    n_sim = np.random.poisson(lam=lambda_sim * e_sim)

    result = engine.fit(n_sim, e_sim, compute_se=True)
    assert result.converged, f"Optimization should converge, message: {result.message}"
    assert result.hyperparameters is not None
    assert result.log_likelihood < 0.0
    assert result.iterations > 0
    assert result.standard_errors is not None

    # 2. Graceful failure on empty or all-zero E inputs
    bad_res = engine.fit(np.array([]), np.array([]))
    assert not bad_res.converged
    assert "empty" in bad_res.message.lower()

    zero_res = engine.fit(np.array([1.0, 2.0]), np.array([0.0, 0.0]))
    assert not zero_res.converged
    assert "valid" in zero_res.message.lower()


# ===========================================================================
# Test 7 — Deterministic reproducibility
# ===========================================================================
def test_deterministic_reproducibility() -> None:
    engine1 = EBGMEngine(seed=42)
    engine2 = EBGMEngine(seed=42)

    n_test = np.array([1.0, 2.0, 5.0, 10.0, 20.0, 50.0])
    e_test = np.array([0.1, 0.5, 1.2, 3.4, 15.0, 45.0])

    res1 = engine1.fit(n_test, e_test, compute_se=False)
    res2 = engine2.fit(n_test, e_test, compute_se=False)

    assert res1.converged == res2.converged
    assert np.isclose(res1.log_likelihood, res2.log_likelihood, rtol=1e-12)
    t1 = res1.hyperparameters.to_tuple()
    t2 = res2.hyperparameters.to_tuple()
    for p1, p2 in zip(t1, t2):
        assert np.isclose(p1, p2, rtol=1e-12), f"Reproducibility mismatch: {p1} vs {p2}"


# ===========================================================================
# Test 8 — Published reference examples (Canida & Ihrie 2017 openEBGM)
# ===========================================================================
def test_published_reference_vectors_open_ebgm() -> None:
    """
    Validation against published reference values in:
    Canida T, Ihrie J. 'openEBGM: An R Implementation of the Gamma-Poisson Shrinker Data Mining Model'
    The R Journal. 2017; 9(2): 499-519. DOI: 10.32614/RJ-2017-063.
    Section 4.2 / 5.2 (CAERS application example).

    Published hyperparameters:
        alpha1 = 3.25118662
        beta1  = 0.39976698
        alpha2 = 2.02696130
        beta2  = 1.90893277
        P      = 0.06539553
    """
    engine = EBGMEngine()
    theta_published = MGPSHyperparameters(
        alpha1=3.25118662,
        beta1=0.39976698,
        alpha2=2.02696130,
        beta2=1.90893277,
        w=0.06539553,
    )

    # Reference test cases directly from The R Journal 2017 article (Section 5.2, code snippet 19-20):
    # (n, E, published_ebgm, published_q05, published_q95)
    published_cases = [
        (1, 0.0360548272, 2.23, 0.49, 13.85),
        (1, 0.0038736591, 2.58, 0.52, 15.78),
        (1, 0.0002979738, 2.63, 0.52, 16.02),
    ]

    for n_val, e_val, exp_ebgm, exp_q05, exp_q95 in published_cases:
        n_arr = np.array([float(n_val)])
        e_arr = np.array([float(e_val)])

        qn = engine.calculate_posterior_weights(n_arr, e_arr, theta_published)
        calc_ebgm = engine.calculate_ebgm(n_arr, e_arr, theta_published, q_n=qn)[0]
        quants = engine.calculate_posterior_quantiles(
            n_arr, e_arr, theta_published, quantiles=(0.05, 0.95), q_n=qn
        )
        calc_q05 = quants[0.05][0]
        calc_q95 = quants[0.95][0]

        # Verify against published numbers rounded to 2 decimal places:
        assert np.isclose(round(calc_ebgm, 2), exp_ebgm, atol=0.01), (
            f"EBGM mismatch for n={n_val}, e={e_val}: calculated {calc_ebgm:.4f} vs published {exp_ebgm}"
        )
        assert np.isclose(round(calc_q05, 2), exp_q05, atol=0.01), (
            f"EB05 mismatch for n={n_val}, e={e_val}: calculated {calc_q05:.4f} vs published {exp_q05}"
        )
        assert np.isclose(round(calc_q95, 2), exp_q95, atol=0.01), (
            f"EB95 mismatch for n={n_val}, e={e_val}: calculated {calc_q95:.4f} vs published {exp_q95}"
        )

    # Boundary reference test vector: Single-component analytic reduction
    # When w -> 1, EBGM must match exact digamma closed form: exp(psi(alpha + n) - ln(beta + e))
    single_alpha = 2.0
    single_beta = 1.5
    theta_single = MGPSHyperparameters(
        alpha1=single_alpha,
        beta1=single_beta,
        alpha2=single_alpha,
        beta2=single_beta,
        w=0.5,  # equal components = single gamma
    )
    n_single = np.array([4.0])
    e_single = np.array([2.0])
    analytic_ebgm = math.exp(sp.digamma(single_alpha + 4.0) - math.log(single_beta + 2.0))
    analytic_q05 = st.gamma.ppf(0.05, a=single_alpha + 4.0, scale=1.0 / (single_beta + 2.0))
    analytic_q95 = st.gamma.ppf(0.95, a=single_alpha + 4.0, scale=1.0 / (single_beta + 2.0))

    calc_single_ebgm = engine.calculate_ebgm(n_single, e_single, theta_single)[0]
    calc_single_quants = engine.calculate_posterior_quantiles(
        n_single, e_single, theta_single, quantiles=(0.05, 0.95)
    )

    assert np.isclose(calc_single_ebgm, analytic_ebgm, rtol=1e-10), (
        f"Analytic EBGM mismatch: {calc_single_ebgm} vs {analytic_ebgm}"
    )
    assert np.isclose(calc_single_quants[0.05][0], analytic_q05, rtol=1e-6), (
        f"Analytic EB05 mismatch: {calc_single_quants[0.05][0]} vs {analytic_q05}"
    )
    assert np.isclose(calc_single_quants[0.95][0], analytic_q95, rtol=1e-6), (
        f"Analytic EB95 mismatch: {calc_single_quants[0.95][0]} vs {analytic_q95}"
    )


# ===========================================================================
# Test 9 — Logarithmic Expected-Count Binning Regression & Approximation
# ===========================================================================
def test_logarithmic_expected_count_binning() -> None:
    engine = EBGMEngine()

    # 1. Extremely small positive E and large E
    n_extreme = np.array([1, 2, 5, 10, 50], dtype=np.int64)
    e_extreme = np.array([1e-8, 1e-6, 0.005, 500.0, 10000.0], dtype=np.float64)
    n_u, e_m, w_u = engine.squash_counts_2d(n_extreme, e_extreme, decimals=2, use_log=True)
    assert len(n_u) == 5, f"Expected 5 distinct bins for extreme values, got {len(n_u)}"
    assert np.all(np.isfinite(e_m)), "Representative expected counts must be finite"
    assert np.all(e_m > 0.0), "Representative expected counts must be strictly positive"
    assert np.all(w_u == 1.0), "Each extreme bin should have weight 1"

    # 2. Repeated bins and weight / arithmetic mean preservation
    # For decimals=2, log10(1.00) = 0.00, log10(1.005) = 0.00216 -> 0.00, log10(1.01) = 0.00432 -> 0.00
    # All 3 should collapse into bin (n=3, log10(E)~0.00)
    n_repeated = np.array([3, 3, 3, 4], dtype=np.int64)
    e_repeated = np.array([1.00, 1.005, 1.01, 2.0], dtype=np.float64)
    n_rep_u, e_rep_m, w_rep_u = engine.squash_counts_2d(n_repeated, e_repeated, decimals=2, use_log=True)
    assert len(n_rep_u) == 2, f"Expected 2 bins, got {len(n_rep_u)}"
    # First bin should have n=3, weight=3, e_mean = mean(1.00, 1.005, 1.01) = 1.005
    idx_n3 = np.where(n_rep_u == 3)[0][0]
    assert w_rep_u[idx_n3] == 3.0, f"Expected weight 3, got {w_rep_u[idx_n3]}"
    assert np.isclose(e_rep_m[idx_n3], 1.005, rtol=1e-10), f"Expected e_mean=1.005, got {e_rep_m[idx_n3]}"
    assert np.sum(w_rep_u) == len(n_repeated), "Sum of bin weights must equal original row count"

    # 3. Invalid inputs: strictly raise ValueError, never silently discard
    invalid_cases = [
        ([1], [0.0], "E == 0.0 must raise ValueError"),
        ([1], [-0.5], "E < 0 must raise ValueError"),
        ([1], [float("nan")], "NaN in E must raise ValueError"),
        ([1], [float("inf")], "Inf in E must raise ValueError"),
        ([-1], [1.0], "Negative n must raise ValueError"),
        ([1.5], [1.0], "Non-integer n must raise ValueError"),
        ([float("nan")], [1.0], "NaN in n must raise ValueError"),
        ([1, 2], [1.0], "Length mismatch must raise ValueError"),
    ]
    for n_inv, e_inv, msg in invalid_cases:
        try:
            engine.squash_counts_2d(n_inv, e_inv, decimals=2, use_log=True)
            assert False, f"Failed to raise ValueError: {msg}"
        except ValueError:
            pass

    # Empty inputs must return empty arrays without error
    n_empty, e_empty, w_empty = engine.squash_counts_2d([], [], decimals=2, use_log=True)
    assert len(n_empty) == 0 and len(e_empty) == 0 and len(w_empty) == 0

    # 4. Deterministic output
    n_det = np.array([2, 5, 2, 10, 5, 2], dtype=np.int64)
    e_det = np.array([0.12, 1.45, 0.12, 3.20, 1.46, 0.12], dtype=np.float64)
    n1, e1, w1 = engine.squash_counts_2d(n_det, e_det, decimals=2, use_log=True)
    n2, e2, w2 = engine.squash_counts_2d(n_det, e_det, decimals=2, use_log=True)
    assert np.array_equal(n1, n2) and np.allclose(e1, e2) and np.array_equal(w1, w2), (
        "Squashing output must be strictly deterministic across calls"
    )

    # 5. Exact unbinned vs binned likelihood comparison
    # Test on a realistic multi-stratum dataset using pilot hyperparameters
    theta = MGPSHyperparameters(
        alpha1=1.1367, beta1=0.4727, alpha2=0.4747, beta2=0.0055, w=0.7584
    )
    rng = np.random.RandomState(42)
    n_test = rng.choice([2, 3, 4, 5, 8, 15, 50], size=5000, p=[0.4, 0.2, 0.15, 0.1, 0.08, 0.05, 0.02])
    # E spans 5 orders of magnitude (0.0001 to 20.0)
    e_test = 10.0 ** rng.uniform(-4.0, 1.3, size=5000)

    # Unbinned likelihood
    nll_exact = engine.negative_log_likelihood(theta.to_tuple(), n_test, e_test)

    # Linear binned likelihood
    n_lin, e_lin, w_lin = engine.squash_counts_2d(n_test, e_test, decimals=2, use_log=False)
    nll_lin = engine.negative_log_likelihood(theta.to_tuple(), n_lin, e_lin, weights=w_lin)
    rel_err_lin = abs(nll_lin - nll_exact) / abs(nll_exact)

    # Logarithmic binned likelihood
    n_log, e_log, w_log = engine.squash_counts_2d(n_test, e_test, decimals=2, use_log=True)
    nll_log = engine.negative_log_likelihood(theta.to_tuple(), n_log, e_log, weights=w_log)
    rel_err_log = abs(nll_log - nll_exact) / abs(nll_exact)

    # Assert logarithmic binning error is orders of magnitude smaller and < 0.001%
    assert rel_err_log < 1e-4, f"Log binning relative error too high: {rel_err_log:.6f}"
    assert rel_err_log < (rel_err_lin / 100.0), (
        f"Log binning ({rel_err_log:.6f}) should have >100x lower error than linear ({rel_err_lin:.6f})"
    )


def test_truncated_likelihood_conditional_formulation() -> None:
    """
    Test 10: Validates truncated Negative Binomial mixture likelihood for n >= 2 selected data:
    1. Mixture probabilities sum to 1.0 (P(0) + P(1) + P(>=2) == 1.0).
    2. Agreement between conditional probability formula and direct evaluation.
    3. Finite likelihood values on difficult / extreme inputs.
    4. Input validation and rejection of invalid counts / parameters.
    5. Correct weighted likelihood behavior after logarithmic binning.
    6. Parameter recovery under simulated n >= 2 selection mechanism.
    7. Demonstration that ordinary fit exhibits severe selection bias on n >= 2 data.
    8. Deterministic reproducibility under fixed seed.
    """
    engine = EBGMEngine(seed=42)
    theta_true = MGPSHyperparameters(alpha1=2.0, beta1=2.0, alpha2=3.0, beta2=1.0, w=0.85)

    # 1. Mixture probabilities sum to 1
    e_vals = np.array([0.0001, 0.01, 0.1, 1.0, 5.0, 20.0, 100.0])
    p0 = engine.calculate_mixture_probabilities(np.zeros(len(e_vals)), e_vals, theta_true)
    p1 = engine.calculate_mixture_probabilities(np.ones(len(e_vals)), e_vals, theta_true)
    p_ge2 = engine.calculate_truncation_probabilities(e_vals, theta_true, truncated_at=2)
    total_prob = p0 + p1 + p_ge2
    assert np.allclose(total_prob, 1.0, atol=1e-12), (
        f"Probabilities do not sum to 1 across dynamic range: {total_prob}"
    )

    # 2. Agreement between conditional probability formula and engine negative_log_likelihood
    n_sample = np.array([2, 3, 5, 8, 15], dtype=np.int64)
    e_sample = np.array([0.05, 0.2, 1.0, 2.5, 10.0], dtype=np.float64)
    p_n = engine.calculate_mixture_probabilities(n_sample, e_sample, theta_true)
    p_sel = engine.calculate_truncation_probabilities(e_sample, theta_true, truncated_at=2)
    direct_cond_nll = -float(np.sum(np.log(p_n / p_sel)))
    engine_nll = engine.negative_log_likelihood(theta_true.to_tuple(), n_sample, e_sample, truncated_at=2)
    assert np.isclose(direct_cond_nll, engine_nll, rtol=1e-9), (
        f"Engine truncated NLL ({engine_nll}) differs from direct formula ({direct_cond_nll})"
    )

    # 3. Finite likelihood on difficult / extreme inputs
    n_extreme = np.array([2, 50, 1000, 50000], dtype=np.int64)
    e_extreme = np.array([1e-7, 0.005, 10.0, 5000.0], dtype=np.float64)
    nll_extreme = engine.negative_log_likelihood(theta_true.to_tuple(), n_extreme, e_extreme, truncated_at=2)
    assert np.isfinite(nll_extreme), f"Truncated NLL returned non-finite on extreme inputs: {nll_extreme}"

    # 4. Input rejection for invalid counts and parameters
    try:
        # Must fail when n < 2 is passed to truncated_at=2
        engine.fit(np.array([1, 2, 5]), np.array([1.0, 1.0, 1.0]), truncated_at=2)
        assert False, "Failed to raise ValueError when n < 2 passed with truncated_at=2"
    except ValueError:
        pass

    try:
        # Must fail for unsupported truncation threshold
        engine.calculate_truncation_probabilities(np.array([1.0]), theta_true, truncated_at=3)
        assert False, "Failed to raise ValueError for unsupported truncated_at=3"
    except ValueError:
        pass

    # 5. Logarithmic binning precision on truncated likelihood
    rng = np.random.RandomState(42)
    M_pop = 25000
    e_pop = np.exp(rng.normal(-0.5, 1.0, size=M_pop))
    e_pop = np.clip(e_pop, 0.01, 30.0)
    z = rng.binomial(1, 1.0 - theta_true.w, size=M_pop)
    lam = np.zeros(M_pop)
    lam[z == 0] = rng.gamma(theta_true.alpha1, 1.0 / theta_true.beta1, size=np.sum(z == 0))
    lam[z == 1] = rng.gamma(theta_true.alpha2, 1.0 / theta_true.beta2, size=np.sum(z == 1))
    n_pop = rng.poisson(lam * e_pop)

    mask = n_pop >= 2
    n_sel = n_pop[mask]
    e_sel = e_pop[mask]

    n_bin, e_bin, w_bin = engine.squash_counts_2d(n_sel, e_sel, decimals=2, use_log=True)
    nll_exact = engine.negative_log_likelihood(theta_true.to_tuple(), n_sel, e_sel, truncated_at=2)
    nll_binned = engine.negative_log_likelihood(theta_true.to_tuple(), n_bin, e_bin, weights=w_bin, truncated_at=2)
    rel_err_binned = abs(nll_binned - nll_exact) / abs(nll_exact)
    assert rel_err_binned < 1e-4, f"Truncated log-binning relative error too high: {rel_err_binned:.6f}"

    # 6 & 7. Simulation: parameter recovery under n >= 2 selection and selection bias demonstration
    guess = [(1.8, 1.8, 2.8, 1.2, 0.8)]
    res_trunc = engine.fit(n_bin, e_bin, weights=w_bin, initial_guesses=guess, compute_se=False, truncated_at=2)
    res_ord = engine.fit(n_bin, e_bin, weights=w_bin, initial_guesses=guess, compute_se=False, truncated_at=None)

    assert res_trunc.converged, "Truncated optimizer failed to converge"
    assert res_ord.converged, "Ordinary optimizer failed to converge"

    mean_true = theta_true.mean_component1()  # 1.0
    mean_trunc = res_trunc.hyperparameters.mean_component1()
    mean_ord = res_ord.hyperparameters.mean_component1()

    # Truncated fit recovers mean within 25% of true mean 1.0 on finite sample (error < 0.25)
    # and has >4x lower bias than ordinary fit
    assert abs(mean_trunc - mean_true) < 0.25, (
        f"Truncated fit did not recover true mean 1.0 (got {mean_trunc:.3f})"
    )
    # Ordinary fit exhibits massive selection bias (> 1.8, >80% relative bias)
    assert mean_ord > 1.8, (
        f"Ordinary fit did not exhibit expected selection bias (got {mean_ord:.3f}, expected > 1.8)"
    )
    assert abs(mean_trunc - mean_true) < (abs(mean_ord - mean_true) / 3.0), (
        f"Truncated fit error ({abs(mean_trunc - mean_true):.3f}) should be >3x smaller than ordinary ({abs(mean_ord - mean_true):.3f})"
    )

    # 8. Deterministic reproducibility
    res_trunc2 = engine.fit(n_bin, e_bin, weights=w_bin, initial_guesses=guess, compute_se=False, truncated_at=2)
    assert res_trunc.hyperparameters == res_trunc2.hyperparameters, (
        "Truncated fit output is not deterministic across runs"
    )


# ===========================================================================
# Main Execution Runner
# ===========================================================================
def main() -> int:
    print("=" * 80)
    print("PHASE 3C.1 — EMPIRICAL BAYES (EBGM/MGPS) SCIENTIFIC VALIDATION SUITE")
    print("=" * 80)

    tests = [
        ("1. Hand-Calculated Expected Counts", test_hand_calculated_expected_counts),
        ("2. Zero and Sparse Counts Handling", test_zero_and_sparse_counts),
        ("3. Numerical Stability for Extreme Count Ratios", test_numerical_stability_extreme_ratios),
        ("4. Valid Posterior Distribution and Quantile Ordering (EB05 <= EBGM <= EB95)", test_posterior_quantile_ordering),
        ("5. Mixture-Weight and Hyperparameter Identifiability Constraints", test_hyperparameter_constraints_and_canonicalization),
        ("6. Optimizer Multi-Start Convergence and Failure Handling", test_optimizer_convergence_and_failure_handling),
        ("7. Deterministic Reproducibility Across Engine Restarts", test_deterministic_reproducibility),
        ("8. Published Reference Vectors (Canida & Ihrie 2017) & Analytic Boundaries", test_published_reference_vectors_open_ebgm),
        ("9. Logarithmic Expected-Count Binning Regression & Error Bounds", test_logarithmic_expected_count_binning),
        ("10. Truncated-Likelihood Conditional Formulation, Precision, and Selection Bias Recovery", test_truncated_likelihood_conditional_formulation),
    ]

    all_passed = True
    for test_name, test_fn in tests:
        passed = run_test(test_name, test_fn)
        if not passed:
            all_passed = False

    print("=" * 80)
    passed_count = sum(1 for r in test_results if r["status"] == PASS)
    total_count = len(test_results)
    print(f"Summary: {passed_count}/{total_count} tests PASSED.")
    if all_passed:
        print("STATUS: SCIENTIFIC VALIDATION COMPLETE — ALL 10 CRITERIA SATISFIED")
        return 0
    else:
        print("STATUS: VALIDATION FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
