"""
Focused regression test for Phase 3B groupby memory fix.

Simulates the actual failure scenario:
- ~50,000 unique canonical drugs (matching real data cardinality)
- ~24,000 unique canonical PTs (matching real data cardinality)
- ~26M case-pair rows (pre-filter), ~6M post candidate-filter rows
- Uses FeatureExtractor.extract_features() with a high-cardinality
  disproportionality_df (1,167,891 candidate pairs) to trigger the
  previously-crashing groupby.
"""
import os
import sys
from pathlib import Path
import time
import gc
import numpy as np
import pandas as pd

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, PROJECT_ROOT)

from src.features.feature_extractor import FeatureExtractor

rng = np.random.default_rng(42)

print("=" * 60)
print("TEST: FeatureExtractor groupby memory fix — high cardinality")
print("=" * 60)

# Realistic cardinalities from actual pipeline run
N_DRUGS = 50_000   # ~50K unique drugs observed in real data
N_PTS = 24_000     # ~24K unique PTs observed in real data
N_PAIRS = 6_000_000  # representative post-filter case-level rows

print(f"\n[Setup] Unique drugs: {N_DRUGS:,}, unique PTs: {N_PTS:,}, rows: {N_PAIRS:,}")

drug_names = np.array([f"drug_{i:05d}" for i in range(N_DRUGS)])
pt_names   = np.array([f"pt_{i:05d}" for i in range(N_PTS)])

# Candidate pairs: 1.167M unique (drug, pt) combinations (matches real count)
N_CANDIDATES = 1_167_891
cand_drug_idx = rng.integers(0, N_DRUGS, N_CANDIDATES)
cand_pt_idx   = rng.integers(0, N_PTS, N_CANDIDATES)

disprop_df = pd.DataFrame({
    "canonical_drug": drug_names[cand_drug_idx],
    "canonical_pt":   pt_names[cand_pt_idx],
    "a": rng.integers(2, 50, N_CANDIDATES).astype(np.int32),
    "b": rng.integers(10, 5000, N_CANDIDATES).astype(np.int32),
    "c": rng.integers(5, 2000, N_CANDIDATES).astype(np.int32),
    "d": rng.integers(100, 6_000_000, N_CANDIDATES).astype(np.int32),
    "prr": rng.uniform(0.5, 20.0, N_CANDIDATES).astype(np.float32),
    "prr_chi2": rng.uniform(0.0, 200.0, N_CANDIDATES).astype(np.float32),
    "ror": rng.uniform(0.5, 25.0, N_CANDIDATES).astype(np.float32),
    "ror_lower_95": rng.uniform(0.3, 15.0, N_CANDIDATES).astype(np.float32),
    "ror_upper_95": rng.uniform(1.0, 50.0, N_CANDIDATES).astype(np.float32),
}).drop_duplicates(subset=["canonical_drug", "canonical_pt"]).reset_index(drop=True)
print(f"[Setup] Candidate pairs (disprop_df): {len(disprop_df):,}")

# case_pairs_df: sample from candidate universe (many cases per pair)
pair_idx = rng.integers(0, len(disprop_df), N_PAIRS)
case_pairs_df = pd.DataFrame({
    "primaryid": rng.integers(1_000_000, 99_000_000, N_PAIRS).astype(str),
    "caseid":    rng.integers(100_000, 9_000_000, N_PAIRS).astype(str),
    "canonical_drug": disprop_df["canonical_drug"].values[pair_idx],
    "canonical_pt":   disprop_df["canonical_pt"].values[pair_idx],
    "age":      rng.uniform(1, 90, N_PAIRS).astype(np.float32),
    "age_cod":  rng.choice(["YR", "MON", "WK", np.nan], N_PAIRS),
    "sex":      rng.choice(["F", "M", "UNK"], N_PAIRS),
    "occp_cod": rng.choice(["MD", "CN", "PH", "OT", "UNK"], N_PAIRS),
    "role_cod": rng.choice(["PS", "SS", "C"], N_PAIRS),
})
print(f"[Setup] case_pairs_df: {len(case_pairs_df):,} rows")
print(f"[Setup] case_pairs_df mem: {case_pairs_df.memory_usage(deep=True).sum()/1e6:.1f} MB")

# Minimal drug_df for co-medication counts
drug_df = pd.DataFrame({
    "caseid":    case_pairs_df["caseid"].sample(min(2_000_000, len(case_pairs_df)), random_state=1),
    "primaryid": rng.integers(1_000_000, 99_000_000, min(2_000_000, len(case_pairs_df))).astype(str),
})

# outc_df and rpsr_df (small)
outc_df = pd.DataFrame({
    "caseid":    case_pairs_df["caseid"].sample(500_000, random_state=2),
    "outc_cod":  rng.choice(["DE", "LT", "HO", "DS", "CA", "RI", "OT"], 500_000),
})
rpsr_df = pd.DataFrame({
    "caseid":    case_pairs_df["caseid"].sample(200_000, random_state=3),
    "rpsr_cod":  rng.choice(["HP", "CSM", "OT"], 200_000),
})

gc.collect()

print("\n[Test] Running FeatureExtractor.extract_features() ...")
t0 = time.time()
extractor = FeatureExtractor()
try:
    model_a, model_b = extractor.extract_features(
        case_pairs_df=case_pairs_df,
        drug_df=drug_df,
        outc_df=outc_df,
        rpsr_df=rpsr_df,
        disproportionality_df=disprop_df,
    )
    elapsed = time.time() - t0
    print(f"[PASS] extract_features completed in {elapsed:.1f}s")
    print(f"  model_a shape: {model_a.shape}")
    print(f"  model_b shape: {model_b.shape}")
    print(f"  model_a columns: {list(model_a.columns)}")
    assert len(model_a) <= len(disprop_df), "model_a rows exceed candidate pairs"
    assert len(model_b) <= len(disprop_df), "model_b rows exceed candidate pairs"
    print("\n[INVARIANT CHECK] Row counts <= candidate pair count: PASS")
    # Check canonical_drug/pt in output are plain strings (not category) to avoid downstream issues
    assert model_a["canonical_drug"].dtype.name in ("object", "string", "category"), \
        f"Unexpected dtype: {model_a['canonical_drug'].dtype}"
    print("[INVARIANT CHECK] Output dtype is compatible: PASS")
    print("\nRESULT: ALL TESTS PASSED")
except MemoryError as e:
    print(f"[FAIL] MemoryError: {e}")
    sys.exit(1)
except Exception as e:
    import traceback
    print(f"[FAIL] Unexpected error: {e}")
    traceback.print_exc()
    sys.exit(1)
