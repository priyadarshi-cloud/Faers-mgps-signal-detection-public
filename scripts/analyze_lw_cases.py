#!/usr/bin/env python3
import os
import pandas as pd
from pathlib import Path

BASE = Path("data/07_phase3a_continuous_ingestion/extracted")
SNAP = Path("data/09_phase3a4_dual_snapshots/as_of_2018_snapshot.csv")

df_snap = pd.read_csv(SNAP, usecols=["primaryid", "caseid", "quarter", "occp_cod"], dtype=str)
df_primary = df_snap[df_snap["quarter"].str.upper() <= "2018Q4"]

valid_primaryids = set(df_primary["primaryid"])
lw_primaryids = set(df_primary[df_primary["occp_cod"] == "LW"]["primaryid"])
lw_caseids = set(df_primary[df_primary["occp_cod"] == "LW"]["caseid"])

print(f"Total primary cases: {len(df_primary):,}")
print(f"Primary cases with occp_cod == 'LW': {len(lw_caseids):,}")

# Check RPSR for these cases across 20 quarters
hp_rpsr_cases = set()
quarters = sorted([d for d in os.listdir(BASE) if os.path.isdir(BASE / d) and d.upper() <= "2018Q4"])
for q in quarters:
    for root, _, files in os.walk(BASE / q):
        for f in files:
            if f.upper().startswith("RPSR") and f.lower().endswith(".txt"):
                df_rp = pd.read_csv(os.path.join(root, f), sep="$", encoding="latin-1", dtype=str, low_memory=False)
                df_rp.columns = [c.lower().strip() for c in df_rp.columns]
                if "primaryid" in df_rp.columns and "rpsr_cod" in df_rp.columns:
                    df_rp_valid = df_rp[df_rp["primaryid"].isin(valid_primaryids)]
                    hp_rows = df_rp_valid[df_rp_valid["rpsr_cod"].str.strip().str.upper() == "HP"]
                    if "caseid" in hp_rows.columns:
                        hp_rpsr_cases.update(hp_rows["caseid"].dropna().unique())

print(f"Total cases with rpsr_cod == 'HP': {len(hp_rpsr_cases):,}")
lw_and_hp = lw_caseids.intersection(hp_rpsr_cases)
print(f"Cases with occp_cod == 'LW' AND rpsr_cod == 'HP': {len(lw_and_hp):,}")
lw_only = len(lw_caseids) - len(lw_and_hp)
print(f"Cases with occp_cod == 'LW' AND rpsr_cod != 'HP' (affected cases): {lw_only:,} ({lw_only / len(df_primary) * 100:.3f}% of cohort)")
