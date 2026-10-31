"""
Phase 3C.2 — Full-Scale Conditional MGPS/EBGM Scoring Pipeline.

Stages:
1. preflight: Validate candidate pairs summary integrity, checksums, schema, and resources.
2. fit: Multi-start L-BFGS-B hyperparameter fitting under conditional likelihood (truncated_at=2)
         using logarithmic 2D binning. Saves fit_checkpoint.json.
3. score: Parallel quantile evaluation (EB05, EB95) and closed-form EBGM scoring across all 1.167M
          candidate pairs with chunked checkpointing.
4. validate: Comprehensive validation of output invariants, distributions, and manifest generation.

Run:
    python scripts/run_phase3c2_mgps_pipeline.py --stage all --workers 8
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import math
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from typing import Any, Dict, List, Optional, Tuple

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import numpy as np
import pandas as pd
import scipy.optimize as opt
import scipy.special as sp
import scipy.stats as st

from src.signal_detection.ebgm_engine import (
    EBGMEngine,
    MGPSHyperparameters,
    OptimizationResult,
)

# -----------------------------------------------------------------------------
# Configuration and Constants
# -----------------------------------------------------------------------------
CANDIDATE_SUMMARY_CSV = os.path.join(PROJECT_ROOT, "data", "10_phase3b_features", "candidate_pairs_summary.csv")
EXPECTED_SHA256 = "1ba9e480ad1d5783e036b395460a5b763d57df565a686b02c081cc9ff0742cec"
EXPECTED_ROW_COUNT = 1167891
TOTAL_COHORT_N = 6005839

OUTPUT_DIR = os.path.join(PROJECT_ROOT, "data", "13_phase3c2_mgps_scoring")
CHECKPOINT_DIR = os.path.join(OUTPUT_DIR, "checkpoints")
FIT_CHECKPOINT_FILE = os.path.join(OUTPUT_DIR, "fit_checkpoint.json")
PREFLIGHT_FILE = os.path.join(OUTPUT_DIR, "preflight_result.json")
FINAL_SCORED_CSV = os.path.join(OUTPUT_DIR, "phase3c2_scored_candidate_pairs.csv")
SUMMARY_METRICS_FILE = os.path.join(OUTPUT_DIR, "phase3c2_summary_metrics.json")
MANIFEST_FILE = os.path.join(OUTPUT_DIR, "phase3c2_manifest.json")

DIVERSE_INITIAL_GUESSES = [
    (0.2339, 0.3354, 2.2487, 0.05, 0.99),   # Pilot conditional regime
    (0.2, 0.1, 2.0, 4.0, 0.3333),           # openEBGM default
    (1.0, 1.0, 2.0, 1.0, 0.20),             # Unit mean baseline
    (0.05, 0.5, 3.0, 1.0, 0.05),            # Sparse baseline
    (0.5, 1.5, 1.5, 0.5, 0.50),             # Balanced
    (0.18, 0.53, 2.14, 0.57, 0.18),         # DuMouchel 1999 SRS
    (1.1, 0.5, 0.5, 0.01, 0.75),            # Pilot un-truncated regime
]


def sha256_file(path: str) -> str:
    """Compute SHA-256 hex digest of a file in streaming chunks."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while chunk := fh.read(8 * 1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


# -----------------------------------------------------------------------------
# Worker Function for Parallel Quantile Evaluation
# -----------------------------------------------------------------------------
def _quantile_worker_task(args: Tuple[int, np.ndarray, np.ndarray, Tuple[float, ...]]) -> Tuple[int, np.ndarray, np.ndarray]:
    """
    Worker task to evaluate EB05 and EB95 via Brent root finding on a batch.
    Args:
        chunk_idx: Index of chunk for tracking.
        sub_n: Observed counts.
        sub_e: Expected counts.
        theta_tuple: (alpha1, beta1, alpha2, beta2, w).
    Returns:
        (chunk_idx, eb05_array, eb95_array)
    """
    chunk_idx, sub_n, sub_e, theta_tuple = args
    theta = MGPSHyperparameters.from_tuple(theta_tuple)
    quants = EBGMEngine.calculate_posterior_quantiles(
        n=sub_n,
        e=sub_e,
        theta=theta,
        quantiles=(0.05, 0.95),
    )
    return chunk_idx, quants[0.05], quants[0.95]


