"""
Phase 3E -- Surrogate SHAP Analysis (DLL-Safe Version)
=======================================================
Uses sklearn RandomForestRegressor (no native DLL required on this host)
with SHAP TreeExplainer to explain log(EB05) predictions.

Application Control policy blocks LightGBM and sklearn.cluster Cython DLLs.
Workaround:
  - sklearn.cluster is pre-mocked before shap import to prevent DLL load.
  - RandomForestRegressor is used instead of LightGBM (pure sklearn, no extra DLL).
  - SHAP TreeExplainer works directly with sklearn RF trees.

EXPLICITLY LABELLED AS SURROGATE THROUGHOUT:
  - No positive training labels are used.
  - The surrogate predicts EBGM/EB05 scores, not clinical causality.
  - SHAP values explain the surrogate approximation of log(EB05) -- NOT
    underlying clinical or biological mechanisms.

Input (immutable -- read-only):
  data/13_phase3c2_mgps_scoring/phase3c2_scored_candidate_pairs.csv
  data/10_phase3b_features/m1_pure_contextual_features.csv
  data/10_phase3b_features/m2_multimodal_features.csv

Outputs (data/15_phase3e_explainable_ai/):
  phase3e_surrogate_metrics.json
  phase3e_shap_global_m1.csv
  phase3e_shap_global_m2.csv
  phase3e_shap_sample_m1.npz
  phase3e_shap_sample_m2.npz
  phase3e_high_signal_local_m2.csv
  phase3e_low_signal_local_m2.csv
  phase3e_signal_prioritisation.json
  phase3e_manifest.json
"""

import sys
import types

# -----------------------------------------------------------------------
# DLL-safety stub: pre-mock sklearn.cluster before shap triggers its import.
# This prevents the Application Control policy from blocking _reachability.pyd.
# -----------------------------------------------------------------------
_mock_cluster = types.ModuleType("sklearn.cluster")
_mock_cluster.KMeans = None
sys.modules["sklearn.cluster"] = _mock_cluster
for _sub in [
    "sklearn.cluster._hdbscan",
    "sklearn.cluster._hdbscan.hdbscan",
    "sklearn.cluster._hdbscan._reachability",
    "sklearn.cluster._kmeans",
]:
    sys.modules[_sub] = types.ModuleType(_sub)

# Now safe to import shap
import shap  # noqa: E402

import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import train_test_split

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
SCORED  = ROOT / "data/13_phase3c2_mgps_scoring/phase3c2_scored_candidate_pairs.csv"
M1_FILE = ROOT / "data/10_phase3b_features/m1_pure_contextual_features.csv"
M2_FILE = ROOT / "data/10_phase3b_features/m2_multimodal_features.csv"
OUT_DIR = ROOT / "data/15_phase3e_explainable_ai"
OUT_DIR.mkdir(parents=True, exist_ok=True)

EXPECTED_SCORED_SHA256 = "79d07631e65fef8a84cd14e3368c3ca379ec59f66088d3a5824d9dbf6ada5758"

RANDOM_SEED   = 42
SHAP_SAMPLE_N = 5_000     # rows for global SHAP (memory-efficient; reduced for speed)
RF_N_TREES    = 100       # RandomForest trees (reduced for speed; 100 sufficient for SHAP stability)
RF_MAX_DEPTH  = 10        # Max depth per tree
RF_MAX_FEAT   = "sqrt"    # Feature subsampling per split

LOCAL_TOP_N   = 30        # pairs for local SHAP explanations


# ---------------------------------------------------------------------------
def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_immutable():
    log.info("Verifying primary scored table SHA-256 (immutability check)...")
    actual = sha256_file(SCORED)
    assert actual.lower() == EXPECTED_SCORED_SHA256.lower(), (
        "IMMUTABILITY VIOLATION: SHA-256 mismatch!\n"
        "  Expected: %s\n  Actual:   %s" % (EXPECTED_SCORED_SHA256, actual)
    )
    log.info("  PASS  SHA-256 verified: %s...", EXPECTED_SCORED_SHA256[:16])
    return actual


