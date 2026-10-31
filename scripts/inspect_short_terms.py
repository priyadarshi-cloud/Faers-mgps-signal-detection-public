"""
Context Inspector for Short Drug Abbreviations and ER/XR/XL Formulation Suffixes.

For each quarter, scans DRUG table for:
1. Short abbreviations (<=3 chars) in drugname / prod_ai fields
2. ER/XR/XL/CR/SR suffix patterns
"""

import os, re, sys
import pandas as pd
from collections import Counter

sys.path.insert(0, os.path.abspath("."))

quarters = [
    ("2014Q1", "data/01_raw/sample_quarters/2014q1/ascii/DRUG14Q1.txt"),
    ("2019Q1", "data/01_raw/sample_quarters/2019q1/ascii/DRUG19Q1.txt"),
    ("2023Q1", "data/01_raw/sample_quarters/2023q1/ascii/DRUG23Q1.txt"),
]

INSPECT_TERMS = {"CA", "E", "B1", "NI", "D", "B", "B2", "B6", "B12", "K", "C"}
FORMULATION_SUFFIX_RE = re.compile(r"\s+\b(ER|XR|XL|CR|SR|LA|SA|DR|IR|MR)\b\s*$", re.IGNORECASE)
NULL_SENTINELS = {"", "NAN", "UNKNOWN", "NULL", "NONE", "N/A", "NA", "UNK", "-"}

def strip_suffix(s):
    return FORMULATION_SUFFIX_RE.sub("", s).strip()

def extract_suffix(s):
    m = FORMULATION_SUFFIX_RE.search(s)
    return m.group(1).upper() if m else ""

for q_label, fpath in quarters:
    print(f"\n{'='*60}")
    print(f"CONTEXT INSPECTION: {q_label}")
    print(f"{'='*60}")
    if not os.path.exists(fpath):
        print(f"  [SKIP] Not found: {fpath}")
        continue
    df = pd.read_csv(fpath, sep="$", encoding="latin-1", low_memory=False, dtype=str)
    df.columns = [c.lower() for c in df.columns]
    total = len(df)
    has_prod_ai = "prod_ai" in df.columns
    has_role = "role_cod" in df.columns

    df["_dn"] = df.get("drugname", pd.Series([""], dtype=str)).fillna("").str.strip().str.upper()
    df["_pa"] = df["prod_ai"].fillna("").str.strip().str.upper() if has_prod_ai else pd.Series([""] * total, dtype=str)
    primary = df["_pa"].where(~df["_pa"].isin(NULL_SENTINELS), df["_dn"])
    primary = primary.fillna("").str.strip()

    # --- SHORT TERM INSPECTION ---
    print("\n[A] SHORT TERM INSPECTION (primary field <=3 chars, non-null)")
    short_mask = primary.str.len().le(3) & ~primary.isin(NULL_SENTINELS) & primary.str.len().gt(0)
    short_df = df[short_mask].copy()
    short_df["_prim"] = primary[short_mask]
    print(f"  Total rows: {short_mask.sum():,} ({100*short_mask.sum()/total:.4f}%)")
    freq = Counter(short_df["_prim"].tolist())
    print(f"  All terms: {dict(freq.most_common(25))}")

    for term in sorted(INSPECT_TERMS):
        n = (primary == term).sum()
        if n == 0:
            continue
        sub = df[primary == term]
        role_dist = sub["role_cod"].value_counts().to_dict() if has_role else {}
        pa_vals = sub["_pa"].value_counts().head(3).to_dict()
        dn_vals = sub["_dn"].value_counts().head(3).to_dict()
        print(f"\n  '{term}': n={n:,}")
        print(f"    role_cod: {role_dist}")
        print(f"    prod_ai top values: {pa_vals}")
        print(f"    drugname top values: {dn_vals}")
        show = [c for c in ["caseid","primaryid","role_cod","drugname","prod_ai","indi_pt"] if c in df.columns]
        for _, r in sub[show].head(3).iterrows():
            print(f"    sample: {dict(r)}")

    # --- ER/XR/XL SUFFIX INSPECTION ---
    print("\n[B] ER/XR/XL/CR/SR SUFFIX INSPECTION")
    suf_mask = primary.str.contains(FORMULATION_SUFFIX_RE) & ~primary.isin(NULL_SENTINELS)
    print(f"  primary field suffix rows: {suf_mask.sum():,} ({100*suf_mask.sum()/total:.3f}%)")
    if suf_mask.sum() > 0:
        sub = df[suf_mask].copy()
        sub["_prim"] = primary[suf_mask]
        sub["_suf"] = sub["_prim"].apply(extract_suffix)
        sub["_base"] = sub["_prim"].apply(strip_suffix)
        print(f"  Suffix freq: {dict(Counter(sub['_suf'].tolist()))}")
        risky = sub[sub["_base"].str.len().le(2)]
        print(f"  Risky (base <=2 chars after strip): {len(risky):,}")
        print(f"  Top 10 base names:")
        for base, cnt in Counter(sub["_base"].tolist()).most_common(10):
            print(f"    '{base}' ({cnt:,}) [suffix was '{sub[sub['_base']==base]['_suf'].iloc[0]}']")
        if has_role:
            print(f"  Role dist: {sub['role_cod'].value_counts().to_dict()}")

    # drugname-level suffix check
    dn_suf_mask = df["_dn"].str.contains(FORMULATION_SUFFIX_RE) & ~df["_dn"].isin(NULL_SENTINELS)
    print(f"  drugname field suffix rows: {dn_suf_mask.sum():,} ({100*dn_suf_mask.sum()/total:.3f}%)")
    if dn_suf_mask.sum() > 0:
        dn_bases = df[dn_suf_mask]["_dn"].apply(strip_suffix)
        print(f"  Top 10 drugname bases: {dict(Counter(dn_bases.tolist()).most_common(10))}")

print("\n=== INSPECTION COMPLETE ===")
