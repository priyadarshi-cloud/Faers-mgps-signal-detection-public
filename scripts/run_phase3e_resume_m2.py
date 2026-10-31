"""
Phase 3E -- Resume from M2 (M1 outputs already saved)
======================================================
M1 surrogate + SHAP completed successfully. This script resumes from M2:
  - Loads M2 features + scored pairs
  - Trains RF surrogate for M2
  - Computes M2 global SHAP
  - Computes M2 local SHAP (high/low signal pairs)
  - Signal prioritisation summary
  - Merges with existing M1 metrics and saves final manifest + report data

SURROGATE DISCLAIMER: SHAP values explain the surrogate's approximation of
log(EB05) scores -- NOT clinical causality or biological mechanisms.
No positive training labels were used at any stage.
"""

import sys
import types

# DLL-safety stub: mock sklearn.cluster before shap triggers its import
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

import shap

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

ROOT    = Path(__file__).resolve().parent.parent
SCORED  = ROOT / "data/13_phase3c2_mgps_scoring/phase3c2_scored_candidate_pairs.csv"
M2_FILE = ROOT / "data/10_phase3b_features/m2_multimodal_features.csv"
OUT_DIR = ROOT / "data/15_phase3e_explainable_ai"
OUT_DIR.mkdir(parents=True, exist_ok=True)

EXPECTED_SHA256 = "79d07631e65fef8a84cd14e3368c3ca379ec59f66088d3a5824d9dbf6ada5758"
RANDOM_SEED  = 42
SHAP_SAMPLE  = 5_000
RF_N_TREES   = 100
RF_MAX_DEPTH = 10
LOCAL_TOP_N  = 30


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_m2():
    """Load scored targets + M2 features, avoiding column-name conflicts."""
    log.info("Loading scored targets (eb05/ebgm only)...")
    scored = pd.read_csv(SCORED, usecols=[
        "canonical_drug", "canonical_pt", "eb05", "ebgm", "eb95", "rank_eb05"
    ])
    log.info("  Scored rows: %d", len(scored))
    log.info("Loading M2 features...")
    feats = pd.read_csv(M2_FILE)
    log.info("  Feature rows: %d  Columns: %s", len(feats), list(feats.columns))
    merged = scored.merge(feats, on=["canonical_drug", "canonical_pt"], how="inner")
    log.info("  Merged rows: %d", len(merged))
    merged["log_eb05"] = np.log(merged["eb05"].clip(lower=1e-6))
    return merged


def train_surrogate(df, feature_cols, label):
    log.info("[%s] Preparing surrogate (%d features)...", label, len(feature_cols))
    # Verify all feature cols are present
    missing = [c for c in feature_cols if c not in df.columns]
    if missing:
        raise KeyError("Missing feature columns in merged dataframe: %s\nAvailable: %s" % (
            missing, list(df.columns)))

    X = df[feature_cols].values.copy().astype(float)
    y = df["log_eb05"].values

    col_medians = np.nanmedian(X, axis=0)
    nan_mask = np.isnan(X)
    n_imputed = int(nan_mask.sum())
    for j in range(X.shape[1]):
        X[nan_mask[:, j], j] = col_medians[j]
    log.info("  Imputed %d NaN values via column medians", n_imputed)

    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.20, random_state=RANDOM_SEED)
    log.info("  Train: %d  Test: %d", len(X_tr), len(X_te))

    log.info("[%s] Fitting RF surrogate (n_trees=%d, max_depth=%d)...",
             label, RF_N_TREES, RF_MAX_DEPTH)
    t0 = time.time()
    model = RandomForestRegressor(
        n_estimators=RF_N_TREES, max_depth=RF_MAX_DEPTH,
        max_features="sqrt", n_jobs=-1, random_state=RANDOM_SEED, verbose=0
    )
    model.fit(X_tr, y_tr)
    elapsed = time.time() - t0
    log.info("  Fit complete in %.1fs", elapsed)

    tr_r2   = float(r2_score(y_tr, model.predict(X_tr)))
    te_r2   = float(r2_score(y_te, model.predict(X_te)))
    tr_rmse = float(np.sqrt(mean_squared_error(y_tr, model.predict(X_tr))))
    te_rmse = float(np.sqrt(mean_squared_error(y_te, model.predict(X_te))))
    log.info("  Train R2=%.4f RMSE=%.4f  |  Test R2=%.4f RMSE=%.4f",
             tr_r2, tr_rmse, te_r2, te_rmse)

    return {
        "model": model, "feature_cols": feature_cols,
        "col_medians": col_medians.tolist(),
        "X": X, "y_all_pred": model.predict(X),
        "metrics": {
            "train_r2": round(tr_r2, 6), "test_r2": round(te_r2, 6),
            "train_rmse": round(tr_rmse, 6), "test_rmse": round(te_rmse, 6),
            "n_train": int(len(X_tr)), "n_test": int(len(X_te)),
            "n_total": int(len(X)), "n_imputed": n_imputed,
            "fit_time_s": round(elapsed, 2),
            "algorithm": "sklearn.RandomForestRegressor",
            "n_estimators": RF_N_TREES, "max_depth": RF_MAX_DEPTH,
        }
    }