# -----------------------------------------------------------------------------
# Stage 1: Preflight Verification
# -----------------------------------------------------------------------------
def run_preflight() -> Dict[str, Any]:
    print("\n" + "=" * 80)
    print("STAGE 1: PREFLIGHT VERIFICATION")
    print("=" * 80)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(CHECKPOINT_DIR, exist_ok=True)

    # 1. File existence and hash
    print(f"1. Checking input file: {CANDIDATE_SUMMARY_CSV} ...")
    if not os.path.exists(CANDIDATE_SUMMARY_CSV):
        raise FileNotFoundError(f"Input file not found: {CANDIDATE_SUMMARY_CSV}")

    t0 = time.time()
    computed_sha = sha256_file(CANDIDATE_SUMMARY_CSV)
    t_sha = time.time() - t0
    sha_matches = computed_sha == EXPECTED_SHA256
    print(f"   SHA-256: {computed_sha} (Computed in {t_sha:.2f}s, Match: {sha_matches})")
    if not sha_matches:
        raise ValueError(f"Input SHA-256 mismatch! Expected {EXPECTED_SHA256}, got {computed_sha}")

    # 2. Schema and counts
    print(f"2. Inspecting data schema and row count ...")
    t0 = time.time()
    df = pd.read_csv(CANDIDATE_SUMMARY_CSV)
    t_read = time.time() - t0
    n_rows = len(df)
    print(f"   Rows loaded: {n_rows:,} (in {t_read:.2f}s)")
    if n_rows != EXPECTED_ROW_COUNT:
        raise ValueError(f"Expected {EXPECTED_ROW_COUNT} rows, got {n_rows}")

    # 3. Key uniqueness
    print("3. Checking pair key uniqueness ...")
    n_unique_keys = df.groupby(["canonical_drug", "canonical_pt"]).ngroups
    keys_unique = n_unique_keys == n_rows
    print(f"   Unique keys: {n_unique_keys:,} (Duplicates: {n_rows - n_unique_keys})")
    if not keys_unique:
        raise ValueError(f"Duplicate pair keys detected in input!")

    # 4. Count sanity: a >= 2, e > 0
    print("4. Validating observed and expected count constraints ...")
    min_a = int(df["a"].min())
    max_a = int(df["a"].max())
    a_valid = min_a >= 2
    print(f"   Observed count range: a in [{min_a}, {max_a}] (a >= 2 satisfied: {a_valid})")
    if not a_valid:
        raise ValueError(f"Found counts a < 2 (minimum a = {min_a})")

    # Verify cohort N and expected counts
    a = df["a"].to_numpy(dtype=np.float64)
    b = df["b"].to_numpy(dtype=np.float64)
    c = df["c"].to_numpy(dtype=np.float64)
    e = (a + b) * (a + c) / float(TOTAL_COHORT_N)

    min_e = float(np.min(e))
    max_e = float(np.max(e))
    e_finite_positive = np.all(np.isfinite(e)) and min_e > 0.0
    print(f"   Expected count range: E in [{min_e:.8e}, {max_e:.2f}] (Strictly positive: {e_finite_positive})")
    if not e_finite_positive:
        raise ValueError("Non-positive or non-finite expected counts encountered!")

    # 5. Disk space check
    import shutil
    free_bytes = shutil.disk_usage(OUTPUT_DIR).free
    free_gb = free_bytes / (1024 ** 3)
    print(f"5. Disk space available: {free_gb:.1f} GB")
    if free_gb < 10.0:
        raise ValueError(f"Insufficient disk space ({free_gb:.1f} GB < 10 GB)")

    preflight_result = {
        "status": "PASS",
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "input_csv": CANDIDATE_SUMMARY_CSV,
        "input_sha256": computed_sha,
        "row_count": n_rows,
        "keys_unique": keys_unique,
        "min_a": min_a,
        "max_a": max_a,
        "min_e": min_e,
        "max_e": max_e,
        "total_cohort_n": TOTAL_COHORT_N,
        "free_disk_gb": free_gb,
    }

    with open(PREFLIGHT_FILE, "w", encoding="utf-8") as fh:
        json.dump(preflight_result, fh, indent=2)

    print("Preflight verification completed successfully.")
    return preflight_result


