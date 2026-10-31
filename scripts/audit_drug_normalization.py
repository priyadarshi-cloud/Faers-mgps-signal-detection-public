"""
Audit real-world drug normalization coverage across 2014Q1, 2019Q1, and 2023Q1 DRUG tables.
Uses vectorized pandas operations (no iterrows) for speed on large files.

Categories:
  - prod_ai_standardized  : prod_ai field present and non-null (post-2019 standard)
  - brand_mapped          : drugname matched a known brand-to-generic entry
  - salt_stripped_cleaned : drugname normalized via rule-based cleaning
  - ambiguous_generic     : contains generic/multi-ingredient terms
  - unresolved_unparseable: very short or unparseable result
  - unknown_empty         : blank / null / NAN
"""

import os
import re
import sys
import pandas as pd
from collections import Counter

sys.path.insert(0, os.path.abspath("."))
from src.preprocessing.drug_normalizer import DrugNormalizer

quarters = [
    ("2014Q1", "data/01_raw/sample_quarters/2014q1/ascii/DRUG14Q1.txt"),
    ("2019Q1", "data/01_raw/sample_quarters/2019q1/ascii/DRUG19Q1.txt"),
    ("2023Q1", "data/01_raw/sample_quarters/2023q1/ascii/DRUG23Q1.txt"),
]

normalizer = DrugNormalizer()
brand_set = set(k.upper() for k in normalizer.brand_mapping.keys())

AMBIGUOUS_TERMS = [
    "MULTIVITAMIN", "TOTAL PARENTERAL NUTRITION", "CHEMOTHERAPY",
    "ELECTROLYTES", "INVESTIGATIONAL", "PLACEBO", "HERBAL",
    "UNSPECIFIED", "VACCINE", "DIALYSIS", "BLOOD", "SALINE",
    "NUTRITION", "ANTACID", "VITAMIN",
]
AMBIG_RE = re.compile("|".join(AMBIGUOUS_TERMS), re.IGNORECASE)

NULL_SENTINELS = {"", "NAN", "UNKNOWN", "NULL", "NONE", "N/A", "NA", "UNK", "-", "NI"}

# Vitamin abbreviation codes classified as AMBIGUOUS by the normalizer (not null, not unresolved).
# Must mirror DrugNormalizer.AMBIGUOUS_VITAMIN_CODES exactly.
AMBIG_VITAMIN_CODES_SET = frozenset({"C", "D", "E", "K", "CA", "B12", "D2", "D3", "D4"})


