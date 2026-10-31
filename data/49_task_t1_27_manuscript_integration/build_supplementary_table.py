import pandas as pd

# Load cluster bootstrap results
df_cb = pd.read_csv('data/45_task_t1_23_cluster_bootstrap_sensitivity/cluster_bootstrap_results.csv')

# Load alternative seeds results
df_seeds = pd.read_csv('data/46_task_t1_24_cluster_bootstrap_audit/alternative_seed_sensitivity.csv')

# We can prepare Supplementary Table S1:
# Let's save a clean, comprehensive CSV that covers all cluster-bootstrap sensitivity outputs
# We can include the 24 rows from df_cb with clear columns:
# benchmark, resampling_regime, resampling_unit, method, ap_point, ap_ci_display, roc_point, roc_ci_display,
# paired_delta_ap_point, paired_delta_ap_ci_display, paired_delta_ap_spans_zero,
# paired_delta_roc_point, paired_delta_roc_ci_display, paired_delta_roc_spans_zero

s1_cols = [
    'benchmark', 'resampling_regime', 'resampling_unit', 'method',
    'ap_point', 'ap_ci_2.5', 'ap_ci_97.5', 'ap_ci_display',
    'roc_point', 'roc_ci_2.5', 'roc_ci_97.5', 'roc_ci_display',
    'paired_delta_ap_point', 'paired_delta_ap_ci_2.5', 'paired_delta_ap_ci_97.5', 'paired_delta_ap_ci_display', 'paired_delta_ap_spans_zero',
    'paired_delta_roc_point', 'paired_delta_roc_ci_2.5', 'paired_delta_roc_ci_97.5', 'paired_delta_roc_ci_display', 'paired_delta_roc_spans_zero'
]

df_s1 = df_cb[s1_cols].copy()

# Add a section column or table identifier
df_s1.insert(0, 'table_section', 'Part A: Full Benchmark Sensitivity Across Resampling Regimes')

# Now add Part B: Random Seed Sensitivity for EU-ADR EB05 vs PRR AP (Drug Clustering)
# Map columns to match
seed_rows = []
for _, r in df_seeds.iterrows():
    seed_rows.append({
        'table_section': 'Part B: Random Seed Sensitivity Analysis (EU-ADR EB05 vs PRR AP, Drug-Clustered)',
        'benchmark': r['benchmark'],
        'resampling_regime': f"Drug-Clustered (Seed {r['seed']}, {r['role']})",
        'resampling_unit': 'drug',
        'method': 'EB05 vs PRR',
        'ap_point': None,
        'ap_ci_2.5': None,
        'ap_ci_97.5': None,
        'ap_ci_display': None,
        'roc_point': None,
        'roc_ci_2.5': None,
        'roc_ci_97.5': None,
        'roc_ci_display': None,
        'paired_delta_ap_point': r['point_delta'],
        'paired_delta_ap_ci_2.5': r['ci_lo'],
        'paired_delta_ap_ci_97.5': r['ci_hi'],
        'paired_delta_ap_ci_display': f"[{r['ci_lo']:.6f}, {r['ci_hi']:.6f}]",
        'paired_delta_ap_spans_zero': r['spans_zero'],
        'paired_delta_roc_point': None,
        'paired_delta_roc_ci_2.5': None,
        'paired_delta_roc_ci_97.5': None,
        'paired_delta_roc_ci_display': None,
        'paired_delta_roc_spans_zero': None
    })

df_part_b = pd.DataFrame(seed_rows)

df_s1_full = pd.concat([df_s1, df_part_b], ignore_index=True)
output_path = 'data/49_task_t1_27_manuscript_integration/supplementary_table_s1.csv'
df_s1_full.to_csv(output_path, index=False)
print(f"Created {output_path} with {len(df_s1_full)} rows ({len(df_s1)} in Part A, {len(df_part_b)} in Part B)")