# -----------------------------------------------------------------------------
# Stage 2: Fit Conditional MGPS Model
# -----------------------------------------------------------------------------
def run_fit(force_refit: bool = False) -> Dict[str, Any]:
    print("\n" + "=" * 80)
    print("STAGE 2: CONDITIONAL MGPS HYPERPARAMETER FITTING (truncated_at=2)")
    print("=" * 80)

    if not force_refit and os.path.exists(FIT_CHECKPOINT_FILE):
        print(f"Existing fit checkpoint found at: {FIT_CHECKPOINT_FILE}")
        with open(FIT_CHECKPOINT_FILE, "r", encoding="utf-8") as fh:
            ckpt = json.load(fh)
        if ckpt.get("converged") and ckpt.get("input_sha256") == EXPECTED_SHA256:
            print("Checkpoint is valid and matches input SHA-256. Resuming using saved fit.")
            print(f"Fitted Hyperparameters: {ckpt['hyperparameters']}")
            return ckpt
        print("Existing checkpoint invalid or SHA mismatch. Re-fitting...")

    # Load data
    print("Loading candidate summary...")
    df = pd.read_csv(CANDIDATE_SUMMARY_CSV)
    a = df["a"].to_numpy(dtype=np.float64)
    b = df["b"].to_numpy(dtype=np.float64)
    c = df["c"].to_numpy(dtype=np.float64)
    e = (a + b) * (a + c) / float(TOTAL_COHORT_N)

    engine = EBGMEngine(seed=42)

    # Logarithmic squashing
    print("Squashing 1,167,891 pairs into 2D logarithmic bins (decimals=2)...")
    t0 = time.time()
    n_bin, e_bin, w_bin = engine.squash_counts_2d(a, e, decimals=2, use_log=True)
    t_squash = time.time() - t0
    n_bins = len(n_bin)
    compression = len(df) / float(n_bins)
    print(f"Compressed {len(df):,} pairs into {n_bins:,} bins ({compression:.2f}x compression) in {t_squash:.2f}s")

    # Multi-start L-BFGS-B fitting
    print(f"Launching multi-start L-BFGS-B optimization ({len(DIVERSE_INITIAL_GUESSES)} starts) under truncated_at=2...")
    t0 = time.time()
    res = engine.fit(
        n=n_bin,
        e=e_bin,
        weights=w_bin,
        initial_guesses=DIVERSE_INITIAL_GUESSES,
        compute_se=True,
        truncated_at=2,
    )
    t_fit = time.time() - t0
    print(f"Optimization completed in {t_fit:.2f}s. Converged: {res.converged}")

    if not res.converged or res.hyperparameters is None:
        raise RuntimeError(f"Conditional MGPS optimizer failed to converge! Message: {res.message}")

    hypers = res.hyperparameters
    print("\nFitted Prior Hyperparameters (Conditional on a >= 2):")
    print(f"  Component 1: shape alpha1 = {hypers.alpha1:.6f}, rate beta1 = {hypers.beta1:.6f} -> Mean1 = {hypers.mean_component1():.4f}")
    print(f"  Component 2: shape alpha2 = {hypers.alpha2:.6f}, rate beta2 = {hypers.beta2:.6f} -> Mean2 = {hypers.mean_component2():.4f}")
    print(f"  Mixture Weight w = {hypers.w:.6f} (Comp 1: {hypers.w*100:.2f}%, Comp 2: {(1-hypers.w)*100:.2f}%)")
    print(f"  Log-Likelihood: {res.log_likelihood:.4f}")
    print(f"  Iterations: {res.iterations}")
    print(f"  Standard Errors: {res.standard_errors}")

    # Sanity checks on fitted parameters
    for p_name, p_val in [("alpha1", hypers.alpha1), ("beta1", hypers.beta1), ("alpha2", hypers.alpha2), ("beta2", hypers.beta2)]:
        if p_val <= 0.051 or p_val >= 9.99:
            print(f"  [WARNING] Parameter {p_name} = {p_val:.4f} is near bounds [0.05, 10.0].")

    fit_record = {
        "converged": bool(res.converged),
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "truncated_at": 2,
        "input_sha256": EXPECTED_SHA256,
        "n_pairs": len(df),
        "n_bins": n_bins,
        "binning_method": "logarithmic_decimals_2",
        "squash_time_seconds": t_squash,
        "fit_time_seconds": t_fit,
        "hyperparameters": hypers.to_tuple(),
        "hyperparameters_dict": {
            "alpha1": hypers.alpha1,
            "beta1": hypers.beta1,
            "alpha2": hypers.alpha2,
            "beta2": hypers.beta2,
            "w": hypers.w,
            "mean_comp1": hypers.mean_component1(),
            "mean_comp2": hypers.mean_component2(),
        },
        "log_likelihood": float(res.log_likelihood),
        "iterations": int(res.iterations),
        "message": str(res.message),
        "starting_point": list(res.starting_point),
        "standard_errors": res.standard_errors,
        "all_restarts": res.all_restarts,
        "environment": {
            "python_version": sys.version,
            "scipy_version": sp.__version__ if hasattr(sp, "__version__") else "unknown",
            "numpy_version": np.__version__,
            "pandas_version": pd.__version__,
        },
    }

    with open(FIT_CHECKPOINT_FILE, "w", encoding="utf-8") as fh:
        json.dump(fit_record, fh, indent=2)

    print(f"Saved fit checkpoint to: {FIT_CHECKPOINT_FILE}")
    return fit_record