# ---------------------------------------------------------------------------
def load_and_merge(model_name, feature_file):
    """Load scored pairs + feature file, compute log_eb05 target.

    NOTE: Only identity and target columns are loaded from SCORED to avoid
    column-name conflicts when the feature file (M2) also contains 'a', 'prr',
    'ror', etc. The feature file is authoritative for feature values.
    """
    log.info("Loading scored pairs (%s)...", model_name)
    scored = pd.read_csv(
        SCORED,
        usecols=["canonical_drug", "canonical_pt", "eb05", "ebgm",
                 "eb95", "rank_eb05"],
    )
    log.info("  Scored rows: %d", len(scored))

    feats = pd.read_csv(feature_file)
    log.info("  Feature rows (%s): %d", feature_file.name, len(feats))

    merged = scored.merge(feats, on=["canonical_drug", "canonical_pt"], how="inner")
    log.info("  Merged rows: %d", len(merged))

    merged["log_eb05"] = np.log(merged["eb05"].clip(lower=1e-6))
    return merged


# ---------------------------------------------------------------------------
def train_surrogate(df, feature_cols, model_label):
    """
    Train a RandomForest regression surrogate predicting log(EB05).
    EXPLICITLY A SURROGATE -- predicts scores, not clinical outcomes.
    """
    log.info("[%s] Preparing surrogate data (%d features)...",
             model_label, len(feature_cols))
    X = df[feature_cols].values.copy().astype(float)
    y = df["log_eb05"].values

    # Median imputation for NaNs
    col_medians = np.nanmedian(X, axis=0)
    nan_mask = np.isnan(X)
    n_imputed = int(nan_mask.sum())
    for j in range(X.shape[1]):
        X[nan_mask[:, j], j] = col_medians[j]
    log.info("  Imputed %d NaN values via column medians", n_imputed)

    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=0.20, random_state=RANDOM_SEED
    )
    log.info("  Train: %d  Test: %d", len(X_tr), len(X_te))

    log.info("[%s] Fitting RandomForest surrogate (n_trees=%d, max_depth=%d)...",
             model_label, RF_N_TREES, RF_MAX_DEPTH)
    t0 = time.time()
    model = RandomForestRegressor(
        n_estimators=RF_N_TREES,
        max_depth=RF_MAX_DEPTH,
        max_features=RF_MAX_FEAT,
        n_jobs=-1,
        random_state=RANDOM_SEED,
        verbose=0,
    )
    model.fit(X_tr, y_tr)
    elapsed = time.time() - t0
    log.info("  Fit complete in %.1fs", elapsed)

    y_tr_pred = model.predict(X_tr)
    y_te_pred = model.predict(X_te)
    train_r2   = float(r2_score(y_tr, y_tr_pred))
    test_r2    = float(r2_score(y_te, y_te_pred))
    train_rmse = float(np.sqrt(mean_squared_error(y_tr, y_tr_pred)))
    test_rmse  = float(np.sqrt(mean_squared_error(y_te, y_te_pred)))
    log.info("  Train R2=%.4f  RMSE=%.4f", train_r2, train_rmse)
    log.info("  Test  R2=%.4f  RMSE=%.4f", test_r2, test_rmse)

    y_all = model.predict(X)

    return {
        "model": model,
        "feature_cols": feature_cols,
        "col_medians": col_medians.tolist(),
        "X": X,
        "y_all_pred": y_all,
        "metrics": {
            "train_r2":   round(train_r2, 6),
            "test_r2":    round(test_r2, 6),
            "train_rmse": round(train_rmse, 6),
            "test_rmse":  round(test_rmse, 6),
            "n_train":    int(len(X_tr)),
            "n_test":     int(len(X_te)),
            "n_total":    int(len(X)),
            "n_imputed":  n_imputed,
            "fit_time_s": round(elapsed, 2),
            "algorithm":  "sklearn.RandomForestRegressor",
            "n_estimators": RF_N_TREES,
            "max_depth":    RF_MAX_DEPTH,
        },
    }