def compute_shap(result, label):
    model, X_all = result["model"], result["X"]
    feature_cols = result["feature_cols"]
    rng = np.random.default_rng(RANDOM_SEED)
    idx = rng.choice(len(X_all), size=min(SHAP_SAMPLE, len(X_all)), replace=False)
    log.info("[%s] Computing SHAP TreeExplainer (sample n=%d)...", label, len(idx))
    t0 = time.time()
    exp = shap.TreeExplainer(model)
    sv  = exp.shap_values(X_all[idx])
    elapsed = time.time() - t0
    log.info("  SHAP done in %.1fs", elapsed)

    gi = pd.DataFrame({
        "feature": feature_cols,
        "mean_abs_shap": np.abs(sv).mean(axis=0)
    }).sort_values("mean_abs_shap", ascending=False).reset_index(drop=True)
    gi["rank"] = range(1, len(gi) + 1)
    gi["mean_abs_shap"] = gi["mean_abs_shap"].round(6)

    log.info("  Top-10 features by mean|SHAP|:")
    for _, row in gi.head(10).iterrows():
        log.info("    %2d. %-35s %.6f", row["rank"], row["feature"], row["mean_abs_shap"])

    return {"global_importance": gi, "shap_values": sv, "sample_idx": idx,
            "shap_time_s": round(elapsed, 2)}


def compute_local_shap(result, df, label):
    model, X_all = result["model"], result["X"]
    feature_cols = result["feature_cols"]
    eb05 = df["eb05"].values
    high_idx = np.argsort(eb05)[-LOCAL_TOP_N:][::-1]
    low_idx  = np.argsort(eb05)[:LOCAL_TOP_N]

    def _build(indices, tag):
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
                "surrogate_set":   tag,
            }
            for feat, sv_val in zip(feature_cols, sv[k]):
                row["shap_" + feat] = round(float(sv_val), 6)
            rows.append(row)
        return pd.DataFrame(rows)

    log.info("[%s] Local SHAP high-signal (%d pairs)...", label, LOCAL_TOP_N)
    high_df = _build(high_idx, "high_signal")
    log.info("[%s] Local SHAP low-signal (%d pairs)...", label, LOCAL_TOP_N)
    low_df  = _build(low_idx,  "low_signal")
    return high_df, low_df


def signal_summary(df):
    total = len(df)
    eb05  = df["eb05"]
    out   = {"total_pairs": int(total), "eb05_thresholds": {}}
    for thresh in [1.0, 2.0, 3.0, 5.0, 10.0, 20.0]:
        n = int((eb05 >= thresh).sum())
        out["eb05_thresholds"]["eb05_ge_%d" % int(thresh)] = {
            "n_pairs": n, "pct_of_total": round(100.0 * n / total, 3)
        }
    sig_df = df[eb05 >= 2.0]
    top_drugs = (sig_df.groupby("canonical_drug")["eb05"]
        .agg(n_signals="count", max_eb05="max", median_eb05="median")
        .sort_values("n_signals", ascending=False).head(20).round(3))
    out["top_20_drugs_by_signal_count"] = top_drugs.reset_index().to_dict("records")
    top_pts = (sig_df.groupby("canonical_pt")["eb05"]
        .agg(n_signals="count", max_eb05="max", median_eb05="median")
        .sort_values("n_signals", ascending=False).head(20).round(3))
    out["top_20_pts_by_signal_count"] = top_pts.reset_index().to_dict("records")
    log.info("Signal prioritisation: %d pairs EB05>=2.0 (%.1f%% of universe)",
             out["eb05_thresholds"]["eb05_ge_2"]["n_pairs"],
             out["eb05_thresholds"]["eb05_ge_2"]["pct_of_total"])
    return out


