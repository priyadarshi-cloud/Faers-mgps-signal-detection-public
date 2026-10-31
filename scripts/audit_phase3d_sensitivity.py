"""
Phase 3D.1 Independent Audit: Reproduce and analyze hyperparameter sensitivity.
Investigates the cause of identical sensitivity likelihoods and reproduces multi-start fits.
"""

import json
import os
import sys
import time
import numpy as np
import pandas as pd
import scipy.optimize as opt
import scipy.stats as st

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.signal_detection.ebgm_engine import EBGMEngine, MGPSHyperparameters

CANDIDATE_SUMMARY_CSV = os.path.join(PROJECT_ROOT, "data", "10_phase3b_features", "candidate_pairs_summary.csv")
FIT_CHECKPOINT_FILE = os.path.join(PROJECT_ROOT, "data", "13_phase3c2_mgps_scoring", "fit_checkpoint.json")
TOTAL_COHORT_N = 6005839

def main():
    print("=" * 80)
    print("PHASE 3D.1 AUDIT: HYPERPARAMETER SENSITIVITY INCONSISTENCY INVESTIGATION")
    print("=" * 80)

    with open(FIT_CHECKPOINT_FILE, "r", encoding="utf-8") as f:
        primary_ckpt = json.load(f)

    print("\n1. Primary Fit Restarts in Phase 3C.2:")
    for i, r in enumerate(primary_ckpt["all_restarts"]):
        print(f"   Start {i+1}: Start Vector = {r['start']}")
        print(f"            Negative Log-Likelihood (fun) = {r['fun']:.4f}")
        print(f"            Fitted Params = {r['params']}")
        print(f"            Iterations = {r['nit']}, Success = {r['success']}")

    # Load data and squash to bins
    print("\n2. Loading data and squashing to 2D logarithmic bins...")
    df = pd.read_csv(CANDIDATE_SUMMARY_CSV)
    a = df["a"].to_numpy(dtype=np.float64)
    b = df["b"].to_numpy(dtype=np.float64)
    c = df["c"].to_numpy(dtype=np.float64)
    e = (a + b) * (a + c) / float(TOTAL_COHORT_N)

    engine = EBGMEngine(seed=42)
    n_bin, e_bin, w_bin = engine.squash_counts_2d(a, e, decimals=2, use_log=True)
    print(f"   Bins created: {len(n_bin):,}")

    # Primary fitted parameters:
    # In Phase 3C.2: alpha1=0.001, beta1=0.006809, alpha2=0.285887, beta2=0.400371, w=0.849904
    primary_vector = (0.28588672696109757, 0.40037082921853445, 0.001, 0.006808950259983445, 0.15009584536479362)
    # Note: in parameter space, (alpha1, beta1, alpha2, beta2, w)
    val_prim = engine.negative_log_likelihood(primary_vector, n_bin, e_bin, w_bin, truncated_at=2)
    print(f"\n3. Evaluating primary solution on squashed bins:")
    print(f"   Vector: {primary_vector}")
    print(f"   Negative Log-Likelihood: {val_prim:.4f} (Matches primary: {abs(val_prim - 3372348.3387) < 0.01})")

    # Evaluate the Phase 3D single-start sensitivity optimization
    single_start_guess = (0.2339, 0.3354, 2.2487, 0.05, 0.99)
    print(f"\n4. Investigating Phase 3D single-start behavior:")
    print(f"   Guess used: {single_start_guess}")

    for bound_val in [0.01, 0.05, 0.0001]:
        # Notice what bounds were used in scripts/run_phase3d_benchmark_evaluation.py:
        # bounds = [(a1_min, 10.0), (0.001, 100.0), (0.05, 10.0), (0.05, 10.0), (0.0001, 0.9999)]
        bounds_as_written = [
            (bound_val, 10.0),
            (0.001, 100.0),
            (0.05, 10.0),
            (0.05, 10.0),
            (0.0001, 0.9999)
        ]
        res = opt.minimize(
            fun=engine.negative_log_likelihood,
            x0=single_start_guess,
            args=(n_bin, e_bin, w_bin, 2),
            method="L-BFGS-B",
            bounds=bounds_as_written,
            options={"maxiter": 500, "ftol": 1e-9, "gtol": 1e-6},
        )
        print(f"   [Bound {bound_val}] fun={res.fun:.4f}, params={list(res.x)}, active bounds: {[i for i, (x, b) in enumerate(zip(res.x, bounds_as_written)) if abs(x - b[0]) < 1e-5 or abs(x - b[1]) < 1e-5]}")

    # Now let's test: What happens if we run multi-start or include the primary solution as starting point?
    print(f"\n5. Multi-start sensitivity with primary solution included in starts:")
    candidate_starts = [
        primary_vector,  # Start at primary solution
        (0.001, 0.0068, 0.2859, 0.4004, 0.85),
        (0.2339, 0.3354, 2.2487, 0.05, 0.99),
        (0.2, 0.1, 2.0, 4.0, 0.3333),
        (0.5, 1.5, 1.5, 0.5, 0.50),
    ]

    for bound_val in [0.0001, 0.001, 0.01, 0.05]:
        print(f"\n   --- Testing Lower Bound alpha >= {bound_val} across both components ---")
        # Apply lower bound to BOTH alpha1 and alpha2 to test symmetric component bounds
        sym_bounds = [
            (bound_val, 10.0),   # alpha1
            (0.001, 100.0),     # beta1
            (bound_val, 10.0),   # alpha2
            (0.001, 100.0),     # beta2
            (0.0001, 0.9999)    # w
        ]
        best_fun = float("inf")
        best_x = None
        best_start = None
        for s in candidate_starts:
            # Clip start vector to bounds
            s_clipped = [min(max(s[k], sym_bounds[k][0]), sym_bounds[k][1]) for k in range(5)]
            res = opt.minimize(
                fun=engine.negative_log_likelihood,
                x0=s_clipped,
                args=(n_bin, e_bin, w_bin, 2),
                method="L-BFGS-B",
                bounds=sym_bounds,
                options={"maxiter": 500, "ftol": 1e-9, "gtol": 1e-6},
            )
            if res.success and res.fun < best_fun:
                best_fun = res.fun
                best_x = res.x
                best_start = s

        print(f"   Best fun: {best_fun:.4f} (from start {best_start})")
        print(f"   Best params: {list(best_x)}")

if __name__ == "__main__":
    main()
