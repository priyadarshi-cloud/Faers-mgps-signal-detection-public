import pandas as pd

df_cb = pd.read_csv('data/45_task_t1_23_cluster_bootstrap_sensitivity/cluster_bootstrap_results.csv')
print("=== cluster_bootstrap_results.csv columns ===")
for c in df_cb.columns:
    print(" ", c)
print(f"Total rows: {len(df_cb)}")

df_seeds = pd.read_csv('data/46_task_t1_24_cluster_bootstrap_audit/alternative_seed_sensitivity.csv')
print("\n=== alternative_seed_sensitivity.csv columns ===")
for c in df_seeds.columns:
    print(" ", c)
print(f"Total rows: {len(df_seeds)}")
