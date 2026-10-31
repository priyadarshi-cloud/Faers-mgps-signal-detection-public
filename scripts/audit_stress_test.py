"""
Phase 3C.1A — Independent Scientific Audit Stress Test.

Stress-tests EBGM engine across:
1. Extreme expected counts (E in [1e-8, 1e5]).
2. Extreme observed counts (N in [0, 1e5]).
3. Extreme ratios (N/E up to 1e8).
4. Highly imbalanced frequency bins.
5. Log-likelihood precision of linear vs logarithmic binning.
6. Execution throughput profiling for scaling projection.
"""

from __future__ import annotations

import math
import sys
import os
import time

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import numpy as np
import scipy.stats as st

from src.signal_detection.ebgm_engine import EBGMEngine, MGPSHyperparameters

engine = EBGMEngine(seed=42)
theta = MGPSHyperparameters(alpha1=1.1367, beta1=0.4727, alpha2=0.4747, beta2=0.0055, w=0.7584)


def run_stress_tests():
    print("=" * 80)
    print("INDEPENDENT SCIENTIFIC AUDIT — STRESS TEST & NUMERICAL STABILITY")
    print("=" * 80)

    # 1. Extreme inputs test
    extreme_cases = [
        (0, 1e-6, "n=0, tiny E"),
        (0, 1000.0, "n=0, huge E"),
        (1, 1e-8, "n=1, ultra-tiny E"),
        (2, 0.000004, "n=2, real FAERS minimum E"),
        (1000, 0.01, "n=1000, small E (extreme disproportionality)"),
        (50000, 5000.0, "n=50000, large E (high-volume)"),
        (100000, 10.0, "n=100000, massive ratio (N/E = 10,000)"),
    ]

    all_finite = True
    for n_val, e_val, label in extreme_cases:
        n_arr = np.array([float(n_val)])
        e_arr = np.array([float(e_val)])

        qn = engine.calculate_posterior_weights(n_arr, e_arr, theta)
        ebgm = engine.calculate_ebgm(n_arr, e_arr, theta, q_n=qn)[0]
        quants = engine.calculate_posterior_quantiles(n_arr, e_arr, theta, quantiles=(0.05, 0.95), q_n=qn)
        eb05 = quants[0.05][0]
        eb95 = quants[0.95][0]

        is_valid = (
            np.isfinite(qn[0]) and 0.0 <= qn[0] <= 1.0 and
            np.isfinite(ebgm) and ebgm > 0.0 and
            np.isfinite(eb05) and np.isfinite(eb95) and
            0.0 < eb05 <= ebgm <= eb95
        )

        status = "PASS" if is_valid else "FAIL"
        print(f"  [{status}] {label:35s}: Qn={qn[0]:.4f}, EBGM={ebgm:10.2f}, EB05={eb05:10.2f}, EB95={eb95:10.2f}")
        if not is_valid:
            all_finite = False

    # 2. Exact vs Binned Log-Likelihood Precision on Pilot Dataset
    pilot_csv = os.path.join(PROJECT_ROOT, "data", "12_phase3c_pilot", "phase3c1_pilot_scored_pairs.csv")
    if os.path.exists(pilot_csv):
        import pandas as pd
        print("\nEvaluating Exact vs Binned Marginal Log-Likelihood on Pilot Dataset (M=25,000)...")
        df_pilot = pd.read_csv(pilot_csv)
        a_pilot = df_pilot["a"].to_numpy()
        e_pilot = df_pilot["e_expected"].to_numpy()

        # Exact unbinned
        t0 = time.time()
        nll_exact = engine.negative_log_likelihood(theta.to_tuple(), a_pilot, e_pilot)
        t_exact = time.time() - t0
        ll_exact = -nll_exact

        # Linear binning
        t0 = time.time()
        n_lin, e_lin, w_lin = engine.squash_counts_2d(a_pilot, e_pilot, decimals=2, use_log=False)
        t_lin_squash = time.time() - t0
        t0 = time.time()
        nll_lin = engine.negative_log_likelihood(theta.to_tuple(), n_lin, e_lin, weights=w_lin)
        t_lin_eval = time.time() - t0
        ll_lin = -nll_lin
        abs_lin = abs(ll_lin - ll_exact)
        rel_lin = (abs_lin / abs(ll_exact)) * 100.0

        # Logarithmic binning
        t0 = time.time()
        n_log, e_log, w_log = engine.squash_counts_2d(a_pilot, e_pilot, decimals=2, use_log=True)
        t_log_squash = time.time() - t0
        t0 = time.time()
        nll_log = engine.negative_log_likelihood(theta.to_tuple(), n_log, e_log, weights=w_log)
        t_log_eval = time.time() - t0
        ll_log = -nll_log
        abs_log = abs(ll_log - ll_exact)
        rel_log = (abs_log / abs(ll_exact)) * 100.0

        print(f"  Exact Unbinned (M={len(a_pilot):,}): LL = {ll_exact:.2f} (Eval time: {t_exact*1000:.2f} ms)")
        print(f"  Linear Binning: (Bins={len(n_lin):,}): LL = {ll_lin:.2f}, Abs Err = {abs_lin:.2f}, Rel Err = {rel_lin:.4f}% (Squash: {t_lin_squash*1000:.2f} ms)")
        print(f"  Logarithmic Binning: (Bins={len(n_log):,}): LL = {ll_log:.2f}, Abs Err = {abs_log:.2f}, Rel Err = {rel_log:.6f}% (Squash: {t_log_squash*1000:.2f} ms)")
        precision_gain = rel_lin / rel_log if rel_log > 0 else float("inf")
        print(f"  --> Logarithmic Binning achieves {precision_gain:,.0f}x lower error with {100.0*(1 - len(n_log)/len(n_lin)):.1f}% fewer bins.")

    # 3. Performance & Vectorization Throughput Test
    print("\nBenchmarking Posterior Quantile Scoring Throughput...")
    n_bench = 5000
    n_vec = np.random.randint(2, 20, size=n_bench).astype(float)
    e_vec = np.random.uniform(0.01, 10.0, size=n_bench)

    t0 = time.time()
    qn_vec = engine.calculate_posterior_weights(n_vec, e_vec, theta)
    ebgm_vec = engine.calculate_ebgm(n_vec, e_vec, theta, q_n=qn_vec)
    t_closed = time.time() - t0

    t1 = time.time()
    quants_vec = engine.calculate_posterior_quantiles(n_vec, e_vec, theta, quantiles=(0.05, 0.95), q_n=qn_vec)
    t_roots = time.time() - t1

    print(f"  Closed-form EBGM (5,000 pairs): {t_closed*1000:.2f} ms ({n_bench/t_closed:,.0f} pairs/sec)")
    print(f"  Brent root EB05/EB95 (5,000 pairs): {t_roots:.2f} s ({n_bench/t_roots:,.0f} pairs/sec)")
    projected_full_quantiles_min = (1167891 / (n_bench / t_roots)) / 60.0
    print(f"  Projected runtime for full 1.16M pair quantiles (single-threaded): {projected_full_quantiles_min:.1f} minutes")

    print("=" * 80)
    print("STRESS TEST COMPLETED")


if __name__ == "__main__":
    run_stress_tests()