# ---------------------------------------------------------------------------
def compute_shap(result, model_label):
    """SHAP TreeExplainer on a random sample. Returns global importance df."""
    model       = result["model"]
    X_all       = result["X"]
    feature_cols = result["feature_cols"]

    rng = np.random.default_rng(RANDOM_SEED)
    idx = rng.choice(len(X_all), size=min(SHAP_SAMPLE_N, len(X_all)), replace=False)
    X_sample = X_all[idx]

    log.info("[%s] Computing SHAP (TreeExplainer, sample n=%d)...",
             model_label, len(idx))
    t0 = time.time()
    explainer   = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X_sample)
    elapsed = time.time() - t0
    log.info("  SHAP done in %.1fs", elapsed)

    mean_abs = np.abs(shap_values).mean(axis=0)
    gi = pd.DataFrame({"feature": feature_cols, "mean_abs_shap": mean_abs})
    gi = gi.sort_values("mean_abs_shap", ascending=False).reset_index(drop=True)
    gi["rank"] = range(1, len(gi) + 1)
    gi["mean_abs_shap"] = gi["mean_abs_shap"].round(6)

    log.info("  Top-5 features by mean|SHAP| (surrogate log-EB05 prediction):")
    for _, row in gi.head(5).iterrows():
        log.info("    %2d. %-35s %.6f", row["rank"], row["feature"], row["mean_abs_shap"])

    return {
        "global_importance": gi,
        "shap_values": shap_values,
        "sample_idx": idx,
        "shap_time_s": round(elapsed, 2),
    }


# ---------------------------------------------------------------------------
def compute_local_shap(result, df, model_label, top_n=LOCAL_TOP_N):
    """Local SHAP for the top-N and bottom-N EB05 pairs."""
    model        = result["model"]
    X_all        = result["X"]
    feature_cols = result["feature_cols"]

    eb05_vals = df["eb05"].values
    high_idx  = np.argsort(eb05_vals)[-top_n:][::-1]
    low_idx   = np.argsort(eb05_vals)[:top_n]

    def _build(indices, label):
        exp = shap.TreeExplainer(model)
        sv  = exp.shap_values(X_all[indices])
        rows = []
        for k, orig_i in enumerate(indices):
            row = {
                "canonical_drug":  df.iloc[orig_i]["canonical_drug"],
                "canonical_pt":    df.iloc[orig_i]["canonical_pt"],
                "eb05":            round(float(df.iloc[orig_i]["eb05"]), 4),
                "ebgm":            round(float(df.iloc[orig_i]["ebgm"]), 4),
                "log_eb05_actual": round(float(df.iloc[orig_i]["log_eb05"]), 4),
                "log_eb05_pred":   round(float(result["y_all_pred"][orig_i]), 4),
                "surrogate_set":   label,
            }
            for feat, sv_val in zip(feature_cols, sv[k]):
                row["shap_" + feat] = round(float(sv_val), 6)
            rows.append(row)
        return pd.DataFrame(rows)

    log.info("[%s] Local SHAP high-signal (%d pairs)...", model_label, top_n)
    high_df = _build(high_idx, "high_signal")
    log.info("[%s] Local SHAP low-signal (%d pairs)...", model_label, top_n)
    low_df  = _build(low_idx, "low_signal")
    return high_df, low_df


# ---------------------------------------------------------------------------
def signal_priority_summary(df):
    """Rank-based signal statistics -- no labels required."""
    total = len(df)
    eb05  = df["eb05"]
    out   = {"total_pairs": int(total), "eb05_thresholds": {}}

    for thresh in [1.0, 2.0, 3.0, 5.0, 10.0, 20.0]:
        n = int((eb05 >= thresh).sum())
        out["eb05_thresholds"]["eb05_ge_%d" % int(thresh)] = {
            "n_pairs": n,
            "pct_of_total": round(100.0 * n / total, 3),
        }

    sig_df = df[eb05 >= 2.0]
    top_drugs = (
        sig_df.groupby("canonical_drug")["eb05"]
        .agg(n_signals="count", max_eb05="max", median_eb05="median")
        .sort_values("n_signals", ascending=False)
        .head(20)
        .round(3)
    )
    out["top_20_drugs_by_signal_count"] = top_drugs.reset_index().to_dict("records")

    top_pts = (
        sig_df.groupby("canonical_pt")["eb05"]
        .agg(n_signals="count", max_eb05="max", median_eb05="median")
        .sort_values("n_signals", ascending=False)
        .head(20)
        .round(3)
    )
    out["top_20_pts_by_signal_count"] = top_pts.reset_index().to_dict("records")

    log.info("Signal prioritisation: %d pairs EB05>=2.0 (%.1f%%)",
             out["eb05_thresholds"]["eb05_ge_2"]["n_pairs"],
             out["eb05_thresholds"]["eb05_ge_2"]["pct_of_total"])
    return out