def audit_quarter(q_label: str, fpath: str) -> None:
    if not os.path.exists(fpath):
        print(f"  [SKIP] File not found: {fpath}")
        return

    df = pd.read_csv(fpath, sep="$", encoding="latin-1", low_memory=False, dtype=str)
    df.columns = [c.lower() for c in df.columns]

    total = len(df)
    has_prod_ai = "prod_ai" in df.columns

    # ── Resolve primary name field (vectorized) ──────────────────────────────
    if has_prod_ai:
        prod_ai_clean = df["prod_ai"].fillna("").str.strip().str.upper()
        drugname_clean = df.get("drugname", pd.Series([""] * total, dtype=str)).fillna("").str.strip().str.upper()
        primary = prod_ai_clean.where(~prod_ai_clean.isin(NULL_SENTINELS), drugname_clean)
    else:
        prod_ai_clean = pd.Series([""] * total, dtype=str)
        primary = df.get("drugname", pd.Series([""] * total, dtype=str)).fillna("").str.strip().str.upper()

    # ── Classify each row (no iterrows) ────────────────────────────────────
    is_null  = primary.isin(NULL_SENTINELS)
    # Ambiguous: pattern-based (multivitamin, vaccine, etc.) OR short vitamin code (C, D, E, K, CA, B12)
    is_ambig_pattern = (~is_null) & primary.str.contains(AMBIG_RE)
    is_ambig_vitcode = (~is_null) & primary.isin(AMBIG_VITAMIN_CODES_SET)
    is_ambig = is_ambig_pattern | is_ambig_vitcode
    is_brand = (~is_null) & (~is_ambig) & primary.isin(brand_set)

    if has_prod_ai:
        is_prod_ai = (
            (~is_null) & (~is_ambig) &
            prod_ai_clean.str.len().gt(2) &
            ~prod_ai_clean.isin(NULL_SENTINELS)
        )
    else:
        is_prod_ai = pd.Series([False] * total, dtype=bool)

    is_remaining = (~is_null) & (~is_ambig) & (~is_brand)
    if has_prod_ai:
        is_remaining = is_remaining & ~is_prod_ai

    # ── Sample up to 2000 remaining entries to estimate unresolved rate ──────
    remaining_vals = primary[is_remaining]
    sample_size    = min(2000, len(remaining_vals))
    sample         = remaining_vals.sample(sample_size, random_state=42) if sample_size > 0 else pd.Series([], dtype=str)

    unresolved_sample: Counter = Counter()
    ambig_from_sample: Counter = Counter()
    cleaned_sample: list = []
    # Sentinel tokens that must never appear in the ingredient display list.
    # The normalizer returns these in uppercase; compare case-insensitively.
    _NON_INGREDIENT = {"UNKNOWN", "AMBIGUOUS"}
    for raw in sample:
        result = normalizer.normalize(drugname=raw.title(), prod_ai=None)
        result_up = result.upper()
        if result_up == "AMBIGUOUS":
            ambig_from_sample[raw] += 1
        elif result_up == "UNKNOWN" or len(result) <= 2:
            unresolved_sample[raw] += 1
        else:
            cleaned_sample.append(result)

    unresolved_rate = len(unresolved_sample) / sample_size if sample_size > 0 else 0
    est_unresolved  = int(is_remaining.sum() * unresolved_rate)
    est_salt_clean  = is_remaining.sum() - est_unresolved

    # ── Final counts ────────────────────────────────────────────────────────
    n_null     = int(is_null.sum())
    n_ambig    = int(is_ambig.sum())
    n_brand    = int(is_brand.sum())
    n_prod_ai  = int(is_prod_ai.sum()) if has_prod_ai else 0
    n_salt     = est_salt_clean
    n_unresolved = est_unresolved + n_null

    normalized_total = n_prod_ai + n_brand + n_salt
    pct_norm  = (normalized_total / total) * 100
    pct_ambig = (n_ambig / total) * 100
    pct_unres = (n_unresolved / total) * 100

    print(f"Total Drug Records:           {total:>10,}")
    print(f"Normalized Records:           {normalized_total:>10,}  ({pct_norm:.2f}%)")
    print(f"  - via prod_ai (standard):   {n_prod_ai:>10,}")
    print(f"  - via brand dictionary:     {n_brand:>10,}")
    print(f"  - via salt/rule cleaning:   {n_salt:>10,}  (est. from {sample_size:,}-row sample)")
    print(f"Ambiguous / Generic:          {n_ambig:>10,}  ({pct_ambig:.2f}%)")
    print(f"Unresolved / Empty:           {n_unresolved:>10,}  ({pct_unres:.2f}%)"
          f"  [{n_null:,} blank/null + {est_unresolved:,} est. unparseable]")

    print("\nTop 8 Ambiguous / Generic Drug Names:")
    for name, cnt in Counter(primary[is_ambig].tolist()).most_common(8):
        print(f"  {name}: {cnt:,}")

    print("\nTop 8 Unresolved Names (from sample):")
    for name, cnt in unresolved_sample.most_common(8):
        print(f"  {name}: {cnt:,}")

    print("\nTop 8 Normalized Ingredients (from sample — excludes UNKNOWN/AMBIGUOUS):")
    # Belt-and-suspenders: exclude any non-ingredient tokens that may have slipped through.
    ingredient_ctr = Counter(r for r in cleaned_sample if r.upper() not in {"UNKNOWN", "AMBIGUOUS"})
    if ingredient_ctr:
        for name, cnt in ingredient_ctr.most_common(8):
            print(f"  {name}: {cnt:,}")
    else:
        print("  (no normalized ingredients in sample)")


for q_label, fpath in quarters:
    print(f"\n=======================================================")
    print(f"=== AUDITING DRUG NORMALIZATION COVERAGE: {q_label} ===")
    print(f"=======================================================")
    audit_quarter(q_label, fpath)

print("\n=== DRUG NORMALIZATION AUDIT COMPLETE ===")