# -----------------------------------------------------------------------------
# Stage 3: Score All Candidate Pairs (Parallel + Checkpointing)
# -----------------------------------------------------------------------------
def run_score(
    fit_record: Dict[str, Any],
    n_workers: int = 8,
    chunk_size: int = 50000,
) -> pd.DataFrame:
    print("\n" + "=" * 80)
    print("STAGE 3: FULL-SCALE SCORING (1,167,891 CANDIDATE PAIRS)")
    print("=" * 80)

    theta_tuple = tuple(fit_record["hyperparameters"])
    theta = MGPSHyperparameters.from_tuple(theta_tuple)
    print(f"Scoring using conditional hyperparameters: {theta}")

    # Check if final output already exists and is complete
    if os.path.exists(FINAL_SCORED_CSV):
        print(f"Checking existing final scored file: {FINAL_SCORED_CSV} ...")
        df_existing = pd.read_csv(FINAL_SCORED_CSV)
        if len(df_existing) == EXPECTED_ROW_COUNT and "ebgm" in df_existing.columns and "eb05" in df_existing.columns:
            print(f"Final scored dataset already exists with {len(df_existing):,} valid rows. Skipping re-scoring.")
            return df_existing
        print("Existing file incomplete. Re-running scoring...")

    # Load full candidate table
    print("Loading candidate pairs summary...")
    t0 = time.time()
    df = pd.read_csv(CANDIDATE_SUMMARY_CSV)
    print(f"Loaded {len(df):,} rows in {time.time() - t0:.2f}s.")

    n_total = len(df)
    a = df["a"].to_numpy(dtype=np.float64)
    b = df["b"].to_numpy(dtype=np.float64)
    c = df["c"].to_numpy(dtype=np.float64)
    e = (a + b) * (a + c) / float(TOTAL_COHORT_N)

    # 1. Closed-form EBGM & Posterior Weight Q_n (Instantaneous vectorized evaluation)
    print("Computing closed-form EBGM and posterior weights (Q_n) across all pairs...")
    t0 = time.time()
    engine = EBGMEngine()
    qn = engine.calculate_posterior_weights(a, e, theta)
    ebgm = engine.calculate_ebgm(a, e, theta, q_n=qn)
    t_ebgm = time.time() - t0
    print(f"Closed-form EBGM evaluated on {n_total:,} pairs in {t_ebgm:.2f}s ({n_total/t_ebgm:,.0f} pairs/sec).")

    # 2. Parallel Quantile Evaluation (EB05 and EB95 via Brent Root-Finding)
    num_chunks = (n_total + chunk_size - 1) // chunk_size
    print(f"Evaluating posterior quantiles (EB05, EB95) in {num_chunks} chunks of {chunk_size:,} pairs using {n_workers} workers...")

    # Check existing completed chunk files
    existing_chunk_files = glob.glob(os.path.join(CHECKPOINT_DIR, "chunk_*.npz"))
    completed_chunks = set()
    chunk_data_map: Dict[int, pd.DataFrame] = {}

    for fpath in existing_chunk_files:
        try:
            data = np.load(fpath)
            c_idx = int(os.path.basename(fpath).replace("chunk_", "").replace(".npz", ""))
            chunk_df = pd.DataFrame({
                "row_idx": data["row_idx"],
                "eb05": data["eb05"],
                "eb95": data["eb95"],
            })
            if len(chunk_df) > 0 and "eb05" in chunk_df.columns and "eb95" in chunk_df.columns:
                completed_chunks.add(c_idx)
                chunk_data_map[c_idx] = chunk_df
        except Exception:
            pass

    print(f"Resuming: found {len(completed_chunks)} already completed chunks out of {num_chunks}.", flush=True)

    chunks_to_compute = []
    for c_idx in range(num_chunks):
        start_idx = c_idx * chunk_size
        end_idx = min(n_total, (c_idx + 1) * chunk_size)
        if c_idx not in completed_chunks:
            chunks_to_compute.append((c_idx, a[start_idx:end_idx], e[start_idx:end_idx], theta_tuple))

    if chunks_to_compute:
        print(f"Launching {len(chunks_to_compute)} pending chunks across {n_workers} worker processes...", flush=True)
        t_quant_start = time.time()
        processed_pairs = 0

        with ProcessPoolExecutor(max_workers=n_workers) as executor:
            for c_idx, eb05_vals, eb95_vals in executor.map(_quantile_worker_task, chunks_to_compute):
                start_idx = c_idx * chunk_size
                end_idx = min(n_total, (c_idx + 1) * chunk_size)

                row_idx_arr = np.arange(start_idx, end_idx, dtype=np.int64)
                chunk_df = pd.DataFrame({
                    "row_idx": row_idx_arr,
                    "eb05": eb05_vals,
                    "eb95": eb95_vals,
                })
                # Save chunk checkpoint via numpy compressed format (.npz)
                chunk_path = os.path.join(CHECKPOINT_DIR, f"chunk_{c_idx:04d}.npz")
                np.savez_compressed(chunk_path, row_idx=row_idx_arr, eb05=eb05_vals, eb95=eb95_vals)
                chunk_data_map[c_idx] = chunk_df

                processed_pairs += len(chunk_df)
                elapsed = time.time() - t_quant_start
                rate = processed_pairs / elapsed
                remaining = (len(chunks_to_compute) * chunk_size - processed_pairs) / rate if rate > 0 else 0
                print(f"  [Chunk {c_idx+1:02d}/{num_chunks:02d}] Saved {len(chunk_df):,} pairs | Elapsed: {elapsed:.1f}s | Speed: {rate:.0f} pairs/s | Est. remaining: {remaining/60:.1f}m", flush=True)

        print(f"All quantile chunks evaluated in {time.time() - t_quant_start:.2f}s.", flush=True)
    else:
        print("All quantile chunks already cached. Skipping worker execution.", flush=True)

    # Assemble all quantiles
    print("Assembling quantiles across all chunks...")
    sorted_chunks = [chunk_data_map[i] for i in range(num_chunks)]
    all_quant_df = pd.concat(sorted_chunks, ignore_index=True).sort_values("row_idx").reset_index(drop=True)

    if len(all_quant_df) != n_total:
        raise ValueError(f"Assembled quantiles row count mismatch: {len(all_quant_df)} vs {n_total}")

    # Build final DataFrame
    print("Constructing final enriched candidate pairs dataset...")
    df["e_expected"] = e
    df["ebgm_qn"] = qn
    df["ebgm"] = ebgm
    df["eb05"] = all_quant_df["eb05"].to_numpy()
    df["eb95"] = all_quant_df["eb95"].to_numpy()

    df["signal_eb05_conservative"] = df["eb05"] >= 2.0
    df["signal_eb05_permissive"] = df["eb05"] >= 1.0

    # Rankings
    print("Computing ranking statistics...")
    df["rank_ebgm"] = df["ebgm"].rank(ascending=False, method="min").astype(np.int64)
    df["rank_eb05"] = df["eb05"].rank(ascending=False, method="min").astype(np.int64)

    # Save to disk
    print(f"Saving full scored candidate dataset to: {FINAL_SCORED_CSV} ...")
    t0 = time.time()
    df.to_csv(FINAL_SCORED_CSV, index=False)
    print(f"Saved {len(df):,} rows ({os.path.getsize(FINAL_SCORED_CSV)/(1024**2):.1f} MB) in {time.time() - t0:.2f}s.")

    return df