# ---------------------------------------------------------------------------
def main():
    t_start = time.time()
    log.info("=" * 70)
    log.info("Phase 3E -- Surrogate SHAP Analysis (DLL-Safe: sklearn RF + SHAP)")
    log.info("SURROGATE DISCLAIMER: explains log(EB05) scores, NOT clinical causality")
    log.info("shap=%s  sklearn=%s  numpy=%s",
             shap.__version__,
             __import__("sklearn").__version__,
             np.__version__)
    log.info("=" * 70)

    scored_sha = verify_immutable()

    manifest = {
        "phase": "Phase 3E -- Surrogate SHAP Analysis",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "surrogate_disclaimer": (
            "Surrogate model predicting log(EB05) MGPS scores. "
            "SHAP values explain the surrogate behaviour -- NOT clinical causality "
            "or biological mechanisms. No positive training labels used."
        ),
        "dll_safety_note": (
            "LightGBM and sklearn.cluster DLLs blocked by Windows Application Control policy. "
            "Using sklearn.RandomForestRegressor + sklearn.cluster mock stub."
        ),
        "historical_label_gate": "BLOCKED -- see phase3e_explainable_ai_report.md",
        "primary_scored_table_sha256": scored_sha,
        "random_seed": RANDOM_SEED,
        "shap_sample_n": SHAP_SAMPLE_N,
        "models": {},
        "files": {},
        "errors": [],
    }

    # --- M1: Pure contextual --------------------------------------------------
    M1_COLS = [
        "mean_age", "median_age", "age_std", "age_missing_ratio",
        "female_ratio", "male_ratio", "hp_reporter_ratio", "csm_reporter_ratio",
        "monotherapy_ratio", "mean_concomitant_count", "secondary_suspect_ratio",
    ]
    log.info("\n--- M1: Pure Contextual Surrogate (%d features) ---", len(M1_COLS))
    df_m1  = load_and_merge("M1", M1_FILE)
    res_m1 = train_surrogate(df_m1, M1_COLS, "M1")
    shap_m1 = compute_shap(res_m1, "M1")

    p = OUT_DIR / "phase3e_shap_global_m1.csv"
    shap_m1["global_importance"].to_csv(p, index=False)
    log.info("Saved: %s", p.name)

    p = OUT_DIR / "phase3e_shap_sample_m1.npz"
    np.savez_compressed(p,
        shap_values=shap_m1["shap_values"],
        sample_idx=shap_m1["sample_idx"],
        feature_names=np.array(M1_COLS))
    log.info("Saved: %s", p.name)

    manifest["models"]["M1_surrogate"] = {
        "description": "Surrogate predicting log(EB05) from 11 pure-contextual features",
        "algorithm": "sklearn.RandomForestRegressor",
        "features": M1_COLS,
        "metrics": res_m1["metrics"],
        "shap_time_s": shap_m1["shap_time_s"],
    }

    # --- M2: Multimodal -------------------------------------------------------
    M2_COLS = [
        "mean_age", "median_age", "age_std", "age_missing_ratio",
        "female_ratio", "male_ratio", "hp_reporter_ratio", "csm_reporter_ratio",
        "monotherapy_ratio", "mean_concomitant_count", "secondary_suspect_ratio",
        "a", "b", "c", "d", "prr", "prr_chi2", "ror", "ror_lower_95", "ror_upper_95",
    ]
    log.info("\n--- M2: Multimodal Surrogate (%d features) ---", len(M2_COLS))
    df_m2  = load_and_merge("M2", M2_FILE)
    res_m2 = train_surrogate(df_m2, M2_COLS, "M2")
    shap_m2 = compute_shap(res_m2, "M2")

    p = OUT_DIR / "phase3e_shap_global_m2.csv"
    shap_m2["global_importance"].to_csv(p, index=False)
    log.info("Saved: %s", p.name)

    p = OUT_DIR / "phase3e_shap_sample_m2.npz"
    np.savez_compressed(p,
        shap_values=shap_m2["shap_values"],
        sample_idx=shap_m2["sample_idx"],
        feature_names=np.array(M2_COLS))
    log.info("Saved: %s", p.name)

    high_df, low_df = compute_local_shap(res_m2, df_m2, "M2")
    p = OUT_DIR / "phase3e_high_signal_local_m2.csv"
    high_df.to_csv(p, index=False)
    p = OUT_DIR / "phase3e_low_signal_local_m2.csv"
    low_df.to_csv(p, index=False)
    log.info("Saved local SHAP CSVs")

    manifest["models"]["M2_surrogate"] = {
        "description": "Surrogate predicting log(EB05) from 20 multimodal features",
        "algorithm": "sklearn.RandomForestRegressor",
        "features": M2_COLS,
        "metrics": res_m2["metrics"],
        "shap_time_s": shap_m2["shap_time_s"],
    }

    # --- Signal prioritisation ------------------------------------------------
    log.info("\n--- Signal Prioritisation ---")
    sig = signal_priority_summary(df_m2)
    p = OUT_DIR / "phase3e_signal_prioritisation.json"
    with open(p, "w") as f:
        json.dump(sig, f, indent=2)
    log.info("Saved: %s", p.name)

    # --- Metrics JSON ---------------------------------------------------------
    metrics_out = {
        "M1_contextual": res_m1["metrics"],
        "M2_multimodal": res_m2["metrics"],
    }
    p = OUT_DIR / "phase3e_surrogate_metrics.json"
    with open(p, "w") as f:
        json.dump(metrics_out, f, indent=2)
    log.info("Saved: %s", p.name)

    # --- Manifest -------------------------------------------------------------
    total_elapsed = time.time() - t_start
    manifest["total_elapsed_s"] = round(total_elapsed, 2)
    manifest["files"] = {
        q.name: sha256_file(q)
        for q in OUT_DIR.iterdir() if q.is_file()
    }
    p = OUT_DIR / "phase3e_manifest.json"
    with open(p, "w") as f:
        json.dump(manifest, f, indent=2)
    log.info("Saved: %s", p.name)

    log.info("\n" + "=" * 70)
    log.info("Phase 3E Surrogate SHAP COMPLETE in %.1fs", total_elapsed)
    log.info("=" * 70)

    # --- Final summary (captured for report) ----------------------------------
    print("\n=== SURROGATE METRICS SUMMARY ===")
    print("M1 contextual (11 feat): Train R2=%.4f  Test R2=%.4f  Test RMSE=%.4f" % (
        res_m1["metrics"]["train_r2"], res_m1["metrics"]["test_r2"],
        res_m1["metrics"]["test_rmse"]))
    print("M2 multimodal (20 feat): Train R2=%.4f  Test R2=%.4f  Test RMSE=%.4f" % (
        res_m2["metrics"]["train_r2"], res_m2["metrics"]["test_r2"],
        res_m2["metrics"]["test_rmse"]))

    print("\n=== M1 TOP-5 GLOBAL SHAP (surrogate -- log-EB05 predictions) ===")
    for _, row in shap_m1["global_importance"].head(5).iterrows():
        print("  %2d. %-35s %.6f" % (row["rank"], row["feature"], row["mean_abs_shap"]))

    print("\n=== M2 TOP-10 GLOBAL SHAP (surrogate -- log-EB05 predictions) ===")
    for _, row in shap_m2["global_importance"].head(10).iterrows():
        print("  %2d. %-35s %.6f" % (row["rank"], row["feature"], row["mean_abs_shap"]))

    print("\n=== SIGNAL PRIORITISATION (EB05 thresholds, no labels) ===")
    for k, v in sig["eb05_thresholds"].items():
        print("  %-20s %9d pairs  (%5.2f%%)" % (k, v["n_pairs"], v["pct_of_total"]))

    print("\n=== TOP-10 DRUGS BY EB05>=2.0 SIGNAL COUNT ===")
    for rec in sig["top_20_drugs_by_signal_count"][:10]:
        print("  %-45s %4d signals  max_eb05=%7.2f" % (
            rec["canonical_drug"][:44], rec["n_signals"], rec["max_eb05"]))

    print("\n=== TOP-10 PTs BY EB05>=2.0 SIGNAL COUNT ===")
    for rec in sig["top_20_pts_by_signal_count"][:10]:
        print("  %-50s %4d signals  max_eb05=%7.2f" % (
            rec["canonical_pt"][:49], rec["n_signals"], rec["max_eb05"]))

    return 0


if __name__ == "__main__":
    sys.exit(main())
