#!/usr/bin/env python3
import pandas as pd
from pathlib import Path

snap_path = Path("data/09_phase3a4_dual_snapshots/as_of_2018_snapshot.csv")
df_snap = pd.read_csv(snap_path, usecols=["quarter", "occp_cod"])
df_primary = df_snap[df_snap["quarter"].str.upper() <= "2018Q4"]
print("Total primary cases:", len(df_primary))
print("occp_cod value counts in primary cohort (N=6,005,839):")
vc = df_primary["occp_cod"].value_counts(dropna=False)
print(vc)
print("\nPercentage breakdown:")
print((vc / len(df_primary) * 100).round(3))