# -----------------------------------------------------------------------------
# Stage 4: Output Validation & Summary Audit
# -----------------------------------------------------------------------------
def run_validate(df: pd.DataFrame, fit_record: Dict[str, Any]) -> Dict[str, Any]:
    print("\n" + "=" * 80)
    print("STAGE 4: OUTPUT INTEGRITY & STATISTICAL AUDIT")
    print("=" * 80)

    n_rows = len(df)
    print(f"1. Verifying row count: {n_rows:,} == {EXPECTED_ROW_COUNT} ...")
    assert n_rows == EXPECTED_ROW_COUNT, f"Row count mismatch: {n_rows} != {EXPECTED_ROW_COUNT}"

    # 2. Key uniqueness and 1-to-1 input correspondence
    print("2. Verifying key uniqueness and source input correspondence ...")
    n_keys = df.groupby(["canonical_drug", "canonical_pt"]).ngroups
    assert n_keys == n_rows, f"Duplicate keys detected: {n_rows - n_keys}"

    print(f"   Loading source candidate summary from {CANDIDATE_SUMMARY_CSV} ...")
    df_src = pd.read_csv(CANDIDATE_SUMMARY_CSV, usecols=["canonical_drug", "canonical_pt", "a", "b", "c", "d"])
    src_sha = sha256_file(CANDIDATE_SUMMARY_CSV)
    assert src_sha == EXPECTED_SHA256, f"Source SHA-256 mismatch: {src_sha} != {EXPECTED_SHA256}"
    assert len(df_src) == n_rows, f"Source row count mismatch: {len(df_src)} != {n_rows}"

    keys_src = df_src["canonical_drug"] + ":::" + df_src["canonical_pt"]
    keys_out = df["canonical_drug"] + ":::" + df["canonical_pt"]
    exact_key_alignment = bool((keys_src == keys_out).all())
    print(f"   Exact 1-to-1 sequential key alignment: {exact_key_alignment}")
    assert exact_key_alignment, "Output keys do not align 1-to-1 with input keys!"

    # Verify contingency cell consistency
    for cell_col in ["a", "b", "c", "d"]:
        if cell_col in df.columns:
            matches = bool((df[cell_col].to_numpy() == df_src[cell_col].to_numpy()).all())
            print(f"   Column '{cell_col}' matches source exactly: {matches}")
            assert matches, f"Cell count '{cell_col}' diverged from source!"

    # 3. Finiteness and validity
    print("3. Checking numerical finiteness across all scores ...")
    score_cols = ["e_expected", "ebgm", "eb05", "eb95", "ebgm_qn"]
    for col in score_cols:
        nans = int(df[col].isna().sum())
        infs = int(np.isinf(df[col]).sum())
        assert nans == 0, f"NaN values detected in {col}: {nans}"
        assert infs == 0, f"Inf values detected in {col}: {infs}"
        print(f"   Column {col:12s}: 0 NaNs, 0 Infs (min={df[col].min():.4e}, max={df[col].max():.4e})")

    # 4. Strict positivity and quantile ordering
    print("4. Validating quantile ordering invariants and diagnostic tolerances ...")
    eb05_positive = bool((df["eb05"] > 0.0).all())
    ebgm_positive = bool((df["ebgm"] > 0.0).all())
    eb95_positive = bool((df["eb95"] > 0.0).all())
    assert eb05_positive, "Detected non-positive EB05 values!"
    assert ebgm_positive, "Detected non-positive EBGM values!"
    assert eb95_positive, "Detected non-positive EB95 values!"

    viol_05_95 = int((df["eb05"] > df["eb95"] + 1e-6).sum())
    viol_05_ebgm = int((df["eb05"] > df["ebgm"] + 1e-6).sum())
    viol_ebgm_95 = int((df["ebgm"] > df["eb95"] + 1e-6).sum())
    print(f"   Strict positivity (EB05, EBGM, EB95 > 0): True")
    print(f"   Violations of EB05 <= EB95: {viol_05_95}")
    print(f"   Ordering diagnostics: EB05 > EBGM: {viol_05_ebgm}, EBGM > EB95: {viol_ebgm_95}")
    assert viol_05_95 == 0, "Quantile ordering violated: EB05 > EB95 detected!"

    # 5. Checkpoint files verification
    print("5. Verifying all 24 chunk checkpoint files ...")
    chunk_files = sorted(glob.glob(os.path.join(CHECKPOINT_DIR, "chunk_*.npz")))
    assert len(chunk_files) == 24, f"Expected 24 chunk files, found {len(chunk_files)}"
    total_chunk_rows = 0
    chunk_manifest: Dict[str, Any] = {}
    for c_path in chunk_files:
        data = np.load(c_path)
        c_rows = len(data["row_idx"])
        total_chunk_rows += c_rows
        fname = os.path.basename(c_path)
        chunk_manifest[fname] = {
            "sha256": sha256_file(c_path),
            "rows": c_rows,
            "size_bytes": os.path.getsize(c_path),
        }
    print(f"   Total rows in all 24 chunk files: {total_chunk_rows:,} == {n_rows:,}")
    assert total_chunk_rows == n_rows, f"Chunk rows sum mismatch: {total_chunk_rows} != {n_rows}"

    # 6. Summary distributions & Metrics
    print("6. Computing score distributions and signal thresholds ...")
    metrics: Dict[str, Any] = {
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_scored_pairs": n_rows,
        "input_sha256": EXPECTED_SHA256,
        "output_sha256": sha256_file(FINAL_SCORED_CSV),
        "fit_hyperparameters": fit_record["hyperparameters_dict"],
        "boundary_diagnostics": {
            "alpha1_near_bound": bool(fit_record["hyperparameters_dict"]["alpha1"] <= 0.0011),
            "beta1_value": fit_record["hyperparameters_dict"]["beta1"],
            "alpha2_value": fit_record["hyperparameters_dict"]["alpha2"],
            "beta2_value": fit_record["hyperparameters_dict"]["beta2"],
            "w_value": fit_record["hyperparameters_dict"]["w"],
        },
        "ordering_diagnostics": {
            "viol_05_95": viol_05_95,
            "viol_05_ebgm": viol_05_ebgm,
            "viol_ebgm_95": viol_ebgm_95,
        },
        "distributions": {},
        "signals": {
            "signal_eb05_conservative_count": int(df["signal_eb05_conservative"].sum()),
            "signal_eb05_conservative_pct": float(df["signal_eb05_conservative"].mean() * 100),
            "signal_eb05_permissive_count": int(df["signal_eb05_permissive"].sum()),
            "signal_eb05_permissive_pct": float(df["signal_eb05_permissive"].mean() * 100),
            "prr_signal_count": int(df["prr_signal"].sum()) if "prr_signal" in df.columns else None,
            "ror_signal_count": int(df["ror_signal"].sum()) if "ror_signal" in df.columns else None,
        },
    }

    for col in score_cols:
        vals = df[col]
        metrics["distributions"][col] = {
            "min": float(vals.min()),
            "p05": float(vals.quantile(0.05)),
            "p25": float(vals.quantile(0.25)),
            "median": float(vals.median()),
            "mean": float(vals.mean()),
            "p75": float(vals.quantile(0.75)),
            "p95": float(vals.quantile(0.95)),
            "p99": float(vals.quantile(0.99)),
            "max": float(vals.max()),
        }

    print("\nScore Distributions Summary:")
    for col, dist in metrics["distributions"].items():
        print(f"  {col:12s}: p05={dist['p05']:.4f}, median={dist['median']:.4f}, mean={dist['mean']:.4f}, p95={dist['p95']:.4f}, max={dist['max']:.2f}")

    print("\nSignal Counts (EB05 Thresholds):")
    print(f"  Conservative (EB05 >= 2.0): {metrics['signals']['signal_eb05_conservative_count']:,} ({metrics['signals']['signal_eb05_conservative_pct']:.2f}%)")
    print(f"  Permissive   (EB05 >= 1.0): {metrics['signals']['signal_eb05_permissive_count']:,} ({metrics['signals']['signal_eb05_permissive_pct']:.2f}%)")
    if metrics["signals"]["prr_signal_count"] is not None:
        print(f"  Baseline PRR Signals:      {metrics['signals']['prr_signal_count']:,} ({df['prr_signal'].mean()*100:.2f}%)")
    if metrics["signals"]["ror_signal_count"] is not None:
        print(f"  Baseline ROR Signals:      {metrics['signals']['ror_signal_count']:,} ({df['ror_signal'].mean()*100:.2f}%)")

    with open(SUMMARY_METRICS_FILE, "w", encoding="utf-8") as fh:
        json.dump(metrics, fh, indent=2)

    # Manifest of all generated artifacts
    manifest = {
        "phase": "Phase 3C.2",
        "description": "Full-scale conditional MGPS/EBGM scoring outputs and checkpoints",
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "status": "COMPLETED_VERIFIED",
        "artifacts": {
            FINAL_SCORED_CSV: {
                "sha256": metrics["output_sha256"],
                "size_bytes": os.path.getsize(FINAL_SCORED_CSV),
                "row_count": n_rows,
            },
            FIT_CHECKPOINT_FILE: {
                "sha256": sha256_file(FIT_CHECKPOINT_FILE),
                "size_bytes": os.path.getsize(FIT_CHECKPOINT_FILE),
            },
            PREFLIGHT_FILE: {
                "sha256": sha256_file(PREFLIGHT_FILE),
                "size_bytes": os.path.getsize(PREFLIGHT_FILE),
            },
            SUMMARY_METRICS_FILE: {
                "sha256": sha256_file(SUMMARY_METRICS_FILE),
                "size_bytes": os.path.getsize(SUMMARY_METRICS_FILE),
            },
        },
        "checkpoints": chunk_manifest,
    }

    with open(MANIFEST_FILE, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)

    print(f"\nManifest and metrics written to:\n  - {SUMMARY_METRICS_FILE}\n  - {MANIFEST_FILE}")
    return metrics