def main():
    t0 = time.time()
    log.info("=" * 70)
    log.info("Phase 3E RESUME -- M2 Surrogate + SHAP + Signal Prioritisation")
    log.info("shap=%s  sklearn=%s  numpy=%s",
             shap.__version__, __import__("sklearn").__version__, np.__version__)
    log.info("M1 outputs already saved; resuming from M2.")
    log.info("=" * 70)

    # Verify primary table unchanged
    log.info("Verifying primary scored table...")
    actual_sha = sha256_file(SCORED)
    assert actual_sha.lower() == EXPECTED_SHA256.lower(), "SHA-256 mismatch!"
    log.info("  PASS  %s...", actual_sha[:16])

    # Load existing M1 metrics
    m1_metrics_path = OUT_DIR / "phase3e_surrogate_metrics.json"
    if m1_metrics_path.exists():
        with open(m1_metrics_path) as f:
            existing_metrics = json.load(f)
        m1_metrics = existing_metrics.get("M1_contextual", {})
        log.info("  Loaded existing M1 metrics: Train R2=%.4f  Test R2=%.4f",
                 m1_metrics.get("train_r2", 0), m1_metrics.get("test_r2", 0))
    else:
        # Reconstruct from known values
        m1_metrics = {
            "train_r2": 0.2362, "test_r2": 0.2300,
            "train_rmse": 1.4705, "test_rmse": 1.4763,
            "n_train": 934312, "n_test": 233579, "n_total": 1167891,
            "n_imputed": 373234, "fit_time_s": 93.3,
            "algorithm": "sklearn.RandomForestRegressor",
            "n_estimators": 100, "max_depth": 10,
            "note": "Reconstructed from task-1246 log (metrics file not found)"
        }
        log.info("  M1 metrics reconstructed from log (metrics file absent)")

    # M2 feature columns
    M2_COLS = [
        "mean_age", "median_age", "age_std", "age_missing_ratio",
        "female_ratio", "male_ratio", "hp_reporter_ratio", "csm_reporter_ratio",
        "monotherapy_ratio", "mean_concomitant_count", "secondary_suspect_ratio",
        "a", "b", "c", "d", "prr", "prr_chi2", "ror", "ror_lower_95", "ror_upper_95",
    ]

    log.info("\n--- M2: Multimodal Surrogate (%d features) ---", len(M2_COLS))
    df_m2  = load_m2()
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
    p = OUT_DIR / "phase3e_high_signal_local_m2.csv"; high_df.to_csv(p, index=False)
    p = OUT_DIR / "phase3e_low_signal_local_m2.csv";  low_df.to_csv(p, index=False)
    log.info("Saved local SHAP CSVs")

    # Signal prioritisation
    log.info("\n--- Signal Prioritisation ---")
    sig = signal_summary(df_m2)
    p = OUT_DIR / "phase3e_signal_prioritisation.json"
    with open(p, "w") as f:
        json.dump(sig, f, indent=2)
    log.info("Saved: %s", p.name)

    # Combined metrics
    metrics_out = {
        "M1_contextual": m1_metrics,
        "M2_multimodal": res_m2["metrics"],
    }
    p = OUT_DIR / "phase3e_surrogate_metrics.json"
    with open(p, "w") as f:
        json.dump(metrics_out, f, indent=2)
    log.info("Saved: %s", p.name)

    # Manifest
    total_elapsed = time.time() - t0
    manifest = {
        "phase": "Phase 3E -- Surrogate SHAP Analysis",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "surrogate_disclaimer": (
            "Surrogate models predict log(EB05) MGPS scores. SHAP values explain "
            "surrogate behaviour -- NOT clinical causality. No positive labels used."
        ),
        "dll_safety_note": (
            "LightGBM blocked by Windows Application Control policy. "
            "Using sklearn.RandomForestRegressor + sklearn.cluster mock stub."
        ),
        "historical_label_gate": "BLOCKED -- see phase3e_explainable_ai_report.md",
        "primary_scored_table_sha256": actual_sha,
        "random_seed": RANDOM_SEED,
        "shap_sample_n": SHAP_SAMPLE,
        "models": {
            "M1_surrogate": {
                "description": "Surrogate predicting log(EB05) from 11 pure-contextual features",
                "algorithm": "sklearn.RandomForestRegressor",
                "features": [
                    "mean_age","median_age","age_std","age_missing_ratio",
                    "female_ratio","male_ratio","hp_reporter_ratio","csm_reporter_ratio",
                    "monotherapy_ratio","mean_concomitant_count","secondary_suspect_ratio"
                ],
                "metrics": m1_metrics,
            },
            "M2_surrogate": {
                "description": "Surrogate predicting log(EB05) from 20 multimodal features",
                "algorithm": "sklearn.RandomForestRegressor",
                "features": M2_COLS,
                "metrics": res_m2["metrics"],
                "shap_time_s": shap_m2["shap_time_s"],
            }
        },
        "total_elapsed_s": round(total_elapsed, 2),
        "files": {
            q.name: sha256_file(q)
            for q in OUT_DIR.iterdir() if q.is_file()
        },
        "errors": [],
    }
    p = OUT_DIR / "phase3e_manifest.json"
    with open(p, "w") as f:
        json.dump(manifest, f, indent=2)
    log.info("Saved: %s", p.name)

    log.info("\n" + "=" * 70)
    log.info("Phase 3E COMPLETE (M2 resume) in %.1fs", total_elapsed)
    log.info("=" * 70)

    # Summary output for report population
    print("\n=== SURROGATE METRICS SUMMARY ===")
    print("M1 contextual (11 feat): Train R2=%.4f  Test R2=%.4f  Test RMSE=%.4f" % (
        m1_metrics["train_r2"], m1_metrics["test_r2"], m1_metrics["test_rmse"]))
    print("M2 multimodal (20 feat): Train R2=%.4f  Test R2=%.4f  Test RMSE=%.4f" % (
        res_m2["metrics"]["train_r2"], res_m2["metrics"]["test_r2"],
        res_m2["metrics"]["test_rmse"]))

    m1_gi_path = OUT_DIR / "phase3e_shap_global_m1.csv"
    if m1_gi_path.exists():
        m1_gi = pd.read_csv(m1_gi_path)
        print("\n=== M1 TOP-5 GLOBAL SHAP (surrogate -- log-EB05 predictions) ===")
        for _, row in m1_gi.head(5).iterrows():
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