# -----------------------------------------------------------------------------
# Main Execution CLI
# -----------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 3C.2 Full-Scale Conditional MGPS Scoring Pipeline")
    parser.add_argument("--stage", choices=["preflight", "fit", "score", "validate", "all"], default="all")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--chunk-size", type=int, default=50000)
    parser.add_argument("--force-refit", action="store_true")
    args = parser.parse_args()

    print("=" * 80)
    print("PHASE 3C.2 — FULL-SCALE CONDITIONAL MGPS/EBGM SCORING PIPELINE")
    print(f"Target Universe: 1,167,891 Candidate Drug-Event Pairs (a >= 2)")
    print(f"Stage: {args.stage} | Workers: {args.workers} | Chunk Size: {args.chunk_size}")
    print("=" * 80)

    try:
        if args.stage in ("preflight", "all"):
            run_preflight()
        if args.stage == "preflight":
            print("\nPreflight check passed. Halting as requested (--stage preflight).")
            return 0

        if args.stage in ("fit", "all"):
            fit_record = run_fit(force_refit=args.force_refit)
        else:
            if not os.path.exists(FIT_CHECKPOINT_FILE):
                raise FileNotFoundError(f"Fit checkpoint not found: {FIT_CHECKPOINT_FILE}. Run --stage fit first.")
            with open(FIT_CHECKPOINT_FILE, "r", encoding="utf-8") as fh:
                fit_record = json.load(fh)
        if args.stage == "fit":
            print("\nModel fitting completed and verified. Halting as requested (--stage fit).")
            return 0

        if args.stage in ("score", "all"):
            df = run_score(fit_record, n_workers=args.workers, chunk_size=args.chunk_size)
        else:
            if not os.path.exists(FINAL_SCORED_CSV):
                raise FileNotFoundError(f"Scored dataset not found: {FINAL_SCORED_CSV}. Run --stage score first.")
            df = pd.read_csv(FINAL_SCORED_CSV)
        if args.stage == "score":
            print("\nScoring completed and verified. Halting as requested (--stage score).")
            return 0

        if args.stage in ("validate", "all"):
            run_validate(df, fit_record)

        print("\n" + "=" * 80)
        print("PHASE 3C.2 PIPELINE EXECUTION SUCCESSFUL — ALL STAGES VERIFIED")
        print("=" * 80)
        return 0

    except Exception as exc:
        print(f"\n[PIPELINE FAILURE] Execution halted with error: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
